"""Raspberry Pi relay outputs via lgpio.

Every relay is claimed already driven to its off level and driven off again
before release, so start, stop and a systemd restart after a crash all leave
the relay open. A hard freeze still holds the last state; the hardware e-stop
covers that (docs/SAFETY.md).
"""
import logging
from parade.relay.interface import RelayInterface
from parade.config.models import RelayOutputConfig
from parade.gpio.rpi import import_lgpio

logger = logging.getLogger(__name__)


class RPiRelay(RelayInterface):
    def __init__(self, relay_configs: list[RelayOutputConfig], chip: int = 0):
        self._configs = {r.id: r for r in relay_configs}
        self._chip = chip
        self._lgpio = None
        self._handle: int | None = None
        self._states: dict[str, bool] = {r.id: False for r in relay_configs}

    def _level(self, relay_id: str, on: bool) -> int:
        return int(on != self._configs[relay_id].active_low)

    async def start(self) -> None:
        lgpio = self._lgpio = import_lgpio()
        for cfg in self._configs.values():
            if cfg.pin <= 0:
                raise RuntimeError(f"Relay '{cfg.id}' has no GPIO pin assigned")
        self._handle = lgpio.gpiochip_open(self._chip)
        try:
            for cfg in self._configs.values():
                try:
                    lgpio.gpio_claim_output(self._handle, cfg.pin, self._level(cfg.id, False))
                except lgpio.error as e:
                    raise RuntimeError(
                        f"Cannot claim GPIO{cfg.pin} for relay '{cfg.id}': {e} "
                        "(is another parade process or the systemd service running?)"
                    ) from e
        except Exception:
            await self.stop()
            raise
        logger.info(
            "RPi relay driver started (all off): %s",
            ", ".join(f"{c.id}=GPIO{c.pin}" for c in self._configs.values()),
        )

    async def stop(self) -> None:
        if self._handle is None:
            return
        for relay_id, cfg in self._configs.items():
            try:
                self._lgpio.gpio_write(self._handle, cfg.pin, self._level(relay_id, False))
                self._lgpio.gpio_free(self._handle, cfg.pin)
            except Exception:
                pass
            self._states[relay_id] = False
        self._lgpio.gpiochip_close(self._handle)
        self._handle = None
        logger.info("RPi relay driver stopped (all off)")

    async def set_relay(self, relay_id: str, state: bool) -> None:
        if relay_id not in self._configs:
            raise KeyError(f"Unknown relay: {relay_id!r}")
        if self._handle is None:
            raise RuntimeError("Relay driver not started")
        self._lgpio.gpio_write(self._handle, self._configs[relay_id].pin, self._level(relay_id, state))
        self._states[relay_id] = state
        logger.info("Relay %s → %s", relay_id, "ON" if state else "off")

    def get_all_states(self) -> dict[str, bool]:
        return dict(self._states)
