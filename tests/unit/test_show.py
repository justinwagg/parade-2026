import random

import pytest

from parade.config.models import PixelSideConfig, PixelStripConfig, RelayOutputConfig, ShowConfig
from parade.core.event_bus import EventBus
from parade.core.events import GPIOChangeEvent, SystemStateChangedEvent
from parade.core.state import SystemState, SystemStateMachine
from parade.pixels.simulated import SimulatedPixels
from parade.relay.simulated import SimulatedRelay
from parade.show.controller import (
    Phase, ShowController, SparkUsage, pct_dmx, spark_dmx, spark_estimates,
)
from parade.show.effects import OFF, Intermittent, Lightning, chase, wave
from parade.show.params import LightningParams, ShowParamStore, ShowParams


class FakeScenes:
    def __init__(self):
        self.rgb: dict[str, tuple] = {}
        self.channels: dict[str, dict] = {}

    def set_fixture_rgb(self, fid, r, g, b):
        self.rgb[fid] = (r, g, b)

    def set_fixture_channels(self, fid, channels, fade_ms=0):
        self.channels[fid] = dict(channels)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def show(tmp_path):
    bus = EventBus()
    sm = SystemStateMachine()
    relay = SimulatedRelay([RelayOutputConfig(id="phone_booth_rotation", pin=18)])
    pixels = SimulatedPixels(PixelStripConfig(id="s", count=8))
    scenes = FakeScenes()
    cfg = ShowConfig(
        enabled=True,
        pixel_sides=[PixelSideConfig(id=f"side_{i}", start=i * 2, count=2) for i in range(4)],
    )
    store = ShowParamStore(tmp_path / "show.yaml")
    clock = FakeClock()
    ctrl = ShowController(
        cfg, store, bus, sm, None, relay, scenes, pixels,
        {"interior": ["in1", "in2", "in3"], "exterior": ["ex1", "ex2"]},
        SparkUsage(tmp_path / "usage.json"), clock=clock,
    )
    sm.transition(SystemState.SAFE)
    sm.transition(SystemState.READY)
    sm.transition(SystemState.RUNNING)
    return ctrl, relay, scenes, pixels, store, clock, bus, sm


def motor(relay):
    return relay.get_all_states()["phone_booth_rotation"]


# ── effects ──────────────────────────────────────────────────────────────────

def test_wave_starts_dark_and_peaks_mid_period():
    assert wave(0, 2) == pytest.approx(0)
    assert wave(1, 2) == pytest.approx(1)


def test_chase_wraps_and_reverses():
    px = chase(0.0, 5, (1, 1, 1), (0, 0, 0), period_s=1.0, length=2)
    assert px == [(1, 1, 1), (0, 0, 0), (0, 0, 0), (0, 0, 0), (1, 1, 1)]
    assert chase(0.0, 5, (1, 1, 1), (0, 0, 0), 1.0, 2, reverse=True) == list(reversed(px))


def test_intermittent_duty_cycle():
    gen = Intermittent(random.Random(1))
    on = sum(gen.frame(t / 10, on_s=1, interval_s=4) for t in range(1000))
    assert 150 < on < 250  # ~1 s on per 5 s


def test_intermittent_applies_new_interval_mid_gap():
    gen = Intermittent(random.Random(1))
    gen.frame(0.0, on_s=1, interval_s=100)
    assert not gen.frame(10.0, on_s=1, interval_s=100)
    assert gen.frame(10.0, on_s=1, interval_s=5)  # shortened gap takes effect now


def test_lightning_fixtures_flash_independently():
    p = LightningParams(min_gap_ms=100, max_gap_ms=400, flash_ms=50)
    a, b = Lightning(random.Random(1)), Lightning(random.Random(2))
    frames = [(a.frame(t / 100, p) != OFF, b.frame(t / 100, p) != OFF) for t in range(1000)]
    assert any(x for x, _ in frames) and any(y for _, y in frames)
    assert any(x != y for x, y in frames)


def test_lightning_uses_palette():
    p = LightningParams(min_gap_ms=20, max_gap_ms=40, flash_ms=50, palette=[[255, 0, 0]])
    fx = Lightning(random.Random(3))
    lit = {fx.frame(t / 100, p) for t in range(300)} - {OFF}
    assert lit == {(255, 0, 0)}


def test_dmx_scaling():
    assert spark_dmx(0) == 0
    assert spark_dmx(1) >= 10  # past the machine's dead zone
    assert spark_dmx(100) == 255
    assert pct_dmx(100) == 255 and pct_dmx(50) == 128


# ── params ───────────────────────────────────────────────────────────────────

def test_param_store_set_and_persist(tmp_path):
    store = ShowParamStore(tmp_path / "show.yaml")
    store.set("spark.on_ms", 500)
    store.set("sides.2.color", [1, 2, 3])
    again = ShowParamStore(tmp_path / "show.yaml")
    assert again.params.spark.on_ms == 500
    assert again.params.sides[2].color == [1, 2, 3]


