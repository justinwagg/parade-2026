#!/usr/bin/env bash
# pi-ap.sh — Run the Pi's built-in WiFi (wlan0) as the parade access point.
#
# Usage:
#   bash scripts/pi-ap.sh             # set up (or refresh) the access point
#   bash scripts/pi-ap.sh --dry-run   # print what would change, change nothing
#   bash scripts/pi-ap.sh --undo      # hand wlan0 back to NetworkManager (home WiFi)
#
# What it does:
#   - hostapd broadcasts the WiFi network (plain WPA2-PSK + AES).
#   - parade-ap-network.service gives wlan0 the address 10.0.0.1 and runs a
#     small DHCP server (dnsmasq) so the iPad gets a 10.0.0.x address.
#   - NetworkManager is told to leave wlan0 alone. It keeps managing eth0
#     (cable to the Mac) and eth1 (Art-Net).
#   Connect the iPad to the WiFi below, then browse to http://10.0.0.1:8080
#   Everything starts automatically on every boot.
#
# Why not NetworkManager's built-in hotspot?
#   On the Pi 3's WiFi chip (BCM43430) it fails: NetworkManager always offers
#   WPA2-PSK-SHA256, the chip can't do it, and phones abort the join at step 3
#   of the 4-way handshake with "incorrect password". hostapd offers WPA2-PSK only.
#
# Password:
#   Read from /etc/parade/ap.env (root-only, chmod 600, never in git):
#       AP_PASSWORD=yourpassword
#   If that file is missing, the script asks for a password and creates it.
#   A copy with the SSID goes to /etc/parade/ap-display.env (chmod 640, group of
#   the user running this script) for the OLED status display.
#
# WARNING: this takes wlan0 off your home WiFi. If you are connected over home
# WiFi (SSH / VS Code), that session will drop. Connect over the Ethernet
# cable from the Mac first. The first run installs hostapd, so the Pi needs
# internet (Mac Internet Sharing over the cable is fine).
#
# Requirements:
#   - Raspberry Pi OS based on Debian 13, with NetworkManager running
#   - wlan0 interface available
#   - Run as a user with sudo

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
AP_SSID="very-good-float-2026"
AP_ADDRESS="10.0.0.1"
AP_PREFIX=24
AP_DHCP_RANGE="10.0.0.10,10.0.0.254,255.255.255.0,12h"
AP_INTERFACE="wlan0"
AP_CHANNEL=6                    # 1, 6 or 11; the Pi 3 Model B is 2.4 GHz only
AP_COUNTRY="US"
ENV_FILE="/etc/parade/ap.env"
DISPLAY_ENV_FILE="/etc/parade/ap-display.env"   # SSID + password for the status display

HOSTAPD_CONF="/etc/hostapd/hostapd.conf"
NM_UNMANAGED_CONF="/etc/NetworkManager/conf.d/90-parade-ap.conf"
NET_UNIT="parade-ap-network.service"
NET_UNIT_FILE="/etc/systemd/system/$NET_UNIT"
HOSTAPD_DROPIN="/etc/systemd/system/hostapd.service.d/parade.conf"
OLD_NM_PROFILE="parade-ap"      # left over from the NetworkManager hotspot version
# ─────────────────────────────────────────────────────────────────────────────

MODE="setup"
case "${1:-}" in
    "") ;;
    --dry-run) MODE="dry-run" ;;
    --undo) MODE="undo" ;;
    *) echo "Usage: $0 [--dry-run | --undo]" >&2; exit 2 ;;
esac
DRY_RUN=0
[[ "$MODE" == "dry-run" ]] && DRY_RUN=1

AP_PASSWORD=""

# Run a command, or in dry-run mode print it.
run() {
    if (( DRY_RUN )); then
        printf '   '; printf ' %q' "$@"; echo
    else
        "$@"
    fi
}

# Write stdin to a root-owned file with the given mode. In dry-run mode,
# print the contents instead, with the password masked.
write_root_file() {
    local path="$1" mode="$2" content
    content="$(cat)"
    if (( DRY_RUN )); then
        echo "    --- would write $path (mode $mode) ---"
        if [[ -n "$AP_PASSWORD" ]]; then
            content="${content//"$AP_PASSWORD"/********}"
        fi
        sed 's/^/    | /' <<<"$content"
    else
        sudo install -d -m 755 "$(dirname "$path")"
        sudo install -m "$mode" -o root -g root /dev/null "$path"
        printf '%s\n' "$content" | sudo tee "$path" >/dev/null
    fi
}

