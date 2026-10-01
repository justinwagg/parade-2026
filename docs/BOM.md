# Control Box Bill of Materials

Parts for the control-box build in [WIRING_GUIDE.md](WIRING_GUIDE.md) (step by step) and [HARDWARE_SETUP_CHECKLIST.md](HARDWARE_SETUP_CHECKLIST.md) (background). Tools (multimeter, crimpers, soldering iron) are not listed except where a test depends on them.

**Status key:** **Have** (on hand) · **Ordered** · **Buy** (still needed) · **Optional** · **Not needed** (kept for the record).

_Last reconciled: 2026-09-27._

---

## Still to buy

- **120V wire:** a **16/3 (or 14/3) SJTW/SJOOW, UL-listed, copper (not CCA)** extension cord, stripped for its black/white/green cores (300V insulation). Inside the box only. (1.9)
- **1000µF ≥10V capacitor** for the strip, if not in hobby stock. (4.3)
- **Contactor coil suppressor: Schneider LAD4RCU**, or a ~150VAC MOV as a stopgap. Stops the NeoPixel glitch when the contactor switches. (5.3)
- **Heat-shrink**, if out, for the outlet's spade connectors. (7.4)
- **Motor fuse:** no purchase expected. Pick **T5A or T6.3A** from the fuse kit once the motor/controller label (or a measured running current) is known. (1.2)
- Optional: 22 AWG stranded hookup wire for the Pi-side signal runs (18 AWG LED-cable offcuts work if they fit the terminals; WIRING_GUIDE Part 1 "Wire sizes"), 3-light receptacle tester (1.7), Kill A Watt-style meter (5.10), inline GFCI cord if the generator has no GFCI outlets (1.8).

## Use restrictions

- **5V / 3.3V only, never 120V:** 16/2 speaker wire, 18 AWG LED cable, M12 aviation connectors, 7-position brass bus bar, DIN fuse distribution module (2.1), DaierTek blade fuse block (spare).
- **PC817 optocoupler boards:** not for NeoPixel data (far too slow).
- **JQC3F-03VDC-C 3.3V relay modules:** spares. The HLS8L 5V board is the one in the design.
- **15A / 20A fuses** from the 5×20 kit: discard. Nothing in this box takes them.
- **Layout:** the 4" DIN rails are too short for one row. Mains rail 1: terminal blocks + 2 fuse holders. Mains rail 2: contactor. Relay board on its own rail at the mains/5V boundary. 5V fuse module, Pi breakout and Pixel Shifter on the 5V side. Keep 5V parts physically apart from the mains rails. Drawing: WIRING_GUIDE Part 1 "Box layout".

---

## 1. Mains (120V AC)

| # | Part | Details | Qty | Status | Guide |
|---|---|---|---|---|---|
| 1.1 | IEC C14 inlet, fused + switched, 10A 250V | 3-pack with 18 AWG leads. Replace the included fuse with **T8A**. Identify the L/N/⏚ output tabs with the meter before wiring. | 1 (+2 spare) | Have | Part 2 |
| 1.2 | 5×20mm slow-blow (T) 250V ceramic fuses | **T8A** (inlet, have) + assortment kit 1–20A: **T1A** coil circuit, **T5A/T6.3A** motor (from label or measured amps). | — | Have | Part 7 |
| 1.3 | Generator cord | Amazon Basics 25 ft NEMA 5-15P → C13, 18 AWG, UL. Indoor cord: route it away from water and foot traffic, or swap for SJTW/SJOOW outdoor cord. | 1 | Have | Part 7 |
| 1.4 | ALITOVE AC terminal cover | Heat-shrink boots or a clip-on cover, if it didn't ship with one. | 1 set | Buy if missing | Part 2 |
| 1.5 | Ring / fork / spade crimp terminals | 280-pc kit (2.8/4.8/6.3mm spades, ring, fork). | 1 kit | Have | Parts 2, 7 |
| 1.6 | Dinkle DIN terminal block kit #1 | 20 × DK2.5N, DK2.5N-PE ground blocks, DSS2.5N-10P jumper, end covers, end brackets. L = 2 blocks + jumper, N = 2 blocks + jumper, PE = 2 PE blocks. Count PE blocks on arrival: **2 needed**. | 1 | Have | Part 7 "DIN terminal blocks" |
| 1.6b | Neutral bar | Superseded by the Dinkle N blocks. | 1 | Have (spare) | — |
| 1.6c | Ferrule crimper kit | Ratchet crimper + 1800 ferrules, 23–7 AWG. Ferrules on every stranded wire in a screw clamp. | 1 | Have | Part 7 |
| 1.7 | 3-light receptacle tester | A multimeter does the same checks (Part 7 steps 12–13). | 0–1 | Optional | Part 7 |
| 1.8 | Inline GFCI cord | Only if the generator's 120V outlets aren't GFCI. | 0–1 | Buy if needed | Part 7 |
| 1.9 | 120V wire | Cores of a 16/3 (or 14/3) SJTW/SJOOW copper extension cord: black = L, white = N, green = ⏚. | ~10 ft each | **Buy** | Part 7 wire list |
| 1.10 | DIN fuse holders, Dinkle DK4-TF(5X20) + DK4C-TF covers | UL, 300V, 16A. 2 used on mains (motor, coil); 3 spare. | 5 | Have | Part 7 |
| 1.11 | DIN rail, 35mm aluminium, 4" | Two for mains (blocks + fuses; contactor), others for Pi/5V parts. | 6 | Have | Part 7 |

