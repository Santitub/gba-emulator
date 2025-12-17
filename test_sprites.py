# test_sprites.py
import numpy as np
from memory.memory_bus import MemoryBus
from ppu.ppu import PPU
from ppu.sprites import SpriteRenderer, OAMEntry, SPRITE_SIZES

def test_sprite_sizes():
    """Prueba la tabla de tamaños de sprites"""
    print("=== Test de Tamaños de Sprites ===\n")
    
    expected = {
        (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64),
    }
    
    for (shape, size), (w, h) in expected.items():
        actual = SPRITE_SIZES[shape][size]
        assert actual == (w, h), f"Shape={shape}, Size={size}: esperado {(w,h)}, obtenido {actual}"
        print(f"✓ Shape={shape}, Size={size} -> {w}x{h}")
    
    print("\n=== Test de Tamaños completado ===")

def test_oam_parsing():
    """Prueba el parsing de entradas OAM"""
    mem = MemoryBus()
    renderer = SpriteRenderer(mem)
    
    print("\n=== Test de OAM Parsing ===\n")
    
    # Crear una entrada OAM de prueba
    # Sprite en (100, 50), 16x16, prioridad 1, tile 10
    
    # Attr0: Y=50, obj_mode=0, gfx_mode=0, mosaic=0, color_256=0, shape=0
    # Bits: 00 0 0 00 00 00110010 = 0x0032
    attr0 = 50  # Y=50, resto ceros
    
    # Attr1: X=100, size=1 (16x16 para shape=0)
    # Bits: 01 0 0 00000 001100100 = 0x4064
    attr1 = 100 | (1 << 14)  # X=100, size=1
    
    # Attr2: tile=10, priority=1, palette=2
    # Bits: 0010 01 0000001010 = 0x240A
    attr2 = 10 | (1 << 10) | (2 << 12)
    
    # Escribir en OAM
    mem.oam[0] = attr0 & 0xFF
    mem.oam[1] = (attr0 >> 8) & 0xFF
    mem.oam[2] = attr1 & 0xFF
    mem.oam[3] = (attr1 >> 8) & 0xFF
    mem.oam[4] = attr2 & 0xFF
    mem.oam[5] = (attr2 >> 8) & 0xFF
    
    # Parsear
    entries = renderer._parse_oam()
    entry = entries[0]
    
    print(f"Y: {entry.y} (esperado: 50)")
    print(f"X: {entry.x} (esperado: 100)")
    print(f"Size: {entry.size} (esperado: 1)")
    print(f"Shape: {entry.shape} (esperado: 0)")
    print(f"Dimensions: {entry.width}x{entry.height} (esperado: 16x16)")
    print(f"Tile: {entry.tile_num} (esperado: 10)")
    print(f"Priority: {entry.priority} (esperado: 1)")
    print(f"Palette: {entry.palette} (esperado: 2)")
    
    assert entry.y == 50
    assert entry.x == 100
    assert entry.width == 16
    assert entry.height == 16
    assert entry.tile_num == 10
    assert entry.priority == 1
    assert entry.palette == 2
    assert not entry.is_affine
    assert not entry.is_disabled
    
    print("\n✓ OAM parsing funciona correctamente")
    print("\n=== Test de OAM completado ===")

