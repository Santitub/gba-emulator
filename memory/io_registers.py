"""
Registros de I/O del GBA
Define todas las direcciones y máscaras de los registros
"""
from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, Tuple


class IORegister(IntEnum):
    """Direcciones de registros de I/O (offset desde 0x04000000)"""
    
    # === LCD Registers ===
    DISPCNT     = 0x000  # Display Control
    GREENSWAP   = 0x002  # Undocumented - Green Swap
    DISPSTAT    = 0x004  # Display Status
    VCOUNT      = 0x006  # Vertical Counter (LY)
    
    # Background Control
    BG0CNT      = 0x008
    BG1CNT      = 0x00A
    BG2CNT      = 0x00C
    BG3CNT      = 0x00E
    
    # Background Scroll
    BG0HOFS     = 0x010
    BG0VOFS     = 0x012
    BG1HOFS     = 0x014
    BG1VOFS     = 0x016
    BG2HOFS     = 0x018
    BG2VOFS     = 0x01A
    BG3HOFS     = 0x01C
    BG3VOFS     = 0x01E
    
    # Background Rotation/Scaling (BG2)
    BG2PA       = 0x020
    BG2PB       = 0x022
    BG2PC       = 0x024
    BG2PD       = 0x026
    BG2X        = 0x028  # 32-bit
    BG2Y        = 0x02C  # 32-bit
    
    # Background Rotation/Scaling (BG3)
    BG3PA       = 0x030
    BG3PB       = 0x032
    BG3PC       = 0x034
    BG3PD       = 0x036
    BG3X        = 0x038  # 32-bit
    BG3Y        = 0x03C  # 32-bit
    
    # Window
    WIN0H       = 0x040
    WIN1H       = 0x042
    WIN0V       = 0x044
    WIN1V       = 0x046
    WININ       = 0x048
    WINOUT      = 0x04A
    
    # Effects
    MOSAIC      = 0x04C
    BLDCNT      = 0x050
    BLDALPHA    = 0x052
    BLDY        = 0x054
    
    # === Sound Registers ===
    SOUND1CNT_L = 0x060  # Channel 1 Sweep
    SOUND1CNT_H = 0x062  # Channel 1 Duty/Length/Envelope
    SOUND1CNT_X = 0x064  # Channel 1 Frequency/Control
    SOUND2CNT_L = 0x068  # Channel 2 Duty/Length/Envelope
    SOUND2CNT_H = 0x06C  # Channel 2 Frequency/Control
    SOUND3CNT_L = 0x070  # Channel 3 Stop/Wave RAM
    SOUND3CNT_H = 0x072  # Channel 3 Length/Volume
    SOUND3CNT_X = 0x074  # Channel 3 Frequency/Control
    SOUND4CNT_L = 0x078  # Channel 4 Length/Envelope
    SOUND4CNT_H = 0x07C  # Channel 4 Frequency/Control
    SOUNDCNT_L  = 0x080  # Sound Control (mixing)
    SOUNDCNT_H  = 0x082  # Sound Control (DMA)
    SOUNDCNT_X  = 0x084  # Sound Control (master)
    SOUNDBIAS   = 0x088  # Sound PWM Control
    WAVE_RAM    = 0x090  # Wave RAM (16 bytes)
    FIFO_A      = 0x0A0  # DMA Sound A FIFO
    FIFO_B      = 0x0A4  # DMA Sound B FIFO
    
    # === DMA Registers ===
    DMA0SAD     = 0x0B0  # DMA 0 Source Address (32-bit)
    DMA0DAD     = 0x0B4  # DMA 0 Destination (32-bit)
    DMA0CNT_L   = 0x0B8  # DMA 0 Word Count
    DMA0CNT_H   = 0x0BA  # DMA 0 Control
    
    DMA1SAD     = 0x0BC
    DMA1DAD     = 0x0C0
    DMA1CNT_L   = 0x0C4
    DMA1CNT_H   = 0x0C6
    
    DMA2SAD     = 0x0C8
    DMA2DAD     = 0x0CC
    DMA2CNT_L   = 0x0D0
    DMA2CNT_H   = 0x0D2
    
    DMA3SAD     = 0x0D4
    DMA3DAD     = 0x0D8
    DMA3CNT_L   = 0x0DC
    DMA3CNT_H   = 0x0DE
    
    # === Timer Registers ===
    TM0CNT_L    = 0x100  # Timer 0 Counter/Reload
    TM0CNT_H    = 0x102  # Timer 0 Control
    TM1CNT_L    = 0x104
    TM1CNT_H    = 0x106
    TM2CNT_L    = 0x108
    TM2CNT_H    = 0x10A
    TM3CNT_L    = 0x10C
    TM3CNT_H    = 0x10E
    
    # === Serial Communication ===
    SIODATA32   = 0x120
    SIOMULTI0   = 0x120
    SIOMULTI1   = 0x122
    SIOMULTI2   = 0x124
    SIOMULTI3   = 0x126
    SIOCNT      = 0x128
    SIOMLT_SEND = 0x12A
    SIODATA8    = 0x12A
    
    # === Keypad ===
    KEYINPUT    = 0x130  # Key Status (Read-Only)
    KEYCNT      = 0x132  # Key Interrupt Control
    
    # === Serial (cont) ===
    RCNT        = 0x134  # SIO Mode Select
    JOYCNT      = 0x140  # JOY Bus Control
    JOY_RECV    = 0x150  # JOY Bus Receive
    JOY_TRANS   = 0x154  # JOY Bus Transmit
    JOYSTAT     = 0x158  # JOY Bus Status
    
    # === Interrupt/System ===
    IE          = 0x200  # Interrupt Enable
    IF          = 0x202  # Interrupt Flags
    WAITCNT     = 0x204  # Wait State Control
    IME         = 0x208  # Interrupt Master Enable
    
    POSTFLG     = 0x300  # Post Boot Flag
    HALTCNT     = 0x301  # Halt Control (Write-Only)


