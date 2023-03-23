import yaml
import shutil
import os
import time
import pandas as pd
import threading
import requests
import socket
import re
from typing import Any
from PIL import Image
import zipfile

import streamlit as st
from streamlit.runtime.scriptrunner.script_run_context import add_script_run_ctx
from paho.mqtt.client import MQTTMessage
from paho.mqtt.client import Client as MQTTClient

from config import Config
from constants import DLPF_ENUM, CLOCK_ENUM, GYRO_RANGE_ENUM, ACCEL_RANGE_ENUM
from utils import TempDir, natural_keys, zipdir
from streamlit_utils import rerun
from streamlit_utils.message_logger import MessageType, Logger
from session_processor import Session
from devices import Devices


# TODO: Inpage help


st.set_page_config(
    page_title='IMU Data Collection',
    page_icon=Image.open('./.streamlit/icon.png'),
    layout='centered',
    initial_sidebar_state='expanded'
)


hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)


# Init sessions state
if 'client_id' not in st.session_state:
    st.session_state.client_id = socket.gethostname()
if 'devices_last_update' not in st.session_state:
    st.session_state.devices_last_update = 0


@st.cache_resource()
def init_resources():
    """Init app resources. Will be called only once."""
    config_path = os.environ.get('config_path', './config.yml')
    cfg = Config(config_path)
    logger = Logger()
    devices = Devices()
    sessions_monitor = rerun.create_directory_monitor(cfg.path.sessions)
    sessions_monitor.start()
    return cfg, logger, devices, sessions_monitor


cfg, logger, devices, sessions_monitor = init_resources()


class Client:
    """MQTT client for communicating with sensor managers"""
    def __init__(self, client_id: str, mqtt_ip: str, mqtt_port: int,):
        self.id = client_id
        self.ip = mqtt_ip
        self.port = mqtt_port
        self.__client = MQTTClient(client_id)
        self.__client.on_connect = self.__on_connect
        self.__client.on_message = self.__on_message
        self.__client.connect(self.ip, self.port)
        self.__client.subscribe(cfg.server.mqtt.topic.info)
        self.__client_thread = None
        self.__is_running = False

    @property
    def is_running(self):
        """Return True if client is running, False otherwise"""
        return self.__is_running

    @property
    def is_connected(self):
        """Return True if client is connected, False otherwise"""
        return self.__client.is_connected()

    def __on_connect(self, client: MQTTClient,
                     userdata: Any, flags: dict, rc: int):
        st.session_state.devices_last_update = 0
        rerun.force_rerun()

    def __on_message(self, client: MQTTClient,
                     userdata: Any, mqtt_msg: MQTTMessage):
        payload = yaml.safe_load(mqtt_msg.payload.decode())
        device_id = payload['device_id']
        msg_type = payload['type']
        msg = payload['msg']
        if msg_type != MessageType.DATA:
            logger.log(device_id, msg_type, msg)
        else:
            data_type, data = msg['type'], msg['data']
            if data_type == 'connected_sensors':
                devices.update(data)
            elif data_type == 'session_part':
                self.download_session_part(**data)
        rerun.force_rerun()

    def run(self):
        """Start MQTT client in a separate thread."""
        if self.__is_running:
            raise RuntimeError('Client is already running')
        self.__client_thread = threading.Thread(
            target=self.__client.loop_forever
        )
        add_script_run_ctx(self.__client_thread)
        self.__is_running = True
        self.__client_thread.start()

    def stop(self):
        """Stop MQTT client."""
        if not self.__is_running:
            raise RuntimeError('Client is not running')
        self.__client.disconnect()
        self.__client_thread.join()
        self.__is_running = False

    def send_command(self, command: str, args: dict):
        """Unified method for sending control commands to sensor managers."""
        payload = {
            'command': command,
            'args': args
        }
        payload = yaml.dump(payload)
        result = self.__client.publish(
            cfg.server.mqtt.topic.control,
            payload
        )
        status = result[0]
        return status

    def download_session_part(self, session_name: str,
                              file_name: str, url: str):
        """Download and unpack session part from file server."""
        file_port = cfg.server.file_server.port
        response = requests.get(
            url=f"http://{self.ip}:{file_port}{url}",
            stream=True
        )
        session_dir = os.path.join(cfg.path.sessions, session_name)
        if not os.path.exists(session_dir):
            os.mkdir(session_dir)
        file_path = os.path.join(session_dir, file_name)
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(session_dir)
        os.remove(file_path)
        response = requests.delete(
            url=f"http://{self.ip}:{file_port}/delete/{file_name}"
        )