def test_param_store_rejects_invalid(tmp_path):
    store = ShowParamStore(tmp_path / "show.yaml")
    with pytest.raises(ValueError):
        store.set("spark.on_ms", -5)
    with pytest.raises(KeyError):
        store.set("spark.nope", 1)
    assert store.params.spark.on_ms == 1000


# ── sequencer ────────────────────────────────────────────────────────────────

async def test_running_starts_rotation(show):
    ctrl, relay, *_ = show
    await ctrl.begin(1000.0)
    assert ctrl.phase == Phase.ROTATING
    assert motor(relay)


async def test_index_without_button_keeps_turning(show):
    ctrl, relay, *_ = show
    await ctrl.begin(1000.0)
    await ctrl.index(1010.0)
    assert ctrl.phase == Phase.ROTATING and motor(relay)


async def test_button_then_late_index_stops(show):
    ctrl, relay, *_ = show
    await ctrl.begin(1000.0)
    ctrl.button(1001.0)
    assert ctrl.phase == Phase.ARMED
    await ctrl.index(1020.0)  # 19 s later: no extra revolution
    assert ctrl.phase == Phase.STOPPED and not motor(relay)


async def test_button_then_quick_index_takes_extra_revolution(show):
    ctrl, relay, *_ = show
    await ctrl.begin(1000.0)
    ctrl.button(1010.0)
    await ctrl.index(1012.0)  # within the 10 s window
    assert ctrl.phase == Phase.EXTRA_REV and motor(relay)
    assert ctrl.boost_active(1012.0)
    await ctrl.index(1024.0)
    assert ctrl.phase == Phase.STOPPED and not motor(relay)


async def test_stop_ends_and_rotation_resumes(show):
    ctrl, relay, *_ = show
    await ctrl.begin(1000.0)
    ctrl.button(1001.0)
    await ctrl.index(1020.0)
    await ctrl.tick(1049.0)
    assert ctrl.phase == Phase.STOPPED
    await ctrl.tick(1050.0)  # 30 s default stop
    assert ctrl.phase == Phase.ROTATING and motor(relay)
    await ctrl.index(1062.0)  # flag cleared: next index doesn't stop
    assert ctrl.phase == Phase.ROTATING


async def test_fog_boost_runs_10s_after_the_stop(show):
    ctrl, *_ = show
    await ctrl.begin(1000.0)
    ctrl.button(1001.0)
    await ctrl.index(1020.0)
    assert ctrl.boost_active(1029.9)
    assert not ctrl.boost_active(1030.1)


async def test_stop_render(show):
    ctrl, relay, scenes, pixels, store, *_ = show
    store.set("fog.during_stop", False)
    await ctrl.begin(1000.0)
    ctrl.button(1001.0)
    await ctrl.index(1020.0)

    f = ctrl.render(1020.0)  # the instant it stops
    assert f.spark_pct == 0
    assert (f.haze_pct, f.fan_pct) == (100, 100)
    assert all(rgb == OFF for rgb in f.interior.values())
    assert all(rgb == OFF for rgb in f.pixels)
    lit = [any(rgb != OFF for rgb in ctrl.render(1020 + t / 20).exterior.values()) for t in range(100)]
    assert any(lit)  # exterior lightning flashes during the boost

    dim = max(ctrl.render(1021.0).interior["in1"])  # mid-pulse, before the fade-up
    bright = max(ctrl.render(1031.0).interior["in1"])  # after fade-up, same pulse phase
    assert 0 < dim < bright

    f = ctrl.render(1035.0)  # boost over
    assert (f.haze_pct, f.fan_pct) == (0, 0)
    assert all(rgb == OFF for rgb in f.exterior.values())


async def test_exterior_off_while_turning_without_boost(show):
    ctrl, *_ = show
    await ctrl.begin(1000.0)
    for t in range(100):
        assert all(rgb == OFF for rgb in ctrl.render(1000 + t / 10).exterior.values())


async def test_sparks_only_while_turning(show):
    ctrl, relay, scenes, pixels, store, *_ = show
    store.set("spark.interval_s", 0.5)
    store.set("spark.jitter_pct", 0)
    await ctrl.begin(1000.0)
    assert any(ctrl.render(1000 + t / 10).spark_pct for t in range(50))
    ctrl.button(1005.0)
    await ctrl.index(1020.0)
    assert not any(ctrl.render(1020 + t / 10).spark_pct for t in range(100))


async def test_leaving_running_blacks_out(show):
    ctrl, relay, scenes, pixels, store, clock, bus, sm = show
    await ctrl.start()
    await bus.publish(SystemStateChangedEvent(source="t", old_state="READY", new_state="RUNNING"))
    clock.t = 1001.0
    await ctrl.step(1001.0)
    await bus.publish(SystemStateChangedEvent(source="t", old_state="RUNNING", new_state="SAFE"))
    assert ctrl.phase == Phase.IDLE
    assert scenes.channels["cold_spark"] == {"intensity": 0}
    assert scenes.channels["fog_machine"] == {"haze": 0, "fan": 0}
    assert all(p == OFF for p in pixels.get_all_pixels())


