"""Live show settings: everything an operator can change while the show runs.

Stored in config/show.yaml and edited from the dashboard's Show tab. Every
effect reads these each frame, so a change shows up on the next frame.
Percentages are 0-100; colours are [r, g, b].
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

Color = list[int]
Pct = float


def _color(r: int, g: int, b: int) -> Color:
    return [r, g, b]


class CycleParams(BaseModel):
    stop_duration_s: float = Field(default=30.0, ge=1, le=600)
    # Index within this many seconds of the performer button -> one extra revolution
    extra_rev_window_s: float = Field(default=10.0, ge=0, le=120)


class WatchdogParams(BaseModel):
    """Cut the motor (FAULT) if no index pass arrives while the booth should be turning."""
    enabled: bool = True
    factor: float = Field(default=2.5, ge=1.2, le=10)  # x the measured revolution time
    first_revolution_s: float = Field(default=60.0, ge=5, le=600)  # before a revolution is measured


class SparkParams(BaseModel):
    enabled: bool = True
    on_ms: float = Field(default=1000, ge=50, le=10000)
    interval_s: float = Field(default=20.0, ge=0.5, le=600)  # off time between bursts
    jitter_pct: Pct = Field(default=30, ge=0, le=100)  # randomise the interval by +/- this much
    level_pct: Pct = Field(default=80, ge=0, le=100)  # spark height


class FogNormalParams(BaseModel):
    """Periodic fog while the booth turns (and after the boost during a stop)."""
    enabled: bool = True
    on_s: float = Field(default=3.0, ge=0.5, le=120)
    interval_s: float = Field(default=20.0, ge=1, le=600)
    haze_pct: Pct = Field(default=60, ge=0, le=100)
    fan_pct: Pct = Field(default=60, ge=0, le=100)
    during_stop: bool = True  # resume the periodic fog once the boost ends mid-stop


class FogBoostParams(BaseModel):
    """Full blast from the arming index (incl. the extra revolution) into the stop."""
    haze_pct: Pct = Field(default=100, ge=0, le=100)
    fan_pct: Pct = Field(default=100, ge=0, le=100)
    after_stop_s: float = Field(default=10.0, ge=0, le=600)


class LightningParams(BaseModel):
    """Random, independent flashes per fixture (or per pixel side)."""
    min_gap_ms: float = Field(default=300, ge=20, le=30000)
    max_gap_ms: float = Field(default=2500, ge=20, le=60000)
    flash_ms: float = Field(default=80, ge=10, le=2000)
    burst_chance_pct: Pct = Field(default=35, ge=0, le=100)  # chance a flash flickers 2-4 times
    brightness_pct: Pct = Field(default=100, ge=0, le=100)
    palette: list[Color] = Field(
        default_factory=lambda: [_color(255, 255, 255), _color(170, 200, 255), _color(140, 90, 255)],
        min_length=1,
    )


class ExteriorTurningParams(BaseModel):
    """Exterior look while the booth turns (outside the fog boost)."""
    effect: Literal["off", "lightning", "solid", "pulse"] = "off"
    color: Color = Field(default_factory=lambda: _color(255, 255, 255))
    pulse_period_s: float = Field(default=1.5, ge=0.2, le=20)
    brightness_pct: Pct = Field(default=100, ge=0, le=100)
    lightning: LightningParams = Field(default_factory=LightningParams)


class ExteriorParams(BaseModel):
    """Exterior lights. The fog look (effect/color/lightning) runs during the fog
    boost, and for the whole stop if stop_coverage is 'whole_stop'."""
    enabled: bool = True
    effect: Literal["lightning", "solid", "pulse"] = "lightning"
    color: Color = Field(default_factory=lambda: _color(255, 255, 255))
    pulse_period_s: float = Field(default=1.5, ge=0.2, le=20)
    lightning: LightningParams = Field(default_factory=lambda: LightningParams(min_gap_ms=150, max_gap_ms=900))
    stop_coverage: Literal["boost", "whole_stop"] = "boost"
    turning: ExteriorTurningParams = Field(default_factory=ExteriorTurningParams)


class SideParams(BaseModel):
    """One side of the booth's top NeoPixels."""
    effect: Literal["off", "solid", "chase", "pulse", "lightning"] = "chase"
    color: Color = Field(default_factory=lambda: _color(0, 60, 255))
    background: Color = Field(default_factory=lambda: _color(0, 0, 0))
    period_s: float = Field(default=1.5, ge=0.1, le=30)  # chase lap / pulse period
    length: int = Field(default=4, ge=1, le=200)  # chase run length in pixels
    brightness_pct: Pct = Field(default=100, ge=0, le=100)
    lightning: LightningParams = Field(default_factory=LightningParams)


