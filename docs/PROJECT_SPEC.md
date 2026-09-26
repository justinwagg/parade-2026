# Parade Float Show-Control System

You are the senior software engineer, embedded systems engineer, controls engineer, and system architect for this project.

We are building a reusable show-control platform for an elaborate parade float. The system will coordinate DMX lighting, addressable LED lighting, physical sensors, relays, mechanical events, and operator controls.

This is not merely a one-off script. The immediate objective is a working proof of concept, but the architecture should allow the system to evolve into a reusable platform for future parade floats and other interactive lighting projects.

Your responsibilities include helping design the architecture, writing the software, documenting the hardware/software interfaces, identifying reliability and safety concerns, building test/simulation infrastructure, and questioning design decisions when there is a substantially better approach.

Do not blindly implement my ideas exactly as stated. Treat my requirements as design intent. If there is a more robust, maintainable, safer, or simpler architecture, explain it and recommend it.

---

# 1. Project Overview

The float will contain several classes of controllable devices:

1. DMX lighting
2. Individually addressable NeoPixel/WS281x-style LEDs
3. GPIO sensors such as microswitches
4. Relays controlling approved external devices
5. Potentially other sensors and actuators added later
6. A web-based operator/configuration interface
7. Mechanical elements whose position or movement can trigger show events

The primary controller will preferably be a Raspberry Pi.

Development will initially occur on a Mac, so the software architecture MUST allow development, testing, and simulation without Raspberry Pi hardware attached.

The system must therefore separate show logic from hardware-specific implementations.

---

# 2. Current Hardware

## DMX

The current DMX interface is a Chauvet DMX-AN2 Ethernet/DMX node.

The application should communicate with the DMX-AN2 over the network using an appropriate supported protocol such as Art-Net or sACN.

Do not hard-code the system around one fixture or one DMX universe.

The eventual float may contain dozens of DMX fixtures with different fixture types, addresses, channel layouts, and operating modes.

Initially, however, I will test with:

Mac or Raspberry Pi
→ Ethernet
→ DMX-AN2
→ wired DMX cable
→ one DMX fixture

Later this may become:

Raspberry Pi
→ Ethernet
→ DMX-AN2
→ wireless DMX transmitter
→ multiple wireless DMX receivers
→ multiple lighting fixtures

One likely fixture type is a Rockville RockWedge LED, but fixture definitions must be configurable rather than embedded directly into application logic.

The system should eventually support fixture profiles defining things such as:

* fixture name
* universe
* DMX starting address
* channel count
* channel definitions
* operating mode
* RGB/RGBW/etc.
* dimmer
* strobe
* macros or fixture-specific functions

Do not invent a fixture's DMX channel mapping. Use manufacturer documentation when implementing fixture profiles.

---

# 3. Physical Float Example

The 2026 float includes a revolving turntable carrying a phone booth.

A microswitch or similar sensor will provide an index/home signal when the booth reaches a known point during each revolution.

The system must be capable of:

* detecting that signal
* debouncing the switch
* counting revolutions
* recording timestamps
* determining rotational period/RPM if useful
* triggering events every revolution or every N revolutions
* enforcing cooldown/retrigger protection
* detecting potentially abnormal sensor behavior

Do not assume that one microswitch provides continuous angular position.

A single switch provides a known reference/index position. If effects later need reliable triggering at arbitrary positions such as 90°, 180°, or 270°, evaluate alternatives such as an encoder, Hall-effect sensors, proximity sensors, or multiple reference sensors.

Design the software so a better position sensor could be added later without rewriting the show engine.

---

# 4. NeoPixel Lighting

The phone booth will contain multiple addressable LED strips or groups.

The system should support effects such as:

* solid colors
* fades
* chases
* pulses
* flashes
* color wipes
* gradients
* animations
* configurable brightness
* groups/zones
* synchronized effects
* timed effects

Effects should not be tightly coupled to one physical strip.

Create an abstraction where logical LED zones can map to physical pixel ranges.

Examples might eventually include:

phone_booth_front
phone_booth_left
phone_booth_right
phone_booth_roof
float_perimeter

The show engine should be able to issue commands such as:

set zone X to blue
fade zone X from blue to white over 2 seconds
run animation Y on zone Z
stop animation
blackout all LED zones

Evaluate whether driving large numbers of NeoPixels directly from the Raspberry Pi is the best production architecture.

Specifically compare:

1. Raspberry Pi directly controlling NeoPixels
2. Raspberry Pi acting as show controller while a dedicated Arduino/RP2040/ESP32 handles deterministic NeoPixel output and possibly GPIO/relay I/O

Favor reliability over architectural simplicity if the difference is meaningful.

---

# 5. GPIO Inputs and Sensors

GPIO inputs may include:

