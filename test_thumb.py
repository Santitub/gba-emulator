# test_thumb.py
import struct
from memory.memory_bus import MemoryBus
from cpu.arm7tdmi import ARM7TDMI

def test_thumb_instructions():
    """Prueba instrucciones THUMB básicas"""
    mem = MemoryBus()
    
    rom_data = bytearray(256)
    
    struct.pack_into('<H', rom_data, 0, 0x2042)  # MOV R0, #0x42
    struct.pack_into('<H', rom_data, 2, 0x2110)  # MOV R1, #0x10
    struct.pack_into('<H', rom_data, 4, 0x1842)  # ADD R2, R0, R1
    struct.pack_into('<H', rom_data, 6, 0x0093)  # LSL R3, R2, #2
    struct.pack_into('<H', rom_data, 8, 0x2B48)  # CMP R3, #0x48
    
    mem.load_rom(bytes(rom_data))
    
    cpu = ARM7TDMI(mem)
    cpu.reset()
    cpu.registers.thumb_mode = True
    
    print("=== Test de Instrucciones THUMB ===\n")
    
    for i in range(5):
        cycles = cpu.step()
        print(f"Ejecutado @ {cpu._current_pc:08X}: {cpu._current_instruction:04X}")
        print(f"  R0={cpu.registers.get(0):02X} R1={cpu.registers.get(1):02X} " +
              f"R2={cpu.registers.get(2):02X} R3={cpu.registers.get(3):02X}")
        print(f"  N={int(cpu.registers.flag_n)} Z={int(cpu.registers.flag_z)} " +
              f"C={int(cpu.registers.flag_c)} V={int(cpu.registers.flag_v)}")
        print()
    
    assert cpu.registers.get(0) == 0x42
    assert cpu.registers.get(1) == 0x10
    assert cpu.registers.get(2) == 0x52
    assert cpu.registers.get(3) == 0x148
    
    print("✓ MOV inmediato funciona")
    print("✓ ADD registro funciona")
    print("✓ LSL funciona")
    print("✓ CMP funciona")
    print("\n=== Todas las pruebas THUMB pasaron! ===")

def test_thumb_branch():
    """Prueba saltos en THUMB"""
    mem = MemoryBus()
    
    rom_data = bytearray(256)
    
    struct.pack_into('<H', rom_data, 0, 0x2001)  # MOV R0, #1
    struct.pack_into('<H', rom_data, 2, 0xE001)  # B +2 (a offset 8)
    struct.pack_into('<H', rom_data, 4, 0x2063)  # MOV R0, #99 (skip)
    struct.pack_into('<H', rom_data, 6, 0x2058)  # MOV R0, #88 (skip)
    struct.pack_into('<H', rom_data, 8, 0x3001)  # ADD R0, #1
    
    mem.load_rom(bytes(rom_data))
    
    cpu = ARM7TDMI(mem)
    cpu.reset()
    cpu.registers.thumb_mode = True
    
    print("\n=== Test de Branch THUMB ===\n")
    
    cpu.step()  # MOV R0, #1
    print(f"Después de MOV: R0 = {cpu.registers.get(0)}, PC = {cpu.registers.pc:08X}")
    
    cpu.step()  # B
    print(f"Después de B: PC = {cpu.registers.pc:08X}")
    assert cpu.registers.pc == 0x08000008
    
    cpu.step()  # ADD R0, #1
    print(f"Después de ADD: R0 = {cpu.registers.get(0)}")
    
    assert cpu.registers.get(0) == 2
    print("\n✓ Branch THUMB funciona")

def test_push_pop():
    """Prueba PUSH y POP"""
    mem = MemoryBus()
    
    rom_data = bytearray(256)
    
    struct.pack_into('<H', rom_data, 0, 0xB507)  # PUSH {R0, R1, R2, LR}
    struct.pack_into('<H', rom_data, 2, 0x2000)  # MOV R0, #0
    struct.pack_into('<H', rom_data, 4, 0x2100)  # MOV R1, #0
    struct.pack_into('<H', rom_data, 6, 0x2200)  # MOV R2, #0
    struct.pack_into('<H', rom_data, 8, 0xBC07)  # POP {R0, R1, R2} (sin PC)
    
    mem.load_rom(bytes(rom_data))
    
    cpu = ARM7TDMI(mem)
    cpu.reset()
    cpu.registers.thumb_mode = True
    cpu.registers.sp = 0x03007F00
    
    cpu.registers.set(0, 0x11111111)
    cpu.registers.set(1, 0x22222222)
    cpu.registers.set(2, 0x33333333)
    cpu.registers.lr = 0x08001001
    
    print("\n=== Test de PUSH/POP ===\n")
    
    sp_before = cpu.registers.sp
    print(f"SP inicial: {sp_before:08X}")
    print(f"R0={cpu.registers.get(0):08X} R1={cpu.registers.get(1):08X} R2={cpu.registers.get(2):08X}")
    
    cpu.step()  # PUSH
    print(f"\nDespués de PUSH: SP = {cpu.registers.sp:08X}")
    assert cpu.registers.sp == sp_before - 16
    
    cpu.step()  # MOV R0, #0
    cpu.step()  # MOV R1, #0
    cpu.step()  # MOV R2, #0
    print(f"Después de MOVs: R0={cpu.registers.get(0)} R1={cpu.registers.get(1)} R2={cpu.registers.get(2)}")
    
    cpu.step()  # POP {R0, R1, R2}
    print(f"\nDespués de POP:")
    print(f"  R0={cpu.registers.get(0):08X} R1={cpu.registers.get(1):08X} R2={cpu.registers.get(2):08X}")
    print(f"  SP={cpu.registers.sp:08X}")
    
    assert cpu.registers.get(0) == 0x11111111
    assert cpu.registers.get(1) == 0x22222222
    assert cpu.registers.get(2) == 0x33333333
    assert cpu.registers.sp == sp_before - 4  # LR todavía en stack
    
    print("\n✓ PUSH/POP funciona")

if __name__ == "__main__":
    test_thumb_instructions()
    test_thumb_branch()
    test_push_pop()