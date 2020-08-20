# -*- coding: utf-8 -*-
"""
BLE Client for Windows 10 systems, implemented with WinRT.

Created on 2020-08-19 by hbldh <henrik.blidh@nedomkull.com>
"""

import logging
import asyncio
import uuid
from functools import wraps
from typing import Callable, Any, Union

from bleak.exc import BleakError, BleakDotNetTaskError, CONTROLLER_ERROR_CODES
from bleak.backends.client import BaseBleakClient
from bleak.backends.dotnet.winrt.discovery import discover

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.service import BleakGATTServiceCollection
from bleak.backends.dotnet.winrt.service import BleakGATTServiceWinRT
from bleak.backends.dotnet.winrt.characteristic import BleakGATTCharacteristicWinRT
from bleak.backends.dotnet.winrt.descriptor import BleakGATTDescriptorWinRT


# Import of RT components needed.

from winrt.windows.storage.streams import DataReader, DataWriter
from winrt.windows.devices.bluetooth import (
    BluetoothLEDevice,
    BluetoothConnectionStatus,
    BluetoothCacheMode,
    BluetoothAddressType,
)
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattCommunicationStatus,
    GattWriteOption,
    GattCharacteristicProperties,
    GattClientCharacteristicConfigurationDescriptorValue,
)


logger = logging.getLogger(__name__)

_communication_statues = {
    getattr(GattCommunicationStatus, k): v
    for k,v in zip(
        ["SUCCESS", "UNREACHABLE", "PROTOCOL_ERROR", "ACCESS_DENIED"],
        ["Success", "Unreachable", "ProtocolError", "AccessDenied"],
    )
}


