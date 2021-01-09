# -*- coding: utf-8 -*-
"""
BLE Client for python-for-android
"""
import asyncio
import logging
import uuid
import warnings
from typing import Callable, Union

from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak.backends.client import BaseBleakClient
from bleak.backends.p4android.service import BleakGATTServiceP4Android 
from bleak.backends.p4android.characteristic import BleakGATTCharacteristicP4Android 
from bleak.backends.p4android.descriptor import BleakGATTDescriptorP4Android 

from android.broadcast import BroadcastReceiver
from jnius import autoclass, cast, PythonJavaClass, java_method

logger = logging.getLogger(__name__)

print('client.py')
class _java:
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
    BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
    BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')
    BluetoothProfile = autoclass('android.bluetooth.BluetoothProfile')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = cast('android.app.Activity', PythonActivity.mActivity)
    context = cast('android.content.Context', activity.getApplicationContext())
    PythonBluetoothGattCallback = autoclass('com.github.hbldh.bleak.PythonBluetoothGattCallback')

    ACTION_BOND_STATE_CHANGED = BluetoothDevice.ACTION_BOND_STATE_CHANGED
    EXTRA_BOND_STATE = BluetoothDevice.EXTRA_BOND_STATE
    BOND_BONDED = BluetoothDevice.BOND_BONDED
    BOND_BONDING = BluetoothDevice.BOND_BONDING
    BOND_NONE = BluetoothDevice.BOND_NONE
    WRITE_TYPE_NO_RESPONSE = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
    WRITE_TYPE_DEFAULT = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
    WRITE_TYPE_SIGNED = BluetoothGattCharacteristic.WRITE_TYPE_SIGNED
