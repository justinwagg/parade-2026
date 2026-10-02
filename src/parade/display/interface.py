from abc import ABC, abstractmethod


class DisplayInterface(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def show(self, lines: list[str], heartbeat: bool = False) -> None:
        """Draw text lines top to bottom; heartbeat lights a pixel in the top-right corner."""
        ...

    @abstractmethod
    def get_lines(self) -> list[str]:
        """Lines currently shown."""
        ...