# Warn if any live SSH session would be cut off by taking over wlan0.
# (Checks real connections, not $SSH_CONNECTION, which goes stale in
# long-lived terminals such as VS Code's remote server.)
warn_if_ssh_on_wlan() {
    (( DRY_RUN )) && return 0
    local wlan_ip
    wlan_ip="$(ip -4 -o addr show dev "$AP_INTERFACE" | awk '{split($4, a, "/"); print a[1]; exit}')"
    if [[ -n "$wlan_ip" ]] &&
       ss -Htn state established '( sport = :22 )' | awk '{print $3}' | grep -qx "$wlan_ip:22"; then
        echo "WARNING: an SSH session is connected over $AP_INTERFACE ($wlan_ip)."
        echo "         This will drop it."
        read -rp "         Continue anyway? [y/N] " answer
        [[ "$answer" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
    fi
}

# Check NetworkManager is running
if ! systemctl is-active --quiet NetworkManager; then
    echo "ERROR: NetworkManager is not running."
    exit 1
fi

# ── Undo: give wlan0 back to NetworkManager ──────────────────────────────────
if [[ "$MODE" == "undo" ]]; then
    echo "==> Turning off the parade access point; NetworkManager takes wlan0 back"
    sudo systemctl disable --now hostapd.service "$NET_UNIT" 2>/dev/null || true
    sudo rm -f "$NM_UNMANAGED_CONF" "$NET_UNIT_FILE" "$HOSTAPD_DROPIN"
    sudo systemctl daemon-reload
    sudo nmcli device set "$AP_INTERFACE" managed yes
    echo ""
    echo "==> Done. NetworkManager manages $AP_INTERFACE again and will rejoin saved"
    echo "    WiFi (e.g. home WiFi). $HOSTAPD_CONF and $ENV_FILE are kept;"
    echo "    run this script without --undo to turn the access point back on."
    exit 0
fi

echo "==> parade WiFi access point setup$( (( DRY_RUN )) && echo ' (dry run: nothing will change)')"
echo "    SSID:      $AP_SSID"
echo "    Address:   $AP_ADDRESS/$AP_PREFIX"
echo "    Interface: $AP_INTERFACE (channel $AP_CHANNEL, country $AP_COUNTRY)"
echo "    Password:  from $ENV_FILE"
echo ""

# ── Password ─────────────────────────────────────────────────────────────────
if (( DRY_RUN )); then
    # Don't read or create the secret in dry-run mode; just say what would happen.
    if [[ -e "$ENV_FILE" ]]; then
        echo "==> Would read AP_PASSWORD from $ENV_FILE"
    else
        echo "==> $ENV_FILE is missing; a real run would ask for a password and create it"
    fi
    AP_PASSWORD="dry-run-placeholder"
elif sudo test -f "$ENV_FILE"; then
    AP_PASSWORD="$(sudo sed -n 's/^AP_PASSWORD=//p' "$ENV_FILE" | tail -n 1)"
    if (( ${#AP_PASSWORD} < 8 || ${#AP_PASSWORD} > 63 )); then
        echo "ERROR: AP_PASSWORD in $ENV_FILE must be 8-63 characters (WPA2 rule)."
        exit 1
    fi
    echo "==> Using password from $ENV_FILE"
else
    echo "==> $ENV_FILE not found. Choose the WiFi password the iPad will use."
    while true; do
        read -rsp "    Password (8-63 characters): " AP_PASSWORD; echo
        if (( ${#AP_PASSWORD} < 8 || ${#AP_PASSWORD} > 63 )); then
            echo "    Must be 8-63 characters. Try again."
            continue
        fi
        read -rsp "    Type it again: " confirm; echo
        [[ "$AP_PASSWORD" == "$confirm" ]] && break
        echo "    Didn't match. Try again."
    done
    printf 'AP_PASSWORD=%s\n' "$AP_PASSWORD" | write_root_file "$ENV_FILE" 600
    echo "==> Saved to $ENV_FILE (root-only)"
fi

# The parade app (running as this user) shows the SSID and password on the
# OLED status display so people can join. Same secret, readable by this user's
# group only.
printf 'AP_SSID=%s\nAP_PASSWORD=%s\nAP_ADDRESS=%s\n' "$AP_SSID" "$AP_PASSWORD" "$AP_ADDRESS" \
    | write_root_file "$DISPLAY_ENV_FILE" 640
run sudo chgrp "$(id -gn)" "$DISPLAY_ENV_FILE"
echo "==> Wrote $DISPLAY_ENV_FILE (readable by group $(id -gn), for the status display)"
echo ""

warn_if_ssh_on_wlan

# ── 1. Tell NetworkManager to leave wlan0 alone ──────────────────────────────
echo "==> Writing $NM_UNMANAGED_CONF"
write_root_file "$NM_UNMANAGED_CONF" 644 <<EOF
# Written by parade scripts/pi-ap.sh — hostapd runs $AP_INTERFACE as the access
# point. Undo with: bash scripts/pi-ap.sh --undo
[keyfile]
unmanaged-devices=interface-name:$AP_INTERFACE
EOF

if nmcli con show "$OLD_NM_PROFILE" &>/dev/null; then
    echo "==> Removing old NetworkManager hotspot profile '$OLD_NM_PROFILE'..."
    run sudo nmcli con delete "$OLD_NM_PROFILE"
fi

echo "==> Releasing $AP_INTERFACE from NetworkManager..."
run sudo nmcli device set "$AP_INTERFACE" managed no

# ── 2. hostapd config (written before installing, so the package doesn't mask
#       the service for lack of a config file) ─────────────────────────────────
echo "==> Writing $HOSTAPD_CONF"
write_root_file "$HOSTAPD_CONF" 600 <<EOF
# Written by parade scripts/pi-ap.sh — rerun the script rather than editing.
interface=$AP_INTERFACE
driver=nl80211
country_code=$AP_COUNTRY
ieee80211d=1
ssid=$AP_SSID
hw_mode=g
channel=$AP_CHANNEL
ieee80211n=1
wmm_enabled=1
auth_algs=1
# Plain WPA2-PSK with AES only: the BCM43430 can't do PSK-SHA256 or WPA3.
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=$AP_PASSWORD
EOF

# ── 3. Install hostapd ───────────────────────────────────────────────────────
if dpkg -s hostapd &>/dev/null; then
    echo "==> hostapd already installed"
else
    echo "==> Installing hostapd (needs internet)..."
    run sudo apt-get install -y hostapd
fi

# Pi OS boots with the WiFi radio blocked (rfkill default_state=0) and relies on
# NetworkManager or a saved rfkill state to unblock it. wlan0 is no longer
# NetworkManager's, so hostapd unblocks the radio itself before starting.
echo "==> Writing $HOSTAPD_DROPIN"
write_root_file "$HOSTAPD_DROPIN" 644 <<EOF
# Written by parade scripts/pi-ap.sh — make sure the WiFi radio is on.
[Unit]
After=systemd-rfkill.service

[Service]
ExecStartPre=/usr/sbin/rfkill unblock wlan
EOF

# ── 4. Address + DHCP for wlan0 ──────────────────────────────────────────────
echo "==> Writing $NET_UNIT_FILE"
write_root_file "$NET_UNIT_FILE" 644 <<EOF
# Written by parade scripts/pi-ap.sh — gives $AP_INTERFACE its access-point
# address and hands out addresses (DHCP) to the iPad. No DNS, no internet routing.
[Unit]
Description=parade access point: address and DHCP on $AP_INTERFACE
BindsTo=sys-subsystem-net-devices-$AP_INTERFACE.device
After=sys-subsystem-net-devices-$AP_INTERFACE.device hostapd.service

[Service]
ExecStartPre=/usr/sbin/ip addr replace $AP_ADDRESS/$AP_PREFIX dev $AP_INTERFACE
ExecStart=/usr/sbin/dnsmasq --keep-in-foreground --conf-file=/dev/null --user=dnsmasq --pid-file=/run/parade-ap-dnsmasq.pid --port=0 --interface=$AP_INTERFACE --bind-dynamic --dhcp-range=$AP_DHCP_RANGE --dhcp-leasefile=/var/lib/misc/parade-ap.leases
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

# ── 5. Start everything (and on every boot) ──────────────────────────────────
echo "==> Starting the access point..."
run sudo systemctl daemon-reload
run sudo systemctl unmask hostapd.service
run sudo systemctl enable hostapd.service "$NET_UNIT"
run sudo systemctl restart hostapd.service
run sudo systemctl restart "$NET_UNIT"

if (( DRY_RUN )); then
    echo ""
    echo "==> Dry run finished. Nothing was changed."
    exit 0
fi

sleep 2
if systemctl is-active --quiet hostapd.service && systemctl is-active --quiet "$NET_UNIT"; then
    echo ""
    echo "==> Access point is live."
    echo "    Connect your iPad to WiFi: $AP_SSID  (password: sudo cat $ENV_FILE)"
    echo "    Then open:  http://$AP_ADDRESS:8080"
    echo ""
    echo "    It starts automatically on every boot."
    echo "    Status:     systemctl status hostapd $NET_UNIT"
    echo "    Undo:       bash scripts/pi-ap.sh --undo   (back to home WiFi)"
else
    echo ""
    echo "ERROR: the access point didn't start. Details:"
    echo "    systemctl status hostapd $NET_UNIT"
    echo "    journalctl -u hostapd -u $NET_UNIT -b"
    exit 1
fi
