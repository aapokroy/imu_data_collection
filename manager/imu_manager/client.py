import yaml
import shutil
import requests
import logging
import traceback
from enum import IntEnum
from typing import Any, Callable, Dict, List

from paho.mqtt.client import Client as MQTTClient
from paho.mqtt.client import MQTTMessage

from imu_manager.manager import Manager
from imu_manager.config import Config
from imu_manager.utils import Singleton, TempDir, CommandThread


class MessageType(IntEnum):
    """Message types for MQTT info messages"""
    ERROR = 0
    SUCCESS = 1
    WARNING = 2
    INFO = 3
    DATA = 4


class Client(metaclass=Singleton):
    """MQTT client for sensor manager"""

    def __init__(self, cfg: Config, manager: Manager,
                 command_thread: CommandThread):
        self.cfg = cfg
        self.manager = manager
        self.command_thread = command_thread
        self.__client = MQTTClient(cfg.device_id)
        self.__client.on_connect = self.__on_connect
        self.__client.on_message = self.__on_message
        self.__client.connect(cfg.server.ip, cfg.server.mqtt.broker.port)
        self.__client.subscribe(cfg.server.mqtt.topic.control)

    def __publish(self, msg_type: MessageType, msg: str, tb: str = None):
        if msg:
            if msg_type == MessageType.INFO:
                logging.info(msg)
            elif msg_type == MessageType.SUCCESS:
                logging.info(msg)
            elif msg_type == MessageType.ERROR:
                logging.error(msg)
                if tb is not None:
                    logging.error(tb)
            elif msg_type == MessageType.WARNING:
                logging.warning(msg)
        payload = {
            'device_id': self.cfg.device_id,
            'type': int(msg_type),
            'msg': msg
        }
        payload = yaml.dump(payload)
        result = self.__client.publish(self.cfg.server.mqtt.topic.info, payload)
        if result[0] != 0:
            logging.error('Failed to send message')

    def __on_connect(self, client: MQTTClient,
                     userdata: Any, flags: dict, rc: int):
        if rc == 0:
            logging.info('Connected to MQTT Broker: {}:{}'.format(
                    self.cfg.server.ip,
                    self.cfg.server.mqtt.broker.port
            ))
            self.__run_manager_command(
                command=self.__cmd_get_connected_sensors,
                args={},
                sync=True
            )
            self.__run_manager_command(
                command=self.__cmd_load_sensors_configurations,
                args={'sensor_ids': None},
                sync=True
            )
        else:
            logging.error(f'Failed to connect, return code {rc}')

    def __on_message(self, client: MQTTClient,
                     userdata: Any, msg: MQTTMessage):
        if msg.topic == self.cfg.server.mqtt.topic.control:
            payload = yaml.safe_load(msg.payload.decode())
            if 'command' not in payload:
                logging.error('Command key not found in payload')
                return
            error, tb = None, None
            try:
                command_name = '_{}__cmd_{}'.format(
                    self.__class__.__name__,
                    payload['command']
                )
                command = self.__getattribute__(command_name)
                args = payload['args'] if 'args' in payload else {}
                logging.info(f'Executing command: {payload["command"]}')
                self.__run_manager_command(command, args)
            except AttributeError:
                error = f'Invalid command: {payload["command"]}'
            except KeyError as e:
                error = f'Invalid command structure: {e}'
                tb = traceback.format_exc()
            except Exception as e:
                error = f'Error while processing command: {e}'
                tb = traceback.format_exc()
            if error:
                self.__publish(MessageType.ERROR, error, tb)

    def __command_wrapper(self, command: Callable[[Dict], None], args: Dict):
        """
        Manager command wrapper.
        Handles errors, actualizes list of connected sensors.
        If new sensors are connected, loads their configurations.
        """
        error, tb = None, None
        try:
            previous_sensor_ids = self.manager.sensors.keys()
            self.manager.update_sensors()
            sensor_ids = self.manager.sensors.keys()
            new_sensor_ids = set(sensor_ids) - set(previous_sensor_ids)
            if new_sensor_ids:
                self.__cmd_load_sensors_configurations(args={
                    'sensor_ids': list(new_sensor_ids)
                })
                self.__cmd_get_connected_sensors(args={})
            command(args)
        except OSError as e:
            if e.errno == 6:
                faulty_sensors = []
                for sensor in self.manager.sensors.values():
                    if not sensor.is_connected:
                        faulty_sensors.append(sensor.id)
                if faulty_sensors:
                    error = 'Connection with sensors {} lost'.format(
                        ', '.join(map(lambda x: f'"{x}"', faulty_sensors))
                    )
                else:
                    error = 'Connection with sensors lost'
            else:
                error = f'Error while running command: {e}'
                tb = traceback.format_exc()
        except KeyError as e:
            error = f'Invalid command structure: {e}'
            tb = traceback.format_exc()
        except Exception as e:
            error = f'Error while running command: {e}'
            tb = traceback.format_exc()
        if error:
            self.__publish(MessageType.ERROR, error, tb)

    def __run_manager_command(self, command: Callable[[Dict], None],
                              args: Dict, sync: bool = False):
        """Run manager command in separate thread"""
        if not self.command_thread.is_busy:
            self.command_thread.run_command(
                command=self.__command_wrapper,
                args=(command, args),
                sync=sync
            )
        else:
            self.__publish(MessageType.ERROR, 'Manager is busy')

    def __filter_sensor_ids(self, sensor_ids: List[str]) -> List[str]:
        """Filter sensor ids to get only existing sensors"""
        if sensor_ids is None:
            return list(self.manager.sensors.keys())
        else:
            sensor_ids = list(filter(
                lambda x: x in self.manager.sensors,
                sensor_ids
            ))
            return sensor_ids

    def run(self, async_: bool = False):
        """Run MQTT client"""
        if async_:
            self.__client.loop_start()
        else:
            self.__client.loop_forever()

    # Manager commands. All commands must have args parameter.
    def __cmd_get_connected_sensors(self, args: Dict):
        data = {
            'id': self.cfg.device_id,
            'buses': self.cfg.i2c.buses,
            'addresses': self.cfg.i2c.addresses,
            'sensors': [
                {
                    'id': sensor.id,
                    'bus': sensor.bus,
                    'address': sensor.address,
                }
                for sensor in self.manager.sensors.values()
            ]
        }
        msg = {
            'type': 'connected_sensors',
            'data': data
        }
        self.__publish(MessageType.DATA, msg)

    def __cmd_load_sensors_configurations(self, args: Dict):
        sensor_ids = self.__filter_sensor_ids(args['sensor_ids'])
        for sensor_id, settings in self.cfg.sensor_settings.items():
            if sensor_id in self.manager.sensors and sensor_id in sensor_ids:
                self.manager.configurate_sensor(sensor_id, **settings)
        self.__publish(MessageType.SUCCESS, 'Sensor configurations loaded')

    def __cmd_reset_sensors(self, args: Dict):
        sensor_ids = self.__filter_sensor_ids(args['sensor_ids'])
        for sensor_id in sensor_ids:
            self.manager.reset_sensor(sensor_id)
            if sensor_id in self.cfg.sensor_settings:
                del self.cfg.sensor_settings[sensor_id]
        self.cfg.save()
        self.__publish(MessageType.SUCCESS, 'Sensors reseted')

    def __cmd_configurate_sensors(self, args: Dict):
        sensor_ids = self.__filter_sensor_ids(args['sensor_ids'])
        del args['sensor_ids']
        for sensor_id in sensor_ids:
            self.manager.configurate_sensor(sensor_id, **args)
            self.cfg.sensor_settings[sensor_id] = args.copy()
        self.cfg.save()
        self.__publish(MessageType.SUCCESS, 'Sensors configurated')

    def __cmd_calibrate_sensors(self, args: Dict):
        sensor_ids = self.__filter_sensor_ids(args['sensor_ids'])
        del args['sensor_ids']
        for sensor_id in sensor_ids:
            self.manager.calibrate_sensor(sensor_id, **args)
        self.__publish(MessageType.SUCCESS, 'Sensors calibrated')

    def __cmd_start_session(self, args: Dict):
        session_name = args['session_name']
        duration = args['duration']
        session_path = session_name
        archive_name = f'{session_name}_{self.cfg.device_id}'
        archive_path = f'{archive_name}.zip'
        with TempDir([session_path, archive_path]):
            self.manager.start_session(session_path, session_name, duration)
            shutil.make_archive(archive_name, 'zip', session_name)
            with open(f'{archive_name}.zip', 'rb') as f:
                response = requests.post(
                    url='http://{}:{}/upload'.format(
                        self.cfg.server.ip,
                        self.cfg.server.file_server.port
                    ),
                    files={'file': f}
                )
                if response.status_code != 200:
                    error = f'Error while uploading session: {response.status_code}'
                    self.__publish(MessageType.ERROR, error)
                else:
                    msg = {
                        'type': 'session_part',
                        'data': {
                            'session_name': session_name,
                            'file_name': response.json()['filename'],
                            'url': response.json()['url']
                        }
                    }
                    self.__publish(MessageType.DATA, msg)
            msg = f'Session "{session_name}" finished'
            self.__publish(MessageType.SUCCESS, msg)
