import logging
from parade.status_lights.interface import Color, StatusLightInterface

logger = logging.getLogger(__name__)


class SimulatedStatusLights(StatusLightInterface):
    def __init__(self):
        self._leds: dict[tuple[str, int], Color] = {}

    async def start(self) -> None:
        logger.info("Simulated status light driver started")

    async def stop(self) -> None:
        pass

    async def set_led(self, serial: str, index: int, color: Color) -> bool:
        self._leds[(serial, index)] = color
        return True

    def get_leds(self) -> dict[tuple[str, int], Color]:
        return dict(self._leds)
