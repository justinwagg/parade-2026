"""Bench checks for wiring, using the same drivers as the app.

    parade-hwcheck inputs                 watch every gpio input, print changes
    parade-hwcheck relay [ID] [--seconds N]   relay ON for N s, then off
    parade-hwcheck pixels test            R, G, B, white, chase, off
    parade-hwcheck pixels color R G B [--seconds N]
    parade-hwcheck pixels ... --order GRBW    try a colour order without editing the config

Stop the service first (sudo systemctl stop parade); the pins can only be
claimed by one process. Pin numbers, pulls and polarity come from the config.
"""
import argparse
import asyncio
import subprocess
import time
from pathlib import Path

from parade.config.loader import load_config
from parade.core.event_bus import EventBus


def _service_running() -> bool:
    try:
        return subprocess.run(
            ["systemctl", "is-active", "--quiet", "parade"], check=False
        ).returncode == 0
    except FileNotFoundError:
        return False


async def check_inputs(config) -> None:
    from parade.gpio.rpi import RPiGPIO

    bus = EventBus()
    gpio = RPiGPIO(config.gpio_inputs, bus, chip=config.hardware.gpio_chip)
    cfgs = {c.id: c for c in config.gpio_inputs}
    t0 = time.monotonic()

    async def on_change(ev):
        c = cfgs[ev.pin_id]
        print(
            f"{time.monotonic() - t0:8.3f}s  {ev.pin_id:<18} GPIO{c.pin:<3} "
            f"{'HIGH' if ev.state else 'low ':<4}  {'ACTIVE' if ev.active else 'idle'}",
            flush=True,
        )

    bus.subscribe("gpio_changed", on_change)
    await gpio.start()
    try:
        print("Current state:")
        phys = gpio.get_physical_states()
        for pid, c in cfgs.items():
            print(
                f"  {pid:<18} GPIO{c.pin:<3} {'HIGH' if phys[pid] else 'low ':<4}  "
                f"{'ACTIVE' if gpio.get_state(pid) else 'idle':<6}  ({c.description})"
            )
        print("\nWatching for changes. Press each switch; Ctrl-C to stop.\n", flush=True)
        await asyncio.Event().wait()
    finally:
        await gpio.stop()


async def check_relay(config, relay_id: str | None, seconds: float) -> None:
    from parade.relay.rpi import RPiRelay

    relays = {r.id: r for r in config.relay_outputs}
    relay_id = relay_id or next(iter(relays), None)
    if relay_id not in relays:
        raise SystemExit(f"Unknown relay {relay_id!r}. Configured: {', '.join(relays) or 'none'}")
    driver = RPiRelay(config.relay_outputs, chip=config.hardware.gpio_chip)
    # Honour the e-stop monitor like the app does: refuse to start while it is
    # pressed, and drop the relay (for good) the moment it is pressed.
    gpio = None
    estop = config.safety.estop_pin
    tripped = asyncio.Event()
    if estop:
        from parade.gpio.rpi import RPiGPIO

        bus = EventBus()

        async def on_change(ev):
            if ev.pin_id == estop and ev.active:
                tripped.set()

        bus.subscribe("gpio_changed", on_change)
        gpio = RPiGPIO(
            [c for c in config.gpio_inputs if c.id == estop], bus, chip=config.hardware.gpio_chip
        )
        await gpio.start()
        if gpio.get_state(estop):
            await gpio.stop()
            raise SystemExit("E-stop is pressed (or its monitor wire is open). Release it first.")
    else:
        print("WARNING: no safety.estop_pin configured; the e-stop is not being watched.")
    await driver.start()
    try:
        print(f"{relay_id} (GPIO{relays[relay_id].pin}) ON for {seconds:g}s ...", flush=True)
        await driver.set_relay(relay_id, True)
        try:
            await asyncio.wait_for(tripped.wait(), timeout=seconds)
            print("E-stop pressed: relay off", flush=True)
        except asyncio.TimeoutError:
            pass
    finally:
        await driver.stop()
        if gpio:
            await gpio.stop()
        print(f"{relay_id} off", flush=True)


async def check_pixels(config, mode: str, color: list[int] | None, seconds: float, order: str | None = None) -> None:
    from parade.pixels.rpi import RPiPixels

    if not config.pixel_strips:
        raise SystemExit("No pixel_strips configured")
    strip = config.pixel_strips[0]
    if order:
        strip = strip.model_copy(update={"color_order": order})
    px = RPiPixels(strip)
    await px.start()
    try:
        if mode == "color":
            print(f"{strip.id}: all {strip.count} pixels {tuple(color)} for {seconds:g}s", flush=True)
            await px.set_all(*color)
            await px.show()
            await asyncio.sleep(seconds)
            return
        for name, c in [("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255)), ("white", (255, 255, 255))]:
            print(f"{strip.id}: {name}", flush=True)
            await px.set_all(*c)
            await px.show()
            await asyncio.sleep(1.5)
        print(f"{strip.id}: chase (pixel 0 → {strip.count - 1})", flush=True)
        for i in range(strip.count):
            await px.set_all(0, 0, 0)
            await px.set_pixel(i, 255, 128, 0)
            await px.show()
            await asyncio.sleep(0.05)
    finally:
        await px.stop()
        print(f"{strip.id}: off", flush=True)


def main() -> None:
    base = Path(__file__).parents[3]
    parser = argparse.ArgumentParser(description="Parade hardware bench checks")
    parser.add_argument("--config", default=str(base / "config/default.yaml"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inputs", help="watch gpio inputs")
    r = sub.add_parser("relay", help="pulse a relay on")
    r.add_argument("relay_id", nargs="?")
    r.add_argument("--seconds", type=float, default=2.0)
    p = sub.add_parser("pixels", help="drive the NeoPixel strip")
    p.add_argument("mode", choices=["test", "color"])
    p.add_argument("rgb", nargs="*", type=int)
    p.add_argument("--seconds", type=float, default=5.0)
    p.add_argument("--order", help="override color_order, e.g. GRBW or RGBW")
    args = parser.parse_args()

    if _service_running():
        raise SystemExit("The parade service is running and owns the pins. Stop it first: sudo systemctl stop parade")
    config = load_config(Path(args.config))

    try:
        if args.cmd == "inputs":
            asyncio.run(check_inputs(config))
        elif args.cmd == "relay":
            asyncio.run(check_relay(config, args.relay_id, args.seconds))
        else:
            if args.mode == "color" and (len(args.rgb) != 3 or not all(0 <= v <= 255 for v in args.rgb)):
                raise SystemExit("pixels color needs three values 0-255, e.g. pixels color 255 0 0")
            asyncio.run(check_pixels(config, args.mode, args.rgb, args.seconds, args.order))
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        raise SystemExit(f"Error: {e}")


if __name__ == "__main__":
    main()
