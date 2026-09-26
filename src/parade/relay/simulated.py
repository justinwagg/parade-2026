import logging
from parade.relay.interface import RelayInterface
from parade.config.models import RelayOutputConfig

logger = logging.getLogger(__name__)


class SimulatedRelay(RelayInterface):
    def __init__(self, relay_configs: list[RelayOutputConfig]):
        self._states: dict[str, bool] = {r.id: False for r in relay_configs}

    async def start(self) -> None:
        logger.info("Simulated relay driver started with %d relays", len(self._states))

    async def stop(self) -> None:
        pass

    async def set_relay(self, relay_id: str, state: bool) -> None:
        if relay_id not in self._states:
            raise KeyError(f"Unknown relay: {relay_id!r}")
        self._states[relay_id] = state
        logger.info("Relay %s → %s", relay_id, "ON" if state else "off")

    def get_all_states(self) -> dict[str, bool]:
        return dict(self._states)
