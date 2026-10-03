import asyncio
import logging
import time
from pathlib import Path
import uvicorn


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def run_dmx_output_loop(ctx):
    """Send DMX universe data to the node at the configured refresh rate."""
    from parade.config.models import ArtNetNodeConfig

    nodes: dict[str, ArtNetNodeConfig] = {
        n.id: n for n in ctx.config.network.artnet_nodes
    }
    universe_configs = {u.id: u for u in ctx.config.dmx.universes}
    logger = logging.getLogger(__name__)

    while True:
        for uid, universe in ctx.universes.items():
            ucfg = universe_configs.get(uid)
            if not ucfg:
                continue
            node = nodes.get(ucfg.node)
            if not node:
                continue
            data = universe.get_buffer()
            try:
                await ctx.dmx_driver.send_universe(uid, node.ip, node.port, data)
            except Exception as e:
                logger.warning("DMX send error: %s", e)
        # Sleep to maintain refresh rate (approximate across all universes)
        min_hz = min(
            (u.refresh_hz for u in universe_configs.values()), default=40
        )
        await asyncio.sleep(1.0 / min_hz)


def _build_log_entry(event) -> dict:
    import time as _time
    et = event.event_type
    if et == "gpio_changed":
        msg = f"GPIO {event.pin_id} → {'ACTIVE' if event.active else 'idle'}"
        tag = "gpio"
    elif et == "operator_trigger":
        msg = f"Operator trigger: {event.trigger_id}"
        tag = "operator"
    elif et == "cue_started":
        msg = f"Cue started: {event.cue_id}"
        tag = "cue"
    elif et == "cue_completed":
        msg = f"Cue completed: {event.cue_id}"
        tag = "cue"
    elif et == "cue_cancelled":
        msg = f"Cue cancelled: {event.cue_id}"
        tag = "cue"
    elif et == "system_state_changed":
        msg = f"State: {event.old_state} → {event.new_state}"
        tag = "system"
    elif et == "emergency_stop":
        msg = "EMERGENCY STOP: relays off, cues cancelled"
        tag = "safety"
    else:
        msg = et
        tag = "system"
    return {"ts": round(event.timestamp * 1000), "tag": tag, "msg": msg}


