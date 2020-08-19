import asyncio
import logging
import pathlib
from io import BytesIO
from typing import Callable, List

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import BaseBleakScanner

import winrt.windows.devices.bluetooth.advertisement as winbleadv
import winrt.windows.storage.streams as winstrm


logger = logging.getLogger(__name__)
_here = pathlib.Path(__file__).parent


def _format_bdaddr(a):
    return ":".join("{:02X}".format(x) for x in a.to_bytes(6, byteorder="big"))


def _format_event_args(e):
    try:
        return "{0}: {1}".format(
            _format_bdaddr(e.bluetooth_address), e.advertisement.local_name or "Unknown"
        )
    except Exception:
        return e.bluetooth_address


class BleakScannerWinRT(BaseBleakScanner):
    """The native Windows Bleak BLE Scanner.

    Implemented using `Python/WinRT <https://github.com/Microsoft/xlang/tree/master/src/package/pywinrt/projection/>`_.

    Keyword Args:
        scanning mode (str): Set to "Passive" to avoid the "Active" scanning mode.

    """

    def __init__(self, **kwargs):
        super(BleakScannerWinRT, self).__init__(**kwargs)

        self.watcher = None
        self._devices = {}
        self._scan_responses = {}

        self._callback = None

        if "scanning_mode" in kwargs and kwargs["scanning_mode"].lower() == "passive":
            self._scanning_mode = winbleadv.BluetoothLEScanningMode.PASSIVE
        else:
            self._scanning_mode = winbleadv.BluetoothLEScanningMode.ACTIVE

        self._signal_strength_filter = kwargs.get("SignalStrengthFilter", None)
        self._advertisement_filter = kwargs.get("AdvertisementFilter", None)

        self._received_token = None
        self._stopped_token = None

    def register_detection_callback(self, callback: Callable):
        """Set a function to act as Received Event Handler.

        Documentation for the Event Handler:
        https://docs.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.advertisement.bluetoothleadvertisementwatcher.received

        Args:
            callback: Function accepting two arguments:
             sender (Windows.Devices.Bluetooth.AdvertisementBluetoothLEAdvertisementWatcher) and
             eventargs (Windows.Devices.Bluetooth.advertisement.BluetoothLEAdvertisementReceivedEventArgs)

        """
        self._callback = callback

    def _received(self, sender, e):
        """Callback for AdvertisementWatcher.Received"""
        logger.debug("Received {0}.".format(_format_event_args(e)))
        try:
            if e.advertisement_type == winbleadv.BluetoothLEAdvertisementType.SCAN_RESPONSE:
                if e.bluetooth_address not in self._scan_responses:
                    self._scan_responses[e.bluetooth_address] = e
            else:
                if e.bluetooth_address not in self._devices:
                    self._devices[e.bluetooth_address] = e
            if self._callback is not None:
                self._callback(sender, e)
        except Exception:
            logger.exception("Error in AdvertisementWatcher.Received callback", exc_info=True)

    def _stopped(self, sender, e):
        logger.debug(
            "{0} devices found. Watcher status: {1}.".format(
                len(self._devices), self.watcher.status
            )
        )

    async def start(self):
        self.watcher = winbleadv.BluetoothLEAdvertisementWatcher()
        self.watcher.scanning_mode = self._scanning_mode

        self._received_token = self.watcher.add_received(self._received)
        self._stopped_token = self.watcher.add_stopped(self._stopped)

        if self._signal_strength_filter is not None:
            self.watcher.signal_strength_filter = self._signal_strength_filter
        if self._advertisement_filter is not None:
            self.watcher._advertisement_filter = self._advertisement_filter

        self.watcher.start()

    async def stop(self):
        self.watcher.stop()

        try:
            self.watcher.remove_received(self._received_token)
            self.watcher.remove_stopped(self._stopped_token)
        except Exception as e:
            logger.debug("Could not remove event handlers: {0}...".format(e))

        self._stopped_token = None
        self._received_token = None

        self.watcher = None

    async def set_scanning_filter(self, **kwargs):
        pass

    async def get_discovered_devices(self) -> List[BLEDevice]:
        found = []
        for event_args in list(self._devices.values()):
            new_device = self.parse_eventargs(event_args)
            if (
                not new_device.name
                and event_args.bluetooth_address in self._scan_responses
            ):
                new_device.name = self._scan_responses[
                    event_args.bluetooth_address
                ].advertisement.local_name
            found.append(new_device)

        return found

    def parse_eventargs(self, event_args):
        bdaddr = _format_bdaddr(event_args.bluetooth_address)
        uuids = []
        try:
            for u in event_args.advertisement.service_uuids:
                uuids.append(u.to_string())
        except NotImplementedError as e:
            # Cannot get service uuids for this device...
            pass
        data = {}
        for m in event_args.advertisement.manufacturer_data:
            reader = winstrm.DataReader.from_buffer(m.data)
            # TODO: Figure out how to use read_bytes instead...
            b = [reader.read_byte() for _ in range(m.data.length)]
            data[m.company_id] = bytes(b)
        local_name = event_args.advertisement.local_name
        return BLEDevice(
            bdaddr, local_name, event_args, uuids=uuids, manufacturer_data=data
        )
