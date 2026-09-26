import pytest
from parade.core.events import OperatorTriggerEvent
from parade.core.event_bus import EventBus


@pytest.mark.asyncio
async def test_subscribe_and_publish(event_bus):
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("operator_trigger", handler)
    ev = OperatorTriggerEvent(trigger_id="test", params={}, source="test")
    await event_bus.publish(ev)
    assert len(received) == 1
    assert received[0].trigger_id == "test"


@pytest.mark.asyncio
async def test_multiple_handlers(event_bus):
    counts = [0, 0]

    async def h1(e):
        counts[0] += 1

    async def h2(e):
        counts[1] += 1

    event_bus.subscribe("operator_trigger", h1)
    event_bus.subscribe("operator_trigger", h2)
    ev = OperatorTriggerEvent(trigger_id="x", params={}, source="test")
    await event_bus.publish(ev)
    assert counts == [1, 1]


@pytest.mark.asyncio
async def test_wrong_type_not_delivered(event_bus):
    received = []

    async def handler(e):
        received.append(e)

    event_bus.subscribe("gpio_changed", handler)
    ev = OperatorTriggerEvent(trigger_id="x", params={}, source="test")
    await event_bus.publish(ev)
    assert len(received) == 0


@pytest.mark.asyncio
async def test_handler_error_does_not_break_others(event_bus):
    received = []

    async def bad(e):
        raise ValueError("fail")

    async def good(e):
        received.append(e)

    event_bus.subscribe("operator_trigger", bad)
    event_bus.subscribe("operator_trigger", good)
    ev = OperatorTriggerEvent(trigger_id="x", params={}, source="test")
    await event_bus.publish(ev)
    assert len(received) == 1