class StopParams(BaseModel):
    """Interior + NeoPixels during the stop: dark at once, pulse throughout,
    and the pulse fades up to full when the performer emerges."""
    pulse_color: Color = Field(default_factory=lambda: _color(255, 0, 60))
    pulse_period_s: float = Field(default=2.0, ge=0.2, le=20)
    pulse_depth_pct: Pct = Field(default=70, ge=0, le=100)  # how far each pulse dips
    dark_level_pct: Pct = Field(default=35, ge=0, le=100)  # pulse brightness before the fade-up
    fade_delay_s: float = Field(default=3.0, ge=0, le=120)
    fade_duration_s: float = Field(default=4.0, ge=0, le=120)
    fade_color: Color = Field(default_factory=lambda: _color(255, 180, 120))


class SparkCalibration(BaseModel):
    """Weigh the hopper before/after a test run to get grams per spark-second."""
    grams_per_spark_s: float | None = Field(default=None, ge=0)
    hopper_grams: float = Field(default=0, ge=0)
    parade_minutes: float = Field(default=90, ge=0)


def _default_sides() -> list[SideParams]:
    return [SideParams() for _ in range(4)]


class ShowParams(BaseModel):
    cycle: CycleParams = Field(default_factory=CycleParams)
    watchdog: WatchdogParams = Field(default_factory=WatchdogParams)
    spark: SparkParams = Field(default_factory=SparkParams)
    fog: FogNormalParams = Field(default_factory=FogNormalParams)
    fog_boost: FogBoostParams = Field(default_factory=FogBoostParams)
    interior: LightningParams = Field(default_factory=LightningParams)
    exterior: ExteriorParams = Field(default_factory=ExteriorParams)
    sides: list[SideParams] = Field(default_factory=_default_sides)
    stop: StopParams = Field(default_factory=StopParams)
    calibration: SparkCalibration = Field(default_factory=SparkCalibration)


def deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge patch into a copy of base (lists are replaced, not merged)."""
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class ShowParamStore:
    """Holds the live ShowParams and saves every change to disk."""

    def __init__(self, path: Path):
        self.path = path
        self.params = self._load()

    def _load(self) -> ShowParams:
        try:
            data = yaml.safe_load(self.path.read_text()) or {}
        except FileNotFoundError:
            return ShowParams()
        try:
            return ShowParams.model_validate(data)
        except ValueError as e:
            logger.error("Invalid %s, using defaults: %s", self.path, e)
            return ShowParams()

    def update(self, patch: dict) -> ShowParams:
        """Apply a partial update. Raises pydantic.ValidationError if it's invalid."""
        merged = deep_merge(self.params.model_dump(), patch)
        params = ShowParams.model_validate(merged)
        self.params = params
        self.save()
        return params

    def set(self, path: str, value) -> ShowParams:
        """Set one setting by dotted path, e.g. 'sides.2.color' or 'spark.on_ms'."""
        data = self.params.model_dump()
        keys = path.split(".")
        node = data
        for key in keys[:-1]:
            node = node[int(key)] if isinstance(node, list) else node[key]
        last = keys[-1]
        if isinstance(node, list):
            node[int(last)] = value
        elif last in node:
            node[last] = value
        else:
            raise KeyError(path)
        params = ShowParams.model_validate(data)
        self.params = params
        self.save()
        return params

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(yaml.safe_dump(self.params.model_dump(), sort_keys=False, default_flow_style=None))
        tmp.replace(self.path)
