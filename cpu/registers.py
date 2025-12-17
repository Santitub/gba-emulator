"""
Registros del ARM7TDMI
Implementa el sistema de registros bankeados y el CPSR/SPSR
"""
from enum import IntEnum
from typing import Dict, Optional


class CPUMode(IntEnum):
    """Modos de operación del ARM7TDMI"""
    USER       = 0b10000  # 0x10 - Modo usuario normal
    FIQ        = 0b10001  # 0x11 - Fast Interrupt
    IRQ        = 0b10010  # 0x12 - Normal Interrupt
    SUPERVISOR = 0b10011  # 0x13 - Modo supervisor (SWI)
    ABORT      = 0b10111  # 0x17 - Abort de datos/prefetch
    UNDEFINED  = 0b11011  # 0x1B - Instrucción indefinida
    SYSTEM     = 0b11111  # 0x1F - Modo sistema privilegiado
    
    @classmethod
    def is_valid(cls, mode: int) -> bool:
        """Verifica si un modo es válido"""
        return mode in [m.value for m in cls]
    
    @classmethod
    def has_spsr(cls, mode: int) -> bool:
        """Verifica si el modo tiene SPSR"""
        return mode not in (cls.USER, cls.SYSTEM)


class PSRFlags:
    """Constantes para acceder a los flags del PSR"""
    # Flags de condición (bits 31-28)
    N_BIT = 31  # Negative
    Z_BIT = 30  # Zero
    C_BIT = 29  # Carry
    V_BIT = 28  # Overflow
    
    # Bits de control
    I_BIT = 7   # IRQ disable
    F_BIT = 6   # FIQ disable
    T_BIT = 5   # Thumb state
    
    # Máscaras
    N_MASK = 1 << 31
    Z_MASK = 1 << 30
    C_MASK = 1 << 29
    V_MASK = 1 << 28
    
    I_MASK = 1 << 7
    F_MASK = 1 << 6
    T_MASK = 1 << 5
    
    MODE_MASK = 0x1F
    
    # Máscara de flags
    FLAGS_MASK = N_MASK | Z_MASK | C_MASK | V_MASK
    CONTROL_MASK = I_MASK | F_MASK | T_MASK | MODE_MASK


