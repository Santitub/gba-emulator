# test_arm.py
import struct
from memory.memory_bus import MemoryBus
from cpu.arm7tdmi import ARM7TDMI

def test_arm_instructions():
    """Prueba instrucciones ARM básicas"""
    mem = MemoryBus()
    
    # Crear ROM con las instrucciones
    rom_data = bytearray(256)
    
    # MOV R0, #0x42  -> E3A00042
    struct.pack_into('<I', rom_data, 0, 0xE3A00042)
    
    # MOV R1, #0x10  -> E3A01010
    struct.pack_into('<I', rom_data, 4, 0xE3A01010)
    
    # ADD R2, R0, R1 -> E0802001
    struct.pack_into('<I', rom_data, 8, 0xE0802001)
    
    # SUB R3, R2, #2 -> E2423002
    struct.pack_into('<I', rom_data, 12, 0xE2423002)
    
    # CMP R3, #0x50  -> E3530050
    struct.pack_into('<I', rom_data, 16, 0xE3530050)
    
    # Cargar ROM
    mem.load_rom(bytes(rom_data))
    
    cpu = ARM7TDMI(mem)
    cpu.reset()
    
    print("=== Test de Instrucciones ARM ===\n")
    
    # Ejecutar instrucciones
    for i in range(5):
        cycles = cpu.step()
        print(f"Ejecutado @ {cpu._current_pc:08X}: {cpu._current_instruction:08X}")
        print(f"  R0={cpu.registers.get(0):08X} R1={cpu.registers.get(1):08X} " +
              f"R2={cpu.registers.get(2):08X} R3={cpu.registers.get(3):08X}")
        print(f"  N={int(cpu.registers.flag_n)} Z={int(cpu.registers.flag_z)} " +
              f"C={int(cpu.registers.flag_c)} V={int(cpu.registers.flag_v)}")
        print()
    
    # Verificar resultados
    assert cpu.registers.get(0) == 0x42, f"R0 debería ser 0x42, es {cpu.registers.get(0):08X}"
    assert cpu.registers.get(1) == 0x10, f"R1 debería ser 0x10, es {cpu.registers.get(1):08X}"
    assert cpu.registers.get(2) == 0x52, f"R2 debería ser 0x52 (0x42+0x10), es {cpu.registers.get(2):08X}"
    assert cpu.registers.get(3) == 0x50, f"R3 debería ser 0x50 (0x52-2), es {cpu.registers.get(3):08X}"
    assert cpu.registers.flag_z == True, "Flag Z debería estar activo (CMP igual)"
    
    print("✓ MOV funciona")
    print("✓ ADD funciona") 
    print("✓ SUB funciona")
    print("✓ CMP funciona")
    
    print("\n=== Todas las pruebas ARM pasaron! ===")

def test_branch():
    """Prueba saltos"""
    mem = MemoryBus()
    
    rom_data = bytearray(256)
    
    # Offset 0: MOV R0, #1 -> E3A00001
    struct.pack_into('<I', rom_data, 0, 0xE3A00001)
    
    # Offset 4: B a offset 16 (saltar instrucciones en 8 y 12)
    # PC durante ejecución = 4 + 8 = 12
    # Queremos ir a offset 16
    # offset_bytes = 16 - 12 = 4
    # offset_words = 4 / 4 = 1
    # Instrucción: EA000001
    struct.pack_into('<I', rom_data, 4, 0xEA000001)
    
    # Offset 8: MOV R0, #99 (se salta) -> E3A00063
    struct.pack_into('<I', rom_data, 8, 0xE3A00063)
    
    # Offset 12: MOV R0, #88 (se salta) -> E3A00058
    struct.pack_into('<I', rom_data, 12, 0xE3A00058)
    
    # Offset 16: ADD R0, R0, #1 (destino) -> E2800001
    struct.pack_into('<I', rom_data, 16, 0xE2800001)
    
    mem.load_rom(bytes(rom_data))
    
    cpu = ARM7TDMI(mem)
    cpu.reset()
    
    print("\n=== Test de Branch ===\n")
    
    cpu.step()  # MOV R0, #1 @ offset 0
    print(f"Después de MOV: R0 = {cpu.registers.get(0)}, PC = {cpu.registers.pc:08X}")
    assert cpu.registers.get(0) == 1
    
    cpu.step()  # B @ offset 4 -> salta a offset 16
    print(f"Después de B: PC = {cpu.registers.pc:08X}")
    assert cpu.registers.pc == 0x08000010, f"PC debería ser 0x08000010, es {cpu.registers.pc:08X}"
    
    cpu.step()  # ADD R0, R0, #1 @ offset 16
    print(f"Después de ADD: R0 = {cpu.registers.get(0)}")
    
    assert cpu.registers.get(0) == 2, f"R0 debería ser 2, es {cpu.registers.get(0)}"
    
    print("\n✓ Branch funciona correctamente")

def test_conditional():
    """Prueba ejecución condicional"""
    mem = MemoryBus()
    
    rom_data = bytearray(256)
    
    # MOV R0, #5     -> E3A00005
    struct.pack_into('<I', rom_data, 0, 0xE3A00005)
    
    # CMP R0, #5     -> E3500005
    struct.pack_into('<I', rom_data, 4, 0xE3500005)
    
    # MOVEQ R1, #1   -> 03A01001 (ejecuta si Z=1)
    struct.pack_into('<I', rom_data, 8, 0x03A01001)
    
    # MOVNE R2, #1   -> 13A02001 (ejecuta si Z=0)
    struct.pack_into('<I', rom_data, 12, 0x13A02001)
    
    mem.load_rom(bytes(rom_data))
    
    cpu = ARM7TDMI(mem)
    cpu.reset()
    
    print("\n=== Test de Condicionales ===\n")
    
    cpu.step()  # MOV R0, #5
    cpu.step()  # CMP R0, #5 -> Z=1
    print(f"Después de CMP: Z={int(cpu.registers.flag_z)}")
    
    cpu.step()  # MOVEQ R1, #1 (debería ejecutar)
    print(f"Después de MOVEQ: R1={cpu.registers.get(1)}")
    
    cpu.step()  # MOVNE R2, #1 (no debería ejecutar)
    print(f"Después de MOVNE: R2={cpu.registers.get(2)}")
    
    assert cpu.registers.get(1) == 1, "MOVEQ debería haber ejecutado"
    assert cpu.registers.get(2) == 0, "MOVNE no debería haber ejecutado"
    
    print("\n✓ Condicionales funcionan correctamente")

if __name__ == "__main__":
    test_arm_instructions()
    test_branch()
    test_conditional()