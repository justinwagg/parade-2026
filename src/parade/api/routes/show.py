"""Phone booth show: live settings and spark-usage counter (see show/controller.py)."""
import time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from parade.api.context import AppContext
from .dependencies import get_ctx

router = APIRouter()


class SetParam(BaseModel):
    path: str  # dotted, e.g. "spark.on_ms" or "sides.2.color"
    value: Any


def _show(ctx: AppContext):
    if ctx.show is None or ctx.show_params is None:
        raise HTTPException(503, "Show sequencer is not enabled (show.enabled in config)")
    return ctx.show, ctx.show_params


@router.get("/api/show")
async def get_show(ctx: AppContext = Depends(get_ctx)):
    show, store = _show(ctx)
    sides = [s.model_dump() for s in ctx.config.show.pixel_sides]
    return {"params": store.params.model_dump(), "status": show.snapshot(), "sides": sides}


@router.post("/api/show/param")
async def set_param(body: SetParam, ctx: AppContext = Depends(get_ctx)):
    _, store = _show(ctx)
    try:
        params = store.set(body.path, body.value)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        msg = e.errors()[0]["msg"] if isinstance(e, ValidationError) else f"Unknown setting {body.path}"
        raise HTTPException(400, msg)
    return {"ok": True, "params": params.model_dump()}


@router.post("/api/show/spark/refilled")
async def spark_refilled(ctx: AppContext = Depends(get_ctx)):
    show, _ = _show(ctx)
    show.usage.reset()
    ctx.event_log.append({"ts": round(time.time() * 1000), "tag": "operator", "msg": "Spark hopper refilled: usage reset"})
    return {"ok": True}
