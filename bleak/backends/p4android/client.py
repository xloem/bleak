# -*- coding: utf-8 -*-
"""
BLE Client for python-for-android
"""
import asyncio
import logging
from typing import Callable, Union

from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakError
from bleak.backends.client import BaseBleakClient

from jnius import autoclass, cast, PythonJavaClass, java_method

logger = logging.getLogger(__name__)

class java:
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
    BluetoothProfile = autoclass('android.bluetooth.BluetoothProfile')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = cast('android.app.Activity', PythonActivity.mActivity)
    context = cast('android.content.Context', activity.getApplicationContext())
    PythonBluetoothGattCallback = autoclass('com.github.hbldh.bleak.PythonBluetoothGattCallback')

class BleakClientP4Android(BaseBleakClient):
    """A python-for-android Bleak Client

    Args:
        address_or_ble_device (`BLEDevice` or str): The Bluetooth address of the BLE peripheral to connect to or the `BLEDevice` object representing it.

    Keyword Args:
        timeout (float): Timeout for required ``BleakScanner.find_device_by_address`` call. Defaults to 10.0.
        disconnected_callback (callable): Callback that will be scheduled in the
            event loop when the client is disconnected. The callable must take one
            argument, which will be this client object.
        adapter (str): Bluetooth adapter to use for discovery.
    """

    def __init__(self, address_or_ble_device: Union[BLEDevice, str], **kwargs):
        super(BleakClientBlueZDBus, self).__init__(address_or_ble_device, **kwargs)
        # kwarg "device" is for backwards compatibility
        self._adapter = kwargs.get("adapter", kwargs.get("device", None))

    # Connectivity methods

    async def connect(self, **kwargs) -> bool:
        """Connect to the specified GATT server.

        Keyword Args:
            timeout (float): Timeout for required ``BleakScanner.find_device_by_address`` call. Defaults to 10.0.

        Returns:
            Boolean representing connection status.

        """
        loop = asyncio.get_event_loop()

        self._adapter = java.BluetoothAdapter.getDefaultAdapter()
        self._device = self._adapter.getRemoteDevice(self.address)

        logger.debug(
            "Connecting to BLE device @ {0}".format(
                self.address
            )
        )
        
        callback = PythonBluetoothGattCallback(self, loop)
        gatt = self._device.connectGatt(java.context, False, callback.java)
        await callback.get()

        if not gatt.discoverServices():
            raise BleakError('failed to initiate service discovery')
        await callback.get()

class PythonBluetoothGattCallback(PythonJavaClass):
    __javainterfaces__ = ['com.github.hbldh.bleak.PythonBluetoothGattCallback$Interface']
    __javacontext__ = 'app'

    _status_codes = {
        getattr(java.BluetoothGatt, name): name
        for name in (
            'GATT_SUCCESS',
            'GATT_READ_NOT_PERMITTED',
            'GATT_WRITE_NOT_PERMITTED',
            'GATT_REQUEST_NOT_SUPPORTED',
            'GATT_INSUFFICIENT_AUTHENTICATION',
            'GATT_INVALID_OFFSET',
            'GATT_INVALID_ATTRIBUTE_LENGTH',
            'GATT_INSUFFICIENT_ENCRYPTION',
            'GATT_CONNECTION_CONGESTED',
            'GATT_FAILURE',
        )}
    GATT_SUCCESS = java.BluetoothGatt.GATT_SUCCESS

    _connection_states = {
        getattr(java.BluetoothGatt, name): name
        for name in (
            'STATE_DISCONNECTED',
            'STATE_CONNECTING',
            'STATE_CONNECTED',
            'STATE_DISCONNECTING'
        )}

    def __init__(self, client, loop):
        self._client = client
        self._loop = loop
        self.java = java.PythonBluetoothGattCallback(self)
        self.results = asyncio.Queue()

    async def get(self):
        return await await self.results.get()

    async def expect(self, *expected):
        results = self.get()
        results.
        if source != expected_source:
            raise BleakException('Expected', expected_source, 'got', source, *result)
        return result
        
    def _result(status, source, *data):
        future = self._loop.create_future()
        if status == PythonBluetoothGattCallback.GATT_SUCCESS:
            future.set_result((source, *data))
        else:
            status = PythonBluetoothGattCallback._status_codes[status]
            future.set_exception(BleakException(source, status, *data))
        self.results.put(future)

    @java_method('(II)V')
    def onConnectionStateChange(status, state):
        state = PythonBluetoothGattCallback._connection_states[new_state]
        self._result(status, 'onConnectionStateChange', state, state)

    @java_method('(I)V')
    def onServicesDiscovered(status):
        self._result(status, 'onServicesDiscovered')
