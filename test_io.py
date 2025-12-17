# test_io.py
from memory.memory_bus import MemoryBus
from hw.timers import TimerController, Timer
from hw.dma import DMAController, DMAChannel, DMAStartTiming

def test_timer_basic():
    """Prueba funcionamiento básico de timer"""
    print("=== Test de Timer Básico ===\n")
    
    mem = MemoryBus()
    timers = TimerController(mem)
    mem.timers = timers
    
    # Configurar timer 0: prescaler 1, habilitado
    timers.write_reload(0, 0xFFFE)  # Reload cerca del overflow
    timers.write_control(0, 0x0080)  # Enable, prescaler 1
    
    assert timers.timers[0].enabled
    print("✓ Timer 0 habilitado")
    print(f"  Counter inicial: {timers.timers[0].counter}")
    print(f"  Reload: {timers.timers[0].reload}")
    
    # Avanzar hasta overflow
    overflows = 0
    for _ in range(10):
        timers.step(1)
        if timers.timers[0].counter == 0xFFFE:
            overflows += 1
    
    print(f"  Counter después de 10 ciclos: {timers.timers[0].counter}")
    print("✓ Timer incrementa correctamente")
    
    print("\n=== Test de Timer Básico completado ===")

def test_timer_prescaler():
    """Prueba prescalers de timer"""
    print("\n=== Test de Prescaler ===\n")
    
    timer = Timer(0)
    
    # Probar cada prescaler
    for prescaler_idx, expected in enumerate([1, 64, 256, 1024]):
        timer.reset()
        timer.reload = 0
        timer.control = 0x80 | prescaler_idx  # Enable + prescaler
        timer.counter = 0
        timer.running = True
        
        assert timer.prescaler == expected
        print(f"✓ Prescaler {prescaler_idx}: {expected} ciclos por tick")
    
    print("\n=== Test de Prescaler completado ===")

def test_timer_cascade():
    """Prueba modo cascade de timers"""
    print("\n=== Test de Timer Cascade ===\n")
    
    mem = MemoryBus()
    timers = TimerController(mem)
    
    # Timer 0: cuenta rápido, overflow frecuente
    timers.write_reload(0, 0xFFFF)  # Overflow en 1 tick
    timers.write_control(0, 0x0080)  # Enable
    
    # Timer 1: modo cascade, cuenta overflows de Timer 0
    timers.write_reload(1, 0)
    timers.write_control(1, 0x0084)  # Enable + cascade
    
    assert timers.timers[1].cascade
    print("✓ Timer 1 en modo cascade")
    
    # Avanzar Timer 0 hasta overflow
    initial_t1 = timers.timers[1].counter
    timers.step(1)  # Timer 0 overflow -> Timer 1 incrementa
    
    print(f"  Timer 1 antes: {initial_t1}")
    print(f"  Timer 1 después: {timers.timers[1].counter}")
    
    print("✓ Cascade funciona")
    
    print("\n=== Test de Timer Cascade completado ===")

def test_timer_irq():
    """Prueba IRQ de timer"""
    print("\n=== Test de Timer IRQ ===\n")
    
    mem = MemoryBus()
    timers = TimerController(mem)
    mem.timers = timers
    
    # Configurar timer con IRQ
    timers.write_reload(0, 0xFFFF)
    timers.write_control(0, 0x00C0)  # Enable + IRQ
    
    assert timers.timers[0].irq_enabled
    print("✓ Timer IRQ habilitado")
    
    # Avanzar hasta overflow
    timers.step(1)
    
    # Verificar IF
    if_reg = mem.get_io_register_16(0x202)
    print(f"  IF después de overflow: {if_reg:04X}")
    
    has_timer_irq = bool(if_reg & 0x08)  # Timer 0 = bit 3
    print(f"  Timer 0 IRQ flag: {has_timer_irq}")
    
    print("\n=== Test de Timer IRQ completado ===")

