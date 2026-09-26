import logging
from parade.pixels.interface import PixelInterface
from parade.config.models import PixelStripConfig

logger = logging.getLogger(__name__)


class SimulatedPixels(PixelInterface):
    def __init__(self, strip_config: PixelStripConfig):
        self._count = strip_config.count
        self._pixels: list[tuple[int, int, int]] = [(0, 0, 0)] * self._count

    async def start(self) -> None:
        logger.info("Simulated pixel driver started (%d pixels)", self._count)

    async def stop(self) -> None:
        pass

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
        pass  # No hardware to flush in simulation

    def get_pixel_count(self) -> int:
        return self._count

    def get_all_pixels(self) -> list[tuple[int, int, int]]:
        return list(self._pixels)
