# Parade Float Show-Control System — Architecture

> **Status:** Milestone 1 design (pre-implementation). Last updated: 2026-09-13.

---

## 1. Purpose and Scope

This document describes the proposed architecture for the parade float show-control system. It covers the software structure, technology choices, hardware abstraction strategy, concurrency model, safety architecture, and milestone plan.

This architecture is designed to:

1. Deliver a working Milestone 1 proof-of-concept on macOS (no Raspberry Pi required).
2. Expand without rewriting to support physical GPIO, NeoPixels, relays, and multiple DMX universes.
3. Remain maintainable, testable, and operable by a single engineer on a parade float.

---

## 2. Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Mature RPi/GPIO/LED libraries, asyncio for concurrency, FastAPI ecosystem, readable cue DSL |
| Async runtime | asyncio (stdlib) | Single-threaded event loop eliminates most race conditions; no external broker needed |
| Web framework | FastAPI | Async-native, automatic OpenAPI docs, WebSocket support for live push |
| Data validation | Pydantic v2 | Config validation, event models, API schemas |
| Configuration | YAML + Pydantic | Human-readable, easily edited outside the codebase, validated at startup |
| DMX/Art-Net | pyartnet (or thin wrapper) | Handles ArtDmx packet framing; proven in Python show-control projects |
| NeoPixels (RPi) | rpi_ws281x | DMA-based WS281x driver; does not require MCU for Milestone 1–2 |
| GPIO (RPi) | RPi.GPIO or gpiozero | Standard RPi GPIO; gpiozero has cleaner simulation path |
| Testing | pytest + pytest-asyncio | Runs entirely on macOS; no hardware dependency |
| Frontend | Plain HTML + Vanilla JS / HTMX | No build toolchain; keeps UI simple and maintainable |

**Explicitly avoided:** Docker, Redis, message brokers, databases, React build pipelines, cloud dependencies. The system must operate fully offline.

---

## 3. High-Level Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        Web Browser                               │
│          Dashboard · Manual Control · Simulation Panel           │
└─────────────────────────┬────────────────────────────────────────┘
                          │  HTTP / WebSocket
┌─────────────────────────▼────────────────────────────────────────┐
│                       FastAPI Server                              │
│               api/routes/ · WebSocket push                        │
└─────────────────────────┬────────────────────────────────────────┘
                          │
       ┌──────────────────┼─────────────────────┐
       │                  │                     │
       ▼                  ▼                     ▼
┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐
│ Safety Mgr  │  │  Show Engine   │  │  Config / Profiles   │
│ safety/     │  │  core/engine   │  │  config/             │
│             │  │                │  │  fixture_profiles/   │
│ • E-stop    │  │ • cue loading  │  │  cues/               │
│ • ARMED     │  │ • trigger eval │  └──────────────────────┘
│ • state     │  │ • action exec  │
└──────┬──────┘  └───────┬────────┘
       │                 │
       └────────┬────────┘
                │
       ┌────────▼────────────────────────────────────────────────┐
       │                     Event Bus                            │
       │              core/event_bus.py                           │
       │   async pub/sub — typed events — timestamped             │
       └──────┬───────────────────────────┬───────────────────────┘
              │                           │
     ┌────────▼────────┐        ┌─────────▼─────────────────┐
     │  Hardware Layer │        │    Sensor/Logic Layer      │
     │                 │        │                            │
     │  DMX Subsystem  │        │  sensors/rotation.py       │
     │  dmx/           │        │  (debounce, RPM, count)    │
     │                 │        └────────────────────────────┘
     │  GPIO Subsystem │
     │  gpio/          │
     │                 │
     │  Pixel Subsystem│
     │  pixels/        │
     │                 │
     │  Relay Subsystem│
     │  relays/        │
     └────────┬────────┘
              │
   ┌──────────▼─────────────────────────────────────────────────┐
   │               Hardware Abstraction Interfaces               │
   │                                                             │
   │  DMXInterface ──── ArtNetDMX (real)                        │
   │               └─── SimulatedDMX (mac dev / testing)        │
   │                                                             │
   │  GPIOInterface ─── RaspberryPiGPIO (real)                  │
   │                └── SimulatedGPIO (mac dev / testing)        │
   │                                                             │
   │  PixelInterface ── RPiPixels (real, rpi_ws281x)             │
   │                 ├─ MicrocontrollerPixels (future)           │
   │                 └─ SimulatedPixels (mac dev / testing)      │
   │                                                             │
   │  RelayInterface ── RPiRelays (real)                        │
   │                 ├─ MicrocontrollerRelays (future)           │
   │                 └─ SimulatedRelays (mac dev / testing)      │
   └─────────────────────────────────────────────────────────────┘
              │                              │
   ┌──────────▼──────┐           ┌───────────▼────────────┐
   │  Chauvet DMX-AN2│           │  Raspberry Pi GPIO     │
   │  (Art-Net node) │           │  NeoPixel strips       │
   │  → DMX fixtures │           │  Relay boards          │
   └─────────────────┘           └────────────────────────┘
