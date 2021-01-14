# -*- coding: utf-8 -*-

import asyncio
import logging
from typing import List
import warnings

from bleak.backends.scanner import BaseBleakScanner, AdvertisementData
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from android.broadcast import BroadcastReceiver
from android.permissions import request_permissions, Permission
from jnius import autoclass, cast, PythonJavaClass, java_method

from . import utils

class _java:
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    ScanCallback = autoclass('android.bluetooth.le.ScanCallback')
    ScanFilter = autoclass('android.bluetooth.le.ScanFilter')
    ScanFilterBuilder = autoclass('android.bluetooth.le.ScanFilter$Builder')
    ScanSettings = autoclass('android.bluetooth.le.ScanSettings')
    ScanSettingsBuilder = autoclass('android.bluetooth.le.ScanSettings$Builder')
    List = autoclass('java.util.ArrayList')
    PythonScanCallback = autoclass('com.github.hbldh.bleak.PythonScanCallback')

    ACCESS_FINE_LOCATION = Permission.ACCESS_FINE_LOCATION
    ACCESS_COARSE_LOCATION = Permission.ACCESS_COARSE_LOCATION
    ACCESS_BACKGROUND_LOCATION = 'android.permission.ACCESS_BACKGROUND_LOCATION'

    ACTION_STATE_CHANGED = BluetoothAdapter.ACTION_STATE_CHANGED
    EXTRA_STATE = BluetoothAdapter.EXTRA_STATE

    STATE_ERROR = BluetoothAdapter.ERROR
    STATE_OFF = BluetoothAdapter.STATE_OFF
    STATE_TURNING_ON = BluetoothAdapter.STATE_TURNING_ON
    STATE_ON = BluetoothAdapter.STATE_ON
    STATE_TURNING_OFF = BluetoothAdapter.STATE_TURNING_OFF

    SCAN_FAILED_NAMES = {
        ScanCallback.SCAN_FAILED_ALREADY_STARTED: 'SCAN_FAILED_ALREADY_STARTED',
        ScanCallback.SCAN_FAILED_APPLICATION_REGISTRATION_FAILED: 'SCAN_FAILED_APPLICATION_REGISTRATION_FAILED',
        ScanCallback.SCAN_FAILED_FEATURE_UNSUPPORTED: 'SCAN_FAILED_FEATURE_UNSUPPORTED',
        ScanCallback.SCAN_FAILED_INTERNAL_ERROR: 'SCAN_FAILED_INTERNAL_ERROR'
    }
    SCAN_FAILED_APPLICATION_REGISTRATION_FAILED = ScanCallback.SCAN_FAILED_APPLICATION_REGISTRATION_FAILED

logger = logging.getLogger(__name__)

