# Network Recovery Card

**Print this and keep it with the float, not only on the Pi.** Try the steps in order.

| | |
|---|---|
| Pi user | `justin` |
| Parade WiFi | `very-good-float-2026` |
| WiFi password (write by hand) | ______________________ |
| Pi on the parade WiFi | `10.0.0.1`. Dashboard: `http://10.0.0.1:8080` |
| Pi on the Mac cable | usually `192.168.2.2` (Mac is `192.168.2.1`). Dashboard: `http://192.168.2.2:8080` |
| DMX-AN2 (Art-Net) | `2.0.0.1`, Pi side `2.0.0.2`, on the USB-Ethernet adapter |

## 1. Over the Mac cable

Cable: Mac's USB 10/100/1000 LAN adapter → Pi's **built-in** Ethernet port (not the USB-Ethernet adapter).

1. Mac: System Settings → General → Sharing → **Internet Sharing off, then on**. Wait 1 minute.
2. **Unplug and replug** the cable at the Pi. Wait 1 minute.
3. `ssh justin@192.168.2.2`
4. Address different? On the Mac: `arp -a | grep bridge100`. Use the `192.168.2.x` entry that isn't `.1` (hardware address starts `b8:27:eb`).
5. Still nothing? Mac: Network → USB 10/100/1000 LAN → Details → TCP/IP must be **Using DHCP** (not Manual `2.0.0.2`).

## 2. Over the parade WiFi

1. Join `very-good-float-2026` from the Mac.
2. `ssh justin@10.0.0.1`

## 3. HDMI monitor + USB keyboard on the Pi

1. Plug in both, power the Pi, log in as `justin`.
2. See what's wrong: `bash ~/parade-2026/scripts/pi-network-status.sh`
3. Restart the parade WiFi: `sudo systemctl restart hostapd parade-ap-network`
4. Radio switched off? `sudo rfkill unblock wlan`, then repeat step 3.
5. Still broken: `bash ~/parade-2026/scripts/pi-ap.sh` (sets the access point up again).
6. Restart the app: `sudo systemctl restart parade`

(The older `sudo nmcli con up parade-ap` no longer applies. The parade WiFi now runs on hostapd, not NetworkManager.)

## 4. Restore the SD-card backup

1. Power off the Pi. Swap in the spare SD card (or re-flash the backup image onto a card with Raspberry Pi Imager → "Use custom").
2. Power on, wait 2 minutes, join `very-good-float-2026`, open `http://10.0.0.1:8080`.

Full guide: `docs/NETWORK.md` in the repo.
