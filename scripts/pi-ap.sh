#!/usr/bin/env bash
# pi-ap.sh — Configure the Pi as a WiFi access point using nmcli (Pi OS Bookworm).
#
# Usage:
#   bash scripts/pi-ap.sh
#
# What it does:
#   Creates (or replaces) a NetworkManager WiFi AP connection named "parade-ap".
#   The Pi will broadcast the SSID below and assign IPs via built-in DHCP.
#   Connect your iPad to this network, then browse to http://10.0.0.1:8080
#
# Requirements:
#   - Pi OS Bookworm (NetworkManager installed and running)
#   - wlan0 interface available
#   - Run as a user with sudo

set -euo pipefail

# ── Config — edit these before running ───────────────────────────────────────
AP_SSID="parade-2026"
AP_PASSWORD="parade2026"        # min 8 chars for WPA2
AP_IP="10.0.0.1/24"
AP_INTERFACE="wlan0"
AP_CON_NAME="parade-ap"
AP_BAND="bg"                    # "bg" = 2.4 GHz, "a" = 5 GHz
# ─────────────────────────────────────────────────────────────────────────────

echo "==> parade WiFi AP setup"
echo "    SSID:      $AP_SSID"
echo "    Password:  $AP_PASSWORD"
echo "    IP:        $AP_IP"
echo "    Interface: $AP_INTERFACE"
echo ""

# Check NetworkManager is running
if ! systemctl is-active --quiet NetworkManager; then
    echo "ERROR: NetworkManager is not running. Is this Pi OS Bookworm?"
    exit 1
fi

# Remove existing connection with the same name (idempotent)
if nmcli con show "$AP_CON_NAME" &>/dev/null; then
    echo "==> Removing existing connection '$AP_CON_NAME'..."
    sudo nmcli con delete "$AP_CON_NAME"
fi

# Create the AP connection
echo "==> Creating AP connection..."
sudo nmcli con add \
    type wifi \
    ifname "$AP_INTERFACE" \
    con-name "$AP_CON_NAME" \
    autoconnect yes \
    ssid "$AP_SSID" \
    mode ap

# Security: WPA2
sudo nmcli con modify "$AP_CON_NAME" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$AP_PASSWORD"

# IP: shared = AP mode + built-in DHCP server
sudo nmcli con modify "$AP_CON_NAME" \
    ipv4.method shared \
    ipv4.addresses "$AP_IP"

# Band: lock to 2.4 GHz (most iPads support; change to "a" for 5 GHz)
sudo nmcli con modify "$AP_CON_NAME" \
    802-11-wireless.band "$AP_BAND"

# Bring it up
echo "==> Activating access point..."
sudo nmcli con up "$AP_CON_NAME"

echo ""
echo "==> AP is live."
echo "    Connect your iPad to WiFi: $AP_SSID  (password: $AP_PASSWORD)"
echo "    Then open:  http://10.0.0.1:8080"
echo ""
echo "    The AP will start automatically on every boot."
echo "    To stop:    sudo nmcli con down $AP_CON_NAME"
echo "    To disable: sudo nmcli con modify $AP_CON_NAME autoconnect no"
