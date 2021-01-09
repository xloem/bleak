from typing import List

from bleak.backends.service import BleakGATTService
from bleak.backends.bluezdbus.characteristic import BleakGATTCharacteristicP4Android


class BleakGATTServiceP4Android(BleakGATTService):
    """GATT Service implementation for the python-for-android backend"""

    def __init__(self, java):
        super().__init__(java)
        self.__uuid = self.obj.getUuid().toString()
        self.__handle = self.obj.getInstanceId()

        characteristics = self.obj.getCharacteristics()
        numCharacteristics = len(characteristics)
        self.__characteristics = [
            BleakGATTCharacteristicP4Android(characteristics[index], self.uuid)
            for index in range(numCharacteristics)]

    @property
    def uuid(self) -> str:
        """The UUID to this service"""
        return self.__uuid

    @property
    def characteristics(self) -> List[BleakGATTCharacteristicBlueZDBus]:
        """List of characteristics for this service"""
        return self.__characteristics
