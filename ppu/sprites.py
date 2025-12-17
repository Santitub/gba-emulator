"""
Sistema de Sprites del GBA
Maneja OAM y renderizado de sprites
"""
import numpy as np
from typing import TYPE_CHECKING, List, Tuple, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from memory.memory_bus import MemoryBus


# Tabla de tamaños de sprites [shape][size] = (width, height)
SPRITE_SIZES = [
    # Shape 0: Square
    [(8, 8), (16, 16), (32, 32), (64, 64)],
    # Shape 1: Horizontal
    [(16, 8), (32, 8), (32, 16), (64, 32)],
    # Shape 2: Vertical
    [(8, 16), (8, 32), (16, 32), (32, 64)],
    # Shape 3: Prohibited
    [(0, 0), (0, 0), (0, 0), (0, 0)],
]


@dataclass
class OAMEntry:
    """Representa una entrada en OAM"""
    # Atributo 0
    y: int
    obj_mode: int      # 0=Normal, 1=Affine, 2=Disable, 3=Affine Double
    gfx_mode: int      # 0=Normal, 1=Semi-Trans, 2=ObjWindow
    mosaic: bool
    color_256: bool    # True=256 colores, False=16 colores
    shape: int         # 0=Square, 1=Horizontal, 2=Vertical
    
    # Atributo 1
    x: int
    affine_index: int  # Para sprites affine
    h_flip: bool       # Para sprites normales
    v_flip: bool       # Para sprites normales
    size: int          # 0-3
    
    # Atributo 2
    tile_num: int
    priority: int      # 0-3
    palette: int       # 0-15 (solo para 4bpp)
    
    @property
    def width(self) -> int:
        return SPRITE_SIZES[self.shape][self.size][0]
    
    @property
    def height(self) -> int:
        return SPRITE_SIZES[self.shape][self.size][1]
    
    @property
    def is_affine(self) -> bool:
        return self.obj_mode in (1, 3)
    
    @property
    def is_double_size(self) -> bool:
        return self.obj_mode == 3
    
    @property
    def is_disabled(self) -> bool:
        return self.obj_mode == 2
    
    @property
    def render_width(self) -> int:
        """Ancho de renderizado (doble para affine double)"""
        if self.is_double_size:
            return self.width * 2
        return self.width
    
    @property
    def render_height(self) -> int:
        """Alto de renderizado (doble para affine double)"""
        if self.is_double_size:
            return self.height * 2
        return self.height


