import asyncio
import logging
from dataclasses import dataclass
from .universe import DMXUniverse, FadeTarget
from .fixtures import FixtureManager

logger = logging.getLogger(__name__)


@dataclass
class SceneFixtureValues:
    fixture_id: str
    channels: dict[str, int]  # channel_name -> value


@dataclass
class Scene:
    id: str
    name: str
    fixtures: list[SceneFixtureValues]


class SceneManager:
    def __init__(
        self,
        fixture_manager: FixtureManager,
        universes: dict[int, DMXUniverse],
    ):
        self._fixture_manager = fixture_manager
        self._universes = universes
        self._scenes: dict[str, Scene] = {}

    def load_scenes(self, scenes_data: list[dict]) -> None:
        for s in scenes_data:
            fixtures = []
            for fixture_id, channels in s.get("fixtures", {}).items():
                fixtures.append(
                    SceneFixtureValues(fixture_id=fixture_id, channels=channels)
                )
            self._scenes[s["id"]] = Scene(
                id=s["id"],
                name=s.get("name", s["id"]),
                fixtures=fixtures,
            )

    def get_scene(self, scene_id: str) -> Scene:
        if scene_id not in self._scenes:
            raise KeyError(f"Scene '{scene_id}' not found")
        return self._scenes[scene_id]

    def list_scenes(self) -> list[str]:
        return list(self._scenes.keys())

    def apply_scene(self, scene_id: str) -> None:
        scene = self.get_scene(scene_id)
        for sfv in scene.fixtures:
            fixture = self._fixture_manager.get_fixture(sfv.fixture_id)
            dmx_values = self._fixture_manager.resolve_channels(
                sfv.fixture_id, sfv.channels
            )
            universe = self._universes.get(fixture.universe)
            if universe is None:
                logger.warning(
                    "Universe %d not found for fixture %s",
                    fixture.universe,
                    sfv.fixture_id,
                )
                continue
            universe.set_channels(dmx_values)

    async def fade_to_scene(self, scene_id: str, duration_ms: float) -> None:
        scene = self.get_scene(scene_id)
        for sfv in scene.fixtures:
            fixture = self._fixture_manager.get_fixture(sfv.fixture_id)
            universe = self._universes.get(fixture.universe)
            if universe is None:
                continue
            dmx_targets = self._fixture_manager.resolve_channels(
                sfv.fixture_id, sfv.channels
            )
            targets = [
                FadeTarget(
                    channel=ch,
                    start_value=universe.get_channel(ch),
                    end_value=val,
                )
                for ch, val in dmx_targets.items()
            ]
            universe.start_fade(targets, duration_ms)

    def set_fixture_rgb(self, fixture_id: str, r: int, g: int, b: int) -> None:
        """Write R/G/B to a fixture and zero all other colour channels (white,
        amber, uv) so previous scene values don't bleed into group animations."""
        try:
            fixture = self._fixture_manager.get_fixture(fixture_id)
        except KeyError:
            logger.warning("set_fixture_rgb: unknown fixture '%s'", fixture_id)
            return
        profile = self._fixture_manager.get_profile(fixture.profile)
        channels: dict[str, int] = {}
        if "red" in profile.channels:   channels["red"]   = r
        if "green" in profile.channels: channels["green"] = g
        if "blue" in profile.channels:  channels["blue"]  = b
        if not channels:
            return
        # Zero all other colour channels so they don't mix with the intended RGB
        for name in ("white", "amber", "uv", "dimmer"):
            if name in profile.channels:
                channels[name] = 0
        dmx_values = self._fixture_manager.resolve_channels(fixture_id, channels)
        universe = self._universes.get(fixture.universe)
        if universe:
            universe.set_channels(dmx_values)

    def set_fixture_off(self, fixture_id: str) -> None:
        """Zero every channel for a fixture, not just RGB."""
        try:
            fixture = self._fixture_manager.get_fixture(fixture_id)
        except KeyError:
            return
        profile = self._fixture_manager.get_profile(fixture.profile)
        channels = {name: 0 for name in profile.channels}
        dmx_values = self._fixture_manager.resolve_channels(fixture_id, channels)
        universe = self._universes.get(fixture.universe)
        if universe:
            universe.set_channels(dmx_values)

    def set_fixture_channels(
        self, fixture_id: str, channels: dict[str, int], fade_ms: float = 0
    ) -> None:
        """Set arbitrary named channels on a fixture, with optional fade."""
        try:
            fixture = self._fixture_manager.get_fixture(fixture_id)
        except KeyError:
            logger.warning("set_fixture_channels: unknown fixture '%s'", fixture_id)
            return
        if not channels:
            return
        dmx_values = self._fixture_manager.resolve_channels(fixture_id, channels)
        universe = self._universes.get(fixture.universe)
        if universe is None:
            return
        if fade_ms > 0:
            targets = [
                FadeTarget(channel=ch, start_value=universe.get_channel(ch), end_value=val)
                for ch, val in dmx_values.items()
            ]
            universe.start_fade(targets, fade_ms)
        else:
            universe.set_channels(dmx_values)

    def blackout_all(self) -> None:
        for universe in self._universes.values():
            universe.blackout()