@dataclass
class RegisterInfo:
    """Información sobre un registro de I/O"""
    name: str
    size: int          # 1, 2, o 4 bytes
    readable: bool
    writable: bool
    read_mask: int     # Bits legibles
    write_mask: int    # Bits escribibles


# Definición de registros con sus propiedades
IO_REGISTER_INFO: Dict[int, RegisterInfo] = {
    # LCD
    IORegister.DISPCNT:   RegisterInfo("DISPCNT",   2, True,  True,  0xFFFF, 0xFFF7),
    IORegister.DISPSTAT:  RegisterInfo("DISPSTAT",  2, True,  True,  0xFFFF, 0xFF38),
    IORegister.VCOUNT:    RegisterInfo("VCOUNT",    2, True,  False, 0x00FF, 0x0000),
    
    # BG Control
    IORegister.BG0CNT:    RegisterInfo("BG0CNT",    2, True,  True,  0xDFFF, 0xDFFF),
    IORegister.BG1CNT:    RegisterInfo("BG1CNT",    2, True,  True,  0xDFFF, 0xDFFF),
    IORegister.BG2CNT:    RegisterInfo("BG2CNT",    2, True,  True,  0xFFFF, 0xFFFF),
    IORegister.BG3CNT:    RegisterInfo("BG3CNT",    2, True,  True,  0xFFFF, 0xFFFF),
    
    # BG Scroll (Write-Only)
    IORegister.BG0HOFS:   RegisterInfo("BG0HOFS",   2, False, True,  0x0000, 0x01FF),
    IORegister.BG0VOFS:   RegisterInfo("BG0VOFS",   2, False, True,  0x0000, 0x01FF),
    IORegister.BG1HOFS:   RegisterInfo("BG1HOFS",   2, False, True,  0x0000, 0x01FF),
    IORegister.BG1VOFS:   RegisterInfo("BG1VOFS",   2, False, True,  0x0000, 0x01FF),
    IORegister.BG2HOFS:   RegisterInfo("BG2HOFS",   2, False, True,  0x0000, 0x01FF),
    IORegister.BG2VOFS:   RegisterInfo("BG2VOFS",   2, False, True,  0x0000, 0x01FF),
    IORegister.BG3HOFS:   RegisterInfo("BG3HOFS",   2, False, True,  0x0000, 0x01FF),
    IORegister.BG3VOFS:   RegisterInfo("BG3VOFS",   2, False, True,  0x0000, 0x01FF),
    
    # Window
    IORegister.WIN0H:     RegisterInfo("WIN0H",     2, False, True,  0x0000, 0xFFFF),
    IORegister.WIN1H:     RegisterInfo("WIN1H",     2, False, True,  0x0000, 0xFFFF),
    IORegister.WIN0V:     RegisterInfo("WIN0V",     2, False, True,  0x0000, 0xFFFF),
    IORegister.WIN1V:     RegisterInfo("WIN1V",     2, False, True,  0x0000, 0xFFFF),
    IORegister.WININ:     RegisterInfo("WININ",     2, True,  True,  0x3F3F, 0x3F3F),
    IORegister.WINOUT:    RegisterInfo("WINOUT",    2, True,  True,  0x3F3F, 0x3F3F),
    
    # Effects
    IORegister.MOSAIC:    RegisterInfo("MOSAIC",    2, False, True,  0x0000, 0xFFFF),
    IORegister.BLDCNT:    RegisterInfo("BLDCNT",    2, True,  True,  0x3FFF, 0x3FFF),
    IORegister.BLDALPHA:  RegisterInfo("BLDALPHA",  2, True,  True,  0x1F1F, 0x1F1F),
    IORegister.BLDY:      RegisterInfo("BLDY",      2, False, True,  0x0000, 0x001F),
    
    # Sound
    IORegister.SOUNDCNT_L: RegisterInfo("SOUNDCNT_L", 2, True, True, 0xFF77, 0xFF77),
    IORegister.SOUNDCNT_H: RegisterInfo("SOUNDCNT_H", 2, True, True, 0x770F, 0xFF0F),
    IORegister.SOUNDCNT_X: RegisterInfo("SOUNDCNT_X", 2, True, True, 0x008F, 0x0080),
    IORegister.SOUNDBIAS:  RegisterInfo("SOUNDBIAS",  2, True, True, 0xC3FE, 0xC3FE),
    
    # DMA (ejemplo para DMA0)
    IORegister.DMA0CNT_H: RegisterInfo("DMA0CNT_H", 2, True, True, 0xFFE0, 0xFFE0),
    IORegister.DMA1CNT_H: RegisterInfo("DMA1CNT_H", 2, True, True, 0xFFE0, 0xFFE0),
    IORegister.DMA2CNT_H: RegisterInfo("DMA2CNT_H", 2, True, True, 0xFFE0, 0xFFE0),
    IORegister.DMA3CNT_H: RegisterInfo("DMA3CNT_H", 2, True, True, 0xFFFF, 0xFFFF),
    
    # Timers
    IORegister.TM0CNT_L:  RegisterInfo("TM0CNT_L",  2, True,  True,  0xFFFF, 0xFFFF),
    IORegister.TM0CNT_H:  RegisterInfo("TM0CNT_H",  2, True,  True,  0x00C7, 0x00C7),
    IORegister.TM1CNT_L:  RegisterInfo("TM1CNT_L",  2, True,  True,  0xFFFF, 0xFFFF),
    IORegister.TM1CNT_H:  RegisterInfo("TM1CNT_H",  2, True,  True,  0x00C7, 0x00C7),
    IORegister.TM2CNT_L:  RegisterInfo("TM2CNT_L",  2, True,  True,  0xFFFF, 0xFFFF),
    IORegister.TM2CNT_H:  RegisterInfo("TM2CNT_H",  2, True,  True,  0x00C7, 0x00C7),
    IORegister.TM3CNT_L:  RegisterInfo("TM3CNT_L",  2, True,  True,  0xFFFF, 0xFFFF),
    IORegister.TM3CNT_H:  RegisterInfo("TM3CNT_H",  2, True,  True,  0x00C7, 0x00C7),
    
    # Keypad
    IORegister.KEYINPUT:  RegisterInfo("KEYINPUT",  2, True,  False, 0x03FF, 0x0000),
    IORegister.KEYCNT:    RegisterInfo("KEYCNT",    2, True,  True,  0xC3FF, 0xC3FF),
    
    # Interrupts
    IORegister.IE:        RegisterInfo("IE",        2, True,  True,  0x3FFF, 0x3FFF),
    IORegister.IF:        RegisterInfo("IF",        2, True,  True,  0x3FFF, 0x3FFF),
    IORegister.WAITCNT:   RegisterInfo("WAITCNT",   2, True,  True,  0xDFFF, 0xDFFF),
    IORegister.IME:       RegisterInfo("IME",       2, True,  True,  0x0001, 0x0001),
    
    # System
    IORegister.POSTFLG:   RegisterInfo("POSTFLG",   1, True,  True,  0x01,   0x01),
    IORegister.HALTCNT:   RegisterInfo("HALTCNT",   1, False, True,  0x00,   0x80),
}


class InterruptFlags(IntEnum):
    """Bits del registro IF/IE"""
    VBLANK     = 0x0001
    HBLANK     = 0x0002
    VCOUNT     = 0x0004
    TIMER0     = 0x0008
    TIMER1     = 0x0010
    TIMER2     = 0x0020
    TIMER3     = 0x0040
    SERIAL     = 0x0080
    DMA0       = 0x0100
    DMA1       = 0x0200
    DMA2       = 0x0400
    DMA3       = 0x0800
    KEYPAD     = 0x1000
    GAMEPAK    = 0x2000


class KeyInput(IntEnum):
    """Bits del registro KEYINPUT (activo bajo)"""
    A      = 0x0001
    B      = 0x0002
    SELECT = 0x0004
    START  = 0x0008
    RIGHT  = 0x0010
    LEFT   = 0x0020
    UP     = 0x0040
    DOWN   = 0x0080
    R      = 0x0100
    L      = 0x0200