class SpriteRenderer:
    """
    Renderizador de sprites del GBA
    """
    
    def __init__(self, memory: 'MemoryBus'):
        self.memory = memory
        
        # Cache de OAM entries
        self._oam_cache: List[OAMEntry] = []
        self._oam_dirty = True
        
        # Base de VRAM para sprites
        self.sprite_vram_base = 0x10000  # Offset en VRAM
        
    def _parse_oam(self) -> List[OAMEntry]:
        """Parsea todas las entradas de OAM"""
        entries = []
        
        for i in range(128):
            offset = i * 8
            
            # Leer atributos
            attr0 = int(self.memory.oam[offset]) | (int(self.memory.oam[offset + 1]) << 8)
            attr1 = int(self.memory.oam[offset + 2]) | (int(self.memory.oam[offset + 3]) << 8)
            attr2 = int(self.memory.oam[offset + 4]) | (int(self.memory.oam[offset + 5]) << 8)
            
            entry = OAMEntry(
                # Attr 0
                y=attr0 & 0xFF,
                obj_mode=(attr0 >> 8) & 0x03,
                gfx_mode=(attr0 >> 10) & 0x03,
                mosaic=bool(attr0 & 0x1000),
                color_256=bool(attr0 & 0x2000),
                shape=(attr0 >> 14) & 0x03,
                
                # Attr 1
                x=attr1 & 0x1FF,
                affine_index=(attr1 >> 9) & 0x1F,
                h_flip=bool(attr1 & 0x1000) and not ((attr0 >> 8) & 0x01),
                v_flip=bool(attr1 & 0x2000) and not ((attr0 >> 8) & 0x01),
                size=(attr1 >> 14) & 0x03,
                
                # Attr 2
                tile_num=attr2 & 0x3FF,
                priority=(attr2 >> 10) & 0x03,
                palette=(attr2 >> 12) & 0x0F,
            )
            
            entries.append(entry)
        
        return entries
    
    def _get_affine_params(self, index: int) -> Tuple[int, int, int, int]:
        """
        Obtiene los parámetros affine para un índice dado
        
        Returns:
            (PA, PB, PC, PD) como enteros con signo de 16 bits (8.8 fixed point)
        """
        # Los parámetros affine están en OAM, intercalados con los atributos
        # Cada grupo de 4 sprites comparte un conjunto de parámetros
        base = index * 32  # 4 sprites * 8 bytes
        
        pa = int(self.memory.oam[base + 6]) | (int(self.memory.oam[base + 7]) << 8)
        pb = int(self.memory.oam[base + 14]) | (int(self.memory.oam[base + 15]) << 8)
        pc = int(self.memory.oam[base + 22]) | (int(self.memory.oam[base + 23]) << 8)
        pd = int(self.memory.oam[base + 30]) | (int(self.memory.oam[base + 31]) << 8)
        
        # Convertir a signed
        if pa >= 0x8000: pa -= 0x10000
        if pb >= 0x8000: pb -= 0x10000
        if pc >= 0x8000: pc -= 0x10000
        if pd >= 0x8000: pd -= 0x10000
        
        return (pa, pb, pc, pd)
    
    def render_scanline(self, line_y: int, dispcnt: int,
                        line_buffer: np.ndarray,
                        priority_buffer: np.ndarray,
                        sprite_buffer: np.ndarray) -> None:
        """
        Renderiza todos los sprites para una scanline
        
        Args:
            line_y: Línea actual (0-159)
            dispcnt: Valor de DISPCNT
            line_buffer: Buffer de píxeles RGB (240, 3)
            priority_buffer: Buffer de prioridades (240,)
            sprite_buffer: Buffer de sprites para blending (240, 4) [R,G,B,priority]
        """
        if not (dispcnt & 0x1000):  # OBJ no habilitado
            return
        
        # Modo de mapeo: 0=2D, 1=1D
        mapping_1d = bool(dispcnt & 0x0040)
        
        # Parsear OAM
        entries = self._parse_oam()
        
        # Procesar sprites en orden inverso (sprite 0 tiene mayor prioridad visual)
        for entry in reversed(entries):
            if entry.is_disabled:
                continue
            
            if entry.width == 0 or entry.height == 0:
                continue
            
            self._render_sprite_line(entry, line_y, mapping_1d, 
                                    line_buffer, priority_buffer, sprite_buffer)
    
    def _render_sprite_line(self, entry: OAMEntry, line_y: int, mapping_1d: bool,
                            line_buffer: np.ndarray,
                            priority_buffer: np.ndarray,
                            sprite_buffer: np.ndarray) -> None:
        """Renderiza una línea de un sprite"""
        
        # Calcular posición Y del sprite (con wrap-around)
        sprite_y = entry.y
        if sprite_y >= 160:
            sprite_y -= 256
        
        render_height = entry.render_height
        render_width = entry.render_width
        
        # ¿Esta línea intersecta con el sprite?
        local_y = line_y - sprite_y
        if local_y < 0 or local_y >= render_height:
            return
        
        # Calcular posición X (con wrap-around)
        sprite_x = entry.x
        if sprite_x >= 240:
            sprite_x -= 512
        
        if entry.is_affine:
            self._render_affine_sprite_line(entry, line_y, local_y, sprite_x, sprite_y,
                                           mapping_1d, line_buffer, priority_buffer, sprite_buffer)
        else:
            self._render_normal_sprite_line(entry, local_y, sprite_x,
                                           mapping_1d, line_buffer, priority_buffer, sprite_buffer)
    
    def _render_normal_sprite_line(self, entry: OAMEntry, local_y: int, sprite_x: int,
                                   mapping_1d: bool,
                                   line_buffer: np.ndarray,
                                   priority_buffer: np.ndarray,
                                   sprite_buffer: np.ndarray) -> None:
        """Renderiza una línea de un sprite normal (sin transformación)"""
        
        width = entry.width
        height = entry.height
        
        # Aplicar V-Flip
        tex_y = (height - 1 - local_y) if entry.v_flip else local_y
        
        for local_x in range(width):
            screen_x = sprite_x + local_x
            
            if screen_x < 0 or screen_x >= 240:
                continue
            
            # Aplicar H-Flip
            tex_x = (width - 1 - local_x) if entry.h_flip else local_x
            
            # Obtener color del pixel
            color = self._get_sprite_pixel(entry, tex_x, tex_y, mapping_1d)
            
            if color is not None:
                # Verificar prioridad
                if entry.priority <= priority_buffer[screen_x]:
                    line_buffer[screen_x] = color[:3]
                    priority_buffer[screen_x] = entry.priority
                
                # Guardar para blending
                sprite_buffer[screen_x] = (*color[:3], entry.priority)
    
    def _render_affine_sprite_line(self, entry: OAMEntry, line_y: int, local_y: int,
                                   sprite_x: int, sprite_y: int,
                                   mapping_1d: bool,
                                   line_buffer: np.ndarray,
                                   priority_buffer: np.ndarray,
                                   sprite_buffer: np.ndarray) -> None:
        """Renderiza una línea de un sprite affine (con transformación)"""
        
        width = entry.width
        height = entry.height
        render_width = entry.render_width
        render_height = entry.render_height
        
        # Centro del sprite
        cx = render_width // 2
        cy = render_height // 2
        
        # Obtener parámetros affine
        pa, pb, pc, pd = self._get_affine_params(entry.affine_index)
        
        for local_x in range(render_width):
            screen_x = sprite_x + local_x
            
            if screen_x < 0 or screen_x >= 240:
                continue
            
            # Transformación affine inversa
            # Queremos encontrar (tex_x, tex_y) dado (local_x, local_y)
            dx = local_x - cx
            dy = local_y - cy
            
            # Aplicar transformación (8.8 fixed point)
            tex_x = ((pa * dx + pb * dy) >> 8) + (width // 2)
            tex_y = ((pc * dx + pd * dy) >> 8) + (height // 2)
            
            # Verificar límites
            if tex_x < 0 or tex_x >= width or tex_y < 0 or tex_y >= height:
                continue
            
            # Obtener color del pixel
            color = self._get_sprite_pixel(entry, tex_x, tex_y, mapping_1d)
            
            if color is not None:
                if entry.priority <= priority_buffer[screen_x]:
                    line_buffer[screen_x] = color[:3]
                    priority_buffer[screen_x] = entry.priority
                
                sprite_buffer[screen_x] = (*color[:3], entry.priority)
    
    def _get_sprite_pixel(self, entry: OAMEntry, tex_x: int, tex_y: int,
                          mapping_1d: bool) -> Optional[Tuple[int, int, int]]:
        """
        Obtiene el color de un pixel del sprite
        
        Returns:
            Tupla (R, G, B) o None si es transparente
        """
        tile_x = tex_x // 8
        tile_y = tex_y // 8
        pixel_x = tex_x % 8
        pixel_y = tex_y % 8
        
        tiles_per_row = entry.width // 8
        
        if entry.color_256:  # 8bpp
            if mapping_1d:
                # Mapeo 1D: tiles consecutivos
                tile_offset = entry.tile_num + tile_y * tiles_per_row * 2 + tile_x * 2
            else:
                # Mapeo 2D: matriz de 32 tiles de ancho
                tile_offset = entry.tile_num + tile_y * 32 + tile_x * 2
            
            # Cada tile 8bpp ocupa 64 bytes
            pixel_addr = self.sprite_vram_base + tile_offset * 32 + pixel_y * 8 + pixel_x
            
            if pixel_addr >= len(self.memory.vram):
                return None
            
            color_idx = int(self.memory.vram[pixel_addr])
            
            if color_idx == 0:
                return None
            
            # Paleta de sprites (offset 0x200 en palette RAM)
            pal_addr = 0x200 + color_idx * 2
        else:  # 4bpp
            if mapping_1d:
                tile_offset = entry.tile_num + tile_y * tiles_per_row + tile_x
            else:
                tile_offset = entry.tile_num + tile_y * 32 + tile_x
            
            # Cada tile 4bpp ocupa 32 bytes
            pixel_addr = self.sprite_vram_base + tile_offset * 32 + pixel_y * 4 + pixel_x // 2
            
            if pixel_addr >= len(self.memory.vram):
                return None
            
            byte = int(self.memory.vram[pixel_addr])
            
            if pixel_x & 1:
                color_idx = (byte >> 4) & 0x0F
            else:
                color_idx = byte & 0x0F
            
            if color_idx == 0:
                return None
            
            # Paleta de sprites con banco
            pal_addr = 0x200 + entry.palette * 32 + color_idx * 2
        
        # Leer color de la paleta
        color16 = int(self.memory.palette_ram[pal_addr]) | (int(self.memory.palette_ram[pal_addr + 1]) << 8)
        
        r = (color16 & 0x1F) << 3
        g = ((color16 >> 5) & 0x1F) << 3
        b = ((color16 >> 10) & 0x1F) << 3
        
        return (r, g, b)