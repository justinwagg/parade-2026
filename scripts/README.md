# Pi Setup Scripts

## First-time setup

Run these once after cloning the repo on a fresh Raspberry Pi OS (Debian 13) install. Run `pi-ap.sh` over the Ethernet cable from the Mac, not over WiFi.

```bash
bash scripts/pi-setup.sh   # installs deps, systemd service, renames hostname to "parade"
bash scripts/pi-ap.sh      # creates WiFi AP: SSID "very-good-float-2026", IP 10.0.0.1
sudo systemctl start parade
```

Connect iPad to WiFi `very-good-float-2026` (password: `sudo cat /etc/parade/ap.env` on the Pi), then open `http://10.0.0.1:8080`.

---

## WiFi access point vs. home WiFi

`wlan0` is the parade access point (run by hostapd, not NetworkManager). The Pi gets internet over the Ethernet cable from the Mac (Mac Internet Sharing), so it doesn't need home WiFi for updates. Full guide: [docs/NETWORK.md](../docs/NETWORK.md).

```bash
bash scripts/pi-network-status.sh   # read-only summary of every port, plus addresses to use
bash scripts/pi-ap.sh --dry-run     # show what pi-ap.sh would change
bash scripts/pi-ap.sh --undo        # hand wlan0 back to NetworkManager (rejoins saved home WiFi)
bash scripts/pi-ap.sh               # back to the parade access point
sudo systemctl restart hostapd parade-ap-network   # restart the access point
```

**⚠️ Don't run `pi-ap.sh` (or `--undo`) over SSH on WiFi**: it changes `wlan0` and cuts that session. Use the Ethernet cable from the Mac or HDMI+keyboard.

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
| `wlan0`   | WiFi access point `very-good-float-2026` for the iPad (hostapd) | `10.0.0.1/24` |
| `eth0`    | Built-in Ethernet: cable to the Mac (internet + SSH via Mac Internet Sharing) | `192.168.2.x` by DHCP |
| `eth1`    | DMX-AN2 controller (USB-Ethernet adapter) | static `2.0.0.2/8`, NetworkManager profile `artnet` (node is `2.0.0.1`) |

See [docs/NETWORK.md](../docs/NETWORK.md) for the diagram, tests and troubleshooting.
