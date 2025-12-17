# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True

"""Clase principal del emulador GBA - Versión Cython"""

from libc.stdint cimport uint32_t

from memory.memory_bus import MemoryBus
from cpu.arm7tdmi import ARM7TDMI
from ppu.ppu import PPU
from apu.apu import APU
from hw.timers import TimerController
from hw.dma import DMAController


cdef class GBA:
    """Emulador de Game Boy Advance"""
    
    cdef public object memory
    cdef public object cpu
    cdef public object ppu
    cdef public object apu
    cdef public object timers
    cdef public object dma
    
    cdef public bint running
    cdef public bint paused
    cdef public uint32_t total_cycles
    cdef public uint32_t frame_count
    
    # Constantes
    cdef readonly uint32_t CPU_FREQUENCY
    cdef readonly uint32_t CYCLES_PER_FRAME
    cdef readonly int SCREEN_WIDTH
    cdef readonly int SCREEN_HEIGHT
    
    def __init__(self):
        self.CPU_FREQUENCY = 16777216
        self.CYCLES_PER_FRAME = 280896
        self.SCREEN_WIDTH = 240
        self.SCREEN_HEIGHT = 160
        
        self.memory = MemoryBus()
        self.cpu = ARM7TDMI(self.memory)
        self.ppu = PPU(self.memory)
        self.apu = APU(self.memory)
        self.timers = TimerController(self.memory)
        self.dma = DMAController(self.memory)
        
        self.memory.cpu = self.cpu
        self.memory.ppu = self.ppu
        self.memory.apu = self.apu
        self.memory.timers = self.timers
        self.memory.dma = self.dma
        
        self.running = False
        self.paused = False
        self.total_cycles = 0
        self.frame_count = 0
    
    def load_bios(self, filepath):
        """Carga el BIOS"""
        try:
            with open(filepath, 'rb') as f:
                self.memory.load_bios(f.read())
            return True
        except Exception as e:
            print(f"Error cargando BIOS: {e}")
            return False
    
    def load_rom(self, filepath):
        """Carga una ROM"""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            if len(data) < 0xC0:
                print("Error: ROM demasiado pequeña")
                return False
            
            self.memory.load_rom(data)
            return True
        except Exception as e:
            print(f"Error cargando ROM: {e}")
            return False
    
    cpdef void reset(self):
        self.total_cycles = 0
        self.frame_count = 0
        self.cpu.reset()
        self.ppu.reset()
        self.apu.reset()
        self.timers.reset()
        self.dma.reset()
    
    cpdef int step(self):
        """Ejecuta un paso de emulación"""
        cdef int dma_cycles, cycles
        
        # DMA tiene prioridad
        dma_cycles = self.dma.step()
        if dma_cycles > 0:
            self.ppu.step(dma_cycles)
            self.apu.step(dma_cycles)
            self.timers.step(dma_cycles)
            self.total_cycles += dma_cycles
            return dma_cycles
        
        # CPU
        cycles = self.cpu.step()
        
        # Actualizar otros componentes
        self.ppu.step(cycles)
        self.apu.step(cycles)
        self.timers.step(cycles)
        
        self.total_cycles += cycles
        return cycles
    
    cpdef void run_frame(self):
        """Ejecuta un frame completo"""
        self.ppu.frame_ready = False
        
        while not self.ppu.frame_ready:
            self.step()
        
        self.frame_count += 1
    
    def get_framebuffer(self):
        return self.ppu.framebuffer
    
    def get_audio_samples(self, count):
        return self.apu.get_samples(count)
    
    cpdef void set_key(self, int key, bint pressed):
        """Establece el estado de una tecla"""
        self.memory.set_key_state(key, pressed)