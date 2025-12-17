# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: nonecheck=False

"""
ARM7TDMI CPU Core - Versión Cython Optimizada
"""

from libc.stdint cimport uint32_t, int32_t

from .registers import CPURegisters, CPUMode
from .arm_instructions import ARMInstructions
from .thumb_instructions import ThumbInstructions


cdef class ARM7TDMI:
    """Emulación del procesador ARM7TDMI"""
    
    cdef public object memory
    cdef public object registers
    cdef public object arm_decoder
    cdef public object thumb_decoder
    
    cdef public bint pipeline_valid
    cdef public uint32_t cycles
    cdef public bint halted
    cdef public bint stopped
    
    cdef public uint32_t _current_instruction
    cdef public uint32_t _current_pc
    
    # Vectores de excepción
    cdef uint32_t VECTOR_RESET
    cdef uint32_t VECTOR_UNDEFINED
    cdef uint32_t VECTOR_SWI
    cdef uint32_t VECTOR_PREFETCH
    cdef uint32_t VECTOR_DATA
    cdef uint32_t VECTOR_IRQ
    cdef uint32_t VECTOR_FIQ
    
    def __init__(self, memory):
        self.memory = memory
        self.registers = CPURegisters()
        
        self.arm_decoder = ARMInstructions(self)
        self.thumb_decoder = ThumbInstructions(self)
        
        self.pipeline_valid = False
        self.cycles = 0
        self.halted = False
        self.stopped = False
        
        self._current_instruction = 0
        self._current_pc = 0
        
        # Inicializar vectores
        self.VECTOR_RESET     = 0x00000000
        self.VECTOR_UNDEFINED = 0x00000004
        self.VECTOR_SWI       = 0x00000008
        self.VECTOR_PREFETCH  = 0x0000000C
        self.VECTOR_DATA      = 0x00000010
        self.VECTOR_IRQ       = 0x00000018
        self.VECTOR_FIQ       = 0x0000001C
    
    cpdef void reset(self):
        """Reinicia la CPU"""
        self.registers.reset()
        self.pipeline_valid = False
        self.cycles = 0
        self.halted = False
        self.stopped = False
    
    cpdef void flush_pipeline(self):
        """Vacía el pipeline"""
        self.pipeline_valid = False
    
    cpdef int step(self):
        """Ejecuta una instrucción"""
        cdef uint32_t instruction
        cdef int cond, cyc
        
        if self.halted:
            return 1
        
        self._current_pc = self.registers.pc
        
        if self.registers.thumb_mode:
            instruction = self.memory.read_16(self.registers.pc)
            self.registers._r15 = (self.registers.pc + 2) & 0xFFFFFFFF
        else:
            instruction = self.memory.read_32(self.registers.pc)
            self.registers._r15 = (self.registers.pc + 4) & 0xFFFFFFFF
        
        self._current_instruction = instruction
        
        if self.registers.thumb_mode:
            cyc = self.thumb_decoder.execute(instruction)
        else:
            cond = (instruction >> 28) & 0xF
            if self.registers.check_condition(cond):
                cyc = self.arm_decoder.execute(instruction)
            else:
                cyc = 1
        
        self.cycles += cyc
        return cyc
    
    cpdef uint32_t get_prefetch_pc(self):
        """PC durante ejecución (PC + 8 para ARM, PC + 4 para THUMB)"""
        if self.registers.thumb_mode:
            return (self._current_pc + 4) & 0xFFFFFFFF
        else:
            return (self._current_pc + 8) & 0xFFFFFFFF
    
    cpdef void trigger_exception(self, uint32_t vector, int new_mode):
        """Dispara una excepción"""
        self.registers.switch_mode(new_mode, save_cpsr=True)
        self.registers.irq_disabled = True
        
        if new_mode == CPUMode.FIQ or vector == self.VECTOR_RESET:
            self.registers.fiq_disabled = True
        
        self.registers.thumb_mode = False
        self.registers.lr = self.registers.pc
        self.registers.pc = vector
        self.flush_pipeline()
    
    cpdef void trigger_irq(self):
        """Dispara IRQ"""
        if not self.registers.irq_disabled:
            self.registers._r14_bank[CPUMode.IRQ] = self.registers.pc
            self.trigger_exception(self.VECTOR_IRQ, CPUMode.IRQ)
            self.halted = False
    
    cpdef void trigger_swi(self):
        """Dispara SWI"""
        cdef uint32_t return_addr
        
        if self.registers.thumb_mode:
            return_addr = (self._current_pc + 2) & 0xFFFFFFFF
        else:
            return_addr = (self._current_pc + 4) & 0xFFFFFFFF
        
        self.registers._r14_bank[CPUMode.SUPERVISOR] = return_addr
        self.trigger_exception(self.VECTOR_SWI, CPUMode.SUPERVISOR)
    
    cpdef void halt(self):
        self.halted = True
    
    cpdef void stop(self):
        self.stopped = True
        self.halted = True
    
    def get_state_str(self):
        """Estado actual como string"""
        lines = ["=" * 60, "ARM7TDMI State", "=" * 60]
        lines.append(str(self.registers))
        lines.append("-" * 60)
        lines.append(f"Cycles: {self.cycles}")
        lines.append(f"Halted: {self.halted} | Stopped: {self.stopped}")
        
        if self.registers.thumb_mode:
            lines.append(f"Last: {self._current_pc:08X}: {self._current_instruction:04X} (THUMB)")
        else:
            lines.append(f"Last: {self._current_pc:08X}: {self._current_instruction:08X} (ARM)")
        
        return "\n".join(lines)