## 2. 5V distribution

| # | Part | Details | Qty | Status | Guide |
|---|---|---|---|---|---|
| 2.1 | 6-channel DIN-rail blade fuse distribution module | 0–32V DC, 30A input, ATO/ATC fuses up to 10A per channel, Dinkle DIN carrier. Inputs: 2 × V+, 2 × V− (7.62mm, M3). Outputs: a **V_n + V−** pair per channel (5.0mm, M2.5; try a 16 AWG ferrule first). **5V only.** Ships with 3A in every channel: re-fuse per Part 2 step 7. Blown-fuse LED lights only with a load connected; may be dim at 5V. Measure its length against the 4" rail. | 1 | Have | Part 2 |
| 2.1b | DaierTek 12-way ATC/ATO blade fuse block | Superseded by 2.1. | 1 | Have (spare) | — |
| 2.2 | Blade fuses (ATO/ATC): **3A** (Pi), **5A** (strip), **1A** (Pixel Shifter), **1A** (relay board) | | + spares | Have | Part 2 |
| 2.3 | 5V wiring | 16/2 speaker wire: ALITOVE → fuse module, fuse module → strip. | 25 ft | Have | Parts 2, 6 |

## 3. Pi

| # | Part | Details | Qty | Status | Guide |
|---|---|---|---|---|---|
| 3.1 | Micro-USB power pigtail | 22 AWG, 12". Keep it short; set the ALITOVE V ADJ so the Pi reads ≈ 5.1V. | 6 | Have | Part 2 |
| 3.2 | DIN screw-terminal breakout for the Pi | Field wires go into screw terminals, not Dupont jumpers. | 1 | Have | Parts 3–7 |
| 3.3 | DIN PCB carriers (C45 adapters, 47×72mm carrier) | For the relay board and Pixel Shifter. | 11 | Have | Parts 6, 7 |
| 3.4 | Pi 3 heatsinks | Only if the closed-box test runs warm. | 1 | Optional | Part 8 |
| 3.5 | Spare high-endurance microSD | Backup image of the finished card. | 1 | Buy (before show day) | Checklist §8 |

## 4. NeoPixels

| # | Part | Details | Qty | Status | Guide |
|---|---|---|---|---|---|
| 4.1 | Adafruit 5163 Ultra Bright 4W RGBW NeoPixel, warm white ~3000K | Chainable modules, JST SM 3-pin each end (pinout differs from other NeoPixel strips: find the data wire with the meter). Config: `strip_type: SK6812RGBW`, `color_order: RGBW`. Up to **0.8 A each** at full: the 5A V2 fuse covers ~6 at full white; inject 5V at the far end too. 6 wired; `count` still 50 until the rest are added. | 6+ | Have | Part 6 |
| 4.2 | Adafruit Pixel Shifter (74HCT2G34) | 3.3V → 5V data. Power from the strip's 5V; GND shared with Pi and strip. | 2 (1 spare) | Have | Part 6 |
| 4.3 | 1000µF ≥10V electrolytic | Across the strip's +/− at its input; mind polarity. | 1 | Buy if not in stock | Part 6 |
| 4.4 | 330Ω resistor | Data line, near the first pixel. | 1 | Have (hobby stock) | Part 6 |
| 4.5 | 18 AWG 3-conductor LED cable | Box → strip (5V, GND, data). | 100 ft | Have | Part 6 |

## 5. Motor circuit

