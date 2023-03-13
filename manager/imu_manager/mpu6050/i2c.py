from typing import Literal, List

from smbus2 import SMBus


def write_bit(bus: SMBus, address: int, reg: int, bit: int,
              value: Literal[0, 1]):
    if bit > 7 or bit < 0:
        raise IndexError('"bit" index is out of range')
    if value > 1 or value < 0:
        raise ValueError('"value" must be equal to 1 or 0')
    byte = bus.read_byte_data(address, reg)
    if value:
        byte |= (1 << bit)
    else:
        byte &= ~(1 << bit)
    bus.write_byte_data(address, reg, byte)


def write_bits(bus: SMBus, address: int, reg: int, bit: int,
               length: int, value: int):
    if bit > 7 or bit < 0:
        raise IndexError('"bit" index is out of range')
    if length > bit + 1:
        raise IndexError('bit sequence is to long')
    if value >= 2**length:
        raise ValueError('"value" binary notation must be lesser then "length"')
    if value < 0:
        raise ValueError('"value" must be greater or equal to 0')
    clear_mask = (2**(bit + 1) - 1) ^ (2**(bit - length + 1) - 1)
    byte = bus.read_byte_data(address, reg)
    byte = byte ^ (byte & clear_mask)
    byte |= value << (bit - length + 1)
    bus.write_byte_data(address, reg, byte)


def write_byte(bus: SMBus, address: int, reg: int, value: int):
    bus.write_byte_data(address, reg, value)


def write_word(bus: SMBus, address: int, reg: int, value: int):
    if value < 0:
        raise ValueError('"value" must be greater or equal to 0')
    bus.write_byte_data(address, reg, value >> 8)
    bus.write_byte_data(address, reg + 1, value % 256)


def write_signed_word(bus: SMBus, address: int, reg: int, value: int):
    if value < 0:
        value = -((-value - 1) - 65535)
    bus.write_byte_data(address, reg, value >> 8)
    bus.write_byte_data(address, reg + 1, value % 256)


def read_bit(bus: SMBus, address: int, reg: int, bit: int) -> Literal[0, 1]:
    if bit > 7 or bit < 0:
        raise IndexError('"bit" index is out of range')
    byte = bus.read_byte_data(address, reg)
    result = (byte & (1 << bit)) >> bit
    return result


def read_bits(bus: SMBus, address: int, reg: int, bit: int,
              length: int) -> int:
    if bit > 7 or bit < 0:
        raise IndexError('"bit" index is out of range')
    if length > bit + 1:
        raise IndexError('bit sequence is to long')
    byte = bus.read_byte_data(address, reg)
    mask = 2**(bit + 1) - 1
    result = (byte & mask) >> (bit - length + 1)
    return result


def read_byte(bus: SMBus, address: int, reg: int) -> int:
    result = bus.read_byte_data(address, reg)
    return result


def read_word(bus: SMBus, address: int, reg: int) -> int:
    buffer = bus.read_i2c_block_data(address, reg, 2)
    result = (buffer[0] << 8) + buffer[1]
    return result


def read_signed_word(bus: SMBus, address: int, reg: int) -> int:
    result = read_word(bus, address, reg)
    if (result >= 0x8000):
        return -((65535 - result) + 1)
    else:
        return result


def write_bytes(bus: SMBus, address: int, reg: int, values: List[int]):
    bus.write_i2c_block_data(address, reg, values)


def read_bytes(bus: SMBus, address: int, reg: int, length: int) -> List[int]:
    result = bus.read_i2c_block_data(address, reg, length)
    return result
