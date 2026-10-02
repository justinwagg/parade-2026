# Architectural Decision Records

This file records significant architectural decisions for the parade float show-control system. Each record includes the context, the decision, the rationale, and the alternatives that were rejected.

Format: ADR (Architectural Decision Record). Status: `accepted` | `superseded` | `pending`.

---

## ADR-001 — Language: Python

**Status:** Accepted
**Date:** 2026-09-13

### Context

The system must run on macOS for development and on Raspberry Pi for production. It needs async concurrency, a web server, DMX/Art-Net networking, GPIO access, and NeoPixel control.

### Decision

Python 3.11+ with asyncio.

### Rationale

- `rpi_ws281x` (NeoPixel DMA driver), `RPi.GPIO` / `gpiozero`, and `pyartnet` are mature Python libraries with no equivalents of comparable quality in other languages for RPi hardware.
- `asyncio` + `FastAPI` provide async web serving, WebSocket push, and non-blocking I/O in a single-threaded model that avoids threading races for show state.
- The Python ecosystem for testing, configuration validation (Pydantic), and YAML handling is excellent.
- Python is readable by embedded engineers, lighting programmers, and show designers — likely future maintainers.

### Alternatives Rejected

- **Node.js/TypeScript:** Strong async, but weaker RPi hardware library ecosystem. Two runtimes (Python for hardware, Node for UI) would add complexity.
- **Go:** Good concurrency, but very few RPi/NeoPixel libraries; would require low-level hardware interfaces from scratch.
- **Rust:** Excellent performance, but steep learning curve, no mature high-level RPi ecosystem, and performance is not the bottleneck here.

---

## ADR-002 — Async Runtime: asyncio (stdlib)

**Status:** Accepted
**Date:** 2026-09-13

### Context

The system runs multiple concurrent concerns: DMX output loop, cue execution, GPIO monitoring, web API, WebSocket push, and sensor processing. These must not block each other.

### Decision

Use Python's stdlib `asyncio` as the only concurrency primitive. One event loop, no threads except where external libraries force it.

### Rationale

- Single-threaded event loop eliminates the entire class of threading race conditions on show state.
- `asyncio.Task` provides lightweight concurrency for cue execution (many cues may run simultaneously).
- FastAPI is async-native; RPi GPIO interrupt callbacks are marshalled back to the event loop via `loop.call_soon_threadsafe`, keeping all show logic on one thread.
- No external broker (Redis, NATS, RabbitMQ) is needed or appropriate for an offline parade system.

### Consequences

- All show logic and action handlers must be non-blocking. Synchronous blocking calls must be wrapped in `asyncio.run_in_executor`.
- A badly written action that blocks the loop will stall the entire system. This must be enforced by code review.

---

## ADR-003 — Web Framework: FastAPI

**Status:** Accepted
**Date:** 2026-09-13

### Context

The system needs a web server for the operator dashboard, REST API for manual control, and WebSocket push for live state updates.

### Decision

FastAPI with Uvicorn, embedded in the same process as the show engine.

### Rationale

- Async-native; runs in the same asyncio event loop as the show engine without thread overhead.
- WebSocket support is first-class.
- Automatic OpenAPI documentation is useful during development.
- Pydantic integration provides request/response validation.
- Mature, well-documented, widely used.

### Alternatives Rejected

- **Flask:** Sync by default; WSGI model requires threading or a separate process for WebSocket support.
- **aiohttp:** Lower-level; more boilerplate; less ecosystem support.
- **Separate frontend process:** Adding a Node/React build pipeline for what is essentially a control panel is unnecessary complexity.

---

## ADR-004 — Frontend: Plain HTML + Vanilla JS (or HTMX)

**Status:** Accepted
**Date:** 2026-09-13

### Context

The operator UI is an internal tool used by one or two people on a parade float. It does not need to be a polished consumer product.

### Decision

Serve static HTML/CSS/JS from FastAPI. Use vanilla JavaScript or HTMX for interactivity. No frontend build toolchain.

### Rationale

- No npm, webpack, or React build pipeline to maintain.
- The system must work offline — no CDN dependencies.
- The UI complexity is moderate (dashboard, manual control, simulation panel). Vanilla JS is sufficient.
- HTMX is a reasonable upgrade for form interactions without adding a build step.

