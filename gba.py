"""Clase principal del emulador GBA"""
from memory.memory_bus import MemoryBus
from cpu.arm7tdmi import ARM7TDMI
from ppu.ppu import PPU
from apu.apu import APU
from hw.timers import TimerController
from hw.dma import DMAController


class GBA:
    """Emulador de Game Boy Advance"""
    
    CPU_FREQUENCY = 16_777_216
    CYCLES_PER_FRAME = 280_896
    SCREEN_WIDTH = 240
    SCREEN_HEIGHT = 160
    
    def __init__(self):
        # Componentes principales
        self.memory = MemoryBus()
        self.cpu = ARM7TDMI(self.memory)
        self.ppu = PPU(self.memory)
        self.apu = APU(self.memory)
        self.timers = TimerController(self.memory)
        self.dma = DMAController(self.memory)
        
        # Conectar componentes
        self.memory.cpu = self.cpu
        self.memory.ppu = self.ppu
        self.memory.apu = self.apu
        self.memory.timers = self.timers
        self.memory.dma = self.dma
        
        # Estado
        self.running = False
        self.paused = False
        self.total_cycles = 0
        self.frame_count = 0
        
        print("GBA Emulator inicializado")
        print(f"  CPU: ARM7TDMI @ {self.CPU_FREQUENCY / 1_000_000:.2f} MHz")
        print(f"  Pantalla: {self.SCREEN_WIDTH}x{self.SCREEN_HEIGHT}")
        print(f"  Audio: PSG + DMA Sound")
        print(f"  Timers: 4 canales")
        print(f"  DMA: 4 canales")
    
    def load_bios(self, filepath: str) -> bool:
        try:
            with open(filepath, 'rb') as f:
                self.memory.load_bios(f.read())
            return True
        except Exception as e:
            print(f"Error cargando BIOS: {e}")
            return False
    
    def load_rom(self, filepath: str) -> bool:
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            if len(data) < 0xC0:
                print("Error: ROM demasiado pequeña")
                return False
            
            title = data[0xA0:0xAC].decode('ascii', errors='ignore').strip('\x00')
            game_code = data[0xAC:0xB0].decode('ascii', errors='ignore')
            
            self.memory.load_rom(data)
            
            print(f"  Título: {title}")
            print(f"  Código: {game_code}")
            
            return True
        except Exception as e:
            print(f"Error cargando ROM: {e}")
            return False
    
    def reset(self) -> None:
        self.total_cycles = 0
        self.frame_count = 0
        self.cpu.reset()
        self.ppu.reset()
        self.apu.reset()
        self.timers.reset()
        self.dma.reset()
        print("Sistema reiniciado")
    
    def step(self) -> int:
        # Ejecutar DMA si hay alguno activo
        dma_cycles = self.dma.step()
        if dma_cycles > 0:
            self.ppu.step(dma_cycles)
            self.apu.step(dma_cycles)
            self.timers.step(dma_cycles)
            self.total_cycles += dma_cycles
            return dma_cycles
        
        # Ejecutar CPU
        cycles = self.cpu.step()
        
        # Actualizar otros componentes
        self.ppu.step(cycles)
        self.apu.step(cycles)
        self.timers.step(cycles)
        
        self.total_cycles += cycles
        return cycles
    
    def run_frame(self) -> None:
        self.ppu.frame_ready = False
        
        while not self.ppu.frame_ready:
            self.step()
        
        self.frame_count += 1
    
    def get_framebuffer(self):
        """Obtiene el framebuffer actual"""
        return self.ppu.framebuffer  # Este método sí existe y retorna una copia
    
    def get_audio_samples(self, count: int):
        return self.apu.get_samples(count)
    
    def set_key(self, key: int, pressed: bool) -> None:
        """Establece el estado de una tecla"""
        self.memory.set_key_state(key, pressed)