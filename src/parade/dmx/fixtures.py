from dataclasses import dataclass
from parade.config.models import FixtureConfig


@dataclass
class FixtureProfile:
    id: str
    name: str
    channel_count: int
    color_model: str
    channels: dict[str, int]  # channel_name -> offset (1-indexed within fixture)
    notes: str = ""
    source: str = ""


class FixtureManager:
    def __init__(
        self, profiles: dict[str, dict], fixture_configs: list[FixtureConfig]
    ):
        self._profiles: dict[str, FixtureProfile] = {}
        self._fixtures: dict[str, FixtureConfig] = {}

        for profile_id, data in profiles.items():
            self._profiles[profile_id] = FixtureProfile(
                id=data["id"],
                name=data.get("name", data["id"]),
                channel_count=data["channel_count"],
                color_model=data.get("color_model", "rgb"),
                channels=data.get("channels", {}),
                notes=data.get("notes", ""),
                source=data.get("source", ""),
            )

        for fc in fixture_configs:
            if fc.profile not in self._profiles:
                raise ValueError(
                    f"Fixture '{fc.id}' references unknown profile '{fc.profile}'"
                )
            self._fixtures[fc.id] = fc

    def get_profile(self, profile_id: str) -> FixtureProfile:
        return self._profiles[profile_id]

    def get_fixture(self, fixture_id: str) -> FixtureConfig:
        return self._fixtures[fixture_id]

    def get_all_fixtures(self) -> dict[str, FixtureConfig]:
        return dict(self._fixtures)

    def get_all_profiles(self) -> dict[str, FixtureProfile]:
        return dict(self._profiles)

    def resolve_channels(
        self, fixture_id: str, channel_values: dict[str, int]
    ) -> dict[int, int]:
        """Translate {channel_name: value} to {dmx_address: value} for a fixture.
        Returns absolute DMX addresses (1-indexed).
        """
        fixture = self._fixtures[fixture_id]
        profile = self._profiles[fixture.profile]
        dmx_values: dict[int, int] = {}
        for name, value in channel_values.items():
            if name in profile.channels:
                offset = profile.channels[name]
                dmx_addr = fixture.address + offset - 1
            else:
                raise ValueError(
                    f"Channel '{name}' not in profile '{profile.id}' "
                    f"for fixture '{fixture_id}'"
                )
            dmx_values[dmx_addr] = max(0, min(255, int(value)))
        return dmx_values
