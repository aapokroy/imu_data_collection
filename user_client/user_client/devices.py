"""
Simple data structures for storing information about connected devices
and sensors.
"""


from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Sensor:
    """Dataclass for storing information about a sensor connnection."""

    id: str
    bus: int
    address: int

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return self.id

    def __eq__(self, other) -> bool:
        if isinstance(other, Sensor):
            return self.id == other.id
        return False


@dataclass
class Device:
    """
    Dataclass for storing information about
    a device (sensor manager) connection.
    """

    id: str
    buses: List[int]
    addresses: List[int]
    sensors: List[Sensor]

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return self.id

    def __eq__(self, other) -> bool:
        if isinstance(other, Device):
            return self.id == other.id
        return False


class Devices:
    """Class for storing information about all active connections."""

    def __init__(self):
        self.__devices = []

    def __len__(self) -> int:
        return len(self.__devices)

    def __getitem__(self, item) -> Device:
        return self.__devices[item]

    def clear(self):
        self.__devices.clear()

    def update(self, device_data: Dict[str, Any]):
        """
        Update list of connected devices and sensors.
        Called by MQTT client when new data is received.
        """
        device = Device(**device_data)
        device.sensors = []
        for sensor_data in device_data['sensors']:
            sensor = Sensor(**sensor_data)
            device.sensors.append(sensor)
        if device not in self.__devices:
            self.__devices.append(device)
