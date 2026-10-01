"""RPi drivers against a fake lgpio, so they run anywhere."""
import asyncio
import sys
import threading
import types
import pytest
from parade.config.models import GPIOInputConfig, RelayOutputConfig


class FakeLgpio(types.ModuleType):
    SET_PULL_UP, SET_PULL_DOWN, SET_PULL_NONE = 1, 2, 4
    BOTH_EDGES = 3

    class error(Exception):
        pass

    def __init__(self):
        super().__init__("lgpio")
        self.levels: dict[int, int] = {}
        self.claims: dict[int, tuple] = {}
        self.debounce: dict[int, int] = {}
        self.callbacks: dict[int, object] = {}
        self.writes: list[tuple[int, int]] = []
        self.closed = False

    def gpiochip_open(self, chip):
        return 7

    def gpiochip_close(self, h):
        self.closed = True

    def gpio_claim_alert(self, h, pin, edges, flags):
        if pin in self.claims:
            raise self.error("GPIO busy")
        self.claims[pin] = ("alert", flags)
        self.levels.setdefault(pin, 1 if flags == self.SET_PULL_UP else 0)

    def gpio_claim_output(self, h, pin, level):
        self.claims[pin] = ("output", level)
        self.levels[pin] = level

    def gpio_set_debounce_micros(self, h, pin, us):
        self.debounce[pin] = us

    def gpio_read(self, h, pin):
        return self.levels[pin]

    def gpio_write(self, h, pin, level):
        self.levels[pin] = level
        self.writes.append((pin, level))

    def gpio_free(self, h, pin):
        self.claims.pop(pin, None)

    def callback(self, h, pin, edge, func):
        self.callbacks[pin] = func
        return types.SimpleNamespace(cancel=lambda: None)


@pytest.fixture
def fake_lgpio(monkeypatch):
    fake = FakeLgpio()
    monkeypatch.setitem(sys.modules, "lgpio", fake)
    return fake


async def test_gpio_input_publishes_from_callback_thread(fake_lgpio, event_bus):
    from parade.gpio.rpi import RPiGPIO

    cfg = GPIOInputConfig(id="btn", pin=27, pull="up", active_low=True, debounce_ms=50)
    gpio = RPiGPIO([cfg], event_bus)
    seen = []

    async def on(ev):
        seen.append(ev)

    event_bus.subscribe("gpio_changed", on)
    await gpio.start()
    assert fake_lgpio.claims[27] == ("alert", FakeLgpio.SET_PULL_UP)
    assert fake_lgpio.debounce[27] == 50_000
    assert gpio.get_state("btn") is False  # pulled high = idle

    t = threading.Thread(target=fake_lgpio.callbacks[27], args=(0, 27, 0, 0))
    t.start(); t.join()
    await asyncio.sleep(0.02)
    assert len(seen) == 1 and seen[0].active is True and seen[0].state is False
    assert gpio.get_state("btn") is True

    # repeated level and watchdog (level 2) are ignored
    fake_lgpio.callbacks[27](0, 27, 0, 0)
    fake_lgpio.callbacks[27](0, 27, 2, 0)
    await asyncio.sleep(0.02)
    assert len(seen) == 1

    await gpio.stop()
    assert 27 not in fake_lgpio.claims and fake_lgpio.closed


async def test_gpio_busy_gives_clear_error(fake_lgpio, event_bus):
    from parade.gpio.rpi import RPiGPIO

    fake_lgpio.claims[17] = ("alert", 0)
    gpio = RPiGPIO([GPIOInputConfig(id="idx", pin=17)], event_bus)
    with pytest.raises(RuntimeError, match="GPIO17.*systemd service"):
        await gpio.start()


@pytest.mark.parametrize("active_low,off_level", [(False, 0), (True, 1)])
async def test_relay_claims_off_and_releases_off(fake_lgpio, active_low, off_level):
    from parade.relay.rpi import RPiRelay

    relay = RPiRelay([RelayOutputConfig(id="motor", pin=18, active_low=active_low)])
    await relay.start()
    assert fake_lgpio.claims[18] == ("output", off_level)
    await relay.set_relay("motor", True)
    assert fake_lgpio.levels[18] == 1 - off_level
    await relay.stop()
    assert fake_lgpio.writes[-1] == (18, off_level)
    assert relay.get_all_states() == {"motor": False}


def test_pixels_require_spi_pin():
    from parade.config.models import PixelStripConfig
    from parade.pixels.rpi import RPiPixels

    with pytest.raises(ValueError, match="pin must be 10"):
        RPiPixels(PixelStripConfig(id="s", pin=12, count=5))


async def test_pixels_resend_last_shown_frame(monkeypatch):
    import parade.pixels.rpi as rpi
    from parade.config.models import PixelStripConfig

    class FakeSpi:
        def __init__(self):
            self.writes = []

        def writebytes2(self, data):
            self.writes.append(data)

        def close(self):
            pass

    monkeypatch.setattr(rpi, "REFRESH_S", 0.01)
    px = rpi.RPiPixels(PixelStripConfig(id="s", pin=10, count=2, strip_type="SK6812RGBW", color_order="RGBW"))
    spi = px._spi = FakeSpi()
    px._refresh_task = asyncio.create_task(px._refresh())
    await px.set_all(0, 0, 255)
    await px.show()
    await px.set_pixel(0, 255, 0, 0)  # buffered but not shown: must not be resent
    await asyncio.sleep(0.05)
    shown = rpi.encode_ws2812_spi([(0, 0, 255)] * 2, order="RGBW")
    assert len(spi.writes) > 2 and all(w == shown for w in spi.writes)
    await px.stop()
    assert px._refresh_task is None
