from types import SimpleNamespace

from parade.config.models import DisplayConfig
from parade.core.state import SystemState, SystemStateMachine
from parade.display.controller import (
    StatusDisplay, controller_url, diag_page, format_uptime, join_page, network_page, show_page,
)
from parade.display.network import (
    InterfaceInfo, NetworkInfo, parse_ipv4, parse_neigh, parse_station_count, read_carrier, read_env_file,
)
from parade.display.simulated import SimulatedDisplay
from parade.display.ssd1306 import line_positions
from parade.health.power import PowerMonitor, build_status

COLS = 21
NET = NetworkInfo(
    interfaces={
        "eth0": InterfaceInfo(True, "192.168.2.2"),
        "wlan0": InterfaceInfo(True, "10.0.0.1"),
        "eth1": InterfaceInfo(False, None),
    },
    wifi_clients=2,
    nodes={"2.0.0.1": True},
    ap={"AP_SSID": "very-good-float-2026", "AP_PASSWORD": "hunter22", "AP_ADDRESS": "10.0.0.1"},
)
LABELS = [("Mac", "eth0"), ("WiFi", "wlan0"), ("ArtNet", "eth1")]


def test_line_positions_fill_the_panel():
    assert line_positions(32) == [0, 10, 21]
    assert line_positions(64)[-1] == 53


def test_parse_ipv4():
    out = '[{"ifname":"lo","addr_info":[{"local":"127.0.0.1"}]},{"ifname":"eth0","addr_info":[]}]'
    assert parse_ipv4(out) == {"lo": "127.0.0.1"}
    assert parse_ipv4("not json") == {}


def test_parse_station_count():
    dump = "Station aa:bb (on wlan0)\n\tinactive time: 0 ms\nStation cc:dd (on wlan0)\n"
    assert parse_station_count(dump) == 2
    assert parse_station_count("") == 0


def test_parse_neigh():
    assert parse_neigh('[{"dst":"2.0.0.1","state":["REACHABLE"]}]') is True
    assert parse_neigh('[{"dst":"2.0.0.1","state":["STALE"]}]') is True
    assert parse_neigh('[{"dst":"2.0.0.1","state":["FAILED"]}]') is False
    assert parse_neigh("[]") is None


def test_read_carrier(tmp_path):
    (tmp_path / "eth0").mkdir()
    (tmp_path / "eth0" / "carrier").write_text("1\n")
    assert read_carrier("eth0", tmp_path) is True
    assert read_carrier("eth9", tmp_path) is None


def test_read_env_file(tmp_path):
    f = tmp_path / "ap.env"
    f.write_text("# comment\nAP_SSID=float\nAP_PASSWORD=a=b\n")
    assert read_env_file(f) == {"AP_SSID": "float", "AP_PASSWORD": "a=b"}
    assert read_env_file(tmp_path / "missing") == {}


def test_join_page():
    url = controller_url(NET, "wlan0", 8080)
    assert join_page(NET, url, COLS) == ["very-good-float-2026", "pw hunter22", "http://10.0.0.1:8080"]


def test_join_page_without_ap_file():
    net = NetworkInfo(interfaces={"wlan0": InterfaceInfo(True, "10.0.0.1")})
    lines = join_page(net, controller_url(net, "wlan0", 8080), COLS)
    assert lines[0] == "WiFi details n/a"
    assert lines[2] == "http://10.0.0.1:8080"


def test_show_page():
    assert show_page(SystemState.RUNNING, True, "spin", NET.nodes, COLS) == [
        "RUNNING         ARMED", "cue: spin", "DMX 2.0.0.1 OK",
    ]
    lines = show_page(SystemState.EMERGENCY_STOP, False, None, {"2.0.0.1": False}, COLS)
    assert lines == ["E-STOP!", "cue: idle", "DMX 2.0.0.1 NO REPLY"]


def test_network_page():
    assert network_page(NET, LABELS, "wlan0", COLS) == [
        "Mac 192.168.2.2", "WiFi 10.0.0.1 2dev", "ArtNet unplugged",
    ]


def test_diag_page():
    system = {"load": {"load1": 0.42}, "memory_mb": {"used": 210, "total": 905},
              "uptime_s": 7980, "cpu_mhz": {"cur": 600}}
    assert diag_page(build_status(0, False, 51.6), system, COLS) == [
        "CPU 52C PWR OK", "load 0.4 mem 210/905M", "up 2h13m 600MHz",
    ]
    assert diag_page(build_status(None, None, None), {}, COLS)[0] == "CPU ?C PWR n/a"


def test_format_uptime():
    assert format_uptime(59) == "0h00m"
    assert format_uptime(90061) == "1d1h"


def test_every_line_fits():
    for lines in (
        join_page(NET, controller_url(NET, "wlan0", 8080), COLS),
        network_page(NET, LABELS, "wlan0", COLS),
        diag_page(build_status(0x50005, True, 85.0), {}, COLS),
        show_page(SystemState.EMERGENCY_STOP, False, "a" * 40, NET.nodes, COLS),
    ):
        assert all(len(line) <= COLS for line in lines)


def make_display():
    sm = SystemStateMachine()
    sm.transition(SystemState.SAFE)
    pm = PowerMonitor()
    driver = SimulatedDisplay()
    display = StatusDisplay(
        DisplayConfig(page_seconds=4.0), driver, sm, SimpleNamespace(active_cue=None), pm, ["2.0.0.1"], 8080,
    )
    display.network = NET
    return display, sm, driver


def test_frame_rotates_pages():
    display, *_ = make_display()
    seen = {tuple(display.frame(t)) for t in (0, 4, 8, 12)}
    assert len(seen) == 4


def test_frame_holds_show_page_on_estop():
    display, sm, _ = make_display()
    sm.transition(SystemState.EMERGENCY_STOP)
    assert all(display.frame(t)[0] == "E-STOP!" for t in (0, 4, 8, 12))


async def test_stop_shows_stopped():
    display, _, driver = make_display()
    await display.start()
    await display.stop()
    assert driver.get_lines()[0] == "parade stopped"
