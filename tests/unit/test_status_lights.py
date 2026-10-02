from parade.config.models import StatusLightConfig, StatusLightsConfig
from parade.core.event_bus import EventBus
from parade.core.events import CueStartedEvent
from parade.core.state import SystemState, SystemStateMachine
from parade.health.power import PowerMonitor, build_status
from parade.status_lights.blinkstick import base_serial
from parade.status_lights.controller import (
    GREEN, ORANGE, RED, RESEND_S, WHITE, YELLOW,
    Pattern, StatusLights, health_pattern, render, state_pattern,
)
from parade.status_lights.simulated import SimulatedStatusLights

STATE = ("BS000001", 1)
HEALTH = ("BS000002", 1)


def make_lights(brightness=1.0):
    config = StatusLightsConfig(
        brightness=brightness,
        state_led=StatusLightConfig(serial=STATE[0], led_index=STATE[1]),
        health_led=StatusLightConfig(serial=HEALTH[0], led_index=HEALTH[1]),
    )
    sm = SystemStateMachine()
    pm = PowerMonitor()
    pm.status = build_status(0x0, False, 45.0)
    bus = EventBus()
    driver = SimulatedStatusLights()
    return StatusLights(config, driver, sm, pm, bus), sm, pm, bus, driver


def test_base_serial_drops_firmware_suffix():
    assert base_serial("BS025458-3.0") == "BS025458"
    assert base_serial("BS025458") == "BS025458"


def test_every_state_has_a_pattern():
    for state in SystemState:
        assert state_pattern(state).color != (0, 0, 0)
    assert state_pattern(SystemState.RUNNING).color == GREEN
    assert state_pattern(SystemState.EMERGENCY_STOP).mode == "blink"


def test_health_patterns():
    assert health_pattern(build_status(0x0, False, 45.0)) == Pattern(GREEN, "pulse", 0.5)
    assert health_pattern(build_status(0x10000, False, 45.0)).color == YELLOW
    uv = health_pattern(build_status(None, True, 45.0))
    assert (uv.color, uv.mode) == (RED, "blink")
    assert health_pattern(build_status(0x4, False, 45.0)).color == ORANGE
    assert health_pattern(build_status(None, None, None)).color == WHITE


def test_render_scales_by_brightness_and_blinks():
    blink = Pattern(RED, "blink", 1.0)
    assert render(blink, 0.1, 0.2) == (51, 0, 0)
    assert render(blink, 0.6, 0.2) == (0, 0, 0)


def test_pulse_never_goes_fully_dark():
    pulse = Pattern(GREEN, "pulse", 0.5)
    assert min(pulse.level(t / 10) for t in range(40)) > 0.1


def test_frame_follows_state():
    lights, sm, *_ = make_lights()
    sm.transition(SystemState.SAFE)
    sm.transition(SystemState.READY)
    assert lights.frame(0.0)["state"] == YELLOW


async def test_cue_start_flashes_state_led_white():
    lights, sm, _, bus, _ = make_lights()
    sm.transition(SystemState.SAFE)
    sm.transition(SystemState.READY)
    sm.transition(SystemState.RUNNING)
    await lights.start()
    await bus.publish(CueStartedEvent(source="test", cue_id="c1"))
    import time
    assert lights.frame(time.monotonic())["state"] == WHITE
    assert lights.frame(time.monotonic() + 1.0)["state"] == GREEN


async def test_update_writes_changes_and_resends():
    lights, sm, _, _, driver = make_lights()
    await lights.update(0.0)
    assert driver.get_leds()[STATE] == state_pattern(SystemState.BOOTING).color

    driver._leds.clear()
    await lights.update(0.01)  # unchanged state colour: not rewritten yet
    assert STATE not in driver.get_leds()
    await lights.update(RESEND_S + 0.01)
    assert STATE in driver.get_leds()


async def test_start_turns_off_unused_led():
    lights, *_, driver = make_lights()
    await driver.set_led(STATE[0], 0, (255, 0, 0))
    await lights.start()
    assert driver.get_leds()[(STATE[0], 0)] == (0, 0, 0)
    assert driver.get_leds()[(HEALTH[0], 0)] == (0, 0, 0)


async def test_stop_turns_leds_off():
    lights, *_, driver = make_lights()
    await lights.start()
    await lights.update(0.0)
    await lights.stop()
    assert driver.get_leds()[STATE] == driver.get_leds()[HEALTH] == (0, 0, 0)


async def test_run_returns_when_nothing_configured():
    lights, *_ = make_lights()
    lights._config = StatusLightsConfig()
    await lights.run()  # would loop forever if it didn't return
