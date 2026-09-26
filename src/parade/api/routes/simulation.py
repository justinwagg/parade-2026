import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from parade.api.context import AppContext
from parade.gpio.simulated import SimulatedGPIO
from parade.relay.simulated import SimulatedRelay
from parade.core.events import OperatorTriggerEvent
from .dependencies import get_ctx

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/sim/gpio")
async def get_gpio_states(ctx: AppContext = Depends(get_ctx)):
    return {"states": ctx.gpio.get_all_states()}


class SetGPIORequest(BaseModel):
    physical_state: bool


@router.post("/api/sim/gpio/{pin_id}")
async def set_gpio(
    pin_id: str,
    body: SetGPIORequest,
    ctx: AppContext = Depends(get_ctx),
):
    if not isinstance(ctx.gpio, SimulatedGPIO):
        raise HTTPException(
            400, "GPIO simulation only available in simulation mode"
        )
    try:
        await ctx.gpio.inject_state(pin_id, body.physical_state)
        return {
            "ok": True,
            "pin_id": pin_id,
            "physical_state": body.physical_state,
        }
    except KeyError as e:
        raise HTTPException(404, str(e))


class SetRelayRequest(BaseModel):
    state: bool


@router.post("/api/sim/relay/{relay_id}")
async def set_relay(
    relay_id: str,
    body: SetRelayRequest,
    ctx: AppContext = Depends(get_ctx),
):
    if not isinstance(ctx.relay_manager, SimulatedRelay):
        raise HTTPException(400, "Relay simulation only available in simulation mode")
    try:
        await ctx.relay_manager.set_relay(relay_id, body.state)
        return {"ok": True, "relay_id": relay_id, "state": body.state}
    except KeyError as e:
        raise HTTPException(404, str(e))


class InjectEventRequest(BaseModel):
    event_type: str
    params: dict = {}


@router.post("/api/sim/events")
async def inject_event(
    body: InjectEventRequest, ctx: AppContext = Depends(get_ctx)
):
    event = OperatorTriggerEvent(
        trigger_id=body.event_type,
        params=body.params,
        source="api_simulation",
    )
    await ctx.event_bus.publish(event)
    return {"ok": True, "event_type": body.event_type}
