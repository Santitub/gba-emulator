# test_apu.py
from memory.memory_bus import MemoryBus
from apu.apu import APU, SquareChannel, WaveChannel, NoiseChannel

def test_square_channel():
    """Prueba el canal de onda cuadrada"""
    print("=== Test de Canal Cuadrado ===\n")
    
    channel = SquareChannel(has_sweep=False)
    
    # Configurar canal con frecuencia alta para cambios rápidos
    channel.duty = 2  # 50% duty
    channel.envelope_initial = 15
    channel.envelope_dir = 0
    channel.envelope_period = 0
    channel.frequency = 2000  # Frecuencia alta = timer pequeño
    channel.volume = 15
    
    # Trigger
    channel.trigger()
    
    assert channel.enabled == True
    print("✓ Canal habilitado después de trigger")
    
    # Timer inicial = (2048 - 2000) * 4 = 192
    print(f"  Timer inicial: {channel.timer}")
    print(f"  Frecuencia: {channel.frequency}")
    
    # Generar suficientes samples para ver cambios
    samples = []
    for _ in range(5000):  # Más iteraciones
        channel.step()
        samples.append(channel.get_sample())
    
    # Verificar que hay variación (onda)
    unique = set(samples)
    print(f"  Valores únicos: {unique}")
    assert len(unique) > 1, "Debería haber variación en samples"
    print(f"✓ Samples generados con {len(unique)} valores únicos")
    print(f"  Rango: {min(samples)} a {max(samples)}")
    
    print("\n=== Test de Canal Cuadrado completado ===")

def test_wave_channel():
    """Prueba el canal de onda programable"""
    print("\n=== Test de Canal Wave ===\n")
    
    channel = WaveChannel()
    
    # Configurar wave RAM con una onda simple
    for i in range(32):
        channel.wave_ram[i] = i % 16  # Rampa
    
    channel.dac_enabled = True
    channel.volume_code = 1  # 100%
    channel.frequency = 2000  # Frecuencia alta
    
    channel.trigger()
    
    assert channel.enabled == True
    print("✓ Canal Wave habilitado")
    print(f"  Timer inicial: {channel.timer}")
    
    # Generar samples
    samples = []
    for _ in range(5000):
        channel.step()
        samples.append(channel.get_sample())
    
    unique = set(samples)
    print(f"✓ Samples generados: {len(samples)}")
    print(f"  Valores únicos: {len(unique)}")
    print(f"  Rango: {min(samples)} a {max(samples)}")
    
    assert len(unique) > 1, "Wave debería tener variación"
    
    print("\n=== Test de Canal Wave completado ===")

def test_noise_channel():
    """Prueba el canal de ruido"""
    print("\n=== Test de Canal Noise ===\n")
    
    channel = NoiseChannel()
    
    channel.envelope_initial = 15
    channel.envelope_dir = 0
    channel.envelope_period = 0
    channel.divisor_code = 0  # Divisor pequeño para cambios rápidos
    channel.clock_shift = 0   # Sin shift para cambios rápidos
    channel.width_mode = 0    # 15-bit LFSR
    channel.volume = 15
    
    channel.trigger()
    
    assert channel.enabled == True
    print("✓ Canal Noise habilitado")
    print(f"  LFSR inicial: {channel.lfsr:04X}")
    print(f"  Timer inicial: {channel.timer}")
    
    # Generar samples
    samples = []
    initial_lfsr = channel.lfsr
    for _ in range(5000):
        channel.step()
        samples.append(channel.get_sample())
    
    # LFSR debería haber cambiado
    assert channel.lfsr != initial_lfsr, f"LFSR no cambió: {channel.lfsr:04X}"
    print(f"✓ LFSR cambió: {initial_lfsr:04X} -> {channel.lfsr:04X}")
    
    # Verificar aleatoriedad básica
    unique = set(samples)
    print(f"✓ Samples con {len(unique)} valores únicos")
    
    print("\n=== Test de Canal Noise completado ===")

def test_fifo():
    """Prueba los canales DMA FIFO"""
    print("\n=== Test de FIFO ===\n")
    
    from apu.apu import DirectSoundChannel
    
    channel = DirectSoundChannel()
    channel.enabled = True
    channel.volume_full = True
    channel.enable_left = True
    channel.enable_right = True
    
    # Escribir samples al FIFO
    # 0x01020304 en little-endian: bytes 0x04, 0x03, 0x02, 0x01
    channel.write_fifo(0x01020304)
    
    assert len(channel.fifo) == 4
    print(f"✓ FIFO tiene {len(channel.fifo)} samples")
    print(f"  Contenido: {list(channel.fifo)}")
    
    # Leer samples (simulando timer overflow)
    samples = []
    for _ in range(4):
        channel.timer_overflow()
        samples.append(channel.current_sample)
    
    print(f"✓ Samples leídos: {samples}")
    
    # FIFO vacío
    assert len(channel.fifo) == 0
    print("✓ FIFO vacío después de leer todos")
    
    print("\n=== Test de FIFO completado ===")

