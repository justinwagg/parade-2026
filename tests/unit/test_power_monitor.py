import pytest
from parade.health.power import (
    UNAVAILABLE,
    PowerMonitor,
    build_status,
    describe_changes,
    find_undervoltage_alarm,
    parse_throttled,
)


def test_parse_throttled():
    assert parse_throttled("throttled=0x0\n") == 0
    assert parse_throttled("throttled=0x50005") == 0x50005
    assert parse_throttled("garbage") is None


def test_no_readings_is_unavailable():
    status = build_status(None, None, None)
    assert status.available is False
    assert status.level == "na"
    assert status.label == "n/a"


def test_healthy():
    status = build_status(0x0, False, 45.0)
    assert status.level == "ok"
    assert status.label == "OK"


def test_undervoltage_now_from_hwmon_alarm():
    status = build_status(None, True, 45.0)
    assert status.undervoltage_now
    assert status.level == "bad"
    assert status.label == "UNDER-VOLTAGE"


def test_undervoltage_now_from_throttled_bit():
    status = build_status(0x1, None, None)
    assert status.undervoltage_now
    assert status.level == "bad"


def test_undervoltage_since_boot_is_warning():
    status = build_status(0x10000, False, 45.0)
    assert not status.undervoltage_now
    assert status.undervoltage_since_boot
    assert status.level == "warn"
    assert status.label == "DIP SINCE BOOT"


def test_throttle_now():
    status = build_status(0x40004, False, 45.0)
    assert status.throttle_now == ("CPU throttled",)
    assert status.level == "bad"
    assert status.label == "THROTTLED"


def test_temperature_bands():
    assert build_status(0, False, 72.0).label == "WARM"
    assert build_status(0, False, 81.0).label == "OVERHEAT"
    assert build_status(0, False, 81.0).level == "bad"


def test_to_dict_is_json_friendly():
    d = build_status(0x50005, True, 50.0).to_dict()
    assert d["level"] == "bad"
    assert isinstance(d["throttle_now"], list)
    assert d["details"]


def test_changes_undervoltage_appears_and_recovers():
    ok = build_status(0x0, False, 45.0)
    uv = build_status(0x50005, True, 45.0)
    recovered = build_status(0x50000, False, 45.0)

    msgs = [m for _, m in describe_changes(ok, uv)]
    assert any("Under-voltage detected" in m for m in msgs)

    changes = describe_changes(uv, recovered)
    assert ("info", "Supply voltage recovered") in changes
    # The sticky bit alone must not be re-reported as a new dip
    assert not any("occurred" in m for _, m in changes)


def test_changes_brief_dip_between_polls():
    ok = build_status(0x0, False, 45.0)
    dipped = build_status(0x10000, False, 45.0)
    assert describe_changes(ok, dipped) == [
        ("warning", "Under-voltage occurred briefly between checks")
    ]


def test_changes_first_poll_reports_since_boot():
    dipped = build_status(0x10000, False, 45.0)
    assert describe_changes(UNAVAILABLE, dipped) == [
        ("warning", "Under-voltage occurred since boot")
    ]


def test_no_changes_when_steady():
    s = build_status(0x10000, False, 45.0)
    assert describe_changes(s, s) == []


def test_temperature_change_messages():
    cool = build_status(0, False, 50.0)
    warm = build_status(0, False, 75.0)
    assert describe_changes(cool, warm)[0][0] == "warning"
    assert describe_changes(warm, cool)[0][0] == "info"


def test_find_undervoltage_alarm(tmp_path):
    (tmp_path / "hwmon0").mkdir()
    (tmp_path / "hwmon0" / "name").write_text("cpu_thermal\n")
    (tmp_path / "hwmon1").mkdir()
    (tmp_path / "hwmon1" / "name").write_text("rpi_volt\n")
    (tmp_path / "hwmon1" / "in0_lcrit_alarm").write_text("0\n")
    assert find_undervoltage_alarm(tmp_path) == tmp_path / "hwmon1" / "in0_lcrit_alarm"
    assert find_undervoltage_alarm(tmp_path / "missing") is None


