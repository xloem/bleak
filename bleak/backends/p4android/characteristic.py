from uuid import UUID
from typing import Union, List

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor

class BleakGATTCharacteristicP4Android(BleakGATTCharacteristic):
    """GATT Characteristic implementation for the python-for-android backend"""

    def __init__(self, obj: dict, java_characteristic, service_uuid: str):
        super(BleakGATTCharacteristicP4Android, self).__init__(obj)
        self.__java = java_characteristic
        self.__service_uuid = service_uuid

        descriptors = self.__java.getDescriptors()
        numDescriptors = len(descriptors)
        self.__descriptors = [

            for index in range(numDescriptors)]
            
        
    @property
    def service_uuid(self) -> str:
        """The uuid of the Service containing this characteristic"""
        return self.__service_uuid

    @property
    def handle(self) -> int:
        """The handle of this characteristic"""
        raise BleakError('The Android Bluetooth API does not provide access to handles.')

    @property
    def uuid(self) -> str:
        """The uuid of this characteristic"""
        return self.obj.get("UUID")

    @property
    def properties(self) -> List:
        """Properties of this characteristic
        """
        return self.obj["Flags"]

    @property
    def descriptors(self) -> List:
        """List of descriptors for this service"""
        return self.__descriptors
