# Control Box Hardware Setup Checklist

Background and requirements for moving the Raspberry Pi from the bench into the float's control box and wiring GPIO inputs, NeoPixels and the booth-rotation relay. **For the step-by-step wiring order and tests, follow [WIRING_GUIDE.md](WIRING_GUIDE.md)**; this checklist holds the details it refers to. Parts to buy are listed in [BOM.md](BOM.md).

## System at a glance

| Load | Powered from | Controlled by | Pi involvement |
|---|---|---|---|
| Raspberry Pi 3 Model B | ALITOVE 5V 60A supply (control box) | — | — |
| NeoPixel strip(s), WS2812B | ALITOVE 5V 60A supply (control box) | Pi GPIO data line | Direct |
| Phone booth rotation motor | Generator 120V AC via the box's IEC inlet (not the ALITOVE) | Relay module on GPIO18 + e-stop in series | Relay input only |
| Turntable index microswitch, performer button, e-stop monitor contact | Pi 3.3V / GND (internal pull-ups) | — | GPIO17, GPIO27, GPIO22 inputs |
| Cold spark machine, fog machine | Generator (direct) | Wireless DMX via DMX-AN2 | Art-Net over eth1 (USB-Ethernet) only |
| RockWedge LED fixtures | Batteries | Wireless DMX via DMX-AN2 | Art-Net over eth1 (USB-Ethernet) only |

The spark and fog machines have no electrical connection to the control box, so they are out of scope here. The only hazardous load the Pi controls is the rotation motor.

---

## 1. Software prerequisites (before wiring anything)

Real drivers exist for all three (`gpio_driver`, `relay_driver`, `pixel_driver: rpi`): `src/parade/gpio/rpi.py` (lgpio, kernel debounce, callbacks handed to the asyncio loop), `src/parade/relay/rpi.py` (claimed off, released off) and `src/parade/pixels/rpi.py` (SPI on GPIO10).

- [x] Real GPIO input, relay and NeoPixel drivers.
- [ ] Run `bash scripts/pi-setup.sh` (installs `python3-lgpio`/`python3-spidev`, venv with `--system-site-packages`, enables SPI, adds `core_freq=250`) and reboot.
- [ ] Bench-test each device with `.venv/bin/parade-hwcheck` as you wire it (WIRING_GUIDE).
- [ ] Switch each driver to `rpi` in `config/default.yaml` once its device passes.

## 2. Power supply (ALITOVE 5V 60A)

A 60A supply is far more than needed (Pi ≤ 2.5A, 50 pixels ≈ 3A at full white), so it will not run out of capacity. The real risk is the opposite: **it will feed a short circuit with up to 60A until a wire melts.** On a float with vibration and connectors being handled, design for that.

### Fusing
- [ ] Fuse **each output branch separately**, close to the supply terminals.
  - Pi branch: ~3A.
  - Each NeoPixel strip branch: sized to the wire, not the load (e.g. 5A for 18 AWG). The fuse protects the wire.
- [ ] Use wire thick enough for its fuse rating, and keep the Pi's feed short.

### Setting the output voltage
- [ ] With a multimeter, measure **at the Pi's power input** (not at the supply terminals) with the NeoPixels at full white.
- [ ] Adjust the supply's **V ADJ** trimmer until the Pi sees **≈ 5.1V**.
  - Pi is happy at 5.0–5.25V. Below ~4.63V it flags under-voltage. Above ~5.25V risks damage.
- [ ] Re-check after the box is fully wired.

### Mains side (AC 110/220V in an enclosed box on a float)
- [ ] **Set the supply's 110V/220V selector switch to 110V** before first power-up (US generator ≈ 120V). On 220V it won't run properly on 120V; on 110V it is destroyed by 220–240V. Tape or glue the switch so it can't be knocked.
- [ ] Fit a **5×20mm slow-blow (T) 250V** fuse in the IEC inlet. ALITOVE doesn't publish the input current; estimated ≈ 5.7A at 110V full load, so **8A** is the working choice (above the load, below the inlet/18 AWG cord's 10A). Confirm against the case label or the supply's internal fuse marking (e.g. `T6.3AL250V`, visible through the vents; supply unplugged) and match or go one step above it.
- [ ] Cover the AC screw terminals (terminal cover or heat-shrink boots). They are live when the box is open.
- [ ] Connect the supply's earth (⏚) terminal to the incoming cord's earth conductor.
- [ ] Strain relief / cable clamp where the AC cord enters the box.
- [ ] Ventilation in and out of the box. The supply has a fan and needs airflow. Watch the dashboard temperature (§7).
- [ ] If running from the generator: switch the supply off while starting the generator; switch on once it's stable.