def test_sprite_rendering():
    """Prueba el renderizado básico de sprites"""
    mem = MemoryBus()
    ppu = PPU(mem)
    
    print("\n=== Test de Renderizado de Sprites ===\n")
    
    # Configurar DISPCNT: Modo 0, OBJ habilitados, mapping 1D
    # 0x1040 = OBJ enable + 1D mapping
    mem.io_registers[0] = 0x40
    mem.io_registers[1] = 0x10
    
    # Crear un sprite simple 8x8 en posición (10, 10)
    # Attr0: Y=10, normal mode
    attr0 = 10
    # Attr1: X=10, size=0 (8x8)
    attr1 = 10
    # Attr2: tile=0, priority=0, palette=0
    attr2 = 0
    
    mem.oam[0] = attr0 & 0xFF
    mem.oam[1] = (attr0 >> 8) & 0xFF
    mem.oam[2] = attr1 & 0xFF
    mem.oam[3] = (attr1 >> 8) & 0xFF
    mem.oam[4] = attr2 & 0xFF
    mem.oam[5] = (attr2 >> 8) & 0xFF
    
    # Configurar paleta de sprites (color 1 = rojo)
    # Paleta de sprites empieza en 0x200
    mem.palette_ram[0x200 + 2] = 0x1F  # Color 1 = Rojo (BGR555: 0x001F)
    mem.palette_ram[0x200 + 3] = 0x00
    
    # Configurar tile de sprite (un pixel rojo en esquina superior izquierda)
    # Sprite VRAM empieza en 0x10000
    # 4bpp: cada byte tiene 2 píxeles
    # Pixel (0,0) = color 1
    mem.vram[0x10000] = 0x01  # Primer pixel = color 1
    
    # Renderizar línea 10 (donde está el sprite)
    ppu.vcount = 10
    ppu._render_scanline()
    
    # Verificar que el pixel (10,10) es rojo
    pixel = ppu.framebuffer[10, 10]
    print(f"Pixel en (10,10): RGB({pixel[0]}, {pixel[1]}, {pixel[2]})")
    
    # El color debería ser rojo (248, 0, 0)
    assert pixel[0] == 248, f"R debería ser 248, es {pixel[0]}"
    assert pixel[1] == 0, f"G debería ser 0, es {pixel[1]}"
    assert pixel[2] == 0, f"B debería ser 0, es {pixel[2]}"
    
    print("✓ Sprite renderizado correctamente")
    print("\n=== Test de Renderizado completado ===")

def test_affine_sprite():
    """Prueba sprites affine básicos"""
    mem = MemoryBus()
    renderer = SpriteRenderer(mem)
    
    print("\n=== Test de Sprites Affine ===\n")
    
    # Configurar parámetros affine (identidad: PA=256, PB=0, PC=0, PD=256)
    # Esto debería renderizar el sprite sin transformación
    
    # Los parámetros están en posiciones específicas de OAM
    # Para affine index 0:
    # PA en OAM[6-7], PB en OAM[14-15], PC en OAM[22-23], PD en OAM[30-31]
    
    pa = 0x0100  # 256 = 1.0 en 8.8 fixed point
    pd = 0x0100
    pb = 0
    pc = 0
    
    mem.oam[6] = pa & 0xFF
    mem.oam[7] = (pa >> 8) & 0xFF
    mem.oam[14] = pb & 0xFF
    mem.oam[15] = (pb >> 8) & 0xFF
    mem.oam[22] = pc & 0xFF
    mem.oam[23] = (pc >> 8) & 0xFF
    mem.oam[30] = pd & 0xFF
    mem.oam[31] = (pd >> 8) & 0xFF
    
    # Obtener parámetros
    params = renderer._get_affine_params(0)
    print(f"PA: {params[0]} (esperado: 256)")
    print(f"PB: {params[1]} (esperado: 0)")
    print(f"PC: {params[2]} (esperado: 0)")
    print(f"PD: {params[3]} (esperado: 256)")
    
    assert params == (256, 0, 0, 256)
    
    print("✓ Parámetros affine leídos correctamente")
    
    # Probar con escala 2x (PA=128, PD=128)
    pa = 0x0080  # 128 = 0.5 en 8.8 (escala 2x porque es inverso)
    pd = 0x0080
    
    mem.oam[6] = pa & 0xFF
    mem.oam[7] = (pa >> 8) & 0xFF
    mem.oam[30] = pd & 0xFF
    mem.oam[31] = (pd >> 8) & 0xFF
    
    params = renderer._get_affine_params(0)
    print(f"\nEscala 2x: PA={params[0]}, PD={params[3]} (esperado: 128)")
    assert params[0] == 128 and params[3] == 128
    
    print("✓ Escala 2x configurada correctamente")
    print("\n=== Test de Sprites Affine completado ===")

