import re
from uuid import UUID
from typing import List, Union

from bleak.backends.dotnet.winrt.utils import service_uuid_re
from bleak.backends.service import BleakGATTService
from bleak.backends.dotnet.winrt.characteristic import BleakGATTCharacteristicWinRT

from winrt.windows.devices.bluetooth.genericattributeprofile import GattDeviceService





class BleakGATTServiceWinRT(BleakGATTService):
    """GATT Characteristic implementation for the .NET backend, implemented with WinRT"""

    def __init__(self, obj: GattDeviceService):
        super().__init__(obj)
        self.__characteristics = [
            # BleakGATTCharacteristicDotNet(c) for c in obj.GetAllCharacteristics()
        ]

        # TODO: Very hacky way...
        self.__uuid = service_uuid_re.search(self.obj.device_id).groups()[0]

    @property
    def uuid(self):
        return self.__uuid

    @property
    def characteristics(self) -> List[BleakGATTCharacteristicWinRT]:
        """List of characteristics for this service"""
        return self.__characteristics

    def get_characteristic(
        self, _uuid: Union[str, UUID]
    ) -> Union[BleakGATTCharacteristicWinRT, None]:
        """Get a characteristic by UUID"""
        try:
            return next(filter(lambda x: x.uuid == str(_uuid), self.characteristics))
        except StopIteration:
            return None

    def add_characteristic(self, characteristic: BleakGATTCharacteristicWinRT):
        """Add a :py:class:`~BleakGATTCharacteristicWinRT` to the service.

        Should not be used by end user, but rather by `bleak` itself.
        """
        self.__characteristics.append(characteristic)
