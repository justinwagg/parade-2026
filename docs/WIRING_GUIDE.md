# Control Box Wiring Guide (play-by-play)

Step-by-step wiring for the five field devices, in the order to build them. Each part ends with a test that must pass before you move on. Parts are in [BOM.md](BOM.md). Background and the reasoning behind each choice are in [HARDWARE_SETUP_CHECKLIST.md](HARDWARE_SETUP_CHECKLIST.md) and [SAFETY.md](SAFETY.md).

| Part | Device | Your item # |
|---|---|---|
| 1 | Before you start: pin map, tools, software | — |
| 2 | Box power: IEC inlet → 5V supply → Pi | (feeds 3 & 4) |
| 3 | Performer "ready" button | 1 |
| 4 | Tabletop index microswitch | 2 |
| 5 | Emergency-stop button (mount + monitor contact) | 5 |
| 6 | NeoPixel strip | 4 |
| 7 | Relay, motor outlet and e-stop power contact | 3 (+ 5) |
| 8 | Whole-system test | — |

The relay and motor come last on purpose: they are the only mains-switching, moving-machinery part, and they depend on the e-stop being in place.

---

## Part 1 — Before you start

### Ground rules
- **Mains work is done unplugged.** Unplug the box's IEC cord (not just the rocker switch) before touching anything on the AC side. The supply's capacitors can hold charge: wait a minute after unplugging.
- **3.3V only on GPIO pins.** Never let 5V, 12V or mains reach a GPIO terminal. Every switch below connects a GPIO pin to **GND** only.
- **Stop the service before bench tests.** Only one program can own the pins: `sudo systemctl stop parade`.

### Pin map (Raspberry Pi 3, BCM numbering)

| Function | GPIO | Header pin | Suggested GND pin | Config id |
|---|---|---|---|---|
| Tabletop index microswitch | **GPIO17** | 11 | 9 | `rotation_index` |
| Performer button | **GPIO27** | 13 | 14 | `performer_button` |
| E-stop monitor contact | **GPIO22** | 15 | 20 | `estop_monitor` |
| Relay module IN | **GPIO18** | 12 | (see Part 7) | `phone_booth_rotation` |
| NeoPixel data (SPI0 MOSI) | **GPIO10** | 19 | 25 | `main_strip` |
| *Reserved by SPI: do not use* | GPIO8, 9, 11 | 24, 21, 23 | — | — |

All GND pins are the same connection. The "suggested" one is just the nearest. With the screw-terminal breakout (BOM 3.2) every wire lands in a labelled screw terminal instead of on a header pin.

### Tools
Multimeter with continuity beep, wire strippers, crimper for ferrules/fork terminals, small screwdriver. Optional: a **3-light receptacle tester** for the motor outlet (the multimeter can do the same checks; Part 7).

### Wire sizes

Every wire must be at least as heavy as the fuse ahead of it needs: the fuse protects the wire. The steps below repeat the size for each run.

| Run | Gauge | Wire | Ends | Part |
|---|---|---|---|---|
| **Mains (120V AC)** |||||
| Inlet → Dinkle L/N/⏚ buses → ALITOVE AC; motor path; earth wires (Part 7 rows E, L, N, M) | **16 AWG** (14 AWG also fits) | Black/white/green cores of 16/3 SJTW/SJOOW cord, 300V | 1.5mm² ferrules in DIN blocks, fuse holders and contactor; blue (16–14 AWG) forks on the ALITOVE; blue insulated female quick-disconnects on the outlet tabs | 2, 7 |
| Inlet's factory leads (BOM 1.1) | 18 AWG | As supplied | — | 2 |
| Coil circuit (Part 7 rows C1–C5) | **16 AWG**; 18 AWG ok (1A fuse) | Same cord cores, or other **300V-insulated** wire. Never speaker wire or LED cable. | 1.5mm² (16) / 1.0mm² (18) ferrules | 7 |
| E-stop NC #1, only if the e-stop is mounted off the box | 16 AWG | SJOOW, glands both ends (BOM 5.8) | ferrules | 5 |
| **5V power** |||||
| ALITOVE V+/V− → fuse-module input | **16 AWG** | 16/2 speaker wire (BOM 2.3) | Blue fork on the ALITOVE; 1.5mm² ferrule at the module. **Keep it short: no fuse protects this run.** | 2 |
| V1 → Pi | **22 AWG** | Micro-USB pigtail (BOM 3.1), 12". Don't lengthen it. | 0.5mm² ferrules | 2 |
| V2 → strip +5V / GND | **16 AWG** preferred, 18 AWG ok | 16/2 speaker wire, or two conductors of the 18 AWG LED cable (BOM 4.5) | 1.5mm² / 1.0mm² ferrules | 6 |
| V3 → Pixel Shifter; V4 → relay board DC+/DC− | **22–18 AWG** | Hookup wire, or LED-cable offcuts | 0.5mm² / 1.0mm² ferrules | 6, 7 |
| **Signal (3.3V / 5V, milliamps)** |||||
| Pi breakout → Pixel Shifter IN/GND, → relay IN, → 2.2kΩ pull-up; box-side leads to the M12 connectors | **22–18 AWG** | Hookup wire, or LED-cable offcuts | 0.5mm² / 1.0mm² ferrules in screw terminals | 3–7 |
| Box → performer button, index microswitch, e-stop NC #2 | **18 AWG** | 3-conductor LED cable (BOM 6.3); twisted pair preferred | — | 3–5 |
| Pixel Shifter OUT → 330Ω → strip DIN | **18 AWG** | Third conductor of the LED cable (BOM 4.5) | — | 6 |

- **Speaker wire and LED cable are 5V/3.3V only** (BOM "Use restrictions"). They never carry mains.
- Before committing to a size, test-fit one ferrule in each kind of terminal: the Pi breakout, relay board, Pixel Shifter and M12 connectors don't publish a wire range here. The fuse module takes 26–12 AWG on its outputs and 26–10 AWG on its inputs.
- 22 AWG hookup wire isn't in the BOM. 18 AWG LED-cable offcuts work for every 22–18 AWG run above, as long as they fit the terminal.

