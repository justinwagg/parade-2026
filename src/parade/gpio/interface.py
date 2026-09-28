from abc import ABC, abstractmethod


class GPIOInterface(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def get_state(self, pin_id: str) -> bool:
        """Return current logical state of the pin (True = active)."""
        ...

    @abstractmethod
    def get_all_states(self) -> dict[str, bool]:
        """Return {pin_id: active_state} for all configured pins."""
        ...

    @abstractmethod
    def get_physical_states(self) -> dict[str, bool]:
        """Return {pin_id: electrical_level} for all configured pins (True = high)."""
        ...