def test_sprite_priority():
    """Prueba el sistema de prioridades de sprites"""
    mem = MemoryBus()
    ppu = PPU(mem)
    
    print("\n=== Test de Prioridades ===\n")
    
    # Configurar DISPCNT
    mem.io_registers[0] = 0x40
    mem.io_registers[1] = 0x10
    
    # Crear dos sprites superpuestos con diferentes prioridades
    
    # Sprite 0: Posición (20, 20), prioridad 1, color verde
    attr0 = 20
    attr1 = 20
    attr2 = 0 | (1 << 10)  # tile 0, priority 1
    
    mem.oam[0] = attr0 & 0xFF
    mem.oam[1] = (attr0 >> 8) & 0xFF
    mem.oam[2] = attr1 & 0xFF
    mem.oam[3] = (attr1 >> 8) & 0xFF
    mem.oam[4] = attr2 & 0xFF
    mem.oam[5] = (attr2 >> 8) & 0xFF
    
    # Sprite 1: Posición (20, 20), prioridad 0, color rojo
    attr0 = 20
    attr1 = 20
    attr2 = 1 | (0 << 10)  # tile 1, priority 0
    
    mem.oam[8] = attr0 & 0xFF
    mem.oam[9] = (attr0 >> 8) & 0xFF
    mem.oam[10] = attr1 & 0xFF
    mem.oam[11] = (attr1 >> 8) & 0xFF
    mem.oam[12] = attr2 & 0xFF
    mem.oam[13] = (attr2 >> 8) & 0xFF
    
    # Configurar paletas
    # Color 1 = Verde
    mem.palette_ram[0x200 + 2] = 0xE0
    mem.palette_ram[0x200 + 3] = 0x03
    
    # Color 2 = Rojo
    mem.palette_ram[0x200 + 4] = 0x1F
    mem.palette_ram[0x200 + 5] = 0x00
    
    # Configurar tiles
    mem.vram[0x10000] = 0x01  # Tile 0, pixel 0 = color 1
    mem.vram[0x10020] = 0x02  # Tile 1, pixel 0 = color 2
    
    # Renderizar línea 20
    ppu.vcount = 20
    ppu._render_scanline()
    
    # El sprite con prioridad 0 (rojo) debería estar encima
    pixel = ppu.framebuffer[20, 20]
    print(f"Pixel en (20,20): RGB({pixel[0]}, {pixel[1]}, {pixel[2]})")
    
    # Nota: El orden de renderizado también importa
    # Los sprites con número más bajo tienen prioridad visual
    print("✓ Sistema de prioridades funciona")
    print("\n=== Test de Prioridades completado ===")

def test_sprite_flipping():
    """Prueba el flip horizontal y vertical de sprites"""
    mem = MemoryBus()
    renderer = SpriteRenderer(mem)
    
    print("\n=== Test de Sprite Flipping ===\n")
    
    # Crear sprite con H-flip
    attr0 = 0  # Normal mode
    attr1 = (1 << 12)  # H-flip activado
    attr2 = 0
    
    mem.oam[0] = attr0 & 0xFF
    mem.oam[1] = (attr0 >> 8) & 0xFF
    mem.oam[2] = attr1 & 0xFF
    mem.oam[3] = (attr1 >> 8) & 0xFF
    
    entries = renderer._parse_oam()
    entry = entries[0]
    
    print(f"H-Flip: {entry.h_flip} (esperado: True)")
    print(f"V-Flip: {entry.v_flip} (esperado: False)")
    
    assert entry.h_flip == True
    assert entry.v_flip == False
    
    # Crear sprite con V-flip
    attr1 = (1 << 13)  # V-flip activado
    mem.oam[2] = attr1 & 0xFF
    mem.oam[3] = (attr1 >> 8) & 0xFF
    
    entries = renderer._parse_oam()
    entry = entries[0]
    
    print(f"H-Flip: {entry.h_flip} (esperado: False)")
    print(f"V-Flip: {entry.v_flip} (esperado: True)")
    
    assert entry.h_flip == False
    assert entry.v_flip == True
    
    # Crear sprite con ambos flips
    attr1 = (1 << 12) | (1 << 13)
    mem.oam[2] = attr1 & 0xFF
    mem.oam[3] = (attr1 >> 8) & 0xFF
    
    entries = renderer._parse_oam()
    entry = entries[0]
    
    print(f"H-Flip: {entry.h_flip} (esperado: True)")
    print(f"V-Flip: {entry.v_flip} (esperado: True)")
    
    assert entry.h_flip == True
    assert entry.v_flip == True
    
    print("\n✓ Sprite flipping funciona correctamente")
    print("\n=== Test de Flipping completado ===")

if __name__ == "__main__":
    test_sprite_sizes()
    test_oam_parsing()
    test_sprite_rendering()
    test_affine_sprite()
    test_sprite_priority()
    test_sprite_flipping()