### Box layout (rough, not yet mocked up)

Interior about **12.5" × 9"**. The ALITOVE is about **8.5" × 4.5"**, with all its screw terminals (AC and DC) in one row across one short end. Check that on yours before drilling.

```
                          ← 4" →                   ← 8.5" →
               +----------------+---------------------------------+
               | RAIL 1 (120V)  | AC:  L  N  PE                   |
               | L#1 L#2 N#1 N#2|  ||                             |
IEC inlet =>   | PE#1 PE#2      |  ||      ALITOVE 5V 60A         |
               | MOTOR  COIL    |  ||      8.5" x 4.5"            |
               | fuse   fuse    |  ||      terminal end faces LEFT|
               |                |  ||      V ADJ pot reachable    |
               | RAIL 2         |  DC:  -V  +V                    |
               | +----------+   +---------------------------------+
               | |CONTACTOR |   | RAIL 3: [5V FUSE MODULE V1..V6] |
motor     =>   | |  LC1D09  |   |                                 |
outlet         | |          |   | RAIL 4:             +--------+  |
               | +----------+   |  [PIXEL SHIFTER]    |  Pi 3  |  |
               |                |                     | on DIN |  |
               | RAIL 5         |                     |breakout|  |
               | [RELAY BOARD]  |                     +--------+  |
               | COM NO | DC IN |                                 |
               |  120V  |  5V ->|                                 |
               +----------------+---------------------------------+
                 BOTTOM WALL: M12 connectors, strip-cable gland, Ethernet gland
```

- **Left 4" column = 120V.** Top to bottom it follows the current: rail 1 (Dinkle 120V L/N/PE buses + the two 120V fuse holders) next to the IEC inlet, rail 2 (contactor) next to the motor outlet, rail 5 (relay board) at the bottom, with its **COM/NO side facing the mains column** and its **DC/IN side facing right**.
- **Right = 5V.** The ALITOVE's terminal end faces the mains column: its **AC screws sit next to rail 1** and its **DC screws sit just above the 5V fuse module** (rail 3), so the unfused ALITOVE → module run is about 2". If the AC screws come out at the bottom of the row instead, flip the whole layout top-to-bottom.
- **Walls:** left wall = 120V only (inlet, motor outlet). Bottom wall = all low-voltage entries (M12s, strip-cable gland, Ethernet gland); connectors and glands facing down also shed water.
- **ALITOVE at the top**, so its heat rises away from the Pi (with the box mounted this edge up). Leave about ½" around it; don't block its fan or vents.
- **E-stop on the lid, over the mains column.** NC #1 (120V) stays on the mains side; only the 3.3V monitor pair crosses to the Pi. Check that the back of the e-stop clears the contactor (about 3.5" deep) with the lid shut, and leave hinge slack.
- **Before drilling:**
  - [ ] Confirm the ALITOVE's terminal layout (AC at the top of the row, DC at the bottom, or flip).
  - [ ] Measure the 5V fuse module and the Pi's DIN breakout; the 5V area is about 8.5" × 4.5".
  - [ ] Cardboard mock-up of the mains column. It's the tight spot: rail 1, the contactor (about 3" tall) and the relay carrier (about 1.9") use about 8" of the 9". Leave about ¾" beside each clamp for wire bends.
  - [ ] Check the e-stop's depth against the contactor with the lid shut.

### Software (once)
```bash
cd ~/parade-2026
bash scripts/pi-setup.sh     # installs lgpio/spidev, enables SPI, pins core_freq=250
sudo reboot                  # required after SPI is enabled
```
After the reboot, `ls /dev/spidev0.0` must exist.

The bench tool used in every test below:
```bash
.venv/bin/parade-hwcheck inputs                 # live view of all switches
.venv/bin/parade-hwcheck relay --seconds 3      # relay ON for 3 s, then off
.venv/bin/parade-hwcheck pixels test            # red, green, blue, white, chase
```

---

## Part 2 — Box power (IEC inlet → ALITOVE → Pi)

This powers the Pi, NeoPixels and relay board. The motor branch is added in Part 7, from the same inlet.

**Wire colours.** US building wire: hot **black**, neutral **white**, earth **green**. IEC cords: hot **brown**, neutral **blue**, earth **green/yellow**. Whatever you use, be consistent and label it.

1. [ ] Mount the fused/switched **IEC C14 inlet** (BOM 1.1) in the box wall. Fit a **T8A** 5×20mm slow-blow fuse, not the fuse that came with it (checklist §2).
2. [ ] Set the ALITOVE's **110V/220V selector to 110V**. Tape it so it can't be knocked.
3. [ ] Wire inlet **L → ALITOVE L**, inlet **N → ALITOVE N**, inlet **⏚ → ALITOVE ⏚**, in **16 AWG** (the SJTW/SJOOW cord cores; Part 7 "Wire list"), with blue (16–14 AWG) fork terminals on the ALITOVE.
   - The inlet's factory leads are 18 AWG. They're acceptable as-is: the T8A inlet fuse sits below their 10A cord rating (checklist §2).
   - Where a conductor has to split later (L, N and ⏚ also go to the motor outlet), put a rated splice point here now: the Dinkle **120V L, N and PE buses** on mains rail 1 (Part 7, "DIN terminal blocks" and "Wire list"). Wires L1, N1, E1 and L2, N2, E2 in that list are this step. Don't stack three wires under one screw.
