# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: nonecheck=False

"""
Registros del ARM7TDMI - Versión Cython Optimizada
"""

from libc.stdint cimport uint32_t, int32_t, uint8_t

# Constantes de modo (DEF para que sean constantes en tiempo de compilación)
DEF _MODE_USER       = 0x10  # 0b10000
DEF _MODE_FIQ        = 0x11  # 0b10001
DEF _MODE_IRQ        = 0x12  # 0b10010
DEF _MODE_SUPERVISOR = 0x13  # 0b10011
DEF _MODE_ABORT      = 0x17  # 0b10111
DEF _MODE_UNDEFINED  = 0x1B  # 0b11011
DEF _MODE_SYSTEM     = 0x1F  # 0b11111

# Constantes PSR
DEF _N_MASK = 0x80000000  # 1 << 31
DEF _Z_MASK = 0x40000000  # 1 << 30
DEF _C_MASK = 0x20000000  # 1 << 29
DEF _V_MASK = 0x10000000  # 1 << 28
DEF _I_MASK = 0x80        # 1 << 7
DEF _F_MASK = 0x40        # 1 << 6
DEF _T_MASK = 0x20        # 1 << 5
DEF _MODE_MASK = 0x1F


# Para compatibilidad con código existente (accesible desde Python)
class CPUMode:
    USER       = _MODE_USER
    FIQ        = _MODE_FIQ
    IRQ        = _MODE_IRQ
    SUPERVISOR = _MODE_SUPERVISOR
    ABORT      = _MODE_ABORT
    UNDEFINED  = _MODE_UNDEFINED
    SYSTEM     = _MODE_SYSTEM
    
    @staticmethod
    def is_valid(mode):
        return mode in (_MODE_USER, _MODE_FIQ, _MODE_IRQ, _MODE_SUPERVISOR, 
                       _MODE_ABORT, _MODE_UNDEFINED, _MODE_SYSTEM)
    
    @staticmethod
    def has_spsr(mode):
        return mode not in (_MODE_USER, _MODE_SYSTEM)


class PSRFlags:
    N_BIT = 31
    Z_BIT = 30
    C_BIT = 29
    V_BIT = 28
    I_BIT = 7
    F_BIT = 6
    T_BIT = 5
    
    N_MASK = _N_MASK
    Z_MASK = _Z_MASK
    C_MASK = _C_MASK
    V_MASK = _V_MASK
    I_MASK = _I_MASK
    F_MASK = _F_MASK
    T_MASK = _T_MASK
    MODE_MASK = _MODE_MASK
    FLAGS_MASK = _N_MASK | _Z_MASK | _C_MASK | _V_MASK
    CONTROL_MASK = _I_MASK | _F_MASK | _T_MASK | _MODE_MASK


