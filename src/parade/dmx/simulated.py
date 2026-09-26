import logging
from .interface import DMXInterface

logger = logging.getLogger(__name__)


class SimulatedDMX(DMXInterface):
    def __init__(self):
        self._sent: dict[int, bytes] = {}

    async def start(self) -> None:
        logger.info("Simulated DMX driver started (no network output)")

    async def stop(self) -> None:
        logger.info("Simulated DMX driver stopped")

    async def send_universe(
        self, universe_id: int, node_ip: str, node_port: int, data: bytes
    ) -> None:
        self._sent[universe_id] = data

    def get_last_sent(self, universe_id: int) -> bytes:
        return self._sent.get(universe_id, bytes(512))
