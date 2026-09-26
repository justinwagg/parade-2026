from abc import ABC, abstractmethod


class DMXInterface(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send_universe(
        self, universe_id: int, node_ip: str, node_port: int, data: bytes
    ) -> None: ...