cdef class CPURegisters:
    """
    Sistema de registros del ARM7TDMI - Optimizado con Cython
    """
    
    # Registros como arrays C
    cdef uint32_t[8] _regs_common      # R0-R7
    cdef uint32_t[5] _r8_r12_usr       # R8-R12 para User/System
    cdef uint32_t[5] _r8_r12_fiq       # R8-R12 para FIQ
    
    # SP y LR bankeados (diccionarios para compatibilidad)
    cdef public dict _r13_bank
    cdef public dict _r14_bank
    
    # PC y PSRs
    cdef public uint32_t _r15
    cdef public uint32_t _cpsr
    cdef public dict _spsr
    
    # Cache de flags para acceso rápido
    cdef public bint flag_n
    cdef public bint flag_z
    cdef public bint flag_c
    cdef public bint flag_v
    cdef public bint irq_disabled
    cdef public bint fiq_disabled
    cdef public bint thumb_mode
    cdef public int _mode
    
    def __init__(self):
        cdef int i
        
        # Inicializar arrays a cero
        for i in range(8):
            self._regs_common[i] = 0
        for i in range(5):
            self._r8_r12_usr[i] = 0
            self._r8_r12_fiq[i] = 0
        
        # Inicializar diccionarios para bancos
        self._r13_bank = {
            _MODE_USER: 0,
            _MODE_SYSTEM: 0,
            _MODE_FIQ: 0,
            _MODE_IRQ: 0,
            _MODE_SUPERVISOR: 0,
            _MODE_ABORT: 0,
            _MODE_UNDEFINED: 0,
        }
        
        self._r14_bank = {
            _MODE_USER: 0,
            _MODE_SYSTEM: 0,
            _MODE_FIQ: 0,
            _MODE_IRQ: 0,
            _MODE_SUPERVISOR: 0,
            _MODE_ABORT: 0,
            _MODE_UNDEFINED: 0,
        }
        
        self._spsr = {
            _MODE_FIQ: 0,
            _MODE_IRQ: 0,
            _MODE_SUPERVISOR: 0,
            _MODE_ABORT: 0,
            _MODE_UNDEFINED: 0,
        }
        
        self._r15 = 0
        self._cpsr = _MODE_SYSTEM | _I_MASK | _F_MASK
        self._mode = _MODE_SYSTEM
        self._sync_flags_from_cpsr()
    
    cdef void _sync_flags_from_cpsr(self):
        """Sincroniza cache de flags desde CPSR"""
        self.flag_n = (self._cpsr & _N_MASK) != 0
        self.flag_z = (self._cpsr & _Z_MASK) != 0
        self.flag_c = (self._cpsr & _C_MASK) != 0
        self.flag_v = (self._cpsr & _V_MASK) != 0
        self.irq_disabled = (self._cpsr & _I_MASK) != 0
        self.fiq_disabled = (self._cpsr & _F_MASK) != 0
        self.thumb_mode = (self._cpsr & _T_MASK) != 0
        self._mode = self._cpsr & _MODE_MASK
    
    cdef void _sync_cpsr_from_flags(self):
        """Sincroniza CPSR desde cache de flags"""
        self._cpsr = self._mode
        if self.flag_n:
            self._cpsr |= _N_MASK
        if self.flag_z:
            self._cpsr |= _Z_MASK
        if self.flag_c:
            self._cpsr |= _C_MASK
        if self.flag_v:
            self._cpsr |= _V_MASK
        if self.irq_disabled:
            self._cpsr |= _I_MASK
        if self.fiq_disabled:
            self._cpsr |= _F_MASK
        if self.thumb_mode:
            self._cpsr |= _T_MASK
    
    cpdef void reset(self):
        """Reinicia todos los registros"""
        cdef int i
        
        for i in range(8):
            self._regs_common[i] = 0
        for i in range(5):
            self._r8_r12_usr[i] = 0
            self._r8_r12_fiq[i] = 0
        
        for mode in self._r13_bank:
            self._r13_bank[mode] = 0
            self._r14_bank[mode] = 0
        
        for mode in self._spsr:
            self._spsr[mode] = 0
        
        self._r15 = 0x08000000
        self._cpsr = _MODE_SYSTEM | _I_MASK | _F_MASK
        
        # Stack pointers iniciales
        self._r13_bank[_MODE_USER] = 0x03007F00
        self._r13_bank[_MODE_SYSTEM] = 0x03007F00
        self._r13_bank[_MODE_IRQ] = 0x03007FA0
        self._r13_bank[_MODE_SUPERVISOR] = 0x03007FE0
        
        self._sync_flags_from_cpsr()
    
    @property
    def mode(self):
        return self._mode
    
    @mode.setter
    def mode(self, int new_mode):
        if CPUMode.is_valid(new_mode):
            self._mode = new_mode
            self._cpsr = (self._cpsr & ~_MODE_MASK) | new_mode
    
    cdef int _get_bank_key(self, int mode):
        """Obtiene clave de banco (System usa banco de User)"""
        if mode == _MODE_SYSTEM:
            return _MODE_USER
        return mode
    
    cpdef uint32_t get(self, int reg):
        """Lee un registro (0-15)"""
        cdef int key
        
        if reg < 8:
            return self._regs_common[reg]
        elif reg < 13:
            if self._mode == _MODE_FIQ:
                return self._r8_r12_fiq[reg - 8]
            else:
                return self._r8_r12_usr[reg - 8]
        elif reg == 13:
            key = self._get_bank_key(self._mode)
            return self._r13_bank[key]
        elif reg == 14:
            key = self._get_bank_key(self._mode)
            return self._r14_bank[key]
        else:  # reg == 15
            return self._r15
    
    cpdef void set(self, int reg, uint32_t value):
        """Escribe un registro (0-15)"""
        cdef int key
        
        if reg < 8:
            self._regs_common[reg] = value
        elif reg < 13:
            if self._mode == _MODE_FIQ:
                self._r8_r12_fiq[reg - 8] = value
            else:
                self._r8_r12_usr[reg - 8] = value
        elif reg == 13:
            key = self._get_bank_key(self._mode)
            self._r13_bank[key] = value
        elif reg == 14:
            key = self._get_bank_key(self._mode)
            self._r14_bank[key] = value
        else:  # reg == 15
            if self.thumb_mode:
                self._r15 = value & 0xFFFFFFFE
            else:
                self._r15 = value & 0xFFFFFFFC
    
    # Propiedades de acceso rápido
    @property
    def pc(self):
        return self._r15
    
    @pc.setter
    def pc(self, uint32_t value):
        self.set(15, value)
    
    @property
    def sp(self):
        return self.get(13)
    
    @sp.setter
    def sp(self, uint32_t value):
        self.set(13, value)
    
    @property
    def lr(self):
        return self.get(14)
    
    @lr.setter
    def lr(self, uint32_t value):
        self.set(14, value)
    
    @property
    def cpsr(self):
        self._sync_cpsr_from_flags()
        return self._cpsr
    
    @cpsr.setter
    def cpsr(self, uint32_t value):
        self._cpsr = value
        self._sync_flags_from_cpsr()
    
    @property
    def spsr(self):
        if self._mode in self._spsr:
            return self._spsr[self._mode]
        return self._cpsr
    
    @spsr.setter
    def spsr(self, uint32_t value):
        if self._mode in self._spsr:
            self._spsr[self._mode] = value
    
    cpdef void set_flags_nz(self, uint32_t result):
        """Establece flags N y Z"""
        self.flag_n = (result & 0x80000000) != 0
        self.flag_z = result == 0
    
    cpdef void set_flags_nzcv(self, uint32_t result, bint carry, bint overflow):
        """Establece todos los flags"""
        self.flag_n = (result & 0x80000000) != 0
        self.flag_z = result == 0
        self.flag_c = carry
        self.flag_v = overflow
    
    cpdef bint check_condition(self, int cond):
        """Verifica una condición ARM (4 bits)"""
        cdef bint n = self.flag_n
        cdef bint z = self.flag_z
        cdef bint c = self.flag_c
        cdef bint v = self.flag_v
        
        if cond == 0x0:    # EQ
            return z
        elif cond == 0x1:  # NE
            return not z
        elif cond == 0x2:  # CS/HS
            return c
        elif cond == 0x3:  # CC/LO
            return not c
        elif cond == 0x4:  # MI
            return n
        elif cond == 0x5:  # PL
            return not n
        elif cond == 0x6:  # VS
            return v
        elif cond == 0x7:  # VC
            return not v
        elif cond == 0x8:  # HI
            return c and not z
        elif cond == 0x9:  # LS
            return not c or z
        elif cond == 0xA:  # GE
            return n == v
        elif cond == 0xB:  # LT
            return n != v
        elif cond == 0xC:  # GT
            return not z and (n == v)
        elif cond == 0xD:  # LE
            return z or (n != v)
        else:  # AL, NV
            return True
    
    cpdef void switch_mode(self, int new_mode, bint save_cpsr=True):
        """Cambia a un nuevo modo de CPU"""
        if not CPUMode.is_valid(new_mode):
            return
        
        self._sync_cpsr_from_flags()
        
        if save_cpsr and CPUMode.has_spsr(new_mode):
            self._spsr[new_mode] = self._cpsr
        
        self._mode = new_mode
        self._cpsr = (self._cpsr & ~_MODE_MASK) | new_mode
    
    cpdef void restore_cpsr_from_spsr(self):
        """Restaura CPSR desde SPSR"""
        if CPUMode.has_spsr(self._mode):
            self._cpsr = self._spsr[self._mode]
            self._sync_flags_from_cpsr()
    
    def __str__(self):
        mode_names = {
            _MODE_USER: "USER", _MODE_FIQ: "FIQ", _MODE_IRQ: "IRQ",
            _MODE_SUPERVISOR: "SVC", _MODE_ABORT: "ABT",
            _MODE_UNDEFINED: "UND", _MODE_SYSTEM: "SYS",
        }
        
        lines = []
        lines.append(f"Mode: {mode_names.get(self._mode, 'UNK')} | {'THUMB' if self.thumb_mode else 'ARM'}")
        self._sync_cpsr_from_flags()
        lines.append(f"CPSR: {self._cpsr:08X} | N={int(self.flag_n)} Z={int(self.flag_z)} C={int(self.flag_c)} V={int(self.flag_v)} | I={int(self.irq_disabled)} F={int(self.fiq_disabled)}")
        lines.append("-" * 50)
        
        for i in range(0, 16, 4):
            regs = [f"R{j:2d}={self.get(j):08X}" for j in range(i, min(i+4, 16))]
            lines.append("  ".join(regs))
        
        return "\n".join(lines)