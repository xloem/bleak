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
from jnius import autoclass, cast, java_method

from . import utils

logger = logging.getLogger(__name__)

class _java:
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
    BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
    BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')
    BluetoothGattDescriptor = autoclass('android.bluetooth.BluetoothGattDescriptor')
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
    DISABLE_NOTIFICATION_VALUE = BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE
    ENABLE_NOTIFICATION_VALUE = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
    ENABLE_INDICATION_VALUE = BluetoothGattDescriptor.ENABLE_INDICATION_VALUE

    GATT_STATUS_NAMES = {
        # https://developer.android.com/reference/android/bluetooth/BluetoothGatt
        # https://android.googlesource.com/platform/external/bluetooth/bluedroid/+/5738f83aeb59361a0a2eda2460113f6dc9194271/stack/include/gatt_api.h
        # https://android.googlesource.com/platform/system/bt/+/master/stack/include/gatt_api.h
        # https://www.bluetooth.com/specifications/bluetooth-core-specification/
        # if error codes are missing you could check the bluetooth
        # specification (last link above) as not all were copied over, since
        # android repurposed so many
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
        0x0014: 'BLU_REM_TERM_CONN_LOW_RES', # names made up from bluetooth spec
        0x0015: 'BLU_REM_TERM_CONN_POW_OFF',
        0x0016: 'BLU_LOC_TERM_CONN',
        0x0017: 'BLU_REPEATED_ATTEMPTS',
        0x0018: 'BLU_PAIRING_NOT_ALLOWED',
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
        disconnected_callback (callable): Callback that will be scheduled in the
            event loop when the client is disconnected. The callable must take one
            argument, which will be this client object.
        adapter (str): Bluetooth adapter to use for discovery. [unused]
    """

    def __init__(self, address_or_ble_device: Union[BLEDevice, str], **kwargs):
        super(BleakClientP4Android, self).__init__(address_or_ble_device, **kwargs)
        # kwarg "device" is for backwards compatibility
        self.__adapter = kwargs.get("adapter", kwargs.get("device", None))
        self.__gatt = None

    def __del__(self):
        if self.__gatt is not None:
            self.__gatt.close()
            self.__gatt = None

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

        self.__gatt, = await self.__callbacks.perform_and_wait(
            dispatchApi = self.__device.connectGatt,
            dispatchParams = (_java.context, False, self.__callbacks.java),
            resultApi = 'onConnectionStateChange',
            resultExpected = ('STATE_CONNECTED',),
            return_indicates_status = False
        )

        logger.debug("Connection successful.")

        self._subscriptions = {}

        await self.__callbacks.perform_and_wait(
            dispatchApi = self.__gatt.discoverServices,
            dispatchParams = (),
            resultApi = 'onServicesDiscovered'
        )

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
            await self.__callbacks.perform_and_wait(
                dispatchApi = self.__gatt.disconnect,
                dispatchParams = (),
                resultApi = 'onConnectionStateChange',
                resultExpected = ('STATE_DISCONNECTED',),
                unless_already = True,
                return_indicates_status = False
            )
            self.__gatt.close()
        except Exception as e:
            logger.error("Attempt to disconnect device failed: {0}".format(e))

        is_disconnected = not await self.is_connected()

        if is_disconnected:
            self.__gatt = None
            self.__callbacks = None

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

        receiver =  BroadcastReceiver(handleBondStateChanged, actions=[ACTION_BOND_STATE_CHANGED])
        receiver.start()
        try:
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
        finally:
            await receiver.stop()

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
        return (
            self.__callbacks is not None and
            self.__callbacks.states['onConnectionStateChange'][1] == 'STATE_DISCONNECTED'
        )

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

        value, = await self.__callbacks.perform_and_wait(
            dispatchApi = self.__gatt.readCharacteristic,
            dispatchParams = (characteristic.obj,),
            resultApi = ('onCharacteristicRead', characteristic.handle)
        )
        value = bytearray(value)
        logger.debug(
            "Read Characteristic {0} | {1}: {2}".format(
                characteristic.uuid, characteristic.handle, value
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

        value, = await self.__callbacks.perform_and_wait(
            dispatchApi = self.__gatt.readDescriptor,
            dispatchParams = (descriptor.obj,),
            resultApi = ('onDescriptorRead', descriptor.uuid)
        )
        value = bytearray(value)

        logger.debug(
            "Read Descriptor {0} | {1}: {2}".format(
                descriptor.uuid, descriptor.handle, value
            )
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

        await self.__callbacks.perform_and_wait(
            dispatchApi = self.__gatt.writeCharacteristic,
            dispatchParams = (characteristic.obj,),
            resultApi = ('onCharacteristicWrite', characteristic.handle)
        )

        logger.debug(
            "Write Characteristic {0} | {1}: {2}".format(
                characteristic.uuid, characteristic.handle, data
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

        await self.__callbacks.perform_and_wait(
            dispatchApi = self.__gatt.writeDescriptor,
            dispatchParams = (descriptor.obj,),
            resultApi = ('onDescriptorWrite', descriptor.uuid)
        )

        logger.debug(
            "Write Descriptor {0} | {1}: {2}".format(descriptor.uuid, descriptor.handle, data)
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

        self._subscriptions[characteristic.handle] = callback

        if not self.__gatt.setCharacteristicNotification(characteristic.obj, True):
            raise BleakError(
                "Failed to enable notification for characteristic {0}".format(
                    characteristic.uuid
                )
            )
        
        await self.write_gatt_descriptor(characteristic.notification_descriptor, _java.ENABLE_NOTIFICATION_VALUE)

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
        
        await self.write_gatt_descriptor(characteristic.notification_descriptor, _java.DISABLE_NOTIFICATION_VALUE)

        if not self.__gatt.setCharacteristicNotification(characteristic.obj, False):
            raise BleakError(
                "Failed to disable notification for characteristic {0}".format(
                    characteristic.uuid
                )
            )
        del self._subscriptions[characteristic.handle]

class _PythonBluetoothGattCallback(utils.AsyncJavaCallbacks):
    __javainterfaces__ = ['com.github.hbldh.bleak.PythonBluetoothGattCallback$Interface']

    def __init__(self, client, loop):
        super().__init__(loop)
        self._client = client
        self.java = _java.PythonBluetoothGattCallback(self)
        #self.futures = {}
        #self.states = {}

    def __del__(self):
        # sometimes there's a segfault; it may have been resolved.
        # if not, this message was to help figure out what had been deallocated when it happened
        print('DESTROYING CLIENT CALLBACKS!  WILL NO MORE BE CALLED?')

    #def _if_expected(self, result, expected):
    #    if result[:len(expected)] == expected[:]:
    #        return result[len(expected):]
    #    else:
    #        return None

    #async def perform_and_wait(self, dispatchApi, dispatchParams, resultApi, resultExpected = (), unless_already = False, return_indicates_status = True):
    #    result2 = None
    #    if unless_already and resultApi in self.futures:
    #        state = self.futures[resultApi]
    #        if state.done():
    #            result2 = self._if_expected(state.result(), resultExpected)
    #            result1 = bool(result2)

    #    if result2 is not None:
    #        logger.debug("Not waiting for android api {0} because found {1}".format(resultApi, resultExpected))
    #    else:
    #        logger.debug("Waiting for android api {0}".format(resultApi))

    #        state = self._loop.create_future()
    #        self.futures[resultApi] = state
    #        result1 = dispatchApi(*dispatchParams)
    #        if return_indicates_status and not result1:
    #            del self.futures[resultApi]
    #            raise BleakError('{} failed, not waiting for {}'.format(dispatchApi.__name__, resultApi))
    #        result2 = await self.expect(state, *resultExpected)

    #        logger.debug("{0} succeeded {1}".format(resultApi, result2))

    #    if return_indicates_status:
    #        return result2
    #    else:
    #        return (result1, *result2)

    #async def expect(self, future, *expected):
    #    result = await future
    #    match = self._if_expected(result, expected)
    #    if match is not None:
    #        return match
    #    else:
    #        raise BleakError('Expected', expected, 'got', result)

    #def _result_state_unthreadsafe(self, status, source, data):
    #    status_str = _java.GATT_STATUS_NAMES.get(status, status)
    #        # some ideas found on the internet for managing GATT_ERROR 133 0x85
    #        # (disputed) change setReportDelay from 0 to 400 (or 500)
    #        # retry after delay up to 2 more times
    #        # connect while hardware already powered up from scanning, before scanning stops
    #        # do not do a cancelDiscovery at end of scanning; let finish on own
    #        # keep bluetoothgatt calls in main thread
    #        # pass BluetoothDevice.TRANSPORT_LE to connection call
    #        # other solutions mentioned on https://github.com/android/connectivity-samples/issues/18
    #    logger.debug("Java state transfer {0} {1}: {2}".format(source, status_str, data))
    #    self.states[source] = (status_str, *data)
    #    future = self.futures.get(source, None)
    #    if future is not None and not future.done():
    #        if status == _java.GATT_SUCCESS:
    #            future.set_result(data)
    #        else:
    #            future.set_exception(BleakError(source, status_str, *data))
    #    else:
    #        if source == 'onConnectionStateChange' and data[0] == 'STATE_DISCONNECTED':
    #            if self._client._disconnected_callback is not None:
    #                self._client._disconnected_callback(self._client)
    #        elif status != _java.GATT_SUCCESS:
    #            # an error happened with nothing waiting for it
    #            exception = BleakError(source, status_str, *data)
    #            namedfutures = [namedfuture for namedfuture in self.futures.items() if not future.done()]
    #            if len(namedfutures):
    #                # send it on existing requests
    #                for name, future in namedfutures:
    #                    warnings.warn('Redirecting error without home to {0}'.format(name))
    #                    future.set_exception(exception)
    #            else:
    #                # send it on the event thread
    #                raise exception
                    
    #def _result_state_threadsafe(self, status, source, *data):
    #    self._loop.call_soon_threadsafe(self._result_state_unthreadsafe, status, source, data)

    def result_state(self, status, resultApi, *data):
        # some ideas found on the internet for managing GATT_ERROR 133 0x85
        # (disputed) change setReportDelay from 0 to 400 (or 500)
        # retry after delay up to 2 more times
        # connect while hardware already powered up from scanning, before scanning stops
        # do not do a cancelDiscovery at end of scanning; let finish on own
        # keep bluetoothgatt calls in main thread
        # pass BluetoothDevice.TRANSPORT_LE to connection call
        # other solutions mentioned on https://github.com/android/connectivity-samples/issues/18
        if status == _java.GATT_SUCCESS:
            failure_str = None
        else:
            failure_str = _java.GATT_STATUS_NAMES.get(status, status)
        self._loop.call_soon_threadsafe(self._result_state_unthreadsafe, failure_str, resultApi, data)

    @java_method('(II)V')
    def onConnectionStateChange(self, status, new_state):
        state = _java.CONNECTION_STATE_NAMES.get(new_state, new_state)
        try:
            self.result_state(status, 'onConnectionStateChange', state)
        except BleakError:
            pass
        if state == 'STATE_DISCONNECTED' and self._client._disconnected_callback is not None:
            self._client._disconnected_callback(self._client)

    @java_method('(I)V')
    def onServicesDiscovered(self, status):
        self.result_state(status, 'onServicesDiscovered')

    @java_method('(I[B)V')
    def onCharacteristicChanged(self, handle, value):
        self._loop.call_soon_threadsafe(
            self._client._subscriptions[handle],
            handle,
            bytearray(value.tolist())
        )

    @java_method('(II[B)V')
    def onCharacteristicRead(self, handle, status, value):
        self.result_state(status, ('onCharacteristicRead', handle), bytes(value.tolist()))

    @java_method('(II)V')
    def onCharacteristicWrite(self, handle, status):
        self.result_state(status, ('onCharacteristicWrite', handle))
    
    @java_method('(Ljava/lang/String;I[B)V')
    def onDescriptorRead(self, uuid, status, value):
        self.result_state(status, ('onDescriptorRead', uuid), bytes(value.tolist()))

    @java_method('(Ljava/lang/String;I)V')
    def onDescriptorWrite(self, uuid, status):
        self.result_state(status, ('onDescriptorWrite', uuid))
