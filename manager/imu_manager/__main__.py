import os
import logging
from logging.handlers import RotatingFileHandler

from imu_manager.manager import Manager
from imu_manager.client import Client
from imu_manager.config import Config
from imu_manager.utils import CommandThread


if __name__ == '__main__':
    log_dir = os.environ.get('log_dir', './logs')
    log_path = os.path.join(log_dir, 'imu_manager.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(threadName)-13.13s] [%(levelname)-7.7s]  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            RotatingFileHandler(log_path, maxBytes=1024),
            logging.StreamHandler()
        ]
    )
    logging.info('Starting sensor manager...')

    config_path = os.environ.get('config_path', './config.yml')
    cfg = Config(config_path, keep_type=['sensor_settings'])

    manager = Manager(cfg.device_id, cfg.i2c.buses, cfg.i2c.addresses)
    command_thread = CommandThread('ManagerThread')
    command_thread.start()
    client = Client(cfg, manager, command_thread)
    client.run()
