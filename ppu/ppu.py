"""
PPU (Picture Processing Unit) del GBA
Maneja todo el renderizado de gráficos
"""
import numpy as np
from typing import TYPE_CHECKING, Optional
from .sprites import SpriteRenderer

if TYPE_CHECKING:
    from memory.memory_bus import MemoryBus

# Constantes de timing
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
CYCLES_PER_PIXEL = 4
HDRAW_CYCLES = 960      # 240 * 4
HBLANK_CYCLES = 272     # 68 * 4
CYCLES_PER_LINE = 1232  # HDRAW + HBLANK
VDRAW_LINES = 160
VBLANK_LINES = 68
TOTAL_LINES = 228


class PPU:
    """
    Unidad de Procesamiento de Gráficos del GBA
    
    Renderiza línea por línea (scanline rendering)
    """
    
    def __init__(self, memory: 'MemoryBus'):
        self.memory = memory
        
        # Framebuffer
        self.framebuffer = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        
        # Estado de scanline
        self.vcount = 0
        self.cycle_counter = 0
        
        # DISPSTAT
        self._dispstat = 0
        self._vcount_target = 0
        
        # Frame ready flag
        self.frame_ready = False
        
        # Sprite renderer
        self.sprite_renderer = SpriteRenderer(memory)
        
        # Referencias affine internas
        self._bg2_internal_x = 0
        self._bg2_internal_y = 0
        self._bg3_internal_x = 0
        self._bg3_internal_y = 0
    
    def reset(self) -> None:
        """Reinicia la PPU"""
        self.vcount = 0
        self.cycle_counter = 0
        self._dispstat = 0
        self.framebuffer.fill(0)
        self.frame_ready = False
        
        self._bg2_internal_x = 0
        self._bg2_internal_y = 0
        self._bg3_internal_x = 0
        self._bg3_internal_y = 0
    
    @property
    def dispstat(self) -> int:
        """Lee DISPSTAT con estado actual"""
        value = self._dispstat & 0xFF38  # Preservar bits configurables
        
        # Bit 0: V-Blank flag
        if self.vcount >= VDRAW_LINES:
            value |= 0x0001
        
        # Bit 1: H-Blank flag
        if self.cycle_counter >= HDRAW_CYCLES:
            value |= 0x0002
        
        # Bit 2: V-Count match flag
        if self.vcount == self._vcount_target:
            value |= 0x0004
        
        return value
    
    def write_dispstat(self, value: int) -> None:
        """Escribe DISPSTAT"""
        # Solo bits 3-5 y 8-15 son escribibles
        self._dispstat = value & 0xFF38
        self._vcount_target = (value >> 8) & 0xFF
    
    def step(self, cycles: int) -> None:
        """
        Avanza la PPU por un número de ciclos
        
        Args:
            cycles: Ciclos de CPU a procesar
        """
        self.cycle_counter += cycles
        
        while self.cycle_counter >= CYCLES_PER_LINE:
            self.cycle_counter -= CYCLES_PER_LINE
            self._end_scanline()
    
    def _end_scanline(self) -> None:
        """Procesa el final de una scanline"""
        # Si estamos en V-Draw, renderizar la línea
        if self.vcount < VDRAW_LINES:
            self._render_scanline()
        
        # Actualizar referencias internas de BG affine al final de cada línea visible
        if self.vcount < VDRAW_LINES:
            self._update_affine_references()
        
        # Avanzar a la siguiente línea
        self.vcount += 1
        
        # Verificar interrupciones H-Blank
        if self._dispstat & 0x0010:  # H-Blank IRQ enable
            self.memory.request_interrupt(0x0002)  # H-Blank interrupt
        
        # Verificar V-Count match
        if self.vcount == self._vcount_target:
            if self._dispstat & 0x0020:  # V-Count IRQ enable
                self.memory.request_interrupt(0x0004)  # V-Count interrupt
        
        # Inicio de V-Blank
        if self.vcount == VDRAW_LINES:
            if self._dispstat & 0x0008:  # V-Blank IRQ enable
                self.memory.request_interrupt(0x0001)  # V-Blank interrupt
            
            # Recargar referencias internas de BG affine
            self._reload_affine_references()
            
            # Frame completo
            self.frame_ready = True
        
        # Fin del frame
        if self.vcount >= TOTAL_LINES:
            self.vcount = 0
    
    def _update_affine_references(self) -> None:
        """Actualiza las referencias internas de BG affine después de cada línea"""
        # BG2
        dmx = self._read_bg_param(0x22)  # BG2PB
        dmy = self._read_bg_param(0x26)  # BG2PD
        self._bg2_internal_x += self._sign_extend_16(dmx)
        self._bg2_internal_y += self._sign_extend_16(dmy)
        
        # BG3
        dmx = self._read_bg_param(0x32)  # BG3PB
        dmy = self._read_bg_param(0x36)  # BG3PD
        self._bg3_internal_x += self._sign_extend_16(dmx)
        self._bg3_internal_y += self._sign_extend_16(dmy)
    
    def _reload_affine_references(self) -> None:
        """Recarga las referencias internas desde los registros"""
        # BG2 reference point
        self._bg2_internal_x = self._read_bg_ref(0x28)  # BG2X
        self._bg2_internal_y = self._read_bg_ref(0x2C)  # BG2Y
        
        # BG3 reference point
        self._bg3_internal_x = self._read_bg_ref(0x38)  # BG3X
        self._bg3_internal_y = self._read_bg_ref(0x3C)  # BG3Y
    
    def _read_bg_param(self, offset: int) -> int:
        """Lee un parámetro de BG de 16 bits"""
        return int(self.memory.io_registers[offset]) | (int(self.memory.io_registers[offset + 1]) << 8)
    
    def _read_bg_ref(self, offset: int) -> int:
        """Lee un punto de referencia de BG de 28 bits (con signo)"""
        value = (int(self.memory.io_registers[offset]) |
                (int(self.memory.io_registers[offset + 1]) << 8) |
                (int(self.memory.io_registers[offset + 2]) << 16) |
                (int(self.memory.io_registers[offset + 3]) << 24))
        # Sign extend desde 28 bits
        if value & 0x08000000:
            value |= 0xF0000000
        return value
    
    def _sign_extend_16(self, value: int) -> int:
        """Extiende signo de 16 bits a 32 bits"""
        if value & 0x8000:
            return value | 0xFFFF0000
        return value
    
    def _render_scanline(self) -> None:
        """Renderiza una línea completa"""
        # Leer DISPCNT
        self._dispcnt = int(self.memory.io_registers[0]) | (int(self.memory.io_registers[1]) << 8)
        
        # Forced blank?
        if self._dispcnt & 0x0080:
            self.framebuffer[self.vcount, :] = [255, 255, 255]
            return
        
        bg_mode = self._dispcnt & 0x07
        
        # Inicializar línea con backdrop
        backdrop = self._get_palette_color(0)
        line = np.full((SCREEN_WIDTH, 3), backdrop, dtype=np.uint8)
        
        # Buffer de prioridades para BGs
        priority_buffer = np.full(SCREEN_WIDTH, 4, dtype=np.uint8)
        
        # Buffer de sprites para composición
        sprite_buffer = np.zeros((SCREEN_WIDTH, 4), dtype=np.uint8)
        
        # Renderizar BGs según el modo
        if bg_mode == 0:
            self._render_mode0(line, priority_buffer)
        elif bg_mode == 1:
            self._render_mode1(line, priority_buffer)
        elif bg_mode == 2:
            self._render_mode2(line, priority_buffer)
        elif bg_mode == 3:
            self._render_mode3(line)
        elif bg_mode == 4:
            self._render_mode4(line)
        elif bg_mode == 5:
            self._render_mode5(line)
        
        # Renderizar sprites (sobre los BGs)
        self.sprite_renderer.render_scanline(
            self.vcount, 
            self._dispcnt,
            line, 
            priority_buffer,
            sprite_buffer
        )
        
        self.framebuffer[self.vcount] = line
    
    def _get_palette_color(self, index: int, palette_bank: int = 0) -> tuple:
        """
        Obtiene un color de la paleta
        
        Args:
            index: Índice del color (0-255 para 8bpp, 0-15 para 4bpp)
            palette_bank: Banco de paleta (0-15, solo para 4bpp)
            
        Returns:
            Tupla (R, G, B) en formato 8-bit
        """
        if palette_bank > 0:
            index = palette_bank * 16 + (index & 0xF)
        
        addr = index * 2
        color16 = int(self.memory.palette_ram[addr]) | (int(self.memory.palette_ram[addr + 1]) << 8)
        
        return self._color15_to_24(color16)
    
    def _color15_to_24(self, color15: int) -> tuple:
        """Convierte color de 15-bit (5-5-5) a 24-bit (8-8-8)"""
        r = (color15 & 0x1F) << 3
        g = ((color15 >> 5) & 0x1F) << 3
        b = ((color15 >> 10) & 0x1F) << 3
        return (r, g, b)
    
    def _read_bgcnt(self, bg: int) -> int:
        """Lee el registro de control de un BG"""
        offset = 0x08 + bg * 2
        return int(self.memory.io_registers[offset]) | (int(self.memory.io_registers[offset + 1]) << 8)
    
    def _read_bg_scroll(self, bg: int) -> tuple:
        """Lee los offsets de scroll de un BG"""
        offset = 0x10 + bg * 4
        hofs = int(self.memory.io_registers[offset]) | (int(self.memory.io_registers[offset + 1]) << 8)
        vofs = int(self.memory.io_registers[offset + 2]) | (int(self.memory.io_registers[offset + 3]) << 8)
        return (hofs & 0x1FF, vofs & 0x1FF)
    
    # ===== Renderizado de Modos =====
    
    def _render_mode0(self, line: np.ndarray, priority_buffer: np.ndarray) -> None:
        """Modo 0: 4 BGs de texto"""
        # Renderizar de menor a mayor prioridad (3 -> 0)
        for priority in range(3, -1, -1):
            for bg in range(3, -1, -1):
                if self._dispcnt & (0x100 << bg):  # BG habilitado
                    bgcnt = self._read_bgcnt(bg)
                    if (bgcnt & 0x03) == priority:
                        self._render_text_bg(bg, line, priority_buffer, priority)
    
    def _render_mode1(self, line: np.ndarray, priority_buffer: np.ndarray) -> None:
        """Modo 1: 2 BGs texto + 1 BG affine"""
        for priority in range(3, -1, -1):
            # BG2 es affine
            if self._dispcnt & 0x400:  # BG2 enabled
                bgcnt = self._read_bgcnt(2)
                if (bgcnt & 0x03) == priority:
                    self._render_affine_bg(2, line, priority_buffer, priority)
            
            # BG0 y BG1 son texto
            for bg in [1, 0]:
                if self._dispcnt & (0x100 << bg):
                    bgcnt = self._read_bgcnt(bg)
                    if (bgcnt & 0x03) == priority:
                        self._render_text_bg(bg, line, priority_buffer, priority)
    
    def _render_mode2(self, line: np.ndarray, priority_buffer: np.ndarray) -> None:
        """Modo 2: 2 BGs affine"""
        for priority in range(3, -1, -1):
            for bg in [3, 2]:
                if self._dispcnt & (0x100 << bg):
                    bgcnt = self._read_bgcnt(bg)
                    if (bgcnt & 0x03) == priority:
                        self._render_affine_bg(bg, line, priority_buffer, priority)
    
    def _render_mode3(self, line: np.ndarray) -> None:
        """Modo 3: Bitmap 240x160 @ 15bpp"""
        if not (self._dispcnt & 0x400):  # BG2 debe estar habilitado
            return
        
        y = self.vcount
        for x in range(SCREEN_WIDTH):
            addr = (y * SCREEN_WIDTH + x) * 2
            color16 = int(self.memory.vram[addr]) | (int(self.memory.vram[addr + 1]) << 8)
            line[x] = self._color15_to_24(color16)
    
    def _render_mode4(self, line: np.ndarray) -> None:
        """Modo 4: Bitmap 240x160 @ 8bpp con paleta"""
        if not (self._dispcnt & 0x400):
            return
        
        # Frame select
        frame_offset = 0xA000 if (self._dispcnt & 0x10) else 0
        
        y = self.vcount
        for x in range(SCREEN_WIDTH):
            addr = frame_offset + y * SCREEN_WIDTH + x
            color_idx = int(self.memory.vram[addr])
            if color_idx != 0:  # 0 es transparente
                line[x] = self._get_palette_color(color_idx)
    
    def _render_mode5(self, line: np.ndarray) -> None:
        """Modo 5: Bitmap 160x128 @ 15bpp"""
        if not (self._dispcnt & 0x400):
            return
        
        # Frame select
        frame_offset = 0xA000 if (self._dispcnt & 0x10) else 0
        
        y = self.vcount
        if y >= 128:
            return
        
        for x in range(min(160, SCREEN_WIDTH)):
            addr = frame_offset + (y * 160 + x) * 2
            color16 = int(self.memory.vram[addr]) | (int(self.memory.vram[addr + 1]) << 8)
            line[x] = self._color15_to_24(color16)
    
    # ===== Renderizado de BGs de Texto =====
    
    def _render_text_bg(self, bg: int, line: np.ndarray, 
                        priority_buffer: np.ndarray, priority: int) -> None:
        """Renderiza un BG en modo texto (tiled)"""
        bgcnt = self._read_bgcnt(bg)
        hofs, vofs = self._read_bg_scroll(bg)
        
        # Configuración del BG
        char_base = ((bgcnt >> 2) & 0x03) * 0x4000
        screen_base = ((bgcnt >> 8) & 0x1F) * 0x800
        palette_mode = (bgcnt >> 7) & 1  # 0=16/16, 1=256/1
        screen_size = (bgcnt >> 14) & 0x03
        
        # Tamaño del mapa
        map_widths = [256, 512, 256, 512]
        map_heights = [256, 256, 512, 512]
        map_width = map_widths[screen_size]
        map_height = map_heights[screen_size]
        
        # Línea a renderizar (con scroll vertical)
        y = (self.vcount + vofs) % map_height
        tile_y = y // 8
        pixel_y = y % 8
        
        for screen_x in range(SCREEN_WIDTH):
            # Coordenada X con scroll
            x = (screen_x + hofs) % map_width
            tile_x = x // 8
            pixel_x = x % 8
            
            # Calcular offset en el tilemap
            # El mapa está dividido en bloques de 32x32 tiles
            screen_block = 0
            if map_width == 512 and tile_x >= 32:
                screen_block += 1
                tile_x -= 32
            if map_height == 512 and tile_y >= 32:
                screen_block += 2
                tile_y -= 32
            
            map_offset = screen_base + screen_block * 0x800 + (tile_y * 32 + tile_x) * 2
            
            # Leer entrada del tilemap
            tile_entry = int(self.memory.vram[map_offset]) | (int(self.memory.vram[map_offset + 1]) << 8)
            
            tile_num = tile_entry & 0x3FF
            h_flip = bool(tile_entry & 0x400)
            v_flip = bool(tile_entry & 0x800)
            palette_bank = (tile_entry >> 12) & 0xF
            
            # Aplicar flips
            px = 7 - pixel_x if h_flip else pixel_x
            py = 7 - pixel_y if v_flip else pixel_y
            
            # Leer pixel del tile
            if palette_mode == 0:  # 4bpp
                tile_addr = char_base + tile_num * 32 + py * 4 + px // 2
                byte = int(self.memory.vram[tile_addr])
                color_idx = (byte >> 4) if (px & 1) else (byte & 0xF)
                
                if color_idx != 0:  # Transparente
                    if priority <= priority_buffer[screen_x]:
                        line[screen_x] = self._get_palette_color(color_idx, palette_bank)
                        priority_buffer[screen_x] = priority
            else:  # 8bpp
                tile_addr = char_base + tile_num * 64 + py * 8 + px
                color_idx = int(self.memory.vram[tile_addr])
                
                if color_idx != 0:
                    if priority <= priority_buffer[screen_x]:
                        line[screen_x] = self._get_palette_color(color_idx)
                        priority_buffer[screen_x] = priority
    
    # ===== Renderizado de BGs Affine =====
    
    def _render_affine_bg(self, bg: int, line: np.ndarray,
                          priority_buffer: np.ndarray, priority: int) -> None:
        """Renderiza un BG en modo affine (rotación/escala)"""
        bgcnt = self._read_bgcnt(bg)
        
        char_base = ((bgcnt >> 2) & 0x03) * 0x4000
        screen_base = ((bgcnt >> 8) & 0x1F) * 0x800
        wraparound = bool(bgcnt & 0x2000)
        screen_size = (bgcnt >> 14) & 0x03
        
        # Tamaño del mapa affine
        affine_sizes = [128, 256, 512, 1024]
        map_size = affine_sizes[screen_size]
        tiles_per_row = map_size // 8
        
        # Obtener referencias internas
        if bg == 2:
            ref_x = self._bg2_internal_x
            ref_y = self._bg2_internal_y
            pa = self._sign_extend_16(self._read_bg_param(0x20))  # BG2PA
            pc = self._sign_extend_16(self._read_bg_param(0x24))  # BG2PC
        else:  # bg == 3
            ref_x = self._bg3_internal_x
            ref_y = self._bg3_internal_y
            pa = self._sign_extend_16(self._read_bg_param(0x30))  # BG3PA
            pc = self._sign_extend_16(self._read_bg_param(0x34))  # BG3PC
        
        # Punto inicial para esta línea
        x_acc = ref_x
        y_acc = ref_y
        
        for screen_x in range(SCREEN_WIDTH):
            # Convertir coordenadas fijas 8.8 a enteros
            tx = x_acc >> 8
            ty = y_acc >> 8
            
            # Verificar si está dentro del mapa
            in_bounds = True
            if not wraparound:
                if tx < 0 or tx >= map_size or ty < 0 or ty >= map_size:
                    in_bounds = False
            else:
                tx = tx % map_size
                ty = ty % map_size
                if tx < 0:
                    tx += map_size
                if ty < 0:
                    ty += map_size
            
            if in_bounds:
                tile_x = tx // 8
                tile_y = ty // 8
                pixel_x = tx % 8
                pixel_y = ty % 8
                
                # Leer tile del mapa (8bpp siempre para affine)
                map_offset = screen_base + tile_y * tiles_per_row + tile_x
                tile_num = int(self.memory.vram[map_offset])
                
                # Leer pixel
                tile_addr = char_base + tile_num * 64 + pixel_y * 8 + pixel_x
                color_idx = int(self.memory.vram[tile_addr])
                
                if color_idx != 0:
                    if priority <= priority_buffer[screen_x]:
                        line[screen_x] = self._get_palette_color(color_idx)
                        priority_buffer[screen_x] = priority
            
            # Avanzar en la textura
            x_acc += pa
            y_acc += pc