### Consequences

- If the UI grows to need a richer component model, migrating to a framework is possible — the FastAPI backend is already a clean API.

---

## ADR-005 — Configuration Format: YAML with Pydantic Validation

**Status:** Accepted
**Date:** 2026-09-13

### Context

Hardware layout, fixture addresses, GPIO pins, cue definitions, and network settings must be configurable without editing Python source code. The format must be human-readable.

### Decision

YAML files for all configuration, loaded at startup and validated with Pydantic v2. Fail fast on validation errors with a clear message.

### Rationale

- YAML is human-readable and widely familiar to non-programmers.
- Pydantic provides strong type validation with helpful error messages.
- Failing at startup on bad config is vastly safer than discovering invalid config during a parade show.
- YAML supports comments, which aids documentation of pin assignments and addresses.

### Alternatives Rejected

- **TOML:** Good but slightly less familiar; no meaningful technical advantage.
- **JSON:** No comments; less readable for deeply nested structures.
- **Python config files:** Executable configuration is a security and maintenance liability.
- **Database:** Unnecessary infrastructure; offline use requires simpler persistence.

---

## ADR-006 — DMX Protocol: Art-Net (primary)

**Status:** Accepted
**Date:** 2026-09-13

### Context

The Chauvet DMX-AN2 supports both Art-Net and sACN (E1.31). One must be selected as the primary protocol.

### Decision

Art-Net over UDP, unicast to the DMX-AN2's IP address. sACN support may be added later but is not required for Milestone 1.

### Rationale

- Art-Net is the most widely supported protocol across DMX nodes, consoles, and software.
- Unicast Art-Net is simpler to configure on a local network than sACN multicast.
- `pyartnet` is a mature Python library for Art-Net output.
- The Chauvet DMX-AN2 supports Art-Net natively.

### Consequences

- The `DMXInterface` abstraction ensures sACN could be added as an alternative implementation without changing the show engine.
- Art-Net has a 2048-universe theoretical limit; the 2-universe limit is the DMX-AN2's hardware constraint, not the protocol's.

---

## ADR-007 — Hardware Abstraction: Interface + Injected Implementations

**Status:** Accepted
**Date:** 2026-09-13

### Context

Show logic must be testable and developable on macOS without hardware. Real hardware implementations must be swappable without changing show logic.

### Decision

Abstract base classes (`DMXInterface`, `GPIOInterface`, `PixelInterface`, `RelayInterface`) with concrete implementations (`ArtNetDMX`, `SimulatedDMX`, `RaspberryPiGPIO`, `SimulatedGPIO`, etc.). The implementation is selected from configuration and injected at startup. Import-guarding ensures RPi-specific libraries do not cause import errors on macOS.

### Rationale

- Show logic never imports or references a concrete hardware class directly.
- Simulated implementations are full first-class citizens, not stubs — they maintain state and expose it via the API.
- Adding a new hardware implementation (e.g., `MicrocontrollerPixels`) requires only a new class conforming to the interface, with no show-engine changes.
- This is the single most important architectural constraint. It must be enforced consistently.

### Consequences

- Simulated implementations must faithfully model the real hardware's event behavior, or tests will pass but real behavior will differ.

---

## ADR-008 — Cue Definitions: External YAML (not embedded Python)

**Status:** Accepted
**Date:** 2026-09-13

### Context

Show routines (WHEN event IF condition THEN actions) must be editable without modifying Python source code. A future web UI must be able to read and write them.

### Decision

Cue definitions are stored as YAML files, loaded at runtime. The cue engine interprets them; no Python code is embedded in cue definitions.

### Rationale

- YAML cue files can be edited by a show designer without Python knowledge.
- A future web-based routine builder can read and write this format.
- The data model is version-controlled separately from application code.
- Conditions are evaluated using a restricted expression evaluator (not `eval`) to prevent arbitrary code execution.

### Schema Note

The cue schema (trigger/condition/action/priority/cooldown) is designed to be the stable data model that a future node-based visual editor will manipulate. The schema should be treated as a public interface from day one.

---

## ADR-009 — Raspberry Pi vs Microcontroller: RPi Direct (Initial)

**Status:** Accepted
**Date:** 2026-09-13

### Context