async def test_gpio_events_drive_the_sequence(show):
    ctrl, relay, scenes, pixels, store, clock, bus, sm = show
    await ctrl.start()
    await bus.publish(SystemStateChangedEvent(source="t", old_state="READY", new_state="RUNNING"))
    clock.t = 1001.0
    await bus.publish(GPIOChangeEvent(source="t", pin_id="performer_button", active=True))
    clock.t = 1030.0
    await bus.publish(GPIOChangeEvent(source="t", pin_id="rotation_index", active=True))
    assert ctrl.phase == Phase.STOPPED


async def test_watchdog_faults_without_index(show):
    ctrl, relay, scenes, pixels, store, clock, bus, sm = show
    await ctrl.begin(1000.0)
    await ctrl.tick(1059.0)
    assert sm.state == SystemState.RUNNING
    await ctrl.tick(1061.0)  # 60 s before any revolution is measured
    assert sm.state == SystemState.FAULT
    assert not motor(relay)


async def test_watchdog_uses_measured_revolution(show):
    ctrl, relay, scenes, pixels, store, clock, bus, sm = show
    await ctrl.begin(1000.0)
    await ctrl.index(1010.0)
    await ctrl.index(1020.0)
    assert ctrl.revolution_s == pytest.approx(10.0)
    await ctrl.tick(1044.0)  # 2.5 x 10 s = 25 s
    assert sm.state == SystemState.RUNNING
    await ctrl.tick(1046.0)
    assert sm.state == SystemState.FAULT


async def test_watchdog_paused_while_stopped(show):
    ctrl, relay, scenes, pixels, store, clock, bus, sm = show
    store.set("cycle.stop_duration_s", 120)
    await ctrl.begin(1000.0)
    ctrl.button(1001.0)
    await ctrl.index(1020.0)
    await ctrl.tick(1100.0)
    assert sm.state == SystemState.RUNNING


async def test_spark_usage_and_estimates(show, tmp_path):
    ctrl, relay, scenes, pixels, store, *_ = show
    store.set("spark.interval_s", 0.5)
    store.set("spark.on_ms", 500)
    store.set("spark.jitter_pct", 0)
    store.set("spark.level_pct", 100)
    await ctrl.begin(1000.0)
    for t in range(100):
        await ctrl.step(1000 + t / 10)
    assert 3 < ctrl.usage.on_s < 7  # ~50 % duty over 10 s
    store.set("calibration.grams_per_spark_s", 2.0)
    store.set("calibration.hopper_grams", 1000)
    est = spark_estimates(store.params, ctrl.usage)
    assert est["duty_pct"] == 50.0
    assert est["left_g"] < 1000
    ctrl.usage.reset()
    assert SparkUsage(ctrl.usage.path).on_s == 0


def test_default_params_match_the_design():
    p = ShowParams()
    assert p.fog_boost.after_stop_s == 10
    assert p.stop.fade_delay_s == 3
    assert (p.fog_boost.haze_pct, p.fog_boost.fan_pct) == (100, 100)
    assert len(p.sides) == 4


def _ext_lit(ctrl, times):
    return [any(rgb != OFF for rgb in ctrl.render(t).exterior.values()) for t in times]


async def test_exterior_whole_stop_coverage(show):
    ctrl, relay, scenes, pixels, store, *_ = show
    store.set("exterior.effect", "solid")
    await ctrl.begin(1000.0)
    ctrl.button(1001.0)
    await ctrl.index(1020.0)
    assert _ext_lit(ctrl, [1025.0]) == [True]  # boost
    assert _ext_lit(ctrl, [1035.0]) == [False]  # boost over (10 s), default coverage
    store.set("exterior.stop_coverage", "whole_stop")
    assert _ext_lit(ctrl, [1035.0, 1049.0]) == [True, True]
    await ctrl.tick(1050.0)  # stop over: turning, turning effect off by default
    assert _ext_lit(ctrl, [1050.0]) == [False]


async def test_exterior_turning_look(show):
    ctrl, relay, scenes, pixels, store, *_ = show
    store.set("exterior.turning.effect", "solid")
    store.set("exterior.turning.color", [0, 0, 255])
    store.set("exterior.turning.brightness_pct", 50)
    await ctrl.begin(1000.0)
    assert set(ctrl.render(1001.0).exterior.values()) == {(0, 0, 128)}
    store.set("exterior.enabled", False)  # master switch
    assert _ext_lit(ctrl, [1002.0]) == [False]


async def test_fog_look_wins_over_turning_look_in_extra_revolution(show):
    ctrl, relay, scenes, pixels, store, *_ = show
    store.set("exterior.turning.effect", "solid")
    store.set("exterior.turning.color", [0, 0, 255])
    store.set("exterior.effect", "solid")
    store.set("exterior.color", [255, 0, 0])
    await ctrl.begin(1000.0)
    ctrl.button(1010.0)
    await ctrl.index(1012.0)
    assert set(ctrl.render(1013.0).exterior.values()) == {(255, 0, 0)}
