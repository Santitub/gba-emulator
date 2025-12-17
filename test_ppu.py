# test_ppu.py
import numpy as np
from memory.memory_bus import MemoryBus
from ppu.ppu import PPU

def test_ppu_init():
    """Prueba inicialización de la PPU"""
    mem = MemoryBus()
    ppu = PPU(mem)
    
    print("=== Test de PPU Inicialización ===\n")
    
    assert ppu.vcount == 0
    assert ppu.framebuffer.shape == (160, 240, 3)
    
    print("✓ PPU inicializada correctamente")
    print(f"  Framebuffer: {ppu.framebuffer.shape}")

def test_ppu_timing():
    """Prueba el timing de la PPU"""
    mem = MemoryBus()
    ppu = PPU(mem)
    
    print("\n=== Test de PPU Timing ===\n")
    
    # Una línea completa
    ppu.step(1232)
    assert ppu.vcount == 1, f"VCOUNT debería ser 1, es {ppu.vcount}"
    print("✓ Una scanline = 1232 ciclos")
    
    # Completar V-Draw (160 líneas)
    ppu.reset()
    for _ in range(160):
        ppu.step(1232)
    assert ppu.vcount == 160, f"VCOUNT debería ser 160, es {ppu.vcount}"
    print("✓ V-Draw = 160 líneas")
    
    # Verificar flag de V-Blank
    assert ppu.dispstat & 0x01, "Flag V-Blank debería estar activo"
    print("✓ Flag V-Blank activo en línea 160")
    
    # Completar frame (228 líneas totales)
    for _ in range(68):
        ppu.step(1232)
    assert ppu.vcount == 0, f"VCOUNT debería volver a 0, es {ppu.vcount}"
    print("✓ Frame completo = 228 líneas")
    
    print("\n=== Test de Timing completado ===")

def test_mode3_rendering():
    """Prueba renderizado en Modo 3 (bitmap 15bpp)"""
    mem = MemoryBus()
    ppu = PPU(mem)
    
    print("\n=== Test de Modo 3 ===\n")
    
    # Configurar DISPCNT para Modo 3, BG2 habilitado
    # Mode 3 = 0x0003, BG2 = 0x0400
    mem.io_registers[0] = 0x03
    mem.io_registers[1] = 0x04
    
    # Dibujar algunos píxeles en VRAM (formato BGR555)
    # Rojo: 0x001F (R=31, G=0, B=0)
    # Verde: 0x03E0 (R=0, G=31, B=0)
    # Azul: 0x7C00 (R=0, G=0, B=31)
    
    # Pixel (0,0) = Rojo
    mem.vram[0] = 0x1F
    mem.vram[1] = 0x00
    
    # Pixel (1,0) = Verde
    mem.vram[2] = 0xE0
    mem.vram[3] = 0x03
    
    # Pixel (2,0) = Azul
    mem.vram[4] = 0x00
    mem.vram[5] = 0x7C
    
    # Pixel (3,0) = Blanco (0x7FFF)
    mem.vram[6] = 0xFF
    mem.vram[7] = 0x7F
    
    # Renderizar primera línea
    ppu._render_scanline()
    
    # Verificar colores (RGB en formato 8-bit)
    fb = ppu.framebuffer
    
    # Rojo (R=248, G=0, B=0) - 31 << 3 = 248
    assert fb[0, 0, 0] == 248, f"Rojo R debería ser 248, es {fb[0, 0, 0]}"
    assert fb[0, 0, 1] == 0, f"Rojo G debería ser 0, es {fb[0, 0, 1]}"
    assert fb[0, 0, 2] == 0, f"Rojo B debería ser 0, es {fb[0, 0, 2]}"
    print(f"✓ Pixel rojo: RGB({fb[0, 0, 0]}, {fb[0, 0, 1]}, {fb[0, 0, 2]})")
    
    # Verde
    assert fb[0, 1, 1] == 248, f"Verde G debería ser 248, es {fb[0, 1, 1]}"
    print(f"✓ Pixel verde: RGB({fb[0, 1, 0]}, {fb[0, 1, 1]}, {fb[0, 1, 2]})")
    
    # Azul
    assert fb[0, 2, 2] == 248, f"Azul B debería ser 248, es {fb[0, 2, 2]}"
    print(f"✓ Pixel azul: RGB({fb[0, 2, 0]}, {fb[0, 2, 1]}, {fb[0, 2, 2]})")
    
    # Blanco
    assert fb[0, 3, 0] == 248 and fb[0, 3, 1] == 248 and fb[0, 3, 2] == 248
    print(f"✓ Pixel blanco: RGB({fb[0, 3, 0]}, {fb[0, 3, 1]}, {fb[0, 3, 2]})")
    
    print("\n=== Test de Modo 3 completado ===")

