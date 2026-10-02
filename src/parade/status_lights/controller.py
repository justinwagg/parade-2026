"""Drive the status lights from the system state and the Pi's power/thermal health.

Indicator only: nothing reads the lights back, and a missing or failing stick
never affects the show.

  state LED   solid colour per SystemState (same colours as the dashboard pill);
              EMERGENCY_STOP blinks red fast. A cue starting flashes it white.
  health LED  pulses slowly while the app is running (a heartbeat: if it stops
              pulsing, the app has hung or exited). Green = OK, yellow = a dip or
              throttle happened since boot or the CPU is warm, white = no health
              data. Blinks fast on a live problem: red = under-voltage,
              orange = throttled or overheating.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import Literal

from parade.config.models import StatusLightConfig, StatusLightsConfig
from parade.core.state import SystemState, SystemStateMachine
from parade.health.power import PowerMonitor, PowerStatus
from parade.status_lights.interface import Color, StatusLightInterface

logger = logging.getLogger(__name__)

TICK_S = 0.05
RESEND_S = 1.0  # rewrite unchanged LEDs this often, so a re-plugged stick catches up
CUE_FLASH_S = 0.15

OFF: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)
RED: Color = (255, 0, 0)
ORANGE: Color = (255, 70, 0)
YELLOW: Color = (255, 160, 0)
GREEN: Color = (0, 255, 0)
BLUE: Color = (0, 60, 255)
PURPLE: Color = (140, 0, 255)


@dataclass(frozen=True)
class Pattern:
    color: Color
    mode: Literal["solid", "blink", "pulse"] = "solid"
    hz: float = 0.0
    scale: float = 1.0  # relative to the configured brightness

    def level(self, t: float) -> float:
        if self.mode == "blink":
            return self.scale if (t * self.hz) % 1.0 < 0.5 else 0.0
        if self.mode == "pulse":
            return self.scale * (0.15 + 0.85 * (0.5 - 0.5 * math.cos(2 * math.pi * self.hz * t)))
        return self.scale


STATE_PATTERNS: dict[SystemState, Pattern] = {
    SystemState.BOOTING: Pattern(BLUE),
    SystemState.SAFE: Pattern(WHITE, scale=0.4),
    SystemState.READY: Pattern(YELLOW),
    SystemState.RUNNING: Pattern(GREEN),
    SystemState.PAUSED: Pattern(ORANGE),
    SystemState.MANUAL: Pattern(PURPLE),
    SystemState.EMERGENCY_STOP: Pattern(RED, "blink", 4.0),
    SystemState.FAULT: Pattern(RED),
}

HEARTBEAT_HZ = 0.5
PROBLEM_BLINK_HZ = 4.0


def state_pattern(state: SystemState) -> Pattern:
    return STATE_PATTERNS.get(state, Pattern(RED))


def health_pattern(status: PowerStatus) -> Pattern:
    level = status.level
    if level == "bad":
        color = RED if status.undervoltage_now else ORANGE
        return Pattern(color, "blink", PROBLEM_BLINK_HZ)
    if level == "warn":
        return Pattern(YELLOW, "pulse", HEARTBEAT_HZ)
    if level == "ok":
        return Pattern(GREEN, "pulse", HEARTBEAT_HZ)
    return Pattern(WHITE, "pulse", HEARTBEAT_HZ, scale=0.4)


def render(pattern: Pattern, t: float, brightness: float) -> Color:
    k = pattern.level(t) * brightness
    return tuple(round(c * k) for c in pattern.color)  # type: ignore[return-value]


class StatusLights:
    def __init__(
        self,
        config: StatusLightsConfig,
        driver: StatusLightInterface,
        state_machine: SystemStateMachine,
        power_monitor: PowerMonitor,
        event_bus,
    ):
        self._config = config
        self._driver = driver
        self._state_machine = state_machine
        self._power_monitor = power_monitor
        self._event_bus = event_bus
        self._flash_until = 0.0
        self._written: dict[tuple[str, int], tuple[Color, float]] = {}

    def _leds(self) -> list[tuple[str, StatusLightConfig]]:
        return [
            (role, led)
            for role, led in (("state", self._config.state_led), ("health", self._config.health_led))
            if led is not None
        ]

    async def start(self) -> None:
        await self._driver.start()
        # Each Nano has two LEDs; turn off the one facing into the enclosure in
        # case something (e.g. a test) left it on.
        for _, led in self._leds():
            await self._driver.set_led(led.serial, 1 - led.led_index, OFF)
        self._event_bus.subscribe("cue_started", self._on_cue_started)

    async def stop(self) -> None:
        self._event_bus.unsubscribe("cue_started", self._on_cue_started)
        for _, led in self._leds():
            await self._driver.set_led(led.serial, led.led_index, OFF)
        await self._driver.stop()

    async def _on_cue_started(self, event) -> None:
        self._flash_until = time.monotonic() + CUE_FLASH_S

    def frame(self, now: float) -> dict[str, Color]:
        """Colour for each configured role at monotonic time `now`."""
        brightness = self._config.brightness
        state = self._state_machine.state
        colors: dict[str, Color] = {}
        for role, _ in self._leds():
            if role == "state":
                halted = state in (SystemState.EMERGENCY_STOP, SystemState.FAULT)
                if now < self._flash_until and not halted:
                    colors[role] = render(Pattern(WHITE), now, brightness)
                else:
                    colors[role] = render(state_pattern(state), now, brightness)
            else:
                colors[role] = render(health_pattern(self._power_monitor.status), now, brightness)
        return colors

    async def update(self, now: float) -> None:
        """Write each LED whose colour changed, or that hasn't been written for RESEND_S."""
        colors = self.frame(now)
        for role, led in self._leds():
            key = (led.serial, led.led_index)
            color = colors[role]
            last = self._written.get(key)
            if last and last[0] == color and now - last[1] < RESEND_S:
                continue
            if await self._driver.set_led(led.serial, led.led_index, color):
                self._written[key] = (color, now)
            else:
                self._written.pop(key, None)

    async def run(self) -> None:
        if not self._leds():
            logger.info("No status lights configured")
            return
        while True:
            try:
                await self.update(time.monotonic())
            except Exception:
                logger.exception("Status light update failed")
                await asyncio.sleep(RESEND_S)
            await asyncio.sleep(TICK_S)