## 3. Powering the Pi

- [ ] Decide how 5V reaches the Pi:
  - **5V GPIO pins (pin 2/4):** bypasses the Pi's on-board polyfuse, so the branch fuse from §2 is mandatory.
  - **Cut micro-USB cable to the supply:** keeps the polyfuse, but USB cables are thin. Keep it short and check voltage at the Pi.
- [ ] Ground from the Pi goes back to the supply's **−** terminal on its own wire (not via the strip's wiring).
- [ ] Confirm the dashboard power indicator shows **PWR OK** with the NeoPixels at full white (§7).

## 4. NeoPixels (WS2812B)

### Power
- [ ] Separate power wires from the supply terminals to the strip. Don't chain the Pi's power through the strip, or the strip's through the Pi.
- [ ] Fuse on the strip branch (§2).
- [ ] 1000µF electrolytic capacitor (≥ 6.3V) across + and − at the strip's power input, observing polarity.
- [ ] Longer strips / more strips later: inject power at both ends (or every ~100–150 pixels), each injection point fused.
- [ ] Consider capping brightness in software (50–60% still looks bright and roughly halves current).

### Data signal (3.3V → 5V)
WS2812B needs a logic "high" of ~0.7 × its supply voltage: ~3.5V at 5.0V, ~3.64V at 5.2V. The Pi outputs 3.3V. It often works on the bench and then fails with longer wires, cold, or a slightly high supply. Symptoms are flicker and wrong colours, starting at the first pixel.
- [ ] Add a level shifter between the Pi and the strip: **Adafruit Pixel Shifter** (screw terminals), or a bare **74AHCT125** / 74HCT245 chip on perfboard powered from the same 5V (see [BOM.md](BOM.md) 4.1).
- [ ] ~330Ω series resistor on the data line, close to the first pixel.
- [ ] Keep the shifter-to-first-pixel data wire short.
- [ ] Pi GND, shifter GND and strip GND all common (back to the supply's −).

### Pin choice (Pi 3)
The strip is driven over SPI on **GPIO10 (MOSI, physical pin 19)**, not PWM on GPIO12. SPI needs no root and doesn't conflict with the Pi 3's on-board audio. The rpi pixel driver only accepts `pin: 10`.
- [ ] SPI enabled and `core_freq=250` set (both done by `scripts/pi-setup.sh`; reboot after). `ls /dev/spidev0.0` must succeed.
- [x] `pixel_strips[0].pin` is `10` in `config/default.yaml`.
- Strips longer than ~160 pixels need `spidev.bufsiz=65536` added to `/boot/firmware/cmdline.txt`; the driver says so at startup if needed.

## 5. Relay and rotation motor

### Relay: module, not bare relay
A bare relay coil needs ~70–90mA and often 5V. A GPIO pin can safely supply ~16mA at 3.3V. Use a **relay module** (transistor or optocoupler driver on board). The GPIO drives only the module's input (a few mA), and the coil runs from the module's own supply.
- [ ] Confirm the relay is a module with a driver stage. **Record model:** ______________________
- [ ] Bench-test that it switches reliably from a **3.3V** GPIO signal. Some 5V modules don't.
- [ ] On hand: 3 × generic 1-channel 5V relay boards. Check trigger type (H/L jumper or silkscreen) and use **high-level trigger** (`active_low: false`). A low-trigger board turns **on** while the Pi boots, because GPIO18 is held low during boot.
- [ ] Power the board's VCC from a **fused 5V branch of the ALITOVE** (not the Pi's 5V pin); GND common; IN → GPIO18.
- [ ] Bench test without the driver: `pinctrl set 18 op dh` → relay ON; `pinctrl set 18 op dl` → relay OFF (if it won't release, the board can't be driven from 3.3V); `sudo reboot` → relay stays OFF throughout boot.

