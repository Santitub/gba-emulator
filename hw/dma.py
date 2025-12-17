"""
Sistema DMA del GBA
4 canales DMA para transferencias de memoria
"""
from typing import TYPE_CHECKING, Optional
from enum import IntEnum

if TYPE_CHECKING:
    from memory.memory_bus import MemoryBus


class DMAStartTiming(IntEnum):
    """Momento de inicio de DMA"""
    IMMEDIATE = 0
    VBLANK = 1
    HBLANK = 2
    SPECIAL = 3  # Depende del canal


class DMAChannel:
    """Un canal DMA individual"""
    
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        
        # Registros
        self.source = 0         # Dirección fuente (28/27 bits)
        self.dest = 0           # Dirección destino (28/27 bits)
        self.count = 0          # Número de transferencias
        self.control = 0        # Control (16-bit)
        
        # Estado interno
        self.internal_source = 0
        self.internal_dest = 0
        self.internal_count = 0
        self.running = False
        
        # Máscaras según canal
        if channel_id == 0:
            self.source_mask = 0x07FFFFFF  # 27 bits
            self.dest_mask = 0x07FFFFFF
            self.count_mask = 0x3FFF       # 14 bits
        elif channel_id in (1, 2):
            self.source_mask = 0x0FFFFFFF  # 28 bits
            self.dest_mask = 0x07FFFFFF
            self.count_mask = 0x3FFF
        else:  # channel_id == 3
            self.source_mask = 0x0FFFFFFF
            self.dest_mask = 0x0FFFFFFF
            self.count_mask = 0xFFFF       # 16 bits
    
    @property
    def dest_control(self) -> int:
        """Control de dirección destino (0=inc, 1=dec, 2=fixed, 3=inc+reload)"""
        return (self.control >> 5) & 0x03
    
    @property
    def source_control(self) -> int:
        """Control de dirección fuente (0=inc, 1=dec, 2=fixed)"""
        return (self.control >> 7) & 0x03
    
    @property
    def repeat(self) -> bool:
        """Repetir transferencia"""
        return bool(self.control & 0x0200)
    
    @property
    def transfer_32bit(self) -> bool:
        """Transferencia de 32 bits (vs 16 bits)"""
        return bool(self.control & 0x0400)
    
    @property
    def start_timing(self) -> int:
        """Momento de inicio"""
        return (self.control >> 12) & 0x03
    
    @property
    def irq_enabled(self) -> bool:
        """IRQ al finalizar"""
        return bool(self.control & 0x4000)
    
    @property
    def enabled(self) -> bool:
        """DMA habilitado"""
        return bool(self.control & 0x8000)
    
    def reset(self) -> None:
        """Reinicia el canal"""
        self.source = 0
        self.dest = 0
        self.count = 0
        self.control = 0
        self.running = False
    
    def write_source_low(self, value: int) -> None:
        """Escribe parte baja de source"""
        self.source = (self.source & 0xFFFF0000) | (value & 0xFFFF)
    
    def write_source_high(self, value: int) -> None:
        """Escribe parte alta de source"""
        self.source = (self.source & 0x0000FFFF) | ((value & 0xFFFF) << 16)
        self.source &= self.source_mask
    
    def write_dest_low(self, value: int) -> None:
        """Escribe parte baja de dest"""
        self.dest = (self.dest & 0xFFFF0000) | (value & 0xFFFF)
    
    def write_dest_high(self, value: int) -> None:
        """Escribe parte alta de dest"""
        self.dest = (self.dest & 0x0000FFFF) | ((value & 0xFFFF) << 16)
        self.dest &= self.dest_mask
    
    def write_count(self, value: int) -> None:
        """Escribe el conteo"""
        self.count = value & self.count_mask
        # Conteo 0 significa máximo
        if self.count == 0:
            self.count = self.count_mask + 1
    
    def write_control(self, value: int) -> None:
        """Escribe el control"""
        was_enabled = self.enabled
        self.control = value
        
        # Si se acaba de habilitar
        if not was_enabled and self.enabled:
            self._reload()
            
            # Si es inmediato, marcar como running
            if self.start_timing == DMAStartTiming.IMMEDIATE:
                self.running = True
    
    def _reload(self) -> None:
        """Recarga los registros internos"""
        self.internal_source = self.source
        self.internal_dest = self.dest
        self.internal_count = self.count if self.count > 0 else (self.count_mask + 1)
    
    def trigger(self) -> None:
        """Dispara el DMA (para non-immediate timing)"""
        if self.enabled and not self.running:
            self.running = True
    
    def is_sound_dma(self) -> bool:
        """Verifica si es DMA de sonido (canales 1-2, timing special)"""
        return (self.channel_id in (1, 2) and 
                self.start_timing == DMAStartTiming.SPECIAL)