```

---

## 4. Repository / Package Structure

```
parade-2026/
├── src/
│   └── parade/
│       ├── main.py               # entry point — config, DI wiring, server start
│       ├── config/
│       │   ├── models.py         # Pydantic models for all config sections
│       │   └── loader.py         # YAML → Pydantic, startup validation
│       ├── core/
│       │   ├── events.py         # Event base + all event type definitions
│       │   ├── event_bus.py      # Async pub/sub
│       │   ├── state.py          # SystemState enum + transition rules
│       │   └── engine.py         # Show/cue engine — trigger eval, action exec
│       ├── dmx/
│       │   ├── interface.py      # DMXInterface abstract base
│       │   ├── artnet.py         # Art-Net (pyartnet) implementation
│       │   ├── simulated.py      # Simulated — stores values, exposes for UI
│       │   ├── universe.py       # Per-universe buffer + async fade engine
│       │   ├── fixtures.py       # FixtureProfile + Fixture instance models
│       │   └── scenes.py         # Scene definitions, semantic → DMX translation
│       ├── gpio/
│       │   ├── interface.py      # GPIOInterface abstract base
│       │   ├── rpi.py            # RPi.GPIO implementation (import-guarded)
│       │   └── simulated.py      # Simulated — injectable state via API
│       ├── pixels/
│       │   ├── interface.py      # PixelInterface abstract base
│       │   ├── rpi.py            # rpi_ws281x driver (import-guarded)
│       │   ├── mcu.py            # Serial protocol to MCU (future)
│       │   └── simulated.py      # Simulated — stores pixel array for UI
│       ├── relays/
│       │   ├── interface.py      # RelayInterface abstract base
│       │   ├── rpi.py            # RPi GPIO relay driver (import-guarded)
│       │   ├── mcu.py            # MCU relay protocol (future)
│       │   └── simulated.py      # Simulated
│       ├── sensors/
│       │   └── rotation.py       # RotationTracker: debounce, count, RPM, events
│       ├── safety/
│       │   └── manager.py        # SafetyManager: e-stop, armed/disarmed, safe outputs
│       └── api/
│           ├── app.py            # FastAPI application factory
│           ├── dependencies.py   # DI — inject engine, dmx, gpio, etc.
│           └── routes/
│               ├── dashboard.py  # GET /status, WS /ws/state
│               ├── dmx.py        # GET/POST /dmx/universe, /dmx/fixture, /dmx/scene
│               ├── simulation.py # POST /sim/gpio, /sim/event, GET /sim/state
│               └── cues.py       # GET/POST /cues — list, trigger, cancel
├── config/
│   └── default.yaml              # starter config (edit for each deployment)
├── fixture_profiles/
│   └── (yaml fixture definitions — one file per fixture family)
├── cues/
│   └── (yaml cue/routine definitions)
├── hardware/
│   └── manuals/                  # manufacturer PDFs (not committed if large)
├── docs/
│   ├── ARCHITECTURE.md           # this file
│   ├── DECISIONS.md
│   ├── HARDWARE.md
│   ├── SAFETY.md
│   ├── TESTING.md
│   └── STATUS.md
├── tests/
│   ├── conftest.py               # shared fixtures, simulated hardware setup
│   ├── unit/
│   │   ├── test_event_bus.py
│   │   ├── test_state_machine.py
│   │   ├── test_cue_engine.py
│   │   ├── test_dmx_universe.py
│   │   ├── test_dmx_scenes.py
│   │   └── test_rotation_sensor.py
│   └── integration/
│       └── test_show_flow.py     # event → cue → DMX action end-to-end
├── pyproject.toml
└── README.md
```

Hardware-specific imports (`RPi.GPIO`, `rpi_ws281x`) are guarded by try/except so the package imports cleanly on macOS. The concrete implementation to use is injected at startup via configuration, not selected by runtime platform detection.

---

## 5. Core Subsystems

### 5.1 Event Bus

A lightweight async pub/sub implemented with asyncio. No external broker.

```
EventBus
  subscribe(event_type, async_handler)
  publish(event)            # calls all handlers for event.type concurrently
  publish_sync(event)       # schedules publish on the running event loop
