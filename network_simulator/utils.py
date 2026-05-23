from datetime import datetime
import random

def log(layer: str, message: str):
    print(f"[{layer:<5}] {message}")


def text_to_bits(text: str) -> str:
    return ' '.join(format(ord(c), '08b') for c in str(text))


def bits_to_text(bits: str) -> str:
    cleaned = bits.replace(' ', '')
    chars = []
    for i in range(0, len(cleaned), 8):
        byte = cleaned[i:i+8]
        if len(byte) == 8:
            chars.append(chr(int(byte, 2)))
    return ''.join(chars)


def nrz_encode(text: str) -> str:
    return text_to_bits(text)


def manchester_encode(text: str) -> str:
    raw = text_to_bits(text).replace(' ', '')
    return ' '.join('10' if bit == '1' else '01' for bit in raw)


def crc16(data: str) -> str:
    crc = 0xFFFF
    for b in str(data).encode('utf-8'):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return f"0x{crc:04X}"


def verify_crc(data: str, fcs: str) -> bool:
    return crc16(data) == fcs


def generate_mac(i: int | None = None) -> str:
    if i is None:
        return 'AA:BB:CC:' + ':'.join(f'{random.randint(0,255):02X}' for _ in range(3))
    return f'AA:BB:CC:DD:EE:{i:02X}'


def random_ephemeral_port() -> int:
    return random.randint(49152, 65535)