* rotation/index microswitch
* operator buttons
* limit switches
* future Hall-effect sensors
* future encoders
* future proximity sensors
* an emergency-stop status signal

GPIO handling should support:

* configurable pins
* active-high or active-low inputs
* pull-up/pull-down configuration
* hardware/software debouncing
* edge detection
* timestamps
* state changes
* event publication
* simulated GPIO when running on a Mac

Do not embed business/show logic directly inside GPIO callbacks.

GPIO changes should become events consumed by the central show-control/event system.

---

# 6. Outputs and Relays

The system may operate relays used to signal or power approved devices.

Relay outputs should support:

* configurable pins
* active-high/active-low operation
* momentary activation
* timed activation
* latched state when appropriate
* safe startup state
* safe shutdown state
* manual control
* show-controlled operation

The software must NEVER assume that directly switching a load from Raspberry Pi GPIO is acceptable.

Hardware interfaces must account for proper relay drivers, isolation where appropriate, current requirements, inductive-load protection, voltage-domain separation, fusing, and appropriate power distribution.

Do not recommend bypassing manufacturer safety systems or interlocks.

---

# 7. Cold Spark / Special Effects

One possible output device is a cold-spark effect machine.

Treat special-effects devices as potentially hazardous equipment.

The application may trigger a device ONLY through an interface explicitly supported by the device manufacturer, such as documented DMX control, dry-contact triggering, or another approved control interface.

Never propose bypassing manufacturer interlocks or directly modifying safety circuitry.

The software design should support an explicit ARMED / DISARMED state for potentially hazardous effects.

Consider requiring all of the following before a hazardous effect can fire:

system healthy
AND effect armed
AND operator enable present
AND no emergency-stop condition
AND trigger condition satisfied

The exact safety requirements must ultimately follow the equipment manufacturer's documentation and applicable event/fire-safety requirements.

---

# 8. Emergency Stop and Safety Architecture

This is a critical requirement.

DO NOT design the emergency stop as a Raspberry Pi GPIO button whose safety behavior depends upon Linux, Python, the network, or this application functioning.

The emergency-stop system must be fundamentally hardware-based and fail-safe.

The software may MONITOR emergency-stop state through GPIO and respond appropriately, but software must not be the only mechanism responsible for removing hazardous power.

Evaluate a hardware architecture using concepts such as:

* normally-closed emergency-stop loop
* de-energize-to-safe behavior
* appropriately rated contactor or safety relay
* deliberate/manual reset after activation
* physical mushroom emergency-stop button
* clear ARMED/SAFE indication

Separate SHOW POWER from any vehicle systems that must remain powered for safe control of the float.

The show controller must never inadvertently disable steering, braking, or other safety-critical vehicle functions.

When an emergency stop occurs, software should also:

* stop active show routines
* inhibit new triggers
* stop hazardous effects
* place lighting/effects into a defined safe state
* log the event
* clearly display the emergency state in the UI

The physical emergency-stop circuit remains authoritative.

---

# 9. Central Architectural Concept: Events + Actions + Cues

Design the software around a central show-control engine.

Hardware devices should generate EVENTS.

Examples:

rotation_index
revolution_count_changed
button_pressed
gpio_changed
timer_elapsed
show_started
operator_trigger
emergency_stop
sensor_fault

The show-control engine evaluates these events and executes ACTIONS.

Examples:

set_dmx_scene
fade_dmx_scene
start_led_effect
stop_led_effect
set_relay
pulse_relay
start_cue
cancel_cue
blackout

A CUE or ROUTINE should be a reusable sequence or collection of actions.

For example:

WHEN rotation_index occurs
AND revolution_count modulo 3 == 0

THEN:

start DMX scene "phone_booth_flash"
start NeoPixel effect "time_travel"
wait 750 ms
pulse relay "approved_effect_trigger" for 250 ms
fade DMX scene to "normal" over 2 seconds

This logic MUST NOT require editing Python source code for every routine.

Design a declarative representation for routines, such as JSON or YAML, and eventually allow the web interface to create and edit this representation.

---

# 10. Timing and Concurrency

Multiple things may happen simultaneously.

The system must therefore handle concurrency intentionally.

For example:

NeoPixels may already be running an animation while DMX performs a fade and a sensor fires another event.

Do not implement show sequences as long blocking chains of `sleep()` calls.

Prefer asynchronous/non-blocking scheduling.

The system should have clearly defined behavior for:

* simultaneous cues
* overlapping effects
* cue cancellation
* higher-priority cues
* blackout
* emergency stop
* manual operator overrides
* repeated sensor triggers
* stale events

Consider using an event bus and asynchronous task scheduler.

Explain the chosen concurrency model.

---

# 11. State Machine

Model important system state explicitly.

At minimum consider states such as:

BOOTING
SAFE
READY
ARMED
RUNNING
PAUSED
EMERGENCY_STOP
FAULT