The spec requires evaluating whether GPIO, NeoPixels, and relays should be driven directly from the Raspberry Pi or delegated to a dedicated microcontroller (Arduino, RP2040, or ESP32).

### Decision

Drive all outputs directly from the Raspberry Pi through at least Milestones 1–3. Re-evaluate based on observed reliability before Milestone 4.

### Rationale

**Timing requirements of a parade float do not justify MCU complexity:**
- The turntable revolves at human-visible RPM (estimate: 1–30 RPM). At 30 RPM, 10 ms timing jitter is 0.18° of angular error — imperceptible.
- `rpi_ws281x` uses DMA for WS281x output, bypassing the Linux scheduler for pixel timing. This is adequate for the expected strip lengths.
- Software debouncing at 20 ms is appropriate for a mechanical microswitch.

**MCU adds significant costs:**
- Second codebase (C/C++ firmware).
- Serial protocol design and maintenance.
- Additional hardware failure point (MCU + cable + UART/USB).
- Firmware flashing procedure during parade day.
- More complex debugging when something goes wrong at midnight before a parade.

**The interface abstractions preserve the option:**
- `PixelInterface`, `RelayInterface`, and `GPIOInterface` are already in place.
- If MCU becomes necessary, `MicrocontrollerPixels`, `MicrocontrollerRelays`, and `MicrocontrollerGPIO` can be added without touching the show engine.

### Triggers for Revisiting

- `rpi_ws281x` proves unreliable for the actual LED strip count/type under parade conditions (vibration, power noise).
- GPIO jitter causes visible show synchronization failures in practice.
- A hardware watchdog becomes necessary for safety-critical relay outputs.

---

## ADR-010 — Event Bus: In-Process Async Pub/Sub (not external broker)

**Status:** Accepted
**Date:** 2026-09-13

### Context

The system needs an event bus to decouple hardware drivers from show logic. External brokers (Redis Pub/Sub, NATS, MQTT) exist and are commonly used.

### Decision

Implement a lightweight in-process async pub/sub in `core/event_bus.py`. No external message broker.

### Rationale

- The spec explicitly prohibits unnecessary infrastructure.
- The system must operate offline; external brokers introduce a network dependency and failure mode.
- All show logic runs in one process on one host; an in-process bus has zero network overhead.
- An asyncio-based pub/sub is ~50 lines of code and has no dependencies.
- Migrating to an external broker later is straightforward if multi-process or multi-host distribution becomes necessary.

---

## ADR-011 — DMX Failure Behavior: Hold Last Look (Default)

**Status:** Accepted
**Date:** 2026-09-13

### Context

If the Art-Net node loses network connectivity or the application crashes, the DMX node will stop receiving packets. The DMX node must do something with its outputs. The choice is: go to blackout or hold last look.

### Decision

Default to **hold last look** on Art-Net node loss. Configurable per universe.

### Rationale

- A parade float driving through a crowd should not suddenly go dark if there is a brief Wi-Fi hiccup or network glitch.
- Hold last look maintains the last intended lighting state until the connection recovers.
- Blackout is available as a configuration option for universes where this is the safer choice (e.g., a hazardous effect universe).
- The DMX-AN2's own node-loss behavior (hold vs. blackout) must be confirmed from the manufacturer's documentation and configured to match this intent.

### Consequences

- If the application crashes while a hazardous effect is active (relay open, spark machine triggered), hold-last-look would maintain that state. This is why hazardous effects must use relay outputs with physically enforced time limits (relay de-energizes after maximum duration regardless of software state).

---

## ADR-012 — Safety Architecture: Hardware E-Stop is Authoritative

**Status:** Accepted
**Date:** 2026-09-13

### Context

The spec requires an emergency stop system. The question is whether the software or hardware is responsible for the safety behavior.

### Decision

The physical emergency-stop circuit is authoritative and operates independently of software. Software monitors e-stop state and responds (cancels cues, sets safe state, updates UI) but is NOT the mechanism that removes power from hazardous loads.

### Rationale

- Software running on Linux is not a deterministic real-time system. It can crash, freeze, deadlock, or be delayed by the scheduler.
- A normally-closed e-stop loop that de-energizes a safety relay is fail-safe: any break in the loop (cut wire, button press, power loss) removes power from show loads.
- This is the standard practice for any system with potentially hazardous outputs (cold spark machines, high-current loads, mechanical movement).
- See SAFETY.md for the hardware architecture specification.