class BleakClientWinRT(BaseBleakClient):
    """The native Windows Bleak Client.

    Implemented using `winrt <https://pythonnet.github.io/>`_, a package that enables Python developers to access
    Windows Runtime APIs directly from Python. Therefore, much of the code below has a distinct C# feel.

    Args:
        address (str): The Bluetooth address of the BLE peripheral to connect to.

    Keyword Args:
            timeout (float): Timeout for required ``discover`` call. Defaults to 2.0.

    """

    def __init__(self, address: str, **kwargs):
        super(BleakClientWinRT, self).__init__(address, **kwargs)

        # Backend specific. WinRT objects.
        self._device_info = None
        self._requester = None
        self._bridge = None

        self._address_type = (
            kwargs["address_type"]
            if "address_type" in kwargs
            and kwargs["address_type"] in ("public", "random")
            else None
        )
        self._disconnected_callback = None

        self._requester_connection_status_changed_token = None

    def __str__(self):
        return "BleakClientDotNet ({0})".format(self.address)

    # Connectivity methods

    async def connect(self, **kwargs) -> bool:
        """Connect to the specified GATT server.

        Keyword Args:
            timeout (float): Timeout for required ``discover`` call. Defaults to 2.0.

        Returns:
            Boolean representing connection status.

        """

        # Try to find the desired device.
        timeout = kwargs.get("timeout", self._timeout)
        devices = await discover(timeout=timeout)
        sought_device = list(
            filter(lambda x: x.address.upper() == self.address.upper(), devices)
        )

        if len(sought_device):
            self._device_info = sought_device[0].details.bluetooth_address
        else:
            raise BleakError(
                "Device with address {0} was " "not found.".format(self.address)
            )

        logger.debug("Connecting to BLE device @ {0}".format(self.address))

        args = [self._device_info,]
        if self._address_type is not None:
            args.append(
                BluetoothAddressType.PUBLIC
                if self._address_type == "public"
                else BluetoothAddressType.RANDOM
            )
        self._requester = await BluetoothLEDevice.from_bluetooth_address_async(*args)

        def _ConnectionStatusChanged_Handler(sender, args):
            logger.debug("_ConnectionStatusChanged_Handler: " + args.to_string())
            if self._disconnected_callback:
                self._disconnected_callback(sender, *args)

        self._requester_connection_status_changed_token = self._requester.add_connection_status_changed(_ConnectionStatusChanged_Handler)

        # Obtain services, which also leads to connection being established.
        services = await self.get_services()
        connected = False
        if self._services_resolved:
            # If services has been resolved, then we assume that we are connected. This is due to
            # some issues with getting `is_connected` to give correct response here.
            connected = True
        else:
            for _ in range(5):
                await asyncio.sleep(0.2)
                connected = await self.is_connected()
                if connected:
                    break

        if connected:
            logger.debug("Connection successful.")
        else:
            raise BleakError(
                "Connection to {0} was not successful!".format(self.address)
            )

        return connected

    async def disconnect(self) -> bool:
        """Disconnect from the specified GATT server.

        Returns:
            Boolean representing if device is disconnected.

        """
        logger.debug("Disconnecting from BLE device...")
        # Remove notifications. Remove them first in the BleakBridge and then clear
        # remaining notifications in Python as well.
        for handle, (fcn, fcn_token) in list(self._notification_callbacks.items()):
            char = self.services.get_characteristic(handle)
            char.obj.remove_value_changed(fcn_token)
            del fcn
        self._notification_callbacks.clear()

        # Dispose all service components that we have requested and created.
        for service in self.services:
            service.obj.close()
        self.services = BleakGATTServiceCollection()
        self._services_resolved = False

        # Dispose of the BluetoothLEDevice and see that the connection status is now Disconnected.
        self._requester.remove_connection_status_changed(self._requester_connection_status_changed_token)
        self._requester_connection_status_changed_token = None
        self._requester.close()
        while self._requester.connection_status != BluetoothConnectionStatus.DISCONNECTED:
            await asyncio.sleep(0.1)

        is_disconnected = self._requester.connection_status == BluetoothConnectionStatus.DISCONNECTED
        self._requester = None

        # Set device info to None as well.
        self._device_info = None

        return is_disconnected

    async def is_connected(self) -> bool:
        """Check connection status between this client and the server.

        Returns:
            Boolean representing connection status.

        """
        if self._requester:
            return (
                self._requester.connection_status == BluetoothConnectionStatus.CONNECTED
            )
        else:
            return False

    def set_disconnected_callback(
        self, callback: Callable[[BaseBleakClient], None], **kwargs
    ) -> None:
        """Set the disconnected callback.

        Args:
            callback: callback to be called on disconnection.

        """
        self._disconnected_callback = callback

    # GATT services methods

    async def get_services(self) -> BleakGATTServiceCollection:
        """Get all services registered for this GATT server.

        Returns:
           A :py:class:`bleak.backends.service.BleakGATTServiceCollection` with this device's services tree.

        """
        # Return the Service Collection.
        if self._services_resolved:
            return self.services
        else:
            logger.debug("Get Services...")
            services_result = await self._requester.get_gatt_services_async(BluetoothCacheMode.UNCACHED)

            if services_result.status != GattCommunicationStatus.SUCCESS:
                if services_result.status == GattCommunicationStatus.PROTOCOL_ERROR:
                    raise BleakDotNetTaskError(
                        "Could not get GATT services: {0} (Error: 0x{1:02X}: {2})".format(
                            _communication_statues.get(services_result.status, ""),
                            services_result.protocol_error,
                            CONTROLLER_ERROR_CODES.get(services_result.protocol_error, "Unknown")
                        )
                    )
                else:
                    raise BleakDotNetTaskError(
                        "Could not get GATT services: {0}".format(
                            _communication_statues.get(services_result.status, "")
                        )
                    )

            for service in services_result.services:
                characteristics_result = await service.get_characteristics_async(BluetoothCacheMode.UNCACHED)
                self.services.add_service(BleakGATTServiceWinRT(service))
                if characteristics_result.status != GattCommunicationStatus.SUCCESS:
                    if (
                        characteristics_result.status
                        == GattCommunicationStatus.PROTOCOL_ERROR
                    ):
                        raise BleakDotNetTaskError(
                            "Could not get GATT characteristics for {0}: {1} (Error: 0x{2:02X}: {3})".format(
                                service,
                                _communication_statues.get(
                                    characteristics_result.status, ""
                                ),
                                characteristics_result.protocol_error,
                                CONTROLLER_ERROR_CODES.get(characteristics_result.protocol_error, "Unknown")
                            )
                        )
                    else:
                        raise BleakDotNetTaskError(
                            "Could not get GATT characteristics for {0}: {1}".format(
                                service,
                                _communication_statues.get(
                                    characteristics_result.status, ""
                                ),
                            )
                        )
                for characteristic in characteristics_result.characteristics:
                    descriptors_result = await characteristic.get_descriptors_async(BluetoothCacheMode.UNCACHED)
                    self.services.add_characteristic(
                        BleakGATTCharacteristicWinRT(characteristic)
                    )
                    if descriptors_result.status != GattCommunicationStatus.SUCCESS:
                        if (
                            characteristics_result.status
                            == GattCommunicationStatus.PROTOCOL_ERROR
                        ):
                            raise BleakDotNetTaskError(
                                "Could not get GATT descriptors for {0}: {1} (Error: 0x{2:02X}: {3})".format(
                                    service,
                                    _communication_statues.get(
                                        descriptors_result.status, ""
                                    ),
                                    descriptors_result.protocol_error,
                                    CONTROLLER_ERROR_CODES.get(
                                        descriptors_result.protocol_error,
                                        "Unknown")
                                )
                            )
                        else:
                            raise BleakDotNetTaskError(
                                "Could not get GATT descriptors for {0}: {1}".format(
                                    characteristic,
                                    _communication_statues.get(
                                        descriptors_result.status, ""
                                    ),
                                )
                            )
                    for descriptor in list(descriptors_result.descriptors):
                        self.services.add_descriptor(
                            BleakGATTDescriptorWinRT(
                                descriptor,
                                "",
                                characteristic.attribute_handle,
                            )
                        )

            logger.info("Services resolved for %s", str(self))
            self._services_resolved = True
            return self.services

    # I/O methods

    async def read_gatt_char(
        self,
        char_specifier: Union[BleakGATTCharacteristic, int, str, uuid.UUID],
        use_cached=False,
        **kwargs
    ) -> bytearray:
        """Perform read operation on the specified GATT characteristic.

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to read from,
                specified by either integer handle, UUID or directly by the
                BleakGATTCharacteristic object representing it.
            use_cached (bool): `False` forces Windows to read the value from the
                device again and not use its own cached value. Defaults to `False`.

        Returns:
            (bytearray) The read data.

        """
        if not isinstance(char_specifier, BleakGATTCharacteristic):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier
        if not characteristic:
            raise BleakError("Characteristic {0} was not found!".format(char_specifier))

        read_result = await characteristic.obj.read_value_async(
                    BluetoothCacheMode.CACHED
                    if use_cached
                    else BluetoothCacheMode.UNCACHED
                )

        if read_result.status == GattCommunicationStatus.SUCCESS:
            reader = DataReader.from_buffer(read_result.value)
            # TODO: Figure out how to use read_bytes instead...
            value = bytearray([reader.read_byte() for _ in range(reader.unconsumed_buffer_length)])
            logger.debug(
                "Read Characteristic {0} : {1}".format(characteristic.uuid, value)
            )
        else:
            if read_result.status == GattCommunicationStatus.PROTOCOL_ERROR:
                raise BleakDotNetTaskError(
                    "Could not get GATT characteristics for {0}: {1} (Error: 0x{2:02X}: {3})".format(
                        characteristic.uuid,
                        _communication_statues.get(read_result.status, ""),
                        read_result.protocol_error,
                        CONTROLLER_ERROR_CODES.get(
                            read_result.protocol_error,
                            "Unknown")
                    )
                )
            else:
                raise BleakError(
                    "Could not read characteristic value for {0}: {1}".format(
                        characteristic.uuid,
                        _communication_statues.get(read_result.status, ""),
                    )
                )
        return value

    async def read_gatt_descriptor(
        self, handle: int, use_cached=False, **kwargs
    ) -> bytearray:
        """Perform read operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
            use_cached (bool): `False` forces Windows to read the value from the
                device again and not use its own cached value. Defaults to `False`.

        Returns:
            (bytearray) The read data.

        """
        descriptor = self.services.get_descriptor(handle)
        if not descriptor:
            raise BleakError("Descriptor with handle {0} was not found!".format(handle))

        read_result = await descriptor.obj.read_value_async(
                    BluetoothCacheMode.CACHED
                    if use_cached
                    else BluetoothCacheMode.UNCACHED
                )

        if read_result.status == GattCommunicationStatus.SUCCESS:
            reader = DataReader.from_buffer(read_result.value)
            # TODO: Figure out how to use read_bytes instead...
            value = bytearray([reader.read_byte() for _ in range(reader.unconsumed_buffer_length)])
            logger.debug("Read Descriptor {0} : {1}".format(handle, value))
        else:
            if read_result.status == GattCommunicationStatus.PROTOCOL_ERROR:
                raise BleakDotNetTaskError(
                    "Could not get GATT characteristics for {0}: {1} (Error: 0x{2:02X}: {3})".format(
                        descriptor.uuid,
                        _communication_statues.get(read_result.status, ""),
                        read_result.protocol_error,
                        CONTROLLER_ERROR_CODES.get(
                            read_result.protocol_error,
                            "Unknown")
                    )
                )
            else:
                raise BleakError(
                    "Could not read Descriptor value for {0}: {1}".format(
                        descriptor.uuid,
                        _communication_statues.get(read_result.status, ""),
                    )
                )

        return value

    async def write_gatt_char(
        self,
        char_specifier: Union[BleakGATTCharacteristic, int, str, uuid.UUID],
        data: bytearray,
        response: bool = False,
    ) -> None:
        """Perform a write operation of the specified GATT characteristic.

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to write
                to, specified by either integer handle, UUID or directly by the
                BleakGATTCharacteristic object representing it.
            data (bytes or bytearray): The data to send.
            response (bool): If write-with-response operation should be done. Defaults to `False`.

        """
        if not isinstance(char_specifier, BleakGATTCharacteristic):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier
        if not characteristic:
            raise BleakError("Characteristic {} was not found!".format(char_specifier))

        writer = DataWriter()
        writer.write_bytes(list(data))
        response = (
            GattWriteOption.WRITE_WITH_RESPONSE
            if response
            else GattWriteOption.WRITE_WITHOUT_RESPONSE
        )
        write_result = await characteristic.obj.write_value_with_result_async(
                    writer.detach_buffer(), response)

        if write_result.status == GattCommunicationStatus.SUCCESS:
            logger.debug(
                "Write Characteristic {0} : {1}".format(characteristic.uuid, data)
            )
        else:
            if write_result.status == GattCommunicationStatus.PROTOCOL_ERROR:
                raise BleakError(
                    "Could not write value {0} to characteristic {1}: {2} (Error: 0x{3:02X}: {4})".format(
                        data,
                        characteristic.uuid,
                        _communication_statues.get(write_result.status, ""),
                        write_result.protocol_error,
                        CONTROLLER_ERROR_CODES.get(
                            write_result.protocol_error,
                            "Unknown")
                    )
                )
            else:
                raise BleakError(
                    "Could not write value {0} to characteristic {1}: {2}".format(
                        data,
                        characteristic.uuid,
                        _communication_statues.get(write_result.status, ""),
                    )
                )

    async def write_gatt_descriptor(self, handle: int, data: bytearray) -> None:
        """Perform a write operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
            data (bytes or bytearray): The data to send.

        """
        descriptor = self.services.get_descriptor(handle)
        if not descriptor:
            raise BleakError("Descriptor with handle {0} was not found!".format(handle))

        writer = DataWriter()
        writer.write_bytes(list(data))
        write_result = await descriptor.obj.write_value_async(writer.detach_buffer())

        if write_result.status == GattCommunicationStatus.SUCCESS:
            logger.debug("Write Descriptor {0} : {1}".format(handle, data))
        else:
            if write_result.status == GattCommunicationStatus.PROTOCOL_ERROR:
                raise BleakError(
                    "Could not write value {0} to characteristic {1}: {2} (Error: 0x{3:02X}: {4})".format(
                        data,
                        descriptor.uuid,
                        _communication_statues.get(write_result.status, ""),
                        write_result.protocol_error,
                        CONTROLLER_ERROR_CODES.get(
                            write_result.protocol_error,
                            "Unknown")
                    )
                )
            else:
                raise BleakError(
                    "Could not write value {0} to descriptor {1}: {2}".format(
                        data,
                        descriptor.uuid,
                        _communication_statues.get(write_result.status, ""),
                    )
                )

    async def start_notify(
        self,
        char_specifier: Union[BleakGATTCharacteristic, int, str, uuid.UUID],
        callback: Callable[[str, Any], Any],
        **kwargs
    ) -> None:
        """Activate notifications/indications on a characteristic.

        Callbacks must accept two inputs. The first will be a uuid string
        object and the second will be a bytearray.

        .. code-block:: python

            def callback(sender, data):
                print(f"{sender}: {data}")
            client.start_notify(char_uuid, callback)

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to activate
                notifications/indications on a characteristic, specified by either integer handle,
                UUID or directly by the BleakGATTCharacteristic object representing it.
            callback (function): The function to be called on notification.

        """
        if not isinstance(char_specifier, BleakGATTCharacteristic):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier
        if not characteristic:
            raise BleakError("Characteristic {0} not found!".format(char_specifier))

        if self._notification_callbacks.get(characteristic.handle):
            await self.stop_notify(characteristic)

        status = await self._start_notify(characteristic, callback)

        if status != GattCommunicationStatus.SUCCESS:
            # TODO: Find out how to get the ProtocolError code that describes a potential GattCommunicationStatus.PROTOCOL_ERROR result.
            raise BleakError(
                "Could not start notify on {0}: {1}".format(
                    characteristic.uuid, _communication_statues.get(status, "")
                )
            )

    async def _start_notify(
        self,
        characteristic: BleakGATTCharacteristic,
        callback: Callable[[str, Any], Any],
    ):
        """Internal method performing call to BleakUWPBridge method.

        Args:
            characteristic: The BleakGATTCharacteristic to start notification on.
            callback: The function to be called on notification.

        Returns:
            (int) The GattCommunicationStatus of the operation.

        """
        characteristic_obj = characteristic.obj
        if (
            characteristic_obj.characteristic_properties
            & GattCharacteristicProperties.INDICATE
        ):
            cccd = GattClientCharacteristicConfigurationDescriptorValue.INDICATE
        elif (
            characteristic_obj.characteristic_properties
            & GattCharacteristicProperties.NOTIFY
        ):
            cccd = GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
        else:
            cccd = GattClientCharacteristicConfigurationDescriptorValue.NONE

        try:
            # TODO: Enable adding multiple handlers!
            fcn = _notification_wrapper(callback, asyncio.get_event_loop())
            fcn_token = characteristic_obj.add_value_changed(fcn)
            self._notification_callbacks[characteristic.handle] = fcn, fcn_token

        except Exception as e:
            logger.debug("Start Notify problem: {0}".format(e))
            if characteristic.handle in self._notification_callbacks:
                callback, token = self._notification_callbacks.pop(characteristic.handle)
                characteristic_obj.remove_value_changed(token)
                del callback

            return GattCommunicationStatus.ACCESS_DENIED

        status = await characteristic_obj.write_client_characteristic_configuration_descriptor_async(
                    cccd
                )

        if status != GattCommunicationStatus.SUCCESS:
            # This usually happens when a device reports that it support indicate,
            # but it actually doesn't.
            if characteristic.handle in self._notification_callbacks:
                callback, token = self._notification_callbacks.pop(characteristic.handle)
                characteristic_obj.remove_value_changed(token)
                del callback

            return GattCommunicationStatus.ACCESS_DENIED
        return status

    async def stop_notify(
        self, char_specifier: Union[BleakGATTCharacteristic, int, str, uuid.UUID]
    ) -> None:
        """Deactivate notification/indication on a specified characteristic.

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to deactivate
                notification/indication on, specified by either integer handle, UUID or
                directly by the BleakGATTCharacteristic object representing it.

        """
        if not isinstance(char_specifier, BleakGATTCharacteristic):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier
        if not characteristic:
            raise BleakError("Characteristic {} not found!".format(char_specifier))

        status = await characteristic.obj.write_client_characteristic_configuration_descriptor_async(
                        GattClientCharacteristicConfigurationDescriptorValue.NONE
                )

        if status != GattCommunicationStatus.SUCCESS:
            raise BleakError(
                "Could not stop notify on {0}: {1}".format(
                    characteristic.uuid, _communication_statues.get(status, "")
                )
            )
        else:
            callback, token = self._notification_callbacks.pop(characteristic.handle)
            characteristic.obj.remove_value_changed(token)
            del callback


def _notification_wrapper(func: Callable, loop: asyncio.AbstractEventLoop):
    @wraps(func)
    def dotnet_notification_parser(sender: Any, args: Any):
        # Return only the UUID string representation as sender.
        # Also do a conversion from System.Bytes[] to bytearray.
        reader = DataReader.from_buffer(args.characteristic_value)
        # TODO: Figure out how to use read_bytes instead...
        value = bytearray([reader.read_byte() for _ in range(reader.unconsumed_buffer_length)])

        return loop.call_soon_threadsafe(
            func, sender.attribute_handle, value
        )

    return dotnet_notification_parser