Do not scatter boolean variables such as `is_running`, `is_armed`, and `estop` throughout unrelated code.

There should be a clear system-state model with documented transitions.

Hazardous outputs must default to disabled after startup or restart.

---

# 12. DMX Show Engine

The DMX subsystem should support:

* multiple universes
* configurable fixtures
* fixture profiles
* DMX addressing
* scenes
* fades
* transitions
* fixture groups
* master intensity
* blackout
* manual channel testing
* live channel inspection
* future expansion

A scene should describe intent rather than require raw DMX values everywhere.

For example:

scene: phone_booth_blue
fixtures:
booth_left:
color: blue
intensity: 100
booth_right:
color: blue
intensity: 100

Fixture profiles should translate these semantic values into actual DMX channel values when possible.

Raw channel control should still be available for testing/debugging.

---

# 13. Web Interface

Build toward a browser-based operator interface.

The interface should eventually include:

## Dashboard

Show:

* system state
* controller status
* DMX node connectivity
* DMX output status
* GPIO states
* revolution count
* estimated RPM
* NeoPixel controller status
* relay states
* emergency-stop state
* active cues
* recent events
* faults/warnings

## Manual Control

Allow authorized manual testing of:

* DMX fixtures
* DMX channels
* scenes
* NeoPixel zones
* NeoPixel animations
* safe relay outputs
* sensor simulation

Potentially hazardous effects must have additional safeguards.

## Fixture Configuration

Allow configuration of:

* universe
* address
* fixture profile
* fixture name
* group

## Routine Builder

Eventually provide a graphical or form-based way to construct:

WHEN [event]
IF [optional conditions]
THEN [actions]

Example:

WHEN rotation_index
IF revolution_count % 3 == 0
THEN
DMX scene = lightning
LED effect = portal
relay spark_trigger = pulse 250ms

The UI does not need to become a full professional theatrical lighting console.

Keep it understandable and appropriate for a custom parade float.

---

# 14. Simulation Mode

This is extremely important.

The entire application must be usable on my Mac before Raspberry Pi hardware exists.

Create a hardware abstraction layer with real and simulated implementations.

For example:

GPIOInterface
RaspberryPiGPIO
SimulatedGPIO

DMXInterface
ArtNetDMX
SimulatedDMX

PixelInterface
RaspberryPiPixels
MicrocontrollerPixels
SimulatedPixels

RelayInterface
RaspberryPiRelays
MicrocontrollerRelays
SimulatedRelays

Simulation mode should allow the UI to:

* toggle simulated microswitches
* generate rotations
* change simulated RPM
* trigger events
* inspect DMX channel output
* visualize NeoPixel states
* inspect relay states
* test cues
* test failure scenarios
* test emergency-stop behavior

I want to be able to develop most show logic without the physical float.

---

# 15. Visual Show Designer

A major long-term goal is an interactive routine designer.

Explore ways to visualize:

EVENT
↓
CONDITION
↓
ACTION
↓
DELAY
↓
ACTION

A node-based editor may eventually make sense, but do not over-engineer this in the first version.

First establish a clean cue/event schema that a future graphical editor can manipulate.

The data model is more important than the visual editor initially.

---

# 16. Logging and Diagnostics

The parade environment will make debugging difficult.

Log meaningful events including:

* application startup
* hardware initialization
* network connectivity
* DMX connectivity/state
* sensor transitions
* revolution events
* cue starts
* cue completion
* cue cancellation
* relay activation
* faults
* emergency stop
* operator actions

Use timestamps.

Provide a useful diagnostic/event screen in the interface.

Avoid logging high-frequency data so aggressively that logs become unusable.

---

# 17. Failure Modes

Design intentionally for failure.

Document expected behavior if:

* the application crashes
* Raspberry Pi reboots
* network connection to the DMX node disappears
* DMX output stops
* a microcontroller disconnects
* a microswitch becomes stuck
* a sensor starts bouncing excessively
* a relay controller disconnects
* NeoPixel communication fails
* configuration is invalid
* two conflicting cues run
* an emergency stop occurs

For DMX specifically, decide explicitly whether loss of control should result in blackout, hold-last-look, or another defined state based on the use case.

Do not leave failure behavior accidental.

---

# 18. Hardware Reliability

Assume this system will operate on a moving parade float with:

* vibration
* electrical noise
* motors
* generators/inverters or batteries
* long wire runs
* high-current LED loads
* potentially unreliable wireless links
* weather exposure
* people physically interacting with equipment

When hardware design becomes relevant, proactively identify concerns involving:

* power distribution
* grounding
* common grounds where required
* ground loops
* wire gauge
* connectors
* strain relief
* fusing
* transient suppression
* voltage regulation
* level shifting
* NeoPixel power injection
* electromagnetic interference
* relay isolation
* cable routing
* DMX termination
* weather protection
* thermal management

