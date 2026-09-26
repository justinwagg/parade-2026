import pytest
from parade.core.event_bus import EventBus
from parade.core.state import SystemStateMachine
from parade.dmx.universe import DMXUniverse
from parade.dmx.fixtures import FixtureManager
from parade.dmx.scenes import SceneManager
from parade.dmx.simulated import SimulatedDMX
from parade.gpio.simulated import SimulatedGPIO


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def state_machine():
    return SystemStateMachine()


@pytest.fixture
def sample_profiles():
    return {
        "test_rgb_3ch": {
            "id": "test_rgb_3ch",
            "name": "Test RGB 3ch",
            "channel_count": 3,
            "color_model": "rgb",
            "channels": {"red": 1, "green": 2, "blue": 3},
        }
    }


@pytest.fixture
def sample_fixture_configs():
    from parade.config.models import FixtureConfig
    return [
        FixtureConfig(
            id="test_fixture",
            name="Test Fixture",
            profile="test_rgb_3ch",
            universe=1,
            address=1,
        )
    ]


@pytest.fixture
def fixture_manager(sample_profiles, sample_fixture_configs):
    return FixtureManager(sample_profiles, sample_fixture_configs)


@pytest.fixture
def universe():
    return DMXUniverse(universe_id=1, refresh_hz=40)


@pytest.fixture
def scene_manager(fixture_manager, universe):
    sm = SceneManager(fixture_manager, {1: universe})
    sm.load_scenes([
        {
            "id": "red_on",
            "name": "Red On",
            "fixtures": {"test_fixture": {"red": 255, "green": 0, "blue": 0}},
        },
        {
            "id": "blue_on",
            "name": "Blue On",
            "fixtures": {"test_fixture": {"red": 0, "green": 0, "blue": 255}},
        },
        {
            "id": "off",
            "name": "Off",
            "fixtures": {"test_fixture": {"red": 0, "green": 0, "blue": 0}},
        },
    ])
    return sm
