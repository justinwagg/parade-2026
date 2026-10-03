from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class SystemConfig(BaseModel):
    name: str = "parade-float"
    environment: Literal["development", "production"] = "development"


class HardwareConfig(BaseModel):
    dmx_driver: Literal["artnet", "simulated"] = "simulated"
    gpio_driver: Literal["rpi", "simulated"] = "simulated"
    pixel_driver: Literal["rpi", "mcu", "simulated"] = "simulated"
    relay_driver: Literal["rpi", "mcu", "simulated"] = "simulated"
    status_light_driver: Literal["blinkstick", "simulated"] = "simulated"
    display_driver: Literal["ssd1306", "simulated"] = "simulated"
    gpio_chip: int = 0  # /dev/gpiochipN for the rpi GPIO and relay drivers


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
    pin: int = 0  # 0 = unassigned (simulation only); rpi driver requires 10 (SPI0 MOSI)
    count: int = Field(ge=1, le=1024)
    strip_type: str = "WS2812B"
    # Byte order on the wire, e.g. "GRB" or "GRBW"; empty = the strip_type's default.
    # W is the white channel (RGBW pixels), sent as 0 for now.
    color_order: str = ""
    brightness: float = Field(default=1.0, ge=0.0, le=1.0)  # hardware output scale; caps current draw
    description: str = ""


class FixtureGroupConfig(BaseModel):
    id: str
    name: str
    fixture_ids: list[str] = []
    description: str = ""


class StatusLightConfig(BaseModel):
    serial: str  # BlinkStick serial without the firmware suffix, e.g. "BS025458"
    led_index: int = Field(default=0, ge=0, le=1)  # which of the Nano's two LEDs faces out of the enclosure
    description: str = ""


class StatusLightsConfig(BaseModel):
    brightness: float = Field(default=0.2, ge=0.0, le=1.0)
    state_led: StatusLightConfig | None = None  # system state (SAFE, RUNNING, E-STOP...)
    health_led: StatusLightConfig | None = None  # Pi power/thermal health and app heartbeat


class DisplayInterfaceConfig(BaseModel):
    label: str  # shown on the display, e.g. "Mac"
    interface: str  # e.g. "eth0"


class DisplayConfig(BaseModel):
    i2c_bus: int = 1
    address: int = 0x3C
    width: int = 128
    height: int = 32
    rotate: int = Field(default=0, ge=0, le=3)  # quarter turns; 2 = upside down
    page_seconds: float = Field(default=4.0, gt=0)
    ap_info_path: str = "/etc/parade/ap-display.env"  # written by scripts/pi-ap.sh
    wifi_interface: str = "wlan0"
    interfaces: list[DisplayInterfaceConfig] = [
        DisplayInterfaceConfig(label="Mac", interface="eth0"),
        DisplayInterfaceConfig(label="WiFi", interface="wlan0"),
        DisplayInterfaceConfig(label="ArtNet", interface="eth1"),
    ]


class PixelSideConfig(BaseModel):
    """A run of NeoPixels on one side of the booth (indices along the strip)."""
    id: str
    name: str = ""
    start: int = Field(ge=0)
    count: int = Field(ge=0)
    reverse: bool = False  # chase direction along this side


class ShowConfig(BaseModel):
    """Wiring of the phone booth show to hardware. The look itself is live
    settings in show.yaml (edited from the dashboard's Show tab)."""
    enabled: bool = False  # True: the show sequencer drives the booth; cues are not run
    params_file: str = "show.yaml"  # next to this config file
    usage_file: str = "spark_usage.json"  # spark-on time since the hopper was refilled
    motor_relay: str = "phone_booth_rotation"
    performer_input: str = "performer_button"
    index_input: str = "rotation_index"
    interior_group: str = "interior"
    exterior_group: str = "exterior"
    spark_fixture: str = "cold_spark"
    fog_fixture: str = "fog_machine"
    pixel_sides: list[PixelSideConfig] = []
    frame_hz: float = Field(default=30.0, ge=5, le=60)


class SafetyConfig(BaseModel):
    estop_pin: str | None = None  # id of the gpio_inputs entry wired to the e-stop monitor contact
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
    status_lights: StatusLightsConfig = StatusLightsConfig()
    display: DisplayConfig = DisplayConfig()
    show: ShowConfig = ShowConfig()
    safety: SafetyConfig = SafetyConfig()
    web: WebConfig = WebConfig()

    @model_validator(mode="after")
    def _check_estop_pin(self) -> "Config":
        pin = self.safety.estop_pin
        if pin is not None and pin not in {g.id for g in self.gpio_inputs}:
            raise ValueError(f"safety.estop_pin {pin!r} is not a gpio_inputs id")
        return self
