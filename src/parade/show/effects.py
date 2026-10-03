"""Effect generators: small state machines asked "what now?" once per frame.

Each takes the current time and the live parameters on every call, so a
setting changed on the dashboard applies on the next frame.
"""
from __future__ import annotations

import math
import random

from parade.show.params import LightningParams

RGB = tuple[int, int, int]
OFF: RGB = (0, 0, 0)

BURST_GAP_MS = (40, 140)  # between flickers within one lightning strike


def scale(color, k: float) -> RGB:
    k = max(0.0, min(1.0, k))
    return tuple(round(c * k) for c in color)  # type: ignore[return-value]


def mix(a, b, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def wave(t: float, period_s: float) -> float:
    """0 -> 1 -> 0 over one period, starting dark at t=0."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * t / max(period_s, 0.01))


class Lightning:
    """Random strikes: a flash in a palette colour, sometimes flickering 2-4
    times, then a random gap. One instance per fixture so each flashes on its own."""

    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._next = None  # time of the next flash start
        self._flash_end = 0.0
        self._color: RGB = OFF
        self._burst_left = 0

    def reset(self) -> None:
        self._next = None
        self._flash_end = 0.0
        self._burst_left = 0

    def _gap(self, p: LightningParams) -> float:
        lo, hi = sorted((p.min_gap_ms, p.max_gap_ms))
        return self._rng.uniform(lo, hi) / 1000

    def frame(self, t: float, p: LightningParams) -> RGB:
        if self._next is None:
            self._next = t + self._gap(p) * self._rng.random()  # stagger the first strike
        if t < self._flash_end:
            return scale(self._color, p.brightness_pct / 100)
        if t >= self._next:
            if self._burst_left == 0:
                self._color = tuple(self._rng.choice(p.palette))  # type: ignore[assignment]
                if self._rng.random() < p.burst_chance_pct / 100:
                    self._burst_left = self._rng.randint(1, 3)
            else:
                self._burst_left -= 1
            self._flash_end = t + p.flash_ms / 1000 * self._rng.uniform(0.6, 1.4)
            if self._burst_left > 0:
                self._next = self._flash_end + self._rng.uniform(*BURST_GAP_MS) / 1000
            else:
                self._next = self._flash_end + self._gap(p)
            return scale(self._color, p.brightness_pct / 100)
        return OFF


class Intermittent:
    """On for on_s, then off for interval_s (+/- jitter), repeating. The jitter
    factor is drawn per cycle, so interval changes apply to the current gap."""

    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._on_until = None
        self._factor = 1.0

    def reset(self) -> None:
        self._on_until = None

    def frame(self, t: float, on_s: float, interval_s: float, jitter_pct: float = 0) -> bool:
        if self._on_until is None:
            # Start with a gap, not a burst, so entering a phase doesn't fire at once
            self._factor = 1 + self._rng.uniform(-1, 1) * jitter_pct / 100
            self._on_until = t - on_s
        next_on = self._on_until + interval_s * self._factor
        if t >= next_on:
            self._factor = 1 + self._rng.uniform(-1, 1) * jitter_pct / 100
            self._on_until = t + on_s
        return t < self._on_until


def chase(t: float, count: int, color, background, period_s: float, length: int, reverse: bool = False) -> list[RGB]:
    """A run of `length` pixels lapping the side once per period."""
    if count <= 0:
        return []
    head = int((t / max(period_s, 0.01)) * count) % count
    out = [tuple(background)] * count
    for k in range(min(length, count)):
        out[(head - k) % count] = tuple(color)
    if reverse:
        out.reverse()
    return out  # type: ignore[return-value]
