# test_cpu.py
from memory.memory_bus import MemoryBus
from cpu.arm7tdmi import ARM7TDMI
from cpu.registers import CPUMode

def test_registers():
    """Prueba el sistema de registros"""
    mem = MemoryBus()
    cpu = ARM7TDMI(mem)
    cpu.reset()
    
    print("=== Test de Registros ===\n")
    
    # Test registros básicos
    cpu.registers.set(0, 0x12345678)
    cpu.registers.set(1, 0xDEADBEEF)
    assert cpu.registers.get(0) == 0x12345678
    assert cpu.registers.get(1) == 0xDEADBEEF
    print("✓ R0-R7 funcionan correctamente")
    
    # Test flags
    cpu.registers.flag_z = True
    cpu.registers.flag_n = True
    assert cpu.registers.flag_z == True
    assert cpu.registers.flag_n == True
    print("✓ Flags N/Z funcionan")
    
    # Test condiciones
    cpu.registers.cpsr = 0x40000000  # Z=1
    assert cpu.registers.check_condition(0x0) == True   # EQ
    assert cpu.registers.check_condition(0x1) == False  # NE
    print("✓ Condiciones funcionan")
    
    # Test cambio de modo
    print(f"\nModo inicial: {cpu.registers.mode:#x}")
    cpu.registers.switch_mode(CPUMode.IRQ)
    print(f"Después de switch a IRQ: {cpu.registers.mode:#x}")
    assert cpu.registers.mode == CPUMode.IRQ
    print("✓ Cambio de modo funciona")
    
    # Test bancos de registros
    cpu.registers.mode = CPUMode.SYSTEM
    cpu.registers.sp = 0x03007F00
    
    cpu.registers.mode = CPUMode.IRQ
    cpu.registers.sp = 0x03007FA0
    
    # Verificar que están separados
    cpu.registers.mode = CPUMode.SYSTEM
    assert cpu.registers.sp == 0x03007F00
    
    cpu.registers.mode = CPUMode.IRQ
    assert cpu.registers.sp == 0x03007FA0
    print("✓ Bancos de registros funcionan")
    
    # Mostrar estado
    cpu.registers.mode = CPUMode.SYSTEM
    print("\n" + str(cpu.registers))
    
    print("\n=== Todas las pruebas pasaron! ===")

if __name__ == "__main__":
    test_registers()