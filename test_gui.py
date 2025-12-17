# test_gui.py
"""Test básico de la GUI"""
import sys

def test_sdl2_import():
    """Verifica que SDL2 esté instalado"""
    print("=== Test de SDL2 ===\n")
    
    try:
        import sdl2
        import sdl2.ext
        print("✓ PySDL2 importado correctamente")
        print(f"  Versión SDL2: {sdl2.SDL_MAJOR_VERSION}.{sdl2.SDL_MINOR_VERSION}.{sdl2.SDL_PATCHLEVEL}")
        return True
    except ImportError as e:
        print(f"✗ Error importando PySDL2: {e}")
        print("\nInstala con: pip install pysdl2 pysdl2-dll")
        return False

def test_window_creation():
    """Prueba crear una ventana SDL2"""
    print("\n=== Test de Ventana ===\n")
    
    try:
        from gui.window import GBAWindow, HAS_SDL2
        
        if not HAS_SDL2:
            print("✗ SDL2 no disponible")
            return False
        
        window = GBAWindow("Test Window")
        
        if window.init():
            print("✓ Ventana creada correctamente")
            
            # Mostrar por 2 segundos
            import sdl2
            import numpy as np
            
            # Crear framebuffer de prueba (gradiente)
            fb = np.zeros((160, 240, 3), dtype=np.uint8)
            for y in range(160):
                for x in range(240):
                    fb[y, x, 0] = x  # R
                    fb[y, x, 1] = y  # G
                    fb[y, x, 2] = 128  # B
            
            print("  Mostrando patrón de prueba por 2 segundos...")
            
            start_time = sdl2.SDL_GetTicks()
            while sdl2.SDL_GetTicks() - start_time < 2000:
                if not window.process_events():
                    break
                
                window.update_framebuffer(fb)
                window.render()
                window.delay(16)
            
            window.shutdown()
            print("✓ Ventana cerrada correctamente")
            return True
        else:
            print("✗ Error creando ventana")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_key_mapping():
    """Prueba el mapeo de teclas"""
    print("\n=== Test de Mapeo de Teclas ===\n")
    
    try:
        from gui.window import KEY_MAP, HAS_SDL2
        
        if not HAS_SDL2:
            print("✗ SDL2 no disponible")
            return False
        
        import sdl2
        
        expected_keys = {
            'Up': sdl2.SDLK_UP,
            'Down': sdl2.SDLK_DOWN,
            'Left': sdl2.SDLK_LEFT,
            'Right': sdl2.SDLK_RIGHT,
            'A': sdl2.SDLK_z,
            'B': sdl2.SDLK_x,
            'Start': sdl2.SDLK_RETURN,
            'Select': sdl2.SDLK_BACKSPACE,
            'L': sdl2.SDLK_a,
            'R': sdl2.SDLK_s,
        }
        
        for name, sdl_key in expected_keys.items():
            if sdl_key in KEY_MAP:
                print(f"✓ {name}: 0x{KEY_MAP[sdl_key]:04X}")
            else:
                print(f"✗ {name}: No mapeado")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_emulator_app():
    """Prueba la aplicación del emulador"""
    print("\n=== Test de EmulatorApp ===\n")
    
    try:
        from gui.emulator_app import EmulatorApp
        
        app = EmulatorApp()
        
        if app.init():
            print("✓ EmulatorApp inicializada")
            
            # No ejecutar el loop, solo verificar inicialización
            app.shutdown()
            print("✓ EmulatorApp cerrada")
            return True
        else:
            print("✗ Error inicializando EmulatorApp")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    all_passed = True
    
    all_passed &= test_sdl2_import()
    
    if all_passed:
        all_passed &= test_key_mapping()
        all_passed &= test_window_creation()
        all_passed &= test_emulator_app()
    
    print("\n" + "=" * 40)
    if all_passed:
        print("Todos los tests pasaron ✓")
    else:
        print("Algunos tests fallaron ✗")
    
    sys.exit(0 if all_passed else 1)