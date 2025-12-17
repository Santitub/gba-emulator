"""
Setup para compilar los módulos Cython del emulador GBA
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
import sys

# Flags de compilación según el sistema
if sys.platform == 'win32':
    extra_compile_args = ['/O2']
else:
    extra_compile_args = ['-O3', '-ffast-math']

# Extensiones a compilar
extensions = [
    Extension(
        "cpu.registers",
        ["cpu/registers.pyx"],
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "cpu.arm_instructions",
        ["cpu/arm_instructions.pyx"],
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "cpu.thumb_instructions",
        ["cpu/thumb_instructions.pyx"],
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "cpu.arm7tdmi",
        ["cpu/arm7tdmi.pyx"],
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "gba_core",
        ["gba.pyx"],
        extra_compile_args=extra_compile_args,
    ),
]

setup(
    name="gba_emulator",
    version="1.0",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': "3",
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'nonecheck': False,
            'initializedcheck': False,
        },
        annotate=True,
    ),
    zip_safe=False,
)