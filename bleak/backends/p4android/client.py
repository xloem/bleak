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

    STATE_OFF = BluetoothAdapter.STATE_OFF
    STATE_TURNING_ON = BluetoothAdapter.STATE_TURNING_ON
    STATE_ON = BluetoothAdapter.STATE_ON
    STATE_TURNING_OFF = BluetoothAdapter.STATE_TURNING_OFF
    TRANSPORT_AUTO = BluetoothDevice.TRANSPORT_AUTO
    TRANSPORT_BREDR = BluetoothDevice.TRANSPORT_BREDR
    TRANSPORT_LE = BluetoothDevice.TRANSPORT_LE
    ACTION_BOND_STATE_CHANGED = BluetoothDevice.ACTION_BOND_STATE_CHANGED
    EXTRA_BOND_STATE = BluetoothDevice.EXTRA_BOND_STATE
    BOND_BONDED = BluetoothDevice.BOND_BONDED
    BOND_BONDING = BluetoothDevice.BOND_BONDING
    BOND_NONE = BluetoothDevice.BOND_NONE
    GATT_SUCCESS = BluetoothGatt.GATT_SUCCESS
    WRITE_TYPE_NO_RESPONSE = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
    WRITE_TYPE_DEFAULT = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
    WRITE_TYPE_SIGNED = BluetoothGattCharacteristic.WRITE_TYPE_SIGNED

    GATT_STATUS_NAMES = {
        # https://developer.android.com/reference/android/bluetooth/BluetoothGatt
        # https://android.googlesource.com/platform/external/bluetooth/bluedroid/+/5738f83aeb59361a0a2eda2460113f6dc9194271/stack/include/gatt_api.h
        # https://android.googlesource.com/platform/system/bt/+/master/stack/include/gatt_api.h
        0x0000: 'GATT_SUCCESS',
        0x0001: 'GATT_INVALID_HANDLE',
        0x0002: 'GATT_READ_NOT_PERMIT',
        0x0003: 'GATT_WRITE_NOT_PERMIT',
        0x0004: 'GATT_INVALID_PDU',
        0x0005: 'GATT_INSUF_AUTHENTICATION',
        0x0006: 'GATT_REQ_NOT_SUPPORTED',
        0x0007: 'GATT_INVALID_OFFSET',
        0x0008: 'GATT_INSUF_AUTHORIZATION',
        0x0009: 'GATT_PREPARE_Q_FULL',
        0x000a: 'GATT_NOT_FOUND',
        0x000b: 'GATT_NOT_LONG',
        0x000c: 'GATT_INSUF_KEY_SIZE',
        0x000d: 'GATT_INVALID_ATTR_LEN',
        0x000e: 'GATT_ERR_UNLIKELY',
        0x000f: 'GATT_INSUF_ENCRYPTION',
        0x0010: 'GATT_UNSUPPORT_GRP_TYPE',
        0x0011: 'GATT_INSUF_RESOURCE',
        0x0012: 'GATT_DATABASE_OUT_OF_SYNC',
        0x0013: 'GATT_VALUE_NOT_ALLOWED',
        0x007f: 'GATT_TOO_SHORT',
        0x0080: 'GATT_NO_RESOURCES',
        0x0081: 'GATT_INTERNAL_ERROR',
        0x0082: 'GATT_WRONG_STATE',
        0x0083: 'GATT_DB_FULL',
        0x0084: 'GATT_BUSY',
        0x0085: 'GATT_ERROR',
        0x0086: 'GATT_CMD_STARTED',
        0x0087: 'GATT_ILLEGAL_PARAMETER',
        0x0088: 'GATT_PENDING',
        0x0089: 'GATT_AUTH_FAIL',
        0x008a: 'GATT_MORE',
        0x008b: 'GATT_INVALID_CFG',
        0x008c: 'GATT_SERVICE_STARTED',
        0x008d: 'GATT_ENCRYPED_NO_MITM',
        0x008e: 'GATT_NOT_ENCRYPTED',
        0x008f: 'GATT_CONGESTED',
        0x0090: 'GATT_DUP_REG',
        0x0091: 'GATT_ALREADY_OPEN',
        0x0092: 'GATT_CANCEL',
        0x00fd: 'GATT_CCC_CFG_ERR',
        0x00fe: 'GATT_PRC_IN_PROGRESS',
        0x00ff: 'GATT_OUT_OF_RANGE',
        0x0101: 'GATT_FAILURE',
    }
    GATT_SUCCESS = 0x0000

    CONNECTION_STATE_NAMES = {
        BluetoothProfile.STATE_DISCONNECTED: 'STATE_DISCONNECTED',
        BluetoothProfile.STATE_CONNECTING: 'STATE_CONNECTING',
        BluetoothProfile.STATE_CONNECTED: 'STATE_CONNECTED',
        BluetoothProfile.STATE_DISCONNECTING: 'STATE_DISCONNECTING'
    }

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
        super(BleakClientP4Android, self).__init__(address_or_ble_device, **kwargs)
        # kwarg "device" is for backwards compatibility
        self.__adapter = kwargs.get("adapter", kwargs.get("device", None))
        self.__gatt = None

    def __del__(self):
        if self.__gatt is not None:
            self.__gatt.close()

    # Connectivity methods

    async def connect(self, **kwargs) -> bool:
        """Connect to the specified GATT server.

        Returns:
            Boolean representing connection status.

        """
        loop = asyncio.get_event_loop()

        self.__adapter = _java.BluetoothAdapter.getDefaultAdapter()
        if self.__adapter is None:
            raise BleakError('Bluetooth is not supported on this hardware platform')
        if self.__adapter.getState() != _java.STATE_ON:
            raise BleakError('Bluetooth is not turned on')

        self.__device = self.__adapter.getRemoteDevice(self.address)
        
        self.__callbacks = _PythonBluetoothGattCallback(self, loop)

        logger.debug("Connecting to BLE device @ {0}".format(self.address))

        connstate = self.__callbacks.prepare('onConnectionStateChange')
        self.__gatt = self.__device.connectGatt(_java.context, False, self.__callbacks.java)
        await self.__callbacks.expect(connstate, 'STATE_CONNECTED')

        logger.debug("Connection succesful.")

        self._subscriptions = {}

        discoverstate = self.__callbacks.prepare('onServicesDiscovered')
        if not self.__gatt.discoverServices():
            raise BleakError('failed to initiate service discovery')

        await self.__callbacks.expect(discoverstate)

        await self.get_services()
        return True

    async def disconnect(self) -> bool:
        """Disconnect from the specified GATT server.

        Returns:
            Boolean representing if device is disconnected.

        """
        logger.debug("Disconnecting from BLE device...")
        if self.__gatt is None:
            # No connection exists. Either one hasn't been created or
            # we have already called disconnect and closed the gatt
            # connection.
            return True

        # Try to disconnect the actual device/peripheral
        try:
            if self.__callbacks.prepare_unless('onConnectionStateChange', 'STATE_DISCONNECTED'):
                self.__gatt.disconnect()
                await self.__callbacks.expect(connstate, 'STATE_DISCONNECTED')
            self.__gatt.close()
            self.__gatt = None
            self.__callbacks = None
        except Exception as e:
            logger.error("Attempt to disconnect device failed: {0}".format(e))

        is_disconnected = not await self.is_connected()

        if is_disconnected:
            self.__gatt = None

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
            bond_state = self.__device.getBondState()
            if bond_state == _java.BOND_BONDED:
                return True
            elif bond_state == _java.BOND_NONE:
                logger.debug(
                    "Pairing to BLE device @ {0}".format(self.address)
                )
                if not self.__device.createBond():
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
        state = self.__callbacks.states['onConnectionStateChange'][1]
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
        java_services = self.__gatt.getServices()
        for service_index in range(len(java_services)):
            java_service = java_services[service_index]
            java_characteristics = java_service.getCharacteristics()

            service = BleakGATTServiceP4Android(java_service)
            self.services.add_service(service)

            for characteristic_index in range(len(java_characteristics)):
                java_characteristic = java_characteristics[characteristic_index]
                java_descriptors = java_characteristic.getDescriptors()

                characteristic = BleakGATTCharacteristicP4Android(
                    java_characteristic,
                    service.uuid)

                self.services.add_characteristic(characteristic)
                for descriptor_index in range(len(java_descriptors)):
                    java_descriptor = java_descriptors[descriptor_index]

                    descriptor = BleakGATTDescriptorP4Android(
                        java_descriptor,
                        characteristic.uuid,
                        characteristic.handle,
                        descriptor_index)
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
        if not self.__gatt.readCharacteristic(characteristic.obj):
            raise BleakError(
                "Failed to initiate read from characteristic {0}".format(
                    characteristic.uuid
                )
            )
        value, = await self.callback.expect(valuestate)
        value = bytearray(value)
        logger.debug(
            "Read Characteristic {0} | {1}: {2}".format(
                characteristic.uuid, self.address, value
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
        if not self.__gatt.readDescriptor(descriptor.obj):
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
        if not self.__gatt.writeCharacteristic(characteristic.obj):
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
        if not self.__gatt.writeDescriptor(descriptor.obj):
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

        if not self.__gatt.setCharacteristicNotification(characteristic.obj, True):
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

        if not self.__gatt.setCharacteristicNotification(characteristic.obj, False):
            raise BleakError(
                "Failed to disable notification for characteristic {0}".format(
                    characteristic.uuid
                )
            )
        del self._subscriptions[characteristic.handle]

    def _dispatch_notification(self, handle, data):
        self._subscriptions[handle](handle, data)

class _PythonBluetoothGattCallback(PythonJavaClass):
    __javainterfaces__ = ['com.github.hbldh.bleak.PythonBluetoothGattCallback$Interface']
    __javacontext__ = 'app'

    def __init__(self, client, loop):
        self._client = client
        self._loop = loop
        self.java = _java.PythonBluetoothGattCallback(self)
        self.futures = {}
        self.states = {}

    def _if_expected(self, result, expected):
        if result[:len(expected)] == expected[:]:
            print('match',expected)
            return result[len(expected):]
        else:
            print('match failure',result[:len(expected)],expected[:])
            return None

    def prepare(self, source):
        logger.debug("Waiting for java {0}".format(source))
        future = self._loop.create_future()
        self.futures[source] = future
        return future

    def prepare_unless(self, source, *expected):
        if source not in self.futures:
            return self.prepare(source)
        future = self.futures[source]
        if future.done():
            match = self._if_expected(future.result(), expected)
            if match is not None:
                logger.debug("Not waiting for java {0} because found {1}".format(source, *expected))
                return match
            else:
                return self.prepare(source)
        logger.debug("Reusing existing wait for java {0}".format(source))
        return future

    async def expect(self, future, *expected):
        #outdated = future.done()
        #if outdated:
        #    result = future.result():
        #else:
        #    result = await future
        #match = self._if_expected(result, expected)
        #if outdated and not match:
        #    del self.futures[source]
        #    result = await self.get_unthreadsafe(source)
        #    match = self._if_expected(result, expected)
        result = await future
        match = self._if_expected(result, expected)
        if match is not None:
            return match
        else:
            raise BleakError('Expected', expected, 'got', result)

    def _result_state_unthreadsafe(self, status, source, data):
        status_str = _java.GATT_STATUS_NAMES.get(status, status)
            # some ideas found on the internet for managing GATT_ERROR 133 0x85
            # change setReportDelay from 0 to 400 (or 500) (disputed)
            # retry after delay up to 2 more times
            # connect while hardware already powered up from scanning, before scanning stops
            # do not do a cancelDiscovery at end of scanning; let finish on own
            # keep bluetoothgatt calls in main thread
            # pass BluetoothDevice.TRANSPORT_LE to connection call
            # other solutions mentioned on https://github.com/android/connectivity-samples/issues/18
        logger.debug("Java state transfer {0} {1}: {2}".format(source, status_str, data))
        print('state:', source, status_str, *data)
        self.states[source] = (status_str, *data)
        future = self.futures.get(source, None)
        if future is None:
            if source == 'onConnectionStateChange' and data[0] == 'STATE_DISCONNECTED':
                self._client._disconnected_callback(self._client)
            return
        if status == _java.GATT_SUCCESS:
            future.set_result(data)
        else:
            future.set_exception(BleakError(source, status_str, *data))
        
    def _result_state_threadsafe(self, status, source, *data):
        self._loop.call_soon_threadsafe(self._result_state_unthreadsafe, status, source, data)

    @java_method('(II)V')
    def onConnectionStateChange(self, status, new_state):
        state = _java.CONNECTION_STATE_NAMES.get(new_state, new_state)
        self._result_state_threadsafe(status, 'onConnectionStateChange', state)

    @java_method('(I)V')
    def onServicesDiscovered(self, status):
        self._result_state_threadsafe(status, 'onServicesDiscovered')

    @java_method('(I[B)V')
    def onCharacteristicChanged(self, handle, value):
        self._loop.call_soon_threadsafe(self._client._dispatch_notification, handle, value)

    @java_method('(II[B)V')
    def onCharacteristicRead(self, handle, status, value):
        self._result_state_threadsafe(status, ('onCharacteristicRead', handle), value)

    @java_method('(II)V')
    def onCharacteristicWrite(self, handle, status):
        self._result_state_threadsafe(status, ('onCharacteristicWrite', handle))
    
    @java_method('(Ljava/lang/String;I[B)V')
    def onDescriptorRead(self, uuid, status, value):
        self._result_state_threadsafe(status, ('onDescriptorRead', uuid), value)

    @java_method('(Ljava/lang/String;I)V')
    def onDescriptorWrite(self, uuid, status):
        self._result_state_threadsafe(status, ('onDescriptorWrite', uuid))
