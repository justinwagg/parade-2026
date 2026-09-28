import json
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from parade.api.context import AppContext
from parade.core.state import SystemState, StateTransitionError, ALLOWED_TRANSITIONS
from .dependencies import get_ctx

router = APIRouter()
logger = logging.getLogger(__name__)


def state_snapshot(ctx: AppContext) -> dict:
    return {
        "system_state": ctx.state_machine.state.value,
        "armed": ctx.state_machine.armed,
        "estop_active": ctx.safety.estop_active if ctx.safety else False,
        "timestamp": time.time(),
        "universes": {
            str(uid): {str(ch): val for ch, val in u.get_all_channels().items()}
            for uid, u in ctx.universes.items()
        },
        "gpio": ctx.gpio.get_all_states(),
        "gpio_physical": ctx.gpio.get_physical_states(),
        "scenes": ctx.scene_manager.list_scenes(),
        "valid_transitions": [
            s.value
            for s in ALLOWED_TRANSITIONS.get(ctx.state_machine.state, set())
        ],
        "relays": ctx.relay_manager.get_all_states(),
        "pixels": [list(p) for p in ctx.pixel_manager.get_all_pixels()],
        "power": ctx.power_monitor.snapshot() if ctx.power_monitor else None,
        "engine": {
            "active_cue": ctx.show_engine.active_cue,
            "active_step": ctx.show_engine.active_step,
            "total_steps": ctx.show_engine.total_steps,
            "active_label": ctx.show_engine.active_label,
            "vars": dict(ctx.show_engine._vars),
        },
    }


@router.get("/api/state")
async def api_get_state(ctx: AppContext = Depends(get_ctx)):
    return state_snapshot(ctx)


@router.get("/api/power/history")
async def api_power_history(ctx: AppContext = Depends(get_ctx)):
    """Rolling ~10 min of power/thermal samples for the dashboard chart."""
    return ctx.power_monitor.history() if ctx.power_monitor else []


@router.post("/api/state/{new_state}")
async def api_set_state(new_state: str, ctx: AppContext = Depends(get_ctx)):
    try:
        s = SystemState(new_state.upper())
        if ctx.safety:
            old, new = await ctx.safety.transition(s)
        else:
            old, new = ctx.state_machine.transition(s)
        return {"ok": True, "old_state": old.value, "new_state": new.value}
    except (ValueError, StateTransitionError) as e:
        raise HTTPException(400, str(e))


@router.get("/api/config")
async def api_get_config(ctx: AppContext = Depends(get_ctx)):
    """Return hardware layout for UI pin-map rendering."""
    return {
        "gpio_inputs": [
            {"id": g.id, "pin": g.pin, "active_low": g.active_low, "description": g.description}
            for g in ctx.config.gpio_inputs
        ],
        "relay_outputs": [
            {"id": r.id, "pin": r.pin, "description": r.description}
            for r in ctx.config.relay_outputs
        ],
        "pixel_strips": [
            {"id": s.id, "pin": s.pin, "count": s.count, "description": s.description}
            for s in ctx.config.pixel_strips
        ],
        "fixtures": [
            {"id": f.id, "name": f.name, "profile": f.profile, "universe": f.universe, "address": f.address}
            for f in ctx.config.fixtures
        ],
        "fixture_groups": [
            {"id": g.id, "name": g.name, "fixture_ids": g.fixture_ids, "description": g.description}
            for g in ctx.config.fixture_groups
        ],
    }


@router.get("/api/cues")
async def api_get_cues(ctx: AppContext = Depends(get_ctx)):
    return {"cues": ctx.show_engine.list_cues()}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ctx: AppContext = ws.app.state.ctx
    ctx.ws_clients.append(ws)
    try:
        await ws.send_text(
            json.dumps({"type": "state", "data": state_snapshot(ctx)})
        )
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in ctx.ws_clients:
            ctx.ws_clients.remove(ws)
