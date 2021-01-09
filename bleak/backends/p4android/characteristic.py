from uuid import UUID
from typing import Union, List

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor

from jnius import autoclass

class java:
    BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')

_GattCharacteristicsFlagsEnum = {
    BluetoothGattCharacteristic.PROPERTY_BROADCAST: 'broadcast',
    BluetoothGattCharacteristic.PROPERTY_EXTENDED_PROPS: 'extended-properties',
    BluetoothGattCharacteristic.PROPERTY_INDICATE: 'indicate',
    BluetoothGattCharacteristic.PROPERTY_NOTIFY: 'notify',
    BluetoothGattCharacteristic.PROPERTY_READ: 'read',
    BluetoothGattCharacteristic.PROPERTY_SIGNED_WRITE: 'authenticated-signed-writes',
    BluetoothGattCharacteristic.PROPERTY_WRITE: 'write',
    BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE: 'write-without-response',
}

class BleakGATTCharacteristicP4Android(BleakGATTCharacteristic):
    """GATT Characteristic implementation for the python-for-android backend"""

    def __init__(self, java, service_uuid: str):
        super(BleakGATTCharacteristicP4Android, self).__init__(java)
        self.__uuid = self.obj.getUuid().toString()
        self.__properties = self.obj.getProperties()
        self.__service_uuid = service_uuid

        self.__properties = [
            name
            for flag, name
            in _GattCharacteristicsFlagsEnum.items()
            if flag & self.__properties
        ]

        descriptors = self.__java.getDescriptors()
        numDescriptors = len(descriptors)
        self.__descriptors = [
            BleakGATTDescriptorP4Android(descriptors[index], self.__uuid)
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
        return self.__uuid

    @property
    def properties(self) -> List:
        """Properties of this characteristic
        """
        return self.__properties

    @property
    def descriptors(self) -> List:
        """List of descriptors for this service"""
        return self.__descriptors

    def get_descriptor(
        self, specifier: Union[str, UUID]
    ) -> Union[BleakGATTDescriptor, None]:
        """Get a descriptor by UUID (str or uuid.UUID)"""
        if isinstance(specifier, int):
            raise BleakError('The Android Bluetooth API does not provide access to handles.')

        matches = [descriptor
            for descriptor in self.descriptors
            if descriptor.uuid == str(specifier)]
        if len(matches) == 0:
            return None
        return matches[0]
