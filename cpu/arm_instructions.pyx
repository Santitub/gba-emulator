# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: nonecheck=False

"""
Instrucciones ARM (32-bit) para el ARM7TDMI - Versión Cython Optimizada
"""

from libc.stdint cimport uint32_t, int32_t, uint64_t, int64_t

cdef class ARMInstructions:
    """Decodificador y ejecutor de instrucciones ARM"""
    
    cdef object cpu
    cdef object reg
    cdef object mem
    
    def __init__(self, cpu):
        self.cpu = cpu
        self.reg = cpu.registers
        self.mem = cpu.memory
    
    # ===== Barrel Shifter - métodos internos (cdef) =====
    
    cdef tuple _shift_lsl(self, uint32_t value, int amount, bint carry):
        """Logical Shift Left"""
        cdef uint32_t result
        cdef bint carry_out
        
        if amount == 0:
            return value, carry
        elif amount < 32:
            carry_out = ((value >> (32 - amount)) & 1) != 0
            result = (value << amount) & 0xFFFFFFFF
            return result, carry_out
        elif amount == 32:
            return 0, (value & 1) != 0
        else:
            return 0, False
    
    cdef tuple _shift_lsr(self, uint32_t value, int amount, bint carry, bint immediate=False):
        """Logical Shift Right"""
        cdef uint32_t result
        cdef bint carry_out
        
        if amount == 0:
            if immediate:
                return 0, (value >> 31) != 0
            return value, carry
        elif amount < 32:
            carry_out = ((value >> (amount - 1)) & 1) != 0
            result = value >> amount
            return result, carry_out
        elif amount == 32:
            return 0, (value >> 31) != 0
        else:
            return 0, False
    
    cdef tuple _shift_asr(self, uint32_t value, int amount, bint carry, bint immediate=False):
        """Arithmetic Shift Right"""
        cdef uint32_t result
        cdef bint carry_out, sign
        
        if amount == 0:
            if immediate:
                amount = 32
            else:
                return value, carry
        
        sign = (value >> 31) != 0
        
        if amount >= 32:
            if sign:
                return 0xFFFFFFFF, True
            else:
                return 0, False
        
        carry_out = ((value >> (amount - 1)) & 1) != 0
        result = value >> amount
        
        if sign:
            result |= (0xFFFFFFFF << (32 - amount)) & 0xFFFFFFFF
        
        return result, carry_out
    
    cdef tuple _shift_ror(self, uint32_t value, int amount, bint carry, bint immediate=False):
        """Rotate Right"""
        cdef uint32_t result
        cdef bint carry_out
        
        if amount == 0:
            if immediate:
                return self._shift_rrx(value, carry)
            return value, carry
        
        amount &= 31
        if amount == 0:
            return value, (value >> 31) != 0
        
        result = ((value >> amount) | (value << (32 - amount))) & 0xFFFFFFFF
        carry_out = ((value >> (amount - 1)) & 1) != 0
        return result, carry_out
    
    cdef tuple _shift_rrx(self, uint32_t value, bint carry):
        """Rotate Right Extended"""
        cdef uint32_t result
        cdef bint carry_out
        
        carry_out = (value & 1) != 0
        result = (value >> 1) | ((<uint32_t>carry) << 31)
        return result, carry_out
    
    cdef tuple _apply_shift(self, uint32_t value, int shift_type, int amount,
                            bint carry, bint immediate=False):
        """Aplica el tipo de shift especificado"""
        if shift_type == 0:
            return self._shift_lsl(value, amount, carry)
        elif shift_type == 1:
            return self._shift_lsr(value, amount, carry, immediate)
        elif shift_type == 2:
            return self._shift_asr(value, amount, carry, immediate)
        else:
            return self._shift_ror(value, amount, carry, immediate)
    
    cdef tuple _get_operand2(self, uint32_t instruction, bint set_carry=True):
        """Obtiene el segundo operando de una instrucción de procesamiento de datos"""
        cdef uint32_t imm, result, rm_value
        cdef int rotate, rm, shift_type, shift_amount, rs
        cdef bint carry = self.reg.flag_c
        
        if instruction & (1 << 25):  # Immediate
            imm = instruction & 0xFF
            rotate = ((instruction >> 8) & 0xF) * 2
            
            if rotate == 0:
                return imm, carry
            
            result = ((imm >> rotate) | (imm << (32 - rotate))) & 0xFFFFFFFF
            if set_carry:
                carry = (result >> 31) != 0
            return result, carry
        else:
            rm = instruction & 0xF
            rm_value = self.reg.get(rm)
            
            if rm == 15:
                rm_value = self.cpu.get_prefetch_pc()
                if instruction & (1 << 4):
                    rm_value += 4
            
            shift_type = (instruction >> 5) & 0x3
            
            if instruction & (1 << 4):  # Shift by register
                rs = (instruction >> 8) & 0xF
                shift_amount = self.reg.get(rs) & 0xFF
                return self._apply_shift(rm_value, shift_type, shift_amount, carry, False)
            else:
                shift_amount = (instruction >> 7) & 0x1F
                return self._apply_shift(rm_value, shift_type, shift_amount, carry, True)
    
    # ===== ALU Operations =====
    
    cdef tuple _alu_add(self, uint32_t a, uint32_t b, bint carry_in=False):
        """Suma con flags"""
        cdef uint64_t result64
        cdef uint32_t result
        cdef bint carry, overflow
        
        result64 = <uint64_t>a + <uint64_t>b + <uint64_t>carry_in
        carry = result64 > 0xFFFFFFFF
        result = <uint32_t>(result64 & 0xFFFFFFFF)
        overflow = (((a ^ result) & (b ^ result)) >> 31) != 0
        
        return result, carry, overflow
    
    cdef tuple _alu_sub(self, uint32_t a, uint32_t b, bint carry_in=True):
        """Resta con flags"""
        cdef int64_t result64
        cdef uint32_t result
        cdef bint carry, overflow
        
        result64 = <int64_t>a - <int64_t>b - (0 if carry_in else 1)
        carry = result64 >= 0
        result = <uint32_t>(result64 & 0xFFFFFFFF)
        overflow = (((a ^ b) & (a ^ result)) >> 31) != 0
        
        return result, carry, overflow
    
    cpdef int execute(self, uint32_t instruction):
        """Ejecuta una instrucción ARM"""
        cdef int bits_27_25 = (instruction >> 25) & 0x7
        cdef int bit4, bit7, bits_7_4, opcode, bits_6_5
        
        # Branch (101)
        if bits_27_25 == 0b101:
            return self._execute_branch(instruction)
        
        # Block Data Transfer (100)
        if bits_27_25 == 0b100:
            return self._execute_block_transfer(instruction)
        
        # Single Data Transfer (01x)
        if bits_27_25 == 0b010 or bits_27_25 == 0b011:
            return self._execute_single_transfer(instruction)
        
        # Data Processing / PSR Transfer / Multiply (00x)
        if bits_27_25 == 0b000 or bits_27_25 == 0b001:
            if bits_27_25 == 0b000:
                bit4 = (instruction >> 4) & 1
                bit7 = (instruction >> 7) & 1
                
                if bit4 and bit7:
                    bits_7_4 = (instruction >> 4) & 0xF
                    if bits_7_4 == 0b1001:
                        return self._execute_multiply(instruction)
                    elif bits_7_4 in (0b1011, 0b1101, 0b1111):
                        return self._execute_halfword_transfer(instruction)
                    else:
                        return self._execute_multiply_long(instruction)
                
                if ((instruction >> 4) & 0xF) == 0b1001:
                    opcode = (instruction >> 20) & 0x1F
                    if opcode == 0b10000 or opcode == 0b10100:
                        return self._execute_swap(instruction)
                
                if bit7 and bit4:
                    bits_6_5 = (instruction >> 5) & 0x3
                    if bits_6_5 != 0:
                        return self._execute_halfword_transfer(instruction)
                
                if (instruction & 0x0FFFFFF0) == 0x012FFF10:
                    return self._execute_bx(instruction)
                
                opcode = (instruction >> 21) & 0xF
                if opcode in (0b1000, 0b1001, 0b1010, 0b1011) and not (instruction & (1 << 20)):
                    return self._execute_psr_transfer(instruction)
            
            return self._execute_data_processing(instruction)
        
        # Software Interrupt (111)
        if bits_27_25 == 0b111:
            return self._execute_swi(instruction)
        
        return 1
    
    cdef int _execute_data_processing(self, uint32_t instruction):
        """Ejecuta instrucciones de procesamiento de datos"""
        cdef int opcode = (instruction >> 21) & 0xF
        cdef bint s_bit = (instruction & (1 << 20)) != 0
        cdef int rn = (instruction >> 16) & 0xF
        cdef int rd = (instruction >> 12) & 0xF
        cdef uint32_t rn_value, op2, result = 0
        cdef bint shifter_carry, carry, overflow, write_result = True
        
        rn_value = self.reg.get(rn)
        if rn == 15:
            rn_value = self.cpu.get_prefetch_pc()
        
        op2, shifter_carry = self._get_operand2(instruction, s_bit)
        carry = self.reg.flag_c
        overflow = self.reg.flag_v
        
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
            result = rn_value & (~op2)
            carry = shifter_carry
        elif opcode == 0xF:  # MVN
            result = (~op2) & 0xFFFFFFFF
            carry = shifter_carry
        
        result &= 0xFFFFFFFF
        
        if write_result:
            self.reg.set(rd, result)
            if rd == 15:
                self.cpu.flush_pipeline()
                if s_bit:
                    self.reg.restore_cpsr_from_spsr()
                return 3
        
        if s_bit:
            self.reg.flag_n = (result & 0x80000000) != 0
            self.reg.flag_z = result == 0
            self.reg.flag_c = carry
            if opcode in (0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0xA, 0xB):
                self.reg.flag_v = overflow
        
        return 1
    
    cdef int _execute_multiply(self, uint32_t instruction):
        """Ejecuta MUL y MLA"""
        cdef int rd = (instruction >> 16) & 0xF
        cdef int rn = (instruction >> 12) & 0xF
        cdef int rs = (instruction >> 8) & 0xF
        cdef int rm = instruction & 0xF
        cdef bint accumulate = (instruction & (1 << 21)) != 0
        cdef bint s_bit = (instruction & (1 << 20)) != 0
        cdef uint32_t result
        
        result = (self.reg.get(rm) * self.reg.get(rs)) & 0xFFFFFFFF
        
        if accumulate:
            result = (result + self.reg.get(rn)) & 0xFFFFFFFF
        
        self.reg.set(rd, result)
        
        if s_bit:
            self.reg.flag_n = (result & 0x80000000) != 0
            self.reg.flag_z = result == 0
        
        return 2
    
    cdef int _execute_multiply_long(self, uint32_t instruction):
        """Ejecuta UMULL, UMLAL, SMULL, SMLAL"""
        cdef int rd_hi = (instruction >> 16) & 0xF
        cdef int rd_lo = (instruction >> 12) & 0xF
        cdef int rs = (instruction >> 8) & 0xF
        cdef int rm = instruction & 0xF
        cdef bint signed = (instruction & (1 << 22)) != 0
        cdef bint accumulate = (instruction & (1 << 21)) != 0
        cdef bint s_bit = (instruction & (1 << 20)) != 0
        cdef int64_t rm_val, rs_val, result
        cdef uint64_t acc
        
        rm_val = self.reg.get(rm)
        rs_val = self.reg.get(rs)
        
        if signed:
            if rm_val >= 0x80000000:
                rm_val -= 0x100000000
            if rs_val >= 0x80000000:
                rs_val -= 0x100000000
        
        result = rm_val * rs_val
        
        if accumulate:
            acc = (<uint64_t>self.reg.get(rd_hi) << 32) | self.reg.get(rd_lo)
            result += acc
        
        result &= 0xFFFFFFFFFFFFFFFF
        
        self.reg.set(rd_lo, <uint32_t>(result & 0xFFFFFFFF))
        self.reg.set(rd_hi, <uint32_t>((result >> 32) & 0xFFFFFFFF))
        
        if s_bit:
            self.reg.flag_n = (result & 0x8000000000000000) != 0
            self.reg.flag_z = result == 0
        
        return 3
    
    cdef int _execute_branch(self, uint32_t instruction):
        """Ejecuta B y BL"""
        cdef bint link = (instruction & (1 << 24)) != 0
        cdef int32_t offset = instruction & 0x00FFFFFF
        cdef uint32_t pc_at_execution, new_pc
        
        # Sign extend
        if offset & 0x800000:
            offset |= <int32_t>0xFF000000
        
        offset = offset << 2
        pc_at_execution = self.cpu._current_pc + 8
        
        if link:
            self.reg.lr = (self.cpu._current_pc + 4) & 0xFFFFFFFF
        
        new_pc = (pc_at_execution + offset) & 0xFFFFFFFF
        self.reg.pc = new_pc
        self.cpu.flush_pipeline()
        
        return 3
    
    cdef int _execute_bx(self, uint32_t instruction):
        """Ejecuta BX"""
        cdef int rm = instruction & 0xF
        cdef uint32_t rm_value = self.reg.get(rm)
        
        self.reg.thumb_mode = (rm_value & 1) != 0
        
        if self.reg.thumb_mode:
            self.reg.pc = rm_value & ~<uint32_t>1
        else:
            self.reg.pc = rm_value & ~<uint32_t>3
        
        self.cpu.flush_pipeline()
        return 3
    
    cdef int _execute_single_transfer(self, uint32_t instruction):
        """Ejecuta LDR, STR, LDRB, STRB"""
        cdef bint load = (instruction & (1 << 20)) != 0
        cdef bint byte_transfer = (instruction & (1 << 22)) != 0
        cdef bint write_back = (instruction & (1 << 21)) != 0
        cdef bint up = (instruction & (1 << 23)) != 0
        cdef bint pre_index = (instruction & (1 << 24)) != 0
        cdef bint immediate = not ((instruction & (1 << 25)) != 0)
        
        cdef int rn = (instruction >> 16) & 0xF
        cdef int rd = (instruction >> 12) & 0xF
        cdef int rm, shift_type, shift_amount
        cdef uint32_t base, offset, address, effective_address, value, misalign
        cdef int cycles = 1
        
        base = self.reg.get(rn)
        if rn == 15:
            base += 8
        
        if immediate:
            offset = instruction & 0xFFF
        else:
            rm = instruction & 0xF
            offset = self.reg.get(rm)
            shift_type = (instruction >> 5) & 0x3
            shift_amount = (instruction >> 7) & 0x1F
            offset, _ = self._apply_shift(offset, shift_type, shift_amount, False, True)
        
        if up:
            address = base + offset
        else:
            address = base - offset
        
        if pre_index:
            effective_address = address
        else:
            effective_address = base
        
        if load:
            if byte_transfer:
                value = self.mem.read_8(effective_address)
            else:
                value = self.mem.read_32(effective_address)
                misalign = effective_address & 3
                if misalign:
                    value = ((value >> (misalign * 8)) | (value << (32 - misalign * 8))) & 0xFFFFFFFF
            
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
            
            if byte_transfer:
                self.mem.write_8(effective_address, value & 0xFF)
            else:
                self.mem.write_32(effective_address, value)
            
            cycles = 2
        
        if write_back or not pre_index:
            if rn != 15:
                self.reg.set(rn, address)
        
        return cycles
    
    cdef int _execute_halfword_transfer(self, uint32_t instruction):
        """Ejecuta LDRH, STRH, LDRSB, LDRSH"""
        cdef bint load = (instruction & (1 << 20)) != 0
        cdef bint write_back = (instruction & (1 << 21)) != 0
        cdef bint immediate = (instruction & (1 << 22)) != 0
        cdef bint up = (instruction & (1 << 23)) != 0
        cdef bint pre_index = (instruction & (1 << 24)) != 0
        
        cdef int rn = (instruction >> 16) & 0xF
        cdef int rd = (instruction >> 12) & 0xF
        cdef int sh = (instruction >> 5) & 0x3
        cdef int rm
        
        cdef uint32_t base, offset, address, effective_address, value
        cdef int cycles = 1
        
        base = self.reg.get(rn)
        if rn == 15:
            base += 8
        
        if immediate:
            offset = ((instruction >> 4) & 0xF0) | (instruction & 0xF)
        else:
            rm = instruction & 0xF
            offset = self.reg.get(rm)
        
        if up:
            address = base + offset
        else:
            address = base - offset
        
        if pre_index:
            effective_address = address
        else:
            effective_address = base
        
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
    
    cdef int _execute_block_transfer(self, uint32_t instruction):
        """Ejecuta LDM y STM"""
        cdef bint load = (instruction & (1 << 20)) != 0
        cdef bint write_back = (instruction & (1 << 21)) != 0
        cdef bint s_bit = (instruction & (1 << 22)) != 0
        cdef bint up = (instruction & (1 << 23)) != 0
        cdef bint pre_index = (instruction & (1 << 24)) != 0
        
        cdef int rn = (instruction >> 16) & 0xF
        cdef int register_list = instruction & 0xFFFF
        
        cdef uint32_t base, address, final_address, value
        cdef int count = 0, i, cycles = 2
        
        base = self.reg.get(rn)
        
        # Count bits
        for i in range(16):
            if register_list & (1 << i):
                count += 1
        
        if count == 0:
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
                
                address += 4
                cycles += 1
        
        if write_back:
            self.reg.set(rn, final_address)
        
        if load and (register_list & (1 << 15)):
            self.cpu.flush_pipeline()
            if s_bit:
                self.reg.restore_cpsr_from_spsr()
            cycles += 2
        
        return cycles
    
    cdef int _execute_swap(self, uint32_t instruction):
        """Ejecuta SWP y SWPB"""
        cdef bint byte_swap = (instruction & (1 << 22)) != 0
        cdef int rn = (instruction >> 16) & 0xF
        cdef int rd = (instruction >> 12) & 0xF
        cdef int rm = instruction & 0xF
        cdef uint32_t address, old_value
        
        address = self.reg.get(rn)
        
        if byte_swap:
            old_value = self.mem.read_8(address)
            self.mem.write_8(address, self.reg.get(rm) & 0xFF)
        else:
            old_value = self.mem.read_32(address)
            self.mem.write_32(address, self.reg.get(rm))
        
        self.reg.set(rd, old_value)
        return 4
    
    cdef int _execute_psr_transfer(self, uint32_t instruction):
        """Ejecuta MRS y MSR"""
        cdef bint msr = (instruction & (1 << 21)) != 0
        cdef bint use_spsr = (instruction & (1 << 22)) != 0
        cdef int field_mask, rm, rd
        cdef uint32_t value, mask, old, imm
        cdef int rotate
        
        if msr:
            field_mask = (instruction >> 16) & 0xF
            
            if instruction & (1 << 25):
                imm = instruction & 0xFF
                rotate = ((instruction >> 8) & 0xF) * 2
                value = ((imm >> rotate) | (imm << (32 - rotate))) & 0xFFFFFFFF
            else:
                rm = instruction & 0xF
                value = self.reg.get(rm)
            
            mask = 0
            if field_mask & 1:
                mask |= 0x000000FF
            if field_mask & 2:
                mask |= 0x0000FF00
            if field_mask & 4:
                mask |= 0x00FF0000
            if field_mask & 8:
                mask |= 0xFF000000
            
            if use_spsr:
                old = self.reg.spsr
                self.reg.spsr = (old & ~mask) | (value & mask)
            else:
                if self.reg.mode == 0x10:
                    mask &= 0xFF000000
                old = self.reg.cpsr
                self.reg.cpsr = (old & ~mask) | (value & mask)
        else:
            rd = (instruction >> 12) & 0xF
            if use_spsr:
                self.reg.set(rd, self.reg.spsr)
            else:
                self.reg.set(rd, self.reg.cpsr)
        
        return 1
    
    cdef int _execute_swi(self, uint32_t instruction):
        """Ejecuta Software Interrupt"""
        self.cpu.trigger_swi()
        return 3