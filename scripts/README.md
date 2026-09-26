# Pi Setup Scripts

## First-time setup

Run these once after cloning the repo on a fresh Pi OS Bookworm install.

```bash
bash scripts/pi-setup.sh   # installs deps, systemd service, renames hostname to "parade"
bash scripts/pi-ap.sh      # creates WiFi AP: SSID "parade-2026", IP 10.0.0.1
sudo systemctl start parade
```

Connect iPad to WiFi `parade-2026` (password: `parade2026`), then open `http://10.0.0.1:8000`.

---

## Switching between AP mode and regular WiFi

`wlan0` can only do one thing at a time — AP mode or client mode. Switching requires taking one connection down before bringing the other up.

**⚠️ Do not do this over SSH on the parade AP** — you'll cut your own connection. Use HDMI+keyboard on the Pi directly, or SSH over ethernet.

### Go to regular WiFi (e.g. to pull updates)

```bash
sudo nmcli con down parade-ap
sudo nmcli con up home-wifi        # replace "home-wifi" with your saved connection name
```

Or connect to a new network on the fly:
```bash
sudo nmcli con down parade-ap
sudo nmcli device wifi connect "SSID" password "password"
```

### Go back to show mode

```bash
sudo nmcli con down home-wifi
sudo nmcli con up parade-ap
```

### Save your home WiFi as a named profile (do this once)

```bash
sudo nmcli con add type wifi ifname wlan0 con-name "home-wifi" \
    ssid "YourSSID" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "YourPassword"
```

### List all saved connections

```bash
nmcli con show
```

---

## Service management

```bash
sudo systemctl start parade      # start
sudo systemctl stop parade       # stop
sudo systemctl restart parade    # restart after code changes
journalctl -u parade -f          # live logs
```

---

## Network overview

| Interface | Purpose | Address |
|-----------|---------|---------|
| `wlan0`   | WiFi AP (show mode) or client (internet) | `10.0.0.1` in AP mode |
| `eth0`    | DMX-AN2 controller | static `2.0.0.x` (set in parade config) |

`eth0` is unaffected by WiFi switching.
