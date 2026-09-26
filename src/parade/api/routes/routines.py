import re
import logging
import yaml
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from parade.api.context import AppContext
from parade.config.loader import load_cues, load_scenes
from .dependencies import get_ctx

router = APIRouter()
logger = logging.getLogger(__name__)

SCENES_SUBDIR = "scenes"


def _scenes_dir(ctx: AppContext) -> Path:
    d = ctx.cues_dir / SCENES_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_id(name: str) -> str:
    """Slugify a scene name into a safe file/cue id."""
    slug = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "scene"


def _reload_engine(ctx: AppContext) -> None:
    all_cues = load_cues(ctx.cues_dir)
    ctx.show_engine.reload_cues(all_cues)


def _list_scene_files(ctx: AppContext) -> list[Path]:
    return sorted(_scenes_dir(ctx).glob("*.yaml"))


# ── Models ────────────────────────────────────────────────────────────────────

class TriggerModel(BaseModel):
    event: str
    condition: str | None = None


class ActionModel(BaseModel):
    type: str
    # All other fields are passed through as extra kwargs
    model_config = {"extra": "allow"}


class SceneModel(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    trigger: TriggerModel
    actions: list[ActionModel]
    priority: int = 10
    cooldown_ms: float = 1000


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/routines")
async def list_routines(ctx: AppContext = Depends(get_ctx)):
    scenes = []
    for f in _list_scene_files(ctx):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh) or []
            cues = data if isinstance(data, list) else [data]
            for cue in cues:
                scenes.append({
                    "id": cue.get("id"),
                    "name": cue.get("name", cue.get("id", f.stem)),
                    "description": cue.get("description", ""),
                    "file": f.name,
                })
        except Exception as e:
            logger.warning("Could not read scene file %s: %s", f, e)
    return {"scenes": scenes}


@router.get("/api/routines/{scene_id}")
async def get_routine(scene_id: str, ctx: AppContext = Depends(get_ctx)):
    for f in _list_scene_files(ctx):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh) or []
            cues = data if isinstance(data, list) else [data]
            for cue in cues:
                if cue.get("id") == scene_id:
                    return {"scene": cue}
        except Exception:
            pass
    raise HTTPException(404, f"Scene '{scene_id}' not found")


@router.post("/api/routines")
async def save_routine(scene: SceneModel, ctx: AppContext = Depends(get_ctx)):
    # Derive id from name if not provided
    scene_id = scene.id or _safe_id(scene.name)

    cue_data = {
        "id": scene_id,
        "name": scene.name,
        "description": scene.description,
        "trigger": scene.trigger.model_dump(exclude_none=True),
        "actions": [a.model_dump() for a in scene.actions],
        "priority": scene.priority,
        "cooldown_ms": scene.cooldown_ms,
    }

    # Save to its own file (one cue per file for easy editing)
    out_path = _scenes_dir(ctx) / f"{scene_id}.yaml"
    with open(out_path, "w") as fh:
        yaml.dump([cue_data], fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

    _reload_engine(ctx)
    logger.info("Scene '%s' saved to %s and engine reloaded", scene_id, out_path)
    return {"ok": True, "id": scene_id}


@router.delete("/api/routines/{scene_id}")
async def delete_routine(scene_id: str, ctx: AppContext = Depends(get_ctx)):
    target = _scenes_dir(ctx) / f"{scene_id}.yaml"
    if not target.exists():
        raise HTTPException(404, f"Scene file '{scene_id}.yaml' not found")
    target.unlink()
    _reload_engine(ctx)
    logger.info("Scene '%s' deleted and engine reloaded", scene_id)
    return {"ok": True, "id": scene_id}


# ── Look (named DMX state) CRUD ───────────────────────────────────────────────

def _looks_path(ctx: AppContext) -> Path:
    return ctx.config_path.parent / "scenes.yaml"


def _reload_looks(ctx: AppContext, looks_data: list[dict]) -> None:
    ctx.scene_manager.load_scenes(looks_data)
    # Update the state snapshot's known scenes list
    ctx.scene_manager._scenes  # already updated by load_scenes


@router.get("/api/looks")
async def list_looks(ctx: AppContext = Depends(get_ctx)):
    data = load_scenes(_looks_path(ctx))
    return {"looks": data}


class LookModel(BaseModel):
    id: str | None = None
    name: str
    fixtures: dict = {}  # fixture_id -> {channel_name: value}


@router.post("/api/looks")
async def save_look(body: LookModel, ctx: AppContext = Depends(get_ctx)):
    path = _looks_path(ctx)
    existing = load_scenes(path)
    look_id = body.id or _safe_id(body.name)
    updated = [s for s in existing if s.get("id") != look_id]
    new_look = {
        "id": look_id,
        "name": body.name,
        "fixtures": body.fixtures,
    }
    updated.append(new_look)
    with open(path, "w") as fh:
        yaml.dump(updated, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _reload_looks(ctx, updated)
    logger.info("Look '%s' saved", look_id)
    return {"ok": True, "id": look_id}


@router.delete("/api/looks/{look_id}")
async def delete_look(look_id: str, ctx: AppContext = Depends(get_ctx)):
    path = _looks_path(ctx)
    existing = load_scenes(path)
    updated = [s for s in existing if s.get("id") != look_id]
    if len(updated) == len(existing):
        raise HTTPException(404, f"Look '{look_id}' not found")
    with open(path, "w") as fh:
        yaml.dump(updated, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _reload_looks(ctx, updated)
    logger.info("Look '%s' deleted", look_id)
    return {"ok": True, "id": look_id}
