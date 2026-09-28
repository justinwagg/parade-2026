import asyncio
import pytest
from parade.config.models import GPIOInputConfig, RelayOutputConfig
from parade.core.engine import ShowEngine
from parade.core.safety import SafetyMonitor
from parade.core.state import SystemState, StateTransitionError
from parade.gpio.simulated import SimulatedGPIO
from parade.relay.simulated import SimulatedRelay


@pytest.fixture
def rig(event_bus, state_machine, scene_manager):
    gpio = SimulatedGPIO(
        [
            GPIOInputConfig(id="estop", pin=22, pull="up", active_low=False),
            GPIOInputConfig(id="go", pin=27, pull="up", active_low=True),
        ],
        event_bus,
    )
    relay = SimulatedRelay([RelayOutputConfig(id="motor", pin=18)])
    cues = [
        {
            # Motor on immediately, then again after a delay (the "stale" re-enable).
            "id": "spin",
            "trigger": {"event": "gpio_changed", "condition": "event.pin_id == 'go' and event.active"},
            "actions": [
                {"type": "set_relay", "relay": "motor", "state": True},
                {"type": "wait", "duration_ms": 200},
                {"type": "set_relay", "relay": "motor", "state": True},
            ],
        }
    ]
    engine = ShowEngine(event_bus, scene_manager, cues, relay_manager=relay, state_machine=state_machine)
    safety = SafetyMonitor(event_bus, state_machine, relay, engine, gpio, "estop")
    state_machine.transition(SystemState.SAFE)
    return gpio, relay, engine, safety, state_machine


async def _run(safety):
    await safety.transition(SystemState.READY)
    await safety.transition(SystemState.RUNNING)


async def _press(gpio, pin):  # active_low "go": press pulls low
    await gpio.inject_state(pin, False)
    await asyncio.sleep(0.02)


async def test_estop_trips_turns_relay_off_and_cancels_cue(rig):
    gpio, relay, engine, safety, sm = rig
    await engine.start(); await safety.start()
    await _run(safety)
    await _press(gpio, "go")
    assert relay.get_all_states()["motor"] is True

    await gpio.inject_state("estop", True)  # NC contact opens -> HIGH
    await asyncio.sleep(0.3)  # longer than the cue's wait
    assert sm.state == SystemState.EMERGENCY_STOP
    assert relay.get_all_states()["motor"] is False
    assert engine.active_cue is None


async def test_reset_refused_while_estop_held(rig):
    gpio, relay, engine, safety, sm = rig
    await engine.start(); await safety.start()
    await gpio.inject_state("estop", True)
    with pytest.raises(StateTransitionError):
        await safety.transition(SystemState.SAFE)
    await gpio.inject_state("estop", False)
    await safety.transition(SystemState.SAFE)
    assert sm.state == SystemState.SAFE
    assert relay.get_all_states()["motor"] is False


async def test_estop_pressed_at_startup_trips(rig):
    gpio, relay, engine, safety, sm = rig
    await gpio.inject_state("estop", True)
    await safety.start()
    assert sm.state == SystemState.EMERGENCY_STOP
    with pytest.raises(StateTransitionError):
        await safety.transition(SystemState.SAFE)


@pytest.mark.parametrize("target", [SystemState.PAUSED, SystemState.SAFE])
async def test_leaving_running_turns_relays_off(rig, target):
    gpio, relay, engine, safety, sm = rig
    await engine.start(); await safety.start()
    await _run(safety)
    await _press(gpio, "go")
    await safety.transition(target)
    await asyncio.sleep(0.3)
    assert relay.get_all_states()["motor"] is False


async def test_engine_refuses_relay_on_outside_running(rig, event_bus):
    gpio, relay, engine, safety, sm = rig
    from parade.core.engine import ActionDef
    await engine._execute_action(ActionDef("set_relay", {"relay": "motor", "state": True}), None)
    assert relay.get_all_states()["motor"] is False
    await relay.set_relay("motor", True)
    await engine._execute_action(ActionDef("set_relay", {"relay": "motor", "state": "off"}), None)
    assert relay.get_all_states()["motor"] is False


async def test_state_changes_are_published(rig, event_bus):
    gpio, relay, engine, safety, sm = rig
    seen = []

    async def on(ev):
        seen.append((ev.old_state, ev.new_state))

    event_bus.subscribe("system_state_changed", on)
    await safety.transition(SystemState.READY)
    assert seen == [("SAFE", "READY")]


def test_config_rejects_unknown_estop_pin():
    from pydantic import ValidationError
    from parade.config.models import Config

    with pytest.raises(ValidationError, match="estop_pin"):
        Config.model_validate({"safety": {"estop_pin": "nope"}})
