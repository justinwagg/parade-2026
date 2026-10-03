"""The phone booth show: a fixed sequence with live-adjustable looks.

  ROTATING --button--> ARMED --index--+-- < extra_rev_window_s after the button --> EXTRA_REV --index--> STOPPED
                                      +-- otherwise -------------------------------------------------> STOPPED
  STOPPED --stop_duration_s--> ROTATING (performer flag cleared)

The fog boost (full haze + fan) starts at the first index after the button and
runs until fog_boost.after_stop_s after the motor cuts. The exterior lights are
on exactly while the boost runs. Sparks run only while the booth turns.

The show only drives outputs in RUNNING. Leaving RUNNING (PAUSED, SAFE, E-STOP,
FAULT) blacks out the show's lights and puts spark and fog at zero; returning to
RUNNING starts again from ROTATING. The SafetyMonitor turns the motor relay off.

Index watchdog: while the motor is on, an index pass must arrive within
watchdog.factor x the measured revolution time (or first_revolution_s before one
is measured). If not (stuck switch, cut wire, jammed booth), the show goes to FAULT.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from parade.config.models import ShowConfig
from parade.core.state import SystemState, StateTransitionError
from parade.show.effects import OFF, RGB, Intermittent, Lightning, chase, mix, scale, wave
from parade.show.params import ShowParamStore, ShowParams, SideParams

logger = logging.getLogger(__name__)

USAGE_SAVE_S = 10.0


class Phase(str, Enum):
    IDLE = "IDLE"  # not RUNNING
    ROTATING = "ROTATING"
    ARMED = "ARMED"
    EXTRA_REV = "EXTRA_REV"
    STOPPED = "STOPPED"


TURNING = (Phase.ROTATING, Phase.ARMED, Phase.EXTRA_REV)


@dataclass
class Frame:
    spark_pct: float = 0.0
    haze_pct: float = 0.0
    fan_pct: float = 0.0
    interior: dict[str, RGB] = field(default_factory=dict)
    exterior: dict[str, RGB] = field(default_factory=dict)
    pixels: list[RGB] = field(default_factory=list)


def spark_dmx(pct: float) -> int:
    """0 = off; anything above maps past the machine's 0-9 dead zone."""
    return 0 if pct <= 0 else round(10 + min(pct, 100) / 100 * 245)


def pct_dmx(pct: float) -> int:
    return round(max(0.0, min(pct, 100.0)) / 100 * 255)


class SparkUsage:
    """Spark-on time since the hopper was last refilled, saved across restarts."""

    def __init__(self, path: Path):
        self.path = path
        self.on_s = 0.0
        self.weighted_s = 0.0  # on time x level, the best proxy for powder used
        self.since = time.time()
        self._dirty = False
        try:
            data = json.loads(path.read_text())
            self.on_s = float(data.get("on_s", 0))
            self.weighted_s = float(data.get("weighted_s", 0))
            self.since = float(data.get("since", self.since))
        except (OSError, ValueError):
            pass

    def add(self, dt: float, level_pct: float) -> None:
        self.on_s += dt
        self.weighted_s += dt * level_pct / 100
        self._dirty = True

    def reset(self) -> None:
        self.on_s = self.weighted_s = 0.0
        self.since = time.time()
        self._dirty = True
        self.save()

    def save(self) -> None:
        if not self._dirty:
            return
        try:
            self.path.write_text(json.dumps(
                {"on_s": round(self.on_s, 2), "weighted_s": round(self.weighted_s, 2), "since": self.since}
            ))
            self._dirty = False
        except OSError as e:
            logger.warning("Couldn't save spark usage: %s", e)


def spark_estimates(params: ShowParams, usage: SparkUsage) -> dict:
    """Powder use at the current settings, per hour of the booth turning."""
    sp, cal = params.spark, params.calibration
    on_s = sp.on_ms / 1000
    duty = on_s / (on_s + sp.interval_s) if sp.enabled else 0.0
    per_hour = duty * sp.level_pct / 100 * 3600  # weighted spark-seconds per hour of spinning
    out = {"duty_pct": round(duty * 100, 1), "weighted_s_per_hour": round(per_hour, 1),
           "used_weighted_s": round(usage.weighted_s, 1), "used_on_s": round(usage.on_s, 1),
           "since": usage.since}
    gps = cal.grams_per_spark_s
    if gps:
        used_g = usage.weighted_s * gps
        left_g = max(cal.hopper_grams - used_g, 0.0)
        g_per_hour = per_hour * gps
        out.update({
            "used_g": round(used_g, 1),
            "left_g": round(left_g, 1),
            "g_per_hour": round(g_per_hour, 1),
            "hours_left": round(left_g / g_per_hour, 2) if g_per_hour else None,
            "parade_need_g": round(g_per_hour * cal.parade_minutes / 60, 1),
        })
        parade_s = cal.parade_minutes * 60
        if parade_s and sp.level_pct and left_g:
            target_duty = left_g / (gps * sp.level_pct / 100 * parade_s)
            if 0 < target_duty < 1:
                out["interval_s_to_last_parade"] = round(on_s * (1 / target_duty - 1), 1)
    return out


