"""
Aplicación principal del emulador GBA - Optimizada
"""
import sys
import os
from typing import Optional

from gba import GBA
from gui.window import GBAWindow, HAS_SDL2


class EmulatorApp:
    """
    Aplicación del emulador GBA con GUI
    """
    
    TARGET_FPS = 60
    FRAME_TIME_MS = 1000 // TARGET_FPS
    
    # Configuración de rendimiento
    CYCLES_PER_BATCH = 10000  # Ejecutar en lotes pequeños para responsividad
    MAX_CYCLES_PER_FRAME = 280896  # Ciclos por frame real del GBA
    
    def __init__(self):
        self.gba: Optional[GBA] = None
        self.window: Optional[GBAWindow] = None
        self.rom_loaded = False
        self.save_path: Optional[str] = None
        
        # Configuración de rendimiento
        self.frame_skip = 0
        self.frame_skip_counter = 0
        self.turbo_mode = False
        self.limit_speed = True
    
    def init(self) -> bool:
        """Inicializa la aplicación"""
        if not HAS_SDL2:
            print("Error: PySDL2 no está instalado")
            print("Ejecuta: pip install pysdl2 pysdl2-dll")
            return False
        
        self.gba = GBA()
        self.window = GBAWindow("GBA Emulator")
        
        if not self.window.init():
            return False
        
        self.window.on_key_down = self._on_key_down
        self.window.on_key_up = self._on_key_up
        self.window.on_load_rom = self.load_rom
        self.window.on_save_state = self._save_state
        self.window.on_load_state = self._load_state
        
        return True
    
    def load_rom(self, path: str) -> bool:
        """Carga una ROM"""
        if not os.path.exists(path):
            print(f"Error: Archivo no encontrado: {path}")
            return False
        
        if self.gba.load_rom(path):
            self.rom_loaded = True
            self.save_path = os.path.splitext(path)[0] + ".sav"
            
            if os.path.exists(self.save_path):
                try:
                    with open(self.save_path, 'rb') as f:
                        self.gba.memory.load_save(f.read())
                    print(f"Save cargado: {self.save_path}")
                except Exception as e:
                    print(f"Error cargando save: {e}")
            
            title = os.path.basename(path)
            self.window.set_title(f"GBA Emulator - {title}")
            self.gba.reset()
            
            return True
        
        return False
    
    def load_bios(self, path: str) -> bool:
        """Carga el BIOS (opcional)"""
        return self.gba.load_bios(path)
    
    def _on_key_down(self, key: int) -> None:
        """Callback cuando se presiona una tecla"""
        if self.gba:
            self.gba.set_key(key, True)
    
    def _on_key_up(self, key: int) -> None:
        """Callback cuando se suelta una tecla"""
        if self.gba:
            self.gba.set_key(key, False)
    
    def _save_state(self) -> None:
        print("Save state: No implementado aún")
    
    def _load_state(self) -> None:
        print("Load state: No implementado aún")
    
    def _save_game(self) -> None:
        """Guarda los datos de SRAM"""
        if self.save_path and self.gba:
            try:
                save_data = self.gba.memory.get_save_data()
                with open(self.save_path, 'wb') as f:
                    f.write(save_data)
                print(f"Juego guardado: {self.save_path}")
            except Exception as e:
                print(f"Error guardando: {e}")
    
    def run_frame_partial(self) -> bool:
        """
        Ejecuta una porción de un frame, permitiendo procesar eventos.
        
        Returns:
            True si el frame está completo
        """
        cycles_this_batch = 0
        target_cycles = self.CYCLES_PER_BATCH
        
        while cycles_this_batch < target_cycles:
            if self.gba.ppu.frame_ready:
                self.gba.ppu.frame_ready = False
                return True
            
            cycles = self.gba.step()
            cycles_this_batch += cycles
        
        return False
    
    def run(self) -> int:
        """Loop principal del emulador"""
        if not self.window:
            return 1
        
        print("\n=== Controles ===")
        print("Flechas: D-Pad    Z: A    X: B")
        print("Enter: Start    Backspace: Select")
        print("A: L    S: R")
        print("Space: Turbo    P: Pausa    Escape: Salir")
        print("1-5: Frame skip (0-4)")
        print("Arrastra un archivo .gba a la ventana para cargarlo")
        print("=" * 40)
        print("\nNOTA: Python es lento para emulación.")
        print("Para mejor rendimiento, usa PyPy: pypy main.py juego.gba")
        print("=" * 40 + "\n")
        
        self.window.running = True
        last_time = self.window.get_ticks()
        frames_this_second = 0
        last_fps_update = last_time
        current_fps = 0
        
        # Para diagnóstico
        total_cycles = 0
        cycle_start_time = last_time
        
        while self.window.running:
            # Procesar eventos SIEMPRE (para mantener responsividad)
            if not self.window.process_events():
                self.window.running = False
                break
            
            # Procesar teclas adicionales
            self._process_extra_keys()
            
            if not self.rom_loaded or self.window.paused:
                # Renderizar pantalla actual sin emular
                self.window.render()
                self.window.delay(16)
                continue
            
            # Ejecutar emulación en lotes pequeños
            frame_complete = False
            batches = 0
            max_batches = 50 if self.turbo_mode else 30  # Limitar para responsividad
            
            while not frame_complete and batches < max_batches:
                frame_complete = self.run_frame_partial()
                batches += 1
                
                # Procesar eventos periódicamente durante frames largos
                if batches % 10 == 0:
                    if not self.window.process_events():
                        self.window.running = False
                        break
            
            # Actualizar pantalla (con frame skip)
            self.frame_skip_counter += 1
            if self.frame_skip_counter > self.frame_skip:
                self.frame_skip_counter = 0
                
                framebuffer = self.gba.ppu.framebuffer
                self.window.update_framebuffer(framebuffer)
                self.window.render()
            
            # Calcular FPS
            frames_this_second += 1
            current_time = self.window.get_ticks()
            
            if current_time - last_fps_update >= 1000:
                current_fps = frames_this_second
                frames_this_second = 0
                last_fps_update = current_time
                
                # Calcular ciclos por segundo
                elapsed = (current_time - cycle_start_time) / 1000.0
                if elapsed > 0:
                    cps = self.gba.total_cycles / elapsed
                    speed_percent = (cps / 16777216) * 100
                    
                    mode = "TURBO" if self.turbo_mode else "NORMAL"
                    skip_str = f"Skip:{self.frame_skip}" if self.frame_skip > 0 else ""
                    
                    title = f"GBA Emulator - {current_fps} FPS | {speed_percent:.1f}% | {mode} {skip_str}"
                    self.window.set_title(title)
            
            # Control de velocidad (solo si no es turbo)
            if self.limit_speed and not self.turbo_mode:
                frame_time = self.window.get_ticks() - last_time
                if frame_time < self.FRAME_TIME_MS:
                    self.window.delay(self.FRAME_TIME_MS - frame_time)
            
            last_time = self.window.get_ticks()
        
        if self.rom_loaded:
            self._save_game()
        
        return 0
    
    def _process_extra_keys(self) -> None:
        """Procesa teclas adicionales para configuración"""
        import sdl2
        
        # Obtener estado del teclado
        keyboard_state = sdl2.SDL_GetKeyboardState(None)
        
        # Turbo con Space
        self.turbo_mode = bool(keyboard_state[sdl2.SDL_SCANCODE_SPACE])
    
    def shutdown(self) -> None:
        """Cierra la aplicación"""
        if self.window:
            self.window.shutdown()


def main():
    """Punto de entrada principal"""
    app = EmulatorApp()
    
    if not app.init():
        print("Error inicializando la aplicación")
        return 1
    
    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        if not app.load_rom(rom_path):
            print(f"Error cargando ROM: {rom_path}")
    
    bios_paths = ['gba_bios.bin', 'bios.bin', 'gba.bin']
    for bios_path in bios_paths:
        if os.path.exists(bios_path):
            app.load_bios(bios_path)
            break
    
    try:
        exit_code = app.run()
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario")
        exit_code = 0
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    finally:
        app.shutdown()
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())