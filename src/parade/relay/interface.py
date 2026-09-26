from abc import ABC, abstractmethod


class RelayInterface(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def set_relay(self, relay_id: str, state: bool) -> None: ...

    @abstractmethod
    def get_all_states(self) -> dict[str, bool]: ...
