# Parade Float Show-Control System

Show-control platform for an elaborate parade float. Coordinates DMX lighting, NeoPixels, GPIO sensors, relays, and mechanical events from a Raspberry Pi. Fully developable and testable on macOS without any hardware attached.

## Current status

**Milestone 1 complete** — Mac → Ethernet → Chauvet DMX-AN2 → one DMX fixture. Simulated GPIO, web dashboard, cue engine all working.

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
- **DMX channel table** — live view of all 512 channels for each universe
- **Scene buttons** — apply or fade to any defined scene
- **Manual channel control** — enter a channel number and value (0–255) to set it directly
- **Simulation panel** — toggle GPIO inputs or inject named operator triggers without physical hardware

### Trying the cue engine

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

---

## Repository layout

```
config/
  default.yaml        # hardware drivers, network, fixtures, GPIO
  scenes.yaml         # named DMX scenes (per-fixture channel values)
cues/
  example.yaml        # event triggers → action sequences
docs/
  ARCHITECTURE.md     # system design and component diagram
  DECISIONS.md        # architectural decision records
  PROJECT_SPEC.md     # requirements and milestone plan
fixture_profiles/
  rockville/
    rockwedge_led.yaml  # RockWedge LED 6ch and 10ch channel maps
hardware/
  manuals/            # manufacturer PDFs (authoritative for hardware behavior)
src/parade/
  config/             # Pydantic models, YAML loader
  core/               # event bus, state machine, show engine
  dmx/                # universe buffer, Art-Net sender, fixtures, scenes
  gpio/               # GPIO interface + simulated implementation
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
  gpio_driver: simulated  # "simulated" | "rpi" (Milestone 2+)
  pixel_driver: simulated # "simulated" | "rpi" (Milestone 2+)
  relay_driver: simulated # "simulated" | "rpi" (Milestone 2+)

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
| Turntable index microswitch | GPIO input | Triggers cues on each rotation |
| Raspberry Pi (Milestone 2+) | Show controller | GPIO, NeoPixels, relays |

Fixture channel maps are in [fixture_profiles/](fixture_profiles/). All channel data comes from manufacturer manuals in [hardware/manuals/](hardware/manuals/).