async def test_monitor_poll_reads_files(tmp_path):
    hw = tmp_path / "hwmon" / "hwmon3"
    hw.mkdir(parents=True)
    (hw / "name").write_text("rpi_volt\n")
    (hw / "in0_lcrit_alarm").write_text("1\n")
    temp = tmp_path / "temp"
    temp.write_text("56789\n")

    monitor = PowerMonitor(hwmon_root=tmp_path / "hwmon", thermal_path=temp, vcgencmd="")
    status = await monitor.poll()
    assert status.undervoltage_now
    assert status.temp_c == pytest.approx(56.789)


async def test_monitor_unavailable_off_pi(tmp_path):
    monitor = PowerMonitor(
        hwmon_root=tmp_path / "none", thermal_path=tmp_path / "none", vcgencmd=""
    )
    assert (await monitor.poll()).available is False


# ── Session stats / history ─────────────────────────────────────────────────

from parade.health.power import SessionStats, read_cpu_freq_mhz, read_memory_mb


def test_session_counts_rising_edges_only():
    stats = SessionStats()
    ok = build_status(0x0, False, 45.0)
    uv = build_status(0x50005, True, 46.0)
    stats.record(UNAVAILABLE, ok, 1000, 1200)
    stats.record(ok, uv, 3000, 600)
    stats.record(uv, uv, 5000, 600)  # still low: same event
    stats.record(uv, build_status(0x50000, False, 45.0), 7000, 1200)
    assert stats.uv_events == 1
    assert stats.last_uv_ms == 5000
    assert stats.throttle_events == 1
    assert [s["uv"] for s in stats.history] == [False, True, True, False]


def test_session_counts_brief_dip_between_polls():
    stats = SessionStats()
    ok = build_status(0x0, False, 45.0)
    dipped = build_status(0x10000, False, 45.0)
    stats.record(UNAVAILABLE, ok, 1000, None)
    sample = stats.record(ok, dipped, 3000, None)
    assert sample["uv"] is True
    assert stats.uv_events == 1
    # Sticky bit stays set afterwards but isn't a new event
    assert stats.record(dipped, dipped, 5000, None)["uv"] is False


def test_session_ignores_dips_from_before_app_start():
    stats = SessionStats()
    sample = stats.record(UNAVAILABLE, build_status(0x10000, False, 45.0), 1000, None)
    assert sample["uv"] is False
    assert stats.uv_events == 0


def test_session_tracks_max_temperature():
    stats = SessionStats()
    prev = UNAVAILABLE
    for ts, t in [(1, 50.0), (2, 61.5), (3, 55.0)]:
        cur = build_status(0, False, t)
        stats.record(prev, cur, ts, None)
        prev = cur
    assert (stats.temp_max_c, stats.temp_max_ms) == (61.5, 2)


def test_session_history_is_bounded():
    from collections import deque
    stats = SessionStats(history=deque(maxlen=3))
    s = build_status(0, False, 45.0)
    for ts in range(10):
        stats.record(s, s, ts, None)
    assert [x["ts"] for x in stats.history] == [7, 8, 9]


def test_flags_table_covers_all_conditions():
    names = [f["name"] for f in build_status(0x40004, False, 45.0).flags]
    assert names == ["Under-voltage", "ARM frequency capped", "CPU throttled", "Soft temperature limit"]
    throttled = next(f for f in build_status(0x40004, False, 45.0).flags if f["name"] == "CPU throttled")
    assert throttled == {"name": "CPU throttled", "now": True, "since_boot": True}


def test_read_cpu_freq_and_memory(tmp_path):
    for name, val in [("scaling_cur_freq", "600000"), ("scaling_min_freq", "600000"), ("scaling_max_freq", "1200000")]:
        (tmp_path / name).write_text(val + "\n")
    assert read_cpu_freq_mhz(tmp_path) == {"cur": 600, "min": 600, "max": 1200}
    assert read_cpu_freq_mhz(tmp_path / "missing") is None

    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:  1048576 kB\nMemFree: 1 kB\nMemAvailable:  524288 kB\n")
    assert read_memory_mb(meminfo) == {"used": 512, "total": 1024}
