"""
Bus de memoria principal del GBA - Versión completa
"""
import numpy as np
from typing import Optional, TYPE_CHECKING, Callable
from .regions import MemoryRegion as MR
from .io_registers import IORegister, IO_REGISTER_INFO, InterruptFlags
from typing import TYPE_CHECKING, Optional
from memory.io_registers import IORegister

if TYPE_CHECKING:
    from ppu.ppu import PPU
    from apu.apu import APU
    from hw.dma import DMAController
    from hw.timers import TimerController


class MemoryBus:
    """
    Bus de memoria del GBA
    Maneja todas las lecturas y escrituras de memoria
    """
    
    def __init__(self):
        # ===== Regiones de memoria =====
        self.bios = np.zeros(0x4000, dtype=np.uint8)       # 16 KB
        self.ewram = np.zeros(0x40000, dtype=np.uint8)     # 256 KB
        self.iwram = np.zeros(0x8000, dtype=np.uint8)      # 32 KB
        self.palette_ram = np.zeros(0x400, dtype=np.uint8) # 1 KB
        self.vram = np.zeros(0x18000, dtype=np.uint8)      # 96 KB
        self.oam = np.zeros(0x400, dtype=np.uint8)         # 1 KB
        self.rom = np.zeros(0, dtype=np.uint8)             # Variable
        self.sram = np.zeros(0x10000, dtype=np.uint8)      # 64 KB
        
        # ===== Registros de I/O =====
        self.io_registers = np.zeros(0x400, dtype=np.uint8)
        
        # ===== Estado interno =====
        self.bios_readable = True
        self.last_bios_read = 0
        
        # Valor de "open bus" (última lectura del bus)
        self.open_bus_value = 0
        
        # ===== Wait State Control =====
        self.waitcnt = 0
        self.sram_wait = 4
        self.ws0_nonseq = 4
        self.ws0_seq = 2
        self.ws1_nonseq = 4
        self.ws1_seq = 4
        self.ws2_nonseq = 4
        self.ws2_seq = 8
        self.prefetch_enabled = False
        
        # ===== Referencias a componentes =====
        self.cpu = None
        self.ppu = None
        self.apu = None
        self.dma = None
        self.timers = None
        
        # ===== Input =====
        self.key_state = 0x03FF  # Todos los botones sueltos (activo bajo)
        
        # ===== Callbacks para escrituras especiales =====
        self._io_write_handlers: dict = {}
        self._io_read_handlers: dict = {}
        
        self._setup_io_handlers()

        self.ppu: Optional['PPU'] = None

        self.timers: Optional['TimerController'] = None
        self.dma: Optional['DMAController'] = None
    
    def _setup_io_handlers(self) -> None:
        """Configura handlers para registros especiales"""
        # Handlers de escritura
        self._io_write_handlers = {
            IORegister.DISPSTAT: self._write_dispstat,
            IORegister.IF: self._write_if,
            IORegister.WAITCNT: self._write_waitcnt,
            IORegister.HALTCNT: self._write_haltcnt,
            IORegister.DMA0CNT_H: lambda v: self._write_dma_control(0, v),
            IORegister.DMA1CNT_H: lambda v: self._write_dma_control(1, v),
            IORegister.DMA2CNT_H: lambda v: self._write_dma_control(2, v),
            IORegister.DMA3CNT_H: lambda v: self._write_dma_control(3, v),
            IORegister.TM0CNT_H: lambda v: self._write_timer_control(0, v),
            IORegister.TM1CNT_H: lambda v: self._write_timer_control(1, v),
            IORegister.TM2CNT_H: lambda v: self._write_timer_control(2, v),
            IORegister.TM3CNT_H: lambda v: self._write_timer_control(3, v),
            IORegister.FIFO_A: self._write_fifo_a,
            IORegister.FIFO_B: self._write_fifo_b,
        }
        
        # Handlers de lectura
        self._io_read_handlers = {
            IORegister.KEYINPUT: self._read_keyinput,
            IORegister.VCOUNT: self._read_vcount,
            IORegister.DISPSTAT: self._read_dispstat,
            IORegister.TM0CNT_L: lambda: self._read_timer_counter(0),
            IORegister.TM1CNT_L: lambda: self._read_timer_counter(1),
            IORegister.TM2CNT_L: lambda: self._read_timer_counter(2),
            IORegister.TM3CNT_L: lambda: self._read_timer_counter(3),
        }
    
    # ===== Carga de datos =====
    
    def load_bios(self, data: bytes) -> None:
        """Carga el BIOS del GBA"""
        size = min(len(data), 0x4000)
        self.bios[:size] = np.frombuffer(data[:size], dtype=np.uint8)
        print(f"BIOS cargado: {size} bytes")
        
    def load_rom(self, data: bytes) -> None:
        """Carga una ROM de GBA"""
        self.rom = np.frombuffer(data, dtype=np.uint8).copy()
        size_mb = len(self.rom) / 1024 / 1024
        print(f"ROM cargada: {len(self.rom)} bytes ({size_mb:.2f} MB)")
        
        # Detectar tipo de guardado
        self._detect_save_type()
    
    def load_save(self, data: bytes) -> None:
        """Carga datos de guardado"""
        size = min(len(data), len(self.sram))
        self.sram[:size] = np.frombuffer(data[:size], dtype=np.uint8)
        print(f"Save cargado: {size} bytes")
    
    def get_save_data(self) -> bytes:
        """Obtiene los datos de guardado actuales"""
        return bytes(self.sram)
    
    def _detect_save_type(self) -> None:
        """Detecta el tipo de guardado buscando strings en la ROM"""
        rom_str = bytes(self.rom).decode('ascii', errors='ignore')
        
        if 'EEPROM_V' in rom_str:
            print("  Tipo de guardado: EEPROM")
        elif 'SRAM_V' in rom_str:
            print("  Tipo de guardado: SRAM")
        elif 'FLASH_V' in rom_str or 'FLASH512_V' in rom_str:
            print("  Tipo de guardado: Flash 64KB")
        elif 'FLASH1M_V' in rom_str:
            print("  Tipo de guardado: Flash 128KB")
        else:
            print("  Tipo de guardado: No detectado (asumiendo SRAM)")
    
    # ===== Acceso a memoria =====
    
    def read_8(self, address: int) -> int:
        """Lee un byte"""
        address &= 0xFFFFFFFF
        region = (address >> 24) & 0xFF
        
        # BIOS
        if region == 0x00:
            if address < 0x4000:
                if self.bios_readable:
                    value = int(self.bios[address])
                    self.last_bios_read = value
                    return value
                return (self.last_bios_read >> ((address & 3) * 8)) & 0xFF
            return 0
        
        # EWRAM
        elif region == 0x02:
            return int(self.ewram[address & 0x3FFFF])
        
        # IWRAM
        elif region == 0x03:
            return int(self.iwram[address & 0x7FFF])
        
        # I/O
        elif region == 0x04:
            return self._read_io(address & 0x3FF)
        
        # Palette
        elif region == 0x05:
            return int(self.palette_ram[address & 0x3FF])
        
        # VRAM
        elif region == 0x06:
            addr = address & 0x1FFFF
            if addr >= 0x18000:
                addr -= 0x8000
            return int(self.vram[addr])
        
        # OAM
        elif region == 0x07:
            return int(self.oam[address & 0x3FF])
        
        # ROM
        elif 0x08 <= region <= 0x0D:
            rom_addr = address & 0x01FFFFFF
            if rom_addr < len(self.rom):
                return int(self.rom[rom_addr])
            return (rom_addr >> 1) & 0xFF  # Open bus para ROM no mapeada
        
        # SRAM
        elif region == 0x0E or region == 0x0F:
            return int(self.sram[address & 0xFFFF])
        
        return 0
    
    def read_16(self, address: int) -> int:
        """Lee una halfword (16 bits)"""
        address &= ~1
        region = (address >> 24) & 0xFF
        
        # Acceso rápido para regiones comunes
        if region == 0x02:  # EWRAM
            addr = address & 0x3FFFF
            return int(self.ewram[addr]) | (int(self.ewram[addr + 1]) << 8)
        
        elif region == 0x03:  # IWRAM
            addr = address & 0x7FFF
            return int(self.iwram[addr]) | (int(self.iwram[addr + 1]) << 8)
        
        elif region == 0x06:  # VRAM
            addr = address & 0x1FFFF
            if addr >= 0x18000:
                addr -= 0x8000
            return int(self.vram[addr]) | (int(self.vram[addr + 1]) << 8)
        
        elif 0x08 <= region <= 0x0D:  # ROM
            rom_addr = address & 0x01FFFFFF
            if rom_addr + 1 < len(self.rom):
                return int(self.rom[rom_addr]) | (int(self.rom[rom_addr + 1]) << 8)
        
        # Fallback
        return self.read_8(address) | (self.read_8(address + 1) << 8)
    
    def read_32(self, address: int) -> int:
        """Lee una word (32 bits)"""
        address &= ~3
        region = (address >> 24) & 0xFF
        
        # Acceso rápido para regiones comunes
        if region == 0x02:  # EWRAM
            addr = address & 0x3FFFF
            return (int(self.ewram[addr]) | 
                   (int(self.ewram[addr + 1]) << 8) |
                   (int(self.ewram[addr + 2]) << 16) |
                   (int(self.ewram[addr + 3]) << 24))
        
        elif region == 0x03:  # IWRAM
            addr = address & 0x7FFF
            return (int(self.iwram[addr]) | 
                   (int(self.iwram[addr + 1]) << 8) |
                   (int(self.iwram[addr + 2]) << 16) |
                   (int(self.iwram[addr + 3]) << 24))
        
        elif 0x08 <= region <= 0x0D:  # ROM
            rom_addr = address & 0x01FFFFFF
            if rom_addr + 3 < len(self.rom):
                return (int(self.rom[rom_addr]) | 
                       (int(self.rom[rom_addr + 1]) << 8) |
                       (int(self.rom[rom_addr + 2]) << 16) |
                       (int(self.rom[rom_addr + 3]) << 24))
        
        # Fallback
        return (self.read_8(address) | 
               (self.read_8(address + 1) << 8) |
               (self.read_8(address + 2) << 16) |
               (self.read_8(address + 3) << 24))
    
    def write_8(self, address: int, value: int) -> None:
        """Escribe un byte"""
        value &= 0xFF
        address &= 0xFFFFFFFF
        region = (address >> 24) & 0xFF
        
        # EWRAM
        if region == 0x02:
            self.ewram[address & 0x3FFFF] = value
        
        # IWRAM
        elif region == 0x03:
            self.iwram[address & 0x7FFF] = value
        
        # I/O
        elif region == 0x04:
            self._write_io(address & 0x3FF, value)
        
        # Palette (escritura de 8 bits escribe el mismo byte dos veces)
        elif region == 0x05:
            addr = address & 0x3FE
            self.palette_ram[addr] = value
            self.palette_ram[addr + 1] = value
        
        # VRAM (comportamiento especial para 8 bits)
        elif region == 0x06:
            addr = address & 0x1FFFE
            if addr >= 0x18000:
                addr -= 0x8000
            # Solo BG VRAM acepta escrituras de 8 bits
            if addr < 0x10000:
                self.vram[addr] = value
                self.vram[addr + 1] = value
        
        # OAM no acepta escrituras de 8 bits
        
        # SRAM
        elif region == 0x0E or region == 0x0F:
            self.sram[address & 0xFFFF] = value
    
    def write_16(self, address: int, value: int) -> None:
        """Escribe una halfword (16 bits)"""
        value &= 0xFFFF
        address &= ~1
        region = (address >> 24) & 0xFF
        
        if region == 0x02:  # EWRAM
            addr = address & 0x3FFFF
            self.ewram[addr] = value & 0xFF
            self.ewram[addr + 1] = (value >> 8) & 0xFF
        
        elif region == 0x03:  # IWRAM
            addr = address & 0x7FFF
            self.iwram[addr] = value & 0xFF
            self.iwram[addr + 1] = (value >> 8) & 0xFF
        
        elif region == 0x04:  # I/O
            addr = address & 0x3FF
            # Caso especial para IF - escribir 1 limpia el bit
            if addr == IORegister.IF:
                # IMPORTANTE: convertir a int de Python para evitar overflow de numpy
                current = int(self.io_registers[IORegister.IF]) | (int(self.io_registers[IORegister.IF + 1]) << 8)
                new_value = current & (~value & 0xFFFF)
                self.io_registers[IORegister.IF] = new_value & 0xFF
                self.io_registers[IORegister.IF + 1] = (new_value >> 8) & 0xFF
                return
            
            self._write_io(addr, value & 0xFF)
            self._write_io(addr + 1, (value >> 8) & 0xFF)
        
        elif region == 0x05:  # Palette
            addr = address & 0x3FF
            self.palette_ram[addr] = value & 0xFF
            self.palette_ram[addr + 1] = (value >> 8) & 0xFF
        
        elif region == 0x06:  # VRAM
            addr = address & 0x1FFFF
            if addr >= 0x18000:
                addr -= 0x8000
            self.vram[addr] = value & 0xFF
            self.vram[addr + 1] = (value >> 8) & 0xFF
        
        elif region == 0x07:  # OAM
            addr = address & 0x3FF
            self.oam[addr] = value & 0xFF
            self.oam[addr + 1] = (value >> 8) & 0xFF
        
        elif region == 0x0E or region == 0x0F:  # SRAM
            addr = address & 0xFFFF
            self.sram[addr] = value & 0xFF
    
    def write_32(self, address: int, value: int) -> None:
        """Escribe una word (32 bits)"""
        value &= 0xFFFFFFFF
        address &= ~3
        
        self.write_16(address, value & 0xFFFF)
        self.write_16(address + 2, (value >> 16) & 0xFFFF)
    
    # ===== I/O Handlers =====
    
    def _read_io(self, address: int) -> int:
        """Lee un registro de I/O"""
        # Verificar si hay handler para este registro o su base (para registros de 16 bits)
        base_addr = address & ~1
        
        if base_addr in self._io_read_handlers:
            val16 = self._io_read_handlers[base_addr]()
            if address & 1:  # Byte alto
                return (val16 >> 8) & 0xFF
            else:  # Byte bajo
                return val16 & 0xFF
        
        # Handler específico para este byte
        if address in self._io_read_handlers:
            return self._io_read_handlers[address]() & 0xFF
        
        # Lectura normal del array
        if address < len(self.io_registers):
            return int(self.io_registers[address])
        
        return 0
    
    def _write_io(self, address: int, value: int) -> None:
        """Escribe un registro de I/O"""
        if address >= len(self.io_registers):
            return
        
        # Caso especial para IF - escribir 1 limpia el bit
        if address == IORegister.IF or address == IORegister.IF + 1:
            current = int(self.io_registers[address])  # Convertir a int Python
            self.io_registers[address] = current & (~value & 0xFF)
            return
        
        # Guardar valor normalmente
        self.io_registers[address] = value
        
        # Handler especial
        base_addr = address & ~1
        if base_addr in self._io_write_handlers and base_addr != IORegister.IF:
            val16 = int(self.io_registers[base_addr]) | (int(self.io_registers[base_addr + 1]) << 8)
            self._io_write_handlers[base_addr](val16)
    
    # ===== Handlers específicos =====
    
    def _read_keyinput(self) -> int:
        """Lee el estado de los botones"""
        return self.key_state
    
    def _read_vcount(self) -> int:
        """Lee el contador vertical (scanline actual)"""
        if self.ppu:
            return self.ppu.vcount
        return int(self.io_registers[0x06])

    def _read_dispstat(self) -> int:
        """Lee DISPSTAT"""
        if self.ppu:
            return self.ppu.dispstat
        return int(self.io_registers[0x04]) | (int(self.io_registers[0x05]) << 8)
    
    def _read_timer_counter(self, timer_id: int) -> int:
        """Lee el contador actual de un timer"""
        if self.timers:
            return self.timers.get_counter(timer_id)
        base = 0x100 + timer_id * 4
        return int(self.io_registers[base]) | (int(self.io_registers[base + 1]) << 8)
    
    def _write_dispstat(self, value: int) -> None:
        """Escribe DISPSTAT"""
        if self.ppu:
            self.ppu.write_dispstat(value)
    
    def _write_if(self, value: int) -> None:
        """Escribe IF (acknowledge interrupts)"""
        # Escribir 1 limpia el bit
        current = self.io_registers[IORegister.IF] | (self.io_registers[IORegister.IF + 1] << 8)
        new_value = current & ~value
        self.io_registers[IORegister.IF] = new_value & 0xFF
        self.io_registers[IORegister.IF + 1] = (new_value >> 8) & 0xFF
    
    def _write_waitcnt(self, value: int) -> None:
        """Actualiza configuración de wait states"""
        self.waitcnt = value
        
        # SRAM wait cycles
        sram_waits = [4, 3, 2, 8]
        self.sram_wait = sram_waits[value & 3]
        
        # Wait State 0
        ws0_n = [4, 3, 2, 8]
        ws0_s = [2, 1]
        self.ws0_nonseq = ws0_n[(value >> 2) & 3]
        self.ws0_seq = ws0_s[(value >> 4) & 1]
        
        # Wait State 1
        ws1_n = [4, 3, 2, 8]
        ws1_s = [4, 1]
        self.ws1_nonseq = ws1_n[(value >> 5) & 3]
        self.ws1_seq = ws1_s[(value >> 7) & 1]
        
        # Wait State 2
        ws2_n = [4, 3, 2, 8]
        ws2_s = [8, 1]
        self.ws2_nonseq = ws2_n[(value >> 8) & 3]
        self.ws2_seq = ws2_s[(value >> 10) & 1]
        
        # Prefetch
        self.prefetch_enabled = bool(value & (1 << 14))
    
    def _write_haltcnt(self, value: int) -> None:
        """Escribe HALTCNT (halt/stop)"""
        if self.cpu:
            if value & 0x80:
                self.cpu.stop()
            else:
                self.cpu.halt()
    
    def _write_dma_control(self, channel: int, value: int) -> None:
        """Escribe control de DMA"""
        if self.dma:
            self.dma.write_control(channel, value)
    
    def _write_timer_control(self, timer_id: int, value: int) -> None:
        """Escribe control de timer"""
        if self.timers:
            self.timers.write_control(timer_id, value)
    
    def _write_fifo_a(self, value: int) -> None:
        """Escribe al FIFO de sonido A"""
        if self.apu:
            self.apu.write_fifo_a(value)
    
    def _write_fifo_b(self, value: int) -> None:
        """Escribe al FIFO de sonido B"""
        if self.apu:
            self.apu.write_fifo_b(value)
    
    # ===== Interrupts =====
    
    def request_interrupt(self, flag: int) -> None:
        """Solicita una interrupción"""
        current = self.io_registers[IORegister.IF] | (self.io_registers[IORegister.IF + 1] << 8)
        new_value = current | flag
        self.io_registers[IORegister.IF] = new_value & 0xFF
        self.io_registers[IORegister.IF + 1] = (new_value >> 8) & 0xFF
        
        self._check_interrupts()
    
    def _check_interrupts(self) -> None:
        """Verifica si hay interrupciones pendientes"""
        ime = self.io_registers[IORegister.IME] & 1
        ie = self.io_registers[IORegister.IE] | (self.io_registers[IORegister.IE + 1] << 8)
        if_reg = self.io_registers[IORegister.IF] | (self.io_registers[IORegister.IF + 1] << 8)
        
        if ime and (ie & if_reg):
            if self.cpu:
                self.cpu.trigger_irq()
    
    # ===== Input =====
    
    def set_key_state(self, key: int, pressed: bool) -> None:
        """Establece el estado de una tecla"""
        if pressed:
            self.key_state &= ~key  # Activo bajo
        else:
            self.key_state |= key
        
        # Verificar interrupción de keypad
        # IMPORTANTE: convertir a int de Python para evitar overflow de numpy
        keycnt = int(self.io_registers[IORegister.KEYCNT]) | (int(self.io_registers[IORegister.KEYCNT + 1]) << 8)
        
        if keycnt & 0x4000:  # IRQ enable
            keys_for_irq = keycnt & 0x03FF
            pressed_keys = (~self.key_state) & 0x03FF
            
            if keycnt & 0x8000:  # AND mode
                if (pressed_keys & keys_for_irq) == keys_for_irq:
                    self.request_interrupt(InterruptFlags.KEYPAD)
            else:  # OR mode
                if pressed_keys & keys_for_irq:
                    self.request_interrupt(InterruptFlags.KEYPAD)
    
    # ===== Utilidades =====
    
    def get_io_register_16(self, reg: int) -> int:
        """Lee un registro de I/O de 16 bits"""
        return int(self.io_registers[reg]) | (int(self.io_registers[reg + 1]) << 8)

    def set_io_register_16(self, reg: int, value: int) -> None:
        """Escribe un registro de I/O de 16 bits"""
        self.io_registers[reg] = value & 0xFF
        self.io_registers[reg + 1] = (value >> 8) & 0xFF

    
    # ===== TESTS =====

    # def load_rom_data(self, address: int, data: bytes) -> None:
    #     """Carga datos directamente en la ROM (para testing)"""
    #     offset = address - 0x08000000
    #     if offset >= 0 and offset + len(data) <= len(self.rom):
    #         for i, b in enumerate(data):
    #             self.rom[offset + i] = b