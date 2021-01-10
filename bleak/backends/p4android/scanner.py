import asyncio
import logging
from typing import List

from bleak.backends.scanner import BaseBleakScanner, AdvertisementData
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from android.permissions import request_permissions, Permission
from jnius import autoclass, cast, PythonJavaClass, java_method

class _java:
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    ScanCallback = autoclass('android.bluetooth.le.ScanCallback')
    ScanFilter = autoclass('android.bluetooth.le.ScanFilter')
    ScanFilterBuilder = autoclass('android.bluetooth.le.ScanFilter$Builder')
    ScanSettings = autoclass('android.bluetooth.le.ScanSettings')
    ScanSettingsBuilder = autoclass('android.bluetooth.le.ScanSettings$Builder')
    List = autoclass('java.util.ArrayList')
    PythonScanCallback = autoclass('com.github.hbldh.bleak.PythonScanCallback')

    STATE_OFF = BluetoothAdapter.STATE_OFF
    STATE_TURNING_ON = BluetoothAdapter.STATE_TURNING_ON
    STATE_ON = BluetoothAdapter.STATE_ON
    STATE_TURNING_OFF = BluetoothAdapter.STATE_TURNING_OFF

logger = logging.getLogger(__name__)

class BleakScannerP4Android(BaseBleakScanner):
    """The python-for-android Bleak BLE Scanner.

    Keyword Args:
        adapter (str): Bluetooth adapter to use for discovery. [ignored]
        filters (dict): A dict of filters to be applied on discovery. [unimplemented]

    """

    def __init__(self, **kwargs):
        super(BleakScannerP4Android, self).__init__(**kwargs)

        # kwarg "device" is for backwards compatibility
        self._adapter = kwargs.get("adapter", kwargs.get("device", None))

        self._devices = {}

        # Discovery filters
        self._filters = kwargs.get("filters", {})

    async def start(self):
        print('start')
        loop = asyncio.get_event_loop()
        permission_acknowledged = loop.create_future()
        def handle_permissions(permissions, grantResults):
            if any(grantResults):
                loop.call_soon_threadsafe(permission_acknowledged.set_result, grantResults)
            else:
                loop.call_soon_threadsafe(permission_acknowledged.set_exception(BleakError("User denied access to " + str(permissions))))
        request_permissions([
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
                'android.permission.ACCESS_BACKGROUND_LOCATION'],
            handle_permissions)
        await permission_acknowledged

        self._adapter = _java.BluetoothAdapter.getDefaultAdapter()
        if self._adapter is None:
            raise BleakError('Bluetooth is not supported on this hardware platform')
        if self._adapter.getState() != _java.STATE_ON:
            raise BleakError('Bluetooth is not turned on')

        callback = _PythonScanCallback(self, loop)
        self._android_callback = _java.PythonScanCallback(callback)
        
        self._scanner = self._adapter.getBluetoothLeScanner()
        print('scanner and callback acquired')

        filters = cast('java.util.List',_java.List())
        # filters could be built with _java.ScanFilterBuilder

        self._scanner.startScan(
            filters,
            _java.ScanSettingsBuilder().
                setScanMode(_java.ScanSettings.SCAN_MODE_LOW_LATENCY).
                setReportDelay(0).
                setPhy(_java.ScanSettings.PHY_LE_ALL_SUPPORTED).
                setNumOfMatches(_java.ScanSettings.MATCH_NUM_MAX_ADVERTISEMENT).
                setMatchMode(_java.ScanSettings.MATCH_MODE_AGGRESSIVE).
                setCallbackType(_java.ScanSettings.CALLBACK_TYPE_ALL_MATCHES).
                build(),
            self._android_callback)
        print('scan started')

        #try:
        #    await asyncio.wait_for(callback.status, timeout=0.2)
        #except asyncio.exceptions.TimeoutError:
        #    pass

    async def stop(self):
        print('stop')
        self._scanner.stopScan(self._android_callback)

    async def set_scanning_filter(self, **kwargs):
        self._filters = kwargs.get("filters", {})

    async def get_discovered_devices(self) -> List[BLEDevice]:
        return [*self._devices.values()]

class _PythonScanCallback(PythonJavaClass):
    __javainterfaces__ = ['com.github.hbldh.bleak.PythonScanCallback$Interface']
    __javacontext__ = 'app'

    _errors = {
        getattr(_java.ScanCallback, name): name
        for name in [
            'SCAN_FAILED_ALREADY_STARTED',
            'SCAN_FAILED_APPLICATION_REGISTRATION_FAILED',
            'SCAN_FAILED_FEATURE_UNSUPPORTED',
            'SCAN_FAILED_INTERNAL_ERROR'
        ]}

    def __init__(self, scanner, loop):
        self._scanner = scanner
        self._loop = loop
        self.status = self._loop.create_future()

    def __del__(self):
        print('DESTROYING SCANNER CALLBACK!  HAS SCANNING STOPPED?')

    @java_method('(I)V')
    def onScanFailed(self, errorCode):
        print('scan failed')
        self._loop.call_soon_threadsafe(self.status.set_exception, BleakError(self._errors[errorCode]))
    
    @java_method('(Landroid/bluetooth/le/ScanResult;)V')
    def onScanResult(self, result):
        print('scan result')
        if not self.status.done():
            self._loop.call_soon_threadsafe(self.status.set_result, True)
        device = result.getDevice()
        print('getting record')
        record = result.getScanRecord()
        print('getting uuids')
        service_uuids = record.getServiceUuids()
        print('enumerating uuids if there')
        if service_uuids is not None:
            service_uuids = [
                service_uuids[index].getUuid().toString()
                for index in range(len(service_uuids))]
        print('getting manufacturer data')
        manufacturer_data = record.getManufacturerSpecificData()
        print('enumeraitng manufacturer data')
        print(manufacturer_data)
        manufacturer_data = {
            manufacturer_data.keyAt(index): manufacturer_data.valueAt(index)
            for index in range(manufacturer_data.size())
        }
        #uuids = device.getUuids() # features
        print('constructing advertisement data')
        advertisement = AdvertisementData(
            local_name=record.getDeviceName(),
            manufacturer_data=manufacturer_data,
            #service_data=record.getServiceData(), # Map<ParcelUuid,byte[]> -> dict
            service_uuids=service_uuids,
            platform_data=(result,)
        )
        device = BLEDevice(
            device.getAddress(),
            device.getName(),
            rssi=result.getRssi(),
            uuids=service_uuids,
            #manufacturer_data=
        )
        self._scanner._devices[device.address] = device
        if self._scanner._callback:
            self._loop.call_soon_threadsafe(self._scanner._callback, device, advertisement)
