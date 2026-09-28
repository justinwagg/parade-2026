"""WS2812B NeoPixels on the Pi's SPI0 MOSI (GPIO10) via spidev.

Each WS2812 data bit is sent as one SPI byte at ~6.4 MHz (156 ns per SPI bit,
6.25 MHz on a Pi 3 with core_freq=250): 0b11000000 gives a ~0.3 µs high pulse
for a 0 and 0b11111000 a ~0.8 µs pulse for a 1. Every byte ends low, so any gap
the SPI controller leaves between bytes only stretches a low period, which the
pixels tolerate. SPI needs no root and does not clash with the Pi 3's PWM audio.
"""
import logging
from pathlib import Path
from parade.pixels.interface import PixelInterface
from parade.config.models import PixelStripConfig

logger = logging.getLogger(__name__)

SPI_MOSI_GPIO = 10
SPI_SPEED_HZ = 6_400_000
_BIT0 = 0b11000000
_BIT1 = 0b11111000
# ≥ 300 µs of low after the data latches the frame (newer WS2812B need > 280 µs).
RESET_BYTES = 240
_COLOR_ORDER = {"WS2812B": "GRB", "WS2812": "GRB"}
_SPIDEV_BUFSIZ = Path("/sys/module/spidev/parameters/bufsiz")

# byte value -> 8 SPI bytes, MSB first
_ENCODE = [bytes(_BIT1 if v & (0x80 >> i) else _BIT0 for i in range(8)) for v in range(256)]


def encode_ws2812_spi(
    pixels: list[tuple[int, int, int]], brightness: float = 1.0, order: str = "GRB"
) -> bytes:
    """Encode RGB pixels as an SPI byte stream for WS2812-family strips."""
    idx = ["RGB".index(c) for c in order]
    out = []
    for px in pixels:
        for i in idx:
            out.append(_ENCODE[int(px[i] * brightness)])
    out.append(bytes(RESET_BYTES))
    return b"".join(out)


def frame_size(count: int) -> int:
    return count * 24 + RESET_BYTES


class RPiPixels(PixelInterface):
    def __init__(self, strip_config: PixelStripConfig, bus: int = 0, device: int = 0):
        if strip_config.pin != SPI_MOSI_GPIO:
            raise ValueError(
                f"Pixel strip '{strip_config.id}': rpi driver drives the strip from SPI0 MOSI, "
                f"so pin must be {SPI_MOSI_GPIO} (got {strip_config.pin})"
            )
        if strip_config.strip_type not in _COLOR_ORDER:
            raise ValueError(f"Unsupported strip_type {strip_config.strip_type!r}")
        self._order = _COLOR_ORDER[strip_config.strip_type]
        self._brightness = strip_config.brightness
        self._count = strip_config.count
        self._bus, self._device = bus, device
        self._pixels: list[tuple[int, int, int]] = [(0, 0, 0)] * self._count
        self._spi = None

    async def start(self) -> None:
        try:
            import spidev
        except ImportError as e:
            raise RuntimeError(
                "spidev is not available. On the Pi: sudo apt install python3-spidev, "
                "and create the venv with --system-site-packages (scripts/pi-setup.sh does both)."
            ) from e
        dev = Path(f"/dev/spidev{self._bus}.{self._device}")
        if not dev.exists():
            raise RuntimeError(
                f"{dev} not found: enable SPI (sudo raspi-config nonint do_spi 0, "
                "or scripts/pi-setup.sh) and reboot"
            )
        try:
            bufsiz = int(_SPIDEV_BUFSIZ.read_text())
        except (OSError, ValueError):
            bufsiz = 4096
        if frame_size(self._count) > bufsiz:
            raise RuntimeError(
                f"{self._count} pixels need a {frame_size(self._count)}-byte SPI transfer but spidev "
                f"bufsiz is {bufsiz}: add spidev.bufsiz=65536 to /boot/firmware/cmdline.txt and reboot"
            )
        spi = spidev.SpiDev()
        spi.open(self._bus, self._device)
        spi.max_speed_hz = SPI_SPEED_HZ
        spi.mode = 0
        self._spi = spi
        await self.show()  # start dark
        logger.info(
            "RPi pixel driver started: %d x %s on GPIO%d (SPI%d.%d), brightness %.0f%%",
            self._count, "WS2812B", SPI_MOSI_GPIO, self._bus, self._device, self._brightness * 100,
        )

    async def stop(self) -> None:
        if self._spi is None:
            return
        try:
            await self.set_all(0, 0, 0)
            await self.show()
        finally:
            self._spi.close()
            self._spi = None
            logger.info("RPi pixel driver stopped (strip blanked)")

    async def set_pixel(self, index: int, r: int, g: int, b: int) -> None:
        if 0 <= index < self._count:
            self._pixels[index] = (
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b)),
            )

    async def set_all(self, r: int, g: int, b: int) -> None:
        c = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        self._pixels = [c] * self._count

    async def show(self) -> None:
        # ~2 ms for 50 pixels; short enough to write inline on the event loop.
        if self._spi is not None:
            self._spi.writebytes2(encode_ws2812_spi(self._pixels, self._brightness, self._order))

    def get_pixel_count(self) -> int:
        return self._count

    def get_all_pixels(self) -> list[tuple[int, int, int]]:
        return list(self._pixels)
