# Safety Architecture

The only hazardous load the control box switches is the **phone booth rotation motor**. The cold spark and fog machines are controlled over wireless DMX and have no electrical connection to the box.

The rule (ADR-012): **the hardware e-stop is authoritative.** The Pi is the show controller, never the thing that makes the motor safe.

## Layers, in order of authority

| # | Layer | Stops the motor when… | Depends on the Pi? |
|---|---|---|---|
| 1 | **E-stop NC #1** (XB4BS8445, 1–2) in series with the **contactor coil** | pressed, cable cut, connector pulled | **No** |
| 2 | **Relay wired COM→NO** (normally open) in the same coil circuit | Pi off/booting/crashed, relay board unpowered, GPIO18 low | No (fails open) |
| 2b | **Contactor** (LC1D09G7) opens **hot and neutral** when its coil drops | any of layers 1–2 | No |
| 3 | **Motor branch fuse** (T5A/T6.3A) and coil fuse (T1A) | motor or wiring fault | No |
| 4 | **GFCI** at the generator outlet | current leaking to earth (shock) | No |
| 5 | Software `SafetyMonitor` (`src/parade/core/safety.py`) | e-stop monitor active, or state leaves RUNNING or MANUAL | Yes |
| 6 | Show sequencer (`src/parade/show/`) | performer armed it and the tabletop reaches the index microswitch (RUNNING only) | Yes |
| 7 | Show **index watchdog** | no index pass within 2.5× the measured revolution (60 s before one is measured): motor off, state → FAULT | Yes |

Wiring for layers 1–4 is in [WIRING_GUIDE.md](WIRING_GUIDE.md) Part 7.

## What the software does

- **E-stop monitor** (`safety.estop_pin`, GPIO22, e-stop NC #2 to GND). Pressed **or wire cut** reads ACTIVE, which triggers:
  1. state → `EMERGENCY_STOP`
  2. every relay driven off
  3. every running cue cancelled
  4. `emergency_stop` event logged; dashboard banner.
- **Reset** needs the e-stop released **and** an operator clicking SAFE. Every transition except to `EMERGENCY_STOP` is refused while the monitor reads ACTIVE, including at boot. Releasing the e-stop never restarts anything by itself.
- **Relays switch on only in RUNNING or MANUAL.** The cue engine refuses `set_relay … state: true` outside RUNNING; the dashboard's manual relay buttons (`src/parade/core/manual.py`) refuse it outside MANUAL or while the e-stop is active. Off is always allowed.
- **Leaving RUNNING** (PAUSED, SAFE, FAULT, EMERGENCY_STOP) drives all relays off. SAFE, FAULT and EMERGENCY_STOP also cancel running cues.
- **MANUAL** (bench testing) is entered and left only through SAFE. Cues are ignored, so **the index microswitch does not stop the motor**: a relay switched on by hand stays on until it is switched off, the state leaves MANUAL, or the e-stop is pressed. Leaving MANUAL drives all relays off and blanks the NeoPixels.
- **Relay driver** (`src/parade/relay/rpi.py`) claims GPIO18 already at its off level and drives it off again on shutdown. `systemctl stop`, a clean exit, or a crash followed by the systemd restart all leave the relay off.
- **Index microswitch** is wired NC, so a cut wire reads as "at index". With the show sequencer (docs/SHOW.md) the booth turns continuously in RUNNING and stops at the index only after the performer button, so a cut wire alone doesn't stop it. The **index watchdog** covers that: no index pass in time (cut wire, stuck switch, jammed booth) cuts the motor and goes to FAULT.
- **Sparks and fog** are set to zero whenever the state leaves RUNNING, and sparks never fire while the booth is stopped.

## What the software cannot do

- A **hard freeze** (kernel hang, SD card failure) leaves GPIO18 at its last level. If the motor was running, it keeps running until layer 1 is used. This is why the e-stop must be within reach whenever the motor can run.
- The speed controller is left switched on, so the motor runs whenever the contactor closes. After an e-stop, if the Pi is frozen (dashboard not responding), the relay may still be on, and **releasing the e-stop would restart the motor.** Switch the box's inlet rocker off (or unplug it) **before** releasing the e-stop.
- Cutting power does not stop inertia. Record the **coast-down time** (checklist §5). If the booth coasts for more than a moment, a brake is a mechanical question, not a software one.
- The Pi cannot see whether the relay actually opened (welded contacts). The e-stop covers that as well.

## Testing

Unit tests: `tests/unit/test_safety.py`. Hardware acceptance tests: WIRING_GUIDE Part 7 (tests 12–19) and Part 8 (5–7). Re-run Part 8 after any wiring change.
