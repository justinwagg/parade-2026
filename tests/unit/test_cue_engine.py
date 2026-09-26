import pytest
import asyncio
from parade.core.engine import ShowEngine
from parade.core.events import OperatorTriggerEvent, GPIOChangeEvent
from parade.core.event_bus import EventBus


@pytest.fixture
def cue_defs():
    return [
        {
            "id": "test_cue_1",
            "trigger": {
                "event": "operator_trigger",
                "condition": "event.trigger_id == 'flash'",
            },
            "actions": [{"type": "set_dmx_scene", "scene": "red_on"}],
        },
        {
            "id": "test_cue_gpio",
            "trigger": {
                "event": "gpio_changed",
                "condition": "event.active == True",
            },
            "actions": [{"type": "set_dmx_scene", "scene": "blue_on"}],
        },
    ]


@pytest.fixture
def engine(event_bus, scene_manager, cue_defs):
    return ShowEngine(event_bus, scene_manager, cue_defs)


@pytest.mark.asyncio
async def test_cue_triggers_on_matching_event(engine, event_bus, scene_manager, universe):
    await engine.start()
    ev = OperatorTriggerEvent(trigger_id="flash", params={}, source="test")
    await event_bus.publish(ev)
    await asyncio.sleep(0.05)
    assert universe.get_channel(1) == 255  # red applied


@pytest.mark.asyncio
async def test_cue_does_not_trigger_on_wrong_params(engine, event_bus, scene_manager, universe):
    await engine.start()
    ev = OperatorTriggerEvent(trigger_id="other", params={}, source="test")
    await event_bus.publish(ev)
    await asyncio.sleep(0.05)
    assert universe.get_channel(1) == 0  # red NOT applied


@pytest.mark.asyncio
async def test_gpio_cue_triggers_on_active(engine, event_bus, scene_manager, universe):
    await engine.start()
    ev = GPIOChangeEvent(pin_id="test_pin", state=True, active=True, source="test")
    await event_bus.publish(ev)
    await asyncio.sleep(0.05)
    assert universe.get_channel(3) == 255  # blue applied
