"""
Instrucciones ARM (32-bit) para el ARM7TDMI
Implementa el set completo de instrucciones ARM
"""
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .arm7tdmi import ARM7TDMI


class ARMInstructions:
    """
    Decodificador y ejecutor de instrucciones ARM
    """
    
    def __init__(self, cpu: 'ARM7TDMI'):
        self.cpu = cpu
        self.reg = cpu.registers
        self.mem = cpu.memory
        
    # ===== Utilidades de Barrel Shifter =====
    
    def _shift_lsl(self, value: int, amount: int, carry: bool) -> Tuple[int, bool]:
        """Logical Shift Left"""
        if amount == 0:
            return value, carry
        elif amount < 32:
            carry_out = bool((value >> (32 - amount)) & 1)
            result = (value << amount) & 0xFFFFFFFF
            return result, carry_out
        elif amount == 32:
            return 0, bool(value & 1)
        else:
            return 0, False
    
    def _shift_lsr(self, value: int, amount: int, carry: bool, immediate: bool = False) -> Tuple[int, bool]:
        """Logical Shift Right"""
        if amount == 0:
            if immediate:  # LSR #0 se interpreta como LSR #32
                return 0, bool(value >> 31)
            return value, carry
        elif amount < 32:
            carry_out = bool((value >> (amount - 1)) & 1)
            result = value >> amount
            return result, carry_out
        elif amount == 32:
            return 0, bool(value >> 31)
        else:
            return 0, False
    
    def _shift_asr(self, value: int, amount: int, carry: bool, immediate: bool = False) -> Tuple[int, bool]:
        """Arithmetic Shift Right"""
        if amount == 0:
            if immediate:  # ASR #0 se interpreta como ASR #32
                amount = 32
            else:
                return value, carry
        
        sign = value >> 31
        
        if amount >= 32:
            if sign:
                return 0xFFFFFFFF, True
            else:
                return 0, False
        
        carry_out = bool((value >> (amount - 1)) & 1)
        result = value >> amount
        
        if sign:
            # Extender signo
            result |= (0xFFFFFFFF << (32 - amount)) & 0xFFFFFFFF
            
        return result, carry_out
    
    def _shift_ror(self, value: int, amount: int, carry: bool, immediate: bool = False) -> Tuple[int, bool]:
        """Rotate Right"""
        if amount == 0:
            if immediate:  # ROR #0 se interpreta como RRX
                return self._shift_rrx(value, carry)
            return value, carry
        
        amount &= 31
        if amount == 0:
            return value, bool(value >> 31)
        
        result = ((value >> amount) | (value << (32 - amount))) & 0xFFFFFFFF
        carry_out = bool((value >> (amount - 1)) & 1)
        return result, carry_out
    
    def _shift_rrx(self, value: int, carry: bool) -> Tuple[int, bool]:
        """Rotate Right Extended (through carry)"""
        carry_out = bool(value & 1)
        result = (value >> 1) | (int(carry) << 31)
        return result, carry_out
    
    def _apply_shift(self, value: int, shift_type: int, amount: int, 
                     carry: bool, immediate: bool = False) -> Tuple[int, bool]:
        """Aplica el tipo de shift especificado"""
        if shift_type == 0:
            return self._shift_lsl(value, amount, carry)
        elif shift_type == 1:
            return self._shift_lsr(value, amount, carry, immediate)
        elif shift_type == 2:
            return self._shift_asr(value, amount, carry, immediate)
        else:  # shift_type == 3
            return self._shift_ror(value, amount, carry, immediate)
    
    def _get_operand2(self, instruction: int, set_carry: bool = True) -> Tuple[int, bool]:
        """
        Obtiene el segundo operando de una instrucción de procesamiento de datos
        """
        carry = self.reg.flag_c
        
        if instruction & (1 << 25):  # Immediate
            imm = instruction & 0xFF
            rotate = ((instruction >> 8) & 0xF) * 2
            
            if rotate == 0:
                return imm, carry
            
            result = ((imm >> rotate) | (imm << (32 - rotate))) & 0xFFFFFFFF
            if set_carry:
                carry = bool(result >> 31)
            return result, carry
        else:
            # Register with shift
            rm = instruction & 0xF
            rm_value = self.reg.get(rm)
            
            # Si Rm es PC, añadir offset del pipeline (PC + 8 para ARM)
            if rm == 15:
                rm_value = self.cpu.get_prefetch_pc()
                if instruction & (1 << 4):  # Register shift
                    rm_value += 4  # Ciclo extra para register shift
            
            shift_type = (instruction >> 5) & 0x3
            
            if instruction & (1 << 4):  # Shift by register
                rs = (instruction >> 8) & 0xF
                shift_amount = self.reg.get(rs) & 0xFF
                return self._apply_shift(rm_value, shift_type, shift_amount, carry, False)
            else:  # Shift by immediate
                shift_amount = (instruction >> 7) & 0x1F
                return self._apply_shift(rm_value, shift_type, shift_amount, carry, True)
    
    # ===== Operaciones de Datos =====
    
    def _alu_add(self, a: int, b: int, carry_in: bool = False) -> Tuple[int, bool, bool]:
        """Suma con flags"""
        a &= 0xFFFFFFFF
        b &= 0xFFFFFFFF
        result = a + b + int(carry_in)
        
        carry = result > 0xFFFFFFFF
        result &= 0xFFFFFFFF
        
        # Overflow: mismo signo en operandos, diferente en resultado
        overflow = ((a ^ result) & (b ^ result)) >> 31
        
        return result, carry, bool(overflow)
    
    def _alu_sub(self, a: int, b: int, carry_in: bool = True) -> Tuple[int, bool, bool]:
        """Resta con flags (a - b - !carry)"""
        a &= 0xFFFFFFFF
        b &= 0xFFFFFFFF
        result = a - b - (0 if carry_in else 1)
        
        carry = result >= 0
        result &= 0xFFFFFFFF
        
        # Overflow
        overflow = ((a ^ b) & (a ^ result)) >> 31
        
        return result, carry, bool(overflow)
    
    def execute(self, instruction: int) -> int:
        """
        Ejecuta una instrucción ARM
        
        Returns:
            Ciclos consumidos
        """
        # Identificar tipo de instrucción (bits 27-25 y otros)
        bits_27_25 = (instruction >> 25) & 0x7
        
        # Branch (101)
        if bits_27_25 == 0b101:
            return self._execute_branch(instruction)
        
        # Block Data Transfer (100)
        if bits_27_25 == 0b100:
            return self._execute_block_transfer(instruction)
        
        # Single Data Transfer (01x)
        if bits_27_25 in (0b010, 0b011):
            return self._execute_single_transfer(instruction)
        
        # Data Processing / PSR Transfer / Multiply (00x)
        if bits_27_25 in (0b000, 0b001):
            # Distinguir entre tipos
            if bits_27_25 == 0b000:
                bit4 = (instruction >> 4) & 1
                bit7 = (instruction >> 7) & 1
                
                # Multiply (bit 7=1, bit 4=1)
                if bit4 and bit7:
                    bits_7_4 = (instruction >> 4) & 0xF
                    if bits_7_4 == 0b1001:
                        return self._execute_multiply(instruction)
                    elif bits_7_4 in (0b1011, 0b1101, 0b1111):
                        return self._execute_halfword_transfer(instruction)
                    else:
                        return self._execute_multiply_long(instruction)
                
                # Swap (bits 24-20 = 1x0x0, bits 7-4 = 1001)
                if ((instruction >> 4) & 0xF) == 0b1001:
                    opcode = (instruction >> 20) & 0x1F
                    if opcode in (0b10000, 0b10100):
                        return self._execute_swap(instruction)
                
                # Halfword Transfer (bit 7=1, bit 4=1)
                if bit7 and bit4:
                    bits_6_5 = (instruction >> 5) & 0x3
                    if bits_6_5 != 0:
                        return self._execute_halfword_transfer(instruction)
                
                # Branch and Exchange
                if (instruction & 0x0FFFFFF0) == 0x012FFF10:
                    return self._execute_bx(instruction)
                
                # PSR Transfer
                opcode = (instruction >> 21) & 0xF
                s_bit = (instruction >> 20) & 1
                if opcode in (0b1000, 0b1001, 0b1010, 0b1011) and not s_bit:
                    return self._execute_psr_transfer(instruction)
            
            # Data Processing
            return self._execute_data_processing(instruction)
        
        # Software Interrupt (111)
        if bits_27_25 == 0b111:
            return self._execute_swi(instruction)
        
        # Instrucción no implementada/desconocida
        return 1
    
    def _execute_data_processing(self, instruction: int) -> int:
        """Ejecuta instrucciones de procesamiento de datos"""
        opcode = (instruction >> 21) & 0xF
        s_bit = bool(instruction & (1 << 20))
        rn = (instruction >> 16) & 0xF
        rd = (instruction >> 12) & 0xF
        
        # Obtener operandos
        rn_value = self.reg.get(rn)
        if rn == 15:
            rn_value = self.cpu.get_prefetch_pc()  # PC + 8
        
        op2, shifter_carry = self._get_operand2(instruction, s_bit)
        
        result = 0
        carry = self.reg.flag_c
        overflow = self.reg.flag_v
        write_result = True
        
        # Ejecutar operación según opcode
        if opcode == 0x0:  # AND
            result = rn_value & op2
            carry = shifter_carry
            
        elif opcode == 0x1:  # EOR
            result = rn_value ^ op2
            carry = shifter_carry
            
        elif opcode == 0x2:  # SUB
            result, carry, overflow = self._alu_sub(rn_value, op2)
            
        elif opcode == 0x3:  # RSB
            result, carry, overflow = self._alu_sub(op2, rn_value)
            
        elif opcode == 0x4:  # ADD
            result, carry, overflow = self._alu_add(rn_value, op2)
            
        elif opcode == 0x5:  # ADC
            result, carry, overflow = self._alu_add(rn_value, op2, self.reg.flag_c)
            
        elif opcode == 0x6:  # SBC
            result, carry, overflow = self._alu_sub(rn_value, op2, self.reg.flag_c)
            
        elif opcode == 0x7:  # RSC
            result, carry, overflow = self._alu_sub(op2, rn_value, self.reg.flag_c)
            
        elif opcode == 0x8:  # TST
            result = rn_value & op2
            carry = shifter_carry
            write_result = False
            
        elif opcode == 0x9:  # TEQ
            result = rn_value ^ op2
            carry = shifter_carry
            write_result = False
            
        elif opcode == 0xA:  # CMP
            result, carry, overflow = self._alu_sub(rn_value, op2)
            write_result = False
            
        elif opcode == 0xB:  # CMN
            result, carry, overflow = self._alu_add(rn_value, op2)
            write_result = False
            
        elif opcode == 0xC:  # ORR
            result = rn_value | op2
            carry = shifter_carry
            
        elif opcode == 0xD:  # MOV
            result = op2
            carry = shifter_carry
            
        elif opcode == 0xE:  # BIC
            result = rn_value & ~op2
            carry = shifter_carry
            
        elif opcode == 0xF:  # MVN
            result = ~op2 & 0xFFFFFFFF
            carry = shifter_carry
        
        result &= 0xFFFFFFFF
        
        # Escribir resultado
        if write_result:
            self.reg.set(rd, result)
            
            # Si Rd es PC
            if rd == 15:
                self.cpu.flush_pipeline()
                if s_bit:
                    self.reg.restore_cpsr_from_spsr()
                return 3
        
        # Actualizar flags si S está activado
        if s_bit:
            self.reg.flag_n = bool(result & 0x80000000)
            self.reg.flag_z = (result == 0)
            self.reg.flag_c = carry
            if opcode in (0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0xA, 0xB):
                self.reg.flag_v = overflow
        
        return 1
    
    def _execute_multiply(self, instruction: int) -> int:
        """Ejecuta MUL y MLA"""
        rd = (instruction >> 16) & 0xF
        rn = (instruction >> 12) & 0xF
        rs = (instruction >> 8) & 0xF
        rm = instruction & 0xF
        
        accumulate = bool(instruction & (1 << 21))
        s_bit = bool(instruction & (1 << 20))
        
        result = (self.reg.get(rm) * self.reg.get(rs)) & 0xFFFFFFFF
        
        if accumulate:  # MLA
            result = (result + self.reg.get(rn)) & 0xFFFFFFFF
        
        self.reg.set(rd, result)
        
        if s_bit:
            self.reg.flag_n = bool(result & 0x80000000)
            self.reg.flag_z = (result == 0)
            # C y V son UNPREDICTABLE
        
        # Ciclos: depende del multiplicador
        return 2  # Simplificado
    
    def _execute_multiply_long(self, instruction: int) -> int:
        """Ejecuta UMULL, UMLAL, SMULL, SMLAL"""
        rd_hi = (instruction >> 16) & 0xF
        rd_lo = (instruction >> 12) & 0xF
        rs = (instruction >> 8) & 0xF
        rm = instruction & 0xF
        
        signed = bool(instruction & (1 << 22))
        accumulate = bool(instruction & (1 << 21))
        s_bit = bool(instruction & (1 << 20))
        
        rm_val = self.reg.get(rm)
        rs_val = self.reg.get(rs)
        
        if signed:
            # Convertir a signed
            if rm_val >= 0x80000000:
                rm_val -= 0x100000000
            if rs_val >= 0x80000000:
                rs_val -= 0x100000000
        
        result = rm_val * rs_val
        
        if accumulate:
            acc = (self.reg.get(rd_hi) << 32) | self.reg.get(rd_lo)
            result += acc
        
        result &= 0xFFFFFFFFFFFFFFFF
        
        self.reg.set(rd_lo, result & 0xFFFFFFFF)
        self.reg.set(rd_hi, (result >> 32) & 0xFFFFFFFF)
        
        if s_bit:
            self.reg.flag_n = bool(result & 0x8000000000000000)
            self.reg.flag_z = (result == 0)
        
        return 3  # Simplificado
    
    def _execute_branch(self, instruction: int) -> int:
        """Ejecuta B y BL"""
        link = bool(instruction & (1 << 24))
        offset = instruction & 0x00FFFFFF
        
        # Sign extend el offset de 24 bits
        if offset & 0x800000:
            offset |= 0xFF000000
        
        # Convertir a signed para la suma
        if offset >= 0x80000000:
            offset = offset - 0x100000000
        
        # El offset está en words, convertir a bytes
        offset = offset << 2
        
        # PC durante ejecución = dirección de instrucción + 8
        pc_at_execution = self.cpu._current_pc + 8
        
        if link:
            # BL: guardar dirección de retorno (siguiente instrucción)
            self.reg.lr = (self.cpu._current_pc + 4) & 0xFFFFFFFF
        
        # Saltar
        new_pc = (pc_at_execution + offset) & 0xFFFFFFFF
        self.reg.pc = new_pc
        self.cpu.flush_pipeline()
        
        return 3
        
    def _execute_bx(self, instruction: int) -> int:
        """Ejecuta BX (Branch and Exchange)"""
        rm = instruction & 0xF
        rm_value = self.reg.get(rm)
        
        # Bit 0 determina el modo (Thumb o ARM)
        self.reg.thumb_mode = bool(rm_value & 1)
        
        # Saltar (alineado)
        if self.reg.thumb_mode:
            self.reg.pc = rm_value & ~1
        else:
            self.reg.pc = rm_value & ~3
        
        self.cpu.flush_pipeline()
        return 3
    
    def _execute_single_transfer(self, instruction: int) -> int:
        """Ejecuta LDR, STR, LDRB, STRB"""
        load = bool(instruction & (1 << 20))
        byte_transfer = bool(instruction & (1 << 22))
        write_back = bool(instruction & (1 << 21))
        up = bool(instruction & (1 << 23))
        pre_index = bool(instruction & (1 << 24))
        immediate = not bool(instruction & (1 << 25))
        
        rn = (instruction >> 16) & 0xF
        rd = (instruction >> 12) & 0xF
        
        base = self.reg.get(rn)
        if rn == 15:
            base += 8
        
        # Calcular offset
        if immediate:
            offset = instruction & 0xFFF
        else:
            rm = instruction & 0xF
            offset = self.reg.get(rm)
            shift_type = (instruction >> 5) & 0x3
            shift_amount = (instruction >> 7) & 0x1F
            offset, _ = self._apply_shift(offset, shift_type, shift_amount, False, True)
        
        # Calcular dirección
        if up:
            address = base + offset
        else:
            address = base - offset
        
        if pre_index:
            effective_address = address
        else:
            effective_address = base
        
        # Ejecutar transferencia
        cycles = 1
        
        if load:
            if byte_transfer:
                value = self.mem.read_8(effective_address)
            else:
                value = self.mem.read_32(effective_address)
                # Rotación para accesos no alineados
                misalign = effective_address & 3
                if misalign:
                    value = ((value >> (misalign * 8)) | 
                            (value << (32 - misalign * 8))) & 0xFFFFFFFF
            
            self.reg.set(rd, value)
            
            if rd == 15:
                self.cpu.flush_pipeline()
                cycles = 5
            else:
                cycles = 3
        else:
            value = self.reg.get(rd)
            if rd == 15:
                value += 4  # Pipeline
            
            if byte_transfer:
                self.mem.write_8(effective_address, value & 0xFF)
            else:
                self.mem.write_32(effective_address, value)
            
            cycles = 2
        
        # Write-back
        if write_back or not pre_index:
            if rn != 15:
                self.reg.set(rn, address)
        
        return cycles
    
    def _execute_halfword_transfer(self, instruction: int) -> int:
        """Ejecuta LDRH, STRH, LDRSB, LDRSH"""
        load = bool(instruction & (1 << 20))
        write_back = bool(instruction & (1 << 21))
        immediate = bool(instruction & (1 << 22))
        up = bool(instruction & (1 << 23))
        pre_index = bool(instruction & (1 << 24))
        
        rn = (instruction >> 16) & 0xF
        rd = (instruction >> 12) & 0xF
        
        sh = (instruction >> 5) & 0x3  # 01=H, 10=SB, 11=SH
        
        base = self.reg.get(rn)
        if rn == 15:
            base += 8
        
        # Offset
        if immediate:
            offset = ((instruction >> 4) & 0xF0) | (instruction & 0xF)
        else:
            rm = instruction & 0xF
            offset = self.reg.get(rm)
        
        # Dirección
        if up:
            address = base + offset
        else:
            address = base - offset
        
        if pre_index:
            effective_address = address
        else:
            effective_address = base
        
        cycles = 1
        
        if load:
            if sh == 1:  # LDRH
                value = self.mem.read_16(effective_address)
            elif sh == 2:  # LDRSB
                value = self.mem.read_8(effective_address)
                if value & 0x80:
                    value |= 0xFFFFFF00
            else:  # LDRSH
                value = self.mem.read_16(effective_address)
                if value & 0x8000:
                    value |= 0xFFFF0000
            
            self.reg.set(rd, value)
            
            if rd == 15:
                self.cpu.flush_pipeline()
                cycles = 5
            else:
                cycles = 3
        else:
            value = self.reg.get(rd)
            if rd == 15:
                value += 4
            
            if sh == 1:  # STRH
                self.mem.write_16(effective_address, value & 0xFFFF)
            
            cycles = 2
        
        if write_back or not pre_index:
            if rn != 15:
                self.reg.set(rn, address)
        
        return cycles
    
    def _execute_block_transfer(self, instruction: int) -> int:
        """Ejecuta LDM y STM"""
        load = bool(instruction & (1 << 20))
        write_back = bool(instruction & (1 << 21))
        s_bit = bool(instruction & (1 << 22))  # User bank transfer
        up = bool(instruction & (1 << 23))
        pre_index = bool(instruction & (1 << 24))
        
        rn = (instruction >> 16) & 0xF
        register_list = instruction & 0xFFFF
        
        base = self.reg.get(rn)
        
        # Contar registros
        count = bin(register_list).count('1')
        
        if count == 0:
            # Lista vacía - comportamiento especial
            if load:
                self.reg.pc = self.mem.read_32(base)
                self.cpu.flush_pipeline()
            else:
                self.mem.write_32(base, self.reg.pc + 4)
            
            if write_back:
                if up:
                    self.reg.set(rn, base + 0x40)
                else:
                    self.reg.set(rn, base - 0x40)
            return 2
        
        # Calcular dirección inicial
        if up:
            if pre_index:
                address = base + 4
            else:
                address = base
            final_address = base + count * 4
        else:
            if pre_index:
                address = base - count * 4
            else:
                address = base - count * 4 + 4
            final_address = base - count * 4
        
        cycles = 2
        
        for i in range(16):
            if register_list & (1 << i):
                if load:
                    value = self.mem.read_32(address)
                    self.reg.set(i, value)
                else:
                    value = self.reg.get(i)
                    if i == 15:
                        value += 4
                    self.mem.write_32(address, value)
                
                if up:
                    address += 4
                else:
                    address += 4  # Siempre incrementa en memoria
                
                cycles += 1
        
        # Write-back
        if write_back:
            self.reg.set(rn, final_address)
        
        # Si cargamos PC
        if load and (register_list & (1 << 15)):
            self.cpu.flush_pipeline()
            if s_bit:
                self.reg.restore_cpsr_from_spsr()
            cycles += 2
        
        return cycles
    
    def _execute_swap(self, instruction: int) -> int:
        """Ejecuta SWP y SWPB"""
        byte_swap = bool(instruction & (1 << 22))
        rn = (instruction >> 16) & 0xF
        rd = (instruction >> 12) & 0xF
        rm = instruction & 0xF
        
        address = self.reg.get(rn)
        
        if byte_swap:
            old_value = self.mem.read_8(address)
            self.mem.write_8(address, self.reg.get(rm) & 0xFF)
        else:
            old_value = self.mem.read_32(address)
            self.mem.write_32(address, self.reg.get(rm))
        
        self.reg.set(rd, old_value)
        
        return 4
    
    def _execute_psr_transfer(self, instruction: int) -> int:
        """Ejecuta MRS y MSR"""
        # MRS: Move PSR to Register
        # MSR: Move Register to PSR
        
        msr = bool(instruction & (1 << 21))  # 0=MRS, 1=MSR
        use_spsr = bool(instruction & (1 << 22))
        
        if msr:  # MSR
            # Determinar qué campos escribir
            field_mask = (instruction >> 16) & 0xF
            
            # Obtener valor fuente
            if instruction & (1 << 25):  # Immediate
                imm = instruction & 0xFF
                rotate = ((instruction >> 8) & 0xF) * 2
                value = ((imm >> rotate) | (imm << (32 - rotate))) & 0xFFFFFFFF
            else:
                rm = instruction & 0xF
                value = self.reg.get(rm)
            
            # Construir máscara
            mask = 0
            if field_mask & 1:  # Control
                mask |= 0x000000FF
            if field_mask & 2:  # Extension
                mask |= 0x0000FF00
            if field_mask & 4:  # Status
                mask |= 0x00FF0000
            if field_mask & 8:  # Flags
                mask |= 0xFF000000
            
            if use_spsr:
                old = self.reg.spsr
                self.reg.spsr = (old & ~mask) | (value & mask)
            else:
                # En modo User, solo se pueden cambiar los flags
                if self.reg.mode == 0x10:
                    mask &= 0xFF000000
                
                old = self.reg.cpsr
                self.reg.cpsr = (old & ~mask) | (value & mask)
        else:  # MRS
            rd = (instruction >> 12) & 0xF
            
            if use_spsr:
                self.reg.set(rd, self.reg.spsr)
            else:
                self.reg.set(rd, self.reg.cpsr)
        
        return 1
    
    def _execute_swi(self, instruction: int) -> int:
        """Ejecuta Software Interrupt"""
        # El número del SWI está en los bits 0-23
        # swi_number = instruction & 0x00FFFFFF
        
        self.cpu.trigger_swi()
        return 3