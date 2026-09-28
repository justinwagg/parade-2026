"""Raspberry Pi power and thermal health: under-voltage, throttling, CPU temperature.

Sources (all readable without root):
  - rpi_volt hwmon ``in0_lcrit_alarm`` — live under-voltage (supply below ~4.63 V)
  - ``vcgencmd get_throttled`` — live and sticky-since-boot throttle flags
  - thermal_zone0 — CPU temperature

On hosts without these (macOS) every reading is None and the status reports
``available=False``, which the dashboard shows as "n/a".
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

HWMON_ROOT = Path("/sys/class/hwmon")
THERMAL_TEMP = Path("/sys/class/thermal/thermal_zone0/temp")
CPUFREQ_DIR = Path("/sys/devices/system/cpu/cpu0/cpufreq")
MEMINFO = Path("/proc/meminfo")
UPTIME = Path("/proc/uptime")

HISTORY_S = 600  # dashboard chart window

TEMP_WARN_C = 70.0
TEMP_BAD_C = 80.0  # Pi firmware starts throttling the CPU at 80 °C

# `vcgencmd get_throttled` bit layout
UNDERVOLTAGE_NOW_BIT = 0
THROTTLE_NOW_BITS = {1: "ARM frequency capped", 2: "CPU throttled", 3: "soft temperature limit"}
UNDERVOLTAGE_SINCE_BOOT_BIT = 16
THROTTLE_SINCE_BOOT_BITS = {17: "ARM frequency capped", 18: "CPU throttled", 19: "soft temperature limit"}


@dataclass(frozen=True)
class PowerStatus:
    available: bool
    undervoltage_now: bool = False
    undervoltage_since_boot: bool = False
    throttle_now: tuple[str, ...] = ()
    throttle_since_boot: tuple[str, ...] = ()
    temp_c: float | None = None

    @property
    def level(self) -> str:
        """'na' | 'ok' | 'warn' | 'bad'."""
        if not self.available:
            return "na"
        hot = self.temp_c is not None and self.temp_c >= TEMP_BAD_C
        if self.undervoltage_now or self.throttle_now or hot:
            return "bad"
        warm = self.temp_c is not None and self.temp_c >= TEMP_WARN_C
        if self.undervoltage_since_boot or self.throttle_since_boot or warm:
            return "warn"
        return "ok"

    @property
    def label(self) -> str:
        level = self.level
        if level == "na":
            return "n/a"
        if level == "bad":
            if self.undervoltage_now:
                return "UNDER-VOLTAGE"
            if self.throttle_now:
                return "THROTTLED"
            return "OVERHEAT"
        if level == "warn":
            if self.undervoltage_since_boot:
                return "DIP SINCE BOOT"
            if self.throttle_since_boot:
                return "THROTTLED SINCE BOOT"
            return "WARM"
        return "OK"

    @property
    def details(self) -> list[str]:
        if not self.available:
            return ["Power monitoring unavailable (not running on a Raspberry Pi)"]
        lines = []
        if self.undervoltage_now:
            lines.append("Under-voltage NOW — supply below ~4.63 V at the Pi")
        elif self.undervoltage_since_boot:
            lines.append("Under-voltage occurred since boot (clears on reboot)")
        for flag in self.throttle_now:
            lines.append(f"{flag} NOW")
        for flag in self.throttle_since_boot:
            if flag not in self.throttle_now:
                lines.append(f"{flag} occurred since boot")
        if self.temp_c is not None:
            lines.append(f"CPU {self.temp_c:.1f} °C (warn {TEMP_WARN_C:.0f}, throttle {TEMP_BAD_C:.0f})")
        if not lines:
            lines.append("No power problems detected")
        return lines

    @property
    def flags(self) -> list[dict]:
        """Every get_throttled condition with its live and since-boot state."""
        rows = [{
            "name": "Under-voltage",
            "now": self.undervoltage_now,
            "since_boot": self.undervoltage_since_boot,
        }]
        for name in THROTTLE_NOW_BITS.values():
            rows.append({
                "name": name[0].upper() + name[1:],
                "now": name in self.throttle_now,
                "since_boot": name in self.throttle_since_boot,
            })
        return rows

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "flags": self.flags,
            "level": self.level,
            "label": self.label,
            "details": self.details,
            "undervoltage_now": self.undervoltage_now,
            "undervoltage_since_boot": self.undervoltage_since_boot,
            "throttle_now": list(self.throttle_now),
            "throttle_since_boot": list(self.throttle_since_boot),
            "temp_c": self.temp_c,
        }


UNAVAILABLE = PowerStatus(available=False)


def build_status(
    throttled: int | None, uv_alarm: bool | None, temp_c: float | None
) -> PowerStatus:
    """Combine raw readings into a PowerStatus. Any reading may be None."""
    if throttled is None and uv_alarm is None and temp_c is None:
        return UNAVAILABLE
    bits = throttled or 0
    return PowerStatus(
        available=True,
        undervoltage_now=bool(uv_alarm) or bool(bits & (1 << UNDERVOLTAGE_NOW_BIT)),
        undervoltage_since_boot=bool(bits & (1 << UNDERVOLTAGE_SINCE_BOOT_BIT)),
        throttle_now=tuple(n for b, n in THROTTLE_NOW_BITS.items() if bits & (1 << b)),
        throttle_since_boot=tuple(n for b, n in THROTTLE_SINCE_BOOT_BITS.items() if bits & (1 << b)),
        temp_c=temp_c,
    )


def _temp_band(temp_c: float | None) -> int:
    if temp_c is None:
        return 0
    if temp_c >= TEMP_BAD_C:
        return 2
    if temp_c >= TEMP_WARN_C:
        return 1
    return 0


def describe_changes(prev: PowerStatus, cur: PowerStatus) -> list[tuple[str, str]]:
    """Return (severity, message) pairs for conditions that changed between polls.

    severity is 'warning' or 'info'. A sticky since-boot flag appearing without the
    matching live flag means a dip/throttle happened and cleared between two polls.
    """
    if not cur.available:
        return []
    out: list[tuple[str, str]] = []
    first = not prev.available

    if cur.undervoltage_now and not prev.undervoltage_now:
        out.append(("warning", "Under-voltage detected — check supply voltage and wiring"))
    elif prev.undervoltage_now and not cur.undervoltage_now:
        out.append(("info", "Supply voltage recovered"))
    elif cur.undervoltage_since_boot and not prev.undervoltage_since_boot:
        when = "since boot" if first else "briefly between checks"
        out.append(("warning", f"Under-voltage occurred {when}"))

    for flag in cur.throttle_now:
        if flag not in prev.throttle_now:
            out.append(("warning", f"{flag}"))
    for flag in prev.throttle_now:
        if flag not in cur.throttle_now:
            out.append(("info", f"{flag} cleared"))
    for flag in cur.throttle_since_boot:
        if flag not in prev.throttle_since_boot and flag not in cur.throttle_now and flag not in prev.throttle_now:
            when = "since boot" if first else "briefly between checks"
            out.append(("warning", f"{flag} occurred {when}"))

    prev_band, cur_band = _temp_band(prev.temp_c), _temp_band(cur.temp_c)
    if cur_band > prev_band:
        limit = TEMP_BAD_C if cur_band == 2 else TEMP_WARN_C
        out.append(("warning", f"CPU temperature {cur.temp_c:.1f} °C (≥ {limit:.0f} °C)"))
    elif cur_band < prev_band and not first:
        out.append(("info", f"CPU temperature back to {cur.temp_c:.1f} °C"))

    return out


def find_undervoltage_alarm(hwmon_root: Path = HWMON_ROOT) -> Path | None:
    """Locate the rpi_volt hwmon alarm file (hwmon index varies between boots)."""
    try:
        for hw in sorted(hwmon_root.iterdir()):
            try:
                if (hw / "name").read_text().strip() == "rpi_volt":
                    alarm = hw / "in0_lcrit_alarm"
                    if alarm.exists():
                        return alarm
            except OSError:
                continue
    except OSError:
        pass
    return None


def parse_throttled(output: str) -> int | None:
    """Parse `vcgencmd get_throttled` output, e.g. 'throttled=0x50000'."""
    _, _, value = output.strip().partition("=")
    try:
        return int(value, 16)
    except ValueError:
        return None


def read_cpu_freq_mhz(cpufreq_dir: Path = CPUFREQ_DIR) -> dict | None:
    """Current / min / max CPU clock. The ondemand governor idles at min — that's normal."""
    try:
        cur, lo, hi = (
            int((cpufreq_dir / f).read_text()) // 1000
            for f in ("scaling_cur_freq", "scaling_min_freq", "scaling_max_freq")
        )
    except (OSError, ValueError):
        return None
    return {"cur": cur, "min": lo, "max": hi}