def test_mode4_rendering():
    """Prueba renderizado en Modo 4 (bitmap 8bpp con paleta)"""
    mem = MemoryBus()
    ppu = PPU(mem)
    
    print("\n=== Test de Modo 4 ===\n")
    
    # Configurar DISPCNT para Modo 4, BG2 habilitado
    mem.io_registers[0] = 0x04
    mem.io_registers[1] = 0x04
    
    # Configurar paleta
    # Color 1 = Rojo
    mem.palette_ram[2] = 0x1F
    mem.palette_ram[3] = 0x00
    
    # Color 2 = Verde
    mem.palette_ram[4] = 0xE0
    mem.palette_ram[5] = 0x03
    
    # Escribir píxeles en VRAM (índices de paleta)
    mem.vram[0] = 1  # Pixel (0,0) = Color 1 (Rojo)
    mem.vram[1] = 2  # Pixel (1,0) = Color 2 (Verde)
    mem.vram[2] = 0  # Pixel (2,0) = Color 0 (Transparente/Backdrop)
    
    # Renderizar primera línea
    ppu._render_scanline()
    
    fb = ppu.framebuffer
    
    print(f"Pixel 0: RGB({fb[0, 0, 0]}, {fb[0, 0, 1]}, {fb[0, 0, 2]})")
    print(f"Pixel 1: RGB({fb[0, 1, 0]}, {fb[0, 1, 1]}, {fb[0, 1, 2]})")
    print(f"Pixel 2: RGB({fb[0, 2, 0]}, {fb[0, 2, 1]}, {fb[0, 2, 2]})")
    
    assert fb[0, 0, 0] == 248, "Pixel 0 debería ser rojo"
    assert fb[0, 1, 1] == 248, "Pixel 1 debería ser verde"
    
    print("✓ Modo 4 funciona correctamente")
    
    print("\n=== Test de Modo 4 completado ===")

def test_palette():
    """Prueba la conversión de paleta"""
    mem = MemoryBus()
    ppu = PPU(mem)
    
    print("\n=== Test de Paleta ===\n")
    
    # Probar conversión de colores
    # 15-bit: XBBBBBGGGGGRRRRR
    
    test_cases = [
        (0x0000, (0, 0, 0)),       # Negro
        (0x7FFF, (248, 248, 248)), # Blanco
        (0x001F, (248, 0, 0)),     # Rojo
        (0x03E0, (0, 248, 0)),     # Verde
        (0x7C00, (0, 0, 248)),     # Azul
    ]
    
    for color15, expected in test_cases:
        result = ppu._color15_to_24(color15)
        assert result == expected, f"Color {color15:04X}: esperado {expected}, obtenido {result}"
        print(f"✓ 0x{color15:04X} -> RGB{result}")
    
    print("\n=== Test de Paleta completado ===")

if __name__ == "__main__":
    test_ppu_init()
    test_ppu_timing()
    test_palette()
    test_mode3_rendering()
    test_mode4_rendering()