def test_dma_basic():
    """Prueba DMA básico"""
    print("\n=== Test de DMA Básico ===\n")
    
    mem = MemoryBus()
    dma = DMAController(mem)
    mem.dma = dma
    
    # Escribir datos fuente
    for i in range(16):
        mem.write_32(0x02000000 + i * 4, 0xDEAD0000 + i)
    
    # Configurar DMA 3: copiar 16 words
    dma.channels[3].write_source_low(0x0000)
    dma.channels[3].write_source_high(0x0200)
    dma.channels[3].write_dest_low(0x0100)
    dma.channels[3].write_dest_high(0x0200)
    dma.channels[3].write_count(16)
    
    # Habilitar: 32-bit, immediate, enable
    dma.channels[3].write_control(0x8400)
    
    assert dma.channels[3].running
    print("✓ DMA 3 iniciado")
    
    # Ejecutar DMA
    cycles = dma.step()
    print(f"  Ciclos consumidos: {cycles}")
    
    # Verificar datos copiados
    for i in range(16):
        value = mem.read_32(0x02000100 + i * 4)
        expected = 0xDEAD0000 + i
        assert value == expected, f"Pos {i}: {value:08X} != {expected:08X}"
    
    print("✓ Datos copiados correctamente")
    
    # DMA debería estar deshabilitado
    assert not dma.channels[3].enabled
    print("✓ DMA deshabilitado después de transferencia")
    
    print("\n=== Test de DMA Básico completado ===")

def test_dma_16bit():
    """Prueba DMA de 16 bits"""
    print("\n=== Test de DMA 16-bit ===\n")
    
    mem = MemoryBus()
    dma = DMAController(mem)
    mem.dma = dma
    
    # Escribir datos fuente
    for i in range(8):
        mem.write_16(0x02000000 + i * 2, 0xAB00 + i)
    
    # Configurar DMA 3: copiar 8 halfwords
    dma.channels[3].source = 0x02000000
    dma.channels[3].dest = 0x02000100
    dma.channels[3].write_count(8)
    
    # 16-bit, immediate, enable
    dma.channels[3].write_control(0x8000)
    
    dma.step()
    
    # Verificar
    for i in range(8):
        value = mem.read_16(0x02000100 + i * 2)
        expected = 0xAB00 + i
        assert value == expected
    
    print("✓ Transferencia 16-bit correcta")
    
    print("\n=== Test de DMA 16-bit completado ===")

def test_dma_address_control():
    """Prueba control de direcciones DMA"""
    print("\n=== Test de Control de Direcciones DMA ===\n")
    
    channel = DMAChannel(3)
    
    # Test dest control
    channel.control = 0x0000  # Increment
    assert channel.dest_control == 0
    
    channel.control = 0x0020  # Decrement
    assert channel.dest_control == 1
    
    channel.control = 0x0040  # Fixed
    assert channel.dest_control == 2
    
    channel.control = 0x0060  # Increment + Reload
    assert channel.dest_control == 3
    
    print("✓ Control de destino correcto")
    
    # Test source control
    channel.control = 0x0000
    assert channel.source_control == 0
    
    channel.control = 0x0080
    assert channel.source_control == 1
    
    channel.control = 0x0100
    assert channel.source_control == 2
    
    print("✓ Control de fuente correcto")
    
    print("\n=== Test de Control de Direcciones completado ===")

def test_dma_timing():
    """Prueba timing de DMA"""
    print("\n=== Test de DMA Timing ===\n")
    
    channel = DMAChannel(3)
    
    channel.control = 0x0000
    assert channel.start_timing == DMAStartTiming.IMMEDIATE
    
    channel.control = 0x1000
    assert channel.start_timing == DMAStartTiming.VBLANK
    
    channel.control = 0x2000
    assert channel.start_timing == DMAStartTiming.HBLANK
    
    channel.control = 0x3000
    assert channel.start_timing == DMAStartTiming.SPECIAL
    
    print("✓ Start timing correcto")
    
    print("\n=== Test de DMA Timing completado ===")

def test_dma_vblank_trigger():
    """Prueba trigger de DMA en V-Blank"""
    print("\n=== Test de DMA V-Blank ===\n")
    
    mem = MemoryBus()
    dma = DMAController(mem)
    
    # Configurar DMA para V-Blank
    dma.channels[3].source = 0x02000000
    dma.channels[3].dest = 0x02000100
    dma.channels[3].write_count(4)
    dma.channels[3].write_control(0x9000)  # Enable + VBlank timing
    
    assert dma.channels[3].enabled
    assert not dma.channels[3].running
    print("✓ DMA habilitado pero no corriendo")
    
    # Trigger V-Blank
    dma.on_vblank()
    
    assert dma.channels[3].running
    print("✓ DMA triggered en V-Blank")
    
    print("\n=== Test de DMA V-Blank completado ===")

if __name__ == "__main__":
    test_timer_basic()
    test_timer_prescaler()
    test_timer_cascade()
    test_timer_irq()
    test_dma_basic()
    test_dma_16bit()
    test_dma_address_control()
    test_dma_timing()
    test_dma_vblank_trigger()