class DMAController:
    """
    Controlador de los 4 canales DMA
    """
    
    def __init__(self, memory: 'MemoryBus'):
        self.memory = memory
        
        # Crear 4 canales
        self.channels = [DMAChannel(i) for i in range(4)]
    
    def reset(self) -> None:
        """Reinicia todos los canales"""
        for channel in self.channels:
            channel.reset()
    
    def step(self) -> int:
        """
        Ejecuta transferencias DMA pendientes
        
        Returns:
            Ciclos consumidos
        """
        cycles = 0
        
        # Procesar canales en orden de prioridad (0 es más alta)
        for channel in self.channels:
            if channel.running:
                cycles += self._execute_transfer(channel)
                break  # Solo un DMA activo a la vez
        
        return cycles
    
    def _execute_transfer(self, channel: DMAChannel) -> int:
        """
        Ejecuta una transferencia DMA completa
        
        Returns:
            Ciclos consumidos
        """
        cycles = 2  # Overhead inicial
        
        unit_size = 4 if channel.transfer_32bit else 2
        
        # Calcular incrementos
        source_delta = self._get_address_delta(channel.source_control, unit_size)
        dest_delta = self._get_address_delta(channel.dest_control, unit_size)
        
        # Realizar transferencias
        for _ in range(channel.internal_count):
            if channel.transfer_32bit:
                value = self.memory.read_32(channel.internal_source)
                self.memory.write_32(channel.internal_dest, value)
                cycles += 2
            else:
                value = self.memory.read_16(channel.internal_source)
                self.memory.write_16(channel.internal_dest, value)
                cycles += 2
            
            # Actualizar direcciones
            channel.internal_source = (channel.internal_source + source_delta) & channel.source_mask
            
            if channel.dest_control != 3:  # No increment+reload
                channel.internal_dest = (channel.internal_dest + dest_delta) & channel.dest_mask
        
        # Finalizar transferencia
        channel.running = False
        
        if channel.repeat and channel.start_timing != DMAStartTiming.IMMEDIATE:
            # Recargar count y posiblemente dest
            channel.internal_count = channel.count if channel.count > 0 else (channel.count_mask + 1)
            
            if channel.dest_control == 3:
                channel.internal_dest = channel.dest
        else:
            # Deshabilitar DMA
            channel.control &= ~0x8000
        
        # Generar IRQ si está habilitado
        if channel.irq_enabled:
            irq_bit = 0x0100 << channel.channel_id
            self.memory.request_interrupt(irq_bit)
        
        return cycles
    
    def _get_address_delta(self, control: int, unit_size: int) -> int:
        """Obtiene el delta de dirección según el control"""
        if control == 0:  # Increment
            return unit_size
        elif control == 1:  # Decrement
            return -unit_size
        else:  # Fixed (2) o Increment+Reload (3)
            return 0
    
    # ===== Triggers externos =====
    
    def on_vblank(self) -> None:
        """Llamado al inicio de V-Blank"""
        for channel in self.channels:
            if channel.enabled and channel.start_timing == DMAStartTiming.VBLANK:
                channel.trigger()
    
    def on_hblank(self) -> None:
        """Llamado al inicio de H-Blank"""
        for channel in self.channels:
            if channel.enabled and channel.start_timing == DMAStartTiming.HBLANK:
                channel.trigger()
    
    def on_sound_fifo(self, fifo_id: int) -> None:
        """
        Llamado cuando un FIFO de sonido necesita datos
        
        Args:
            fifo_id: 0 para FIFO A, 1 para FIFO B
        """
        # DMA 1 para FIFO A, DMA 2 para FIFO B
        channel_id = fifo_id + 1
        channel = self.channels[channel_id]
        
        if channel.enabled and channel.is_sound_dma():
            channel.trigger()
    
    # ===== Acceso a registros =====
    
    def write_control(self, channel_id: int, value: int) -> None:
        """Escribe el control de un canal"""
        if 0 <= channel_id < 4:
            self.channels[channel_id].write_control(value)
    
    def read_control(self, channel_id: int) -> int:
        """Lee el control de un canal"""
        if 0 <= channel_id < 4:
            return self.channels[channel_id].control
        return 0