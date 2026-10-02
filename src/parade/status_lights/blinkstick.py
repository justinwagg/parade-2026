"""BlinkStick Nano status LEDs over USB via pyusb (apt package python3-usb).

Each LED is set with one HID feature report (report 5: channel, index, r, g, b)
sent as a USB control transfer. Sticks are matched by serial number, so it doesn't
matter which port each is plugged into. A stick that is missing or gets unplugged
is looked for again every RESCAN_S; the show keeps running either way.

Using the sticks without root needs the udev rule installed by scripts/pi-setup.sh.
"""
import asyncio
import logging
import time
from parade.status_lights.interface import Color, StatusLightInterface

logger = logging.getLogger(__name__)

VENDOR_ID = 0x20A0
PRODUCT_ID = 0x41E5
REPORT_SET_INDEXED = 5
RESCAN_S = 5.0


def base_serial(serial: str) -> str:
    """'BS025458-3.0' -> 'BS025458' (drop the firmware version suffix)."""
    return serial.split("-", 1)[0]


class BlinkStickLights(StatusLightInterface):
    def __init__(self, serials: list[str]):
        self._wanted = {base_serial(s) for s in serials}
        self._devices: dict = {}
        self._leds: dict[tuple[str, int], Color] = {}
        self._usb = None
        self._last_scan = 0.0
        self._reported_missing: set[str] | None = None

    async def start(self) -> None:
        try:
            import usb.core
            import usb.util
        except ImportError:
            logger.error("pyusb not installed (sudo apt install python3-usb); status lights disabled")
            return
        self._usb = usb
        await asyncio.to_thread(self._scan)

    async def stop(self) -> None:
        if self._usb is None:
            return
        for dev in self._devices.values():
            self._usb.util.dispose_resources(dev)
        self._devices.clear()

    def _scan(self) -> None:
        usb = self._usb
        self._last_scan = time.monotonic()
        try:
            found = list(usb.core.find(find_all=True, idVendor=VENDOR_ID, idProduct=PRODUCT_ID))
        except usb.core.NoBackendError:
            logger.error("libusb not available; status lights disabled")
            self._usb = None
            return
        for dev in found:
            try:
                serial = base_serial(usb.util.get_string(dev, dev.iSerialNumber) or "")
            except (usb.core.USBError, ValueError) as e:
                # ValueError: no permission to read the string (udev rule missing)
                logger.debug("Can't read BlinkStick serial: %s", e)
                continue
            if serial not in self._wanted or serial in self._devices:
                continue
            try:
                if dev.is_kernel_driver_active(0):
                    dev.detach_kernel_driver(0)
            except (usb.core.USBError, NotImplementedError):
                pass
            self._devices[serial] = dev
            logger.info("Status light %s connected", serial)

        missing = self._wanted - self._devices.keys()
        if missing != self._reported_missing:
            if missing:
                logger.warning(
                    "Status light(s) not found: %s (unplugged, or udev rule missing)",
                    ", ".join(sorted(missing)),
                )
            self._reported_missing = missing

    async def set_led(self, serial: str, index: int, color: Color) -> bool:
        serial = base_serial(serial)
        self._leds[(serial, index)] = color
        if self._usb is None:
            return False
        dev = self._devices.get(serial)
        if dev is None and time.monotonic() - self._last_scan >= RESCAN_S:
            await asyncio.to_thread(self._scan)
            dev = self._devices.get(serial)
        if dev is None:
            return False
        r, g, b = color
        try:
            await asyncio.to_thread(
                dev.ctrl_transfer, 0x20, 0x09, REPORT_SET_INDEXED, 0,
                bytes([REPORT_SET_INDEXED, 0, index, r, g, b]),
            )
        except self._usb.core.USBError as e:
            logger.warning("Status light %s lost: %s", serial, e)
            self._devices.pop(serial, None)
            self._usb.util.dispose_resources(dev)
            return False
        return True

    def get_leds(self) -> dict[tuple[str, int], Color]:
        return dict(self._leds)
