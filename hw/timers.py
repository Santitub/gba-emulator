"""
Sistema de Timers del GBA
4 timers de 16-bit con prescaler y cascade
"""
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from memory.memory_bus import MemoryBus


class Timer:
    """Un timer individual del GBA"""
    
    # Prescaler: ciclos por tick
    PRESCALERS = [1, 64, 256, 1024]
    
    def __init__(self, timer_id: int):
        self.timer_id = timer_id
        
        # Registros
        self.counter = 0        # Valor actual (16-bit)
        self.reload = 0         # Valor de recarga (16-bit)
        self.control = 0        # Control (16-bit)
        
        # Estado interno
        self.prescaler_counter = 0
        self.running = False
        
        # Callbacks
        self.on_overflow: Optional[Callable] = None
    
    @property
    def prescaler(self) -> int:
        """Obtiene el prescaler actual"""
        return self.PRESCALERS[self.control & 0x03]
    
    @property
    def cascade(self) -> bool:
        """Timer en modo cascade (cuenta overflows del timer anterior)"""
        return bool(self.control & 0x04) and self.timer_id > 0
    
    @property
    def irq_enabled(self) -> bool:
        """IRQ habilitado en overflow"""
        return bool(self.control & 0x40)
    
    @property
    def enabled(self) -> bool:
        """Timer habilitado"""
        return bool(self.control & 0x80)
    
    def reset(self) -> None:
        """Reinicia el timer"""
        self.counter = 0
        self.reload = 0
        self.control = 0
        self.prescaler_counter = 0
        self.running = False
    
    def write_reload(self, value: int) -> None:
        """Escribe el valor de recarga"""
        self.reload = value & 0xFFFF
    
    def write_control(self, value: int) -> None:
        """Escribe el registro de control"""
        was_enabled = self.enabled
        self.control = value & 0x00C7  # Solo bits válidos
        
        # Si se acaba de habilitar, recargar contador
        if not was_enabled and self.enabled:
            self.counter = self.reload
            self.prescaler_counter = 0
            self.running = True
        elif not self.enabled:
            self.running = False
    
    def read_counter(self) -> int:
        """Lee el valor actual del contador"""
        return self.counter
    
    def step(self, cycles: int) -> int:
        """
        Avanza el timer por un número de ciclos
        
        Returns:
            Número de overflows ocurridos
        """
        if not self.running or self.cascade:
            return 0
        
        overflows = 0
        self.prescaler_counter += cycles
        
        # Procesar ticks según prescaler
        while self.prescaler_counter >= self.prescaler:
            self.prescaler_counter -= self.prescaler
            overflows += self._tick()
        
        return overflows
    
    def cascade_tick(self) -> int:
        """
        Llamado cuando el timer anterior hace overflow (modo cascade)
        
        Returns:
            Número de overflows
        """
        if not self.running or not self.cascade:
            return 0
        
        return self._tick()
    
    def _tick(self) -> int:
        """
        Incrementa el contador una vez
        
        Returns:
            1 si hubo overflow, 0 si no
        """
        self.counter += 1
        
        if self.counter > 0xFFFF:
            self.counter = self.reload
            
            if self.on_overflow:
                self.on_overflow(self.timer_id)
            
            return 1
        
        return 0


class TimerController:
    """
    Controlador de los 4 timers del GBA
    """
    
    def __init__(self, memory: 'MemoryBus'):
        self.memory = memory
        
        # Crear 4 timers
        self.timers = [Timer(i) for i in range(4)]
        
        # Configurar callbacks de overflow
        for timer in self.timers:
            timer.on_overflow = self._on_timer_overflow
    
    def reset(self) -> None:
        """Reinicia todos los timers"""
        for timer in self.timers:
            timer.reset()
    
    def step(self, cycles: int) -> None:
        """Avanza todos los timers"""
        # Timer 0 siempre cuenta ciclos directamente
        overflows_0 = self.timers[0].step(cycles)
        
        # Los demás pueden ser cascade
        cascade_overflows = overflows_0
        
        for i in range(1, 4):
            timer = self.timers[i]
            
            if timer.cascade:
                # Modo cascade: cuenta overflows del timer anterior
                for _ in range(cascade_overflows):
                    cascade_overflows = timer.cascade_tick()
            else:
                # Modo normal: cuenta ciclos
                cascade_overflows = timer.step(cycles)
    
    def _on_timer_overflow(self, timer_id: int) -> None:
        """Callback cuando un timer hace overflow"""
        # Generar interrupción si está habilitada
        if self.timers[timer_id].irq_enabled:
            irq_bit = 0x08 << timer_id  # Timer 0=bit3, Timer 1=bit4, etc.
            self.memory.request_interrupt(irq_bit)
        
        # Notificar al APU si es timer 0 o 1
        if timer_id in (0, 1) and self.memory.apu:
            self.memory.apu.timer_overflow(timer_id)
    
    # ===== Acceso a registros =====
    
    def read_counter(self, timer_id: int) -> int:
        """Lee el contador de un timer"""
        if 0 <= timer_id < 4:
            return self.timers[timer_id].read_counter()
        return 0
    
    def read_control(self, timer_id: int) -> int:
        """Lee el control de un timer"""
        if 0 <= timer_id < 4:
            return self.timers[timer_id].control
        return 0
    
    def write_reload(self, timer_id: int, value: int) -> None:
        """Escribe el reload de un timer"""
        if 0 <= timer_id < 4:
            self.timers[timer_id].write_reload(value)
    
    def write_control(self, timer_id: int, value: int) -> None:
        """Escribe el control de un timer"""
        if 0 <= timer_id < 4:
            self.timers[timer_id].write_control(value)
    
    def get_counter(self, timer_id: int) -> int:
        """Obtiene el valor actual del contador"""
        if 0 <= timer_id < 4:
            return self.timers[timer_id].counter
        return 0