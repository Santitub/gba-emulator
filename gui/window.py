"""
Ventana principal del emulador GBA usando SDL2
"""
import ctypes
import numpy as np
from typing import Optional, Callable
import os

try:
    import sdl2
    import sdl2.ext
    import sdl2.sdlmixer as mixer
    HAS_SDL2 = True
except ImportError:
    HAS_SDL2 = False
    print("ADVERTENCIA: PySDL2 no instalado. Ejecuta: pip install pysdl2 pysdl2-dll")


# Mapeo de teclas SDL2 a botones GBA
KEY_MAP = {
    sdl2.SDLK_UP: 0x0040,      # Up
    sdl2.SDLK_DOWN: 0x0080,    # Down
    sdl2.SDLK_LEFT: 0x0020,    # Left
    sdl2.SDLK_RIGHT: 0x0010,   # Right
    sdl2.SDLK_z: 0x0001,       # A
    sdl2.SDLK_x: 0x0002,       # B
    sdl2.SDLK_RETURN: 0x0008,  # Start
    sdl2.SDLK_BACKSPACE: 0x0004,  # Select
    sdl2.SDLK_a: 0x0200,       # L
    sdl2.SDLK_s: 0x0100,       # R
} if HAS_SDL2 else {}


class GBAWindow:
    """
    Ventana SDL2 para el emulador GBA
    """
    
    # Constantes
    GBA_WIDTH = 240
    GBA_HEIGHT = 160
    SCALE = 3
    WINDOW_WIDTH = GBA_WIDTH * SCALE
    WINDOW_HEIGHT = GBA_HEIGHT * SCALE
    
    AUDIO_SAMPLE_RATE = 32768
    AUDIO_BUFFER_SIZE = 1024
    
    def __init__(self, title: str = "GBA Emulator"):
        if not HAS_SDL2:
            raise RuntimeError("PySDL2 no está instalado")
        
        self.title = title
        self.running = False
        self.paused = False
        self.fast_forward = False
        
        # SDL2 objects
        self.window = None
        self.renderer = None
        self.texture = None
        
        # Framebuffer
        self.pixel_buffer = np.zeros((self.GBA_HEIGHT, self.GBA_WIDTH, 4), dtype=np.uint8)
        
        # Callbacks
        self.on_frame: Optional[Callable] = None
        self.on_key_down: Optional[Callable[[int], None]] = None
        self.on_key_up: Optional[Callable[[int], None]] = None
        self.on_load_rom: Optional[Callable[[str], bool]] = None
        self.on_save_state: Optional[Callable] = None
        self.on_load_state: Optional[Callable] = None
        
        # Estado
        self.frame_count = 0
        self.last_fps_time = 0
        self.fps = 0
        
    def init(self) -> bool:
        """Inicializa SDL2 y crea la ventana"""
        # Inicializar SDL2
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_AUDIO | sdl2.SDL_INIT_GAMECONTROLLER) < 0:
            print(f"Error inicializando SDL2: {sdl2.SDL_GetError()}")
            return False
        
        # Crear ventana
        self.window = sdl2.SDL_CreateWindow(
            self.title.encode('utf-8'),
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            self.WINDOW_WIDTH,
            self.WINDOW_HEIGHT,
            sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_RESIZABLE
        )
        
        if not self.window:
            print(f"Error creando ventana: {sdl2.SDL_GetError()}")
            return False
        
        # Crear renderer
        self.renderer = sdl2.SDL_CreateRenderer(
            self.window, -1,
            sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC
        )
        
        if not self.renderer:
            print(f"Error creando renderer: {sdl2.SDL_GetError()}")
            return False
        
        # Configurar escalado
        sdl2.SDL_RenderSetLogicalSize(self.renderer, self.GBA_WIDTH, self.GBA_HEIGHT)
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b"1")
        
        # Crear textura para el framebuffer
        self.texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_ARGB8888,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            self.GBA_WIDTH,
            self.GBA_HEIGHT
        )
        
        if not self.texture:
            print(f"Error creando textura: {sdl2.SDL_GetError()}")
            return False
        
        print("SDL2 inicializado correctamente")
        print(f"  Ventana: {self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        print(f"  Escala: {self.SCALE}x")
        
        return True
    
    def init_audio(self) -> bool:
        """Inicializa el sistema de audio"""
        # Configurar audio
        if mixer.Mix_OpenAudio(self.AUDIO_SAMPLE_RATE, sdl2.AUDIO_S16SYS, 2, self.AUDIO_BUFFER_SIZE) < 0:
            print(f"Error inicializando audio: {sdl2.SDL_GetError()}")
            return False
        
        print(f"  Audio: {self.AUDIO_SAMPLE_RATE} Hz, stereo")
        return True
    
    def shutdown(self) -> None:
        """Cierra SDL2 y libera recursos"""
        if self.texture:
            sdl2.SDL_DestroyTexture(self.texture)
        if self.renderer:
            sdl2.SDL_DestroyRenderer(self.renderer)
        if self.window:
            sdl2.SDL_DestroyWindow(self.window)
        
        mixer.Mix_CloseAudio()
        sdl2.SDL_Quit()
        
        print("SDL2 cerrado")
    
    def update_framebuffer(self, framebuffer: np.ndarray) -> None:
        """
        Actualiza el framebuffer desde un array numpy RGB
        
        Args:
            framebuffer: Array numpy de shape (160, 240, 3) con valores RGB
        """
        # Convertir RGB a ARGB para SDL2
        self.pixel_buffer[:, :, 0] = framebuffer[:, :, 2]  # B
        self.pixel_buffer[:, :, 1] = framebuffer[:, :, 1]  # G
        self.pixel_buffer[:, :, 2] = framebuffer[:, :, 0]  # R
        self.pixel_buffer[:, :, 3] = 255  # A
        
        # Actualizar textura
        sdl2.SDL_UpdateTexture(
            self.texture,
            None,
            self.pixel_buffer.ctypes.data_as(ctypes.c_void_p),
            self.GBA_WIDTH * 4
        )
    
    def render(self) -> None:
        """Renderiza el frame actual"""
        sdl2.SDL_RenderClear(self.renderer)
        sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)
        sdl2.SDL_RenderPresent(self.renderer)
    
    def process_events(self) -> bool:
        """
        Procesa eventos SDL2
        
        Returns:
            False si se debe cerrar la ventana
        """
        event = sdl2.SDL_Event()
        
        while sdl2.SDL_PollEvent(ctypes.byref(event)):
            if event.type == sdl2.SDL_QUIT:
                return False
            
            elif event.type == sdl2.SDL_KEYDOWN:
                key = event.key.keysym.sym
                
                # Teclas especiales
                if key == sdl2.SDLK_ESCAPE:
                    return False
                elif key == sdl2.SDLK_SPACE:
                    self.fast_forward = True
                elif key == sdl2.SDLK_p:
                    self.paused = not self.paused
                elif key == sdl2.SDLK_o:
                    self._open_rom_dialog()
                elif key == sdl2.SDLK_F1:
                    if self.on_save_state:
                        self.on_save_state()
                elif key == sdl2.SDLK_F2:
                    if self.on_load_state:
                        self.on_load_state()
                elif key == sdl2.SDLK_r:
                    # Reset (podríamos añadir callback)
                    pass
                elif event.type == sdl2.SDL_KEYDOWN:
                    key = event.key.keysym.sym
                    
                    # Teclas especiales
                    if key == sdl2.SDLK_ESCAPE:
                        return False
                    elif key == sdl2.SDLK_SPACE:
                        self.fast_forward = True
                    elif key == sdl2.SDLK_p:
                        self.paused = not self.paused
                        print("PAUSA" if self.paused else "CONTINUAR")
                    elif key == sdl2.SDLK_o:
                        self._open_rom_dialog()
                    elif key == sdl2.SDLK_F1:
                        if self.on_save_state:
                            self.on_save_state()
                    elif key == sdl2.SDLK_F2:
                        if self.on_load_state:
                            self.on_load_state()
                    
                    # Frame skip con teclas 1-5
                    elif key == sdl2.SDLK_1:
                        print("Frame skip: 0")
                    elif key == sdl2.SDLK_2:
                        print("Frame skip: 1")
                    elif key == sdl2.SDLK_3:
                        print("Frame skip: 2")
                    elif key == sdl2.SDLK_4:
                        print("Frame skip: 3")
                    elif key == sdl2.SDLK_5:
                        print("Frame skip: 4")
                    
                    # Botones del GBA
                    if key in KEY_MAP and self.on_key_down:
                        self.on_key_down(KEY_MAP[key])
                
                # Botones del GBA
                if key in KEY_MAP and self.on_key_down:
                    self.on_key_down(KEY_MAP[key])
            
            elif event.type == sdl2.SDL_KEYUP:
                key = event.key.keysym.sym
                
                if key == sdl2.SDLK_SPACE:
                    self.fast_forward = False
                
                if key in KEY_MAP and self.on_key_up:
                    self.on_key_up(KEY_MAP[key])
            
            elif event.type == sdl2.SDL_DROPFILE:
                # Archivo arrastrado a la ventana
                file_path = event.drop.file.decode('utf-8')
                sdl2.SDL_free(event.drop.file)
                
                if file_path.lower().endswith('.gba'):
                    if self.on_load_rom:
                        self.on_load_rom(file_path)
        
        return True
    
    def _open_rom_dialog(self) -> None:
        """Abre un diálogo para seleccionar ROM (básico)"""
        # Implementación simple: buscar en directorio actual
        print("\n=== Cargar ROM ===")
        print("Escribe la ruta del archivo .gba:")
        
        # En una implementación real, usaríamos un diálogo de archivo
        # Por ahora, el usuario puede arrastrar el archivo a la ventana
        print("(También puedes arrastrar el archivo a la ventana)")
    
    def set_title(self, title: str) -> None:
        """Cambia el título de la ventana"""
        if self.window:
            sdl2.SDL_SetWindowTitle(self.window, title.encode('utf-8'))
    
    def update_fps(self) -> None:
        """Actualiza el contador de FPS"""
        current_time = sdl2.SDL_GetTicks()
        self.frame_count += 1
        
        if current_time - self.last_fps_time >= 1000:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = current_time
            
            # Actualizar título con FPS
            self.set_title(f"{self.title} - {self.fps} FPS")
    
    def delay(self, ms: int) -> None:
        """Espera un número de milisegundos"""
        sdl2.SDL_Delay(ms)
    
    def get_ticks(self) -> int:
        """Obtiene el tiempo en milisegundos desde inicio"""
        return sdl2.SDL_GetTicks()