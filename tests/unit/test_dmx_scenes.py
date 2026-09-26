import pytest
import asyncio
from parade.dmx.scenes import SceneManager


def test_apply_scene(scene_manager, universe):
    scene_manager.apply_scene("red_on")
    assert universe.get_channel(1) == 255  # red at address 1
    assert universe.get_channel(2) == 0    # green


def test_apply_scene_not_found(scene_manager):
    with pytest.raises(KeyError):
        scene_manager.apply_scene("nonexistent")


def test_list_scenes(scene_manager):
    scenes = scene_manager.list_scenes()
    assert "red_on" in scenes
    assert "blue_on" in scenes


def test_blackout_all(scene_manager, universe):
    scene_manager.apply_scene("red_on")
    assert universe.get_channel(1) == 255
    scene_manager.blackout_all()
    assert universe.get_channel(1) == 0


@pytest.mark.asyncio
async def test_fade_to_scene(scene_manager, universe):
    scene_manager.apply_scene("red_on")
    assert universe.get_channel(1) == 255
    await scene_manager.fade_to_scene("blue_on", duration_ms=100)
    await asyncio.sleep(0.15)
    assert universe.get_channel(1) == 0    # red -> 0
    assert universe.get_channel(3) == 255  # blue -> 255