```

All hardware drivers publish to the event bus. The show engine subscribes. The API WebSocket handler also subscribes to push live updates to browsers.

Events are Pydantic dataclasses with:
- `event_type: str` — machine-readable discriminator
- `timestamp: float` — unix time
- `source: str` — originating subsystem
- Type-specific payload fields

Defined event types (Milestone 1 subset):

| Event Type | Source | Payload |
|---|---|---|
| `gpio_changed` | GPIO driver | pin, state, active |
| `rotation_index` | RotationTracker | revolution_count, timestamp |
| `revolution_count_changed` | RotationTracker | count, rpm |
| `timer_elapsed` | Show Engine | timer_id |
| `show_started` | Show Engine | — |
| `show_stopped` | Show Engine | — |
| `operator_trigger` | API | trigger_id, params |
| `emergency_stop` | Safety Manager | source |
| `emergency_stop_cleared` | Safety Manager | — |
| `system_state_changed` | Safety Manager | old_state, new_state |
| `sensor_fault` | Sensor layer | sensor_id, description |
| `dmx_node_offline` | DMX subsystem | node_address |
| `dmx_node_online` | DMX subsystem | node_address |
| `cue_started` | Show Engine | cue_id |
| `cue_completed` | Show Engine | cue_id |
| `cue_cancelled` | Show Engine | cue_id, reason |

### 5.2 System State Machine

System state is centralized in `SafetyManager` and `SystemState`. No scattered boolean variables.

```
BOOTING
  └─► SAFE           (hardware init complete, outputs in safe state)
        ├─► MANUAL   (bench testing: relays/pixels by hand, cues ignored; back to SAFE only)
        └─► READY    (operator has cleared the system for operation)
              └─► RUNNING    (show active)
              │     └─► PAUSED
              │           └─► RUNNING
              └─► ARMED     (hazardous effects enabled — separate flag, see §5.5)

Any state ──► EMERGENCY_STOP   (hardware e-stop or software emergency)
                └─► SAFE       (manual reset only)

Any state ──► FAULT            (unrecoverable software/hardware error)
                └─► SAFE       (operator acknowledge + restart if needed)
```

Allowed transitions are defined as a table. Attempting an illegal transition raises a `StateTransitionError` and logs an error rather than silently failing.

### 5.3 Show / Cue Engine

The cue engine loads cue definitions from YAML and evaluates them against incoming events.

**Cue definition schema (YAML):**

```yaml
id: phone_booth_flash_every_3rd
description: "Flash effects on every 3rd revolution"
trigger:
  event: rotation_index
  condition: "revolution_count % 3 == 0"   # evaluated safely (restricted AST)
priority: 10
cooldown_ms: 500
cancellable: true
actions:
  - type: set_dmx_scene
    scene: phone_booth_flash
  - type: start_pixel_effect
    zone: phone_booth
    effect: time_travel
  - type: wait
    duration_ms: 750
  - type: pulse_relay
    relay: approved_effect_trigger
    duration_ms: 250
  - type: fade_dmx_scene
    scene: phone_booth_normal
    duration_ms: 2000