### Consequences

- "Show power" (all effects, high-current loads) is on a separate circuit controlled by the safety relay.
- "Controller power" (Raspberry Pi, network switch, DMX node) remains powered through the e-stop to allow the system to communicate its state and accept a reset.
- Software e-stop handling improves user experience and provides additional protection but is never the sole safety mechanism.

---

## ADR-013 — Fixture Profiles: YAML, Derived from Manufacturer Documentation Only

**Status:** Accepted
**Date:** 2026-09-13

### Context

DMX fixtures have manufacturer-defined channel layouts. These must be correct for the software to control fixtures properly.

### Decision

Fixture profiles are YAML files in `fixture_profiles/`. Channel maps are transcribed from official manufacturer documentation. No channel assignments are invented or estimated.

### Rationale

- An incorrect channel map can cause unexpected behavior: sending intensity values to a strobe channel, triggering macros unintentionally, or failing to produce expected colors.
- Manufacturer documentation is authoritative. Training-data estimates are insufficient.
- The Rockville RockWedge LED channel map must be confirmed from the physical manual before the fixture profile is written.

### Consequences

- The RockWedge fixture profile cannot be implemented until the physical manual is obtained. This is a known blocker for Milestone 1 fixture testing.
- Profiles should include a `source` field citing the document and revision used.

---

## ADR-014 — Single Process Architecture

**Status:** Accepted
**Date:** 2026-09-13

### Context

The system could be designed as multiple cooperating processes (separate web server, show engine, DMX worker, etc.) or as a single process with internal concurrency.

### Decision

Single Python process with asyncio concurrency. All subsystems share the same event loop and in-process event bus.

### Rationale

- A parade float runs on a single Raspberry Pi. Inter-process communication adds latency and complexity.
- asyncio Tasks provide sufficient concurrency isolation between subsystems.
- Single-process startup, shutdown, and error handling is vastly simpler than an orchestrated multi-process system.
- The spec explicitly prohibits unnecessary infrastructure; multiple processes imply process supervision (systemd units, supervisor, etc.).

### Consequences

- All subsystem code runs in the same address space. Bugs in one subsystem can theoretically affect others. Mitigated by clear module boundaries and thorough testing.
- If the process crashes, all subsystems stop simultaneously — which is acceptable given the hardware safety architecture (physical e-stop, relay safe states).

---

## ADR-015 — Pi Hardware Drivers: lgpio for GPIO/Relays, SPI for NeoPixels

**Status:** Accepted
**Date:** 2026-09-27

### Context

Milestone 2 needs real drivers for GPIO inputs, relay outputs and WS2812B NeoPixels on a Raspberry Pi 3 running Debian 13. `RPi.GPIO` is deprecated there. The usual NeoPixel library (`rpi_ws281x`) drives PWM on GPIO12/18, which needs root and conflicts with the Pi 3's on-board audio.

### Decision

- GPIO inputs and relays use **`lgpio`** directly (`/dev/gpiochipN`), with kernel-side debounce and edge callbacks handed to the asyncio loop via `call_soon_threadsafe`.
- NeoPixels use **SPI0 MOSI (GPIO10) via `spidev`**. Each WS2812 bit is encoded as one SPI byte at ~6.4 MHz; `core_freq=250` pins the Pi 3's SPI clock.
- Both libraries come from apt (`python3-lgpio`, `python3-spidev`); the venv is created with `--system-site-packages`. They are imported lazily, so macOS development is unaffected.

### Rationale

- lgpio is the maintained Pi GPIO library on current Raspberry Pi OS. gpiozero would only add a layer over it here.
- SPI needs no root, no DMA channel and no audio changes, and the byte-per-bit encoding ends every byte low, so gaps between SPI bytes are harmless.
- apt packages avoid building C extensions inside the venv on the Pi.

### Consequences

- The strip must be on GPIO10; GPIO8/9/11 are reserved by SPI0.
- Strips longer than ~160 pixels need a larger `spidev.bufsiz` kernel parameter.
- Pending decision P-5 (relay driver hardware) is partly resolved: GPIO18 drives a high-trigger relay module; whether it switches the motor directly or through a contactor depends on the motor data (WIRING_GUIDE Part 7).

---

