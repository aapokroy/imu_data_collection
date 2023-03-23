import os
import time
import yaml
from contextlib import ExitStack
from typing import List

from imu_manager.mpu6050.mpu6050 import MPU6050
from imu_manager.utils import Singleton


class Manager(metaclass=Singleton):
    """
    Class that handles connections to sensors and provides high-level methods
    for working with them.
    """

    def __init__(self, device_id: str,
                 i2c_buses: List[int], i2c_addresses: List[int]):
        self.device_id = device_id
        self.buses = i2c_buses
        self.addresses = i2c_addresses
        self.sensors = {}
        self.update_sensors()

    def update_sensors(self):
        """Update list of connected sensors"""
        self.sensors = {}
        for bus in self.buses:
            for address in self.addresses:
                try:
                    id_ = f'{self.device_id}_B{bus}A{address}'
                    sensor = MPU6050(id_, bus, address)
                    if sensor.is_connected:
                        self.sensors[sensor.id] = sensor
                except OSError:
                    pass

    def reset_sensor(self, sensor_id: str):
        """Reset sensor settings to minimal functional state"""
        self.sensors[sensor_id].reset()

    def reset_sensors(self):
        """Reset sensors settings to minimal functional state"""
        for sensor_id in self.sensors:
            self.reset_sensor(sensor_id)

    def configure_sensor(self, sensor_id: str,
                           clock_source: int, dlpf_mode: int, rate: int,
                           full_scale_accel_range: int,
                           full_scale_gyro_range: int,
                           accel_fifo_enabled: bool,
                           x_gyro_fifo_enabled: bool,
                           y_gyro_fifo_enabled: bool,
                           z_gyro_fifo_enabled: bool):
        """Configure sensor"""
        sensor = self.sensors[sensor_id]
        sensor.clock_source = clock_source
        sensor.dlpf_mode = dlpf_mode
        sensor.rate = rate
        sensor.full_scale_accel_range = full_scale_accel_range
        sensor.full_scale_gyro_range = full_scale_gyro_range
        sensor.accel_fifo_enabled = accel_fifo_enabled
        sensor.x_gyro_fifo_enabled = x_gyro_fifo_enabled
        sensor.y_gyro_fifo_enabled = y_gyro_fifo_enabled
        sensor.z_gyro_fifo_enabled = z_gyro_fifo_enabled

    def configure_sensors(self, clock_source: int, dlpf_mode: int, rate: int,
                            full_scale_accel_range: int,
                            full_scale_gyro_range: int,
                            accel_fifo_enabled: bool,
                            x_gyro_fifo_enabled: bool,
                            y_gyro_fifo_enabled: bool,
                            z_gyro_fifo_enabled: bool):
        """Configure all sensors"""
        for sensor_id in self.sensors:
            self.configure_sensor(
                sensor_id, clock_source, dlpf_mode, rate,
                full_scale_accel_range, full_scale_gyro_range,
                accel_fifo_enabled,
                x_gyro_fifo_enabled, y_gyro_fifo_enabled, z_gyro_fifo_enabled
            )

    def get_temperature(self, sensor_id: str) -> float:
        """Get sensor temperature"""
        return self.sensors[sensor_id].get_temperature()

    def calibrate_sensor(self, sensor_id: str,
                         max_iters: int, rough_iters: int, buffer_size: int,
                         epsilon: float = 0.1, mu: float = 0.5,
                         v_threshold: float = 0.05):
        """
        Calibrate sensor to make all measurements zero-centered.
        With one exception: accelerometer Z axis is calibrated to 1g.
        """
        self.sensors[sensor_id].calibrate(
            max_iters, rough_iters, buffer_size,
            epsilon, mu, v_threshold
        )

    def calibrate_sensors(self, max_iters: int, rough_iters: int,
                          buffer_size: int, epsilon: float = 0.1,
                          mu: float = 0.5, v_threshold: float = 0.05):
        """Calibrate all sensors"""
        for sensor_id in self.sensors:
            self.calibrate_sensor(
                sensor_id, max_iters, rough_iters, buffer_size,
                epsilon, mu, v_threshold
            )

    def start_session(self, session_path: str, session_name: str,
                      duration: float) -> dict:
        """Start data collection session"""
        metadata_path = os.path.join(session_path, 'metadata')
        raw_data_path = os.path.join(session_path, 'raw_data')
        if not os.path.isdir(session_path):
            os.mkdir(session_path)
        if not os.path.isdir(metadata_path):
            os.mkdir(metadata_path)
        if not os.path.isdir(raw_data_path):
            os.mkdir(raw_data_path)

        session_info = {}
        session_info['name'] = session_name
        session_info['device_id'] = self.device_id
        session_info['time'] = {
            'start': None,
            'duration': duration
        }
        session_info['sensors'] = {}
        session_info['overflows'] = {}
        session_info['files'] = {}
        for sensor_id, sensor in self.sensors.items():
            session_info['sensors'][sensor_id] = {
                'clock_source': sensor.clock_source,
                'dlpf_mode': sensor.dlpf_mode,
                'rate': sensor.rate,
                'sample_rate': sensor.sample_rate,
                'full_scale_accel_range': sensor.full_scale_accel_range,
                'full_scale_gyro_range': sensor.full_scale_gyro_range,
                'accel_factor': sensor.accel_factor,
                'gyro_factor': sensor.gyro_factor,
                'accel_fifo_enabled': sensor.accel_fifo_enabled,
                'x_gyro_fifo_enabled': sensor.x_gyro_fifo_enabled,
                'y_gyro_fifo_enabled': sensor.y_gyro_fifo_enabled,
                'z_gyro_fifo_enabled': sensor.z_gyro_fifo_enabled,
                'package_length':  sensor.package_length
            }
            session_info['overflows'][sensor_id] = []
            session_info['files'][sensor_id] = f'{sensor_id}'

        package_length = []
        packages_per_read = []
        package_count = []
        for sensor in self.sensors.values():
            package_length.append(sensor.package_length)
            if sensor.package_length != 0:
                packages_per_read.append(32 // sensor.package_length)
            else:
                packages_per_read.append(0)
            package_count.append(0)

        with ExitStack() as stack:
            files = []
            for fname in session_info['files'].values():
                fpath = os.path.join(raw_data_path, fname)
                files.append(stack.enter_context(open(fpath, 'wb')))
            time_start = time.time()
            for sensor in self.sensors.values():
                sensor.reset_fifo()
            while time.time() - time_start < duration:
                for i, sensor in enumerate(self.sensors.values()):
                    if package_length[i] > 0:
                        fifo_count = sensor.get_fifo_count()
                        if fifo_count == 1024:
                            session_info['overflows'][sensor.id].append(time.time() - time_start)
                        if fifo_count > package_length[i] * packages_per_read[i]:
                            package = sensor.get_fifo_bytes(package_length[i] * packages_per_read[i])
                            files[i].write(bytes(package))
                            package_count[i] += packages_per_read[i]

        session_info['time']['start'] = time_start
        session_info['n_packages'] = dict(zip(list(self.sensors.keys()), package_count))
        session_info_path = os.path.join(
            metadata_path,
            f'{self.device_id}_session_info.yml'
        )
        with open(session_info_path, 'w') as f:
            yaml.dump(session_info, f, sort_keys=False)
        return session_info