print('java consts loaded')

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

        self._adapter = _java.BluetoothAdapter.getDefaultAdapter()
        if self._adapter is None:
            raise BleakError('Bluetooth is not supported on this hardware platform')
        if self._adapter.getState() != _java.STATE_ON:
            raise BleakError('Bluetooth is not turned on')

        self._device = self._adapter.getRemoteDevice(self.address)
        
        self._callback = _PythonBluetoothGattCallback(self, loop)

        logger.debug("Connecting to BLE device @ {0}".format(self.address))

        connstate = self._callback.prepare('onConnectionStateChange')
        self._gatt = self._device.connectGatt(_java.context, False, self._callback.java)
        await self_callback.expect(connstate, 'STATE_CONNECTED')

        logger.debug("Connection succesful.")

        discoverstate = self._callback.prepare('onServicesDiscovered')
        if not self._gatt.discoverServices():
            raise BleakError('failed to initiate service discovery')

        await self._callback.expect(discoverstate)

        self._gatt = await callback.connect()
        self._subscriptions = {}

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
            if self._callback.prepare_unless('onConnectionStateChange', 'STATE_DISCONNECTED'):
                self._gatt.disconnect()
                await self._callback.expect(connstate, 'STATE_DISCONNECTED')
            self._gatt.close()
            self._gatt = None
        except Exception as e:
            logger.error("Attempt to disconnect device failed: {0}".format(e))

        is_disconnected = not await self.is_connected()

        if is_disconnected:
            self._gatt = None

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

        bondedFuture = loop.create_future()
        def handleBondStateChanged(context, intent):
            bond_state = intent.getIntExtra(_java.EXTRA_BOND_STATE, -1)
            if bond_state == -1:
                loop.call_soon_threadsafe(
                    bondedFuture.set_exception,
                    BleakError('Unexpected bond state {}'.format(bond_state))
                )
            elif bond_state == _java.BOND_NONE:
                loop.call_soon_threadsafe(
                    bondedFuture.set_exception,
                    BleakError('Device with address {0} could not be paired with.'.format(self.address))
                )
            elif bond_state == _java.BOND_BONDED:
                loop.call_soon_threadsafe(
                    bondedFuture.set_result,
                    True
                )

        with BroadcastReceiver(handleBondStateChanged, actions=[ACTION_BOND_STATE_CHANGED]):
            # See if it is already paired.
            bond_state = self._device.getBondState()
            if bond_state == _java.BOND_BONDED:
                return True
            elif bond_state == _java.BOND_NONE:
                logger.debug(
                    "Pairing to BLE device @ {0}".format(self.address)
                )
                if not self._device.createBond():
                    raise BleakError(
                        "Could not initiate bonding with device @ {0}".format(self.address)
                    )
            return await bondedFuture

    async def unpair(self) -> bool:
        """Unpair with the peripheral.

        Returns:
            Boolean regarding success of unpairing.

        """
        warnings.warn(
            "Unpairing is seemingly unavailable in the Android API at the moment."
        )
        return False

    async def is_connected(self) -> bool:
        """Check connection status between this client and the server.

        Returns:
            Boolean representing connection status.

        """
        state = await self._callback.get_unthreadsafe('onConnectionStateChange')
        return state == 'STATE_DISCONNECTED'

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

    # IO methods

    async def read_gatt_char(
        self,
        char_specifier: Union[BleakGATTCharacteristicP4Android, int, str, uuid.UUID],
        **kwargs
    ) -> bytearray:
        """Perform read operation on the specified GATT characteristic.

        Args:
            char_specifier (BleakGATTCharacteristicP4Android, int, str or UUID): The characteristic to read from,
                specified by either integer handle, UUID or directly by the
                BleakGATTCharacteristicP4Android object representing it.

        Returns:
            (bytearray) The read data.

        """
        if not isinstance(char_specifier, BleakGATTCharacteristicP4Android):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier

        if not characteristic:
            raise BleakError(
                "Characteristic with UUID {0} could not be found!".format(
                    char_specifier
                )
            )

        # so, if we want parallel reads, we'll want to multiplex these callbacks
        # just like the notification callbacks.
        # the easy way is to bundle handle up with the identifier
        valuestate = self.callback.prepare(('onCharacteristicRead', characteristic.handle))
        if not self._gatt.readCharacteristic(characteristic.obj):
            raise BleakError(
                "Failed to initiate read from characteristic {0}".format(
                    characteristic.uuid
                )
            )
        value, = await self.callback.expect(valuestate)
        value = bytearray(value)
        logger.debug(
            "Read Characteristic {0} | {1}: {2}".format(
                characteristic.uuid, self._address, value
            )
        )
        return value

    async def read_gatt_descriptor(
        self,
        desc_specifier: Union[BleakGATTDescriptorP4Android, str, uuid.UUID],
        **kwargs
    ) -> bytearray:
        """Perform read operation on the specified GATT descriptor.

        Args:
            desc_specifier (BleakGATTDescriptorP4Android, str or UUID): The descriptor to read from,
                specified by either UUID or directly by the
                BleakGATTDescriptorP4Android object representing it.

        Returns:
            (bytearray) The read data.

        """
        if not isinstance(desc_specifier, BleakGATTDescriptorP4Android):
            descriptor = self.services.get_descriptor(descriptor)
        else:
            descriptor = desc_specifier

        if not descriptor:
            raise BleakError(
                "Descriptor with UUID {0} was not found!".format(
                    desc_specifier
                )
            )

        valuestate = self.callback.prepare(('onDescriptorRead', descriptor.uuid))
        if not self._gatt.readDescriptor(descriptor.obj):
            raise BleakError(
                "Failed to initiate read from descriptor {0}".format(
                    descriptor.uuid
                )
            )
        value, = await self.callback.expect(valuestate)
        value = bytearray(value)

        logger.debug(
            "Read Descriptor {0} | {1}: {2}".format(descriptor.uuid, self.address, value)
        )

        return value

    async def write_gatt_char(
        self,
        char_specifier: Union[BleakGATTCharacteristicP4Android, int, str, uuid.UUID],
        data: bytearray,
        response: bool = False,
    ) -> None:
        """Perform a write operation on the specified GATT characteristic.

        Args:
            char_specifier (BleakGATTCharacteristicP4Android, int, str or UUID): The characteristic to write
                to, specified by either integer handle, UUID or directly by the
                BleakGATTCharacteristicP4Android object representing it.
            data (bytes or bytearray): The data to send.
            response (bool): If write-with-response operation should be done. Defaults to `False`.

        """
        if not isinstance(char_specifier, BleakGATTCharacteristicP4Android):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier

        if not characteristic:
            raise BleakError("Characteristic {0} was not found!".format(char_specifier))

        if (
            "write" not in characteristic.properties
            and "write-without-response" not in characteristic.properties
        ):
            raise BleakError(
                "Characteristic %s does not support write operations!"
                % str(characteristic.uuid)
            )
        if not response and "write-without-response" not in characteristic.properties:
            response = True
            # Force response here, since the device only supports that.
        if (
            response
            and "write" not in characteristic.properties
            and "write-without-response" in characteristic.properties
        ):
            response = False
            logger.warning(
                "Characteristic %s does not support Write with response. Trying without..."
                % str(characteristic.uuid)
            )

        if response:
            characteristic.obj.setWriteType(_java.WRITE_TYPE_DEFAULT)
        else:
            characteristic.obj.setWriteType(_java.WRITE_TYPE_NO_RESPONSE)

        characteristic.obj.setValue(data)

        writestate = self.callback.prepare(('onCharacteristicWrite', characteristic.handle))
        if not self._gatt.writeCharacteristic(characteristic.obj):
            raise BleakError(
                "Failed to initiate write to characteristic {0}".format(
                    characteristic.uuid
                )
            )
        await self.callback.expect(writestate)

        logger.debug(
            "Write Characteristic {0} | {1}: {2}".format(
                characteristic.uuid, self.address, data
            )
        )

    async def write_gatt_descriptor(
        self,
        desc_specifier: Union[BleakGATTDescriptorP4Android, str, uuid.UUID],
        data: bytearray,
    ) -> None:
        """Perform a write operation on the specified GATT descriptor.

        Args:
            desc_specifier (BleakGATTDescriptorP4Android, str or UUID): The descriptor to write
                to, specified by either UUID or directly by the
                BleakGATTDescriptorP4Android object representing it.
            data (bytes or bytearray): The data to send.

        """
        if not isinstance(desc_specifier, BleakGATTDescriptorP4Android):
            descriptor = self.services.get_descriptor(desc_specifier)
        else:
            descriptor = desc_specifier

        if not descriptor:
            raise BleakError("Descriptor {0} was not found!".format(desc_specifier))

        descriptor.obj.setValue(data)
        writestate = self.callback.prepare(('onDescriptorWrite', descriptor.uuid))
        if not self._gatt.writeDescriptor(descriptor.obj):
            raise BleakError(
                "Failed to initiate write to descriptor {0}".format(
                    descriptor.uuid
                )
            )
        await self.callback.expect(writestate)

        logger.debug(
            "Write Descriptor {0} | {1}: {2}".format(handle, self.address, data)
        )

    async def start_notify(
        self,
        char_specifier: Union[BleakGATTCharacteristicP4Android, int, str, uuid.UUID],
        callback: Callable[[int, bytearray], None],
        **kwargs
    ) -> None:
        """Activate notifications/indications on a characteristic.

        Callbacks must accept two inputs. The first will be an integer handle of the characteristic generating the
        data and the second will be a ``bytearray`` containing the data sent from the connected server.

        .. code-block:: python

            def callback(sender: int, data: bytearray):
                print(f"{sender}: {data}")
            client.start_notify(char_uuid, callback)

        Args:
            char_specifier (BleakGATTCharacteristicP4Android, int, str or UUID): The characteristic to activate
                notifications/indications on a characteristic, specified by either integer handle,
                UUID or directly by the BleakGATTCharacteristicP4Android object representing it.
            callback (function): The function to be called on notification.
        """
        if not isinstance(char_specifier, BleakGATTCharacteristicBlueZDBus):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier

        if not characteristic:
            raise BleakError(
                "Characteristic with UUID {0} could not be found!".format(
                    char_specifier
                )
            )

        if not self._gatt.setCharacteristicNotification(characteristic.obj, True):
            raise BleakError(
                "Failed to enable notification for characteristic {0}".format(
                    characteristic.uuid
                )
            )

        self._subscriptions[characteristic.handle] = callback

    async def stop_notify(
        self,
        char_specifier: Union[BleakGATTCharacteristicP4Android, int, str, uuid.UUID],
    ) -> None:
        """Deactivate notification/indication on a specified characteristic.

        Args:
            char_specifier (BleakGATTCharacteristicP4Android, int, str or UUID): The characteristic to deactivate
                notification/indication on, specified by either integer handle, UUID or
                directly by the BleakGATTCharacteristicP4Android object representing it.

        """
        if not isinstance(char_specifier, BleakGATTCharacteristicP4Android):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier
        if not characteristic:
            raise BleakError("Characteristic {} not found!".format(char_specifier))

        if not self._gatt.setCharacteristicNotification(characteristic.obj, False):
            raise BleakError(
                "Failed to disable notification for characteristic {0}".format(
                    characteristic.uuid
                )
            )
        del self._subscriptions[characteristic.handle]

    def _dispatch_notification(self, handle, data):
        self._subscriptions[handle](handle, data)

