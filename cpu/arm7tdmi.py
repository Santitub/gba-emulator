"""
ARM7TDMI CPU Core - CORREGIDO
"""
from typing import TYPE_CHECKING
from .registers import CPURegisters, CPUMode, PSRFlags
from .arm_instructions import ARMInstructions
from .thumb_instructions import ThumbInstructions

if TYPE_CHECKING:
    from memory.memory_bus import MemoryBus


class ARM7TDMI:
    """
    Emulación del procesador ARM7TDMI
    Soporta instrucciones ARM (32-bit) y THUMB (16-bit)
    """
    
    VECTOR_RESET     = 0x00000000
    VECTOR_UNDEFINED = 0x00000004
    VECTOR_SWI       = 0x00000008
    VECTOR_PREFETCH  = 0x0000000C
    VECTOR_DATA      = 0x00000010
    VECTOR_IRQ       = 0x00000018
    VECTOR_FIQ       = 0x0000001C
    
    def __init__(self, memory: 'MemoryBus'):
        self.memory = memory
        self.registers = CPURegisters()
        
        # Decodificadores de instrucciones
        self.arm_decoder = ARMInstructions(self)
        self.thumb_decoder = ThumbInstructions(self)
        
        # Pipeline - NO pre-llenado
        self.pipeline_valid = False
        
        # Ciclos
        self.cycles = 0
        
        # Estado
        self.halted = False
        self.stopped = False
        
        # Debug
        self._current_instruction = 0
        self._current_pc = 0
        
    def reset(self) -> None:
        """Reinicia la CPU"""
        self.registers.reset()
        self.pipeline_valid = False
        self.cycles = 0
        self.halted = False
        self.stopped = False
        print(f"CPU Reset - PC: {self.registers.pc:08X}")
    
    def flush_pipeline(self) -> None:
        """Vacía el pipeline"""
        self.pipeline_valid = False
    
    def step(self) -> int:
        """Ejecuta una instrucción"""
        if self.halted:
            return 1
        
        # Guardar PC de la instrucción actual ANTES de fetch
        self._current_pc = self.registers.pc
        
        # Fetch de la instrucción
        if self.registers.thumb_mode:
            instruction = self.memory.read_16(self.registers.pc)
            self.registers._r15 = (self.registers.pc + 2) & 0xFFFFFFFF
        else:
            instruction = self.memory.read_32(self.registers.pc)
            self.registers._r15 = (self.registers.pc + 4) & 0xFFFFFFFF
        
        self._current_instruction = instruction
        
        # Execute
        if self.registers.thumb_mode:
            cycles = self.thumb_decoder.execute(instruction)
        else:
            cond = (instruction >> 28) & 0xF
            if self.registers.check_condition(cond):
                cycles = self.arm_decoder.execute(instruction)
            else:
                cycles = 1
            
        self.cycles += cycles
        return cycles
    
    def get_prefetch_pc(self) -> int:
        """
        Obtiene el valor de PC que se ve durante la ejecución
        (PC + 8 para ARM, PC + 4 para THUMB)
        """
        if self.registers.thumb_mode:
            return (self._current_pc + 4) & 0xFFFFFFFF
        else:
            return (self._current_pc + 8) & 0xFFFFFFFF
    
    def trigger_exception(self, vector: int, new_mode: int) -> None:
        """Dispara una excepción"""
        self.registers.switch_mode(new_mode, save_cpsr=True)
        self.registers.irq_disabled = True
        
        if new_mode == CPUMode.FIQ or vector == self.VECTOR_RESET:
            self.registers.fiq_disabled = True
            
        self.registers.thumb_mode = False
        self.registers.lr = self.registers.pc
        self.registers.pc = vector
        self.flush_pipeline()
    
    def trigger_irq(self) -> None:
        """Dispara IRQ"""
        if not self.registers.irq_disabled:
            # LR debe apuntar a la instrucción a la que volver + 4
            self.registers._r14_bank[CPUMode.IRQ] = self.registers.pc
            self.trigger_exception(self.VECTOR_IRQ, CPUMode.IRQ)
            self.halted = False
    
    def trigger_swi(self) -> None:
        """Dispara SWI"""
        # LR debe apuntar a la siguiente instrucción
        if self.registers.thumb_mode:
            self.registers._r14_bank[CPUMode.SUPERVISOR] = (self._current_pc + 2) & 0xFFFFFFFF
        else:
            self.registers._r14_bank[CPUMode.SUPERVISOR] = (self._current_pc + 4) & 0xFFFFFFFF
        self.trigger_exception(self.VECTOR_SWI, CPUMode.SUPERVISOR)
    
    def halt(self) -> None:
        self.halted = True
    
    def stop(self) -> None:
        self.stopped = True
        self.halted = True
    
    def get_state_str(self) -> str:
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