## ADR-016 — WiFi Access Point: hostapd, not NetworkManager's Hotspot

**Status:** Accepted
**Date:** 2026-10-02

### Context

The iPad controls the float over the Pi's own WiFi network on `wlan0`. NetworkManager (which manages the Pi's other ports) has a built-in hotspot mode. On this Pi 3 Model B (BCM43430 WiFi, Debian 13, NetworkManager 1.52, wpa_supplicant 2.10) it failed: phones reported "incorrect password" with the correct password. Debug logs showed the phone's password proof (4-way handshake message 2) verified, then the phone left right after message 3. NetworkManager always configures `key_mgmt=WPA-PSK WPA-PSK-SHA256` (also with `pmf disable`), the chip has no AES-CMAC/MFP support, and the security description in message 3 then disagrees with what the chip broadcasts.

### Decision

- **hostapd** runs `wlan0` as the access point with plain WPA2-PSK / CCMP only, channel 6, country US.
- `parade-ap-network.service` sets `10.0.0.1/24` on `wlan0` and runs dnsmasq for DHCP only (no DNS, no NAT).
- NetworkManager ignores `wlan0` (`unmanaged-devices`) and keeps managing `eth0` (Mac cable, DHCP) and `eth1` (Art-Net).
- `scripts/pi-ap.sh` sets all of this up; the password lives in root-only `/etc/parade/ap.env`, never in git.

### Rationale

- hostapd is the standard, long-proven access point for Raspberry Pis and lets us choose the exact security settings.
- NetworkManager has no setting that removes WPA-PSK-SHA256.
- The Pi gets internet over the Mac cable, so `wlan0` doesn't need to switch to home WiFi for updates.

### Consequences

- `wlan0` no longer falls back to home WiFi. `bash scripts/pi-ap.sh --undo` hands it back to NetworkManager if needed.
- The iPad gets no internet through the Pi (not needed for the show).
- Recovery uses `sudo systemctl restart hostapd parade-ap-network`, not `nmcli con up parade-ap` (docs/NETWORK_RECOVERY.md).

---

## ADR-017 — Status Lights: BlinkStick Nano via pyusb

**Status:** Accepted
**Date:** 2026-10-02

### Context

With the lid on, there's no way to see the system state or whether the Pi is healthy without a phone on the dashboard. Two BlinkStick Nanos (USB, two RGB LEDs each) are plugged into the Pi; only one LED per stick faces up through the lid.

### Decision

- One stick shows the system state, the other Pi power/thermal health with a slow heartbeat pulse. Colours follow the dashboard's state pill.
- The driver talks to the sticks directly with **pyusb** (apt `python3-usb`, imported lazily), one USB control transfer per LED. It doesn't use the `blinkstick` PyPI package.
- Sticks are matched by serial number. A missing or unplugged stick is retried every 5 s, and unchanged LEDs are rewritten every second so a re-plugged stick catches up.
- Indicator only: the lights read state, nothing reads the lights, and any USB error is logged and ignored.

### Rationale

- The `blinkstick` package (1.2.0) declares only a Windows dependency, so it doesn't install `pyusb` on Linux, and it pulls in more than the one report we need.
- The heartbeat makes a hung or crashed app visible. Without it, a BlinkStick keeps showing its last colour.

### Consequences

- Non-root access needs a udev rule for USB ID `20a0:41e5` (group `plugdev`), installed by `scripts/pi-setup.sh`.
- On a clean shutdown the LEDs go dark. After a crash the state LED keeps its last colour, but the health LED stops pulsing.

---

## Pending Decisions

The following decisions cannot be made until more hardware information is available.

| # | Decision | Blocked By |
|---|---|---|
| P-1 | Angular position sensing: single microswitch vs. encoder vs. multiple sensors | Turntable speed range and required angular resolution unknown |
| P-2 | NeoPixel power architecture: single injection point vs. distributed | Strip count, layout, and power supply topology unknown |
| P-3 | MCU communication protocol (if MCU is added) | MCU hardware selection; reliability testing results |
| P-4 | Cold spark machine control interface | Machine make/model and manufacturer documentation needed |
| P-5 | Relay driver hardware selection | Load types, current requirements, isolation needs unknown |
| P-6 | Network topology: dedicated switch vs. router | Infrastructure constraints on float unknown |
