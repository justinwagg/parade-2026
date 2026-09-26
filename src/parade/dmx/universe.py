import asyncio
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FadeTarget:
    channel: int  # 1-indexed
    start_value: int
    end_value: int


class DMXFade:
    def __init__(
        self,
        universe: "DMXUniverse",
        targets: list[FadeTarget],
        duration_ms: float,
    ):
        self._universe = universe
        self._targets = targets
        self._duration_ms = duration_ms
        self._task: asyncio.Task | None = None

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self._run())
        return self._task

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        t0 = time.monotonic()
        while True:
            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms >= self._duration_ms:
                for t in self._targets:
                    self._universe.set_channel(t.channel, t.end_value)
                break
            progress = elapsed_ms / self._duration_ms
            for t in self._targets:
                value = round(
                    t.start_value + (t.end_value - t.start_value) * progress
                )
                self._universe.set_channel(t.channel, value)
            await asyncio.sleep(0.02)  # 50 Hz fade update rate


class DMXUniverse:
    def __init__(self, universe_id: int, refresh_hz: int = 40):
        self.universe_id = universe_id
        self.refresh_hz = refresh_hz
        self._buffer = bytearray(512)
        self._active_fades: list[DMXFade] = []

    def set_channel(self, channel: int, value: int) -> None:
        """channel is 1-indexed (DMX convention)."""
        if 1 <= channel <= 512:
            self._buffer[channel - 1] = max(0, min(255, int(value)))

    def set_channels(self, values: dict[int, int]) -> None:
        for ch, val in values.items():
            self.set_channel(ch, val)

    def get_channel(self, channel: int) -> int:
        if 1 <= channel <= 512:
            return self._buffer[channel - 1]
        return 0

    def get_buffer(self) -> bytes:
        return bytes(self._buffer)

    def get_all_channels(self) -> dict[int, int]:
        """Return dict of channel (1-indexed) -> value for non-zero channels."""
        return {i + 1: v for i, v in enumerate(self._buffer) if v > 0}

    def blackout(self) -> None:
        self._buffer = bytearray(512)
        for fade in self._active_fades:
            fade.cancel()
        self._active_fades.clear()

    def start_fade(self, targets: list[FadeTarget], duration_ms: float) -> DMXFade:
        fade = DMXFade(self, targets, duration_ms)
        self._active_fades.append(fade)
        fade.start()
        return fade
