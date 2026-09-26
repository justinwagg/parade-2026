import logging
from .interface import GPIOInterface
from parade.config.models import GPIOInputConfig
from parade.core.events import GPIOChangeEvent
from parade.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class SimulatedGPIO(GPIOInterface):
    def __init__(self, configs: list[GPIOInputConfig], event_bus: EventBus):
        self._configs = {c.id: c for c in configs}
        self._event_bus = event_bus
        # Physical state: False = low, True = high.
        # Active-low pins start pulled high (True = inactive) to match real pull-up hardware.
        self._physical_states: dict[str, bool] = {
            c.id: c.active_low for c in configs
        }

    async def start(self) -> None:
        logger.info("Simulated GPIO started with %d pins", len(self._configs))

    async def stop(self) -> None:
        logger.info("Simulated GPIO stopped")

    def _logical_state(self, pin_id: str, physical: bool) -> bool:
        config = self._configs[pin_id]
        return (not physical) if config.active_low else physical

    def get_state(self, pin_id: str) -> bool:
        phys = self._physical_states.get(pin_id, False)
        return self._logical_state(pin_id, phys)

    def get_all_states(self) -> dict[str, bool]:
        return {
            pid: self._logical_state(pid, phys)
            for pid, phys in self._physical_states.items()
        }

    def get_physical_states(self) -> dict[str, bool]:
        return dict(self._physical_states)

    async def inject_state(self, pin_id: str, physical_state: bool) -> None:
        """Set a pin's physical state and publish a gpio_changed event."""
        if pin_id not in self._configs:
            raise KeyError(f"Unknown pin '{pin_id}'")
        old_phys = self._physical_states[pin_id]
        if old_phys == physical_state:
            return
        self._physical_states[pin_id] = physical_state
        active = self._logical_state(pin_id, physical_state)
        event = GPIOChangeEvent(
            pin_id=pin_id,
            state=physical_state,
            active=active,
            source="simulated_gpio",
        )
        logger.debug(
            "GPIO %s -> physical=%s active=%s", pin_id, physical_state, active
        )
        await self._event_bus.publish(event)
