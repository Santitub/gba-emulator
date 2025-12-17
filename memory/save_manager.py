"""
Gestor de guardado para diferentes tipos de memoria
"""
import os
from enum import Enum
from typing import Optional
import numpy as np


class SaveType(Enum):
    """Tipos de memoria de guardado"""
    NONE = 0
    SRAM = 1         # 32KB
    FLASH_64K = 2    # 64KB
    FLASH_128K = 3   # 128KB
    EEPROM_512 = 4   # 512 bytes
    EEPROM_8K = 5    # 8KB


class SaveManager:
    """
    Gestor de guardado de partidas
    Soporta SRAM, Flash y EEPROM
    """
    
    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.save_path = self._get_save_path()
        self.save_type = SaveType.SRAM
        self.data = np.zeros(0x10000, dtype=np.uint8)  # 64KB max
        
        # Estado de Flash
        self.flash_state = 0
        self.flash_bank = 0
        self.flash_id_mode = False
        
        # Estado de EEPROM
        self.eeprom_state = 0
        self.eeprom_buffer = 0
        self.eeprom_address = 0
        self.eeprom_bits_read = 0
    
    def _get_save_path(self) -> str:
        """Obtiene la ruta del archivo de guardado"""
        base = os.path.splitext(self.rom_path)[0]
        return base + ".sav"
    
    def detect_type(self, rom_data: bytes) -> SaveType:
        """Detecta el tipo de guardado analizando la ROM"""
        rom_str = rom_data.decode('ascii', errors='ignore')
        
        if 'EEPROM_V' in rom_str:
            # Detectar tamaño por el código del juego u otros factores
            self.save_type = SaveType.EEPROM_8K
        elif 'SRAM_V' in rom_str or 'SRAM_F_V' in rom_str:
            self.save_type = SaveType.SRAM
        elif 'FLASH1M_V' in rom_str:
            self.save_type = SaveType.FLASH_128K
            self.data = np.zeros(0x20000, dtype=np.uint8)
        elif 'FLASH_V' in rom_str or 'FLASH512_V' in rom_str:
            self.save_type = SaveType.FLASH_64K
        else:
            self.save_type = SaveType.SRAM
        
        return self.save_type
    
    def load(self) -> bool:
        """Carga el archivo de guardado"""
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, 'rb') as f:
                    data = f.read()
                size = min(len(data), len(self.data))
                self.data[:size] = np.frombuffer(data[:size], dtype=np.uint8)
                return True
            except Exception as e:
                print(f"Error cargando save: {e}")
        return False
    
    def save(self) -> bool:
        """Guarda el archivo de guardado"""
        try:
            with open(self.save_path, 'wb') as f:
                f.write(bytes(self.data))
            return True
        except Exception as e:
            print(f"Error guardando: {e}")
            return False
    
    # ===== SRAM =====
    
    def sram_read(self, address: int) -> int:
        """Lee de SRAM"""
        return int(self.data[address & 0x7FFF])
    
    def sram_write(self, address: int, value: int) -> None:
        """Escribe a SRAM"""
        self.data[address & 0x7FFF] = value & 0xFF
    
    # ===== Flash =====
    
    def flash_read(self, address: int) -> int:
        """Lee de Flash"""
        if self.flash_id_mode and address < 2:
            # Retornar ID del fabricante
            if self.save_type == SaveType.FLASH_128K:
                return [0x62, 0x13][address]  # Sanyo 128K
            return [0x32, 0x1B][address]  # Panasonic 64K
        
        offset = self.flash_bank * 0x10000 if self.save_type == SaveType.FLASH_128K else 0
        return int(self.data[(address & 0xFFFF) + offset])
    
    def flash_write(self, address: int, value: int) -> None:
        """Escribe comando a Flash"""
        address &= 0xFFFF
        
        # Máquina de estados de comandos Flash
        if self.flash_state == 0:
            if address == 0x5555 and value == 0xAA:
                self.flash_state = 1
        elif self.flash_state == 1:
            if address == 0x2AAA and value == 0x55:
                self.flash_state = 2
            else:
                self.flash_state = 0
        elif self.flash_state == 2:
            if address == 0x5555:
                if value == 0x90:  # Enter ID mode
                    self.flash_id_mode = True
                elif value == 0xF0:  # Exit ID mode
                    self.flash_id_mode = False
                elif value == 0x80:  # Erase
                    self.flash_state = 3
                    return
                elif value == 0xA0:  # Write byte
                    self.flash_state = 4
                    return
                elif value == 0xB0:  # Bank switch (128K only)
                    self.flash_state = 5
                    return
            self.flash_state = 0
        elif self.flash_state == 3:
            if address == 0x5555 and value == 0xAA:
                self.flash_state = 6
            else:
                self.flash_state = 0
        elif self.flash_state == 4:
            # Escribir byte
            offset = self.flash_bank * 0x10000 if self.save_type == SaveType.FLASH_128K else 0
            self.data[address + offset] = value
            self.flash_state = 0
        elif self.flash_state == 5:
            if address == 0x0000:
                self.flash_bank = value & 1
            self.flash_state = 0
        elif self.flash_state == 6:
            if address == 0x2AAA and value == 0x55:
                self.flash_state = 7
            else:
                self.flash_state = 0
        elif self.flash_state == 7:
            if value == 0x10:  # Chip erase
                self.data.fill(0xFF)
            elif value == 0x30:  # Sector erase
                sector = (address >> 12) & 0xF
                offset = self.flash_bank * 0x10000 if self.save_type == SaveType.FLASH_128K else 0
                start = sector * 0x1000 + offset
                self.data[start:start + 0x1000] = 0xFF
            self.flash_state = 0
    
    # ===== EEPROM =====
    
    def eeprom_read(self) -> int:
        """Lee de EEPROM"""
        if self.eeprom_state == 3:  # Reading data
            if self.eeprom_bits_read < 4:
                self.eeprom_bits_read += 1
                return 0  # 4 bits de relleno
            
            bit_index = self.eeprom_bits_read - 4
            byte_index = bit_index // 8
            bit_in_byte = 7 - (bit_index % 8)
            
            address = self.eeprom_address * 8 + byte_index
            value = (self.data[address] >> bit_in_byte) & 1
            
            self.eeprom_bits_read += 1
            if self.eeprom_bits_read >= 68:  # 4 + 64 bits
                self.eeprom_state = 0
            
            return value
        return 1  # Ready
    
    def eeprom_write(self, value: int) -> None:
        """Escribe a EEPROM"""
        bit = value & 1
        
        # Implementación simplificada de EEPROM
        # El protocolo completo requiere más estados
        pass