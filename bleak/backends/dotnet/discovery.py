# -*- coding: utf-8 -*-
"""
Perform Bluetooth LE Scan.

Created on 2017-12-05 by hbldh <henrik.blidh@nedomkull.com>

"""
import pathlib
import logging
import asyncio
from typing import List


from bleak.backends.device import BLEDevice

# Import of Bleak CLR->UWP Bridge. It is not needed here, but it enables loading of Windows.Devices
from BleakBridge import Bridge

from System import Array, Byte
from Windows.Devices import Enumeration
from Windows.Devices.Bluetooth.Advertisement import (
    BluetoothLEAdvertisementWatcher,
    BluetoothLEScanningMode,
    BluetoothLEAdvertisementType,
    BluetoothLEAdvertisementReceivedEventArgs,
    BluetoothLEAdvertisementWatcherStoppedEventArgs,
)

from bleak.backends.dotnet.utils import BleakDataReader
from Windows.Foundation import TypedEventHandler
from Windows.Storage.Streams import DataReader, IBuffer

logger = logging.getLogger(__name__)
_here = pathlib.Path(__file__).parent


async def discover(timeout: float = 5.0, **kwargs) -> List[BLEDevice]:
    """Perform a Bluetooth LE Scan using Windows.Devices.Bluetooth.Advertisement

    Args:
        timeout (float): Time to scan for.

    Keyword Args:
        SignalStrengthFilter (Windows.Devices.Bluetooth.BluetoothSignalStrengthFilter): A
          BluetoothSignalStrengthFilter object used for configuration of Bluetooth
          LE advertisement filtering that uses signal strength-based filtering.
        AdvertisementFilter (Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementFilter): A
          BluetoothLEAdvertisementFilter object used for configuration of Bluetooth LE
          advertisement filtering that uses payload section-based filtering.
        string_output (bool): If set to false, ``discover`` returns .NET
            device objects instead.

    Returns:
        List of strings or objects found.

    """
    signal_strength_filter = kwargs.get("SignalStrengthFilter", None)
    advertisement_filter = kwargs.get("AdvertisementFilter", None)

    watcher = BluetoothLEAdvertisementWatcher()

    devices = {}
    scan_responses = {}

    bridge = Bridge()

    def _format_bdaddr(a):
        return ":".join("{:02X}".format(x) for x in a.to_bytes(6, byteorder="big"))

    def _format_event_args(e):
        try:
            return "{0}: {1}".format(
                _format_bdaddr(e.BluetoothAddress),
                e.Advertisement.LocalName or "Unknown",
            )
        except Exception:
            return e.BluetoothAddress

    def AdvertisementWatcher_Received(sender, e):
        if sender == watcher:
            logger.debug("Received {0}.".format(_format_event_args(e)))
            if e.AdvertisementType == BluetoothLEAdvertisementType.ScanResponse:
                if e.BluetoothAddress not in scan_responses:
                    scan_responses[e.BluetoothAddress] = e
            else:
                if e.BluetoothAddress not in devices:
                    devices[e.BluetoothAddress] = e

    def AdvertisementWatcher_Stopped(sender, e):
        if sender == watcher:
            logger.debug(
                "{0} devices found. Watcher status: {1}.".format(
                    len(devices), watcher.Status
                )
            )

    bridge.AddWatcherEventHandlers(
        watcher,
        TypedEventHandler[
            BluetoothLEAdvertisementWatcher,
            BluetoothLEAdvertisementReceivedEventArgs
        ](AdvertisementWatcher_Received),
        TypedEventHandler[
            BluetoothLEAdvertisementWatcher,
            BluetoothLEAdvertisementWatcherStoppedEventArgs,
        ](AdvertisementWatcher_Stopped),
    )
    watcher.ScanningMode = BluetoothLEScanningMode.Active

    if signal_strength_filter is not None:
        watcher.SignalStrengthFilter = signal_strength_filter
    if advertisement_filter is not None:
        watcher.AdvertisementFilter = advertisement_filter

    # Watcher works outside of the Python process.
    watcher.Start()
    await asyncio.sleep(timeout)
    watcher.Stop()

    bridge.RemoveWatcherEventHandlers(watcher)
    del AdvertisementWatcher_Received
    del AdvertisementWatcher_Stopped
    bridge.Dispose()

    found = []
    for d in list(devices.values()):
        bdaddr = _format_bdaddr(d.BluetoothAddress)
        uuids = []
        for u in d.Advertisement.ServiceUuids:
            uuids.append(u.ToString())
        data = {}
        for m in d.Advertisement.ManufacturerData:
            with BleakDataReader(m.Data) as reader:
                data[m.CompanyId] = reader.read()
        local_name = d.Advertisement.LocalName
        if not local_name and d.BluetoothAddress in scan_responses:
            local_name = scan_responses[d.BluetoothAddress].Advertisement.LocalName
        found.append(
            BLEDevice(
                bdaddr,
                local_name,
                d,
                uuids=uuids,
                manufacturer_data=data,
            )
        )

    return found
