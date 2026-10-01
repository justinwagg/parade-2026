"""MANUAL mode: hands-on control for bench testing and setup.

In MANUAL the cue engine ignores every trigger (it only acts in RUNNING), and
the operator drives the hardware directly from the dashboard: relays on/off
with no time limit, NeoPixels set to a colour or a built-in animation, and a
per-input activation counter so a quick press of a switch still shows up
between dashboard refreshes.

Safety: relays can only be switched on while the state is MANUAL and the
e-stop is not active. Leaving MANUAL (to SAFE, FAULT or EMERGENCY_STOP) drives
the relays off through SafetyMonitor, and this class stops any pixel
animation and blanks the strip.
"""
import asyncio
import colorsys
import logging
import math
import time

from parade.core.state import SystemState

logger = logging.getLogger(__name__)

FRAME_S = 1 / 30
PIXEL_EFFECTS = ("rainbow", "chase", "breathe", "theater")


class ManualModeError(Exception):
    pass


class ManualController:
    def __init__(self, event_bus, state_machine, relay_manager, pixel_manager, safety):
        self._event_bus = event_bus
        self._state_machine = state_machine
        self._relay_manager = relay_manager
        self._pixel_manager = pixel_manager
        self._safety = safety
        self._pixel_task: asyncio.Task | None = None
        self.pixel_mode = "off"  # "off", "solid", or one of PIXEL_EFFECTS
        self._activations: dict[str, int] = {}
        self._last_change: dict[str, float] = {}

    async def start(self) -> None:
        self._event_bus.subscribe("gpio_changed", self._on_gpio)
        self._event_bus.subscribe("system_state_changed", self._on_state)

    async def stop(self) -> None:
        await self._cancel_pixel_task()

    @property
    def active(self) -> bool:
        return self._state_machine.state == SystemState.MANUAL

    def snapshot(self) -> dict:
        return {
            "pixel_mode": self.pixel_mode,
            "input_activations": dict(self._activations),
            # ms since epoch, matching the event log
            "input_last_change": {k: round(v * 1000) for k, v in self._last_change.items()},
        }

    def reset_input_counts(self) -> None:
        self._activations.clear()
        self._last_change.clear()

    def _require_manual(self) -> None:
        if not self.active:
            raise ManualModeError(
                f"Manual control needs MANUAL mode (state is {self._state_machine.state.value})"
            )

    # ── Relays ────────────────────────────────────────────────────────────────

    async def set_relay(self, relay_id: str, on: bool) -> None:
        # Off is always allowed, as in the cue engine.
        if on:
            self._require_manual()
            if self._safety is not None and self._safety.estop_active:
                raise ManualModeError("E-stop is pressed (or its monitor wire is open)")
        await self._relay_manager.set_relay(relay_id, on)
        logger.info("Manual: relay %s → %s", relay_id, "ON" if on else "off")

    # ── Pixels ────────────────────────────────────────────────────────────────

    async def set_pixel_color(self, r: int, g: int, b: int) -> None:
        self._require_manual()
        await self._cancel_pixel_task()
        await self._pixel_manager.set_all(r, g, b)
        await self._pixel_manager.show()
        self.pixel_mode = "solid" if (r or g or b) else "off"

    async def pixels_off(self) -> None:
        await self._cancel_pixel_task()
        await self._pixel_manager.set_all(0, 0, 0)
        await self._pixel_manager.show()
        self.pixel_mode = "off"

    async def run_pixel_effect(self, effect: str, color: tuple[int, int, int], speed: float) -> None:
        self._require_manual()
        if effect not in PIXEL_EFFECTS:
            raise ManualModeError(f"Unknown effect {effect!r}. Choose from: {', '.join(PIXEL_EFFECTS)}")
        await self._cancel_pixel_task()
        self.pixel_mode = effect
        self._pixel_task = asyncio.create_task(self._animate(effect, color, max(0.1, min(speed, 5.0))))

    async def _cancel_pixel_task(self) -> None:
        task, self._pixel_task = self._pixel_task, None
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _animate(self, effect: str, color: tuple[int, int, int], speed: float) -> None:
        px = self._pixel_manager
        n = px.get_pixel_count()
        if n <= 0:
            return
        r, g, b = color
        t0 = time.monotonic()
        try:
            while True:
                t = (time.monotonic() - t0) * speed
                if effect == "rainbow":
                    for i in range(n):
                        h = (i / n + t * 0.2) % 1.0
                        cr, cg, cb = colorsys.hsv_to_rgb(h, 1.0, 1.0)
                        await px.set_pixel(i, int(cr * 255), int(cg * 255), int(cb * 255))
                elif effect == "chase":
                    head = int(t * 15) % n
                    await px.set_all(0, 0, 0)
                    for k, level in enumerate((1.0, 0.4, 0.15)):  # head + fading tail
                        await px.set_pixel((head - k) % n, int(r * level), int(g * level), int(b * level))
                elif effect == "breathe":
                    level = 0.05 + 0.95 * (0.5 - 0.5 * math.cos(t * math.pi * 0.5))
                    await px.set_all(int(r * level), int(g * level), int(b * level))
                elif effect == "theater":
                    step = int(t * 6) % 3
                    for i in range(n):
                        if i % 3 == step:
                            await px.set_pixel(i, r, g, b)
                        else:
                            await px.set_pixel(i, 0, 0, 0)
                await px.show()
                await asyncio.sleep(FRAME_S)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Manual pixel effect %s failed", effect)

    # ── Events ────────────────────────────────────────────────────────────────

    async def _on_gpio(self, event) -> None:
        self._last_change[event.pin_id] = time.time()
        if event.active:
            self._activations[event.pin_id] = self._activations.get(event.pin_id, 0) + 1

    async def _on_state(self, event) -> None:
        if event.new_state == SystemState.MANUAL.value:
            self.reset_input_counts()
        elif event.old_state == SystemState.MANUAL.value:
            await self.pixels_off()
            logger.info("Left MANUAL: pixel effects stopped, strip blanked")
