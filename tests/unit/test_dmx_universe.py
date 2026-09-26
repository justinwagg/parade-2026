import pytest
import asyncio
from parade.dmx.universe import DMXUniverse, FadeTarget


def test_set_and_get_channel():
    u = DMXUniverse(1)
    u.set_channel(1, 200)
    assert u.get_channel(1) == 200


def test_channel_clamped():
    u = DMXUniverse(1)
    u.set_channel(1, 999)
    assert u.get_channel(1) == 255
    u.set_channel(1, -5)
    assert u.get_channel(1) == 0


def test_channel_1_indexed():
    u = DMXUniverse(1)
    u.set_channel(1, 100)
    buf = u.get_buffer()
    assert buf[0] == 100  # channel 1 is index 0


def test_blackout_clears_all():
    u = DMXUniverse(1)
    u.set_channels({1: 255, 2: 128, 3: 64})
    u.blackout()
    assert u.get_channel(1) == 0
    assert u.get_channel(2) == 0


def test_get_all_channels_only_nonzero():
    u = DMXUniverse(1)
    u.set_channel(5, 100)
    result = u.get_all_channels()
    assert 5 in result
    assert result[5] == 100
    assert 1 not in result


@pytest.mark.asyncio
async def test_fade_reaches_target():
    u = DMXUniverse(1)
    u.set_channel(1, 0)
    targets = [FadeTarget(channel=1, start_value=0, end_value=200)]
    fade = u.start_fade(targets, duration_ms=100)
    await asyncio.sleep(0.15)
    assert u.get_channel(1) == 200
