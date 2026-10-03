# Parade Float Show-Control System

Show-control platform for an elaborate parade float. Coordinates DMX lighting, NeoPixels, GPIO sensors, relays, and mechanical events from a Raspberry Pi. Fully developable and testable on macOS without any hardware attached.

## Current status

**Milestone 1 complete** — Mac → Ethernet → Chauvet DMX-AN2 → one DMX fixture. Simulated GPIO, web dashboard, cue engine all working.

**Milestone 2 in progress** — real Raspberry Pi drivers for GPIO inputs, the motor relay and NeoPixels, plus e-stop monitoring. Wiring the control box: follow [docs/WIRING_GUIDE.md](docs/WIRING_GUIDE.md). See [docs/STATUS.md](docs/STATUS.md).

**Phone booth show** — the booth runs a fixed sequence (turn → performer ready → extra revolution → stop → turn) whose looks are changed live from the dashboard's **Show** tab. See [docs/SHOW.md](docs/SHOW.md).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design and [docs/DECISIONS.md](docs/DECISIONS.md) for architectural decision records.

---

## Quick start

**One-time setup:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Run the app:**
```bash
source .venv/bin/activate
parade
```

Open **http://localhost:8080** in a browser.

**Run tests:**
```bash
.venv/bin/pytest
```

---

## Using the dashboard

The web UI at http://localhost:8080 provides:

- **State control** — transition the system through SAFE → READY → RUNNING using the buttons
- **Show tab** — the phone booth show: live phase and timers, every look and timing (lightning, sparks, fog, exterior, NeoPixel sides, stop pulse and fade-up), and the spark powder counter. Changes apply instantly and are saved to `config/show.yaml`. RUNNING starts the booth turning. See [docs/SHOW.md](docs/SHOW.md)
- **MANUAL mode** — from SAFE, switch to MANUAL to drive relays and NeoPixels by hand and watch inputs register (Manual tab). Cues are ignored; returning to SAFE switches everything off
- **DMX channel table** — live view of all 512 channels for each universe
- **Scene buttons** — apply or fade to any defined scene
- **Manual channel control** — enter a channel number and value (0–255) to set it directly
- **Simulation panel** — toggle GPIO inputs or inject named operator triggers without physical hardware

### Trying the show without hardware

1. Start the app with simulated drivers and open the **Show** tab
2. Go READY → RUNNING: the phase shows ROTATING and the motor relay turns on
3. On the Live tab, toggle `performer_button` (ARMED), then `rotation_index`: the booth takes an extra revolution if the index came within 10 s, otherwise stops
4. Watch the stop countdown, fog boost and the lights' pulse and fade-up, then rotation resumes

### Trying the cue engine

With `show.enabled: false` in `config/default.yaml` the cue engine and Builder tab come back instead of the show.

1. Start the app and open the dashboard
2. In the **Simulation** panel, toggle `rotation_index` to active
3. The `blue_wash` scene applies automatically (triggered by the `trigger_blue_on_gpio` cue)
4. In the Simulation panel, inject operator trigger `flash`
5. The fixture flashes white, then fades back to blue over 2 seconds

---

## Connecting real hardware

### Mac network setup

The DMX-AN2 uses Art-Net, which requires both devices on the same subnet. Set your Mac's ethernet interface to:

| Field | Value |
|---|---|
| IP address | `2.0.0.2` (or any `2.x.x.x` other than the node's IP) |
| Subnet mask | `255.0.0.0` |

### Enable Art-Net output

In [config/default.yaml](config/default.yaml), change:
```yaml
hardware:
  dmx_driver: simulated
```
to:
```yaml
hardware:
  dmx_driver: artnet
```

The node IP defaults to `2.0.0.1` (Chauvet DMX-AN2 factory default). If you've changed it via the DMX-AN2 web UI, update `network.artnet_nodes[0].ip` in the same file.

Restart `parade` — it begins sending Art-Net at 40 Hz immediately.

### Pi networking

The Pi runs its own WiFi network (`very-good-float-2026`) for the iPad at `http://10.0.0.1:8080`, gets internet over an Ethernet cable from the Mac, and talks Art-Net to the DMX-AN2 on a USB-Ethernet adapter. Setup, tests and troubleshooting: [docs/NETWORK.md](docs/NETWORK.md). Printable recovery card: [docs/NETWORK_RECOVERY.md](docs/NETWORK_RECOVERY.md).

```bash
bash scripts/pi-network-status.sh   # plain-English status of every port
```

### GPIO, relay and NeoPixels (on the Pi)

1. `bash scripts/pi-setup.sh`, then `sudo reboot` (installs `lgpio`/`spidev`, enables SPI).
2. Wire each device and check it with the bench tool (service stopped). Step by step: [docs/WIRING_GUIDE.md](docs/WIRING_GUIDE.md).
   ```bash
   .venv/bin/parade-hwcheck inputs          # watch switches
   .venv/bin/parade-hwcheck relay           # relay ON 2 s (refuses if e-stop pressed)
   .venv/bin/parade-hwcheck pixels test     # colour test + chase
   ```
3. Set the matching driver to `rpi` in `config/default.yaml` (`gpio_driver`, `relay_driver`, `pixel_driver`; independent of each other).

Pin map and wiring rules: [docs/HARDWARE.md](docs/HARDWARE.md). Safety behaviour (e-stop, relay safe states): [docs/SAFETY.md](docs/SAFETY.md).

---

## Repository layout

```
config/
  default.yaml        # hardware drivers, network, fixtures, GPIO
  scenes.yaml         # named DMX scenes (per-fixture channel values)
  show.yaml           # live phone booth show settings (written by the Show tab)
cues/
  example.yaml        # event triggers → action sequences
docs/
  ARCHITECTURE.md     # system design and component diagram
  DECISIONS.md        # architectural decision records
  WIRING_GUIDE.md     # step-by-step control-box wiring with tests
  HARDWARE.md         # pin map, drivers, bench tool
  SAFETY.md           # e-stop and relay safety layers
  SHOW.md             # phone booth show: cycle, settings, spark calibration
  HARDWARE_SETUP_CHECKLIST.md  # power, relay & NeoPixel background checklist
  NETWORK.md          # Pi networking: WiFi access point, Mac cable, Art-Net
  NETWORK_RECOVERY.md # printable one-page network recovery card
  BOM.md              # parts to buy for the control box
  PROJECT_SPEC.md     # requirements and milestone plan
fixture_profiles/
  rockville/
    rockwedge_led.yaml  # RockWedge LED 6ch and 10ch channel maps
hardware/
  manuals/            # manufacturer PDFs (authoritative for hardware behavior)
src/parade/
  config/             # Pydantic models, YAML loader
  core/               # event bus, state machine, show engine, safety monitor
  dmx/                # universe buffer, Art-Net sender, fixtures, scenes
  gpio/               # GPIO interface + simulated and lgpio implementations
  relay/              # relay interface + simulated and lgpio implementations
  pixels/             # NeoPixel interface + simulated and SPI implementations
  show/               # phone booth show: sequencer, effects, live settings
  status_lights/      # BlinkStick state/health LEDs
  display/            # OLED status display
  tools/hwcheck.py    # parade-hwcheck bench tool
  api/                # FastAPI routes, WebSocket push, static dashboard
  main.py             # entry point, wiring
tests/
  unit/               # pytest tests for all core subsystems
```

---

## Configuration reference

### config/default.yaml

```yaml
hardware:
  dmx_driver: simulated   # "simulated" | "artnet"
  gpio_driver: simulated  # "simulated" | "rpi" (lgpio)
  pixel_driver: simulated # "simulated" | "rpi" (SPI on GPIO10)
  relay_driver: simulated # "simulated" | "rpi" (lgpio)
  gpio_chip: 0            # /dev/gpiochipN (0 on a Pi 3)

network:
  artnet_nodes:
    - id: main_node
      ip: "2.0.0.1"       # DMX-AN2 IP (change if reconfigured)
      port: 6454

dmx:
  universes:
    - id: 1
      node: main_node
      protocol: artnet
      refresh_hz: 40      # 10–40 Hz per DMX-AN2 spec
      on_node_loss: hold  # "hold" | "blackout"

fixtures:
  - id: booth_wash
    name: "Phone Booth Wash"
    profile: rockville_rockwedge_6ch  # profile id from fixture_profiles/
    universe: 1
    address: 1            # DMX start address (1–512)
```

### config/scenes.yaml

Each scene maps fixture ids to per-channel values (0–255). Channel names come from the fixture profile.

```yaml
- id: blue_wash
  name: "Blue Wash"
  fixtures:
    booth_wash:
      red: 0
      green: 0
      blue: 255
      white: 0
      amber: 0
      uv: 0
```

### cues/example.yaml

A cue pairs an event trigger with a condition and an action sequence.

```yaml
- id: operator_flash
  trigger:
    event: operator_trigger
    condition: "event.trigger_id == 'flash'"
  actions:
    - type: set_dmx_scene
      scene: white_flash
    - type: wait
      duration_ms: 1000
    - type: fade_dmx_scene
      scene: blue_wash
      duration_ms: 2000
```

Available action types: `set_dmx_scene`, `fade_dmx_scene`, `wait`, `blackout`.

---

## Hardware

| Device | Role | Notes |
|---|---|---|
| Chauvet DMX-AN2 | Art-Net → DMX node | Default IP `2.0.0.1`, port 6454, 2-universe |
| Rockville RockWedge LED | DMX fixture | RGBWA+UV, 6ch or 10ch mode |
| Turntable index microswitch | GPIO26 (NC) | Stops the booth after the performer button; index watchdog |
| Performer button | GPIO27 (NO) | Arms the stop (performer ready) |
| E-stop | Mains NC contact + GPIO22 monitor | Hardware cut; software goes to EMERGENCY STOP |
| Relay module | GPIO18 | Switches the rotation motor (see WIRING_GUIDE Part 7) |
| WS2812B NeoPixels | GPIO10 (SPI) via level shifter | 50 px |
| Raspberry Pi 3 Model B | Show controller | GPIO, NeoPixels, relays |

Fixture channel maps are in [fixture_profiles/](fixture_profiles/). All channel data comes from manufacturer manuals in [hardware/manuals/](hardware/manuals/).
