"""
GBA Emulator - Punto de entrada principal
"""
import sys
import os

def main():
    print("=" * 50)
    print("  GBA Emulator - Python Implementation")
    print("=" * 50)
    print()
    
    # Intentar usar GUI
    try:
        from gui.emulator_app import main as gui_main
        return gui_main()
    except ImportError as e:
        print(f"No se pudo cargar la GUI: {e}")
        print("Ejecuta: pip install pysdl2 pysdl2-dll")
        print()
        
        # Fallback a modo consola
        return console_mode()

def console_mode():
    """Modo consola (sin GUI)"""
    from gba import GBA
    
    gba = GBA()
    
    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
        if gba.load_rom(rom_path):
            print("\nROM cargada. Ejecutando en modo headless...")
            print("(Presiona Ctrl+C para detener)")
            
            try:
                for frame in range(600):  # 10 segundos a 60 FPS
                    gba.run_frame()
                    
                    if frame % 60 == 0:
                        print(f"Frame {frame}, Ciclos: {gba.total_cycles}")
                
                print("\nEjecución completada")
            except KeyboardInterrupt:
                print("\nDetenido por el usuario")
        else:
            print("Error al cargar la ROM")
            return 1
    else:
        print("Uso: python main.py <archivo.gba>")
        print()
        print("Para GUI completa, instala SDL2:")
        print("  pip install pysdl2 pysdl2-dll")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())