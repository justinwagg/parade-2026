# Hardware

Control-box wiring: [WIRING_GUIDE.md](WIRING_GUIDE.md) (step by step) · [HARDWARE_SETUP_CHECKLIST.md](HARDWARE_SETUP_CHECKLIST.md) (background, power, open questions) · [BOM.md](BOM.md) (parts) · [SAFETY.md](SAFETY.md).

## Controller

Raspberry Pi 3 Model B, Raspberry Pi OS (Debian 13), powered from the ALITOVE 5V 60A supply. GPIO via `lgpio` on `/dev/gpiochip0`; NeoPixels via `spidev` on `/dev/spidev0.0`.

## Pin map (BCM)

| GPIO | Header pin | Use | Wiring | Config |
|---|---|---|---|---|
| 17 | 11 | Tabletop index microswitch (V-153-1C25) | C + **NC** to GND, pull-up + external 2.2kΩ to 3.3V | `rotation_index`, `active_low: false` |
| 27 | 13 | Performer ready button | **NO** to GND, pull-up | `performer_button`, `active_low: true` |
| 22 | 15 | E-stop monitor contact (NC #2, ZBE102) | **NC** to GND, pull-up | `estop_monitor`, `active_low: false`, `safety.estop_pin` |
| 18 | 12 | Relay board IN (HLS8L 5V, high-trigger) → contactor coil | → relay board IN | `phone_booth_rotation`, `active_low: false` |
| 10 | 19 | NeoPixel data (SPI0 MOSI) | → Adafruit Pixel Shifter → 330Ω → DIN | `main_strip`, `pin: 10` |
| 8, 9, 11 | 24, 21, 23 | Reserved by SPI0 | do not use | — |
| 2 | 3 | OLED status display SDA (I2C1) | → OLED module SDA | `display` |
| 3 | 5 | OLED status display SCL (I2C1) | → OLED module SCL | `display` |

Rule of thumb for inputs: wire **NO** when a broken wire should mean "nothing happened" (performer button). Wire **NC** when a broken wire should mean "stop" (index, e-stop).

## Drivers

`config/default.yaml` → `hardware`: `gpio_driver`, `relay_driver`, `pixel_driver` are each `simulated` or `rpi` and can be switched independently. `status_light_driver` is `simulated` or `blinkstick`. `display_driver` is `simulated` or `ssd1306`. `gpio_chip` selects `/dev/gpiochipN` (0 on a Pi 3).

## Status lights

Two BlinkStick Nanos in the Pi's USB ports. Each Nano has two LEDs; only LED 1 (`led_index: 1`) faces up through the enclosure lid. Sticks are matched by serial, so either can go in any port. Config: `status_lights` in `config/default.yaml`. Needs `python3-usb` and the udev rule `/etc/udev/rules.d/85-blinkstick.rules` (both from `scripts/pi-setup.sh`).

**Left (`BS025458`): system state**, same colours as the dashboard.

| Light | State |
|---|---|
| blue | BOOTING |
| dim white | SAFE |
| yellow | READY |
| green | RUNNING |
| orange | PAUSED |
| purple | MANUAL |
| red, fast blink | EMERGENCY STOP |
| red, solid | FAULT |
| brief white flash | a cue just started |

**Right (`BS025473`): Pi health + heartbeat.** A slow pulse means the app is running. If it stops pulsing (frozen or off), the app has hung or exited.

| Light | Meaning |
|---|---|
| green pulse | power and temperature OK |
| yellow pulse | under-voltage or throttling happened since boot (clears on reboot), or CPU ≥ 70 °C |
| red, fast blink | under-voltage now: check the 5 V supply and wiring |
| orange, fast blink | CPU throttled or ≥ 80 °C now |
| dim white pulse | no health data |

## Status display

128×32 SSD1306 OLED on I2C1 at `0x3C`, mounted upside down (`rotate: 2`). Wiring: OLED module VCC → GPIO header pin 1 (**3.3 V**, not 5 V: the module pulls SDA/SCL up to VCC), OLED GND → header pin 9, OLED SDA → header pin 3 (GPIO2), OLED SCL → header pin 5 (GPIO3). Needs I2C enabled and `python3-luma.oled` (both from `scripts/pi-setup.sh`). Check it with `i2cdetect -y 1` (shows `3c`). Config: `display` in `config/default.yaml`.

Pages rotate every 4 s. In EMERGENCY STOP or FAULT the display holds the show page.

| Page | Shows |
|---|---|
| join | WiFi SSID, password, controller URL (`http://10.0.0.1:8080`) |
| show | state (+ ARMED), running cue, whether the Art-Net node (2.0.0.1) answers |
| network | IP or "unplugged" for the Mac cable (eth0), WiFi (wlan0, + devices joined), Art-Net (eth1) |
| diag | CPU temperature, power status, load, memory, uptime, CPU clock |

A pixel in the top-right corner blinks once a second while the app runs. If it stops, the app has hung. On a clean stop the display shows "parade stopped".

The SSID and password come from `/etc/parade/ap-display.env`, written by `scripts/pi-ap.sh` (chmod 640, readable by the app's user only). If it's missing, the join page says "WiFi details n/a".

## Manual mode

With the app running, go SAFE → **MANUAL** (Manual tab → "Manual Mode — Hardware Test") to switch relays on/off, watch each input's live state and press counter, and run NeoPixel colours/animations without any cue. Use it to set the speed controller with the booth turning. The index switch does not stop the motor in MANUAL; use OFF, SAFE or the e-stop. See [SAFETY.md](SAFETY.md).

## Bench tool

`.venv/bin/parade-hwcheck inputs | relay [ID] [--seconds N] | pixels test | pixels color R G B`. Uses the real drivers and the config. Stop the service first. The relay check honours the e-stop monitor.
