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

from android.broadcast import BroadcastReceiver
from jnius import autoclass, cast, PythonJavaClass, java_method

logger = logging.getLogger(__name__)

class java:
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
    BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
    BluetoothProfile = autoclass('android.bluetooth.BluetoothProfile')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = cast('android.app.Activity', PythonActivity.mActivity)
    context = cast('android.content.Context', activity.getApplicationContext())
    PythonBluetoothGattCallback = autoclass('com.github.hbldh.bleak.PythonBluetoothGattCallback')

    ACTION_BOND_STATE_CHANGED = java.BluetoothDevice.ACTION_BOND_STATE_CHANGED
    BOND_BONDED = java.BluetoothDevice.BOND_BONDED
    BOND_BONDING = java.BluetoothDevice.BOND_BONDING
    BOND_NONE = java.BluetoothDevice.BOND_NONE

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
        self._gatt = None

    # Connectivity methods

    async def connect(self, **kwargs) -> bool:
        """Connect to the specified GATT server.

        Returns:
            Boolean representing connection status.

        """
        loop = asyncio.get_event_loop()

        self._adapter = java.BluetoothAdapter.getDefaultAdapter()
        self._device = self._adapter.getRemoteDevice(self.address)
        
        callback = PythonBluetoothGattCallback(self, loop)
        self._gatt = await callback.connect()

        await self.get_services()
        return True

    async def disconnect(self) -> bool:
        """Disconnect from the specified GATT server.

        Returns:
            Boolean representing if device is disconnected.

        """
        logger.debug("Disconnecting from BLE device...")
        if self._gatt is None:
            # No connection exists. Either one hasn't been created or
            # we have already called disconnect and closed the gatt
            # connection.
            return True

        # Try to disconnect the actual device/peripheral
        try:
            self._gatt.disconnect()
        except Exception as e:
            logger.error("Attempt to disconnect device failed: {0}".format(e))

        is_disconnected = not await self.is_connected()

        # Reset all stored services.
        self.services = BleakGATTServiceCollection()
        self._services_resolved = False

        return is_disconnected

    async def pair(self, *args, **kwargs) -> bool:
        """Pair with the peripheral.

        You can use ConnectDevice method if you already know the MAC address of the device.
        Else you need to StartDiscovery, Trust, Pair and Connect in sequence.

        Returns:
            Boolean regarding success of pairing.

        """
        loop = asyncio.get_event_loop()

        # See if it is already paired.
        bond_state = self._device.getBondState()
        if bond_state == java.BOND_BONDED:
            return True
        elif bond_state == java.BOND_NONE:
            logger.debug(
                "Pairing to BLE device @ {0}".format(self.address)
            )
            if not self._device.createBond():
                raise BleakError(
                    "Could not initiate bonding with device @ {0}".format(self.address)
                )

        # boding is likely now in progress (state == BOND_BONDING)
        # register for the java.ACTION_BOND_STATE_CHANGED intent using BroadcastReceiver to wait for completion
        # new bond state is additionally included in intent

    # GATT services methods

    async def get_services(self) -> BleakGATTServiceCollection:
        """Get all services registered for this GATT server.

        Returns:
           A :py:class:`bleak.backends.service.BleakGATTServiceCollection` with this device's services tree.

        """
        if self._services_resolved:
            return self.services

        logger.debug("Get Services...")
        services = self._gatt.getServices()
        for i in range(len(services)):
            service = BleakGATTServiceP4Android(services[i])
            self.services.add_service(service)
            for characteristic in service.characteristics:
                self.services.add_characteristic(characteristic)
                for descriptor in characteristic.descriptors:
                    self.services.add_descriptor(descriptor)

        self._services_resolved = True
        return self.services

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
        getattr(java.BluetoothProfile, name): name
        for name in (
            'STATE_DISCONNECTED',
            'STATE_CONNECTING',
            'STATE_CONNECTED',
            'STATE_DISCONNECTING'
        )}

    def __init__(self, client, loop, device):
        self._client = client
        self._loop = loop
        self._device = device
        self.java = java.PythonBluetoothGattCallback(self)
        self.results = asyncio.Queue()

    async def connect(self):
        logger.debug("Connecting to BLE device @ {0}".format(self.address))
        self.gatt = self._device.connectGatt(java.context, False, self.java)
        await self.expect('onConnectionStateChange', 'STATE_CONNECTED')
        logger.debug("Connection succesful.")

        if not self.gatt.discoverServices():
            raise BleakError('failed to initiate service discovery')
        await self.expect('onServicesDiscovered')

        return self.gatt

    async def get(self):
        return await (await self.results.get())

    async def expect(self, *expected):
        results = await self.get()
        if results[:len(expected)] != expected[:]:
            raise BleakException('Expected', expected, 'got', results)
        return results[len(expected):]
        
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
