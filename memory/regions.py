"""Definición de regiones de memoria del GBA"""
from dataclasses import dataclass
from enum import IntEnum

class MemoryRegion(IntEnum):
    """Regiones de memoria del GBA"""
    BIOS_START      = 0x00000000
    BIOS_END        = 0x00003FFF
    BIOS_SIZE       = 0x00004000  # 16 KB
    
    EWRAM_START     = 0x02000000
    EWRAM_END       = 0x0203FFFF
    EWRAM_SIZE      = 0x00040000  # 256 KB
    
    IWRAM_START     = 0x03000000
    IWRAM_END       = 0x00007FFF
    IWRAM_SIZE      = 0x00008000  # 32 KB
    
    IO_START        = 0x04000000
    IO_END          = 0x040003FE
    IO_SIZE         = 0x00000400  # 1 KB
    
    PALETTE_START   = 0x05000000
    PALETTE_END     = 0x050003FF
    PALETTE_SIZE    = 0x00000400  # 1 KB
    
    VRAM_START      = 0x06000000
    VRAM_END        = 0x06017FFF
    VRAM_SIZE       = 0x00018000  # 96 KB
    
    OAM_START       = 0x07000000
    OAM_END         = 0x070003FF
    OAM_SIZE        = 0x00000400  # 1 KB
    
    ROM_START       = 0x08000000
    ROM_END         = 0x09FFFFFF
    ROM_SIZE        = 0x02000000  # 32 MB máximo
    
    SRAM_START      = 0x0E000000
    SRAM_END        = 0x0E00FFFF
    SRAM_SIZE       = 0x00010000  # 64 KB

@dataclass
class MemoryTiming:
    """Tiempos de acceso a memoria (en ciclos)"""
    n_cycles: int  # Accesos no secuenciales
    s_cycles: int  # Accesos secuenciales

# Tiempos de acceso por región
MEMORY_TIMINGS = {
    'BIOS':    MemoryTiming(1, 1),
    'EWRAM':   MemoryTiming(3, 3),
    'IWRAM':   MemoryTiming(1, 1),
    'IO':      MemoryTiming(1, 1),
    'PALETTE': MemoryTiming(1, 1),
    'VRAM':    MemoryTiming(1, 1),
    'OAM':     MemoryTiming(1, 1),
    'ROM_WS0': MemoryTiming(4, 2),  # Wait State 0
    'ROM_WS1': MemoryTiming(4, 4),  # Wait State 1
    'ROM_WS2': MemoryTiming(4, 8),  # Wait State 2
    'SRAM':    MemoryTiming(4, 4),
}