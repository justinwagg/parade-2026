from __future__ import annotations
import time
from dataclasses import dataclass, field


@dataclass
class Event:
    source: str
    event_type: str = field(default="event")
    timestamp: float = field(default_factory=time.time)


@dataclass
class GPIOChangeEvent(Event):
    pin_id: str = ""
    state: bool = False
    active: bool = False
    event_type: str = field(default="gpio_changed")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "gpio_changed"


@dataclass
class OperatorTriggerEvent(Event):
    trigger_id: str = ""
    params: dict = field(default_factory=dict)
    event_type: str = field(default="operator_trigger")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "operator_trigger"


@dataclass
class SystemStateChangedEvent(Event):
    old_state: str = ""
    new_state: str = ""
    event_type: str = field(default="system_state_changed")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "system_state_changed"


@dataclass
class DMXNodeOnlineEvent(Event):
    node_id: str = ""
    event_type: str = field(default="dmx_node_online")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "dmx_node_online"


@dataclass
class DMXNodeOfflineEvent(Event):
    node_id: str = ""
    event_type: str = field(default="dmx_node_offline")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "dmx_node_offline"


@dataclass
class CueStartedEvent(Event):
    cue_id: str = ""
    event_type: str = field(default="cue_started")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "cue_started"


@dataclass
class CueCompletedEvent(Event):
    cue_id: str = ""
    event_type: str = field(default="cue_completed")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "cue_completed"


@dataclass
class CueCancelledEvent(Event):
    cue_id: str = ""
    reason: str = ""
    event_type: str = field(default="cue_cancelled")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "cue_cancelled"


@dataclass
class EmergencyStopEvent(Event):
    event_type: str = field(default="emergency_stop")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "emergency_stop"


@dataclass
class SensorFaultEvent(Event):
    sensor_id: str = ""
    description: str = ""
    event_type: str = field(default="sensor_fault")

    def __post_init__(self):
        if self.event_type == "event":
            self.event_type = "sensor_fault"


# Map event_type string -> class for deserialization
EVENT_TYPES: dict[str, type] = {
    "gpio_changed": GPIOChangeEvent,
    "operator_trigger": OperatorTriggerEvent,
    "system_state_changed": SystemStateChangedEvent,
    "dmx_node_online": DMXNodeOnlineEvent,
    "dmx_node_offline": DMXNodeOfflineEvent,
    "cue_started": CueStartedEvent,
    "cue_completed": CueCompletedEvent,
    "cue_cancelled": CueCancelledEvent,
    "emergency_stop": EmergencyStopEvent,
    "sensor_fault": SensorFaultEvent,
}
