# Project Status

_Last updated: 2026-10-02_

**Next step:** finish the box layout checks (WIRING_GUIDE Part 1 "Box layout": confirm the ALITOVE's terminal order, measure the 5V fuse module and Pi breakout, cardboard mock-up of the mains column), then run `bash scripts/pi-setup.sh`, reboot, and bench-test the switches (WIRING_GUIDE Parts 1, 3, 4).

## 2026-10-02

- **Pi networking set up** ([NETWORK.md](NETWORK.md)): `wlan0` is the WiFi access point `very-good-float-2026` at `10.0.0.1` (iPhone joined and got `10.0.0.187`); `eth0` (built-in Ethernet) gets internet and SSH from the Mac via Internet Sharing (`192.168.2.2`); `eth1` Art-Net unchanged.
- The access point runs on **hostapd**, not NetworkManager's hotspot, which phones rejected with "incorrect password" on the Pi 3's WiFi chip (ADR-016). `scripts/pi-ap.sh` reads the password from root-only `/etc/parade/ap.env` and supports `--dry-run` / `--undo`.
- New read-only `scripts/pi-network-status.sh`; printable [NETWORK_RECOVERY.md](NETWORK_RECOVERY.md).
- Still to do: NETWORK.md test checklist items 7–8 (reboot test, parade-day test without the Mac cable) and an SD-card backup.

## 2026-10-01

- **MANUAL mode** (`src/parade/core/manual.py`, Manual tab → "Manual Mode — Hardware Test"): entered from SAFE only. Cues are ignored; the operator switches relays on/off with no time limit, sees each input's live state and a press counter, and sets the NeoPixels to a colour or a built-in animation (rainbow, chase, breathe, marquee). Leaving MANUAL drives relays off and blanks the strip. Intended for setting the motor speed controller and checking switches. The index switch does **not** stop the motor in MANUAL (docs/SAFETY.md).
- **Relay + contactor coil verified switching ON** on the Pi (`parade-hwcheck relay`, and from MANUAL mode).
- **Art-Net link to the DMX-AN2 working** over a USB-Ethernet adapter (`eth1`, NetworkManager profile `artnet`, static `2.0.0.2/8`). The node answers ArtPoll as `DMX-AN2`, both ports on universe 1.
- `config/default.yaml` now uses the `rpi` drivers for GPIO, relays and pixels.
- **E-stop monitor temporarily disabled** (`safety.estop_pin: null`) until the e-stop is wired. Re-enable (`estop_pin: estop_monitor`) before any test with people near the booth.

## Hardware design changes, 2026-09-27

- **5V distribution:** the DaierTek blade fuse block is replaced by a 6-channel DIN-rail blade fuse module (BOM 2.1; DaierTek kept as a spare). Channels: **V1 Pi 3A, V2 strip 5A, V3 Pixel Shifter 1A, V4 relay board 1A**, V5/V6 spare. Each channel has its own V− terminal, so no separate 5V GND bus. The module ships with 3A in every channel: re-fuse before use.
- **Pixel Shifter** now has its own fused channel (V3) instead of sharing the strip's.
- **Wire gauges** are specified for every run (WIRING_GUIDE Part 1 "Wire sizes"): 16 AWG for all 120V and the ALITOVE → module feed, 22 AWG Pi pigtail, 16 (or 18) AWG strip power, 22–18 AWG signal, 18 AWG field cable.
- **Part 7 wire list** now names the physical part and clamp for every wire (e.g. "IEC inlet L tab → 120V L bus, L #1 top").
- **Box layout** drafted (WIRING_GUIDE Part 1): 4" mains column on the left, ALITOVE top-right with its terminal end facing the mains column, 5V parts bottom-right, low-voltage entries on the bottom wall, e-stop on the lid. Not yet mocked up.

## Milestone 1 — Mac + DMX proof of concept: **complete**

## Milestone 2 — Raspberry Pi + physical GPIO + NeoPixels: **software done, wiring in progress**

Done:
- Real drivers selectable per device in `config/default.yaml` → `hardware`:
  - GPIO inputs: `src/parade/gpio/rpi.py` (lgpio, kernel debounce)
  - Relays: `src/parade/relay/rpi.py` (claimed and released in the off state)
  - NeoPixels: `src/parade/pixels/rpi.py` (WS2812B over SPI on GPIO10, `brightness` cap)
- `SafetyMonitor` (`src/parade/core/safety.py`): e-stop monitor input on GPIO22, relays off whenever the state leaves RUNNING, reset blocked while the e-stop is pressed. State changes are now published as `system_state_changed` events.
- The cue engine refuses relay-ON outside RUNNING, and cancels running cues on SAFE, FAULT or EMERGENCY_STOP.
- `stop_rotation_at_index` cue: the index switch cuts the motor relay.
- Status lights: two BlinkStick Nanos show system state and Pi health/heartbeat (`src/parade/status_lights/`, colour key in [HARDWARE.md](HARDWARE.md#status-lights)).
- OLED status display: 128×32 SSD1306 on I2C rotates WiFi join info, show state, network and diagnostics (`src/parade/display/`, see [HARDWARE.md](HARDWARE.md#status-display)).
- `parade-hwcheck` bench tool; `scripts/pi-setup.sh` installs lgpio/spidev and enables SPI.
- Verified on the Pi 3: input pull-ups and reads on GPIO17/22/27, relay claim/release low on GPIO18, full app boot with rpi GPIO + relay drivers (trips EMERGENCY STOP with the monitor unwired, as designed).

Not yet verified on hardware:
- NeoPixel output (SPI is now enabled; strip not yet tested).
- RockWedge fixtures responding to DMX (node link verified; fixture addresses/mode not yet checked).
- Everything in [WIRING_GUIDE.md](WIRING_GUIDE.md) Parts 2–8.

Open questions (block parts of Part 7):
- Motor fuse size (expected T5A/T6.3A): needs the motor/controller rated current or a measured running current.
- Speed controller auto-start on power-up (WIRING_GUIDE step 19). If it doesn't restart by itself, the switching plan changes.
- Which event turns the motor on. Only the stop is defined.
- E-stop placement: proposed on the box lid over the mains column (WIRING_GUIDE "Box layout"); confirm it clears the contactor with the lid shut.
- Box layout fit: sizes of the 5V fuse module and the Pi DIN breakout aren't recorded yet.

Parts: all control-box parts are on hand or ordered except the 120V wire (16/3 extension cord cores) and, if not in stock, a 1000µF capacitor and heat-shrink. See [BOM.md](BOM.md) "Still to buy".

## Known issues
- `safety.estop_pin` is `null` in `config/default.yaml` while the e-stop is unwired: the software does not watch the e-stop.
- e2e tests (`tests/e2e`) need a Playwright browser, which doesn't launch on the Pi; run them on the Mac.
