# Network Setup

How the Pi talks to the iPad, the Mac and the DMX-AN2, how to set it up, how to test it, and what to do when something goes wrong.

Printable one-page recovery card (keep a paper copy off the Pi): [NETWORK_RECOVERY.md](NETWORK_RECOVERY.md).

## The setup

The Pi 3 Model B has three network connections. Each does one job.

```
                         Raspberry Pi 3 Model B ("parade", Debian 13)
                        ┌──────────────────────────────────────────────┐
  iPad / iPhone  ~~~~~~ │ wlan0  built-in WiFi                         │
  WiFi "very-good-      │        access point, 10.0.0.1                │
  float-2026"           │        hostapd + parade-ap-network           │
                        │                                              │
  Mac ───── cable ───── │ eth0   built-in Ethernet port                │
  "USB 10/100/1000 LAN" │        192.168.2.x from Mac Internet Sharing │
  adapter (en8)         │        internet for the Pi, SSH from the Mac │
                        │                                              │
  Chauvet DMX-AN2 ───── │ eth1   USB-Ethernet adapter                  │
  2.0.0.1               │        2.0.0.2/8, no gateway (Art-Net only)  │
                        └──────────────────────────────────────────────┘
                          parade app (systemd "parade"), web UI port 8080
```

| Port | Physical part | Address | Job | Managed by |
|---|---|---|---|---|
| `wlan0` | Pi built-in WiFi (2.4 GHz only) | `10.0.0.1/24`, hands out `10.0.0.10`–`.254` | WiFi network for the iPad | hostapd + `parade-ap-network.service` |
| `eth0` | Pi built-in Ethernet port | `192.168.2.x` from the Mac (usually `.2`) | Internet for the Pi, SSH/VS Code from the Mac | NetworkManager (profile `netplan-eth0`, DHCP) |
| `eth1` | USB-Ethernet adapter in a Pi USB port | `2.0.0.2/8`, no gateway | Art-Net to the DMX-AN2 (`2.0.0.1`) | NetworkManager (profile `artnet`) |

On parade day only `wlan0` and `eth1` matter. The Mac and its cable are for setup and updates.

### Words used here

- **IP address**: a device's number on a network, like `10.0.0.1`. `/24` means "the first three numbers are the network", so `10.0.0.1` and `10.0.0.187` are neighbours.
- **DHCP**: a device asking the network "please give me an address". The Pi hands out addresses to the iPad; the Mac hands one to the Pi.
- **Gateway / default route**: where a device sends anything that isn't on one of its own networks, i.e. the way to the internet. The Pi's is the Mac (`192.168.2.1`). Art-Net (`eth1`) must never have one.
- **SSID**: the WiFi network's name, `very-good-float-2026`.
- **Access point (AP)**: the Pi broadcasting its own WiFi network, like a home router.

### What the iPad gets

The iPad gets an address and can reach the parade controls at **http://10.0.0.1:8080**. It gets **no internet** through the Pi; iOS shows "No Internet Connection" under the WiFi name, which is expected and harmless. An iPhone with cellular data keeps using cellular for the internet, which can look like the Pi is sharing internet. It isn't.

### Why hostapd and not NetworkManager's hotspot

NetworkManager's built-in hotspot always offers the WPA2-PSK-SHA256 method, which the Pi 3's WiFi chip (BCM43430) can't do. Phones then abort the join and say "incorrect password", even with the right password. hostapd offers plain WPA2 (AES) only, which works. Details: [DECISIONS.md ADR-016](DECISIONS.md).

## Mac Internet Sharing (gives the Pi internet over the cable)

Do this on the Mac, with the cable between the Mac's USB 10/100/1000 LAN adapter and the Pi's **built-in** Ethernet port (not the USB-Ethernet adapter; that one is Art-Net).

1. **System Settings → Network → USB 10/100/1000 LAN → Details → TCP/IP**: Configure IPv4 = **Using DHCP**. If it says Manual with `2.0.0.2`, that's left over from testing the DMX-AN2 directly from the Mac; change it.
2. **System Settings → General → Sharing → Internet Sharing → ⓘ**:
   - Share your connection from: **Wi-Fi**
   - To devices using: **USB 10/100/1000 LAN** (on)