### Motor side
- [ ] **Motor:** Bemonoc 300 W 110V AC gear motor + speed controller. Contactor chosen (Schneider LC1D09G7). **Still collect from the labels / on the bench** (sizes the motor fuse, sets the index cam position):
  - [ ] Photo of the **nameplate**: voltage ______ AC/DC ______ current (A/FLA) ______ power (W/HP) ______ phase/Hz ______ duty ______ code letter ______
  - [ ] Thermally protected? ______ Auto-reset? ______ (auto-reset motors can restart by themselves once cool; the contactor wiring below handles this)
  - [ ] How it's powered/controlled today: wall plug / battery / **speed controller or driver** (photo its label too; a controller changes where the contactor goes)
  - [ ] Gearbox type (worm usually self-locks; spur/belt coasts). **Coast-down time** after cutting power, with the booth loaded: ______ s. If it coasts for more than a moment, a brake may be needed; the e-stop removes power, it doesn't stop inertia.
  - [ ] Power source on the float (generator 120V AC / battery / other) and cable run length box → motor: ______
  - [ ] Optional: running current under real load (booth + person), and start-up peak, with a clamp meter
- [x] **Wiring decided (Design B):** generator 120V → IEC inlet (T8A) → Dinkle L/N/PE blocks. Motor path: L → motor fuse → contactor pole 1 → outlet hot; N → contactor pole 2 → outlet neutral; earth straight through. Coil circuit: L → T1A → e-stop NC #1 → relay COM→NO → contactor A1, A2 → N. Full wire list: WIRING_GUIDE Part 7.
- [x] The relay board switches only the contactor coil; the contactor (½ HP rated) carries the motor and its start-up surge. No flyback diode or motor snubber needed (AC motor on its own controller).
- [ ] The motor never runs from the ALITOVE. It gets its own fused mains branch from the inlet, tapped ahead of the e-stop and relay so the Pi stays powered when the motor is cut. Keep motor/mains wiring away from the 5V/GPIO wiring.

### Boot and failure behaviour
- [ ] GPIO18 is pulled **low** during Pi boot. With `active_low: false` the relay stays **off** (motor stopped) while the Pi boots. If you switch to a low-trigger module (`active_low: true`), re-verify the motor doesn't twitch at power-up.
- [ ] If the app crashes or freezes while the motor is running, the relay **holds its last state**, so the booth keeps spinning. That's why the e-stop below is required.

### Motor e-stop (required)
- [ ] **Normally-closed** e-stop contact (XB4BS8445, terminals 1–2) wired **in series with the contactor coil**, independent of the Pi. Pressing it, a cut wire or a pulled connector all drop the contactor and stop the motor.
- [ ] Mounted where the operator can reach it while watching the booth.
- [ ] Second NC contact block (ZBE102) on the e-stop wired **GPIO22 ↔ GND** (`estop_monitor`, `safety.estop_pin`). Pressed or cut reads ACTIVE: the app goes to EMERGENCY STOP, drives relays off, cancels cues, and blocks reset until released (see SAFETY.md). Monitoring only; the Pi must never be what makes it safe.
- [ ] Test: motor running → press e-stop → motor stops, even with the Pi unplugged.

## 6. GPIO inputs (microswitch, performer button)

- [ ] **3.3V only.** Never connect 5V or 12V to a GPIO pin.
- [ ] Wiring: switch between the GPIO pin and GND; internal pull-up enabled (`pull: up`). This is already the config.
  - Performer button: **GPIO27** (physical pin 13), **NO** contact, `active_low: true`. A broken wire = never "ready".
  - Turntable index microswitch: **GPIO17** (physical pin 11), **C + NC** contacts, `active_low: false`. A broken wire reads as "at index", which cuts the motor. Add a **2.2kΩ** pull-up GPIO17 → 3.3V: the V-153-1C25's high-current contacts switch unreliably at the internal pull-up's ~0.07 mA.
  - E-stop monitor: **GPIO22** (physical pin 15), NC contact, `active_low: false`.
- [ ] Long cable runs across the float pick up noise. If you see false triggers in the event log, add an external 4.7–10kΩ pull-up to 3.3V and/or a 100nF capacitor from pin to GND at the Pi end.
- [ ] Twisted pair (signal + GND) for long runs where possible.
- [ ] Tune `debounce_ms` if a single press logs multiple events.

## 7. Using the dashboard power indicator

The **Live** tab opens with a **Pi Health — Power & Thermal** card, updated every 2 seconds:

