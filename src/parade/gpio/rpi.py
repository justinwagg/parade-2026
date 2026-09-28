"""Raspberry Pi GPIO inputs via lgpio (/dev/gpiochipN).

lgpio is installed from apt (python3-lgpio) and imported lazily so the rest of
the app still runs on macOS. Edge callbacks arrive on lgpio's own thread and are
handed to the asyncio loop; show logic never runs in the callback.
"""
import asyncio
import logging
from .interface import GPIOInterface
from parade.config.models import GPIOInputConfig
from parade.core.events import GPIOChangeEvent
from parade.core.event_bus import EventBus

logger = logging.getLogger(__name__)


def import_lgpio():
    try:
        import lgpio
    except ImportError as e:
        raise RuntimeError(
            "lgpio is not available. On the Pi: sudo apt install python3-lgpio, "
            "and create the venv with --system-site-packages (scripts/pi-setup.sh does both)."
        ) from e
    return lgpio


class RPiGPIO(GPIOInterface):
    def __init__(self, configs: list[GPIOInputConfig], event_bus: EventBus, chip: int = 0):
        self._configs = {c.id: c for c in configs}
        self._event_bus = event_bus
        self._chip = chip
        self._lgpio = None
        self._handle: int | None = None
        self._callbacks: list = []
        self._loop: asyncio.AbstractEventLoop | None = None
        # Physical state: False = low, True = high.
        self._physical_states: dict[str, bool] = {c.id: c.active_low for c in configs}

    async def start(self) -> None:
        lgpio = self._lgpio = import_lgpio()
        self._loop = asyncio.get_running_loop()
        self._handle = lgpio.gpiochip_open(self._chip)
        pull_flags = {
            "up": lgpio.SET_PULL_UP,
            "down": lgpio.SET_PULL_DOWN,
            "none": lgpio.SET_PULL_NONE,
        }
        try:
            for cfg in self._configs.values():
                try:
                    lgpio.gpio_claim_alert(
                        self._handle, cfg.pin, lgpio.BOTH_EDGES, pull_flags[cfg.pull]
                    )
                except lgpio.error as e:
                    raise RuntimeError(
                        f"Cannot claim GPIO{cfg.pin} for input '{cfg.id}': {e} "
                        "(is another parade process or the systemd service running?)"
                    ) from e
                lgpio.gpio_set_debounce_micros(self._handle, cfg.pin, cfg.debounce_ms * 1000)
                self._physical_states[cfg.id] = bool(lgpio.gpio_read(self._handle, cfg.pin))
                self._callbacks.append(
                    lgpio.callback(self._handle, cfg.pin, lgpio.BOTH_EDGES, self._make_callback(cfg.id))
                )
        except Exception:
            await self.stop()
            raise
        logger.info(
            "RPi GPIO started on gpiochip%d: %s", self._chip,
            ", ".join(
                f"{c.id}=GPIO{c.pin}({'ACTIVE' if self.get_state(c.id) else 'idle'})"
                for c in self._configs.values()
            ),
        )

    async def stop(self) -> None:
        for cb in self._callbacks:
            cb.cancel()
        self._callbacks.clear()
        if self._handle is not None:
            for cfg in self._configs.values():
                try:
                    self._lgpio.gpio_free(self._handle, cfg.pin)
                except Exception:
                    pass
            self._lgpio.gpiochip_close(self._handle)
            self._handle = None
            logger.info("RPi GPIO stopped")

    def _make_callback(self, pin_id: str):
        def _callback(chip, gpio, level, timestamp):
            # Runs on lgpio's thread. level 2 = watchdog timeout (not used).
            if level in (0, 1) and self._loop is not None:
                self._loop.call_soon_threadsafe(self._on_level, pin_id, bool(level))
        return _callback

    def _on_level(self, pin_id: str, physical: bool) -> None:
        if self._physical_states.get(pin_id) == physical:
            return
        self._physical_states[pin_id] = physical
        event = GPIOChangeEvent(
            pin_id=pin_id,
            state=physical,
            active=self._logical_state(pin_id, physical),
            source="rpi_gpio",
        )
        logger.debug("GPIO %s -> physical=%s active=%s", pin_id, physical, event.active)
        asyncio.ensure_future(self._event_bus.publish(event))

    def _logical_state(self, pin_id: str, physical: bool) -> bool:
        return (not physical) if self._configs[pin_id].active_low else physical

    def get_state(self, pin_id: str) -> bool:
        return self._logical_state(pin_id, self._physical_states.get(pin_id, False))

    def get_all_states(self) -> dict[str, bool]:
        return {pid: self._logical_state(pid, phys) for pid, phys in self._physical_states.items()}

    def get_physical_states(self) -> dict[str, bool]:
        return dict(self._physical_states)
