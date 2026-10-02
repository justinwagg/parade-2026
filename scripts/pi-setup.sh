#!/usr/bin/env bash
# pi-setup.sh — Run once on a headless Pi to install parade as a systemd service.
#
# Usage:
#   cd /path/to/parade-2026
#   bash scripts/pi-setup.sh
#
# What it does:
#   1. Installs system packages (python3-venv, git, lgpio, spidev, pyusb)
#   2. Enables SPI (NeoPixels on GPIO10) and pins the core clock for it;
#      lets the plugdev group use BlinkStick status lights
#   3. Creates a Python venv at .venv/ (sees the apt lgpio/spidev/pyusb) and installs the project
#   4. Writes a systemd service that auto-starts parade on boot
#   5. Optionally renames the Pi hostname to "parade"
#
# Requirements: Pi OS Bookworm, internet access for apt/pip

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="parade"
HOSTNAME_NEW="parade"
PARADE_USER="${USER:-pi}"
# ─────────────────────────────────────────────────────────────────────────────

echo "==> parade setup — repo: $REPO_DIR"

# 1. System packages
echo "==> Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends python3-venv python3-pip git \
    python3-lgpio python3-spidev python3-usb

# 2. SPI for NeoPixels (GPIO10 / SPI0 MOSI). core_freq=250 keeps the Pi 3's
#    SPI clock (and so the WS2812 bit timing) from changing with CPU load.
BOOT_CONFIG="/boot/firmware/config.txt"
NEEDS_REBOOT=0
if [ ! -e /dev/spidev0.0 ]; then
    echo "==> Enabling SPI..."
    sudo raspi-config nonint do_spi 0
    NEEDS_REBOOT=1
fi
if ! grep -q '^core_freq=250' "$BOOT_CONFIG"; then
    echo "==> Adding core_freq=250 to $BOOT_CONFIG..."
    echo 'core_freq=250' | sudo tee -a "$BOOT_CONFIG" > /dev/null
    NEEDS_REBOOT=1
fi
sudo usermod -aG gpio,spi,plugdev "$PARADE_USER"

# BlinkStick status lights (USB): let plugdev drive them without root.
BLINKSTICK_RULE=/etc/udev/rules.d/85-blinkstick.rules
if [ ! -e "$BLINKSTICK_RULE" ]; then
    echo "==> Adding BlinkStick udev rule..."
    echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="20a0", ATTR{idProduct}=="41e5", GROUP="plugdev", MODE="0664"' \
        | sudo tee "$BLINKSTICK_RULE" > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi

# 3. Python venv. --system-site-packages lets it import the apt-installed
#    lgpio, spidev and pyusb; re-running it on an existing venv just updates that flag.
VENV="$REPO_DIR/.venv"
echo "==> Creating/updating venv at $VENV..."
python3 -m venv --system-site-packages "$VENV"
echo "==> Installing Python dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e "$REPO_DIR"

# 4. Systemd service
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
echo "==> Writing $SERVICE_FILE..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Parade Show Control
After=network.target

[Service]
Type=simple
User=$PARADE_USER
WorkingDirectory=$REPO_DIR
ExecStart=$VENV/bin/parade
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "==> Service enabled. Start now with: sudo systemctl start parade"

# 5. Hostname (optional — comment out if you want to keep default)
CURRENT_HOSTNAME="$(hostnamectl --static)"
if [ "$CURRENT_HOSTNAME" != "$HOSTNAME_NEW" ]; then
    echo "==> Renaming hostname: $CURRENT_HOSTNAME → $HOSTNAME_NEW"
    sudo hostnamectl set-hostname "$HOSTNAME_NEW"
    # Keep /etc/hosts consistent
    sudo sed -i "s/$CURRENT_HOSTNAME/$HOSTNAME_NEW/g" /etc/hosts
    echo "    Hostname changed. mDNS address will be ${HOSTNAME_NEW}.local after reboot."
fi

echo ""
echo "==> Setup complete."
echo "    Start the service:   sudo systemctl start parade"
echo "    View logs:           journalctl -u parade -f"
echo "    Web UI (from iPad):  http://${HOSTNAME_NEW}.local:8080"
echo ""
echo "    If you haven't set up the WiFi access point yet, run:"
echo "    bash scripts/pi-ap.sh"
if [ "$NEEDS_REBOOT" = 1 ]; then
    echo ""
    echo "    ** SPI / core_freq changed: reboot before using NeoPixels (sudo reboot) **"
fi
