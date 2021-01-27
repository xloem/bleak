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
from bleak.exc import BleakError
from bleak.backends.client import BaseBleakClient
from bleak.backends.p4android.service import BleakGATTServiceP4Android
from bleak.backends.p4android.characteristic import BleakGATTCharacteristicP4Android
from bleak.backends.p4android.descriptor import BleakGATTDescriptorP4Android

from android.broadcast import BroadcastReceiver
from jnius import java_method

from . import defs
from . import utils

logger = logging.getLogger(__name__)


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

        self.__adapter = defs.BluetoothAdapter.getDefaultAdapter()
        if self.__adapter is None:
            raise BleakError("Bluetooth is not supported on this hardware platform")
        if self.__adapter.getState() != defs.STATE_ON:
            raise BleakError("Bluetooth is not turned on")

        self.__device = self.__adapter.getRemoteDevice(self.address)

        self.__callbacks = _PythonBluetoothGattCallback(self, loop)

        logger.debug("Connecting to BLE device @ {0}".format(self.address))

        (self.__gatt,) = await self.__callbacks.perform_and_wait(
            dispatchApi=self.__device.connectGatt,
            dispatchParams=(
                defs.context,
                False,
                self.__callbacks.java,
                defs.TRANSPORT_LE,
            ),
            resultApi="onConnectionStateChange",
            resultExpected=("STATE_CONNECTED",),
            return_indicates_status=False,
        )

        logger.debug("Connection successful.")

        self._subscriptions = {}

        await self.__callbacks.perform_and_wait(
            dispatchApi=self.__gatt.discoverServices,
            dispatchParams=(),
            resultApi="onServicesDiscovered",
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
                dispatchApi=self.__gatt.disconnect,
                dispatchParams=(),
                resultApi="onConnectionStateChange",
                resultExpected=("STATE_DISCONNECTED",),
                unless_already=True,
                return_indicates_status=False,
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
            bond_state = intent.getIntExtra(defs.EXTRA_BOND_STATE, -1)
            if bond_state == -1:
                loop.call_soon_threadsafe(
                    bondedFuture.set_exception,
                    BleakError("Unexpected bond state {}".format(bond_state)),
                )
            elif bond_state == defs.BOND_NONE:
                loop.call_soon_threadsafe(
                    bondedFuture.set_exception,
                    BleakError(
                        "Device with address {0} could not be paired with.".format(
                            self.address
                        )
                    ),
                )
            elif bond_state == defs.BOND_BONDED:
                loop.call_soon_threadsafe(bondedFuture.set_result, True)

        receiver = BroadcastReceiver(
            handleBondStateChanged, actions=[defs.ACTION_BOND_STATE_CHANGED]
        )
        receiver.start()
        try:
            # See if it is already paired.
            bond_state = self.__device.getBondState()
            if bond_state == defs.BOND_BONDED:
                return True
            elif bond_state == defs.BOND_NONE:
                logger.debug("Pairing to BLE device @ {0}".format(self.address))
                if not self.__device.createBond():
                    raise BleakError(
                        "Could not initiate bonding with device @ {0}".format(
                            self.address
                        )
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
            self.__callbacks is not None
            and self.__callbacks.states["onConnectionStateChange"][1]
            == "STATE_DISCONNECTED"
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
                    java_characteristic, service.uuid
                )

                self.services.add_characteristic(characteristic)
                for descriptor_index in range(len(java_descriptors)):
                    java_descriptor = java_descriptors[descriptor_index]

                    descriptor = BleakGATTDescriptorP4Android(
                        java_descriptor,
                        characteristic.uuid,
                        characteristic.handle,
                        descriptor_index,
                    )
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

        (value,) = await self.__callbacks.perform_and_wait(
            dispatchApi=self.__gatt.readCharacteristic,
            dispatchParams=(characteristic.obj,),
            resultApi=("onCharacteristicRead", characteristic.handle),
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
            descriptor = self.services.get_descriptor(desc_specifier)
        else:
            descriptor = desc_specifier

        if not descriptor:
            raise BleakError(
                "Descriptor with UUID {0} was not found!".format(desc_specifier)
            )

        (value,) = await self.__callbacks.perform_and_wait(
            dispatchApi=self.__gatt.readDescriptor,
            dispatchParams=(descriptor.obj,),
            resultApi=("onDescriptorRead", descriptor.uuid),
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
            characteristic.obj.setWriteType(defs.WRITE_TYPE_DEFAULT)
        else:
            characteristic.obj.setWriteType(defs.WRITE_TYPE_NO_RESPONSE)

        characteristic.obj.setValue(data)

        await self.__callbacks.perform_and_wait(
            dispatchApi=self.__gatt.writeCharacteristic,
            dispatchParams=(characteristic.obj,),
            resultApi=("onCharacteristicWrite", characteristic.handle),
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
            dispatchApi=self.__gatt.writeDescriptor,
            dispatchParams=(descriptor.obj,),
            resultApi=("onDescriptorWrite", descriptor.uuid),
        )

        logger.debug(
            "Write Descriptor {0} | {1}: {2}".format(
                descriptor.uuid, descriptor.handle, data
            )
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

        await self.write_gatt_descriptor(
            characteristic.notification_descriptor, defs.ENABLE_NOTIFICATION_VALUE
        )

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

        await self.write_gatt_descriptor(
            characteristic.notification_descriptor, defs.DISABLE_NOTIFICATION_VALUE
        )

        if not self.__gatt.setCharacteristicNotification(characteristic.obj, False):
            raise BleakError(
                "Failed to disable notification for characteristic {0}".format(
                    characteristic.uuid
                )
            )
        del self._subscriptions[characteristic.handle]


class _PythonBluetoothGattCallback(utils.AsyncJavaCallbacks):
    __javainterfaces__ = [
        "com.github.hbldh.bleak.PythonBluetoothGattCallback$Interface"
    ]

    def __init__(self, client, loop):
        super().__init__(loop)
        self._client = client
        self.java = defs.PythonBluetoothGattCallback(self)

    def result_state(self, status, resultApi, *data):
        if status == defs.GATT_SUCCESS:
            failure_str = None
        else:
            failure_str = defs.GATT_STATUS_NAMES.get(status, status)
        self._loop.call_soon_threadsafe(
            self._result_state_unthreadsafe, failure_str, resultApi, data
        )

    @java_method("(II)V")
    def onConnectionStateChange(self, status, new_state):
        state = defs.CONNECTION_STATE_NAMES.get(new_state, new_state)
        try:
            self.result_state(status, "onConnectionStateChange", state)
        except BleakError:
            pass
        if (
            state == "STATE_DISCONNECTED"
            and self._client._disconnected_callback is not None
        ):
            self._client._disconnected_callback(self._client)

    @java_method("(I)V")
    def onServicesDiscovered(self, status):
        self.result_state(status, "onServicesDiscovered")

    @java_method("(I[B)V")
    def onCharacteristicChanged(self, handle, value):
        self._loop.call_soon_threadsafe(
            self._client._subscriptions[handle], handle, bytearray(value.tolist())
        )

    @java_method("(II[B)V")
    def onCharacteristicRead(self, handle, status, value):
        self.result_state(
            status, ("onCharacteristicRead", handle), bytes(value.tolist())
        )

    @java_method("(II)V")
    def onCharacteristicWrite(self, handle, status):
        self.result_state(status, ("onCharacteristicWrite", handle))

    @java_method("(Ljava/lang/String;I[B)V")
    def onDescriptorRead(self, uuid, status, value):
        self.result_state(status, ("onDescriptorRead", uuid), bytes(value.tolist()))

    @java_method("(Ljava/lang/String;I)V")
    def onDescriptorWrite(self, uuid, status):
        self.result_state(status, ("onDescriptorWrite", uuid))
