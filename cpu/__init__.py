"""Módulo CPU optimizado con Cython"""
try:
    from .arm7tdmi import ARM7TDMI
    from .registers import CPURegisters, CPUMode
    CYTHON_AVAILABLE = True
except ImportError:
    CYTHON_AVAILABLE = False
    print("Cython CPU no disponible, usando versión Python")

__all__ = ['ARM7TDMI', 'CPURegisters', 'CPUMode', 'CYTHON_AVAILABLE']