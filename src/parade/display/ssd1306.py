"""SSD1306 I2C OLED (128x32 on the float) via luma.oled (apt package python3-luma.oled).

Wiring: VCC → 3.3 V (header pin 1), GND → header pin 9, SDA → GPIO2 (pin 3),
SCL → GPIO3 (pin 5). I2C must be enabled (raspi-config nonint do_i2c 0).

Text uses Pillow's built-in 6x11 bitmap font: 21 characters per line on a
128-pixel-wide panel, 3 lines on 32 rows. A frame is only sent when it changes
(a full frame is ~50 ms on the 100 kHz bus). I2C errors are logged and the next
frame is tried again, so a loose wire never stops the show.
"""
import asyncio
import logging
from parade.config.models import DisplayConfig
from parade.display.interface import DisplayInterface

logger = logging.getLogger(__name__)

CHAR_W = 6
LINE_H = 11


def line_positions(height: int) -> list[int]:
    """Top y of each text line, spread so the last line ends on the bottom row."""
    rows = max(1, (height + 1) // LINE_H)
    if rows == 1:
        return [0]
    return [round(i * (height - LINE_H) / (rows - 1)) for i in range(rows)]


class SSD1306Display(DisplayInterface):
    def __init__(self, config: DisplayConfig):
        self._config = config
        self._device = None
        self._font = None
        self._last: tuple | None = None
        self._lines: list[str] = []
        self._failing = False

    async def start(self) -> None:
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import ssd1306
            from PIL import ImageFont
        except ImportError:
            logger.error("luma.oled not installed (sudo apt install python3-luma.oled); display disabled")
            return
        cfg = self._config
        try:
            self._device = await asyncio.to_thread(
                lambda: ssd1306(
                    i2c(port=cfg.i2c_bus, address=cfg.address),
                    width=cfg.width, height=cfg.height, rotate=cfg.rotate,
                )
            )
        except Exception as e:  # luma raises DeviceNotFoundError / DevicePermissionError / OSError
            logger.error("OLED display not found on I2C bus %d at 0x%02X: %s", cfg.i2c_bus, cfg.address, e)
            return
        self._device.persist = True  # keep the last frame (e.g. "stopped") after exit
        self._font = ImageFont.load_default_imagefont()
        logger.info("OLED display started (%dx%d at 0x%02X)", cfg.width, cfg.height, cfg.address)

    async def stop(self) -> None:
        pass

    def _render(self, lines: list[str], heartbeat: bool) -> None:
        from PIL import Image, ImageDraw

        dev = self._device
        img = Image.new(dev.mode, dev.size)
        draw = ImageDraw.Draw(img)
        for y, text in zip(line_positions(dev.height), lines):
            draw.text((0, y), text, font=self._font, fill="white")
        if heartbeat:
            draw.rectangle((dev.width - 2, 0, dev.width - 1, 1), fill="white")
        dev.display(img)

    async def show(self, lines: list[str], heartbeat: bool = False) -> None:
        self._lines = list(lines)
        if self._device is None:
            return
        frame = (tuple(lines), heartbeat)
        if frame == self._last:
            return
        try:
            await asyncio.to_thread(self._render, lines, heartbeat)
        except OSError as e:
            if not self._failing:
                logger.warning("OLED display write failed: %s", e)
                self._failing = True
            self._last = None
            return
        if self._failing:
            logger.info("OLED display writing again")
            self._failing = False
        self._last = frame

    def get_lines(self) -> list[str]:
        return list(self._lines)
