"""
APU (Audio Processing Unit) del GBA
Maneja todo el sistema de audio
"""
import numpy as np
from typing import TYPE_CHECKING, Optional, List
from collections import deque

if TYPE_CHECKING:
    from memory.memory_bus import MemoryBus

# Constantes de audio
SAMPLE_RATE = 32768
CPU_FREQUENCY = 16777216
CYCLES_PER_SAMPLE = CPU_FREQUENCY // SAMPLE_RATE  # ~512 ciclos

# Duty cycles para canales de onda cuadrada
DUTY_CYCLES = [
    [0, 0, 0, 0, 0, 0, 0, 1],  # 12.5%
    [1, 0, 0, 0, 0, 0, 0, 1],  # 25%
    [1, 0, 0, 0, 0, 1, 1, 1],  # 50%
    [0, 1, 1, 1, 1, 1, 1, 0],  # 75%
]


class SquareChannel:
    """Canal de onda cuadrada (Channel 1 y 2)"""
    
    def __init__(self, has_sweep: bool = False):
        self.has_sweep = has_sweep
        self.enabled = False
        
        # Sweep (solo canal 1)
        self.sweep_period = 0
        self.sweep_negate = False
        self.sweep_shift = 0
        self.sweep_timer = 0
        self.sweep_enabled = False
        self.sweep_shadow = 0
        
        # Duty y longitud
        self.duty = 0
        self.length_counter = 0
        self.length_enabled = False
        
        # Envelope
        self.envelope_initial = 0
        self.envelope_dir = 0  # 0=decrease, 1=increase
        self.envelope_period = 0
        self.envelope_timer = 0
        self.volume = 0
        
        # Frecuencia
        self.frequency = 0
        self.timer = 0
        self.duty_position = 0
    
    def reset(self) -> None:
        """Reinicia el canal"""
        self.enabled = False
        self.volume = 0
        self.timer = 0
        self.duty_position = 0
        self.length_counter = 0
    
    def trigger(self) -> None:
        """Dispara el canal (reinicia generación)"""
        self.enabled = True
        
        if self.length_counter == 0:
            self.length_counter = 64
        
        # Reiniciar timer
        self.timer = (2048 - self.frequency) * 4
        
        # Reiniciar envelope
        self.volume = self.envelope_initial
        self.envelope_timer = self.envelope_period
        
        # Reiniciar sweep (canal 1)
        if self.has_sweep:
            self.sweep_shadow = self.frequency
            self.sweep_timer = self.sweep_period if self.sweep_period else 8
            self.sweep_enabled = self.sweep_period > 0 or self.sweep_shift > 0
            
            if self.sweep_shift > 0:
                self._calculate_sweep()
    
    def _calculate_sweep(self) -> int:
        """Calcula nueva frecuencia de sweep"""
        new_freq = self.sweep_shadow >> self.sweep_shift
        
        if self.sweep_negate:
            new_freq = self.sweep_shadow - new_freq
        else:
            new_freq = self.sweep_shadow + new_freq
        
        # Overflow check
        if new_freq > 2047:
            self.enabled = False
        
        return new_freq
    
    def step_sweep(self) -> None:
        """Avanza el sweep (llamado a 128 Hz)"""
        if not self.has_sweep or not self.sweep_enabled:
            return
        
        self.sweep_timer -= 1
        if self.sweep_timer <= 0:
            self.sweep_timer = self.sweep_period if self.sweep_period else 8
            
            if self.sweep_enabled and self.sweep_period > 0:
                new_freq = self._calculate_sweep()
                
                if new_freq <= 2047 and self.sweep_shift > 0:
                    self.frequency = new_freq
                    self.sweep_shadow = new_freq
                    self._calculate_sweep()
    
    def step_length(self) -> None:
        """Avanza el contador de longitud (llamado a 256 Hz)"""
        if self.length_enabled and self.length_counter > 0:
            self.length_counter -= 1
            if self.length_counter == 0:
                self.enabled = False
    
    def step_envelope(self) -> None:
        """Avanza el envelope (llamado a 64 Hz)"""
        if self.envelope_period == 0:
            return
        
        self.envelope_timer -= 1
        if self.envelope_timer <= 0:
            self.envelope_timer = self.envelope_period
            
            if self.envelope_dir:
                if self.volume < 15:
                    self.volume += 1
            else:
                if self.volume > 0:
                    self.volume -= 1
    
    def step(self) -> None:
        """Avanza el timer de frecuencia"""
        self.timer -= 1
        if self.timer <= 0:
            self.timer = (2048 - self.frequency) * 4
            self.duty_position = (self.duty_position + 1) & 7
    
    def get_sample(self) -> int:
        """Obtiene el sample actual (-15 a 15)"""
        if not self.enabled:
            return 0
        
        if DUTY_CYCLES[self.duty][self.duty_position]:
            return self.volume
        return -self.volume


