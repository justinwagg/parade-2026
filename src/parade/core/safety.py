"""Software response to the e-stop and to leaving RUNNING.

This is the software layer only. The hardware e-stop removes motor power on
its own (docs/SAFETY.md). This class makes sure the software agrees with it:
relays are driven off, running cues are cancelled, and nothing can switch the
motor back on by itself when the e-stop is released.
"""
import logging
from parade.core.events import EmergencyStopEvent, GPIOChangeEvent, SystemStateChangedEvent
from parade.core.state import SystemState, StateTransitionError

logger = logging.getLogger(__name__)

# States in which cues are cancelled outright (PAUSED only stops relays).
_HALT_STATES = {SystemState.SAFE, SystemState.MANUAL, SystemState.EMERGENCY_STOP, SystemState.FAULT}


class SafetyMonitor:
    def __init__(self, event_bus, state_machine, relay_manager, show_engine, gpio, estop_pin: str | None):
        self._event_bus = event_bus
        self._state_machine = state_machine
        self._relay_manager = relay_manager
        self._show_engine = show_engine
        self._gpio = gpio
        self._estop_pin = estop_pin

    @property
    def estop_active(self) -> bool:
        # .get(): the input may have been removed on the setup page; the config
        # validator rejects that combination at the next load.
        return self._estop_pin is not None and self._gpio.get_all_states().get(self._estop_pin, False)

    async def start(self) -> None:
        self._event_bus.subscribe("gpio_changed", self._on_gpio)
        if self._estop_pin is None:
            logger.warning("No e-stop monitor input configured (safety.estop_pin)")
        elif self.estop_active:
            await self.trip("e-stop pressed (or monitor wire open) at startup")

    async def transition(self, new_state: SystemState) -> tuple[SystemState, SystemState]:
        """Operator/system state change. Raises StateTransitionError if not allowed."""
        if self.estop_active and new_state != SystemState.EMERGENCY_STOP:
            raise StateTransitionError(
                f"E-stop is pressed (or its monitor wire is open): release it before going to {new_state.value}"
            )
        old, new = self._state_machine.transition(new_state)
        await self._after_transition(old, new)
        return old, new

    async def trip(self, reason: str) -> None:
        logger.critical("EMERGENCY STOP: %s", reason)
        if self._state_machine.state != SystemState.EMERGENCY_STOP:
            try:
                old, new = self._state_machine.transition(SystemState.EMERGENCY_STOP)
            except StateTransitionError:
                # e.g. still BOOTING; relays are still driven off below
                old = new = self._state_machine.state
            if old != new:
                await self._after_transition(old, new)
            else:
                await self._halt(cancel_cues=True)
        await self._event_bus.publish(EmergencyStopEvent(source="safety_monitor"))

    async def _after_transition(self, old: SystemState, new: SystemState) -> None:
        if new != SystemState.RUNNING:
            await self._halt(cancel_cues=new in _HALT_STATES)
        await self._event_bus.publish(
            SystemStateChangedEvent(old_state=old.value, new_state=new.value, source="safety_monitor")
        )

    async def _halt(self, cancel_cues: bool) -> None:
        # Relays first (fast), then cues. The engine refuses relay-ON outside
        # RUNNING, so a cue unwinding after this cannot re-energize anything.
        await self.all_relays_off()
        if cancel_cues:
            await self._show_engine.cancel_all()

    async def all_relays_off(self) -> None:
        for relay_id, on in self._relay_manager.get_all_states().items():
            try:
                await self._relay_manager.set_relay(relay_id, False)
            except Exception:
                logger.exception("Failed to switch relay %s off", relay_id)

    async def _on_gpio(self, event: GPIOChangeEvent) -> None:
        if event.pin_id != self._estop_pin:
            return
        if event.active:
            await self.trip("e-stop pressed (or monitor wire open)")
        else:
            logger.warning("E-stop released. Return to SAFE from the dashboard to continue.")