def test_apu_integration():
    """Prueba integración de la APU"""
    print("\n=== Test de Integración APU ===\n")
    
    mem = MemoryBus()
    apu = APU(mem)
    
    # Habilitar sonido
    apu.write_soundcnt_x(0x80)
    assert apu.master_enable == True
    print("✓ Master enable activado")
    
    # Configurar canal 1 con frecuencia alta
    apu.write_sound1cnt_l(0x00)  # Sin sweep
    apu.write_sound1cnt_h(0xF080)  # Vol 15, 50% duty
    apu.write_sound1cnt_x(0x87D0)  # Freq alta (2000), trigger
    
    assert apu.channel1.enabled == True
    print("✓ Canal 1 configurado y habilitado")
    print(f"  Frecuencia: {apu.channel1.frequency}")
    
    # Configurar mixer
    apu.write_soundcnt_l(0x7777)  # Vol max, todos habilitados
    print("✓ Mixer configurado")
    
    # Generar samples (suficientes ciclos)
    for _ in range(100000):
        apu.step(1)
    
    buffer_size = apu.get_buffer_size()
    print(f"✓ Samples en buffer: {buffer_size}")
    
    samples = apu.get_samples(10)
    if samples:
        print(f"  Primeros samples: L={samples[0][0]}, R={samples[0][1]}")
    
    print("\n=== Test de Integración completado ===")

def test_envelope():
    """Prueba el sistema de envelope"""
    print("\n=== Test de Envelope ===\n")
    
    channel = SquareChannel()
    
    # Envelope decreciente
    channel.envelope_initial = 15
    channel.envelope_dir = 0  # Decrease
    channel.envelope_period = 1
    channel.frequency = 1024
    
    channel.trigger()
    
    initial_volume = channel.volume
    print(f"Volumen inicial: {initial_volume}")
    
    # Simular pasos de envelope
    for i in range(5):
        channel.step_envelope()
        print(f"  Después de step {i+1}: volumen = {channel.volume}")
    
    assert channel.volume < initial_volume
    print("✓ Envelope decreciente funciona")
    
    # Envelope creciente
    channel.envelope_initial = 0
    channel.envelope_dir = 1  # Increase
    channel.envelope_period = 1
    
    channel.trigger()
    print(f"\nVolumen inicial (creciente): {channel.volume}")
    
    for i in range(5):
        channel.step_envelope()
        print(f"  Después de step {i+1}: volumen = {channel.volume}")
    
    assert channel.volume > 0
    print("✓ Envelope creciente funciona")
    
    print("\n=== Test de Envelope completado ===")

def test_sweep():
    """Prueba el sistema de sweep (solo canal 1)"""
    print("\n=== Test de Sweep ===\n")
    
    channel = SquareChannel(has_sweep=True)
    
    # Sweep hacia arriba
    channel.sweep_period = 1
    channel.sweep_shift = 2
    channel.sweep_negate = False
    channel.frequency = 256
    channel.envelope_initial = 15
    
    channel.trigger()
    
    initial_freq = channel.frequency
    print(f"Frecuencia inicial: {initial_freq}")
    print(f"Sweep shadow: {channel.sweep_shadow}")
    
    # Simular pasos de sweep
    for i in range(3):
        channel.step_sweep()
        print(f"  Después de sweep {i+1}: freq = {channel.frequency}")
    
    assert channel.frequency > initial_freq
    print("✓ Sweep hacia arriba funciona")
    
    print("\n=== Test de Sweep completado ===")

def test_length_counter():
    """Prueba el contador de longitud"""
    print("\n=== Test de Length Counter ===\n")
    
    channel = SquareChannel()
    
    channel.length_counter = 5
    channel.length_enabled = True
    channel.envelope_initial = 15
    channel.frequency = 1024
    
    channel.trigger()
    
    print(f"Length counter inicial: {channel.length_counter}")
    print(f"Enabled: {channel.enabled}")
    
    # Avanzar length counter
    for i in range(6):
        channel.step_length()
        print(f"  Step {i+1}: length={channel.length_counter}, enabled={channel.enabled}")
    
    assert channel.enabled == False
    print("✓ Canal deshabilitado cuando length llega a 0")
    
    print("\n=== Test de Length Counter completado ===")

def test_duty_cycles():
    """Prueba los diferentes duty cycles"""
    print("\n=== Test de Duty Cycles ===\n")
    
    from apu.apu import DUTY_CYCLES
    
    for duty_idx, duty in enumerate(DUTY_CYCLES):
        ones = sum(duty)
        percentage = (ones / 8) * 100
        print(f"Duty {duty_idx}: {duty} = {percentage:.1f}%")
    
    assert DUTY_CYCLES[0].count(1) == 1  # 12.5%
    assert DUTY_CYCLES[1].count(1) == 2  # 25%
    assert DUTY_CYCLES[2].count(1) == 4  # 50%
    assert DUTY_CYCLES[3].count(1) == 6  # 75%
    
    print("✓ Duty cycles correctos")
    
    print("\n=== Test de Duty Cycles completado ===")

if __name__ == "__main__":
    test_duty_cycles()
    test_square_channel()
    test_wave_channel()
    test_noise_channel()
    test_fifo()
    test_envelope()
    test_sweep()
    test_length_counter()
    test_apu_integration()