"""Funciones auxiliares para el emulador GBA"""

def sign_extend(value: int, bits: int) -> int:
    """Extiende el signo de un valor de N bits a 32 bits"""
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)

def rotate_right(value: int, amount: int, bits: int = 32) -> int:
    """Rotación a la derecha"""
    amount %= bits
    mask = (1 << bits) - 1
    return ((value >> amount) | (value << (bits - amount))) & mask

def arithmetic_shift_right(value: int, amount: int, bits: int = 32) -> int:
    """Desplazamiento aritmético a la derecha (preserva signo)"""
    if amount == 0:
        return value
    sign = value >> (bits - 1)
    mask = (1 << bits) - 1
    result = value >> amount
    if sign:
        result |= (((1 << amount) - 1) << (bits - amount))
    return result & mask

def get_bit(value: int, bit: int) -> int:
    """Obtiene un bit específico"""
    return (value >> bit) & 1

def set_bit(value: int, bit: int, state: bool) -> int:
    """Establece un bit específico"""
    if state:
        return value | (1 << bit)
    return value & ~(1 << bit)

def get_bits(value: int, start: int, end: int) -> int:
    """Obtiene un rango de bits [start, end]"""
    mask = (1 << (end - start + 1)) - 1
    return (value >> start) & mask

def to_signed_32(value: int) -> int:
    """Convierte a entero con signo de 32 bits"""
    if value >= 0x80000000:
        return value - 0x100000000
    return value

def to_unsigned_32(value: int) -> int:
    """Convierte a entero sin signo de 32 bits"""
    return value & 0xFFFFFFFF