@st.cache_resource(max_entries=1)
def init_mqtt_client(client_id: str, mqtt_ip: str, mqtt_port: int):
    try:
        client = Client(client_id, mqtt_ip, mqtt_port)
        client.run()
        return client
    except ConnectionRefusedError:
        st.session_state.mqtt_connection_error = 'Connection refused'
    except socket.timeout:
        st.session_state.mqtt_connection_error = 'Connection timeout'
    except OSError:
        st.session_state.mqtt_connection_error = 'Network is unreachable'
    except ValueError:
        st.session_state.mqtt_connection_error = 'Invalid IP address'


client = init_mqtt_client(
    st.session_state.client_id,
    cfg.server.ip,
    cfg.server.mqtt.broker.port
)

if client and client.is_running and not client.is_connected:
    st.spinner('Connecting to MQTT broker...')

if client and client.is_connected:
    last_update = st.session_state.devices_last_update
    update_interval = cfg.devices_update_interval
    if time.time() - last_update > update_interval:
        devices.clear()
        client.send_command(
            command='get_connected_sensors',
            args={}
        )
        st.session_state.devices_last_update = time.time()


def st_server_connection():
    """Streamlit server connection widget."""
    def update_connection():
        """Save server connection settings and stop MQTT client if needed."""
        if 'server_ip' in st.session_state:
            cfg.server.ip = st.session_state.server_ip
        if 'mqtt_port' in st.session_state:
            cfg.server.mqtt.broker.port = st.session_state.mqtt_port
        if 'file_port' in st.session_state:
            cfg.server.file_server.port = st.session_state.file_port
        cfg.save()
        if client and client.is_running:
            if cfg.server.ip != client.ip \
                  or cfg.server.mqtt.broker.port != client.port:
                client.stop()

    st.header('Server conncetion')
    cols = st.columns(3)
    with cols[0]:
        st.text_input(
            'Server IP', value=cfg.server.ip,
            key='server_ip', on_change=update_connection
        )
    with cols[1]:
        st.number_input(
            'MQTT port',
            min_value=0, max_value=65535, value=cfg.server.mqtt.broker.port,
            key='mqtt_port', on_change=update_connection
        )
    with cols[2]:
        st.number_input(
            'File server port',
            min_value=0, max_value=65535, value=cfg.server.file_server.port,
            key='file_port', on_change=update_connection
        )

    cols = st.columns(2)

    # MQTT client connection status
    with cols[0]:
        if client and client.is_connected:
            st.success('Successfully connected to MQTT broker')
        elif client and client.is_running:
            st.info('Connecting to MQTT broker...')
        else:
            if 'mqtt_connection_error' in st.session_state:
                st.error(st.session_state.mqtt_connection_error)
            else:
                st.error('Cannot connect to MQTT broker')

    # File server connection status
    with cols[1]:
        file_port = cfg.server.file_server.port
        try:
            response = requests.get(
                url=f"http://{cfg.server.ip}:{file_port}/ping"
            )
            if response.status_code == 200:
                st.success('Successfully connected to file server')
            else:
                st.error('Cannot connect to file server')
        except Exception:
            st.error('Cannot connect to file server')


