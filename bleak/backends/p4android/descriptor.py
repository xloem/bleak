from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.exc import BleakError

class BleakGATTDescriptorP4Android(BleakGATTDescriptor):
    """GATT Descriptor implementation for python-for-android backend"""
    
    def __init__(
        self,
        java,
        characteristic_uuid: str,
    ):
        super(BleakGATTDescriptorP4Android, self).__init__(java)
        self.__uuid = self.obj.getUuid().toString()
        self.__characteristic_uuid = characteristic_uuid

    @property
    def characteristic_handle(self) -> int:
        """handle for the characteristic that this descriptor belongs to"""
        raise BleakError('The Android Bluetooth API does not provide access to handles.')

    @property
    def characteristic_uuid(self) -> str:
        """UUID for the characteristic that this descriptor belongs to"""
        return self.__characteristic_uuid

    @property
    def uuid(self) -> str:
        """UUID for this descriptor"""
        return self.__uuid

    @property
    def handle(self) -> int:
        """Integer handle for this descriptor"""
        raise BleakError('The Android Bluetooth API does not provide access to handles.')
