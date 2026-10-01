import asyncio
import pytest
from parade.config.models import GPIOInputConfig, PixelStripConfig, RelayOutputConfig
from parade.core.engine import ShowEngine
from parade.core.manual import ManualController, ManualModeError
from parade.core.safety import SafetyMonitor
from parade.core.state import SystemState, StateTransitionError
from parade.gpio.simulated import SimulatedGPIO
from parade.pixels.simulated import SimulatedPixels
from parade.relay.simulated import SimulatedRelay


@pytest.fixture
async def rig(event_bus, state_machine, scene_manager):
    gpio = SimulatedGPIO(
        [
            GPIOInputConfig(id="estop", pin=22, pull="up", active_low=False),
            GPIOInputConfig(id="go", pin=27, pull="up", active_low=True),
        ],
        event_bus,
    )
    relay = SimulatedRelay([RelayOutputConfig(id="motor", pin=18)])
    pixels = SimulatedPixels(PixelStripConfig(id="strip", count=10))
    cues = [
        {
            "id": "spin",
            "trigger": {"event": "gpio_changed", "condition": "event.pin_id == 'go' and event.active"},
            "actions": [{"type": "set_relay", "relay": "motor", "state": True}],
        }
    ]
    engine = ShowEngine(event_bus, scene_manager, cues, relay_manager=relay, state_machine=state_machine)
    safety = SafetyMonitor(event_bus, state_machine, relay, engine, gpio, "estop")
    manual = ManualController(event_bus, state_machine, relay, pixels, safety)
    state_machine.transition(SystemState.SAFE)
    await engine.start(); await safety.start(); await manual.start()
    yield gpio, relay, pixels, manual, safety, state_machine
    await manual.stop()


async def _press(gpio, pin):  # active_low "go": press pulls low, release high
    await gpio.inject_state(pin, False)
    await asyncio.sleep(0.02)
    await gpio.inject_state(pin, True)
    await asyncio.sleep(0.02)


async def test_manual_entered_and_left_only_through_safe(rig):
    *_, safety, sm = rig
    await safety.transition(SystemState.READY)
    with pytest.raises(StateTransitionError):
        await safety.transition(SystemState.MANUAL)
    await safety.transition(SystemState.SAFE)
    await safety.transition(SystemState.MANUAL)
    with pytest.raises(StateTransitionError):
        await safety.transition(SystemState.RUNNING)
    assert sm.state == SystemState.MANUAL


async def test_relay_on_only_in_manual_and_off_on_exit(rig):
    gpio, relay, pixels, manual, safety, sm = rig
    with pytest.raises(ManualModeError):
        await manual.set_relay("motor", True)
    assert relay.get_all_states()["motor"] is False

    await safety.transition(SystemState.MANUAL)
    await manual.set_relay("motor", True)
    assert relay.get_all_states()["motor"] is True

    await safety.transition(SystemState.SAFE)
    assert relay.get_all_states()["motor"] is False


async def test_estop_in_manual_turns_relay_off(rig):
    gpio, relay, pixels, manual, safety, sm = rig
    await safety.transition(SystemState.MANUAL)
    await manual.set_relay("motor", True)
    await gpio.inject_state("estop", True)
    await asyncio.sleep(0.02)
    assert sm.state == SystemState.EMERGENCY_STOP
    assert relay.get_all_states()["motor"] is False
    with pytest.raises(ManualModeError):
        await manual.set_relay("motor", True)


async def test_cues_ignored_in_manual_and_presses_counted(rig):
    gpio, relay, pixels, manual, safety, sm = rig
    await safety.transition(SystemState.MANUAL)
    await _press(gpio, "go")
    await _press(gpio, "go")
    assert relay.get_all_states()["motor"] is False  # the "spin" cue did not fire
    assert manual.snapshot()["input_activations"] == {"go": 2}


async def test_pixel_effect_runs_and_stops_on_exit(rig):
    gpio, relay, pixels, manual, safety, sm = rig
    with pytest.raises(ManualModeError):
        await manual.set_pixel_color(255, 0, 0)

    await safety.transition(SystemState.MANUAL)
    await manual.set_pixel_color(255, 0, 0)
    assert pixels.get_all_pixels() == [(255, 0, 0)] * 10

    await manual.run_pixel_effect("rainbow", (255, 255, 255), 1.0)
    await asyncio.sleep(0.1)
    assert len(set(pixels.get_all_pixels())) > 1
    assert manual.pixel_mode == "rainbow"

    await safety.transition(SystemState.SAFE)
    await asyncio.sleep(0.1)
    assert pixels.get_all_pixels() == [(0, 0, 0)] * 10
    assert manual.pixel_mode == "off"


async def test_unknown_effect_rejected(rig):
    *_, manual, safety, sm = rig
    await safety.transition(SystemState.MANUAL)
    with pytest.raises(ManualModeError):
        await manual.run_pixel_effect("strobe", (255, 255, 255), 1.0)
