"""MPU6050 byte decrpytion constants"""


DLPF_ENUM = {
    '256': 0,
    '188': 1,
    '98': 2,
    '42': 3,
    '20': 4,
    '10': 5,
    '5': 6
}

CLOCK_ENUM = {
    'internal': 0,
    'pll xgyro': 1,
    'pll ygyro': 2,
    'pll zgyro': 3,
    'pll ext32k': 4,
    'pll ext19m': 5,
    'keep reset': 7
}

GYRO_RANGE_ENUM = {
    '±250 Â°/s': 0,
    '±500 Â°/s': 1,
    '±1000 Â°/s': 2,
    '±2000 Â°/s': 3
}

ACCEL_RANGE_ENUM = {
    '±2g': 0,
    '±4g': 1,
    '±8g': 2,
    '±16g': 3
}
