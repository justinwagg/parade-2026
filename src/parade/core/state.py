from enum import Enum


class SystemState(str, Enum):
    BOOTING = "BOOTING"
    SAFE = "SAFE"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    FAULT = "FAULT"


# Valid transitions: from_state -> set of allowed to_states
ALLOWED_TRANSITIONS: dict[SystemState, set[SystemState]] = {
    SystemState.BOOTING: {SystemState.SAFE, SystemState.FAULT},
    SystemState.SAFE: {
        SystemState.READY,
        SystemState.FAULT,
        SystemState.EMERGENCY_STOP,
    },
    SystemState.READY: {
        SystemState.RUNNING,
        SystemState.SAFE,
        SystemState.FAULT,
        SystemState.EMERGENCY_STOP,
    },
    SystemState.RUNNING: {
        SystemState.PAUSED,
        SystemState.SAFE,
        SystemState.FAULT,
        SystemState.EMERGENCY_STOP,
    },
    SystemState.PAUSED: {
        SystemState.RUNNING,
        SystemState.SAFE,
        SystemState.FAULT,
        SystemState.EMERGENCY_STOP,
    },
    SystemState.EMERGENCY_STOP: {SystemState.SAFE},
    SystemState.FAULT: {SystemState.SAFE},
}


class StateTransitionError(Exception):
    pass


class SystemStateMachine:
    def __init__(self):
        self._state = SystemState.BOOTING
        self._armed = False

    @property
    def state(self) -> SystemState:
        return self._state

    @property
    def armed(self) -> bool:
        return self._armed

    def transition(self, new_state: SystemState) -> tuple[SystemState, SystemState]:
        """Returns (old_state, new_state). Raises StateTransitionError if invalid."""
        allowed = ALLOWED_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            raise StateTransitionError(
                f"Cannot transition {self._state} -> {new_state}. Allowed: {allowed}"
            )
        old = self._state
        self._state = new_state
        if new_state == SystemState.EMERGENCY_STOP:
            self._armed = False
        return old, new_state

    def set_armed(self, armed: bool) -> None:
        if armed and self._state not in (
            SystemState.READY,
            SystemState.RUNNING,
            SystemState.PAUSED,
        ):
            raise StateTransitionError(f"Cannot arm in state {self._state}")
        self._armed = armed
