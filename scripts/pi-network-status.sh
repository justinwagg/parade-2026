#!/usr/bin/env bash
# pi-network-status.sh — Plain-English summary of the Pi's network. Read-only.
#
# Usage:
#   bash scripts/pi-network-status.sh
#
# Shows what each network port is doing, where internet traffic goes, whether
# the internet is reachable, whether the parade app is running, and the exact
# addresses to use from the iPad and the Mac. Changes nothing; no sudo needed.

set -uo pipefail

# ── Config (matches scripts/pi-ap.sh and the "artnet" NetworkManager profile) ─
AP_IF="wlan0"
AP_ADDRESS="10.0.0.1"
MAC_IF="eth0"
ARTNET_IF="eth1"
ARTNET_ADDRESS="2.0.0.2"
WEB_PORT=8080
SERVICE_NAME="parade"
AP_LEASES="/var/lib/misc/parade-ap.leases"
# ─────────────────────────────────────────────────────────────────────────────

ok()   { echo "    [ OK ] $*"; }
warn() { echo "    [WARN] $*"; }
info() { echo "           $*"; }

ipv4_of() { ip -4 -o addr show dev "$1" 2>/dev/null | awk '{print $4; exit}'; }
link_up() { [[ "$(cat "/sys/class/net/$1/carrier" 2>/dev/null)" == 1 ]]; }
exists()  { [[ -e "/sys/class/net/$1" ]]; }

echo "==> parade network status — $(hostname), $(date '+%Y-%m-%d %H:%M')"

# ── wlan0: WiFi access point for the iPad ────────────────────────────────────
echo ""
echo "WiFi access point ($AP_IF) — the iPad connects here"
ap_addr="$(ipv4_of "$AP_IF")"
ap_type="$(iw dev "$AP_IF" info 2>/dev/null | awk '$1 == "type" {print $2}')"
ap_ssid="$(iw dev "$AP_IF" info 2>/dev/null | awk '$1 == "ssid" {$1 = ""; sub(/^ /, ""); print}')"
if ! exists "$AP_IF"; then
    warn "$AP_IF not found (WiFi hardware missing or disabled?)"
elif [[ "$ap_type" == "AP" ]] && systemctl is-active --quiet hostapd; then
    ok "Broadcasting WiFi \"$ap_ssid\""
    if [[ "${ap_addr%/*}" == "$AP_ADDRESS" ]]; then
        ok "Address $ap_addr"
    else
        warn "Address is '${ap_addr:-none}', expected $AP_ADDRESS/24 (check: systemctl status parade-ap-network)"
    fi
    systemctl is-active --quiet parade-ap-network \
        && ok "Handing out addresses to devices (DHCP)" \
        || warn "DHCP is not running, so devices can't get an address (systemctl status parade-ap-network)"
    clients="$(iw dev "$AP_IF" station dump 2>/dev/null | grep -c '^Station')"
    info "Devices connected right now: $clients"
    if [[ -r "$AP_LEASES" ]] && (( clients > 0 )); then
        while read -r _ mac addr name _; do
            iw dev "$AP_IF" station get "$mac" &>/dev/null && info "  - $name at $addr"
        done < "$AP_LEASES"
    fi
elif [[ "$ap_type" == "managed" && -n "$ap_ssid" ]]; then
    warn "Joined WiFi \"$ap_ssid\" as a normal client (${ap_addr:-no address}), NOT the access point"
    info "To switch back: bash scripts/pi-ap.sh"
else
    warn "Not broadcasting (hostapd: $(systemctl is-active hostapd 2>/dev/null))"
    info "Start it: sudo systemctl restart hostapd parade-ap-network   or rerun: bash scripts/pi-ap.sh"
fi

# ── eth0: cable to the Mac ───────────────────────────────────────────────────
echo ""
echo "Ethernet to the Mac ($MAC_IF) — built-in port, internet via Mac Internet Sharing"
mac_addr="$(ipv4_of "$MAC_IF")"
if ! exists "$MAC_IF"; then
    warn "$MAC_IF not found"
elif ! link_up "$MAC_IF"; then
    info "No cable / Mac not connected (normal on parade day)"
elif [[ -z "$mac_addr" ]]; then
    warn "Cable is plugged in but no address yet"
    info "Turn Mac Internet Sharing off and on, wait a minute, then unplug and replug the cable"
else
    ok "Cable connected, address $mac_addr (from the Mac)"
fi

# ── eth1: Art-Net to the DMX-AN2 ─────────────────────────────────────────────
echo ""
echo "Art-Net ($ARTNET_IF) — USB-Ethernet adapter to the DMX-AN2"
art_addr="$(ipv4_of "$ARTNET_IF")"
if ! exists "$ARTNET_IF"; then
    warn "$ARTNET_IF not found (USB-Ethernet adapter unplugged?)"
else
    [[ "${art_addr%/*}" == "$ARTNET_ADDRESS" ]] \
        && ok "Address $art_addr" \
        || warn "Address is '${art_addr:-none}', expected $ARTNET_ADDRESS/8 (NetworkManager profile 'artnet')"
    link_up "$ARTNET_IF" \
        && ok "Cable connected" \
        || warn "No link (DMX-AN2 off or cable unplugged)"
    ip route show default dev "$ARTNET_IF" 2>/dev/null | grep -q . \
        && warn "Has a default route; Art-Net must not have a gateway" \
        || ok "No gateway (correct)"
fi

# ── Internet ─────────────────────────────────────────────────────────────────
echo ""
echo "Internet"
default_route="$(ip route show default | head -n 1)"
if [[ -z "$default_route" ]]; then
    info "No route to the internet (normal on parade day; the show doesn't need it)"
else
    gw="$(awk '{print $3}' <<<"$default_route")"
    dev="$(awk '{for (i = 1; i < NF; i++) if ($i == "dev") print $(i + 1)}' <<<"$default_route")"
    info "Internet traffic goes out $dev via $gw"
    if ping -c 2 -W 2 1.1.1.1 &>/dev/null; then
        ok "Internet reachable (pinged 1.1.1.1)"
    else
        warn "Internet NOT reachable (ping 1.1.1.1 failed)"
    fi
fi

# ── parade app ───────────────────────────────────────────────────────────────
echo ""
echo "parade app"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "Service '$SERVICE_NAME' is running"
else
    warn "Service '$SERVICE_NAME' is $(systemctl is-active "$SERVICE_NAME" 2>/dev/null)"
    info "Start: sudo systemctl start $SERVICE_NAME    Logs: journalctl -u $SERVICE_NAME -e"
fi
ss -Hltn "( sport = :$WEB_PORT )" 2>/dev/null | grep -q . \
    && ok "Web UI listening on port $WEB_PORT" \
    || warn "Nothing listening on port $WEB_PORT"

# ── How to connect ───────────────────────────────────────────────────────────
echo ""
echo "How to connect"
info "iPad:  join WiFi \"${ap_ssid:-very-good-float-2026}\", open http://$AP_ADDRESS:$WEB_PORT"
info "       (WiFi password: sudo cat /etc/parade/ap.env)"
if [[ -n "$mac_addr" ]]; then
    info "Mac over the cable:  http://${mac_addr%/*}:$WEB_PORT"
    info "                     ssh $USER@${mac_addr%/*}"
fi
info "Mac over the parade WiFi:  ssh $USER@$AP_ADDRESS"
