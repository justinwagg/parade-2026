from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from parade.config.models import Config
from parade.core.event_bus import EventBus
from parade.core.state import SystemStateMachine
from parade.core.engine import ShowEngine
from parade.dmx.interface import DMXInterface
from parade.dmx.universe import DMXUniverse
from parade.dmx.fixtures import FixtureManager
from parade.dmx.scenes import SceneManager
from parade.gpio.interface import GPIOInterface
from parade.relay.interface import RelayInterface
from parade.pixels.interface import PixelInterface
from parade.health.power import PowerMonitor
from parade.core.safety import SafetyMonitor


@dataclass
class AppContext:
    config: Config
    event_bus: EventBus
    state_machine: SystemStateMachine
    dmx_driver: DMXInterface
    universes: dict[int, DMXUniverse]
    fixture_manager: FixtureManager
    scene_manager: SceneManager
    gpio: GPIOInterface
    relay_manager: RelayInterface
    pixel_manager: PixelInterface
    show_engine: ShowEngine
    # Path used for hot-reload of user-built scenes
    cues_dir: Path = field(default_factory=lambda: Path("cues"))
    # Paths used by the setup API for config persistence and profile discovery
    config_path: Path = field(default_factory=lambda: Path("config/default.yaml"))
    profiles_dir: Path = field(default_factory=lambda: Path("fixture_profiles"))
    # Pi under-voltage / throttle / temperature monitor (None in tests)
    power_monitor: PowerMonitor | None = None
    # E-stop monitoring and relay safe-states; owns operator state transitions
    safety: SafetyMonitor | None = None
    # WebSocket clients for live push
    ws_clients: list = field(default_factory=list)
    # Bounded event log: each entry is a dict {ts, tag, level, msg}
    event_log: deque = field(default_factory=lambda: deque(maxlen=200))
