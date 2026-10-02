"""Network facts for the status display, all readable without root.

  - link (carrier) per interface: /sys/class/net/<if>/carrier
  - IPv4 address per interface: `ip -j -4 addr`
  - devices joined to the WiFi access point: `iw dev <wlan> station dump`
  - Art-Net node reachability: the kernel's ARP entry for the node (`ip -j neigh`).
    The DMX loop sends to the node continuously, so the kernel keeps re-checking
    it: FAILED/INCOMPLETE means the node stopped answering.
  - access point SSID/password: the env file written by scripts/pi-ap.sh
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SYS_NET = Path("/sys/class/net")
NEIGH_OK = {"REACHABLE", "STALE", "DELAY", "PROBE", "PERMANENT", "NOARP"}
NEIGH_FAILED = {"FAILED", "INCOMPLETE"}


@dataclass(frozen=True)
class InterfaceInfo:
    link: bool | None  # None: interface doesn't exist
    ipv4: str | None


@dataclass(frozen=True)
class NetworkInfo:
    interfaces: dict[str, InterfaceInfo] = field(default_factory=dict)
    wifi_clients: int | None = None
    nodes: dict[str, bool | None] = field(default_factory=dict)  # node ip -> answering?
    ap: dict[str, str] = field(default_factory=dict)  # AP_SSID, AP_PASSWORD, AP_ADDRESS


def read_carrier(interface: str, root: Path = SYS_NET) -> bool | None:
    try:
        return (root / interface / "carrier").read_text().strip() == "1"
    except FileNotFoundError:
        return None
    except OSError:
        return False  # reading carrier on an interface that's down raises EINVAL


def parse_ipv4(output: str) -> dict[str, str]:
    """`ip -j -4 addr` -> {ifname: first IPv4 address}."""
    out = {}
    try:
        for iface in json.loads(output or "[]"):
            addrs = iface.get("addr_info") or []
            if addrs and "local" in addrs[0]:
                out[iface["ifname"]] = addrs[0]["local"]
    except (ValueError, TypeError, KeyError):
        pass
    return out


def parse_station_count(output: str) -> int:
    return sum(1 for line in output.splitlines() if line.startswith("Station "))


def parse_neigh(output: str) -> bool | None:
    """`ip -j neigh show to <ip>` -> True (answering), False (stopped), None (unknown)."""
    try:
        entries = json.loads(output or "[]")
    except ValueError:
        return None
    for entry in entries:
        states = set(entry.get("state") or [])
        if states & NEIGH_OK:
            return True
        if states & NEIGH_FAILED:
            return False
    return None


def read_env_file(path: Path) -> dict[str, str]:
    try:
        text = path.read_text()
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            out[key] = value
    return out


async def _run(*cmd: str) -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
    except (OSError, asyncio.TimeoutError):
        return None
    if proc.returncode != 0:
        return None
    return stdout.decode(errors="replace")


async def read_network(
    interfaces: list[str], wifi_interface: str, node_ips: list[str], ap_info_path: Path,
) -> NetworkInfo:
    ipv4 = parse_ipv4(await _run("ip", "-j", "-4", "addr") or "")
    stations = await _run("iw", "dev", wifi_interface, "station", "dump")
    nodes = {}
    for ip in node_ips:
        out = await _run("ip", "-j", "neigh", "show", "to", ip)
        nodes[ip] = parse_neigh(out) if out is not None else None
    return NetworkInfo(
        interfaces={i: InterfaceInfo(read_carrier(i), ipv4.get(i)) for i in interfaces},
        wifi_clients=parse_station_count(stations) if stations is not None else None,
        nodes=nodes,
        ap=read_env_file(ap_info_path),
    )