print('main class defined')
class _PythonBluetoothGattCallback(PythonJavaClass):
    __javainterfaces__ = ['com.github.hbldh.bleak.PythonBluetoothGattCallback$Interface']
    __javacontext__ = 'app'

    print('status codes')
    _status_codes = {
        getattr(_java.BluetoothGatt, name): name
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

    print('success field')
    GATT_SUCCESS = _java.BluetoothGatt.GATT_SUCCESS

    print('connection states')
    _connection_states = {
        getattr(_java.BluetoothProfile, name): name
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
        self.java = _java.PythonBluetoothGattCallback(self)
        self.states = {}

    def _if_expected(self, result, expected):
        if result[:len(expected)] == expected[:]:
            return result[len(expected):]
        else:
            return None

    def prepare(self, source):
        future = self._loop.create_future()
        self.states[source] = future
        return future

    def prepare_unless(self, source, *expected):
        if source in self.states:
            future = self.states[source]
            if future.done():
                match = self._if_expected(future.result(), expected)
                if match:
                    return match
                else:
                    future = self._loop.create_future()
        else:
            future = self._loop.create_future()
        self.states[source] = future
        return future

    async def expect(self, future, *expected):
        #outdated = future.done()
        #if outdated:
        #    result = future.result():
        #else:
        #    result = await future
        #match = self._if_expected(result, expected)
        #if outdated and not match:
        #    del self.states[source]
        #    result = await self.get_unthreadsafe(source)
        #    match = self._if_expected(result, expected)
        result = await future
        match = self._if_expected(result, expected)
        if match:
            return match
        else:
            raise BleakException('Expected', expected, 'got', result)

    def _result_state_unthreadsafe(self, status, source, data):
        future = self.states[source]
        if status == _PythonBluetoothGattCallback.GATT_SUCCESS:
            future.set_result(data)
        else:
            status = _PythonBluetoothGattCallback._status_codes[status]
            future.set_exception(BleakException(source, status, *data))
        
    def _result_state_threadsafe(self, status, source, *data):
        self._loop.call_soon_threadsafe(self._result_unthreadsafe, status, source, data)

    @java_method('(II)V')
    def onConnectionStateChange(self, status, state):
        state = _PythonBluetoothGattCallback._connection_states[new_state]
        self._result_state_threadsafe(status, 'onConnectionStateChange', state, state)

    @java_method('(I)V')
    def onServicesDiscovered(self, status):
        self._result_state_threadsafe(status, 'onServicesDiscovered')

    @java_method('(I[B)V')
    def onCharacteristicChanged(self, handle, value):
        self._loop.call_soon_threadsafe(self._client._dispatch_notification, handle, value)

    @java_method('(II[B)V')
    def onCharacteristicRead(self, handle, status, value):
        self._result_state_threadsafe(status, ('onCharacteristicRead', handle), value)

    @java_method('(LII)V')
    def onCharacteristicWrite(self, handle, status):
        self._result_state_threadsafe(status, ('onCharacteristicWrite', handle))
    
    @java_method('(Ljava/lang/String;I[B)V')
    def onDescriptorRead(self, uuid, status, value):
        self._result_state_threadsafe(status, ('onDescriptorRead', uuid), value)

    @java_method('(Ljava/lang/String;I)V')
    def onDescriptorWrite(self, uuid, status):
        self._result_state_threadsafe(status, ('onDescriptorWrite', uuid))

