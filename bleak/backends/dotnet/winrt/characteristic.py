# -*- coding: utf-8 -*-
from uuid import UUID
from typing import List, Union

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.dotnet.winrt.descriptor import BleakGATTDescriptorWinRT

from winrt.windows.devices.bluetooth.genericattributeprofile import GattCharacteristicProperties

from bleak.backends.dotnet.winrt.utils import service_uuid_re

_GattCharacteristicsPropertiesEnum = {
    GattCharacteristicProperties.NONE: ("None", "The characteristic doesn’t have any properties that apply"),
    GattCharacteristicProperties.BROADCAST: ("Broadcast".lower(), "The characteristic supports broadcasting"),
    GattCharacteristicProperties.READ: ("Read".lower(), "The characteristic is readable"),
    GattCharacteristicProperties.WRITE_WITHOUT_RESPONSE: (
        "Write-Without-Response".lower(),
        "The characteristic supports Write Without Response",
    ),
    GattCharacteristicProperties.WRITE: ("Write".lower(), "The characteristic is writable"),
    GattCharacteristicProperties.NOTIFY: ("Notify".lower(), "The characteristic is notifiable"),
    GattCharacteristicProperties.INDICATE: ("Indicate".lower(), "The characteristic is indicatable"),
    GattCharacteristicProperties.AUTHENTICATED_SIGNED_WRITES: (
        "Authenticated-Signed-Writes".lower(),
        "The characteristic supports signed writes",
    ),
    GattCharacteristicProperties.EXTENDED_PROPERTIES: (
        "Extended-Properties".lower(),
        "The ExtendedProperties Descriptor is present",
    ),
    GattCharacteristicProperties.RELIABLE_WRITES: ("Reliable-Writes".lower(), "The characteristic supports reliable writes"),
    GattCharacteristicProperties.WRITABLE_AUXILIARIES: (
        "Writable-Auxiliaries".lower(),
        "The characteristic has writable auxiliaries",
    ),
}


class BleakGATTCharacteristicWinRT(BleakGATTCharacteristic):
    """GATT Characteristic implementation for the .NET backend, implemented with WinRT"""

    def __init__(self, obj: GattCharacteristicProperties):
        super().__init__(obj)
        self.__descriptors = [
            # BleakGATTDescriptorDotNet(d, self.uuid) for d in obj.GetAllDescriptors()
        ]
        self.__props = [
            _GattCharacteristicsPropertiesEnum[v][0]
            for v in [2 ** n for n in range(10)]
            if (self.obj.characteristic_properties & v)
        ]

        self.__service_uuid = service_uuid_re.search(self.obj.service.device_id).groups()[0]

    def __str__(self):
        return "[{0}] {1}: {2}".format(self.handle, self.uuid, self.description)

    @property
    def service_uuid(self) -> str:
        """The uuid of the Service containing this characteristic"""
        return self.__service_uuid

    @property
    def handle(self) -> int:
        """The handle of this characteristic"""
        return int(self.obj.attribute_handle)

    @property
    def uuid(self) -> str:
        """The uuid of this characteristic"""
        try:
            return self.obj.uuid.to_string()
        except:
            return ""

    @property
    def description(self) -> str:
        """Description for this characteristic"""
        return self.obj.user_description

    @property
    def properties(self) -> List:
        """Properties of this characteristic"""
        return self.__props

    @property
    def descriptors(self) -> List[BleakGATTDescriptorWinRT]:
        """List of descriptors for this service"""
        return self.__descriptors

    def get_descriptor(
        self, specifier: Union[int, str, UUID]
    ) -> Union[BleakGATTDescriptorWinRT, None]:
        """Get a descriptor by handle (int) or UUID (str or uuid.UUID)"""
        try:
            if isinstance(specifier, int):
                return next(filter(lambda x: x.handle == specifier, self.descriptors))
            else:
                return next(
                    filter(lambda x: x.uuid == str(specifier), self.descriptors)
                )
        except StopIteration:
            return None

    def add_descriptor(self, descriptor: BleakGATTDescriptor):
        """Add a :py:class:`~BleakGATTDescriptor` to the characteristic.

        Should not be used by end user, but rather by `bleak` itself.
        """
        self.__descriptors.append(descriptor)