class ShowController:
    def __init__(
        self,
        config: ShowConfig,
        store: ShowParamStore,
        event_bus,
        state_machine,
        safety,
        relay_manager,
        scene_manager,
        pixel_manager,
        groups: dict[str, list[str]],
        usage: SparkUsage,
        log: Callable[[str], None] = lambda msg: None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._cfg = config
        self._store = store
        self._bus = event_bus
        self._sm = state_machine
        self._safety = safety
        self._relays = relay_manager
        self._scenes = scene_manager
        self._pixels = pixel_manager
        self._interior = groups.get(config.interior_group, [])
        self._exterior = groups.get(config.exterior_group, [])
        self.usage = usage
        self._log = log
        self._clock = clock

        self.phase = Phase.IDLE
        self.phase_at = 0.0
        self.armed_at: float | None = None
        self.boost_from: float | None = None
        self.stop_at: float | None = None
        self.motor_on = False
        self.motor_since: float | None = None
        self.last_index_at: float | None = None
        self.revolution_s: float | None = None
        self.last_frame = Frame()

        self._spark = Intermittent()
        self._fog = Intermittent()
        self._interior_fx = {fid: Lightning() for fid in self._interior}
        self._exterior_fx = {fid: Lightning() for fid in self._exterior}
        self._side_fx = [Lightning() for _ in config.pixel_sides]
        self._last_tick: float | None = None
        self._last_usage_save = 0.0

    @property
    def params(self) -> ShowParams:
        return self._store.params

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self._bus.subscribe("gpio_changed", self._on_gpio)
        self._bus.subscribe("system_state_changed", self._on_state)
        if self._sm.state == SystemState.RUNNING:
            await self.begin(self._clock())

    async def stop(self) -> None:
        self._bus.unsubscribe("gpio_changed", self._on_gpio)
        self._bus.unsubscribe("system_state_changed", self._on_state)
        await self.end()
        self.usage.save()

    async def _on_state(self, event) -> None:
        if event.new_state == SystemState.RUNNING.value:
            await self.begin(self._clock())
        elif self.phase != Phase.IDLE:
            await self.end()

    async def _on_gpio(self, event) -> None:
        if self.phase == Phase.IDLE or not event.active:
            return
        now = self._clock()
        if event.pin_id == self._cfg.performer_input:
            self.button(now)
        elif event.pin_id == self._cfg.index_input:
            await self.index(now)

    # ── sequencer ────────────────────────────────────────────────────────────
    def _enter(self, phase: Phase, now: float) -> None:
        if phase != self.phase:
            logger.info("Show: %s -> %s", self.phase.value, phase.value)
            self._log(f"Show: {phase.value}")
        self.phase, self.phase_at = phase, now

    async def _motor(self, on: bool) -> None:
        if on and not self.motor_on:
            self.motor_since = self._clock()
        self.motor_on = on
        await self._relays.set_relay(self._cfg.motor_relay, on)

    async def begin(self, now: float) -> None:
        """RUNNING: start from ROTATING with fresh effects."""
        for fx in (self._spark, self._fog, *self._interior_fx.values(),
                   *self._exterior_fx.values(), *self._side_fx):
            fx.reset()
        self.armed_at = self.boost_from = self.stop_at = None
        self._last_tick = None
        await self._resume(now)

    async def end(self) -> None:
        """Left RUNNING: forget the cycle and black out the show's outputs."""
        self._enter(Phase.IDLE, self._clock())
        self.motor_on = False
        self.armed_at = self.boost_from = self.stop_at = None
        await self._write(self._blackout())

    async def _resume(self, now: float) -> None:
        self.armed_at = self.boost_from = self.stop_at = None
        self.last_index_at = now  # the booth restarts from the index position
        self._enter(Phase.ROTATING, now)
        await self._motor(True)
        self.motor_since = now

    def button(self, now: float) -> None:
        if self.phase == Phase.ROTATING:
            self.armed_at = now
            self._enter(Phase.ARMED, now)

    async def index(self, now: float) -> None:
        if self.phase not in TURNING:
            return
        full_lap = self.motor_since is not None and self.motor_since <= (self.last_index_at or -1)
        if self.last_index_at is not None and full_lap:
            lap = now - self.last_index_at
            if lap > 0.5:  # ignore switch bounce
                self.revolution_s = lap if self.revolution_s is None else 0.7 * self.revolution_s + 0.3 * lap
        self.last_index_at = now
        if self.phase == Phase.ARMED:
            self.boost_from = now
            if now - (self.armed_at or now) < self.params.cycle.extra_rev_window_s:
                self._enter(Phase.EXTRA_REV, now)
            else:
                await self._stop_booth(now)
        elif self.phase == Phase.EXTRA_REV:
            await self._stop_booth(now)

    async def _stop_booth(self, now: float) -> None:
        await self._motor(False)
        self.stop_at = now
        self._enter(Phase.STOPPED, now)

    def boost_active(self, now: float) -> bool:
        if self.boost_from is None or now < self.boost_from:
            return False
        if self.phase == Phase.EXTRA_REV:
            return True
        if self.phase == Phase.STOPPED and self.stop_at is not None:
            return now - self.stop_at < self.params.fog_boost.after_stop_s
        return False

    def watchdog_deadline(self) -> float | None:
        wd = self.params.watchdog
        if not wd.enabled or not self.motor_on or self.last_index_at is None:
            return None
        limit = wd.factor * self.revolution_s if self.revolution_s else wd.first_revolution_s
        return self.last_index_at + limit

    async def tick(self, now: float) -> None:
        """Timers: end of the stop, and the index watchdog."""
        if self.phase == Phase.STOPPED and self.stop_at is not None:
            if now - self.stop_at >= self.params.cycle.stop_duration_s:
                await self._resume(now)
        deadline = self.watchdog_deadline()
        if deadline is not None and now > deadline:
            msg = f"Index watchdog: no index pass for {now - self.last_index_at:.0f} s, motor stopped"
            logger.error(msg)
            self._log(msg)
            await self._motor(False)
            try:
                if self._safety is not None:
                    await self._safety.transition(SystemState.FAULT)
                else:
                    self._sm.transition(SystemState.FAULT)
            except StateTransitionError as e:
                logger.error("Watchdog couldn't enter FAULT: %s", e)

    # ── rendering ────────────────────────────────────────────────────────────
    def _blackout(self) -> Frame:
        return Frame(
            interior={f: OFF for f in self._interior},
            exterior={f: OFF for f in self._exterior},
            pixels=[OFF] * self._pixels.get_pixel_count(),
        )

    def _stop_look(self, now: float) -> RGB:
        """Dark at the stop, pulsing throughout; the pulse fades up to full at fade_delay_s."""
        st = self.params.stop
        ts = now - (self.stop_at or now)
        dark = st.dark_level_pct / 100
        if ts < st.fade_delay_s:
            envelope, progress = dark, 0.0
        else:
            progress = 1.0 if st.fade_duration_s <= 0 else min(1.0, (ts - st.fade_delay_s) / st.fade_duration_s)
            envelope = dark + (1 - dark) * progress
        low = 1 - st.pulse_depth_pct / 100
        level = low + (1 - low) * wave(ts, st.pulse_period_s)
        attack = min(1.0, ts / (st.pulse_period_s / 2))  # rise out of the blackout
        return scale(mix(st.pulse_color, st.fade_color, progress), envelope * level * attack)

    @staticmethod
    def _look(effect, color, period_s, brightness_pct, lightning, fx: Lightning, now: float, t0: float) -> RGB:
        b = brightness_pct / 100
        if effect == "off":
            return OFF
        if effect == "solid":
            return scale(color, b)
        if effect == "pulse":
            return scale(color, b * wave(now - t0, period_s))
        return fx.frame(now, lightning)

    def _side(self, i: int, side: SideParams, n: int, now: float, reverse: bool) -> list[RGB]:
        b = side.brightness_pct / 100
        if side.effect == "off" or n == 0:
            return [OFF] * n
        if side.effect == "solid":
            return [scale(side.color, b)] * n
        if side.effect == "pulse":
            return [scale(side.color, b * wave(now, side.period_s))] * n
        if side.effect == "lightning":
            return [self._side_fx[i].frame(now, side.lightning)] * n
        px = chase(now, n, side.color, side.background, side.period_s, side.length, reverse)
        return [scale(c, b) for c in px]

    def render(self, now: float) -> Frame:
        if self.phase == Phase.IDLE:
            return self._blackout()
        p = self.params
        f = Frame()
        turning = self.phase in TURNING
        boost = self.boost_active(now)

        if turning and p.spark.enabled and self._spark.frame(
            now, p.spark.on_ms / 1000, p.spark.interval_s, p.spark.jitter_pct
        ):
            f.spark_pct = p.spark.level_pct

        if boost:
            f.haze_pct, f.fan_pct = p.fog_boost.haze_pct, p.fog_boost.fan_pct
        elif p.fog.enabled and (turning or p.fog.during_stop) and self._fog.frame(
            now, p.fog.on_s, p.fog.interval_s
        ):
            f.haze_pct, f.fan_pct = p.fog.haze_pct, p.fog.fan_pct

        ext = p.exterior
        fog_look = boost or (self.phase == Phase.STOPPED and ext.stop_coverage == "whole_stop")
        for fid, fx in self._exterior_fx.items():
            if not ext.enabled:
                f.exterior[fid] = OFF
            elif fog_look:
                t0 = self.boost_from if self.boost_from is not None else (self.stop_at or now)
                f.exterior[fid] = self._look(ext.effect, ext.color, ext.pulse_period_s, 100,
                                             ext.lightning, fx, now, t0)
            elif turning:
                tl = ext.turning
                f.exterior[fid] = self._look(tl.effect, tl.color, tl.pulse_period_s, tl.brightness_pct,
                                             tl.lightning, fx, now, 0.0)
            else:
                f.exterior[fid] = OFF

        count = self._pixels.get_pixel_count()
        f.pixels = [OFF] * count
        if turning:
            for fid, fx in self._interior_fx.items():
                f.interior[fid] = fx.frame(now, p.interior)
            for i, side_cfg in enumerate(self._cfg.pixel_sides):
                side = p.sides[i] if i < len(p.sides) else SideParams(effect="off")
                n = max(0, min(side_cfg.count, count - side_cfg.start))
                f.pixels[side_cfg.start:side_cfg.start + n] = self._side(i, side, n, now, side_cfg.reverse)
        else:
            look = self._stop_look(now)
            f.interior = {fid: look for fid in self._interior}
            for side_cfg in self._cfg.pixel_sides:
                n = max(0, min(side_cfg.count, count - side_cfg.start))
                f.pixels[side_cfg.start:side_cfg.start + n] = [look] * n
        return f

    async def _write(self, f: Frame) -> None:
        for fid, rgb in {**f.interior, **f.exterior}.items():
            self._scenes.set_fixture_rgb(fid, *rgb)
        if self._cfg.spark_fixture:
            self._scenes.set_fixture_channels(self._cfg.spark_fixture, {"intensity": spark_dmx(f.spark_pct)})
        if self._cfg.fog_fixture:
            self._scenes.set_fixture_channels(
                self._cfg.fog_fixture, {"haze": pct_dmx(f.haze_pct), "fan": pct_dmx(f.fan_pct)}
            )
        for i, rgb in enumerate(f.pixels):
            await self._pixels.set_pixel(i, *rgb)
        await self._pixels.show()
        self.last_frame = f

    async def step(self, now: float) -> None:
        """One frame: timers, render, write, usage."""
        if self.phase == Phase.IDLE:
            return
        await self.tick(now)
        if self.phase == Phase.IDLE:  # the watchdog may have ended the show
            return
        f = self.render(now)
        await self._write(f)
        if self._last_tick is not None and f.spark_pct > 0:
            self.usage.add(now - self._last_tick, f.spark_pct)
        self._last_tick = now
        if now - self._last_usage_save >= USAGE_SAVE_S:
            self._last_usage_save = now
            self.usage.save()

    async def run(self) -> None:
        period = 1 / self._cfg.frame_hz
        while True:
            try:
                await self.step(self._clock())
            except Exception:
                logger.exception("Show frame failed")
            await asyncio.sleep(period)

    # ── status ───────────────────────────────────────────────────────────────
    def describe(self) -> str:
        """Short text for the OLED, e.g. 'STOPPED 12/30s'."""
        now = self._clock()
        if self.phase == Phase.STOPPED and self.stop_at is not None:
            return f"STOPPED {now - self.stop_at:.0f}/{self.params.cycle.stop_duration_s:.0f}s"
        if self.phase == Phase.ARMED and self.armed_at is not None:
            return f"ARMED {now - self.armed_at:.0f}s"
        return self.phase.value.replace("_", " ")

    def snapshot(self) -> dict:
        now = self._clock()
        f = self.last_frame
        deadline = self.watchdog_deadline()
        stop_left = None
        if self.phase == Phase.STOPPED and self.stop_at is not None:
            stop_left = max(0.0, self.params.cycle.stop_duration_s - (now - self.stop_at))
        return {
            "phase": self.phase.value,
            "phase_s": round(now - self.phase_at, 1) if self.phase != Phase.IDLE else None,
            "armed": self.phase in (Phase.ARMED, Phase.EXTRA_REV),
            "motor": self.motor_on,
            "boost": self.boost_active(now),
            "stop_left_s": None if stop_left is None else round(stop_left, 1),
            "revolution_s": None if self.revolution_s is None else round(self.revolution_s, 1),
            "watchdog_left_s": None if deadline is None else round(deadline - now, 1),
            "spark_pct": f.spark_pct,
            "haze_pct": f.haze_pct,
            "fan_pct": f.fan_pct,
            "spark": spark_estimates(self.params, self.usage),
        }