class WaveChannel:
    """Canal de onda programable (Channel 3)"""
    
    def __init__(self):
        self.enabled = False
        self.dac_enabled = False
        
        # Wave RAM
        self.wave_ram = np.zeros(32, dtype=np.uint8)
        self.wave_bank = 0
        self.wave_dimension = 0  # 0=32 samples, 1=64 samples
        
        # Longitud
        self.length_counter = 0
        self.length_enabled = False
        
        # Volumen
        self.volume_code = 0  # 0=0%, 1=100%, 2=50%, 3=25%
        self.force_volume = False
        
        # Frecuencia
        self.frequency = 0
        self.timer = 0
        self.position = 0
    
    def reset(self) -> None:
        """Reinicia el canal"""
        self.enabled = False
        self.timer = 0
        self.position = 0
        self.length_counter = 0
    
    def trigger(self) -> None:
        """Dispara el canal"""
        if self.dac_enabled:
            self.enabled = True
        
        if self.length_counter == 0:
            self.length_counter = 256
        
        self.timer = (2048 - self.frequency) * 2
        self.position = 0
    
    def step_length(self) -> None:
        """Avanza el contador de longitud"""
        if self.length_enabled and self.length_counter > 0:
            self.length_counter -= 1
            if self.length_counter == 0:
                self.enabled = False
    
    def step(self) -> None:
        """Avanza el timer de frecuencia"""
        self.timer -= 1
        if self.timer <= 0:
            self.timer = (2048 - self.frequency) * 2
            self.position = (self.position + 1) & 31
    
    def get_sample(self) -> int:
        """Obtiene el sample actual"""
        if not self.enabled or not self.dac_enabled:
            return 0
        
        # Obtener sample de wave RAM (4 bits) - convertir a int Python
        sample = int(self.wave_ram[self.position])
        
        # Aplicar volumen
        if self.force_volume:
            sample = (sample * 3) >> 2  # 75%
        else:
            shifts = [4, 0, 1, 2]  # 0%, 100%, 50%, 25%
            sample >>= shifts[self.volume_code]
        
        # Convertir a signed (-8 a 7)
        return sample - 8