def read_memory_mb(meminfo: Path = MEMINFO) -> dict | None:
    try:
        fields = {}
        for line in meminfo.read_text().splitlines():
            key, _, rest = line.partition(":")
            fields[key] = int(rest.split()[0])
        total = fields["MemTotal"] // 1024
        used = total - fields["MemAvailable"] // 1024
    except (OSError, ValueError, KeyError, IndexError):
        return None
    return {"used": used, "total": total}


def read_uptime_s(uptime: Path = UPTIME) -> float | None:
    try:
        return float(uptime.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def read_load() -> dict | None:
    try:
        load1, load5, _ = os.getloadavg()
    except OSError:
        return None
    return {"load1": load1, "load5": load5, "cores": os.cpu_count() or 1}


@dataclass
class SessionStats:
    """Events and extremes since the app started, plus a rolling sample history."""
    started_ms: int = field(default_factory=lambda: round(time.time() * 1000))
    uv_events: int = 0
    last_uv_ms: int | None = None
    throttle_events: int = 0
    last_throttle_ms: int | None = None
    temp_max_c: float | None = None
    temp_max_ms: int | None = None
    history: deque = field(default_factory=lambda: deque(maxlen=HISTORY_S))

    def record(self, prev: PowerStatus, cur: PowerStatus, ts_ms: int, cpu_mhz: int | None) -> dict:
        """Fold one poll into the stats and return its history sample.

        A sample is flagged when the condition is live, or when its sticky
        since-boot bit newly appeared (it came and went between polls). Sticky
        bits already set on the first poll happened before this session and
        aren't counted.
        """
        new_uv = prev.available and cur.undervoltage_since_boot and not prev.undervoltage_since_boot
        new_throttle = prev.available and bool(set(cur.throttle_since_boot) - set(prev.throttle_since_boot))
        sample = {
            "ts": ts_ms,
            "temp_c": cur.temp_c,
            "cpu_mhz": cpu_mhz,
            "uv": cur.undervoltage_now or bool(new_uv),
            "throttle": bool(cur.throttle_now) or bool(new_throttle),
        }
        last = self.history[-1] if self.history else {"uv": False, "throttle": False}
        if sample["uv"] and not last["uv"]:
            self.uv_events += 1
        if sample["uv"]:
            self.last_uv_ms = ts_ms
        if sample["throttle"] and not last["throttle"]:
            self.throttle_events += 1
        if sample["throttle"]:
            self.last_throttle_ms = ts_ms
        if cur.temp_c is not None and (self.temp_max_c is None or cur.temp_c > self.temp_max_c):
            self.temp_max_c, self.temp_max_ms = cur.temp_c, ts_ms
        self.history.append(sample)
        return sample

    def to_dict(self) -> dict:
        return {
            "started_ts": self.started_ms,
            "uv_events": self.uv_events,
            "last_uv_ts": self.last_uv_ms,
            "throttle_events": self.throttle_events,
            "last_throttle_ts": self.last_throttle_ms,
            "temp_max_c": self.temp_max_c,
            "temp_max_ts": self.temp_max_ms,
        }


class PowerMonitor:
    def __init__(
        self,
        poll_s: float = 2.0,
        hwmon_root: Path = HWMON_ROOT,
        thermal_path: Path = THERMAL_TEMP,
        vcgencmd: str | None = None,
    ):
        self.poll_s = poll_s
        self.status: PowerStatus = UNAVAILABLE
        self.raw_throttled: int | None = None
        self.system: dict = {}
        self.session = SessionStats(history=deque(maxlen=int(HISTORY_S / poll_s)))
        self._uv_path = find_undervoltage_alarm(hwmon_root)
        self._thermal_path = thermal_path
        self._vcgencmd = vcgencmd if vcgencmd is not None else shutil.which("vcgencmd")

    def _read_uv_alarm(self) -> bool | None:
        if not self._uv_path:
            return None
        try:
            return self._uv_path.read_text().strip() == "1"
        except OSError:
            return None

    def _read_temp_c(self) -> float | None:
        try:
            return int(self._thermal_path.read_text().strip()) / 1000.0
        except (OSError, ValueError):
            return None

    async def _read_throttled(self) -> int | None:
        if not self._vcgencmd:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                self._vcgencmd, "get_throttled",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
        except (OSError, asyncio.TimeoutError):
            return None
        return parse_throttled(stdout.decode(errors="replace"))

    async def poll(self) -> PowerStatus:
        self.raw_throttled = await self._read_throttled()
        return build_status(self.raw_throttled, self._read_uv_alarm(), self._read_temp_c())

    def _read_system(self) -> dict:
        return {
            "cpu_mhz": read_cpu_freq_mhz(),
            "load": read_load(),
            "memory_mb": read_memory_mb(),
            "uptime_s": read_uptime_s(),
        }

    def snapshot(self) -> dict:
        """Everything the dashboard shows: status, system metrics, session stats."""
        return {
            **self.status.to_dict(),
            "raw_throttled": None if self.raw_throttled is None else hex(self.raw_throttled),
            "system": self.system,
            "session": self.session.to_dict(),
            "sample": self.session.history[-1] if self.session.history else None,
            "history_s": HISTORY_S,
            "poll_s": self.poll_s,
        }

    def history(self) -> list[dict]:
        return list(self.session.history)

    async def run(self, on_change: Callable[[str, str], None]) -> None:
        """Poll forever; call on_change(severity, message) for each condition change."""
        while True:
            cur = await self.poll()
            self.system = self._read_system()
            for severity, msg in describe_changes(self.status, cur):
                getattr(logger, severity)("Power: %s", msg)
                on_change(severity, msg)
            if cur.available:
                cpu = self.system.get("cpu_mhz")
                self.session.record(
                    self.status, cur, round(time.time() * 1000), cpu["cur"] if cpu else None
                )
            self.status = cur
            await asyncio.sleep(self.poll_s)
