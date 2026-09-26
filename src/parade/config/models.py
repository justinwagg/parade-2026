from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class SystemConfig(BaseModel):
    name: str = "parade-float"
    environment: Literal["development", "production"] = "development"


class HardwareConfig(BaseModel):
    dmx_driver: Literal["artnet", "simulated"] = "simulated"
    gpio_driver: Literal["rpi", "simulated"] = "simulated"
    pixel_driver: Literal["rpi", "mcu", "simulated"] = "simulated"
    relay_driver: Literal["rpi", "mcu", "simulated"] = "simulated"


class ArtNetNodeConfig(BaseModel):
    id: str
    ip: str
    port: int = 6454


class NetworkConfig(BaseModel):
    artnet_nodes: list[ArtNetNodeConfig] = []


class DMXUniverseConfig(BaseModel):
    id: int
    node: str  # references ArtNetNodeConfig.id
    protocol: Literal["artnet", "sacn"] = "artnet"
    refresh_hz: int = Field(default=40, ge=10, le=44)
    on_node_loss: Literal["hold", "blackout"] = "hold"


class DMXConfig(BaseModel):
    universes: list[DMXUniverseConfig] = []


class FixtureConfig(BaseModel):
    id: str
    name: str
    profile: str  # fixture profile id from fixture_profiles/
    universe: int
    address: int = Field(ge=1, le=512)


class GPIOInputConfig(BaseModel):
    id: str
    pin: int
    pull: Literal["up", "down", "none"] = "none"
    active_low: bool = False
    debounce_ms: int = 20
    description: str = ""


class RelayOutputConfig(BaseModel):
    id: str
    pin: int = 0  # 0 = unassigned (simulation only)
    active_low: bool = False
    description: str = ""


class PixelStripConfig(BaseModel):
    id: str
    pin: int = 0  # 0 = unassigned (simulation only)
    count: int = Field(ge=1, le=1024)
    strip_type: str = "WS2812B"
    description: str = ""


class FixtureGroupConfig(BaseModel):
    id: str
    name: str
    fixture_ids: list[str] = []
    description: str = ""


class SafetyConfig(BaseModel):
    estop_pin: str | None = None
    armed_requires_operator: bool = True


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"


class Config(BaseModel):
    system: SystemConfig = SystemConfig()
    hardware: HardwareConfig = HardwareConfig()
    network: NetworkConfig = NetworkConfig()
    dmx: DMXConfig = DMXConfig()
    fixtures: list[FixtureConfig] = []
    fixture_groups: list[FixtureGroupConfig] = []
    gpio_inputs: list[GPIOInputConfig] = []
    relay_outputs: list[RelayOutputConfig] = []
    pixel_strips: list[PixelStripConfig] = []
    safety: SafetyConfig = SafetyConfig()
    web: WebConfig = WebConfig()