def st_manage_sessions():
    """
    Streamlit UI for managing sessions.
    Displays a list of sessions and allows to merge, decode and delete them.
    Allows to inspect session metadata and data.
    """
    sessions = []
    for fname in os.listdir(cfg.path.sessions):
        session_dir = os.path.join(cfg.path.sessions, fname)
        metadata_dir = os.path.join(session_dir, 'metadata')
        if os.path.isdir(session_dir) and os.path.isdir(metadata_dir):
            sessions.append(Session(session_dir))
    sessions.sort(key=lambda x: natural_keys(x.name))
    name2session = {session.name: session for session in sessions}
    selected_sessions = st.multiselect(
        'Select sessions to manage (All by default)',
        options=[session.name for session in sessions]
    )
    selected_sessions = [name2session[name] for name in selected_sessions]
    if not selected_sessions:
        selected_sessions = sessions

    # Sessions metadata
    data = {
        'date': [session.date for session in selected_sessions],
        'time': [session.time for session in selected_sessions],
        'name': [session.name for session in selected_sessions],
        'duration': [session.duration for session in selected_sessions],
        'merged': [session.merged for session in selected_sessions],
        'decoded': [session.decoded for session in selected_sessions],
    }
    for device in devices:
        data[device.id] = [
            device.id in session.device_ids
            for session in selected_sessions
            ]
    df = pd.DataFrame(data)
    df.sort_values(by=['date', 'time'], inplace=True, ascending=False)
    df.reset_index(drop=True, inplace=True)
    st.dataframe(df, use_container_width=True)

    # Global session managemnet buttons
    cols = st.columns(4)
    with cols[0]:
        merge_all_sessions = st.button(
            'Merge',
            type='primary',
            use_container_width=True
        )
    with cols[1]:
        decode_all_sessions = st.button(
            'Decode',
            type='primary',
            use_container_width=True
        )
    with cols[2]:
        download_sessions = st.button(
            'Download',
            type='primary',
            use_container_width=True
        )
    with cols[3]:
        delete_sessions = st.button(
            'Delete',
            type='primary',
            use_container_width=True
        )
    if merge_all_sessions:
        progress_text = 'Merging sessions...'
        progress_bar = st.progress(0, text=progress_text)
        for i, session in enumerate(sessions):
            if not session.merged:
                session.merge()
            progress_percent = (i + 1) / len(sessions)
            progress_bar.progress(progress_percent, text=progress_text)
        st.experimental_rerun()
    if decode_all_sessions:
        progress_text = 'Decoding sessions...'
        progress_bar = st.progress(0, text=progress_text)
        for i, session in enumerate(sessions):
            if session.merged and not session.decoded:
                session.decode()
            progress_percent = (i + 1) / len(sessions)
            progress_bar.progress(progress_percent, text=progress_text)
        st.experimental_rerun()
    if download_sessions:
        archive_path = './sessions.zip'
        with TempDir(archive_path):
            with st.spinner('Archiving sessions...'):
                with zipfile.ZipFile(archive_path, 'w') as zipf:
                    for session in selected_sessions:
                        session_dir = os.path.join(cfg.path.sessions, session.name)
                        zipdir(session_dir, zipf)
            st.download_button(
                label='Download archive',
                data=open(archive_path, 'rb').read(),
                file_name='./sessions.zip',
                mime='application/zip',
                use_container_width=True
            )
    if delete_sessions:
        for session in selected_sessions:
            shutil.rmtree(os.path.join(cfg.path.sessions, session.name))

    # Single session management
    st.write('---')
    session_name = st.selectbox('Session name', name2session.keys())
    if session_name:
        session = name2session[session_name]
        session_dir = os.path.join(cfg.path.sessions, session.name)

        # Session status
        if session.decoded:
            st.success('Session is merged and decoded')
        elif session.merged:
            st.info('Session is merged, but not decoded')
        else:
            st.info('Session parts aren\'t merged')
            st.write(f'Recieved session parts from: {", ".join(session.device_ids)}')

        # Session metadata
        if session.merged:
            with st.expander("Session metadata"):
                metadata_cols = st.columns(3)
                with metadata_cols[0]:
                    block = []
                    block.append(f'Date: {session.date}')
                    block.append(f'Time: {session.time}')
                    block.append(f'Duration: {session.duration}')
                    total_overflows = sum(map(len, session.overflows.values()))
                    block.append(f'Overflows: {total_overflows}')
                    st.markdown('  \n'.join(block))
                with metadata_cols[1]:
                    block = []
                    for device_id in session.device_ids:
                        block.append(f'- {device_id}')
                    st.markdown('  \n'.join(block))
                with metadata_cols[2]:
                    block = []
                    for sensor_id in session.sensor_ids:
                        block.append(f'- {sensor_id}')
                    st.markdown('  \n'.join(block))

        # Session data
        if session.decoded:
            with st.expander('Session data'):
                files = []
                for file in os.listdir(session_dir):
                    file_path = os.path.join(session_dir, file)
                    if os.path.isfile(file_path):
                        files.append(file)
                tabs = st.tabs(files)
                for i, tab in enumerate(tabs):
                    with tab:
                        file_path = os.path.join(session_dir, files[i])
                        try:
                            df = pd.read_csv(file_path).head(500)
                            style = df.style
                            accel_subset = [f'accel_{axis}' for axis in 'xyz']
                            gyro_subset = [f'gyro_{axis}' for axis in 'xyz']
                            accel_subset = [col for col in accel_subset if col in df.columns]
                            gyro_subset = [col for col in gyro_subset if col in df.columns]
                            style = style.background_gradient(
                                subset=accel_subset,
                                axis=None,
                                cmap='Reds'
                            )
                            style = style.background_gradient(
                                subset=gyro_subset,
                                axis=None,
                                cmap='Reds'
                            )
                            st.dataframe(style, use_container_width=True)
                        except pd.errors.EmptyDataError:
                            st.warning((
                                'Data file is empty, '
                                'probably corresponding sensor is not configured.'
                            ))

        # Control buttons
        if session.decoded:
            pass
        elif session.merged:
            if st.button('Decode session', use_container_width=True):
                session.decode()
                st.experimental_rerun()
        else:
            cols = st.columns(2)
            with cols[0]:
                if st.button("Merge session parts", use_container_width=True):
                    session.merge()
                    st.experimental_rerun()
            with cols[1]:
                if st.button("Merge and decode", use_container_width=True):
                    session.merge()
                    session.decode()
                    st.experimental_rerun()


