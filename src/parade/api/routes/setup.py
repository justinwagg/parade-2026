import logging
import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from parade.api.context import AppContext
from parade.config.models import FixtureConfig, GPIOInputConfig, RelayOutputConfig, FixtureGroupConfig
from parade.dmx.fixtures import FixtureManager
from .dependencies import get_ctx

router = APIRouter()
logger = logging.getLogger(__name__)


class SetupPayload(BaseModel):
    fixtures: list[dict] = []
    fixture_groups: list[dict] = []
    gpio_inputs: list[dict] = []
    relay_outputs: list[dict] = []


@router.get("/api/profiles")
async def get_profiles(ctx: AppContext = Depends(get_ctx)):
    profiles = ctx.fixture_manager.get_all_profiles()
    return {
        "profiles": [
            {
                "id": p.id,
                "name": p.name,
                "channel_count": p.channel_count,
                "color_model": p.color_model,
                "channels": p.channels,
                "notes": p.notes,
                "source": p.source,
            }
            for p in profiles.values()
        ]
    }


@router.get("/api/setup")
async def get_setup(ctx: AppContext = Depends(get_ctx)):
    return {
        "fixtures": [f.model_dump() for f in ctx.config.fixtures],
        "fixture_groups": [g.model_dump() for g in ctx.config.fixture_groups],
        "gpio_inputs": [g.model_dump() for g in ctx.config.gpio_inputs],
        "relay_outputs": [r.model_dump() for r in ctx.config.relay_outputs],
    }


@router.post("/api/setup")
async def post_setup(body: SetupPayload, ctx: AppContext = Depends(get_ctx)):
    try:
        new_fixtures = [FixtureConfig.model_validate(f) for f in body.fixtures]
        new_groups = [FixtureGroupConfig.model_validate(g) for g in body.fixture_groups]
        new_gpio = [GPIOInputConfig.model_validate(g) for g in body.gpio_inputs]
        new_relays = [RelayOutputConfig.model_validate(r) for r in body.relay_outputs]
    except Exception as e:
        raise HTTPException(400, f"Validation error: {e}")

    # Verify all fixture profiles exist before committing changes
    known_profiles = set(ctx.fixture_manager.get_all_profiles().keys())
    for f in new_fixtures:
        if f.profile not in known_profiles:
            raise HTTPException(400, f"Unknown profile '{f.profile}' for fixture '{f.id}'")

    # Update in-memory config
    ctx.config.fixtures = new_fixtures
    ctx.config.fixture_groups = new_groups
    ctx.config.gpio_inputs = new_gpio
    ctx.config.relay_outputs = new_relays

    # Hot-reload engine groups
    ctx.show_engine.reload_groups(new_groups)

    # Reinitialize fixture manager (profiles unchanged, fixtures updated)
    profiles_dict = {
        p_id: {
            "id": p.id, "name": p.name, "channel_count": p.channel_count,
            "color_model": p.color_model, "channels": p.channels,
            "notes": p.notes, "source": p.source,
        }
        for p_id, p in ctx.fixture_manager.get_all_profiles().items()
    }
    ctx.fixture_manager = FixtureManager(profiles_dict, new_fixtures)

    # Hot-reload simulated GPIO (preserve existing physical states for unchanged pins)
    from parade.gpio.simulated import SimulatedGPIO
    if isinstance(ctx.gpio, SimulatedGPIO):
        old_phys = ctx.gpio.get_physical_states()
        ctx.gpio._configs = {c.id: c for c in new_gpio}
        ctx.gpio._physical_states = {
            c.id: old_phys.get(c.id, c.active_low) for c in new_gpio
        }

    # Hot-reload simulated relay (preserve existing on/off states for unchanged relays)
    from parade.relay.simulated import SimulatedRelay
    if isinstance(ctx.relay_manager, SimulatedRelay):
        old_states = ctx.relay_manager.get_all_states()
        ctx.relay_manager._states = {
            r.id: old_states.get(r.id, False) for r in new_relays
        }

    # Persist to YAML
    persisted = False
    warning = None
    try:
        _write_config(ctx)
        persisted = True
    except Exception as e:
        logger.warning("Failed to persist config to YAML: %s", e)
        warning = str(e)

    hw = ctx.config.hardware
    if persisted and "rpi" in (hw.gpio_driver, hw.relay_driver):
        warning = "Saved. GPIO/relay pin changes take effect after restarting parade (sudo systemctl restart parade)."

    result = {"ok": True, "persisted": persisted}
    if warning:
        result["warning"] = warning
    return result


def _write_config(ctx: AppContext) -> None:
    with open(ctx.config_path) as f:
        data = yaml.safe_load(f) or {}

    data["fixtures"] = [f.model_dump() for f in ctx.config.fixtures]
    data["fixture_groups"] = [g.model_dump() for g in ctx.config.fixture_groups]
    data["gpio_inputs"] = [g.model_dump() for g in ctx.config.gpio_inputs]
    data["relay_outputs"] = [r.model_dump() for r in ctx.config.relay_outputs]

    with open(ctx.config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
