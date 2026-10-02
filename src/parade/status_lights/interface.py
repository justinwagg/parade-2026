from abc import ABC, abstractmethod

Color = tuple[int, int, int]


class StatusLightInterface(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def set_led(self, serial: str, index: int, color: Color) -> bool:
        """Set one LED. Returns False if the stick isn't reachable right now."""
        ...

    @abstractmethod
    def get_leds(self) -> dict[tuple[str, int], Color]:
        """Last colour written to each (serial, index)."""
        ...