class NoiseChannel:
    """Canal de ruido (Channel 4)"""
    
    def __init__(self):
        self.enabled = False
        
        # Longitud
        self.length_counter = 0
        self.length_enabled = False
        
        # Envelope
        self.envelope_initial = 0
        self.envelope_dir = 0
        self.envelope_period = 0
        self.envelope_timer = 0
        self.volume = 0
        
        # Noise
        self.clock_shift = 0
        self.width_mode = 0  # 0=15 bits, 1=7 bits
        self.divisor_code = 0
        
        self.timer = 0
        self.lfsr = 0x7FFF  # Linear Feedback Shift Register
    
    def reset(self) -> None:
        """Reinicia el canal"""
        self.enabled = False
        self.volume = 0
        self.lfsr = 0x7FFF
    
    def trigger(self) -> None:
        """Dispara el canal"""
        self.enabled = True
        
        if self.length_counter == 0:
            self.length_counter = 64
        
        self.volume = self.envelope_initial
        self.envelope_timer = self.envelope_period
        self.lfsr = 0x7FFF
        
        self._reload_timer()
    
    def _reload_timer(self) -> None:
        """Recarga el timer basado en la configuración"""
        divisors = [8, 16, 32, 48, 64, 80, 96, 112]
        self.timer = divisors[self.divisor_code] << self.clock_shift
    
    def step_length(self) -> None:
        """Avanza el contador de longitud"""
        if self.length_enabled and self.length_counter > 0:
            self.length_counter -= 1
            if self.length_counter == 0:
                self.enabled = False
    
    def step_envelope(self) -> None:
        """Avanza el envelope"""
        if self.envelope_period == 0:
            return
        
        self.envelope_timer -= 1
        if self.envelope_timer <= 0:
            self.envelope_timer = self.envelope_period
            
            if self.envelope_dir:
                if self.volume < 15:
                    self.volume += 1
            else:
                if self.volume > 0:
                    self.volume -= 1
    
    def step(self) -> None:
        """Avanza el LFSR"""
        self.timer -= 1
        if self.timer <= 0:
            self._reload_timer()
            
            # XOR bits 0 y 1
            xor_result = (self.lfsr & 1) ^ ((self.lfsr >> 1) & 1)
            
            # Shift y set bit 14
            self.lfsr = (self.lfsr >> 1) | (xor_result << 14)
            
            # Si modo 7-bit, también set bit 6
            if self.width_mode:
                self.lfsr = (self.lfsr & ~0x40) | (xor_result << 6)
    
    def get_sample(self) -> int:
        """Obtiene el sample actual"""
        if not self.enabled:
            return 0
        
        # Bit 0 invertido determina el output
        if self.lfsr & 1:
            return -self.volume
        return self.volume


class DirectSoundChannel:
    """Canal de Direct Sound (DMA A o B)"""
    
    def __init__(self):
        self.enabled = False
        self.fifo: deque = deque(maxlen=32)
        
        self.volume_full = True  # True=100%, False=50%
        self.enable_left = False
        self.enable_right = False
        self.timer_select = 0  # 0=Timer 0, 1=Timer 1
        
        self.current_sample = 0
    
    def reset(self) -> None:
        """Reinicia el canal"""
        self.fifo.clear()
        self.current_sample = 0
    
    def write_fifo(self, value: int) -> None:
        """Escribe 4 bytes al FIFO"""
        for i in range(4):
            sample = (value >> (i * 8)) & 0xFF
            # Convertir a signed
            if sample >= 128:
                sample -= 256
            if len(self.fifo) < 32:
                self.fifo.append(sample)
    
    def timer_overflow(self) -> bool:
        """
        Llamado cuando el timer asociado hace overflow
        Returns: True si se necesita DMA refill
        """
        if len(self.fifo) > 0:
            self.current_sample = self.fifo.popleft()
        else:
            self.current_sample = 0
        
        # Solicitar DMA si FIFO está medio vacío
        return len(self.fifo) <= 16
    
    def get_sample(self) -> int:
        """Obtiene el sample actual"""
        if not self.enabled:
            return 0
        
        sample = self.current_sample
        
        if not self.volume_full:
            sample >>= 1
        
        return sample


