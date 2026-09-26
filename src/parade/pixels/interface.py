from abc import ABC, abstractmethod


class PixelInterface(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def set_pixel(self, index: int, r: int, g: int, b: int) -> None: ...

    @abstractmethod
    async def set_all(self, r: int, g: int, b: int) -> None: ...

    @abstractmethod
    async def show(self) -> None:
        """Commit buffered pixel values to hardware (no-op in simulation)."""
        ...

    @abstractmethod
    def get_pixel_count(self) -> int: ...

    @abstractmethod
    def get_all_pixels(self) -> list[tuple[int, int, int]]: ...