Do not assume breadboard-style wiring is appropriate for production use.

---

# 19. Configuration

Avoid hard-coding hardware configuration.

Eventually configuration should describe things such as:

controllers
DMX universes
fixtures
fixture addresses
GPIO inputs
relay outputs
LED zones
sensors
cue definitions
safety configuration

Prefer a human-readable configuration format.

Validate configuration at application startup and report useful errors.

---

# 20. Development Philosophy

Use modular architecture.

Prefer clean interfaces and small components over a giant application file.

Keep these concerns separate:

* web/API layer
* show engine
* event system
* cue scheduler
* DMX subsystem
* GPIO subsystem
* NeoPixel subsystem
* relay subsystem
* configuration
* hardware abstraction
* safety state
* simulation
* logging

Hardware-specific code must not leak throughout application logic.

Use dependency injection or another sensible mechanism so simulated hardware can replace real hardware.

Write tests for show logic independently from actual hardware.

Favor boring, well-supported technologies over unnecessary complexity.

Do not introduce Docker, Kubernetes, cloud dependencies, databases, message brokers, or other infrastructure unless there is a concrete reason.

The finished parade system should be capable of operating completely offline on its own local network.

---

# 21. Raspberry Pi vs Microcontroller Responsibilities

Before finalizing the architecture, explicitly evaluate whether the Raspberry Pi should directly handle:

* sensors
* relays
* NeoPixels

or whether these real-time responsibilities should be delegated to a microcontroller.

A likely architecture worth evaluating is:

Raspberry Pi

* application server
* web UI
* cue engine
* event engine
* DMX / Art-Net
* configuration
* logging
* operator interface

Microcontroller

* deterministic GPIO
* switch/encoder reading
* NeoPixel generation
* relay outputs
* hardware watchdog
* communication with Pi

Possible Pi-to-microcontroller transports might include USB serial, UART, Ethernet, or another suitable mechanism.

Do not choose one simply because it sounds sophisticated. Compare complexity, latency, reliability, development effort, and failure behavior.

---

# 22. Repository Documentation

Maintain living documentation in the repository.

At minimum create and maintain:

README.md
ARCHITECTURE.md
HARDWARE.md
SAFETY.md
CONFIGURATION.md
TESTING.md

ARCHITECTURE.md should explain the system at a level that allows another engineer to understand how everything interacts.

HARDWARE.md should document actual hardware connections as they become known.

SAFETY.md should clearly distinguish software safety behavior from hardware safety mechanisms.

Do not invent pin assignments, electrical ratings, DMX maps, or hardware connections that have not yet been decided.

Mark unknowns explicitly.

---

# 23. Working With Me

Treat this as an iterative engineering project.

When I propose hardware or software changes:

1. determine how they fit the existing architecture
2. identify important risks or conflicts
3. recommend an approach
4. update documentation
5. then implement

Do not rewrite functioning architecture unnecessarily.

When you discover architectural knowledge that should survive the current conversation, capture it in the repository documentation.

When assumptions are necessary, state them clearly.

Ask me for hardware-specific information when it actually blocks implementation, especially:

* fixture manuals
* pin assignments
* voltage/current requirements
* relay specifications
* sensor types
* motor/controller details
* NeoPixel quantity
* power supply information

Do not fabricate those details.

---

# 24. Immediate Milestone

Do NOT attempt to build the complete float-control system first.

The first milestone is deliberately narrow:

Mac
→ Ethernet
→ DMX-AN2
→ one wired DMX fixture

Build a proof of concept that allows me to:

1. start the application on my Mac
2. configure the DMX-AN2 network destination and universe
3. configure one fixture
4. manually change its DMX channels
5. create a basic scene
6. activate that scene from the application
7. fade between two scenes
8. view the outgoing DMX values
9. simulate a GPIO event
10. have that simulated event trigger a DMX scene

This proof of concept should establish the architecture that later GPIO, NeoPixels, relays, sensors, and physical show controls will use.

Do not prematurely implement Raspberry Pi-specific hardware code merely to demonstrate progress.

---

# 25. First Task

Before writing significant application code, analyze this specification and produce:

1. a proposed system architecture
2. a component diagram
3. recommended technology stack
4. proposed repository structure
5. event/cue data model
6. hardware abstraction strategy
7. simulation strategy
8. safety architecture
9. Raspberry Pi versus microcontroller recommendation
10. initial development milestones
11. important unanswered questions
12. risks or design issues you believe I have overlooked

For each major architectural decision, explain WHY you recommend it.

Then create or update ARCHITECTURE.md with the agreed design.

After that, begin only the first proof-of-concept milestone.

Do not skip directly to implementing the complete system.