class APU:
    """
    Unidad de Procesamiento de Audio del GBA
    """
    
    def __init__(self, memory: 'MemoryBus'):
        self.memory = memory
        
        # Canales PSG
        self.channel1 = SquareChannel(has_sweep=True)
        self.channel2 = SquareChannel(has_sweep=False)
        self.channel3 = WaveChannel()
        self.channel4 = NoiseChannel()
        
        # Canales DMA
        self.dma_a = DirectSoundChannel()
        self.dma_b = DirectSoundChannel()
        
        # Control
        self.master_enable = False
        self.psg_volume_right = 0
        self.psg_volume_left = 0
        self.psg_enable_right = [False, False, False, False]
        self.psg_enable_left = [False, False, False, False]
        self.psg_master_volume = 0  # 0=25%, 1=50%, 2=100%
        
        # Bias
        self.bias = 0x200
        self.amplitude_resolution = 0
        
        # Frame sequencer
        self.frame_sequencer_counter = 0
        self.frame_sequencer_step = 0
        
        # Sample generation
        self.sample_counter = 0
        self.sample_buffer: List[tuple] = []
        self.buffer_size = 2048
    
    def reset(self) -> None:
        """Reinicia la APU"""
        self.channel1.reset()
        self.channel2.reset()
        self.channel3.reset()
        self.channel4.reset()
        self.dma_a.reset()
        self.dma_b.reset()
        
        self.master_enable = False
        self.frame_sequencer_counter = 0
        self.frame_sequencer_step = 0
        self.sample_counter = 0
        self.sample_buffer.clear()
    
    def step(self, cycles: int) -> None:
        """Avanza la APU por un número de ciclos"""
        if not self.master_enable:
            return
        
        for _ in range(cycles):
            self._step_frame_sequencer()
            self._step_channels()
            self._generate_sample()
    
    def _step_frame_sequencer(self) -> None:
        """Frame sequencer para controlar timing de PSG"""
        self.frame_sequencer_counter += 1
        
        # Frame sequencer corre a CPU_FREQ / 8192 = 2048 Hz
        if self.frame_sequencer_counter >= 8192:
            self.frame_sequencer_counter = 0
            
            # Step 0, 2, 4, 6: Length
            if self.frame_sequencer_step % 2 == 0:
                self.channel1.step_length()
                self.channel2.step_length()
                self.channel3.step_length()
                self.channel4.step_length()
            
            # Step 2, 6: Sweep
            if self.frame_sequencer_step in (2, 6):
                self.channel1.step_sweep()
            
            # Step 7: Envelope
            if self.frame_sequencer_step == 7:
                self.channel1.step_envelope()
                self.channel2.step_envelope()
                self.channel4.step_envelope()
            
            self.frame_sequencer_step = (self.frame_sequencer_step + 1) & 7
    
    def _step_channels(self) -> None:
        """Avanza los canales de audio"""
        self.channel1.step()
        self.channel2.step()
        self.channel3.step()
        self.channel4.step()
    
    def _generate_sample(self) -> None:
        """Genera un sample de audio"""
        self.sample_counter += 1
        
        if self.sample_counter >= CYCLES_PER_SAMPLE:
            self.sample_counter = 0
            
            # Mezclar canales PSG
            psg_left = 0
            psg_right = 0
            
            samples = [
                self.channel1.get_sample(),
                self.channel2.get_sample(),
                self.channel3.get_sample(),
                self.channel4.get_sample(),
            ]
            
            for i, sample in enumerate(samples):
                if self.psg_enable_left[i]:
                    psg_left += sample
                if self.psg_enable_right[i]:
                    psg_right += sample
            
            # Aplicar volumen PSG
            psg_left = (psg_left * (self.psg_volume_left + 1)) >> 3
            psg_right = (psg_right * (self.psg_volume_right + 1)) >> 3
            
            # Aplicar volumen master PSG
            psg_shifts = [2, 1, 0, 0]  # 25%, 50%, 100%, prohibited
            psg_left >>= psg_shifts[self.psg_master_volume]
            psg_right >>= psg_shifts[self.psg_master_volume]
            
            # Añadir DMA
            left = psg_left
            right = psg_right
            
            dma_a_sample = self.dma_a.get_sample()
            dma_b_sample = self.dma_b.get_sample()
            
            if self.dma_a.enable_left:
                left += dma_a_sample
            if self.dma_a.enable_right:
                right += dma_a_sample
            if self.dma_b.enable_left:
                left += dma_b_sample
            if self.dma_b.enable_right:
                right += dma_b_sample
            
            # Aplicar bias y clamp
            left = self._apply_bias(left)
            right = self._apply_bias(right)
            
            # Añadir al buffer
            if len(self.sample_buffer) < self.buffer_size:
                self.sample_buffer.append((left, right))
    
    def _apply_bias(self, sample: int) -> int:
        """Aplica bias y limita el sample"""
        sample += self.bias
        
        # Clamp a 10 bits (0-1023)
        if sample < 0:
            sample = 0
        elif sample > 1023:
            sample = 1023
        
        # Convertir a rango de audio (-1.0 a 1.0) escalado a 16-bit
        return int((sample - 512) * 64)
    
    # ===== Escritura de registros =====
    
    def write_sound1cnt_l(self, value: int) -> None:
        """SOUND1CNT_L - Channel 1 Sweep"""
        self.channel1.sweep_shift = value & 0x07
        self.channel1.sweep_negate = bool(value & 0x08)
        self.channel1.sweep_period = (value >> 4) & 0x07
    
    def write_sound1cnt_h(self, value: int) -> None:
        """SOUND1CNT_H - Channel 1 Duty/Envelope"""
        self.channel1.length_counter = 64 - (value & 0x3F)
        self.channel1.duty = (value >> 6) & 0x03
        self.channel1.envelope_period = (value >> 8) & 0x07
        self.channel1.envelope_dir = (value >> 11) & 0x01
        self.channel1.envelope_initial = (value >> 12) & 0x0F
    
    def write_sound1cnt_x(self, value: int) -> None:
        """SOUND1CNT_X - Channel 1 Frequency/Control"""
        self.channel1.frequency = value & 0x7FF
        self.channel1.length_enabled = bool(value & 0x4000)
        
        if value & 0x8000:
            self.channel1.trigger()
    
    def write_sound2cnt_l(self, value: int) -> None:
        """SOUND2CNT_L - Channel 2 Duty/Envelope"""
        self.channel2.length_counter = 64 - (value & 0x3F)
        self.channel2.duty = (value >> 6) & 0x03
        self.channel2.envelope_period = (value >> 8) & 0x07
        self.channel2.envelope_dir = (value >> 11) & 0x01
        self.channel2.envelope_initial = (value >> 12) & 0x0F
    
    def write_sound2cnt_h(self, value: int) -> None:
        """SOUND2CNT_H - Channel 2 Frequency/Control"""
        self.channel2.frequency = value & 0x7FF
        self.channel2.length_enabled = bool(value & 0x4000)
        
        if value & 0x8000:
            self.channel2.trigger()
    
    def write_sound3cnt_l(self, value: int) -> None:
        """SOUND3CNT_L - Channel 3 Enable/Bank"""
        self.channel3.wave_dimension = (value >> 5) & 0x01
        self.channel3.wave_bank = (value >> 6) & 0x01
        self.channel3.dac_enabled = bool(value & 0x80)
        
        if not self.channel3.dac_enabled:
            self.channel3.enabled = False
    
    def write_sound3cnt_h(self, value: int) -> None:
        """SOUND3CNT_H - Channel 3 Length/Volume"""
        self.channel3.length_counter = 256 - (value & 0xFF)
        self.channel3.volume_code = (value >> 13) & 0x03
        self.channel3.force_volume = bool(value & 0x8000)
    
    def write_sound3cnt_x(self, value: int) -> None:
        """SOUND3CNT_X - Channel 3 Frequency/Control"""
        self.channel3.frequency = value & 0x7FF
        self.channel3.length_enabled = bool(value & 0x4000)
        
        if value & 0x8000:
            self.channel3.trigger()
    
    def write_sound4cnt_l(self, value: int) -> None:
        """SOUND4CNT_L - Channel 4 Length/Envelope"""
        self.channel4.length_counter = 64 - (value & 0x3F)
        self.channel4.envelope_period = (value >> 8) & 0x07
        self.channel4.envelope_dir = (value >> 11) & 0x01
        self.channel4.envelope_initial = (value >> 12) & 0x0F
    
    def write_sound4cnt_h(self, value: int) -> None:
        """SOUND4CNT_H - Channel 4 Frequency/Control"""
        self.channel4.divisor_code = value & 0x07
        self.channel4.width_mode = (value >> 3) & 0x01
        self.channel4.clock_shift = (value >> 4) & 0x0F
        self.channel4.length_enabled = bool(value & 0x4000)
        
        if value & 0x8000:
            self.channel4.trigger()
    
    def write_soundcnt_l(self, value: int) -> None:
        """SOUNDCNT_L - PSG Control"""
        self.psg_volume_right = value & 0x07
        self.psg_volume_left = (value >> 4) & 0x07
        
        for i in range(4):
            self.psg_enable_right[i] = bool(value & (0x100 << i))
            self.psg_enable_left[i] = bool(value & (0x1000 << i))
    
    def write_soundcnt_h(self, value: int) -> None:
        """SOUNDCNT_H - DMA Sound Control"""
        self.psg_master_volume = value & 0x03
        
        self.dma_a.volume_full = bool(value & 0x04)
        self.dma_b.volume_full = bool(value & 0x08)
        
        self.dma_a.enable_right = bool(value & 0x100)
        self.dma_a.enable_left = bool(value & 0x200)
        self.dma_a.timer_select = (value >> 10) & 0x01
        
        if value & 0x800:
            self.dma_a.reset()
        
        self.dma_b.enable_right = bool(value & 0x1000)
        self.dma_b.enable_left = bool(value & 0x2000)
        self.dma_b.timer_select = (value >> 14) & 0x01
        
        if value & 0x8000:
            self.dma_b.reset()
    
    def write_soundcnt_x(self, value: int) -> None:
        """SOUNDCNT_X - Sound Enable"""
        self.master_enable = bool(value & 0x80)
        
        if not self.master_enable:
            self.channel1.reset()
            self.channel2.reset()
            self.channel3.reset()
            self.channel4.reset()
    
    def write_soundbias(self, value: int) -> None:
        """SOUNDBIAS - Sound PWM Control"""
        self.bias = value & 0x3FF
        self.amplitude_resolution = (value >> 14) & 0x03
    
    def write_wave_ram(self, offset: int, value: int) -> None:
        """Escribe al Wave RAM"""
        # Cada byte contiene 2 samples de 4 bits
        idx = offset * 2
        self.channel3.wave_ram[idx] = (value >> 4) & 0x0F
        self.channel3.wave_ram[idx + 1] = value & 0x0F
    
    def write_fifo_a(self, value: int) -> None:
        """Escribe al FIFO A"""
        self.dma_a.write_fifo(value)
    
    def write_fifo_b(self, value: int) -> None:
        """Escribe al FIFO B"""
        self.dma_b.write_fifo(value)
    
    def timer_overflow(self, timer_id: int) -> None:
        """Llamado cuando un timer hace overflow"""
        need_dma = False
        
        if self.dma_a.timer_select == timer_id:
            if self.dma_a.timer_overflow():
                need_dma = True
        
        if self.dma_b.timer_select == timer_id:
            if self.dma_b.timer_overflow():
                need_dma = True
        
        # TODO: Triggear DMA si es necesario
    
    # ===== Buffer de samples =====
    
    def get_samples(self, count: int) -> List[tuple]:
        """Obtiene samples del buffer"""
        samples = self.sample_buffer[:count]
        self.sample_buffer = self.sample_buffer[count:]
        return samples
    
    def get_buffer_size(self) -> int:
        """Obtiene el tamaño actual del buffer"""
        return len(self.sample_buffer)