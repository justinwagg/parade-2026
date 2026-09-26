import pytest
from parade.core.state import SystemStateMachine, SystemState, StateTransitionError


def test_initial_state():
    sm = SystemStateMachine()
    assert sm.state == SystemState.BOOTING


def test_valid_transition():
    sm = SystemStateMachine()
    old, new = sm.transition(SystemState.SAFE)
    assert old == SystemState.BOOTING
    assert new == SystemState.SAFE
    assert sm.state == SystemState.SAFE


def test_invalid_transition():
    sm = SystemStateMachine()
    sm.transition(SystemState.SAFE)
    with pytest.raises(StateTransitionError):
        sm.transition(SystemState.BOOTING)


def test_emergency_stop_clears_armed():
    sm = SystemStateMachine()
    sm.transition(SystemState.SAFE)
    sm.transition(SystemState.READY)
    sm.set_armed(True)
    assert sm.armed
    sm.transition(SystemState.EMERGENCY_STOP)
    assert not sm.armed


def test_armed_requires_ready_state():
    sm = SystemStateMachine()
    with pytest.raises(StateTransitionError):
        sm.set_armed(True)