- **Status banner:** what's wrong, in plain words, and what to do.
- **Tiles:** supply, throttling, CPU temperature (with session max), CPU clock, CPU load, memory, uptime.
- **Chart:** CPU temperature over the last 10 minutes, with red/amber strips marking exactly when under-voltage or throttling happened. Hover or touch it for readings at any moment. Use it to match a dip to the cue that caused it.
- **Firmware flags table:** each condition, now vs since boot, plus event counts for this app session.

The header also shows a small **PWR** pill on every tab. Tap it to jump to the card. Changes are also written to the event log (tag `power`) and to the system journal (`journalctl -u parade`).

The Pi 3 cannot measure its supply voltage, only whether it fell below ~4.63V. Use a multimeter for actual volts.

| Pill | Meaning | Action |
|---|---|---|
| `PWR OK · 47°C` (green) | No problems since boot | — |
| `PWR DIP SINCE BOOT` (amber) | Supply dipped below ~4.63V at some point since boot | Check wiring and voltage at the Pi. Clears only on reboot. |
| `PWR THROTTLED SINCE BOOT` (amber) | CPU was slowed at some point since boot | Usually heat or supply. Check both. |
| `PWR WARM` (amber) | CPU ≥ 70°C | Improve box ventilation |
| `PWR UNDER-VOLTAGE` (red, blinking) | Supply is low **right now** | Fix before showing |
| `PWR THROTTLED` / `OVERHEAT` (red) | CPU slowed now / ≥ 80°C | Fix before showing |
| `PWR n/a` (grey) | Not running on a Pi (e.g. Mac) | — |

### Power stress test (do after §3 and §4)
- [ ] Reboot the Pi (clears the since-boot flags).
- [ ] Run the NeoPixels at full white, full brightness, for several minutes.
- [ ] Run a fast full-brightness flash/strobe effect (worst case for current spikes).
- [ ] Pill must stay **green**. Any amber/red means voltage is sagging in the wiring. Check wire gauge, connections and voltage at the Pi.
- [ ] Repeat with the box closed for 20+ minutes to check temperature.

## 8. Before show day

- [ ] Run `bash scripts/pi-setup.sh` to install the systemd service (starts on boot). The service serves on **port 8000**; running `parade` by hand uses **8080**.
- [ ] Run `bash scripts/pi-ap.sh` to switch wlan0 to the `parade-2026` access point. Do this from HDMI+keyboard or over Ethernet, not over WiFi SSH. See `scripts/README.md`.
- [x] Plug the DMX-AN2 into the USB-Ethernet adapter (`eth1`) and give it a static `2.0.0.2/8` address. Done with a NetworkManager profile (no gateway, so internet stays on wlan0):
  `sudo nmcli con add type ethernet con-name artnet ifname eth1 ipv4.method manual ipv4.addresses 2.0.0.2/8 ipv4.never-default yes ipv6.method disabled`
  Check with `ping 2.0.0.1`. If the adapter ever enumerates under another name, re-point the profile (`nmcli con mod artnet connection.interface-name <name>`).
- [ ] Enable the read-only overlay filesystem (`raspi-config` → Performance → Overlay File System) so sudden power cuts can't corrupt the SD card. Turn it off again to make config changes.
- [ ] Back up the SD card image.

## Open questions

- Relay module: relay is a **Helishun HLS8L-DC5V-S-C** (datasheet gives no motor rating, so it switches the contactor coil, Design B). Still to confirm: the board's trigger type (high/low jumper) and the 3.3V bench test.
- Rotation motor: **Bemonoc 300 W 110V AC gear motor, 45 RPM, with speed controller** ([B0GSYZCTPM](https://www.amazon.com/dp/B0GSYZCTPM)), switched via a Schneider LC1D09G7 contactor (WIRING_GUIDE Part 7, Design B). Still needed: rated current from the labels or a measured running current (→ motor fuse, expected T5A/T6.3A), plug type (expected NEMA 5-15P), whether the controller auto-starts when power is applied (WIRING_GUIDE step 19), and coast-down time.
- Which event turns the motor **on** (performer button? operator trigger?). The index switch already turns it off (`stop_rotation_at_index` cue).
- Final NeoPixel count and layout (affects power injection and fusing).
- E-stop placement: on the control box (simplest; 120V stays inside) or remote (needs its own enclosure and mains-rated cable, BOM 5.8).
