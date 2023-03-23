# IMU data collection
This is a system for creating a dataset of IMU data to use in machine learning applications.

## Table of contents
- [IMU data collection](#imu-data-collection)
  - [Table of contents](#table-of-contents)
  - [Project structure](#project-structure)
  - [Setup](#setup)
    - [Broker server setup](#broker-server-setup)
    - [User client setup](#user-client-setup)
    - [Orange Pi Zero setup](#orange-pi-zero-setup)
      - [Install armbian](#install-armbian)
      - [Connect to the board](#connect-to-the-board)
      - [Setup WiFi connection](#setup-wifi-connection)
      - [Enable I2C](#enable-i2c)
      - [Install docker](#install-docker)
      - [Install app](#install-app)
      - [Autorun app](#autorun-app)
      - [Connect sensors to the board](#connect-sensors-to-the-board)
  - [Data collection](#data-collection)
    - [Configure and calibrate sensors](#configure-and-calibrate-sensors)
    - [Collect](#collect)
    - [Merge, decode and download](#merge-decode-and-download)

## Project structure
Data is collected using MPU-6050 IMU sensors. The sensors are connected via I2C to an Orange Pi Zero board acting as a sensor hub. (Any armbian compatible board with I2C should work)

Sensor hubs are connected to a broker server via MQTT protocol. The broker server consists of a Mosquitto broker server and a simple FastAPI data transfer server.

The data is collected using a user client. The client is a simple streamlit web application that allows the user to connect to the broker server, configurate sensors, run the data collection and download the collected data.

## Setup
### Broker server setup
1. Install docker and docker-compose on your server
2. Create a directory for the app and download following file and folder into it:
    - `server/docker-compose.yml`
    - `server/mosquitto`
3. Run `docker-compose up -d` in the app directory to start the server

### User client setup
You can host the client on the same server as the broker server or run it locally on your computer to have direct access to the data.
1. Install docker and docker-compose
2. Create a directory for the app and download following files into it:
    - `user_client/docker-compose.yml`
    - `user_client/config.yml`
3. Create a folder named `sessions` in the app directory
4. Fill in the `config.yml` file with your MQTT broker credentials.
5. Run `docker-compose up -d` in the app directory to start the client
6. Open `http://localhost:8085` in your browser to access the client

### Orange Pi Zero setup
#### Install armbian
Download the latest armbian image from https://www.armbian.com/orange-pi-zero/ and flash it to an SD card using etcher or similar.

#### Connect to the board
Connect the board to your network using an ethernet cable. Connect to the board using ssh. The default username is `root` and the default password is `1234`.

#### Setup WiFi connection
To setup WiFi connection, run `nmtui` and follow the instructions.

```bash
$ nmtui
```

#### Enable I2C
To enable I2C buses, run `armbian-config` and enable i2c0 and i2c1 in the `System/Hardware` section.

```bash
$ armbian-config
```

#### Install docker
To install docker, run the following commands:

```bash
$ apt update
$ apt install apt-transport-https ca-certificates curl software-properties-common
$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
$ add-apt-repository "deb [arch=armhf] https://download.docker.com/linux/ubuntu eoan stable"
$ apt update
$ apt install docker-ce docker-ce-cli docker-compose
```

#### Install app
Create a directory for the app and download following files into it:
- `manager/docker-compose.yml`
- `manager/config.yml`

Fill in the `config.yml` file with your MQTT broker credentials and unique ID for the sensor hub.

#### Autorun app
To autorun the app on boot, edit the `/etc/rc.local` file and add the following lines before the `exit 0` line:

```bash
sudo mkdir /sys/fs/cgroup/systemd
sudo mount -t cgroup -o none,name=systemd cgroup /sys/fs/cgroup/systemd

docker pull pokroy/imu_manager:latest

cd path/to/manager
docker-compose up -d
```

After rebooting the board, the app should be running.

### Connect sensors to the board
MPU-6050 sensors can be switched between 2 different I2C addresses. So you can connect only 2 sensors to each I2C bus. And Orange Pi Zero has 2 I2C buses. So you can connect up to 4 sensors to each hub.

To connect more sensors, you can use a multiplexer like TCA9548A. If you use raspberry pi, you can simply set up more I2C buses in `boot/config.txt` file.

Either way, you need to wire the sensors to the board. And then set up the `config.yml` file to match used I2C buses and addresses. Sensor hub will scan all listed I2C buses and addresses and connect to the sensors if they are available.

## Data collection
Run the user client and connect to the broker server. If you see `Sessions` and `Sensors` sections, you are connected to the broker server.

Connected sensors should be displayed in the `Sensors` section. (You might need to press the `Refresh` button to see the sensors)

### Configure and calibrate sensors
If you run sensor managers for the first time, you need to configure the sensors. To do that, move to the `Configure sensors` tab in `Sensors` section and press the `Configure` button. This will configure all sensors to the default settings.

After configuring the sensors, you need to calibrate them. To do that, move to the `Calibrate sensors` tab in `Sensors` section and press the `Calibrate` button. This will calibrate all sensors to the default settings.

Make sure that the sensors are flat on the table and not moving during calibration.

Default calibration settings should be good enough for most applications.

### Collect
Data is collected in sessions. To start a new session, move to the `New session` tab, enter session name and duration then press the `Start session` button.

### Merge, decode and download
Each sensor hub will send its data separately. So session parts need to be merged together.

Also, sensor readings are stored in raw binary format. So they need to be decoded to human readable format.

To do that, move to the `Sessions` section, select `Manage sessionns` tab and select all sessions you want to manage. (All sessions will be selected by default) Then press `Merge` and `Decode` buttons.

Same way you can download and delete session data.