def st_new_session():
    """Streamlit UI for starting a new session."""
    session_name = st.text_input('Session name')
    name_is_valid = re.match(r'^[\w-]+$', session_name)
    cols = st.columns(2)
    with cols[0]:
        duration = st.number_input(
            'Duration', value=1, min_value=0,
            max_value=cfg.max_session_duration
        )
    with cols[1]:
        name_conflict_option = st.selectbox(
            'If session with this name already exists',
            [
                'add number to session name',
                'add timestamp to session name',
                'overwrite existing session'
            ]
        )
        if name_is_valid and \
                os.path.isdir(os.path.join(cfg.path.sessions, session_name)):
            if name_conflict_option == 'add number to session name':
                session_names = os.listdir(cfg.path.sessions)
                session_names = [
                    name for name in session_names
                    if os.path.isdir(os.path.join(cfg.path.sessions, name))
                ]
                i = 2
                while f'{session_name}_{i}' in session_names:
                    i += 1
                session_name = f'{session_name}_{i}'
            elif name_conflict_option == 'add timestamp to session name':
                session_name = '{}_{}'.format(
                    session_name,
                    int(time.time())
                )
    submitted = st.button(
        'Start session', type='primary',
        use_container_width=True,
        disabled=(not name_is_valid or duration <= 0)
    )
    st.caption('Session will be saved in {}'.format(
        os.path.join(cfg.path.sessions, session_name)
    ))
    session_dir = os.path.join(cfg.path.sessions, session_name)
    if session_name and not name_is_valid:
        st.error('Session name is not valid')
    if session_name and os.path.isdir(session_dir):
        st.warning(("""Session with this name already exists.
        It will be overwritten if you start a new session."""))
    if submitted:
        if os.path.isdir(session_dir):
            shutil.rmtree(session_dir)
        command = 'start_session'
        args = {
            'session_name': session_name,
            'duration': duration
        }
        client.send_command(command, args)
        progress_text = 'Session is running'
        progress_bar = st.progress(0, progress_text)
        sleep_time = 0.2
        for i in range(int(duration / sleep_time)):
            percent = (i + 1) * sleep_time / duration
            progress_bar.progress(percent, progress_text)
            time.sleep(sleep_time)


def st_sensor_select(key):
    """Multiselect widget for selecting available sensors."""
    with st.expander('Select sensors'):
        id2device = {device.id: device for device in devices}
        device_ids = list(id2device.keys())
        selected_device_ids = st.multiselect(
            'Devices', options=device_ids, default=device_ids,
            key=f'{key}_sensor_select_devices'
        )
        sensors = []
        for device_id in selected_device_ids:
            sensors += id2device[device_id].sensors
        sensor_ids = [sensor.id for sensor in sensors]
        selected_sensor_ids = st.multiselect(
            'Sensors', options=sensor_ids, default=sensor_ids,
            key=f'{key}_sensor_select_sensors'
        )
        if len(selected_device_ids) == len(device_ids) \
                and len(selected_sensor_ids) == len(sensor_ids):
            return None
        else:
            return selected_sensor_ids


def st_sensor_command_wrapper(name, body):
    """
    Wrapper for sensor command widgets.
    Adds sensor selection and submit button.
    Sends mqtt command on submit.
    """
    key = name.lower().replace(' ', '_')
    command, args = body()
    selected_sensor_ids = st_sensor_select(key)
    disabled = (selected_sensor_ids == [])
    args['sensor_ids'] = selected_sensor_ids
    submit_button = st.button(
        label=name,
        type='primary',
        use_container_width=True,
        disabled=disabled
    )
    if submit_button:
        status = client.send_command(command, args)
        if status == 0:
            st.info(f"Command sended: {name}")
        else:
            st.error(f'Failed to send command: {name}')
    if disabled:
        st.warning('At least one sensor should be selected.')


def st_reset_sensors():
    """Streamlit UI for sensor reset."""
    return 'reset_sensors', {}


