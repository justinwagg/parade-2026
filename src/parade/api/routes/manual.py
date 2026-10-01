"""MANUAL mode controls: relays, NeoPixels and input counters (see core/manual.py)."""
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from parade.api.context import AppContext
from parade.core.manual import ManualModeError
from .dependencies import get_ctx

router = APIRouter()

RGB = list[int]


class RelayRequest(BaseModel):
    state: bool


class ColorRequest(BaseModel):
    color: RGB = Field(min_length=3, max_length=3)


class EffectRequest(BaseModel):
    effect: str
    color: RGB = Field(default=[255, 255, 255], min_length=3, max_length=3)
    speed: float = 1.0


def _manual(ctx: AppContext):
    if ctx.manual is None:
        raise HTTPException(503, "Manual control not available")
    return ctx.manual


def _log(ctx: AppContext, msg: str) -> None:
    ctx.event_log.append({"ts": round(time.time() * 1000), "tag": "manual", "msg": msg})


@router.post("/api/manual/relay/{relay_id}")
async def manual_relay(relay_id: str, body: RelayRequest, ctx: AppContext = Depends(get_ctx)):
    try:
        await _manual(ctx).set_relay(relay_id, body.state)
    except ManualModeError as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(404, str(e))
    _log(ctx, f"Manual: relay {relay_id} → {'ON' if body.state else 'off'}")
    return {"ok": True, "relay_id": relay_id, "state": body.state}


@router.post("/api/manual/pixels/color")
async def manual_pixel_color(body: ColorRequest, ctx: AppContext = Depends(get_ctx)):
    try:
        await _manual(ctx).set_pixel_color(*body.color)
    except ManualModeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.post("/api/manual/pixels/effect")
async def manual_pixel_effect(body: EffectRequest, ctx: AppContext = Depends(get_ctx)):
    try:
        await _manual(ctx).run_pixel_effect(body.effect, tuple(body.color), body.speed)
    except ManualModeError as e:
        raise HTTPException(400, str(e))
    _log(ctx, f"Manual: pixels {body.effect}")
    return {"ok": True}


@router.post("/api/manual/pixels/off")
async def manual_pixels_off(ctx: AppContext = Depends(get_ctx)):
    await _manual(ctx).pixels_off()
    return {"ok": True}


@router.post("/api/manual/inputs/reset")
async def manual_inputs_reset(ctx: AppContext = Depends(get_ctx)):
    _manual(ctx).reset_input_counts()
    return {"ok": True}