3. Turn **Internet Sharing** on. The Mac becomes `192.168.2.1` on the cable.
4. Wait about a minute (the Mac's DHCP can be slow to start), then unplug and replug the cable at the Pi. The Pi should get `192.168.2.2` (it may differ; the status script shows it).
5. Connect from the Mac: `ssh justin@192.168.2.2`, or VS Code Remote-SSH to the same.

**Testing the DMX-AN2 straight from the Mac** (no Pi): turn Internet Sharing off, set the adapter to Manual `2.0.0.3`, subnet `255.0.0.0` (`2.0.0.2` is the Pi's `eth1`, `2.0.0.1` is the DMX-AN2). Set it back to Using DHCP afterwards.

## Setting up the access point

Run on the Pi, connected **over the cable** (or HDMI + keyboard), never over home WiFi: it takes `wlan0` off home WiFi.

```bash
cd ~/parade-2026
bash scripts/pi-ap.sh --dry-run   # shows exactly what it will do, changes nothing
bash scripts/pi-ap.sh             # first run asks for the WiFi password
```

The first run installs hostapd, so the Pi needs internet (Mac Internet Sharing is fine). It's safe to rerun; it rewrites the same settings and restarts the access point (connected iPads drop for a few seconds).

What it changes on the Pi:

| File | Purpose |
|---|---|
| `/etc/parade/ap.env` | WiFi password (`AP_PASSWORD=...`), root-only, never in git |
| `/etc/hostapd/hostapd.conf` | WiFi network: name, channel 6, WPA2-AES (contains the password, root-only) |
| `/etc/systemd/system/hostapd.service.d/parade.conf` | Switches the WiFi radio on before hostapd starts at boot |
| `/etc/systemd/system/parade-ap-network.service` | Gives `wlan0` `10.0.0.1` and hands out addresses (dnsmasq) |
| `/etc/NetworkManager/conf.d/90-parade-ap.conf` | Tells NetworkManager to leave `wlan0` alone |

Everything starts automatically at boot.

- **See the password:** `sudo cat /etc/parade/ap.env`
- **Change the password:** `sudo rm /etc/parade/ap.env`, then `bash scripts/pi-ap.sh` (it asks for a new one). Forget the network on the iPad and rejoin.
- **Change the WiFi name or channel:** edit `AP_SSID` / `AP_CHANNEL` at the top of `scripts/pi-ap.sh`, then rerun it.
- **Back to home WiFi** (rarely needed; the cable gives the Pi internet): `bash scripts/pi-ap.sh --undo`. NetworkManager takes `wlan0` back and rejoins saved WiFi. Run `bash scripts/pi-ap.sh` to return to the access point.

## Checking status

```bash
bash scripts/pi-network-status.sh
```

Read-only, no sudo. Prints each port in plain English with `[ OK ]` / `[WARN]`, the internet check, whether `parade` is running, and the exact addresses to use from the iPad and the Mac.

## Test checklist

Run after any network change, and on install day.

| # | Do | Expected |
|---|---|---|
| 1 | `bash scripts/pi-network-status.sh` (over the cable) | All `[ OK ]`: broadcasting `very-good-float-2026`, `10.0.0.1/24`, DHCP running; `eth0` `192.168.2.x`; `eth1` `2.0.0.2/8`, no gateway; internet reachable; `parade` running, port 8080 listening |
| 2 | iPad: Settings → Wi-Fi → `very-good-float-2026`, enter the password | Joins. "No Internet Connection" under the name is normal |
| 3 | iPad: Safari → `http://10.0.0.1:8080` | Parade dashboard loads |
| 4 | Status script again | "Devices connected right now: 1" and the iPad listed with a `10.0.0.x` address |
| 5 | `ping -c 3 2.0.0.1` on the Pi | 3 replies from the DMX-AN2 |
| 6 | Mac browser → `http://192.168.2.2:8080` | Dashboard loads over the cable |
| 7 | **Reboot test:** `sudo reboot`, wait 2 minutes | WiFi reappears, iPad rejoins by itself, dashboard loads; `ssh justin@192.168.2.2` works again; status all `[ OK ]` |
| 8 | **Parade-day test:** unplug the Mac cable, reboot the Pi | iPad still joins and the dashboard works. Status shows the cable as "not connected" and no internet; both are normal |

## Install day routine

1. Mac: Internet Sharing on (steps above); cable from the Mac to the Pi's **built-in** Ethernet port.
2. `ssh justin@192.168.2.2` (or VS Code). Address unknown? See troubleshooting.
3. Update: `cd ~/parade-2026 && git pull`, then `sudo systemctl restart parade`.
4. `bash scripts/pi-network-status.sh`; fix anything marked `[WARN]`.
5. Run test checklist items 2–5.
6. Back up the SD card ([HARDWARE_SETUP_CHECKLIST.md §8](HARDWARE_SETUP_CHECKLIST.md)).

## Parade day routine

1. Power the Pi; wait about 2 minutes.
2. iPad: join `very-good-float-2026`, open `http://10.0.0.1:8080`. Bookmark it to the home screen once, beforehand.
3. Check the DMX fixtures respond (dashboard scene buttons).
4. Keep the [recovery card](NETWORK_RECOVERY.md) and a spare SD card with the box.

## Troubleshooting

**The Pi gets no address on the cable (`eth0`)**
- On the Mac, the USB 10/100/1000 LAN adapter must be **Using DHCP**, not Manual (`2.0.0.2` left over from DMX-AN2 testing breaks Internet Sharing).
- Turn Internet Sharing off and on. The Mac's DHCP can take about a minute to start answering after that.
- The Pi gives up after 4 failed tries (about 3 minutes) and doesn't retry by itself. **Unplug and replug the cable** at the Pi to make it try again.
- Check the cable goes into the Pi's built-in port, not the USB-Ethernet adapter.

**I don't know the Pi's address on the cable**
- On the Mac: `arp -a | grep bridge100`. The Pi is the `192.168.2.x` entry that isn't `.1`. Its hardware address starts `b8:27:eb`.
- Or connect over the parade WiFi instead: join `very-good-float-2026` from the Mac, `ssh justin@10.0.0.1`.

**The phone says "incorrect password"**
- Check the password: `sudo cat /etc/parade/ap.env`. Passwords are case-sensitive.
- On the phone: tap ⓘ next to the network → Forget This Network, then join again.
- If the right password still fails, make sure hostapd (not NetworkManager) runs the WiFi: the status script should say "Broadcasting", and `nmcli device` should list `wlan0` as **unmanaged**. If not, rerun `bash scripts/pi-ap.sh`.

**The WiFi network doesn't appear**
- `systemctl status hostapd parade-ap-network`, and `journalctl -u hostapd -b` for errors.
- Radio switched off? `rfkill list wifi` must show "Soft blocked: no". Fix: `sudo rfkill unblock wlan && sudo systemctl restart hostapd`.
- Restart it: `sudo systemctl restart hostapd parade-ap-network`, or rerun `bash scripts/pi-ap.sh`.

**The iPad joins but the dashboard won't load**
- Check the address: `http://10.0.0.1:8080` (http, not https; port 8080).
- Status script: is `parade` running and port 8080 listening? Logs: `journalctl -u parade -e`.
- iPad shows a `169.254.x.x` address (Settings → Wi-Fi → ⓘ): DHCP isn't answering. `sudo systemctl restart parade-ap-network`.

**The Pi has no internet even though the cable is connected**
- The Mac itself must be online (on its WiFi). Status script shows where internet traffic goes; it should be `eth0 via 192.168.2.1`.

**DMX fixtures don't respond**
- `ping -c 3 2.0.0.1`. No reply: check the DMX-AN2 power and the cable into the **USB-Ethernet adapter**, and that the status script shows `eth1` at `2.0.0.2/8`.
- `eth1` must have no gateway. If it gained one: `nmcli con show artnet | grep -E 'gateway|never-default'` should show no gateway and `never-default: yes`.

**Nothing works and you can't get in**
- Use the [recovery card](NETWORK_RECOVERY.md): HDMI monitor + USB keyboard, or restore the SD-card backup.