4. [ ] If the enclosure is metal, bond it to the same earth point with **16 AWG** green wire, ending in a ring terminal on a star washer.
5. [ ] Cover the ALITOVE's AC terminals (BOM 1.4).
6. [ ] Clip the **fuse module** (BOM 2.1) onto its own 5V rail, away from the mains rails. DC side: ALITOVE **V+ → module input V+**, **V− → module input V−**, **16 AWG** (16/2 speaker wire, BOM 2.3). Keep this run short: no fuse protects it. The module has two of each input terminal; one of each is enough.
7. [ ] Re-fuse the module (it ships with 3A in every channel) and label each channel. Every load takes its + from **V_n** and its GND from the **V−** terminal beside it:
   - **V1 — Pi: 3A** → micro-USB pigtail (BOM 3.1; **22 AWG**, 0.5mm² ferrules, keep its 12" length) → Pi.
   - **V2 — NeoPixel strip: 5A** (wired in Part 6).
   - **V3 — Pixel Shifter: 1A** (wired in Part 6).
   - **V4 — Relay board: 1A** (wired in Part 7).
   - V5, V6: spare. Pull their fuses.
8. [ ] **Before first plug-in**, unplugged, with the multimeter on continuity:
   - Inlet L ↔ N, L ↔ ⏚, N ↔ ⏚: **no beep** (no shorts).
   - Inlet ⏚ ↔ ALITOVE ⏚ (and metal box): **beep**.
   - Module input V+ ↔ V−: **no beep**.
   - Each output V_n ↔ its V−: **no beep**.
9. [ ] Plug in, switch on. Set **V ADJ** so the Pi's input reads **≈ 5.1V** (checklist §2).

✅ **Pass:** the Pi boots, and the dashboard header shows a green **PWR OK** pill.

---

## Part 3 — Performer "ready" button (your #1)

**How it works:** a normally-open (NO) momentary button between **GPIO27** and **GND**. The Pi's internal pull-up holds the pin HIGH, and pressing pulls it LOW, which the app reads as ACTIVE. If the wire is cut, the button simply never reads as pressed, so a broken wire can't fake a "ready".

1. [ ] Identify the button's **NO** contacts with the multimeter: **no beep** at rest, **beep** while pressed. If it has three terminals (C / NO / NC), use **C** and **NO**. Ignore any LED terminals.
2. [ ] Run **18 AWG** cable (the LED cable, BOM 6.3) from the button to the box. Use an M12 panel connector at the box if you want it detachable (BOM 6.4; low voltage only).
3. [ ] Button terminal 1 → **GPIO27** (pin 13). Button terminal 2 → **GND** (pin 14). Any box-side leads (M12 → breakout): 22–18 AWG.
4. [ ] Config (already set in `config/default.yaml`):
   ```yaml
   - id: performer_button
     pin: 27
     pull: up
     active_low: true
     debounce_ms: 50
   ```
5. [ ] Test: `.venv/bin/parade-hwcheck inputs`.
   - At rest: `performer_button  GPIO27  HIGH  idle`.
   - Press: exactly **one** `low ACTIVE` line. Release: exactly **one** `HIGH idle` line.
   - Wiggle the cable for 30 s without pressing: **no lines**.

✅ **Pass:** one line per press and one per release, with nothing from wiggling.
**If a single press prints several lines:** raise `debounce_ms` (try 80).
**If lines appear on their own:** see "noisy input" in Part 8.

---

## Part 4 — Tabletop index microswitch (your #2)

**How it works:** the microswitch is wired through its **NC (normally-closed)** contact between **GPIO17** and **GND**. At rest the contact is closed and the pin reads LOW (idle). When the tabletop's cam presses the lever, the contact opens and the pull-up takes the pin HIGH (ACTIVE). The `stop_rotation_at_index` cue then switches the motor relay off. It runs on every index hit in RUNNING, regardless of the performer flag.

**Why NC here and NO on the performer button:** this switch is what stops the motor. With NC wiring, a cut or unplugged wire reads as "at index", so the motor gets switched off. With NO wiring, the same fault would leave the motor spinning with no automatic stop.

1. [ ] Identify the microswitch terminals with the multimeter. Usually marked **C** (common), **NO** and **NC**. **C ↔ NC** beeps at rest and goes silent when the lever is pressed. Use **C and NC**.
2. [ ] Mount it so a cam or bump on the rotating tabletop presses the lever once per revolution.
   - **Place the cam slightly before the desired stop position.** The motor coasts after power is cut (checklist §5, coast-down time).
   - The lever must stay pressed for **longer than `debounce_ms` (20 ms)**. A short blip is ignored as noise. At slow turntable speeds this is easy. If you ever see missed hits, lower `debounce_ms` or lengthen the cam.
3. [ ] **18 AWG** twisted pair (or two conductors of the LED cable, BOM 6.3) to the box. **C → GND** (pin 9), **NC → GPIO17** (pin 11).
   - Add a **2.2kΩ resistor from GPIO17 to 3.3V** (pin 1 or 17) at the box end. The V-153-1C25 is a 15A switch with contacts made for large currents, and the Pi's internal pull-up alone passes only ~0.07 mA through them, which such contacts can switch unreliably. 2.2kΩ passes ~1.5 mA.
4. [ ] Config (already set):
   ```yaml
   - id: rotation_index
     pin: 17
     pull: up
     active_low: false      # NC wiring: actuated (or cut wire) = HIGH = ACTIVE
     debounce_ms: 20
   ```
5. [ ] Test: `.venv/bin/parade-hwcheck inputs`.
   - At rest: `rotation_index  GPIO17  low  idle`.
   - Press the lever by hand: one `HIGH ACTIVE` line. Release: one `low idle` line.
   - Unplug the switch connector: `HIGH ACTIVE` (the fault reads as "stop"). Plug it back in: `low idle`.
   - Turn the tabletop slowly by hand through a full revolution: exactly one ACTIVE/idle pair.

✅ **Pass:** one ACTIVE/idle pair per revolution, and unplugging reads ACTIVE.

---

## Part 5 — Emergency-stop button (your #5, part 1: mounting + monitor)

**How it works:** the e-stop has **two separate normally-closed contact blocks**:

| Contact block | Circuit | Voltage | Job |
|---|---|---|---|
| **NC #1 — power** | In series with the motor's hot (Part 7) | Mains | **Cuts the motor.** Works with the Pi off, crashed or unplugged. This is the actual safety function. |
| **NC #2 — monitor** | GPIO22 ↔ GND | 3.3V | Tells the software: relays off, cues cancelled, dashboard shows EMERGENCY STOP, reset blocked until released. |

**Never** put mains and the 3.3V monitor on the same contact block. They must be separate blocks.

1. [ ] Confirm your e-stop has **two NC contact blocks**. Most 22mm e-stops accept clip-on extra blocks if yours has only one. **Schneider XB4BS8445** ships with 1 NC (terminals **1–2**, used as NC #1 for the coil circuit) and 1 NO (terminals 3–4, not used). Add a **ZBE102** NC block for NC #2 (monitor). Check each block with the multimeter: **beep** with the button out, **no beep** with it pressed in.
2. [ ] Mount the e-stop where the operator can reach it while watching the booth (checklist §5). Mounting it on the control box is simplest: NC #1 carries 120V and then never leaves the box. If it must be remote, use a yellow e-stop enclosure and 16 AWG mains-rated cable (e.g. 16/3 SJOOW) with glands at both ends (BOM 5.8), and never run NC #1 through the M12 connectors.
3. [ ] Wire **NC #2 (monitor)** only, for now, in **18 AWG** (LED cable, BOM 6.3; 22–18 AWG if it stays inside the box): one side → **GPIO22** (pin 15), other side → **GND** (pin 20).
4. [ ] Config (already set):
   ```yaml
   - id: estop_monitor
     pin: 22
     pull: up
     active_low: false     # contact opens when pressed (or wire cut) → HIGH → ACTIVE
   safety:
     estop_pin: estop_monitor
   ```
5. [ ] Test: `.venv/bin/parade-hwcheck inputs`.
   - Button out: `estop_monitor  GPIO22  low  idle`.
   - Press it: `HIGH ACTIVE`. Twist to release: `low idle`.
   - Unplug the monitor wire: `HIGH ACTIVE`.
6. [ ] Switch the app to the real input driver. In `config/default.yaml`:
   ```yaml
   hardware:
     gpio_driver: rpi
   ```
   then `sudo systemctl restart parade` and open the dashboard.
   - Button out → the system comes up in **SAFE**.
   - Press the e-stop → **EMERGENCY STOP** banner. Try **SAFE**: refused with "E-stop is pressed…". Release the e-stop → **SAFE** now works.

✅ **Pass:** pressing or unplugging trips EMERGENCY STOP, and reset works only after release.

> With `gpio_driver: rpi`, an **unwired** monitor contact reads as pressed, and the app stays in EMERGENCY STOP. That's deliberate. If you need to run the real inputs before the e-stop is wired, set `safety.estop_pin: null` temporarily, and put it back before the motor is connected.

---

## Part 6 — NeoPixel strip (your #4)

**How it works:** the strip is powered straight from the ALITOVE (5A fused branch). The Pi only sends data, on **GPIO10** (SPI), through a **level shifter** that turns the Pi's 3.3V signal into the 5V the strip needs.

```
ALITOVE ─[V2 5A]───────────────────────────────┬──────────── strip +5V
                                               ═╪═ 1000µF (− stripe to GND)
ALITOVE − ─────────────────────────────────────┴──┬───────── strip GND
                                                  │
Pi GPIO10 (pin 19) ──► Pixel Shifter IN ─► OUT ──[330Ω]───── strip DIN
Pi GND   (pin 25) ───► Pixel Shifter GND ─────────┘
                       Pixel Shifter power ← V3 (1A)
```

1. [ ] Find the strip's **input** end: the arrows printed on the strip point **away** from it, and the pads read **DIN** (not DOUT). Read the pad labels (**+5V / DIN / GND**). Don't trust wire colours; they vary between strips.
2. [ ] **Capacitor:** 1000µF across **+5V and GND** at the strip's input. The stripe on the capacitor marks **−**, which goes to GND. Backwards, it can burst.
3. [ ] **Power:** fuse-module **V2 (5A)** → strip **+5V**. The **V−** beside it → strip **GND**. **16 AWG** 16/2 speaker wire (BOM 2.3) preferred; 18 AWG (two conductors of the LED cable, BOM 4.5) is ok. If the far end looks dim or yellow at full white in step 8, switch to 16 AWG.
4. [ ] **Level shifter: Adafruit Pixel Shifter** (BOM 4.2). Wire it following the labels printed on the board:
   - Power and GND from fuse-module **V3 (1A)** and the V− beside it, in **22–18 AWG**. Same ALITOVE 5V as the strip, on its own fuse. If the strip's fuse blows while the shifter stays powered, the 330Ω resistor limits what leaks into the strip through DIN.
   - Data **in** ← Pi **GPIO10** (pin 19), 22–18 AWG.
   - GND ← also to a Pi **GND** pin (25). The Pi, shifter and strip must share ground.
   - Data **out** → **330Ω resistor** → strip **DIN**, on the LED cable's third conductor (**18 AWG**). Put the resistor near the strip end and keep this wire short.
5. [ ] Config: `pin: 10` is already set. Optionally cap current with `brightness: 0.6` (60% still looks bright and cuts current by roughly 40%).
6. [ ] Test: `.venv/bin/parade-hwcheck pixels test`.
   - Whole strip shows **red → green → blue → white**, then one orange pixel runs from the input end to the far end, then all off.
   - Red shows as green (or vice versa): the strip isn't WS2812B/GRB. Note what it actually is and stop.
   - First pixel flickers or shows random colours: data or ground wiring. Check the shifter, the shared GND and the resistor.
7. [ ] Switch the app to the real pixel driver: `hardware: pixel_driver: rpi`, then restart.
8. [ ] Run the **power stress test** (checklist §7). The **PWR** pill must stay green with the strip at full white.

✅ **Pass:** correct colours, a clean chase end to end, and PWR stays green at full white.

---

## Part 7 — Relay, motor outlet and e-stop power contact (your #3 and #5, part 2)

### Your plan, checked

> *Generator → IEC inlet on the box. Inlet feeds the 5V supply. Earth goes straight from the inlet to the motor outlet's earth. Hot goes through the relay.*

That's the right shape. Specifically:

- ✅ **Earth straight through, inlet → outlet.** Correct and required. Earth is **never** switched, fused, or run through the relay or e-stop.
- ✅ **Switch the hot, not the neutral.** Correct. **Neutral also runs straight through**, inlet → outlet.
- ✅ **Tap the 5V supply off the inlet ahead of the relay and e-stop.** The Pi stays powered when the motor is cut, so it can show the e-stop state and accept a reset.

Three additions (and, for your 300 W motor, a contactor; see "The motor" below):

1. **The e-stop's power contact (NC #1) goes in series in the same hot line**, ahead of the relay. Otherwise the e-stop depends on the Pi, which it must not (ADR-012).
2. **Use the relay's COM and NO terminals, never NC.** With NO, the motor is off whenever the relay isn't actively energised: Pi off, booting, crashed, relay board unpowered.
3. **Fuse the motor branch** separately, sized to the motor. A motor fault then blows its own fuse, not the one that keeps the Pi alive.

```
                                 IEC INLET (fused, switched)
GENERATOR 120V AC ─(GFCI)─ cord ─┤
                                 ├─ L ─┬─────────────────────────────────────────── ALITOVE L
                                 │     └─[MOTOR FUSE]─[E-STOP NC #1]─[RELAY COM→NO]── outlet L
                                 ├─ N ─┬─────────────────────────────────────────── ALITOVE N
                                 │     └─────────────────────────────────────────── outlet N
                                 └─ ⏚ ─┬─────────────────────────────────────────── ALITOVE ⏚ (+ metal box)
                                       └─────────────────────────────────────────── outlet ⏚
```

### The motor: Bemonoc 300W 110V AC gear motor + speed controller

Listing: [Amazon B0GSYZCTPM](https://www.amazon.com/dp/B0GSYZCTPM). What the listing states: **110V AC, 300 W, 45 RPM, reversible gear motor, with speed controller.** The controller plugs into the wall, and the motor plugs into the controller.

Still to read off the **labels** when it arrives (the listing doesn't show them):
- Motor nameplate: rated current (A) ______ capacitor value ______ brake? ______
- Controller label: input current / fuse ______ plug type ______
- Coast-down time with the booth loaded (step 22) ______ s

**Your plan:** the controller's power cord plugs into the box's motor outlet. The controller is left switched **on** with the speed set, so whenever the outlet is live the motor runs. The e-stop and relay decide whether the outlet is live. That's a good plan, and it switches in the right place: **the controller's mains input, never the wires between the controller and the motor** (those carry the controller's regulated output plus a speed-sensor cable on most AC gear-motor controllers).

**This motor needs Design B (contactor).** 300 W at 110 V is at least 2.7 A running (300 ÷ 110, before efficiency and power factor, so the real figure is higher). An induction motor starting under load draws several times that. Hobby relay boards and 22mm e-stop contact blocks aren't meant to switch that directly. A contactor is.

- **Design A (relay switches the motor directly):** not for this motor. The board's **HLS8L-DC5V-S-C** relay is marked 15A 120VAC, but its datasheet gives no motor (HP) rating, and the board's traces and screw terminals aren't rated at all. The Design A drawing above is kept only because it shows the earth, neutral and 5V tap, which are the same in both designs.
- **Design B (relay drives a contactor):** the contactor's main contact switches the outlet's hot. The e-stop NC #1 and the relay's COM→NO sit in series in the contactor's **coil** circuit, so they only carry the coil's small current.

```
INLET L ─┬──────────────────────────────────────────────────────── ALITOVE L
         ├─[1A FUSE]──[E-STOP NC #1]──[RELAY COM→NO]──► contactor coil A1
         │                                               contactor coil A2 ──► N
         └─[MOTOR FUSE]──[CONTACTOR main contact]────────────────► outlet L ──► speed controller ──► motor
INLET N ──────────────────────────────────────────────────────────► ALITOVE N, coil A2, outlet N
INLET ⏚ ──────────────────────────────────────────────────────────► ALITOVE ⏚, metal box, outlet ⏚
```

The e-stop still works without the Pi: pressing it drops the coil, and the contactor opens. The relay and e-stop never carry motor current.

**Contactor (BOM 5.2): Schneider LC1D09G7**, 120VAC coil, rated ½ HP at 115V single-phase (the motor is 300 W ≈ 0.4 HP). Pole 1 switches the hot, pole 2 the neutral.

**Motor fuse (BOM 1.2, in a DK4-TF holder, BOM 1.10):** **time-delay (slow-blow)**, sized just above the controller/motor rated current from the labels. It must also be **below the inlet fuse**, so a motor fault blows the motor fuse and the Pi stays up. Expected **T5A or T6.3A**; stay at or below T6.3A in the 5×20 holder. If the label calls for more, stop and re-plan (inlet to T10A, motor T8A).

### Wire list: generator to motor outlet with the Schneider LC1D09G7

Every mains wire in the box, in build order. Box **unplugged**.

**Wire:** **16 AWG** stranded for everything here: the black/white/green cores of a **16/3 SJTW/SJOOW copper extension cord** (300V insulation), used inside the box only. 14/3 also fits every terminal. Colours: **black = hot (L)**, **white = neutral (N)**, **green = earth (⏚)**. The coil circuit (C1–C5) carries only the 1A-fused coil current, so 18 AWG is also ok there, but only in 300V-insulated wire. Ferrules on every stranded end that goes into a screw clamp (1.5mm² for 16 AWG, 1.0mm² for 18 AWG). Blue (16–14 AWG) fork terminals on the ALITOVE's screws.

**Names used below.** Every label points to one physical part. Nothing on this list touches the 5V side: the **5V fuse module** is a separate rail and never carries 120V.

| Name in this guide | What it physically is | Where |
|---|---|---|
| **IEC inlet** | The fused, switched C14 power socket in the box wall (BOM 1.1). The generator cord plugs in here. Three tabs on the back: **L**, **N**, **⏚**. | Box wall |
| **120V L bus**: blocks **L #1**, **L #2** | Two plain Dinkle DK2.5N blocks joined by a jumper, labelled **L**. One hot connection with 4 clamps. | Mains rail 1 |
| **120V N bus**: blocks **N #1**, **N #2** | Two plain Dinkle DK2.5N blocks joined by a jumper, labelled **N**. One neutral connection with 4 clamps. | Mains rail 1 |
| **120V PE bus**: blocks **PE #1**, **PE #2** | Two **green-yellow** Dinkle PE blocks, joined through the metal rail. One earth connection with 4 clamps. | Mains rail 1 |
| **120V motor fuse holder** | Dinkle DK4-TF, 5×20 slow-blow fuse sized from the motor label (T5A/T6.3A) | Mains rail 1 |
| **120V coil fuse holder** | Dinkle DK4-TF, **T1A** | Mains rail 1 |
| **Contactor** | Schneider LC1D09G7. Terminals 1/L1, 2/T1, 3/L2, 4/T2, A1, A2. | Mains rail 2 |
| **Relay board, 120V side** | The HLS8L's **COM / NO / NC** screw terminals. (Its other side, DC+/DC−/IN, is 5V.) | Between the mains and 5V areas |
| **E-stop NC #1** | The e-stop's factory NC block, terminals **1** and **2** | Box lid/wall |
| **ALITOVE AC terminals** | The 5V supply's **L**, **N**, **⏚** input screws | — |
| **Motor outlet** | SS-6B NEMA 5-15R: **hot tab** (narrow slot), **neutral tab** (wide slot), **earth tab** (round hole) | Box wall |

Each Dinkle block has a **top clamp** and a **bottom clamp**, joined inside. On a fuse holder, call the top clamp **in** and the bottom clamp **out**. The wire list below says which clamp every wire lands in, and each clamp takes one wire:

| Block | Top clamp | Bottom clamp |
|---|---|---|
| 120V L bus, **L #1** | L1 (from IEC inlet L) | L2 (to ALITOVE L) |
| 120V L bus, **L #2** | M1 (to motor fuse holder) | C1 (to coil fuse holder) |
| 120V N bus, **N #1** | N1 (from IEC inlet N) | N2 (to ALITOVE N) |
| 120V N bus, **N #2** | M4 (to contactor 3/L2) | C5 (from contactor A2) |
| 120V PE bus, **PE #1** | E1 (from IEC inlet ⏚) | E2 (to ALITOVE ⏚) |
| 120V PE bus, **PE #2** | E3 (to motor outlet earth tab) | E4 (to metal box, if metal) |

**Wire list.** The **#** column is just the wire's name: E = earth, L = hot feed, N = neutral feed, M = motor power, C = contactor coil. (Wire **L1** lands *on* block **L #1**; don't mix the two up.)

| # | From | To | Colour | Notes |
|---|---|---|---|---|
| **Earth** |||||
| E1 | IEC inlet **⏚ tab** | 120V PE bus, **PE #1 top** | green | the earth coming in |
| E2 | 120V PE bus, **PE #1 bottom** | ALITOVE AC **⏚** screw | green | fork terminal |
| E3 | 120V PE bus, **PE #2 top** | Motor outlet **earth tab** (round hole) | green | never through a fuse, switch or contactor |
| E4 | 120V PE bus, **PE #2 bottom** | Metal box / metal panel | green | only if metal; ring terminal + star washer |
| **Hot feed** |||||
| L1 | IEC inlet **L tab** (after its switch/fuse) | 120V L bus, **L #1 top** | black | the hot coming in |
| L2 | 120V L bus, **L #1 bottom** | ALITOVE AC **L** screw | black | the Pi's supply: always live, ahead of the e-stop. Fork terminal. |
| **Neutral feed** |||||
| N1 | IEC inlet **N tab** | 120V N bus, **N #1 top** | white | the neutral coming in |
| N2 | 120V N bus, **N #1 bottom** | ALITOVE AC **N** screw | white | fork terminal |
| **Motor power path** |||||
| M1 | 120V L bus, **L #2 top** | 120V **motor fuse holder, in** | black | slow-blow; size from the motor/controller label |
| M2 | 120V **motor fuse holder, out** | Contactor **1/L1** | black | |
| M3 | Contactor **2/T1** | Motor outlet **hot tab** (narrow slot) | black | switched hot |
| M4 | 120V N bus, **N #2 top** | Contactor **3/L2** | white | |
| M5 | Contactor **4/T2** | Motor outlet **neutral tab** (wide slot) | white | switched neutral |
| — | Contactor 5/L3, 6/T3 | — | — | unused pole |
| **Coil circuit** (carries only the coil current) |||||
| C1 | 120V L bus, **L #2 bottom** | 120V **coil fuse holder (T1A), in** | black | |
| C2 | 120V **coil fuse holder, out** | **E-stop NC #1**, terminal **1** | black | XB4BS8445: its NC block, marked **1–2** |
| C3 | **E-stop NC #1**, terminal **2** | Relay board, 120V side, **COM** | black | 18 AWG (300V-insulated) ok if 16 won't fit the relay terminal |
| C4 | Relay board, 120V side, **NO** | Contactor **A1** | black | **NO**, never NC |
| C5 | Contactor **A2** | 120V N bus, **N #2 bottom** | white | |

Then the low-voltage side of the relay board (Part 7 step 1): **DC+** ← fuse module V4 (1A), **DC−** ← the V− beside it, **IN** ← GPIO18.

**Checks before plugging in** (multimeter on continuity, e-stop pulled out, contactor released):
- Inlet ⏚ ↔ outlet earth tab, and inlet ⏚ ↔ ALITOVE ⏚: **beep**.
- Inlet L ↔ outlet hot tab, inlet N ↔ outlet neutral tab: **no beep** (contactor open).
- Inlet L ↔ contactor A1: **no beep**. Short the relay board's COM–NO with a clip lead: **beep**. Also press the e-stop with the clip lead still on: **no beep**.
- L ↔ N ↔ ⏚ at the inlet: **no beep** between any pair. (The ALITOVE's input may read a few hundred kΩ to MΩ between L and N; that's normal. A beep is a short.)

Then run the powered tests, steps 11–23.

### DIN terminal blocks (Dinkle kit): how they go together

**Pieces.** A **DK2.5N** block is a thin slice with a screw clamp at the top and the bottom, joined inside by one metal strip, so one block connects two wires. Each block is open on one side; the next block's closed side covers it, and an **end cover** closes the last one. A **jumper** (DSS2.5N) is a metal comb pressed into the blocks' centre slots to join neighbouring blocks: two jumpered blocks = one connection point with four clamps. **PE blocks** (green-yellow) grip the metal rail, which joins them to each other. **End brackets** clamp the row in place.

1. [ ] Screw two 35mm rails to the back panel on the mains side of the box: **mains rail 1** for the buses and the two 120V fuse holders, **mains rail 2** for the contactor (one 4" rail is too short for everything; BOM "Layout").
2. [ ] On mains rail 1, snap on, left to right, all facing the same way: `[bracket] [L #1][L #2] [cover] [N #1][N #2] [cover] [PE #1][PE #2] [motor fuse holder] [coil fuse holder] [bracket]`. On mains rail 2: the contactor, with a bracket each side. Hook the top edge over the rail lip and press the bottom until it clicks. Remove with a flat screwdriver in the release slot. Tighten the PE blocks' foot screw if they have one, and the brackets.
3. [ ] Cut two 2-prong pieces off the jumper with side cutters. Press one fully into the L pair's centre slots, the other into the N pair's.
4. [ ] Label the groups **120V L**, **120V N**, **120V PE**, and each block's number (#1, #2). Label the fuse holders **MOTOR** and **COIL 1A**.
5. [ ] Meter check before wiring: L #1 ↔ L #2 **beep**, N #1 ↔ N #2 **beep**, any L ↔ any N **silent**, PE #1 ↔ PE #2 ↔ rail **beep**.
6. [ ] Landing each wire: strip to the length printed on the block or its paperwork, crimp a **ferrule**, back the screw out a few turns, push the ferrule **into** the clamp's metal box (not beside it, not under the screw head) until the insulation meets the plastic, tighten firmly, **tug hard**. One wire per clamp.
7. [ ] The earth never relies on the rail alone: the inlet's earth wire (E1) lands directly on **PE #1 top**, and a metal box gets its own wire (E4) from **PE #2 bottom**.

### Wiring steps (box unplugged)

1. [ ] **Relay board low-voltage side:**
   - Trigger jumper set to **H** (high-level trigger). Config: `active_low: false`.
   - **DC+/VCC** ← fuse-module **V4 (1A)**. **DC−/GND** ← the **V−** beside it. **22–18 AWG.**
   - **IN** ← Pi **GPIO18** (pin 12), 22–18 AWG.
2. [ ] **Bench-test the relay before any mains is connected to it:** `.venv/bin/parade-hwcheck relay --seconds 3`.
   - It clicks on and the board LED lights for 3 s, then it clicks off.
   - With the multimeter on continuity across **COM–NO**: **beep** only during those 3 s.
   - `sudo reboot` and watch: the relay must stay **off** the whole time the Pi boots (checklist §5).
3. [ ] **Motor outlet (SS-6B snap-in NEMA 5-15R, 15A 125V):**
   - Cut the panel hole to the size in the listing/datasheet, and check the panel thickness is within the range the snap-in clips are made for. Too thin and it rattles loose; too thick and it won't latch.
   - Its terminals are **spade tabs**. Crimp **fully insulated female quick-disconnects** (blue, 16–14 AWG) onto **16 AWG**, sized to the tabs (usually 6.3mm / 0.250"; measure or check the listing).
   - **Identify each tab with the meter** before wiring. Push a stiff wire or probe into a slot, then find the tab that beeps: **narrow slot = hot**, **wide slot = neutral**, **round hole = earth**. Mark the tabs with a marker.
   - Push each connector fully onto its tab and tug-test it. Add heat-shrink or insulating boots if the connectors aren't fully insulated.
4. [ ] **Earth (E3):** 120V PE bus **PE #2 top** → motor outlet **earth tab** (round hole).
5. [ ] **Neutral (M4, M5):** 120V N bus **N #2 top** → contactor **3/L2**. Contactor **4/T2** → motor outlet **neutral tab** (wide slot).
6. [ ] **Hot, motor path (M1–M3):** 120V L bus **L #2 top** → 120V **motor fuse holder, in**. Motor fuse holder **out** → contactor **1/L1**. Contactor **2/T1** → motor outlet **hot tab** (narrow slot).
   - Schneider LC1D09G7: pole 1 (**1/L1 → 2/T1**) carries the hot as above. Pole 2 (**3/L2 → 4/T2**) carries the neutral, splice → 3/L2 → 4/T2 → outlet **N**, so the outlet is fully dead when off. Pole 3 (5/L3–6/T3) is unused. Coil terminals are **A1/A2**. (HCH8s-25: same idea, terminals 1→2 and 3→4.) Use ferrules on stranded wire in the screw clamps.
6b. [ ] **Coil circuit (C1–C5):** 120V L bus **L #2 bottom** → 120V **coil fuse holder (T1A), in**. Coil fuse holder **out** → **e-stop NC #1 terminal 1**. E-stop **terminal 2** → relay board **COM**. Relay board **NO** → contactor **A1**. Contactor **A2** → 120V N bus **N #2 bottom**. A coil suppressor (BOM 5.3) is optional.
7. [ ] Keep mains wiring physically apart from the GPIO and 5V wiring. Cable-tie it to its own side of the box. The relay board carries both, so route its mains wires away from the IN/VCC side.
8. [ ] Strain relief and glands on every cable that leaves the box. Cover all exposed mains terminals.

### Tests

**Unplugged (continuity, multimeter):**
9. [ ] Inlet ⏚ ↔ outlet ⏚: **beep**. (Earth runs straight through, never switched.)
10. [ ] Inlet L ↔ outlet L: **no beep**. Inlet N ↔ outlet N: **no beep**. No beep between any two of L, N, ⏚ at the outlet. (Both L and N run through the contactor's normally-open poles — no continuity until the coil is energised.)

**Powered, nothing plugged into the motor outlet:**
11. [ ] Plug the box into a **GFCI-protected** generator outlet (many portable generators have them; otherwise use an inline GFCI cord). Mains, a float, weather and people are exactly what GFCIs are for.
12. [ ] Relay off: the motor outlet is **completely dead** (the 2-pole contactor opens hot and neutral). A receptacle tester shows **no lights**; a multimeter on AC volts reads **0V** between every pair of holes.
13. [ ] `.venv/bin/parade-hwcheck relay --seconds 30` (you'll hear the contactor clunk). While it's on:
    - **Receptacle tester:** shows **correct wiring**.
    - **Or multimeter** (AC volts, meter rated CAT II 300V or better, one hand, fingers behind the probe guards):

      | Probes in | Should read |
      |---|---|
      | narrow slot ↔ wide slot (hot ↔ neutral) | **~120V** |
      | narrow slot ↔ round hole (hot ↔ earth) | **~120V** |
      | wide slot ↔ round hole (neutral ↔ earth) | **~0V** |

    - Hot↔earth ~0V and neutral↔earth ~120V: L and N are swapped. Hot↔earth also ~0V: earth is disconnected. Fix before continuing.
    - After the 30 s the outlet goes dead again (0V everywhere).

**Stand-in load: a plain lamp plugged into the motor outlet:**
14. [ ] `parade-hwcheck relay --seconds 10`: lamp lights, then goes off.
15. [ ] Run it again and **press the e-stop** while the lamp is lit: the lamp goes out **immediately**, and the tool prints `E-stop pressed: relay off`. Release the e-stop: the lamp stays out. (The bench tool also refuses to start while the e-stop is pressed.)
16. [ ] Unplug the Pi's micro-USB with the lamp lit: the lamp goes out (relay drops). Plug the Pi back in.
17. [ ] Switch the app to the real relay driver: `hardware: relay_driver: rpi`, then restart.

**Speed controller setup (before plugging it into the box):**
18. [ ] Plug the controller into a wall outlet with the motor attached (no booth load). Set **direction** and **speed** for the show. Mark the knob position and the switch settings with a paint pen or tape; a bumped knob changes the show.
19. [ ] **Auto-start test.** Leave the controller's switch **ON**, pull its plug from the wall, then plug it back in. The motor must start **by itself**. Note any soft-start delay ______ s.
    - If it won't restart without a button press, this plan doesn't work with this controller. Stop here and tell me what it does.
20. [ ] Never flip the direction switch while the motor is turning. Stop it, wait for it to stop completely, then flip.

**Motor on the box:**
21. [ ] Plug the controller into the box's motor outlet, with the tabletop clear and the e-stop in reach. `parade-hwcheck relay --seconds 3`: the contactor clunks, the motor runs about 3 s (minus any soft-start) and stops.
22. [ ] Run it again and press the e-stop mid-run. Time the **coast-down** with the booth loaded and record it above. A 45 RPM gearbox usually stops quickly. If it doesn't, move the index cam earlier (Part 4).
23. [ ] Watch the **PWR** pill on the dashboard while the motor starts. It must stay green; a dip means the motor start is sagging the generator or the wiring.

✅ **Pass:** the e-stop and a Pi power loss both stop the motor on their own, and GPIO18 switches it cleanly on and off.

---

## Part 8 — Whole-system test

Run this with all five devices wired and all drivers set to `rpi`:
```yaml
hardware:
  gpio_driver: rpi
  relay_driver: rpi
  pixel_driver: rpi
```

1. [ ] `sudo systemctl restart parade`, then `journalctl -u parade -f`. Look for `RPi relay driver started (all off)`, `RPi GPIO started …` with every input `idle`, and `RPi pixel driver started`.
2. [ ] Dashboard: SAFE → READY → RUNNING.
3. [ ] Performer button → the log shows `GPIO performer_button → ACTIVE` and cue **Performer Ready**.
4. [ ] Start the motor (see "open item" below), let the tabletop reach the index → the relay drops (**Stop Rotation at Index**) and **Run Core Animation** starts.
5. [ ] Motor running → press the e-stop: the motor stops, the dashboard shows **EMERGENCY STOP**, and the relay shows off. Release it, return to SAFE, and the motor **does not** restart.
6. [ ] RUNNING with the motor on → click **SAFE** or **PAUSED**: the relay drops.
7. [ ] `sudo systemctl stop parade` with the motor running: the relay drops.
8. [ ] Close the box, run 20+ minutes, and check the **PWR** pill and temperature (checklist §7).

**Open item: what starts the motor?** The index switch stops it, but no cue turns the relay **on** yet. For bench tests and setting the speed controller, switch it on by hand in **MANUAL** mode (Manual tab); note the index switch does not stop it there. Once you decide the trigger (performer button? an operator button?), add this action to that cue in the dashboard's cue builder:
```yaml
- type: set_relay
  relay: phone_booth_rotation
  state: true
```
The app refuses to switch the relay on unless the state is RUNNING. Turning it off always works.

### Noisy input (false triggers in the log)
- Twisted pair for every switch run. Keep switch cables away from the motor and mains cables.
- Add an external **4.7–10kΩ pull-up** from the GPIO terminal to **3.3V** (pin 1 or 17) at the box end (BOM 6.5).
- Optionally add **100nF** from the GPIO terminal to GND at the box end (BOM 6.5).
- Raise `debounce_ms`, but keep it shorter than the index cam's press time.
