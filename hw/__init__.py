"""Módulo de hardware I/O del emulador GBA"""
from .timers import TimerController
from .dma import DMAController

__all__ = ['TimerController', 'DMAController']