```

**Trigger evaluation:**
- `event` must match the incoming event type.
- `condition` is an optional expression evaluated against event fields and current system state. Expressions are evaluated using a restricted evaluator (no `exec`/`eval` with arbitrary code — use a simple expression parser or restricted `ast.literal_eval`-style evaluator).

**Action execution:**
- Each cue run is an `asyncio.Task`.
- `wait` actions use `asyncio.sleep` — non-blocking.
- Multiple cues can run concurrently; their tasks are independent.
- Higher-priority cues cancel lower-priority tasks when they conflict on the same resource (configurable per cue).
- Blackout cancels all active cue tasks and sends blackout to all outputs.
- Emergency stop cancels all tasks, inhibits new triggers, places all outputs in safe state.

**Defined action types:**

| Action | Effect |
|---|---|
| `set_dmx_scene` | Apply a named scene immediately |
| `fade_dmx_scene` | Fade current universe state to a scene over `duration_ms` |
| `set_dmx_raw` | Set raw channel values (debug/test only) |
| `start_pixel_effect` | Start a named effect on a pixel zone |
| `stop_pixel_effect` | Stop an effect on a zone (or all zones) |
| `set_relay` | Set relay to on/off |
| `pulse_relay` | Pulse relay for `duration_ms` |
| `wait` | Async delay |
| `publish_event` | Publish a synthetic event to the bus |
| `set_system_state` | Transition system state |
| `blackout` | Immediate all-output blackout |

### 5.4 DMX Subsystem

**Universe buffer model:**

Each configured universe maintains a `bytearray[512]` of current channel values. Writes to the buffer are immediate. A background asyncio task sends the buffer as ArtDmx packets at approximately 40 Hz, regardless of whether values changed (keep-alive required by Art-Net spec).

**Fixture profiles:**

Profiles define the channel layout for a fixture family. They are loaded from YAML files in `fixture_profiles/`. Profiles are never invented — they are derived from manufacturer documentation.

```yaml
# fixture_profiles/rockville/rockwedge_led.yaml
# Source: RockwedgeLED_Manual_v3_OL.pdf, p.7
# 6-channel mode (set fixture to D-mode via onboard LCD)
- id: rockville_rockwedge_6ch
  channel_count: 6
  color_model: rgbwau   # Red/Green/Blue/White/Amber/UV
  channels:
    red: 1       # 0–255, direct LED control, no master dimmer
    green: 2
    blue: 3
    white: 4
    amber: 5
    uv: 6        # labeled "Purple Dimmer" in manual; this is the UV LED
```

**Fixture instances** are defined in configuration:

```yaml
fixtures:
  - id: booth_wash_left
    name: "Phone Booth Left Wash"
    profile: rockville_rockwedge_6ch
    universe: 1
    address: 1
```

**Scenes** describe intent, not raw bytes. The RockWedge's 6-channel mode exposes individual color channels — scenes address channels by their semantic name from the fixture profile:

```yaml
scenes:
  phone_booth_normal:
    fixtures:
      booth_wash_left:
        red: 0
        green: 0
        blue: 255
        white: 0
        amber: 0
        uv: 0
      booth_wash_right:
        red: 0
        green: 0
        blue: 255
        white: 0
        amber: 0
        uv: 0
  phone_booth_flash:
    fixtures:
      booth_wash_left:
        red: 255
        green: 255
        blue: 255
        white: 255
        amber: 0
        uv: 0
```

The scene translator maps semantic channel names through the fixture profile to actual DMX addresses. For 10-channel mode fixtures, semantic `intensity` maps to the master dimmer channel; for 6-channel mode (which has no master dimmer), intensity scaling can be applied proportionally across color channels if needed.

The scene translator uses the fixture profile to convert semantic values (color, intensity) to DMX channel values.

**Fade engine:**

Fades run as asyncio tasks. Each fade step updates the universe buffer; the 40 Hz output loop picks up the latest values. Multiple simultaneous fades on different fixtures are independent tasks.

**Art-Net node behavior:**

The Chauvet DMX-AN2 is configured with a static IP on the Art-Net subnet (2.x.x.x) or DHCP, then assigned to a universe. ArtDmx packets are sent unicast to the node's IP:6454. The node IP and universe-to-port mapping are configuration items.

**Failure behavior on Art-Net node loss:**

Default: **hold last look** (do not blackout). The universe buffer retains its last values. The show engine receives a `dmx_node_offline` event and can respond programmatically (e.g., inhibit new cues). Rationale: brief network interruption during a parade should not cause sudden blackout. Configurable per universe.

### 5.5 GPIO Subsystem

GPIO inputs publish `gpio_changed` events to the event bus. Show logic never lives directly in GPIO callbacks.

Configuration per input:

```yaml
gpio_inputs:
  - id: rotation_index
    pin: 17                # TBD — physical pin assignment
    mode: input
    pull: up               # pull_up / pull_down / none
    active_low: true
    debounce_ms: 20
    description: "Turntable index microswitch"
