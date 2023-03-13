import struct
import yaml
import os
import pandas as pd
from datetime import datetime


class Session:
    def __init__(self, session_dir: str):
        self.name = os.path.basename(session_dir)
        self.duration = None
        self.timestamp = None
        self.date = None
        self.time = None
        self.overflows = None
        self.session_dir = session_dir
        self.metadata_dir = os.path.join(session_dir, 'metadata')
        self.session_info_path = os.path.join(self.metadata_dir, 'session_info.yml')
        self.merged = False
        self.decoded = False
        self.device_ids = []
        self.sensor_ids = []
        if os.path.isdir(session_dir):
            if not os.path.isdir(self.metadata_dir):
                raise FileNotFoundError(f'No metadata directory found in {session_dir}')
            if os.path.isfile(self.session_info_path):
                self.merged = True
                self.decoded = True
                with open(self.session_info_path, 'r') as f:
                    info = yaml.safe_load(f)
                self.duration = info['time']['duration']
                self.timestamp = min(info['time']['start'].values())
                self.overflows = info['overflows']
                for file_name in info['files'].values():
                    decoded_df_path = os.path.join(session_dir, f'{file_name}.csv')
                    if not os.path.isfile(decoded_df_path):
                        self.decoded = False
                for device_id, sensor_ids in info['devices'].items():
                    self.device_ids.append(device_id)
                    self.sensor_ids.extend(sensor_ids)
            else:
                for fname in os.listdir(self.metadata_dir):
                    with open(os.path.join(self.metadata_dir, fname), 'r') as f:
                        metadata = yaml.safe_load(f)
                        self.device_ids.append(metadata['device_id'])
                        self.sensor_ids.extend(metadata['sensors'].keys())
                        if not self.duration:
                            self.duration = metadata['time']['duration']
                        timestamp = metadata['time']['start']
                        if not self.timestamp or self.timestamp > timestamp:
                            self.timestamp = timestamp
        if self.timestamp:
            dt = datetime.utcfromtimestamp(self.timestamp)
            self.date = dt.strftime('%Y-%m-%d')
            self.time = dt.strftime('%H:%M:%S')

    def merge(self):
        session_parts = []
        for file_name in os.listdir(self.metadata_dir):
            if '_session_info.yml' in file_name:
                file_path = os.path.join(self.metadata_dir, file_name)
                with open(file_path, 'r') as f:
                    session_parts.append(yaml.safe_load(f))
                os.remove(file_path)
        session_info = {}
        session_info['name'] = session_parts[0]['name']
        session_info['devices'] = dict(zip(
            [part['device_id'] for part in session_parts],
            [list(part['sensors'].keys()) for part in session_parts]
        ))
        session_info['time'] = {
            'start': dict(zip(
                [part['device_id'] for part in session_parts],
                [part['time']['start'] for part in session_parts]
            )),
            'duration': session_parts[0]['time']['duration']
        }
        session_info['sensors'] = {}
        session_info['overflows'] = {}
        session_info['files'] = {}
        session_info['n_packages'] = {}
        for part in session_parts:
            session_info['sensors'].update(part['sensors'])
            session_info['overflows'].update(part['overflows'])
            session_info['files'].update(part['files'])
            session_info['n_packages'].update(part['n_packages'])        
        session_info['crops'] = {}
        start_time_max = max([part['time']['start'] for part in session_parts])
        for device_id, sensor_ids in session_info['devices'].items():
            delta_t = start_time_max - session_info['time']['start'][device_id]
            for sensor_id in sensor_ids:
                n = session_info['n_packages'][sensor_id]
                delta_n = int(delta_t * session_info['sensors'][sensor_id]['sample_rate'])
                session_info['crops'][sensor_id] = [delta_n, n]
        n_min = min([crop[1] - crop[0] for crop in session_info['crops'].values()])
        for sensor_id in session_info['sensors']:
            crop = session_info['crops'][sensor_id]
            crop[1] -= (crop[1] - crop[0]) - n_min
            session_info['crops'][sensor_id] = crop
        with open(self.session_info_path, 'w') as f:
            yaml.dump(session_info, f, sort_keys=False)
        self.merged = True

    def decode(self):
        with open(self.session_info_path, 'r') as f:
            session_info = yaml.safe_load(f)
        source_file_paths, target_file_paths = [], []
        for fname in session_info['files'].values():
            source_file_paths.append(os.path.join(self.session_dir, 'raw_data', fname))
            target_file_paths.append(os.path.join(self.session_dir, f'{fname}.csv'))
        for i, sensor_id in enumerate(session_info['sensors']):
            package_length = session_info['sensors'][sensor_id]['package_length']
            accel_factor = session_info['sensors'][sensor_id]['accel_factor']
            gyro_factor = session_info['sensors'][sensor_id]['gyro_factor']
            accel_fifo_enabled = session_info['sensors'][sensor_id]['accel_fifo_enabled']
            x_gyro_fifo_enabled = session_info['sensors'][sensor_id]['x_gyro_fifo_enabled']
            y_gyro_fifo_enabled = session_info['sensors'][sensor_id]['y_gyro_fifo_enabled']
            z_gyro_fifo_enabled = session_info['sensors'][sensor_id]['z_gyro_fifo_enabled']
            crop = session_info['crops'][sensor_id]
            df = []
            with open(source_file_paths[i], 'rb') as f:
                data = list(f.read())
                for j in range(crop[0], crop[1]):
                    package = data[j * package_length: (j + 1) * package_length]
                    package_format = '>' + 'h' * (package_length // 2)
                    package = struct.unpack(package_format, memoryview(bytearray(package)))
                    readings = []
                    p = 0
                    if accel_fifo_enabled:
                        readings.append(package[0] * accel_factor)
                        readings.append(package[1] * accel_factor)
                        readings.append(package[2] * accel_factor)
                        p = 3
                    if x_gyro_fifo_enabled:
                        readings.append(package[p] * gyro_factor)
                        p += 1
                    if y_gyro_fifo_enabled:
                        readings.append(package[p] * gyro_factor)
                        p += 1
                    if z_gyro_fifo_enabled:
                        readings.append(package[p] * gyro_factor)
                    df.append(readings)
            columns = []
            if accel_fifo_enabled:
                columns += ['accel_x', 'accel_y', 'accel_z']
            if x_gyro_fifo_enabled:
                columns.append('gyro_x')
            if y_gyro_fifo_enabled:
                columns.append('gyro_y')
            if z_gyro_fifo_enabled:
                columns.append('gyro_z')
            df = pd.DataFrame(df, columns=columns)
            df.to_csv(target_file_paths[i], index=False)
        self.decoded = True