async def push_ws_updates(ctx):
    """Periodically push state + drained log entries to WebSocket clients."""
    import json
    from parade.api.routes.dashboard import state_snapshot

    while True:
        if ctx.ws_clients:
            state_msg = json.dumps({"type": "state", "data": state_snapshot(ctx)})
            # Drain log queue into a batch
            log_entries = list(ctx.event_log)
            ctx.event_log.clear()
            log_msg = json.dumps({"type": "log", "entries": log_entries}) if log_entries else None

            dead = []
            for ws in list(ctx.ws_clients):
                try:
                    await ws.send_text(state_msg)
                    if log_msg:
                        await ws.send_text(log_msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                ctx.ws_clients.remove(ws)
        # Push faster when a cue is running or in MANUAL so animations and
        # switch presses show up promptly in the dashboard
        fast = ctx.show_engine.active_cue or (ctx.manual and ctx.manual.active)
        await asyncio.sleep(0.1 if fast else 0.5)


async def async_main(
    config_path: Path, profiles_dir: Path, cues_dir: Path, port_override: int | None = None
) -> None:
    from parade.config.loader import load_config, load_fixture_profiles, load_cues, load_scenes
    from parade.core.event_bus import EventBus
    from parade.core.state import SystemStateMachine, SystemState
    from parade.dmx.universe import DMXUniverse
    from parade.dmx.fixtures import FixtureManager
    from parade.dmx.scenes import SceneManager
    from parade.core.engine import ShowEngine
    from parade.api.context import AppContext
    from parade.api.app import create_app
    from parade.health.power import PowerMonitor
    from parade.core.safety import SafetyMonitor
    from parade.core.manual import ManualController

    logger = logging.getLogger(__name__)

    # Load config
    config = load_config(config_path)
    profiles = load_fixture_profiles(profiles_dir)
    cues_data = load_cues(cues_dir)

    logger.info(
        "Loaded %d fixture profiles, %d cues", len(profiles), len(cues_data)
    )

    # Build DMX driver
    if config.hardware.dmx_driver == "artnet":
        from parade.dmx.artnet import ArtNetDMX
        dmx_driver = ArtNetDMX()
    else:
        from parade.dmx.simulated import SimulatedDMX
        dmx_driver = SimulatedDMX()

    await dmx_driver.start()

    # Build universes
    universes = {
        ucfg.id: DMXUniverse(ucfg.id, ucfg.refresh_hz)
        for ucfg in config.dmx.universes
    }

    # Build fixture manager
    fixture_manager = FixtureManager(profiles, config.fixtures)

    # Build scene manager and load scenes from config/scenes.yaml
    scene_manager = SceneManager(fixture_manager, universes)
    scenes_path = config_path.parent / "scenes.yaml"
    scenes_data = load_scenes(scenes_path)
    scene_manager.load_scenes(scenes_data)
    logger.info("Loaded %d scenes", len(scenes_data))

    # Build event bus and GPIO
    event_bus = EventBus()
    chip = config.hardware.gpio_chip
    if config.hardware.gpio_driver == "rpi":
        from parade.gpio.rpi import RPiGPIO
        gpio = RPiGPIO(config.gpio_inputs, event_bus, chip=chip)
    else:
        from parade.gpio.simulated import SimulatedGPIO
        gpio = SimulatedGPIO(config.gpio_inputs, event_bus)

    # Build relay manager
    if config.hardware.relay_driver == "rpi":
        from parade.relay.rpi import RPiRelay
        relay_manager = RPiRelay(config.relay_outputs, chip=chip)
    elif config.hardware.relay_driver == "simulated":
        from parade.relay.simulated import SimulatedRelay
        relay_manager = SimulatedRelay(config.relay_outputs)
    else:
        raise NotImplementedError(f"Relay driver {config.hardware.relay_driver!r} not implemented")

    # Build pixel manager
    from parade.config.models import PixelStripConfig
    strip = config.pixel_strips[0] if config.pixel_strips else PixelStripConfig(id="default", count=1)
    if config.hardware.pixel_driver == "rpi":
        if not config.pixel_strips:
            raise ValueError("pixel_driver is 'rpi' but no pixel_strips are configured")
        from parade.pixels.rpi import RPiPixels
        pixel_manager = RPiPixels(strip)
    elif config.hardware.pixel_driver == "simulated":
        from parade.pixels.simulated import SimulatedPixels
        pixel_manager = SimulatedPixels(strip)
    else:
        raise NotImplementedError(f"Pixel driver {config.hardware.pixel_driver!r} not implemented")

    # Relays first so they are driven off as early as possible.
    await relay_manager.start()
    await gpio.start()
    await pixel_manager.start()

    # Build state machine
    state_machine = SystemStateMachine()

    # Build show engine
    show_engine = ShowEngine(
        event_bus, scene_manager, cues_data,
        relay_manager=relay_manager,
        pixel_manager=pixel_manager,
        state_machine=state_machine,
        groups=config.fixture_groups,
    )
    if config.show.enabled:
        logger.info("Show sequencer enabled: cues are loaded but not run")
    else:
        await show_engine.start()

    # Assemble context (set ref so log handler can append)
    ctx = AppContext(
        config=config,
        event_bus=event_bus,
        state_machine=state_machine,
        dmx_driver=dmx_driver,
        universes=universes,
        fixture_manager=fixture_manager,
        scene_manager=scene_manager,
        gpio=gpio,
        relay_manager=relay_manager,
        pixel_manager=pixel_manager,
        show_engine=show_engine,
        cues_dir=cues_dir,
        config_path=config_path,
        profiles_dir=profiles_dir,
        power_monitor=PowerMonitor(),
        safety=SafetyMonitor(
            event_bus, state_machine, relay_manager, show_engine, gpio,
            config.safety.estop_pin,
        ),
    )

    ctx.manual = ManualController(event_bus, state_machine, relay_manager, pixel_manager, ctx.safety)
    await ctx.manual.start()

    # Wire event bus → log queue
    LOG_EVENT_TYPES = [
        "gpio_changed", "operator_trigger", "cue_started",
        "cue_completed", "cue_cancelled", "system_state_changed",
        "emergency_stop",
    ]

    def _make_log_handler(app_ctx_ref):
        async def _log_handler(event):
            app_ctx_ref[0].event_log.append(_build_log_entry(event))
        return _log_handler

    # Use a list as a mutable ref so the lambda can be assigned after ctx is built
    ctx_ref = [None]
    log_handler = _make_log_handler(ctx_ref)
    for etype in LOG_EVENT_TYPES:
        event_bus.subscribe(etype, log_handler)

    ctx_ref[0] = ctx

    # Transition to SAFE (boot complete)
    state_machine.transition(SystemState.SAFE)
    logger.info("System state: SAFE")
    await ctx.safety.start()  # trips immediately if the e-stop is already pressed

    # Create FastAPI app
    app = create_app(ctx)

    # Start background tasks
    output_task = asyncio.create_task(run_dmx_output_loop(ctx))
    ws_task = asyncio.create_task(push_ws_updates(ctx))

    def _log_power_change(severity: str, msg: str) -> None:
        ctx.event_log.append({"ts": round(time.time() * 1000), "tag": "power", "msg": msg})

    power_task = asyncio.create_task(ctx.power_monitor.run(_log_power_change))

    # Status lights (BlinkStick LEDs showing state + health). Indicator only.
    from parade.status_lights.controller import StatusLights
    sl_cfg = config.status_lights
    if config.hardware.status_light_driver == "blinkstick":
        from parade.status_lights.blinkstick import BlinkStickLights
        sl_driver = BlinkStickLights([l.serial for l in (sl_cfg.state_led, sl_cfg.health_led) if l])
    else:
        from parade.status_lights.simulated import SimulatedStatusLights
        sl_driver = SimulatedStatusLights()
    status_lights = StatusLights(sl_cfg, sl_driver, state_machine, ctx.power_monitor, event_bus)
    await status_lights.start()
    lights_task = asyncio.create_task(status_lights.run())

    # OLED status display (joining info, state, network, diagnostics). Indicator only.
    from parade.display.controller import StatusDisplay
    if config.hardware.display_driver == "ssd1306":
        from parade.display.ssd1306 import SSD1306Display
        display_driver = SSD1306Display(config.display)
    else:
        from parade.display.simulated import SimulatedDisplay
        display_driver = SimulatedDisplay()
    # Phone booth show (sequencer + live looks), when enabled
    show_task = None
    if config.show.enabled:
        from parade.show.controller import ShowController, SparkUsage
        from parade.show.params import ShowParamStore
        ctx.show_params = ShowParamStore(config_path.parent / config.show.params_file)
        ctx.show = ShowController(
            config.show, ctx.show_params, event_bus, state_machine, ctx.safety,
            relay_manager, scene_manager, pixel_manager,
            {g.id: list(g.fixture_ids) for g in config.fixture_groups},
            SparkUsage(config_path.parent / config.show.usage_file),
            log=lambda msg: ctx.event_log.append(
                {"ts": round(time.time() * 1000), "tag": "cue", "msg": msg}
            ),
        )
        await ctx.show.start()
        show_task = asyncio.create_task(ctx.show.run())

    def _activity() -> str | None:
        return ctx.show.describe() if ctx.show else show_engine.active_cue

    status_display = StatusDisplay(
        config.display, display_driver, state_machine, _activity, ctx.power_monitor,
        [n.ip for n in config.network.artnet_nodes],
        port_override if port_override is not None else config.web.port,
    )
    await status_display.start()
    display_task = asyncio.create_task(status_display.run())

    # Run uvicorn
    server_config = uvicorn.Config(
        app,
        host=config.web.host,
        port=port_override if port_override is not None else config.web.port,
        log_level=config.web.log_level,
        loop="asyncio",
    )
    server = uvicorn.Server(server_config)

    try:
        await server.serve()
    finally:
        output_task.cancel()
        ws_task.cancel()
        power_task.cancel()
        lights_task.cancel()
        display_task.cancel()
        if show_task:
            show_task.cancel()
            await ctx.show.stop()
        # Stop cues before hardware so nothing writes to a closed driver.
        await show_engine.stop()
        await ctx.manual.stop()
        await relay_manager.stop()
        await gpio.stop()
        await pixel_manager.stop()
        await dmx_driver.stop()
        await status_lights.stop()
        await status_display.stop()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Parade Float Show Control")
    parser.add_argument(
        "--config", default="config/default.yaml", help="Config file path"
    )
    parser.add_argument(
        "--profiles",
        default="fixture_profiles",
        help="Fixture profiles directory",
    )
    parser.add_argument(
        "--cues", default="cues", help="Cue definitions directory"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Override web port from config"
    )
    args = parser.parse_args()

    # src/parade/main.py -> parents[0]=src/parade, parents[1]=src, parents[2]=project_root
    base = Path(__file__).parents[2]

    config_path = (
        Path(args.config)
        if Path(args.config).is_absolute()
        else base / args.config
    )
    profiles_dir = (
        Path(args.profiles)
        if Path(args.profiles).is_absolute()
        else base / args.profiles
    )
    cues_dir = (
        Path(args.cues)
        if Path(args.cues).is_absolute()
        else base / args.cues
    )

    setup_logging("info")
    asyncio.run(async_main(config_path, profiles_dir, cues_dir, port_override=args.port))


if __name__ == "__main__":
    main()