```

`RotationTracker` (in `sensors/rotation.py`) subscribes to `gpio_changed` events for the rotation index pin and publishes `rotation_index` and `revolution_count_changed` events with timestamps and RPM calculations. It also implements:

- Revolution period measurement (rolling average of last N)
- RPM estimation
- Stale-signal detection (no pulse in expected window → `sensor_fault`)
- Stuck-low / stuck-high detection

If angular position at fractions of a revolution becomes necessary later, the sensor abstraction allows adding an encoder, Hall-effect sensors, or additional microswitches without modifying the cue engine.

### 5.6 NeoPixel Subsystem

LED zones are logical abstractions mapped to physical pixel ranges:

```yaml
pixel_zones:
  phone_booth_front:
    strip: strip_0
    start: 0
    end: 30
  phone_booth_left:
    strip: strip_0
    start: 31
    end: 60
```

Effects (chase, fade, pulse, etc.) operate on zones rather than raw pixel indices. The `PixelInterface` exposes zone-level commands. Implementations handle the translation to physical indices.

For Milestone 1, `SimulatedPixels` stores the pixel array and exposes it via the WebSocket for visualization.

### 5.7 Relay Subsystem

Relay outputs are defined in configuration with:
- active_high / active_low polarity
- safe state (open/closed at startup and shutdown)
- maximum activation duration (safety guard against software bugs that leave relays stuck)

Potentially hazardous relay outputs additionally require:
- System state = ARMED
- No active emergency stop
- Effect-specific ARMED flag

### 5.8 Safety Manager

The `SafetyManager` owns the authoritative system state and the ARMED flag for hazardous effects.

On emergency stop (via monitored GPIO or software trigger):
1. Transitions state to `EMERGENCY_STOP`
2. Publishes `emergency_stop` event
3. Show engine cancels all active cue tasks
4. All relay outputs transition to their defined safe state
5. Hazardous effect ARMED flag is cleared
6. DMX outputs optionally fade to safe scene or blackout (configurable)
7. E-stop state displayed prominently in UI

Recovery from EMERGENCY_STOP requires explicit manual operator action (UI button or physical reset), not an automatic timer.

Implemented as `SafetyMonitor` in `src/parade/core/safety.py`, which also owns operator state transitions (the dashboard's state buttons go through it). See [SAFETY.md](SAFETY.md).

**Critical distinction:** Software monitors and responds to the e-stop condition. The physical e-stop circuit is a normally-closed loop that removes power from show loads directly, independent of software. See SAFETY.md for the hardware architecture.

---

## 6. Hardware Abstraction Strategy

Each hardware category has an abstract base class (ABC) defining its interface. Concrete implementations are injected at startup. This is the project's core extensibility mechanism.

```python
# Pattern used across all hardware abstractions
class DMXInterface(ABC):
    @abstractmethod
    async def send_universe(self, universe: int, data: bytes) -> None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
```

The implementation to use is selected from configuration:

```yaml
hardware:
  dmx_driver: artnet        # artnet | simulated
  gpio_driver: simulated    # rpi | simulated
  pixel_driver: simulated   # rpi | mcu | simulated
  relay_driver: simulated   # rpi | mcu | simulated
```

On macOS, `artnet` is a valid choice for DMX (sends real Art-Net over the network) but `rpi` drivers are unavailable. The application fails at startup with a clear error if an unavailable driver is configured, rather than failing silently at runtime.

---

## 7. Simulation Architecture

The simulation layer must allow developing and testing show logic without physical hardware.

### SimulatedGPIO
- Maintains an in-memory dict of pin states.
- Exposes `POST /sim/gpio/{pin}` to inject state changes from the UI or test code.
- Publishes `gpio_changed` events identically to the real GPIO driver.

### SimulatedDMX
- Stores the universe buffer in memory.
- Exposes the current buffer via WebSocket to the UI (live DMX channel viewer).
- Does not send any network packets.

### SimulatedPixels
- Stores pixel array in memory.
- Exposes current state via WebSocket for a simple color-grid visualizer in the UI.

### SimulatedRelays
- Stores relay states in memory.
- Exposes state via API and UI.

### Simulation Panel (UI)
The web interface includes a Simulation Panel (only visible when `hardware.gpio_driver == simulated`):
- Buttons to toggle simulated microswitches
- Slider for simulated RPM (auto-fires rotation index events at the appropriate interval)
- Buttons to inject specific named events
- Live DMX channel value table
- Live pixel zone color display
- Relay state indicators

---

## 8. Configuration Model

A single YAML file `config/config.yaml` with all configuration. Loaded at startup by `config/loader.py`, validated with Pydantic, fails fast on any error.

Top-level sections:

```yaml
system:
  name: "parade-float-2026"
  environment: development  # development | production