**Motor:** Bemonoc 300 W 110V AC reversible gear motor, 45 RPM, with speed controller ([B0GSYZCTPM](https://www.amazon.com/dp/B0GSYZCTPM)). The controller plugs into the box's motor outlet. The outlet is switched by a contactor whose coil runs through the e-stop and the Pi's relay (Part 7, Design B). **Still needed from the labels:** rated current (→ motor fuse), and whether the controller auto-starts when power is applied (Part 7 step 19).

| # | Part | Details | Qty | Status | Guide |
|---|---|---|---|---|---|
| 5.1 | E-stop: Schneider XB4BS8445 | 40mm mushroom, push-turn. Ships 1NC (terminals **1–2**, = NC #1, coil circuit) + 1NO (3–4, unused). | 1 | Have | Parts 5, 7 |
| 5.1b | Schneider ZBE102 NC block | Clips into the free collar position: NC #2, e-stop monitor on GPIO22. | 1 | Have | Part 5 |
| 5.2 | Contactor: Schneider LC1D09G7 | UL, **½ HP at 115V single-phase**, **120VAC coil** (G7), DIN rail. Pole 1 (1/L1→2/T1) = hot, pole 2 (3/L2→4/T2) = neutral, pole 3 unused, coil A1/A2. Check the coil label says 120V and the printing looks genuine. | 1 | Have | Part 7 |
| 5.3 | Coil suppressor: **Schneider LAD4RCU** (RC, 110–240VAC) | Clips onto the LC1D09G7's coil terminals **A1/A2**. The coil's switching spike glitches the first NeoPixels (confirmed 2026-10-01: no glitch with the e-stop holding the coil off); the pixel driver's 30 ms resend hides it for now. Stopgap from a local shop: a **~150VAC MOV** (e.g. Littelfuse V150LA10A), or **100Ω ½W + 0.1µF X2 275VAC** in series, across A1/A2. | 1 | Buy | Part 7 |
| 5.4 | Relay board: HLS8L-DC5V-S-C | High-level trigger (H), **COM→NO**, VCC from fuse-module channel V4 (1A). Switches only the contactor coil (the relay has no motor rating). Pass the 3.3V bench test. | 1 (+2 spare) | Have | Part 7 |
| 5.5 | Motor outlet: SS-6B NEMA 5-15R snap-in | 15A 125V, spade tabs. Check the panel thickness for the snap-in clips. Identify the hot/neutral/earth tabs with the meter. | 1 (+1 spare) | Have | Part 7 |
| 5.6 | Outlet connectors | 6.3mm female spades from the crimp kit, with heat-shrink over each so no metal shows. | 3 | Have | Part 7 |
| 5.7 | Flyback diode / RC snubber on motor | AC motor via its own controller. | — | Not needed | — |
| 5.8 | Separate e-stop enclosure + mains-rated cable | **Only if** the e-stop mounts away from the box: yellow 22mm single-hole box, SJOOW cable, glands both ends (NC #1 carries 120V; never through the M12 connectors). On the box itself: not needed. | 0–1 | Decide placement | Part 5 |
| 5.10 | Kill A Watt-style meter | Only if the motor label doesn't give amps. | 0–1 | Optional | Part 7 |

## 6. Inputs

| # | Part | Details | Qty | Status | Guide |
|---|---|---|---|---|---|
| 6.1 | Index microswitch: V-153-1C25 SPDT | Wire **C + NC**. Add a **2.2kΩ** pull-up GPIO17 → 3.3V (its contacts are made for high current and switch unreliably at the Pi's tiny pull-up current alone). | 1 | Have | Part 4 |
| 6.2 | Performer button (momentary, NO) | | 1 | Have | Part 3 |
| 6.3 | Switch cable | 18 AWG 3-conductor LED cable (twisted pair preferred for long runs). | — | Have | Parts 3, 4 |
| 6.4 | M12 4-pin panel connectors | Performer button, index switch, e-stop monitor leads. **Low voltage only.** | 4 | Have | Parts 3–5 |
| 6.5 | 2.2kΩ, 10kΩ resistors; 100nF caps | Index pull-up; extra noise filtering only if needed. | — | Have (hobby stock) | Parts 4, 8 |

## 7. Enclosure

| # | Part | Details | Qty | Status | Guide |
|---|---|---|---|---|---|
| 7.1 | Gratury IP67 enclosure 16.1×12.2×7.1" | Hinged clear lid, mounting plate. Holes for the inlet, outlet, e-stop and M12s break the seal, so fit glands everywhere else. | 1 | Have | — |
| 7.2 | Cable glands | Strip cable, Ethernet, anything not on a panel connector. | assorted | Have | Parts 6, 8 |
| 7.3 | Vents / 5V fan | Only if the closed-box test (Part 8) shows the temperature climbing. | 0–1 | Optional | Part 8 |
| 7.4 | Heat-shrink | Spade connectors, splices, component legs. | 1 kit | Buy if out | Parts 6, 7 |
| 7.5 | Cable ties + adhesive mounts | Secure every run against vibration. | — | Have (assumed) | — |
| 7.6 | Ethernet patch cable | Pi USB-Ethernet adapter (eth1) → DMX-AN2. | 1 | Have (assumed) | — |