class BleakScannerP4Android(BaseBleakScanner):

    __scanner = None

    """The python-for-android Bleak BLE Scanner.

    Keyword Args:
        adapter (str): Bluetooth adapter to use for discovery. [ignored]
        filters (dict): A dict of filters to be applied on discovery. [unimplemented]

    """

    def __init__(self, **kwargs):
        super(BleakScannerP4Android, self).__init__(**kwargs)

        # kwarg "device" is for backwards compatibility
        self.__adapter = kwargs.get("adapter", kwargs.get("device", None))

        self._devices = {}
        self.__javascanner = None
        self.__callback = None

        # Discovery filters
        self._filters = kwargs.get("filters", {})

    def __del__(self):
        self.__stop()

    async def start(self):
        print('start')
        if BleakScannerP4Android.__scanner is not None:
            raise BleakError('A BleakScanner is already scanning on this adapter.')
        loop = asyncio.get_event_loop()

        if self.__javascanner is None:
            if self.__callback is None:
                self.__callback = _PythonScanCallback(self, loop)

            permission_acknowledged = loop.create_future()
            def handle_permissions(permissions, grantResults):
                if any(grantResults):
                    loop.call_soon_threadsafe(permission_acknowledged.set_result, grantResults)
                else:
                    loop.call_soon_threadsafe(permission_acknowledged.set_exception(BleakError("User denied access to " + str(permissions))))
            request_permissions([
                    _java.ACCESS_FINE_LOCATION,
                    _java.ACCESS_COARSE_LOCATION,
                    _java.ACCESS_BACKGROUND_LOCATION],
                handle_permissions)
            await permission_acknowledged
    
            self.__adapter = _java.BluetoothAdapter.getDefaultAdapter()
            if self.__adapter is None:
                raise BleakError('Bluetooth is not supported on this hardware platform')
            if self.__adapter.getState() != _java.STATE_ON:
                raise BleakError('Bluetooth is not turned on')
        
            self.__javascanner = self.__adapter.getBluetoothLeScanner()
            print('SCANNER IS', repr(self.__javascanner))

        BleakScannerP4Android.__scanner = self

        filters = cast('java.util.List',_java.List())
        # filters could be built with _java.ScanFilterBuilder

        scanfuture = self.__callback.perform_and_wait(
            dispatchApi = self.__javascanner.startScan,
            dispatchParams = (
                filters,
                _java.ScanSettingsBuilder().
                    setScanMode(_java.ScanSettings.SCAN_MODE_LOW_LATENCY).
                    setReportDelay(0).
                    setPhy(_java.ScanSettings.PHY_LE_ALL_SUPPORTED).
                    setNumOfMatches(_java.ScanSettings.MATCH_NUM_MAX_ADVERTISEMENT).
                    setMatchMode(_java.ScanSettings.MATCH_MODE_AGGRESSIVE).
                    setCallbackType(_java.ScanSettings.CALLBACK_TYPE_ALL_MATCHES).
                    build(),
                self.__callback.java
            ),
            resultApi = 'onScan',
            return_indicates_status = False
        )
        self.__javascanner.flushPendingScanResults(self.__callback.java)

        try:
            await asyncio.wait_for(scanfuture, timeout=0.2)
        except asyncio.exceptions.TimeoutError:
            pass
        except BleakError as bleakerror:
            print('errory !!!')
            logging.debug(repr(bleakerror) + repr(bleakerror.args))
            await self.stop()
            if bleakerror.args != ('onScan', 'SCAN_FAILED_APPLICATION_REGISTRATION_FAILED'):
                raise bleakerror
            else:
                # there's probably a clearer solution to this if android source and vendor
                # documentation are reviewed for the meaning of the error
                # https://stackoverflow.com/questions/27516399/solution-for-ble-scans-scan-failed-application-registration-failed
                warnings.warn('BT API gave SCAN_FAILED_APPLICATION_REGISTRATION_FAILED.  Resetting adapter.')
                def handlerWaitingForState(state, stateFuture):
                    def handleAdapterStateChanged(context, intent):
                        adapter_state = intent.getIntExtra(_java.EXTRA_STATE, _java.STATE_ERROR)
                        if adapter_state == _java.STATE_ERROR:
                            loop.call_soon_threadsafe(
                                stateOffFuture.set_exception,
                                BleakError('Unexpected adapter state {}'.format(adapter_state))
                            )
                        elif adapter_state == state:
                            loop.call_soon_threadsafe(
                                stateFuture.set_result,
                                adapter_state
                            )
                    return handleAdapterStateChanged

                stateOffFuture = loop.create_future()
                receiver = BroadcastReceiver(handlerWaitingForState(_java.STATE_OFF, stateOffFuture), actions=[_java.ACTION_STATE_CHANGED])
                receiver.start()
                try:
                    print('turning off')
                    self.__adapter.disable()
                    print('waiting for state=off')
                    await stateOffFuture
                finally:
                    receiver.stop()

                stateOnFuture = loop.create_future()
                receiver = BroadcastReceiver(handlerWaitingForState(_java.STATE_ON, stateOnFuture), actions=[_java.ACTION_STATE_CHANGED])
                try:
                    print('turning on')
                    self.__adapter.enable()
                    print('waiting for state=on')
                    await stateOnFuture
                finally:
                    receiver.stop()

                return await self.start()

    def __stop(self):
        print('stop')
        if self.__javascanner is not None:
            self.__javascanner.stopScan(self.__callback.java)
            BleakScannerP4Android.__scanner = None
            self.__javascanner = None

    async def stop(self):
        self.__stop()

    async def set_scanning_filter(self, **kwargs):
        self._filters = kwargs.get("filters", {})

    async def get_discovered_devices(self) -> List[BLEDevice]:
        return [*self._devices.values()]

class _PythonScanCallback(utils.AsyncJavaCallbacks):
    __javainterfaces__ = ['com.github.hbldh.bleak.PythonScanCallback$Interface']

    def __init__(self, scanner, loop):
        super().__init__(loop)
        self._scanner = scanner
        self.java = _java.PythonScanCallback(self)
        print('INIT SCANNER CALLBACK!')

    def __del__(self):
        print('DESTROYING SCANNER CALLBACK!  HAS SCANNING STOPPED?')

    def result_state(self, status_str, name, *data):
        self._loop.call_soon_threadsafe(self._result_state_unthreadsafe, status_str, name, data)

    @java_method('(I)V')
    def onScanFailed(self, errorCode):
        self.result_state(_java.SCAN_FAILED_NAMES[errorCode], 'onScan')
    
    @java_method('(Landroid/bluetooth/le/ScanResult;)V')
    def onScanResult(self, result):
        device = result.getDevice()
        record = result.getScanRecord()
        service_uuids = record.getServiceUuids()
        if service_uuids is not None:
            service_uuids = [
                service_uuids[index].getUuid().toString()
                for index in range(len(service_uuids))]
        manufacturer_data = record.getManufacturerSpecificData()
        manufacturer_data = {
            manufacturer_data.keyAt(index): manufacturer_data.valueAt(index)
            for index in range(manufacturer_data.size())
        }
        service_data_iterator = record.getServiceData().entrySet().iterator()
        service_data = {}
        while service_data_iterator.hasNext():
            entry = service_data_iterator.next()
            service_data[entry.getKey().toString()] = bytearray(entry.getValue().tolist())
        advertisement = AdvertisementData(
            local_name=record.getDeviceName(),
            manufacturer_data=manufacturer_data,
            service_data=service_data,
            service_uuids=service_uuids,
            platform_data=(result,)
        )
        device = BLEDevice(
            device.getAddress(),
            device.getName(),
            rssi=result.getRssi(),
            uuids=service_uuids,
            manufacturer_data=manufacturer_data
        )
        self._scanner._devices[device.address] = device
        if 'onScan' not in self.states:
            self.result_state(None, 'onScan', device)
        if self._scanner._callback:
            self._loop.call_soon_threadsafe(self._scanner._callback, device, advertisement)
