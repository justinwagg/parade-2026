#!/usr/bin/env bash
# pi-setup.sh — Run once on a headless Pi to install parade as a systemd service.
#
# Usage:
#   cd /path/to/parade-2026
#   bash scripts/pi-setup.sh
#
# What it does:
#   1. Installs system packages (python3-venv, git)
#   2. Creates a Python venv at .venv/ and installs the project
#   3. Writes a systemd service that auto-starts parade on boot
#   4. Optionally renames the Pi hostname to "parade"
#
# Requirements: Pi OS Bookworm, internet access for apt/pip

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="parade"
HOSTNAME_NEW="parade"
PARADE_USER="${USER:-pi}"
BIND_HOST="0.0.0.0"
BIND_PORT="8000"
# ─────────────────────────────────────────────────────────────────────────────

echo "==> parade setup — repo: $REPO_DIR"

# 1. System packages
echo "==> Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends python3-venv python3-pip git

# 2. Python venv
VENV="$REPO_DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo "==> Creating venv at $VENV..."
    python3 -m venv "$VENV"
fi
echo "==> Installing Python dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e "$REPO_DIR"

# 3. Systemd service
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
ExecStart=$VENV/bin/parade --host $BIND_HOST --port $BIND_PORT
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

# 4. Hostname (optional — comment out if you want to keep default)
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
echo "    Web UI (from iPad):  http://${HOSTNAME_NEW}.local:${BIND_PORT}"
echo ""
echo "    If you haven't set up the WiFi access point yet, run:"
echo "    bash scripts/pi-ap.sh"
