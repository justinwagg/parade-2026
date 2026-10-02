import logging
from parade.display.interface import DisplayInterface

logger = logging.getLogger(__name__)


class SimulatedDisplay(DisplayInterface):
    def __init__(self):
        self._lines: list[str] = []

    async def start(self) -> None:
        logger.info("Simulated status display started")

    async def stop(self) -> None:
        pass

    async def show(self, lines: list[str], heartbeat: bool = False) -> None:
        self._lines = list(lines)

    def get_lines(self) -> list[str]:
        return list(self._lines)
