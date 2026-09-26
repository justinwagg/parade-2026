import asyncio
import socket
import struct
import logging
from .interface import DMXInterface

logger = logging.getLogger(__name__)

ARTNET_HEADER = b"Art-Net\x00"
ARTDMX_OPCODE = 0x5000
ARTNET_PROTOCOL_VERSION = 14


class ArtNetDMX(DMXInterface):
    def __init__(self):
        self._sock: socket.socket | None = None
        self._sequence: int = 0

    async def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        logger.info("Art-Net DMX driver started")

    async def stop(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None
        logger.info("Art-Net DMX driver stopped")

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence % 255) + 1
        return self._sequence

    def _build_artdmx_packet(self, universe: int, data: bytes) -> bytes:
        padded = (data + bytes(512))[:512]
        return (
            ARTNET_HEADER
            + struct.pack("<H", ARTDMX_OPCODE)
            + struct.pack(">H", ARTNET_PROTOCOL_VERSION)
            + bytes([self._next_sequence()])
            + b"\x00"  # physical
            + struct.pack("<H", universe & 0x7FFF)
            + struct.pack(">H", len(padded))
            + padded
        )

    async def send_universe(
        self, universe_id: int, node_ip: str, node_port: int, data: bytes
    ) -> None:
        if not self._sock:
            return
        packet = self._build_artdmx_packet(universe_id, data)
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, self._sock.sendto, packet, (node_ip, node_port)
            )
        except OSError as e:
            logger.warning(
                "Art-Net send error to %s:%d: %s", node_ip, node_port, e
            )