def st_calibrate_sensors():
    """Streamlit UI for sensor calibration."""
    max_iters = st.number_input(
        "Number of iterations",
        min_value=5, max_value=500, value=100
    )
    rough_iters = st.number_input(
        "Number of \"rough\" iterations",
        min_value=0, max_value=max_iters, value=5
    )
    buffer_size = st.number_input(
        "Buffer size",
        min_value=1, max_value=500, value=150
    )
    command = 'calibrate_sensors'
    args = {
        'max_iters': max_iters,
        'rough_iters': rough_iters,
        'buffer_size': buffer_size
    }
    return command, args


def st_configure_sensors():
    """Streamlit UI for sensor configuration."""
    rate_col1, rate_col2 = st.columns(2)
    with rate_col1:
        clock_type = st.selectbox("Clock source", CLOCK_ENUM.keys(), 1)
        rate = st.number_input(
            'Sample rate divider',
            min_value=0, max_value=255, value=9
        )
    with rate_col2:
        dlpf = st.selectbox(
            'DLPF mode',
            options=DLPF_ENUM.keys(), index=6
        )
        gyro_rate = 8000 if dlpf == '256' else 1000
        st.metric("Sample rate", gyro_rate / (rate + 1))
    st.write('---')
    conf_col1, conf_col2 = st.columns(2)
    with conf_col1:
        accel_range = st.selectbox("Accel range", ACCEL_RANGE_ENUM.keys())
        accel_fifo_enabled = st.checkbox("Accel fifo enabled", True)
    with conf_col2:
        gyro_range = st.selectbox("Gyro range", GYRO_RANGE_ENUM.keys())
        x_gyro_fifo_enabled = st.checkbox("X gyro fifo enabled", True)
        y_gyro_fifo_enabled = st.checkbox("Y gyro fifo enabled", True)
        z_gyro_fifo_enabled = st.checkbox("Z gyro fifo enabled", True)
    command = 'configure_sensors'
    args = {
        'clock_source': CLOCK_ENUM[clock_type],
        'dlpf_mode': DLPF_ENUM[dlpf],
        'rate': rate,
        'full_scale_accel_range': ACCEL_RANGE_ENUM[accel_range],
        'full_scale_gyro_range': GYRO_RANGE_ENUM[gyro_range],
        'accel_fifo_enabled': accel_fifo_enabled,
        'x_gyro_fifo_enabled': x_gyro_fifo_enabled,
        'y_gyro_fifo_enabled': y_gyro_fifo_enabled,
        'z_gyro_fifo_enabled': z_gyro_fifo_enabled
    }
    return command, args


def st_connected_sensors():
    """Streamlit UI for displaying connected devices."""
    cols = {
        'device': [],
        'bus': [],
        'address': [],
        'is_connected': []
    }
    for device in devices:
        for bus in device.buses:
            for address in device.addresses:
                cols['device'].append(device.id)
                cols['bus'].append(bus)
                cols['address'].append(address)
                cols['is_connected'].append(False)
                for sensor in device.sensors:
                    if sensor.bus == bus and sensor.address == address:
                        cols['is_connected'][-1] = True
                        break
    df = pd.DataFrame(cols)
    st.dataframe(df, use_container_width=True)

    cols = st.columns(2)
    with cols[0]:
        if st.button('Refresh', type='primary',     use_container_width=True):
            devices.clear()
            client.send_command(
                command='get_connected_sensors',
                args={}
            )
            st.session_state.devices_last_update = time.time()
    with cols[1]:
        if st.button('Load configurations', use_container_width=True):
            client.send_command(
                command='load_sensors_configurations',
                args={'sensor_ids': None}
            )


st.title('IMU data collection')
st_server_connection()
if client and client.is_connected:
    with st.sidebar:
        logger()

    st.header('Sessions')
    session_tabs = st.tabs(['New session', 'Manage sessions'])
    with session_tabs[0]:
        st_new_session()
    with session_tabs[1]:
        st_manage_sessions()

    st.header('Sensors')
    tabs = st.tabs([
        'Connected sensors',
        'Configure sensors',
        'Calibrate sensors',
        'Reset sensors'
    ])
    with tabs[0]:
        st_connected_sensors()
    with tabs[1]:
        st_sensor_command_wrapper(
            'Configure sensors',
            st_configure_sensors
        )
    with tabs[2]:
        st_sensor_command_wrapper(
            'Calibrate sensors',
            st_calibrate_sensors
        )
    with tabs[3]:
        st_sensor_command_wrapper(
            'Reset sensors',
            st_reset_sensors
        )
