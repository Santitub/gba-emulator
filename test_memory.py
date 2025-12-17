# test_memory.py
from memory.memory_bus import MemoryBus
from memory.io_registers import IORegister, InterruptFlags, KeyInput

def test_memory_regions():
    """Prueba las regiones de memoria"""
    mem = MemoryBus()
    
    print("=== Test de Regiones de Memoria ===\n")
    
    # EWRAM
    mem.write_32(0x02000000, 0xDEADBEEF)
    assert mem.read_32(0x02000000) == 0xDEADBEEF
    # Mirror
    assert mem.read_32(0x02040000) == 0xDEADBEEF
    print("✓ EWRAM funciona con mirrors")
    
    # IWRAM
    mem.write_32(0x03000000, 0x12345678)
    assert mem.read_32(0x03000000) == 0x12345678
    # Mirror
    assert mem.read_32(0x03008000) == 0x12345678
    print("✓ IWRAM funciona con mirrors")
    
    # Palette RAM
    mem.write_16(0x05000000, 0x7FFF)
    assert mem.read_16(0x05000000) == 0x7FFF
    print("✓ Palette RAM funciona")
    
    # VRAM
    mem.write_16(0x06000000, 0x1234)
    assert mem.read_16(0x06000000) == 0x1234
    print("✓ VRAM funciona")
    
    # OAM
    mem.write_32(0x07000000, 0xAABBCCDD)
    assert mem.read_32(0x07000000) == 0xAABBCCDD
    print("✓ OAM funciona")
    
    print("\n=== Test de Regiones completado ===")

def test_io_registers():
    """Prueba los registros de I/O"""
    mem = MemoryBus()
    
    print("\n=== Test de Registros I/O ===\n")
    
    # DISPCNT
    mem.write_16(0x04000000, 0x0403)
    val = mem.read_16(0x04000000)
    print(f"DISPCNT escrito: 0x0403, leído: {val:04X}")
    assert (val & 0x0407) == 0x0403
    print("✓ DISPCNT funciona")
    
    # IME
    mem.write_16(0x04000208, 0x0001)
    assert mem.read_16(0x04000208) == 0x0001
    print("✓ IME funciona")
    
    # IE
    mem.write_16(0x04000200, InterruptFlags.VBLANK | InterruptFlags.HBLANK)
    assert mem.read_16(0x04000200) == 0x0003
    print("✓ IE funciona")
    
    # IF (escribir 1 limpia)
    # Primero establecer algunos flags
    mem.io_registers[IORegister.IF] = 0xFF
    mem.io_registers[IORegister.IF + 1] = 0x00
    print(f"IF antes: {mem.get_io_register_16(IORegister.IF):04X}")
    
    # Escribir para limpiar VBLANK (bit 0)
    mem.write_16(0x04000202, 0x0001)
    result = mem.get_io_register_16(IORegister.IF)
    print(f"IF después de acknowledge 0x0001: {result:04X}")
    assert result == 0x00FE, f"IF debería ser 0x00FE, es {result:04X}"
    print("✓ IF (acknowledge) funciona")
    
    print("\n=== Test de I/O completado ===")

def test_keypad():
    """Prueba el input del keypad"""
    mem = MemoryBus()
    
    print("\n=== Test de Keypad ===\n")
    
    # Inicialmente todos los botones están sueltos (1s)
    initial = mem.read_16(0x04000130)
    print(f"Estado inicial: {initial:04X}")
    assert initial == 0x03FF
    
    # Presionar A
    mem.set_key_state(KeyInput.A, True)
    state = mem.read_16(0x04000130)
    print(f"Después de A presionado: {state:04X}")
    assert (state & KeyInput.A) == 0
    
    # Presionar B también
    mem.set_key_state(KeyInput.B, True)
    state = mem.read_16(0x04000130)
    print(f"Después de A+B presionados: {state:04X}")
    assert (state & (KeyInput.A | KeyInput.B)) == 0
    
    # Soltar A
    mem.set_key_state(KeyInput.A, False)
    state = mem.read_16(0x04000130)
    print(f"Después de soltar A: {state:04X}")
    assert (state & KeyInput.A) == KeyInput.A
    assert (state & KeyInput.B) == 0
    
    print("\n✓ Keypad funciona correctamente")

def test_interrupts():
    """Prueba el sistema de interrupciones"""
    mem = MemoryBus()
    
    print("\n=== Test de Interrupciones ===\n")
    
    class MockCPU:
        def __init__(self):
            self.irq_triggered = False
        def trigger_irq(self):
            self.irq_triggered = True
    
    mock_cpu = MockCPU()
    mem.cpu = mock_cpu
    
    # Habilitar IME
    mem.write_16(0x04000208, 1)
    
    # Habilitar interrupción VBLANK
    mem.write_16(0x04000200, InterruptFlags.VBLANK)
    
    # Solicitar interrupción VBLANK
    mem.request_interrupt(InterruptFlags.VBLANK)
    
    assert mock_cpu.irq_triggered == True
    print("✓ Interrupción VBLANK disparada")
    
    assert mem.get_io_register_16(IORegister.IF) & InterruptFlags.VBLANK
    print("✓ IF tiene flag VBLANK")
    
    # Acknowledge
    mem.write_16(0x04000202, InterruptFlags.VBLANK)
    assert (mem.get_io_register_16(IORegister.IF) & InterruptFlags.VBLANK) == 0
    print("✓ IF limpiado después de acknowledge")
    
    print("\n=== Test de Interrupciones completado ===")

if __name__ == "__main__":
    test_memory_regions()
    test_io_registers()
    test_keypad()
    test_interrupts()