class CPURegisters:
    """
    Sistema de registros del ARM7TDMI
    
    Gestiona los 37 registros totales:
    - 16 registros generales (R0-R15)
    - Registros bankeados para cada modo
    - CPSR y 5 SPSRs
    """
    
    def __init__(self):
        # Registros no bankeados (R0-R7, compartidos por todos los modos)
        self._regs_common = [0] * 8  # R0-R7
        
        # Registros bankeados R8-R12 (User/System vs FIQ)
        self._r8_r12_usr = [0] * 5   # R8-R12 para User/System/IRQ/SVC/ABT/UND
        self._r8_r12_fiq = [0] * 5   # R8-R12 para FIQ
        
        # Registros bankeados R13 (SP) y R14 (LR) por modo
        self._r13_bank = {
            CPUMode.USER:       0,
            CPUMode.SYSTEM:     0,  # Comparte con USER
            CPUMode.FIQ:        0,
            CPUMode.IRQ:        0,
            CPUMode.SUPERVISOR: 0,
            CPUMode.ABORT:      0,
            CPUMode.UNDEFINED:  0,
        }
        
        self._r14_bank = {
            CPUMode.USER:       0,
            CPUMode.SYSTEM:     0,  # Comparte con USER
            CPUMode.FIQ:        0,
            CPUMode.IRQ:        0,
            CPUMode.SUPERVISOR: 0,
            CPUMode.ABORT:      0,
            CPUMode.UNDEFINED:  0,
        }
        
        # R15 (PC) - compartido
        self._r15 = 0
        
        # Program Status Registers
        self._cpsr = CPUMode.SYSTEM | PSRFlags.I_MASK | PSRFlags.F_MASK
        
        self._spsr = {
            CPUMode.FIQ:        0,
            CPUMode.IRQ:        0,
            CPUMode.SUPERVISOR: 0,
            CPUMode.ABORT:      0,
            CPUMode.UNDEFINED:  0,
        }
        
    def reset(self) -> None:
        """Reinicia todos los registros al estado inicial"""
        # Limpiar registros comunes
        for i in range(8):
            self._regs_common[i] = 0
            
        # Limpiar registros bankeados R8-R12
        for i in range(5):
            self._r8_r12_usr[i] = 0
            self._r8_r12_fiq[i] = 0
            
        # Limpiar SP y LR bankeados
        for mode in self._r13_bank:
            self._r13_bank[mode] = 0
            self._r14_bank[mode] = 0
            
        # Limpiar SPSRs
        for mode in self._spsr:
            self._spsr[mode] = 0
            
        # Estado inicial del GBA
        self._r15 = 0x08000000  # PC apunta al inicio de la ROM
        
        # CPSR: Modo System, IRQ y FIQ deshabilitados, modo ARM
        self._cpsr = CPUMode.SYSTEM | PSRFlags.I_MASK | PSRFlags.F_MASK
        
        # Configurar stack pointers iniciales (valores típicos del BIOS)
        self._r13_bank[CPUMode.USER] = 0x03007F00
        self._r13_bank[CPUMode.SYSTEM] = 0x03007F00
        self._r13_bank[CPUMode.IRQ] = 0x03007FA0
        self._r13_bank[CPUMode.SUPERVISOR] = 0x03007FE0
        
    @property
    def mode(self) -> int:
        """Obtiene el modo actual de la CPU"""
        return self._cpsr & PSRFlags.MODE_MASK
    
    @mode.setter
    def mode(self, new_mode: int) -> None:
        """Cambia el modo de la CPU"""
        if CPUMode.is_valid(new_mode):
            self._cpsr = (self._cpsr & ~PSRFlags.MODE_MASK) | new_mode
        else:
            raise ValueError(f"Modo inválido: {new_mode:#x}")
    
    def _get_sp_lr_bank_key(self, mode: int) -> int:
        """Obtiene la clave del banco para SP/LR"""
        # System y User comparten registros
        if mode == CPUMode.SYSTEM:
            return CPUMode.USER
        return mode
    
    def get(self, reg: int) -> int:
        """
        Lee un registro (0-15)
        
        Args:
            reg: Número de registro (0-15)
            
        Returns:
            Valor del registro (32 bits)
        """
        if reg < 0 or reg > 15:
            raise ValueError(f"Registro inválido: {reg}")
            
        # R0-R7: Siempre los mismos
        if reg < 8:
            return self._regs_common[reg]
            
        # R8-R12: Bankeados solo en FIQ
        elif reg < 13:
            if self.mode == CPUMode.FIQ:
                return self._r8_r12_fiq[reg - 8]
            else:
                return self._r8_r12_usr[reg - 8]
                
        # R13 (SP): Bankeado por modo
        elif reg == 13:
            key = self._get_sp_lr_bank_key(self.mode)
            return self._r13_bank.get(key, self._r13_bank[CPUMode.USER])
            
        # R14 (LR): Bankeado por modo
        elif reg == 14:
            key = self._get_sp_lr_bank_key(self.mode)
            return self._r14_bank.get(key, self._r14_bank[CPUMode.USER])
            
        # R15 (PC)
        else:
            return self._r15
    
    def set(self, reg: int, value: int) -> None:
        """
        Escribe un registro (0-15)
        
        Args:
            reg: Número de registro (0-15)
            value: Valor a escribir (se trunca a 32 bits)
        """
        value &= 0xFFFFFFFF
        
        if reg < 0 or reg > 15:
            raise ValueError(f"Registro inválido: {reg}")
            
        # R0-R7
        if reg < 8:
            self._regs_common[reg] = value
            
        # R8-R12
        elif reg < 13:
            if self.mode == CPUMode.FIQ:
                self._r8_r12_fiq[reg - 8] = value
            else:
                self._r8_r12_usr[reg - 8] = value
                
        # R13 (SP)
        elif reg == 13:
            key = self._get_sp_lr_bank_key(self.mode)
            self._r13_bank[key] = value
            
        # R14 (LR)
        elif reg == 14:
            key = self._get_sp_lr_bank_key(self.mode)
            self._r14_bank[key] = value
            
        # R15 (PC)
        else:
            # Alinear PC según modo ARM/Thumb
            if self.thumb_mode:
                self._r15 = value & ~1
            else:
                self._r15 = value & ~3
    
    # ===== Propiedades de acceso rápido =====
    
    @property
    def pc(self) -> int:
        """Program Counter (R15)"""
        return self._r15
    
    @pc.setter
    def pc(self, value: int) -> None:
        self.set(15, value)
    
    @property
    def sp(self) -> int:
        """Stack Pointer (R13)"""
        return self.get(13)
    
    @sp.setter
    def sp(self, value: int) -> None:
        self.set(13, value)
    
    @property
    def lr(self) -> int:
        """Link Register (R14)"""
        return self.get(14)
    
    @lr.setter
    def lr(self, value: int) -> None:
        self.set(14, value)
    
    # ===== CPSR/SPSR =====
    
    @property
    def cpsr(self) -> int:
        """Current Program Status Register"""
        return self._cpsr
    
    @cpsr.setter
    def cpsr(self, value: int) -> None:
        self._cpsr = value & 0xFFFFFFFF
    
    @property
    def spsr(self) -> int:
        """Saved Program Status Register (del modo actual)"""
        mode = self.mode
        if mode in self._spsr:
            return self._spsr[mode]
        return self._cpsr  # User/System no tienen SPSR
    
    @spsr.setter
    def spsr(self, value: int) -> None:
        mode = self.mode
        if mode in self._spsr:
            self._spsr[mode] = value & 0xFFFFFFFF
    
    # ===== Flags de condición =====
    
    @property
    def flag_n(self) -> bool:
        """Flag Negative"""
        return bool(self._cpsr & PSRFlags.N_MASK)
    
    @flag_n.setter
    def flag_n(self, value: bool) -> None:
        if value:
            self._cpsr |= PSRFlags.N_MASK
        else:
            self._cpsr &= ~PSRFlags.N_MASK
    
    @property
    def flag_z(self) -> bool:
        """Flag Zero"""
        return bool(self._cpsr & PSRFlags.Z_MASK)
    
    @flag_z.setter
    def flag_z(self, value: bool) -> None:
        if value:
            self._cpsr |= PSRFlags.Z_MASK
        else:
            self._cpsr &= ~PSRFlags.Z_MASK
    
    @property
    def flag_c(self) -> bool:
        """Flag Carry"""
        return bool(self._cpsr & PSRFlags.C_MASK)
    
    @flag_c.setter
    def flag_c(self, value: bool) -> None:
        if value:
            self._cpsr |= PSRFlags.C_MASK
        else:
            self._cpsr &= ~PSRFlags.C_MASK
    
    @property
    def flag_v(self) -> bool:
        """Flag Overflow"""
        return bool(self._cpsr & PSRFlags.V_MASK)
    
    @flag_v.setter
    def flag_v(self, value: bool) -> None:
        if value:
            self._cpsr |= PSRFlags.V_MASK
        else:
            self._cpsr &= ~PSRFlags.V_MASK
    
    # ===== Bits de control =====
    
    @property
    def irq_disabled(self) -> bool:
        """IRQ deshabilitado"""
        return bool(self._cpsr & PSRFlags.I_MASK)
    
    @irq_disabled.setter
    def irq_disabled(self, value: bool) -> None:
        if value:
            self._cpsr |= PSRFlags.I_MASK
        else:
            self._cpsr &= ~PSRFlags.I_MASK
    
    @property
    def fiq_disabled(self) -> bool:
        """FIQ deshabilitado"""
        return bool(self._cpsr & PSRFlags.F_MASK)
    
    @fiq_disabled.setter
    def fiq_disabled(self, value: bool) -> None:
        if value:
            self._cpsr |= PSRFlags.F_MASK
        else:
            self._cpsr &= ~PSRFlags.F_MASK
    
    @property
    def thumb_mode(self) -> bool:
        """Modo Thumb (vs ARM)"""
        return bool(self._cpsr & PSRFlags.T_MASK)
    
    @thumb_mode.setter
    def thumb_mode(self, value: bool) -> None:
        if value:
            self._cpsr |= PSRFlags.T_MASK
        else:
            self._cpsr &= ~PSRFlags.T_MASK
    
    # ===== Métodos de utilidad =====
    
    def set_flags_nz(self, result: int) -> None:
        """Establece flags N y Z basándose en el resultado"""
        result &= 0xFFFFFFFF
        self.flag_n = bool(result & 0x80000000)
        self.flag_z = (result == 0)
    
    def set_flags_nzcv(self, result: int, carry: bool, overflow: bool) -> None:
        """Establece todos los flags de condición"""
        self.set_flags_nz(result)
        self.flag_c = carry
        self.flag_v = overflow
    
    def check_condition(self, cond: int) -> bool:
        """
        Verifica una condición ARM (4 bits)
        
        Args:
            cond: Código de condición (0-15)
            
        Returns:
            True si la condición se cumple
        """
        n = self.flag_n
        z = self.flag_z
        c = self.flag_c
        v = self.flag_v
        
        conditions = {
            0x0: z,                    # EQ - Equal
            0x1: not z,                # NE - Not Equal
            0x2: c,                    # CS/HS - Carry Set
            0x3: not c,                # CC/LO - Carry Clear
            0x4: n,                    # MI - Minus/Negative
            0x5: not n,                # PL - Plus/Positive
            0x6: v,                    # VS - Overflow Set
            0x7: not v,                # VC - Overflow Clear
            0x8: c and not z,          # HI - Unsigned Higher
            0x9: not c or z,           # LS - Unsigned Lower or Same
            0xA: n == v,               # GE - Signed Greater or Equal
            0xB: n != v,               # LT - Signed Less Than
            0xC: not z and (n == v),   # GT - Signed Greater Than
            0xD: z or (n != v),        # LE - Signed Less or Equal
            0xE: True,                 # AL - Always
            0xF: True,                 # NV - Never (reserved, treat as always)
        }
        
        return conditions.get(cond, True)
    
    def switch_mode(self, new_mode: int, save_cpsr: bool = True) -> None:
        """
        Cambia a un nuevo modo de CPU
        
        Args:
            new_mode: Nuevo modo
            save_cpsr: Si guardar CPSR en SPSR del nuevo modo
        """
        if not CPUMode.is_valid(new_mode):
            return
            
        if save_cpsr and CPUMode.has_spsr(new_mode):
            self._spsr[new_mode] = self._cpsr
            
        self.mode = new_mode
    
    def restore_cpsr_from_spsr(self) -> None:
        """Restaura CPSR desde SPSR (para retorno de excepciones)"""
        if CPUMode.has_spsr(self.mode):
            self._cpsr = self._spsr[self.mode]
    
    def __str__(self) -> str:
        """Representación legible de los registros"""
        mode_names = {
            CPUMode.USER: "USER",
            CPUMode.FIQ: "FIQ",
            CPUMode.IRQ: "IRQ",
            CPUMode.SUPERVISOR: "SVC",
            CPUMode.ABORT: "ABT",
            CPUMode.UNDEFINED: "UND",
            CPUMode.SYSTEM: "SYS",
        }
        
        lines = []
        lines.append(f"Mode: {mode_names.get(self.mode, 'UNK')} | " +
                    f"{'THUMB' if self.thumb_mode else 'ARM'}")
        lines.append(f"CPSR: {self._cpsr:08X} | " +
                    f"N={int(self.flag_n)} Z={int(self.flag_z)} " +
                    f"C={int(self.flag_c)} V={int(self.flag_v)} | " +
                    f"I={int(self.irq_disabled)} F={int(self.fiq_disabled)}")
        lines.append("-" * 50)
        
        for i in range(0, 16, 4):
            regs = [f"R{j:2d}={self.get(j):08X}" for j in range(i, min(i+4, 16))]
            lines.append("  ".join(regs))
            
        return "\n".join(lines)