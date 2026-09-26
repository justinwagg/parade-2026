import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from parade.api.context import AppContext
from .dependencies import get_ctx

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/dmx/universes/{universe_id}/channels")
async def get_channels(universe_id: int, ctx: AppContext = Depends(get_ctx)):
    u = ctx.universes.get(universe_id)
    if not u:
        raise HTTPException(404, f"Universe {universe_id} not found")
    return {"universe_id": universe_id, "channels": u.get_all_channels()}


@router.get("/api/dmx/universes/{universe_id}/buffer")
async def get_buffer(universe_id: int, ctx: AppContext = Depends(get_ctx)):
    u = ctx.universes.get(universe_id)
    if not u:
        raise HTTPException(404, f"Universe {universe_id} not found")
    return {"universe_id": universe_id, "buffer": list(u.get_buffer())}


class SetChannelsRequest(BaseModel):
    channels: dict[int, int]  # {channel: value}


@router.post("/api/dmx/universes/{universe_id}/channels")
async def set_channels(
    universe_id: int,
    body: SetChannelsRequest,
    ctx: AppContext = Depends(get_ctx),
):
    u = ctx.universes.get(universe_id)
    if not u:
        raise HTTPException(404, f"Universe {universe_id} not found")
    u.set_channels(body.channels)
    return {"ok": True}


@router.get("/api/dmx/scenes")
async def list_scenes(ctx: AppContext = Depends(get_ctx)):
    return {"scenes": ctx.scene_manager.list_scenes()}


@router.post("/api/dmx/scenes/{scene_id}/apply")
async def apply_scene(scene_id: str, ctx: AppContext = Depends(get_ctx)):
    try:
        ctx.scene_manager.apply_scene(scene_id)
        return {"ok": True, "scene": scene_id}
    except KeyError as e:
        raise HTTPException(404, str(e))


class FadeRequest(BaseModel):
    duration_ms: float = 1000.0


@router.post("/api/dmx/scenes/{scene_id}/fade")
async def fade_to_scene(
    scene_id: str,
    body: FadeRequest,
    ctx: AppContext = Depends(get_ctx),
):
    try:
        asyncio.create_task(
            ctx.scene_manager.fade_to_scene(scene_id, body.duration_ms)
        )
        return {"ok": True, "scene": scene_id, "duration_ms": body.duration_ms}
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/api/dmx/blackout")
async def blackout(ctx: AppContext = Depends(get_ctx)):
    ctx.scene_manager.blackout_all()
    return {"ok": True}


@router.get("/api/dmx/fixtures")
async def list_fixtures(ctx: AppContext = Depends(get_ctx)):
    fixtures = ctx.fixture_manager.get_all_fixtures()
    return {
        "fixtures": {
            fid: {
                "name": f.name,
                "profile": f.profile,
                "universe": f.universe,
                "address": f.address,
            }
            for fid, f in fixtures.items()
        }
    }
