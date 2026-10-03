"""OLED status display: joining info, show state, network and Pi diagnostics.

Pages rotate every `page_seconds`:
  join      WiFi SSID, password, controller URL
  show      state (+ARMED), running cue, Art-Net node answering
  network   each interface's IP / link, devices on the WiFi
  diag      CPU temperature, power flags, load, memory, uptime

In EMERGENCY_STOP or FAULT the display holds the show page. A pixel in the
top-right corner blinks once a second while the app is running; if it stops,
the app has hung. Indicator only: display errors never affect the show.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable

from parade.config.models import DisplayConfig
from parade.core.state import SystemState, SystemStateMachine
from parade.display.interface import DisplayInterface
from parade.display.network import NetworkInfo, read_network
from parade.health.power import PowerMonitor, PowerStatus

logger = logging.getLogger(__name__)

TICK_S = 0.5
NETWORK_POLL_S = 5.0
CHAR_W = 6

STATE_LABELS = {SystemState.EMERGENCY_STOP: "E-STOP!"}
HOLD_STATES = (SystemState.EMERGENCY_STOP, SystemState.FAULT)


def fit(text: str, cols: int) -> str:
    return text if len(text) <= cols else text[:cols]


def first_fitting(cols: int, *options: str) -> str:
    """The first option that fits, else the last one cut to width."""
    for opt in options:
        if len(opt) <= cols:
            return opt
    return fit(options[-1], cols)


def format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    m = int(seconds // 60)
    d, m = divmod(m, 1440)
    h, m = divmod(m, 60)
    return f"{d}d{h}h" if d else f"{h}h{m:02d}m"


def controller_url(net: NetworkInfo, wifi_interface: str, port: int) -> str:
    wifi = net.interfaces.get(wifi_interface)
    host = (wifi.ipv4 if wifi else None) or net.ap.get("AP_ADDRESS") or "10.0.0.1"
    return f"http://{host}:{port}"


def join_page(net: NetworkInfo, url: str, cols: int) -> list[str]:
    ssid, password = net.ap.get("AP_SSID"), net.ap.get("AP_PASSWORD")
    if not ssid:
        return ["WiFi details n/a", fit("rerun pi-ap.sh", cols), fit(url, cols)]
    return [
        first_fitting(cols, f"WiFi {ssid}", ssid),
        first_fitting(cols, f"pw {password}", password or "") if password else "pw n/a",
        first_fitting(cols, url, url.removeprefix("http://")),
    ]


def show_page(
    state: SystemState, armed: bool, cue: str | None, nodes: dict[str, bool | None], cols: int,
) -> list[str]:
    label = STATE_LABELS.get(state, state.value)
    top = f"{label:<{cols - 5}}ARMED" if armed else label
    if not nodes:
        dmx = "DMX no node"
    else:
        ip, ok = next(iter(nodes.items()))
        dmx = f"DMX {ip} " + {True: "OK", False: "NO REPLY", None: "?"}[ok]
    return [fit(top, cols), fit(cue or "idle", cols), fit(dmx, cols)]


def network_page(
    net: NetworkInfo, labels: list[tuple[str, str]], wifi_interface: str, cols: int,
) -> list[str]:
    lines = []
    for label, iface in labels:
        info = net.interfaces.get(iface)
        if info is None or info.link is None:
            text = f"{label} missing"
        elif not info.link:
            text = f"{label} unplugged"
        elif not info.ipv4:
            text = f"{label} no IP"
        else:
            text = f"{label} {info.ipv4}"
            if iface == wifi_interface and net.wifi_clients is not None:
                text = first_fitting(cols, f"{text} {net.wifi_clients}dev", text)
        lines.append(fit(text, cols))
    return lines


def diag_page(status: PowerStatus, system: dict, cols: int) -> list[str]:
    temp = f"CPU {status.temp_c:.0f}C" if status.temp_c is not None else "CPU ?C"
    load = (system.get("load") or {}).get("load1")
    mem = system.get("memory_mb") or {}
    cpu = system.get("cpu_mhz") or {}
    line2 = " ".join(filter(None, [
        f"load {load:.1f}" if load is not None else "",
        f"mem {mem['used']}/{mem['total']}M" if mem else "",
    ]))
    line3 = f"up {format_uptime(system.get('uptime_s'))}"
    if cpu:
        line3 += f" {cpu['cur']}MHz"
    return [fit(f"{temp} PWR {status.label}", cols), fit(line2, cols), fit(line3, cols)]


class StatusDisplay:
    def __init__(
        self,
        config: DisplayConfig,
        driver: DisplayInterface,
        state_machine: SystemStateMachine,
        activity: Callable[[], str | None],
        power_monitor: PowerMonitor,
        node_ips: list[str],
        web_port: int,
    ):
        self._config = config
        self._driver = driver
        self._state_machine = state_machine
        self._activity = activity
        self._power_monitor = power_monitor
        self._node_ips = node_ips
        self._web_port = web_port
        self._cols = config.width // CHAR_W
        self.network = NetworkInfo()

    async def start(self) -> None:
        await self._driver.start()

    async def stop(self) -> None:
        await self._driver.show(["parade stopped", "app not running"])
        await self._driver.stop()

    async def refresh_network(self) -> None:
        cfg = self._config
        self.network = await read_network(
            [i.interface for i in cfg.interfaces], cfg.wifi_interface,
            self._node_ips, Path(cfg.ap_info_path),
        )

    def pages(self) -> dict[str, list[str]]:
        cfg, cols, net = self._config, self._cols, self.network
        return {
            "join": join_page(net, controller_url(net, cfg.wifi_interface, self._web_port), cols),
            "show": show_page(
                self._state_machine.state, self._state_machine.armed,
                self._activity(), net.nodes, cols,
            ),
            "network": network_page(
                net, [(i.label, i.interface) for i in cfg.interfaces], cfg.wifi_interface, cols,
            ),
            "diag": diag_page(self._power_monitor.status, self._power_monitor.system, cols),
        }

    def frame(self, now: float) -> list[str]:
        pages = self.pages()
        if self._state_machine.state in HOLD_STATES:
            return pages["show"]
        order = list(pages.values())
        return order[int(now // self._config.page_seconds) % len(order)]

    async def run(self) -> None:
        last_poll = 0.0
        while True:
            now = time.monotonic()
            try:
                if now - last_poll >= NETWORK_POLL_S:
                    last_poll = now
                    await self.refresh_network()
                await self._driver.show(self.frame(now), heartbeat=int(now) % 2 == 0)
            except Exception:
                logger.exception("Status display update failed")
            await asyncio.sleep(TICK_S)
