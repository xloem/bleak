import asyncio

from bleak.backends.scanner import BaseBleakScanner, AdvertisementData
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from android.permissions import request_permissions, Permission
from jnius import autoclass, cast, PythonJavaClass, java_method

class java:
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    ScanCallback = autoclass('android.bluetooth.le.ScanCallback')
    ScanFilter = autoclass('android.bluetooth.le.ScanFilter')
    ScanFilterBuilder = autoclass('android.bluetooth.le.ScanFilter.Builder')
    ScanSettings = autoclass('android.bluetooth.le.ScanSettings')
    ScanSettingsBuilder = autoclass('android.bluetooth.le.ScanSettings.Builder')
    List = autoclass('java.util.ArrayList')
    PythonScanCallback = autoclass('com.github.hbldh.bleak.PythonScanCallback')

logger = logging.getLogger(__name__)

class BleakScannerP4Android(BaseBleakScanner):
    """The python-for-android Bleak BLE Scanner.

    Keyword Args:
        adapter (str): Bluetooth adapter to use for discovery. [ignored]
        filters (dict): A dict of filters to be applied on discovery.

    """

    def __init__(self, **kwargs):
        super(BleakScannerP4Android, self).__init__(**kwargs)

        # kwarg "device" is for backwards compatibility
        self._adapter = kwargs.get("adapter", kwargs.get("device", None))

        self._devices = {}

        # Discovery filters
        self._filters = kwargs.get("filters", {})

    async def start(self):
        loop = asyncio.get_event_loop()
        permission_acknowledged = loop.create_future()
        def handle_permissions(permissions, grantResults):
            if any(grantResults):
                permission_acknowledged.set_result(grantResults)
            else:
                permission_acknowledged.set_exception(BleakError("User denied access to " + str(permissions))
        request_permissions([
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARS_LOCATION,
                'android.permission.ACCESS_BACKGROUND_LOCATION'],
            handle_permissions)
        await permission_acknowledged

        self._adapter = java.BluetoothAdapter.getDefaultAdaper()

        callback = PythonScanCallback(self, loop)
        self._android_callback = java.PythonScanCallback(callback)
        
        self._scanner = self._adapter.getBluetoothLeScanner()

        filters = cast('java.util.list',java.List())
        # filters could be built with java.ScanFilterBuilder

        self._scanner.startScan(
            filters,
            java.ScanSettingsBuilder().
                setScanMode(java.ScanSettings.SCAN_MODE_LOW_LATENCY).
                setReportDelay(0).
                setPhy(java.ScanSettings.PHY_LE_ALL_SUPPORTED).
                setNumOfMatches(java.ScanSettings.MATCH_NUM_MAX_ADVERTISEMENT).
                setMatchMode(java.ScanSettings.MATCH_MODE_AGGRESSIVE).
                setCallbackType(ScanSettings.CALLBACK_TYPE_ALL_MATCHES).
                build(),
            self._android_callback)

        await callback.status

    async def stop(self):
        self._scanner.stopScan(self._android_callback)

    async def get_discovered_devices(self) -> List[BLEDevice]:
        return [*self._devices.values()]

class PythonScanCallback(PythonJavaClass):
    __javainterfaces__ = ['PythonScanCallback$Interface']
    __javacontext__ = 'app'

    _errors = {
        getattr(java.ScanCallback, name): name
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

    @java_method('(I)V')
    def onScanFailed(self, errorCode):
        self.status.set_exception(BleakError(self._errors[errorCode]()))
    
    @java_method('(Landroid/bluetooth/le/ScanResult;)V')
    def onScanResult(self, result):
        if not self.status.done()
            self.status.set_result(True)
        device = result.getDevice()
        record = result.getScanRecord()
        advertisement = AdvertisementData(
            local_name=record,getDeviceName(),
            #manufacturer_data=record.getManufacturerSpecificData(), # SparseArray -> dict
            #service_data=record.getServiceData(), # Map<ParcelUuid,byte[]> -> dict
            #service_uuids=record.getServiceUuids(), # List<ParcelUuid> -> list,
            platform_data=(result,)
        )
        device = BLEDevice(
            device.getAddress(),
            device.getAlias(),
            rssi=result.getRssi(),
            #uuids=,
            #manufacturer_data=
        )
        self._scanner._devices[device.address] = device
        if self._scanner._callback:
            self._loop.call_soon(self._scanner._callback, device, advertisement)
