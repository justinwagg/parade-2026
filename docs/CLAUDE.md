# Parade Float Show Control

This repository contains a reusable show-control platform for parade floats.

Read `docs/PROJECT_SPEC.md` before making architectural changes.

## Core Principles

- The Raspberry Pi is the show controller, not the safety controller.
- Physical emergency-stop functionality must remain hardware-based and fail-safe.
- Never bypass manufacturer safety systems or interlocks.
- Never invent electrical ratings, GPIO assignments, fixture DMX maps, or hardware capabilities.
- Manufacturer documentation is authoritative for hardware behavior.
- Hardware-specific functionality must sit behind interfaces that have simulated implementations.
- The complete application must be developable and testable on macOS without physical hardware attached.
- Show logic must be event/action/cue based rather than embedded directly in hardware callbacks.
- Avoid blocking sleeps in show-control logic.
- Configuration belongs in configuration files, not source code.
- Do not implement features beyond the current milestone unless needed for its architecture.
- Prefer simple, maintainable technology over unnecessary infrastructure.

## Workflow

Before implementing a substantial change:

1. Read the relevant documentation.
2. Inspect the existing implementation and tests.
3. Explain any architectural change that is required.
4. Implement the smallest complete solution.
5. Run appropriate automated tests.
6. Update documentation when behavior or architecture changes.
7. Update `docs/STATUS.md` when a milestone materially advances.

## Project Documentation

- Requirements: `docs/PROJECT_SPEC.md`
- Architecture: `docs/ARCHITECTURE.md`
- Hardware inventory/wiring: `docs/HARDWARE.md`
- Safety architecture: `docs/SAFETY.md`
- Architectural decisions: `docs/DECISIONS.md`
- Testing strategy: `docs/TESTING.md`
- Current project state: `docs/STATUS.md`

## Hardware

Consult documentation in `hardware/manuals/` before implementing hardware-specific behavior.

If required hardware information is missing, identify the missing information rather than guessing.

## Git

- Keep changes focused on the current task.
- Do not rewrite unrelated working code.
- Do not remove tests simply to make a change pass.
- Review `git diff` before considering work complete.