hardware:
  dmx_driver: artnet        # artnet | simulated
  gpio_driver: simulated    # rpi | simulated
  pixel_driver: simulated   # rpi | mcu | simulated
  relay_driver: simulated   # rpi | mcu | simulated

network:
  artnet_nodes:
    - id: main_node
      ip: "2.0.0.1"         # TBD — set from DMX-AN2 config
      port: 6454

dmx:
  universes:
    - id: 1
      node: main_node
      protocol: artnet
      refresh_hz: 40
      on_node_loss: hold    # hold | blackout

fixtures:
  - id: booth_wash_left
    name: "Phone Booth Left Wash"
    profile: rockville_rockwedge_6ch
    universe: 1
    address: 1

gpio_inputs: []             # empty until RPi hardware is defined

relay_outputs: []           # empty until relay hardware is defined

pixel_zones: []             # empty until NeoPixel hardware is defined

safety:
  estop_pin: null           # TBD — physical pin assignment
  armed_requires_operator: true

web:
  host: "0.0.0.0"
  port: 8080
  log_level: info
```

Fixture profiles and cue definitions are loaded from their respective directories, not embedded in the main config file. This keeps `config.yaml` focused on deployment-specific settings.

---

## 9. Concurrency Model

Python asyncio, single-threaded event loop.

- Hardware drivers (DMX output loop, GPIO polling) run as asyncio `Task`s.
- Cue action sequences run as asyncio `Task`s (one task per active cue instance).
- The FastAPI server runs within the same event loop (via `uvicorn` with `loop="none"`).
- WebSocket push to browsers is an asyncio task that subscribes to the event bus.
- Fades are asyncio tasks updating the universe buffer.
- No threading except where unavoidable (RPi GPIO interrupt callbacks — marshalled back to the event loop via `loop.call_soon_threadsafe`).

**Ordering guarantees:**
- Events published within the event loop are handled in publication order per subscriber.
- Concurrent cue tasks are independent; ordering between them is not guaranteed.

**Conflict resolution for simultaneous cues:**
- Each cue has a numeric priority (higher = more important).
- If a new cue is triggered and a conflicting cue (same output resource) is active:
  - If new cue priority > active cue priority → cancel active cue, start new one.
  - If new cue priority ≤ active cue priority → new cue is suppressed (logged).
- Cooldown per cue prevents rapid re-triggering.
- Blackout (priority 0/special) cancels everything.

---

## 10. Failure Mode Behavior

| Failure | Behavior |
|---|---|
| Application crash | DMX-AN2 holds last look (configurable). RPi GPIO safe state is passive (inputs). Relay safe states defined in config. Physical e-stop circuit remains authoritative. |
| Raspberry Pi reboot | Same as crash. System starts in BOOTING → SAFE state, no outputs armed. |
| Art-Net node network loss | `dmx_node_offline` event published. Default: hold last look. Show continues without DMX updates until reconnect. |
| DMX output stops sending | Node detects loss and enters its own failsafe mode (hold or blackout — depends on DMX-AN2 firmware setting). |
| Microcontroller disconnect (future) | `mcu_offline` event. Pixel/relay outputs frozen. Alert displayed. |
| Microswitch stuck closed | RotationTracker detects impossibly high RPM or continuous trigger. Publishes `sensor_fault`. Cue engine can treat as abnormal. |
| Microswitch stuck open | RotationTracker detects no pulse within expected window. Publishes `sensor_fault`. |
| Excessive switch bounce | Debounce filter absorbs brief multi-transitions. If bounce rate exceeds threshold, `sensor_fault`. |
| Relay controller disconnect | `relay_offline` event. Outputs unknown. Alert displayed. |
| NeoPixel communication failure | Zone returns error. Alert displayed. Show continues for other outputs. |
| Invalid configuration at startup | Fail fast with clear error message. Do not start. |
| Two conflicting cues | Priority system arbitrates. Logged. |
| Emergency stop | All tasks cancelled. All outputs to safe state. ARMED cleared. State → EMERGENCY_STOP. |

---

## 11. Raspberry Pi vs Microcontroller Decision

**Recommendation: Use Raspberry Pi directly for Milestone 1–3. Re-evaluate before Milestone 4 based on observed reliability.**

### Analysis

| Concern | RPi Direct | RPi + MCU |
|---|---|---|
| NeoPixel timing | rpi_ws281x uses DMA — adequate for WS281x | MCU provides hardware-exact timing |
| GPIO debounce | Software debounce in asyncio — 1–10 ms latency | Hardware interrupt, ~µs latency |
| Relay safety | Software state management | Hardware watchdog possible |
| Development complexity | Single codebase | Two codebases, serial protocol, two firmwares |
| Failure points | One device | Two devices + serial link |
| Parade-float timing requirements | RPM counter ≈ 1–30 RPM; 1–2 ms jitter is irrelevant | MCU justified only if timing is critical |

**Why direct RPi is sufficient for a parade float:**

A parade float revolving at even 30 RPM completes one revolution every 2 seconds. A 10 ms timing jitter on the index signal represents 0.18° of angular error — imperceptible. The `rpi_ws281x` library's DMA approach avoids the Linux scheduler for pixel output. Software debouncing at 20 ms is adequate for a mechanical microswitch.

**When to reconsider adding an MCU:**

- If rpi_ws281x proves unreliable for specific LED strip count/type.
- If GPIO response latency causes visible show synchronization issues in practice.
- If a hardware watchdog becomes necessary for safety-critical relay outputs.

**If an MCU is added later:**

The `PixelInterface`, `RelayInterface`, and `GPIOInterface` abstractions are already designed for this. A `MicrocontrollerPixels`, `MicrocontrollerRelays`, and `MicrocontrollerGPIO` implementation would speak a simple binary serial protocol over USB/UART. The show engine would require no changes.

---

## 12. Known Hardware

### Chauvet DMX-AN2

Source: DMX-AN2_QRG_Rev1_ML6.pdf

- Type: Ethernet-to-DMX Art-Net/sACN node
- Outputs: **2 × 3-pin XLR** DMX ports (each independently configurable as Input or Output)
- Protocols: Art-Net, sACN — selectable per port via web UI
- Art-Net IP constraint: **Art-Net function restricted to IP addresses beginning with 2 or 10**
- Default IP: **2.0.0.1** (static); switchable to DHCP via web UI
- Web UI credentials: Admin/Admin (default); master recovery: CHAUVETDJ/CHAUVETDJ
- Frame rate: Configurable per port — 10, 15, 20, 25, 30, 35, or 40 Hz
- Universe: Configurable per port via web UI
- Channel range: 512 per port (1024 total)
- Power: 9 VDC 500 mA (included adapter) or 48 V PoE
- Reset: Hold reset button 3 seconds to restore factory defaults
- Limitation: 2-universe maximum (one port per universe)

**Software implication:** Our Mac must have its network interface configured on the 2.x.x.x or 10.x.x.x subnet to reach the node and to send valid Art-Net. A dedicated Ethernet interface or VLAN is recommended to keep Art-Net traffic separate from general network use.

**Node-loss behavior:** The QRG does not document what the DMX-AN2 does when Art-Net packets stop (hold last look vs. blackout). This should be tested empirically before parade day. Our software defaults to hold-last-look on the sending side regardless.

### Rockville RockWedge LED

Source: RockwedgeLED_Manual_v3_OL.pdf (© 2024 Rockville)

- Full description: 54W RGBWA+UV Wireless DMX PAR Light with Rechargeable Battery
- LED source: 3 LEDs × 18W each; each LED is a 6-in-1 (Red, Green, Blue, White, Amber, UV)
- Color model: **RGBWA+UV** (6 channels — the "Purple" channel in the manual is UV)
- DMX connector: 3-pin XLR in and out
- DMX address: Set via onboard LCD display (range 1–512)
- DMX modes: **6-channel** (D-mode) and **10-channel** (A-mode) — see fixture profile YAML

**6-channel mode:** Individual R/G/B/W/Amber/UV dimmers, no master dimmer.

**10-channel mode:** Master Dimmer + R/G/B/W/Amber/UV + Strobe + Function + Speed. Function channel (ch9) must be set to 0–8 for direct color control; values 9–255 activate auto/sound programs.

**Wireless DMX:** The fixture includes a built-in 2.4 GHz wireless DMX receiver. In this system we will use wired DMX via the 3-pin XLR connection. The wireless receiver can be enabled/disabled via the onboard menu (2.4G ON/OFF).

Fixture profile: [fixture_profiles/rockville/rockwedge_led.yaml](../fixture_profiles/rockville/rockwedge_led.yaml)

### Other Hardware (TBD)

See HARDWARE.md for the inventory as it is populated.

---

## 13. Open Questions and Assumptions

| # | Question | Impact | Status |
|---|---|---|---|
| 1 | Exact Raspberry Pi model (3B+, 4, 5)? | GPIO library, performance ceiling | Unknown |
| 2 | NeoPixel strip type (WS2812B, SK6812, etc.) and total pixel count? | `rpi_ws281x` configuration, power injection | Unknown |
| 3 | Number of relay outputs and their load types? | Relay driver selection, isolation requirements | Unknown |
| 4 | GPIO pin assignments for all inputs/outputs? | Config file, wiring documentation | Unknown |
| 5 | Power supply topology (12V, 5V rails, battery vs. generator)? | Power distribution design, EMI mitigation | Unknown |
| 6 | Cold spark machine make/model and supported control interface (DMX? dry contact?)? | Safety requirements, control wiring | Unknown |
| 7 | Network topology — dedicated switch, router, DHCP server available? | Static vs. DHCP for DMX-AN2 | Unknown |
| 8 | Rockville RockWedge LED exact DMX channel map and modes? | Fixture profile YAML — **blocks fixture implementation** | Needs manual |
| 9 | Chauvet DMX-AN2 firmware version and node-loss failsafe behavior? | Failure mode design | Needs manual |
| 10 | How many total DMX universes will the complete float require? | Whether one DMX-AN2 is sufficient | Unknown |
| 11 | Turntable rotation speed range (min/max RPM)? | RotationTracker timeout thresholds | Unknown |
| 12 | Will angular positions other than index (90°, 180°, 270°) be needed? | Whether microswitch is sufficient or encoder needed | Unknown |

---

## 14. Development Milestones

### Milestone 1 — Mac + DMX Proof of Concept *(current target)*

**Goal:** Demonstrate the core architecture on a Mac with a real DMX fixture.

Deliverables:
- Configuration loading and validation (Pydantic)
- `SimulatedGPIO` and `ArtNetDMX` implementations
- DMX universe buffer with 40 Hz output loop
- Fixture profile loading (pending RockWedge manual)
- Basic scene management and scene activation
- Linear fade between two scenes
- Minimal cue engine (event → action)
- Simulated GPIO event triggering a DMX scene
- FastAPI web server with:
  - Dashboard showing DMX universe values
  - Manual DMX channel/scene control
  - Simulation panel for GPIO injection
- pytest suite covering event bus, state machine, cue engine, DMX fade math

### Milestone 2 — Raspberry Pi + Physical GPIO + NeoPixels

- `RaspberryPiGPIO` implementation
- `RotationTracker` (rotation index sensor, debounce, RPM)
- `RPiPixels` implementation (rpi_ws281x)
- Physical testing on Pi with actual hardware
- LED zone effects (solid, fade, chase, pulse)

### Milestone 3 — Full Show Logic

- Complete cue DSL (all action types)
- Multi-universe DMX support
- Relay outputs (simulated → real)
- Emergency stop monitoring (GPIO)
- Safety Manager full implementation
- Cue priority and cancellation

### Milestone 4 — Advanced UI and Show Design

- Routine builder (WHEN/IF/THEN form)
- Fixture configuration UI
- Live event log
- Show designer (node-based — future)

---

## 15. Architectural Risks

1. **rpi_ws281x reliability at scale:** DMA pixel output has worked well for thousands of pixels in hobby projects, but floats introduce vibration, power noise, and long cable runs. Test early with actual strip length and power topology before committing.

2. **Art-Net timing on wireless:** Future architecture includes wireless DMX. Art-Net over Wi-Fi introduces latency and packet loss. sACN has better provisions for multicast. Evaluate when wireless DMX is added.

3. **Condition expression safety:** Cue conditions evaluated from YAML must not allow arbitrary code execution. Use a restricted evaluator or a simple parser.

4. **Config file size growth:** As the show grows to dozens of fixtures and hundreds of cues, a single `config.yaml` becomes unwieldy. The design allows splitting into `fixtures.yaml`, `gpio.yaml`, `cues/`, etc. via a config directory pattern — do this when needed, not preemptively.

5. **Single-process asyncio limits:** If a slow cue action blocks the event loop, the entire system stalls. All actions must be non-blocking. Long-running DMX fades and pixel effects are async tasks, but any third-party library calls that are synchronous must be wrapped in `asyncio.run_in_executor`.
