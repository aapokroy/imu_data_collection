from imu_manager.mpu6050 import i2c_interface


class MPU6050:
    def __init__(self, sensor_id, bus,
                 address=i2c_interface.MPU6050_DEFAULT_ADDRESS):
        self.id = sensor_id
        self.bus = bus
        self.address = address
        self._mpu6050 = i2c_interface.MPU6050_I2C(bus, address)
        self._mpu6050.set_sleep_enabled(False)
        self._mpu6050.set_fifo_enabled(True)
        self._accel_fifo_enabled = self._mpu6050.get_accel_fifo_enabled()
        self._x_gyro_fifo_enabled = self._mpu6050.get_x_gyro_fifo_enabled()
        self._y_gyro_fifo_enabled = self._mpu6050.get_y_gyro_fifo_enabled()
        self._z_gyro_fifo_enabled = self._mpu6050.get_z_gyro_fifo_enabled()
        self._dlpf_mode = self._mpu6050.get_dlpf_mode()
        self._full_scale_accel_range = self._mpu6050.get_full_scale_accel_range()
        self._full_scale_gyro_range = self._mpu6050.get_full_scale_gyro_range()
        self._clock_source = self._mpu6050.get_clock_source()
        self._rate = self._mpu6050.get_rate()
        if self._dlpf_mode == i2c_interface.MPU6050_DLPF_BW_256:
            self._gyro_output_rate = i2c_interface.MPU6050_DEFAULT_GYRO_OUTPUT_RATE
        else:
            self._gyro_output_rate = i2c_interface.MPU6050_DLPF_GYRO_OUTPUT_RATE

    @property
    def is_connected(self):
        return self._mpu6050.test_connection()

    def reset(self):
        self._mpu6050.reset()
        self._mpu6050.set_sleep_enabled(False)
        self._mpu6050.set_fifo_enabled(True)
        self._accel_fifo_enabled = False
        self._x_gyro_fifo_enabled = False
        self._y_gyro_fifo_enabled = False
        self._z_gyro_fifo_enabled = False
        self._dlpf_mode = i2c_interface.MPU6050_DLPF_BW_5
        self._full_scale_accel_range = i2c_interface.MPU6050_ACCEL_FS_2
        self._full_scale_gyro_range = i2c_interface.MPU6050_GYRO_FS_250
        self._clock_source = i2c_interface.MPU6050_CLOCK_INTERNAL
        self._rate = 0
        self._gyro_output_rate = i2c_interface.MPU6050_DEFAULT_GYRO_OUTPUT_RATE

    @staticmethod
    def accel_range_to_factor(range_):
        if range_ == i2c_interface.MPU6050_ACCEL_FS_2:
            return 2 / 32768.0
        elif range_ == i2c_interface.MPU6050_ACCEL_FS_4:
            return 4 / 32768.0
        elif range_ == i2c_interface.MPU6050_ACCEL_FS_8:
            return 8 / 32768.0
        elif range_ == i2c_interface.MPU6050_ACCEL_FS_16:
            return 16 / 32768.0

    @staticmethod
    def gyro_range_to_factor(range_):
        if range_ == i2c_interface.MPU6050_GYRO_FS_250:
            return 250 / 32768.0
        elif range_ == i2c_interface.MPU6050_GYRO_FS_500:
            return 500 / 32768.0
        elif range_ == i2c_interface.MPU6050_GYRO_FS_1000:
            return 1000 / 32768.0
        elif range_ == i2c_interface.MPU6050_GYRO_FS_2000:
            return 2000 / 32768.0

    @property
    def rate(self):
        return self._mpu6050.get_rate()

    @rate.setter
    def rate(self, rate):
        self._rate = rate
        self._mpu6050.set_rate(rate)

    @property
    def sample_rate(self):
        return self._gyro_output_rate / (1 + self._rate)

    @property
    def clock_source(self):
        return self._clock_source

    @clock_source.setter
    def clock_source(self, source):
        self._clock_source = source
        self._mpu6050.set_clock_source(source)

    @property
    def full_scale_gyro_range(self):
        return self._full_scale_gyro_range

    @full_scale_gyro_range.setter
    def full_scale_gyro_range(self, range_):
        self._full_scale_gyro_range = range_
        self._mpu6050.set_full_scale_gyro_range(range_)

    @property
    def full_scale_accel_range(self):
        return self._full_scale_accel_range

    @full_scale_accel_range.setter
    def full_scale_accel_range(self, range_):
        self._full_scale_accel_range = range_
        self._mpu6050.set_full_scale_accel_range(range_)

    @property
    def gyro_factor(self):
        return MPU6050.gyro_range_to_factor(self._full_scale_gyro_range)

    @property
    def accel_factor(self):
        return MPU6050.accel_range_to_factor(self._full_scale_accel_range)

    @property
    def dlpf_mode(self):
        return self._dlpf_mode

    @dlpf_mode.setter
    def dlpf_mode(self, mode):
        self._dlpf_mode = mode
        self._mpu6050.set_dlpf_mode(mode)
        if mode == i2c_interface.MPU6050_DLPF_BW_256:
            self._gyro_output_rate = i2c_interface.MPU6050_DEFAULT_GYRO_OUTPUT_RATE
        else:
            self._gyro_output_rate = i2c_interface.MPU6050_DLPF_GYRO_OUTPUT_RATE

    def get_temperature(self):
        t = self._mpu6050.get_temperature()
        t *= i2c_interface.MPU6050_TEMP_FACTOR
        t += i2c_interface.MPU6050_TEMP_OFFSET
        return t

    def _calibrate_axis(self, get_x, set_offset, offset_factor, max_iters,
                        rough_iters, buffer_size, epsilon, mu, v_threshold,
                        target=0):
        v = 0
        offset = 0
        set_offset(0)
        for i in range(max_iters):
            delta = sum([get_x() for i in range(buffer_size)])
            delta /= buffer_size
            delta -= target
            if i < rough_iters:
                offset += mu * v - delta
            else:
                offset += mu * v - delta * epsilon
            v = mu * v - delta * epsilon
            if abs(delta) < offset_factor and abs(v) < v_threshold:
                break
            set_offset(int(offset / offset_factor))

    def calibrate(self, max_iters, rough_iters, buffer_size,
                  epsilon=0.1, mu=0.5, v_threshold=0.05): 
        self._calibrate_axis(self._mpu6050.get_acceleration_x,
                             self._mpu6050.set_accel_offset_x,
                             i2c_interface.MPU6050_ACCEL_OFFSET_FACTOR,
                             max_iters, rough_iters, buffer_size,
                             epsilon, mu, v_threshold)
        self._calibrate_axis(self._mpu6050.get_acceleration_y,
                             self._mpu6050.set_accel_offset_y,
                             i2c_interface.MPU6050_ACCEL_OFFSET_FACTOR,
                             max_iters, rough_iters, buffer_size,
                             epsilon, mu, v_threshold)
        self._calibrate_axis(self._mpu6050.get_acceleration_z,
                             self._mpu6050.set_accel_offset_z,
                             i2c_interface.MPU6050_ACCEL_OFFSET_FACTOR,
                             max_iters, rough_iters, buffer_size,
                             epsilon, mu, v_threshold,
                             target=(1 / self.accel_factor))
        self._calibrate_axis(self._mpu6050.get_rotation_x,
                             self._mpu6050.set_gyro_offset_x,
                             i2c_interface.MPU6050_GYRO_OFFSET_FACTOR,
                             max_iters, rough_iters, buffer_size,
                             epsilon, mu, v_threshold)
        self._calibrate_axis(self._mpu6050.get_rotation_y,
                             self._mpu6050.set_gyro_offset_y,
                             i2c_interface.MPU6050_GYRO_OFFSET_FACTOR,
                             max_iters, rough_iters, buffer_size,
                             epsilon, mu, v_threshold)
        self._calibrate_axis(self._mpu6050.get_rotation_z,
                             self._mpu6050.set_gyro_offset_z,
                             i2c_interface.MPU6050_GYRO_OFFSET_FACTOR,
                             max_iters, rough_iters, buffer_size,
                             epsilon, mu, v_threshold)

    @property
    def x_gyro_fifo_enabled(self):
        return self._x_gyro_fifo_enabled

    @x_gyro_fifo_enabled.setter
    def x_gyro_fifo_enabled(self, enabled):
        self._x_gyro_fifo_enabled = enabled
        self._mpu6050.set_x_gyro_fifo_enabled(enabled)

    @property
    def y_gyro_fifo_enabled(self):
        return self._y_gyro_fifo_enabled

    @y_gyro_fifo_enabled.setter
    def y_gyro_fifo_enabled(self, enabled):
        self._y_gyro_fifo_enabled = enabled
        self._mpu6050.set_y_gyro_fifo_enabled(enabled)

    @property
    def z_gyro_fifo_enabled(self):
        return self._z_gyro_fifo_enabled

    @z_gyro_fifo_enabled.setter
    def z_gyro_fifo_enabled(self, enabled):
        self._z_gyro_fifo_enabled = enabled
        self._mpu6050.set_z_gyro_fifo_enabled(enabled)

    @property
    def accel_fifo_enabled(self):
        return self._accel_fifo_enabled

    @accel_fifo_enabled.setter
    def accel_fifo_enabled(self, enabled):
        self._accel_fifo_enabled = enabled
        self._mpu6050.set_accel_fifo_enabled(enabled)

    @property
    def package_length(self):
        package_byte_length = 0
        if self._accel_fifo_enabled:
            package_byte_length += 6
        if self._x_gyro_fifo_enabled:
            package_byte_length += 2
        if self._y_gyro_fifo_enabled:
            package_byte_length += 2
        if self._z_gyro_fifo_enabled:
            package_byte_length += 2
        return package_byte_length

    def get_fifo_count(self):
        return self._mpu6050.get_fifo_count()

    def get_fifo_byte(self):
        return self._mpu6050.get_fifo_byte()

    def get_fifo_bytes(self, length):
        return self._mpu6050.get_fifo_bytes(length)

    def reset_fifo(self):
        self._mpu6050.reset_fifo()
