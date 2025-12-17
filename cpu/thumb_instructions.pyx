# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: nonecheck=False

"""
Instrucciones THUMB (16-bit) para el ARM7TDMI - Versión Cython Optimizada
"""

from libc.stdint cimport uint32_t, int32_t, uint16_t, uint64_t, int64_t

cdef class ThumbInstructions:
    """Decodificador y ejecutor de instrucciones THUMB"""
    
    cdef object cpu
    cdef object reg
    cdef object mem
    
    def __init__(self, cpu):
        self.cpu = cpu
        self.reg = cpu.registers
        self.mem = cpu.memory
    
    # ===== Utilidades (cdef para uso interno) =====
    
    cdef tuple _alu_add(self, uint32_t a, uint32_t b, bint carry_in=False):
        """Suma con flags"""
        cdef uint64_t result64 = <uint64_t>a + <uint64_t>b + <uint64_t>carry_in
        cdef bint carry = result64 > 0xFFFFFFFF
        cdef uint32_t result = <uint32_t>(result64 & 0xFFFFFFFF)
        cdef bint overflow = (((a ^ result) & (b ^ result)) >> 31) != 0
        return result, carry, overflow
    
    cdef tuple _alu_sub(self, uint32_t a, uint32_t b, bint carry_in=True):
        """Resta con flags"""
        cdef int64_t result64 = <int64_t>a - <int64_t>b - (0 if carry_in else 1)
        cdef bint carry = (a >= b) if carry_in else (a > b)
        cdef uint32_t result = <uint32_t>(result64 & 0xFFFFFFFF)
        cdef bint overflow = (((a ^ b) & (a ^ result)) >> 31) != 0
        return result, carry, overflow
    
    cdef void _set_nz(self, uint32_t value):
        """Establece flags N y Z"""
        self.reg.flag_n = (value & 0x80000000) != 0
        self.reg.flag_z = value == 0
    
    cdef void _set_nzc(self, uint32_t value, bint carry):
        """Establece flags N, Z y C"""
        self._set_nz(value)
        self.reg.flag_c = carry
    
    cdef void _set_nzcv(self, uint32_t value, bint carry, bint overflow):
        """Establece todos los flags"""
        self._set_nz(value)
        self.reg.flag_c = carry
        self.reg.flag_v = overflow
    
    cpdef int execute(self, uint16_t instruction):
        """Ejecuta una instrucción THUMB"""
        cdef int top3 = instruction >> 13
        cdef int op, cond
        
        # Format 1: Move shifted register (000xx)
        if top3 == 0b000:
            op = (instruction >> 11) & 0x3
            if op != 0b11:
                return self._format1_shift(instruction)
            else:
                return self._format2_add_sub(instruction)
        
        # Format 3: Move/Compare/Add/Sub immediate (001xx)
        if top3 == 0b001:
            return self._format3_immediate(instruction)
        
        # Format 4 y 5 (010...)
        if (instruction >> 10) == 0b010000:
            return self._format4_alu(instruction)
        
        if (instruction >> 10) == 0b010001:
            return self._format5_hireg_bx(instruction)
        
        # Format 6: PC-relative load (01001)
        if (instruction >> 11) == 0b01001:
            return self._format6_pc_load(instruction)
        
        # Format 7 y 8 (0101...)
        if (instruction >> 12) == 0b0101:
            if not (instruction & (1 << 9)):
                return self._format7_load_store_reg(instruction)
            else:
                return self._format8_load_store_signed(instruction)
        
        # Format 9: Load/Store immediate offset (011xx)
        if top3 == 0b011:
            return self._format9_load_store_imm(instruction)
        
        # Format 10: Load/Store halfword (1000x)
        if (instruction >> 12) == 0b1000:
            return self._format10_load_store_half(instruction)
        
        # Format 11: SP-relative load/store (1001x)
        if (instruction >> 12) == 0b1001:
            return self._format11_sp_relative(instruction)
        
        # Format 12: Load address (1010x)
        if (instruction >> 12) == 0b1010:
            return self._format12_load_address(instruction)
        
        # Format 13: Add offset to SP (10110000)
        if (instruction >> 8) == 0b10110000:
            return self._format13_sp_offset(instruction)
        
        # Format 14: Push/Pop (1011x10x)
        if (instruction >> 12) == 0b1011 and ((instruction >> 9) & 0x3) == 0b10:
            return self._format14_push_pop(instruction)
        
        # Format 15: Multiple load/store (1100x)
        if (instruction >> 12) == 0b1100:
            return self._format15_multiple(instruction)
        
        # Format 16/17: Conditional branch / SWI (1101xxxx)
        if (instruction >> 12) == 0b1101:
            cond = (instruction >> 8) & 0xF
            if cond < 0xE:
                return self._format16_cond_branch(instruction)
            elif cond == 0xF:
                return self._format17_swi(instruction)
        
        # Format 18: Unconditional branch (11100)
        if (instruction >> 11) == 0b11100:
            return self._format18_branch(instruction)
        
        # Format 19: Long branch with link (1111x)
        if (instruction >> 12) == 0b1111:
            return self._format19_long_branch(instruction)
        
        return 1
    
    cdef int _format1_shift(self, uint16_t instruction):
        """LSL, LSR, ASR con offset inmediato"""
        cdef int op = (instruction >> 11) & 0x3
        cdef int offset = (instruction >> 6) & 0x1F
        cdef int rs = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t rs_value = self.reg.get(rs)
        cdef uint32_t result
        cdef bint carry = self.reg.flag_c
        
        if op == 0b00:  # LSL
            if offset == 0:
                result = rs_value
            else:
                carry = ((rs_value >> (32 - offset)) & 1) != 0
                result = (rs_value << offset) & 0xFFFFFFFF
        elif op == 0b01:  # LSR
            if offset == 0:
                offset = 32
            if offset == 32:
                carry = (rs_value >> 31) != 0
                result = 0
            else:
                carry = ((rs_value >> (offset - 1)) & 1) != 0
                result = rs_value >> offset
        else:  # ASR
            if offset == 0:
                offset = 32
            if offset >= 32:
                carry = (rs_value >> 31) != 0
                result = 0xFFFFFFFF if carry else 0
            else:
                carry = ((rs_value >> (offset - 1)) & 1) != 0
                result = rs_value >> offset
                if rs_value & 0x80000000:
                    result |= (0xFFFFFFFF << (32 - offset)) & 0xFFFFFFFF
        
        self.reg.set(rd, result)
        self._set_nzc(result, carry)
        return 1
    
    cdef int _format2_add_sub(self, uint16_t instruction):
        """ADD/SUB con registro o inmediato de 3 bits"""
        cdef bint imm_flag = (instruction & (1 << 10)) != 0
        cdef bint sub_flag = (instruction & (1 << 9)) != 0
        cdef int rn_or_imm = (instruction >> 6) & 0x7
        cdef int rs = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t rs_value = self.reg.get(rs)
        cdef uint32_t operand = rn_or_imm if imm_flag else self.reg.get(rn_or_imm)
        cdef uint32_t result
        cdef bint carry, overflow
        
        if sub_flag:
            result, carry, overflow = self._alu_sub(rs_value, operand)
        else:
            result, carry, overflow = self._alu_add(rs_value, operand)
        
        self.reg.set(rd, result)
        self._set_nzcv(result, carry, overflow)
        return 1
    
    cdef int _format3_immediate(self, uint16_t instruction):
        """MOV, CMP, ADD, SUB con inmediato de 8 bits"""
        cdef int op = (instruction >> 11) & 0x3
        cdef int rd = (instruction >> 8) & 0x7
        cdef uint32_t imm = instruction & 0xFF
        cdef uint32_t rd_value = self.reg.get(rd)
        cdef uint32_t result
        cdef bint carry, overflow
        
        if op == 0b00:  # MOV
            self.reg.set(rd, imm)
            self._set_nz(imm)
        elif op == 0b01:  # CMP
            result, carry, overflow = self._alu_sub(rd_value, imm)
            self._set_nzcv(result, carry, overflow)
        elif op == 0b10:  # ADD
            result, carry, overflow = self._alu_add(rd_value, imm)
            self.reg.set(rd, result)
            self._set_nzcv(result, carry, overflow)
        else:  # SUB
            result, carry, overflow = self._alu_sub(rd_value, imm)
            self.reg.set(rd, result)
            self._set_nzcv(result, carry, overflow)
        
        return 1
    
    cdef int _format4_alu(self, uint16_t instruction):
        """Operaciones ALU entre registros bajos"""
        cdef int op = (instruction >> 6) & 0xF
        cdef int rs = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t rd_value = self.reg.get(rd)
        cdef uint32_t rs_value = self.reg.get(rs)
        cdef uint32_t result
        cdef bint carry = self.reg.flag_c
        cdef bint overflow = self.reg.flag_v
        cdef int shift, cycles = 1
        cdef bint sign
        
        if op == 0x0:  # AND
            result = rd_value & rs_value
            self._set_nz(result)
            self.reg.set(rd, result)
        elif op == 0x1:  # EOR
            result = rd_value ^ rs_value
            self._set_nz(result)
            self.reg.set(rd, result)
        elif op == 0x2:  # LSL
            shift = rs_value & 0xFF
            if shift == 0:
                result = rd_value
            elif shift < 32:
                carry = ((rd_value >> (32 - shift)) & 1) != 0
                result = (rd_value << shift) & 0xFFFFFFFF
            elif shift == 32:
                carry = (rd_value & 1) != 0
                result = 0
            else:
                carry = False
                result = 0
            self._set_nzc(result, carry)
            self.reg.set(rd, result)
            cycles = 2
        elif op == 0x3:  # LSR
            shift = rs_value & 0xFF
            if shift == 0:
                result = rd_value
            elif shift < 32:
                carry = ((rd_value >> (shift - 1)) & 1) != 0
                result = rd_value >> shift
            elif shift == 32:
                carry = (rd_value >> 31) != 0
                result = 0
            else:
                carry = False
                result = 0
            self._set_nzc(result, carry)
            self.reg.set(rd, result)
            cycles = 2
        elif op == 0x4:  # ASR
            shift = rs_value & 0xFF
            sign = (rd_value >> 31) != 0
            if shift == 0:
                result = rd_value
            elif shift < 32:
                carry = ((rd_value >> (shift - 1)) & 1) != 0
                result = rd_value >> shift
                if sign:
                    result |= (0xFFFFFFFF << (32 - shift)) & 0xFFFFFFFF
            else:
                carry = sign
                result = 0xFFFFFFFF if sign else 0
            self._set_nzc(result, carry)
            self.reg.set(rd, result)
            cycles = 2
        elif op == 0x5:  # ADC
            result, carry, overflow = self._alu_add(rd_value, rs_value, self.reg.flag_c)
            self._set_nzcv(result, carry, overflow)
            self.reg.set(rd, result)
        elif op == 0x6:  # SBC
            result, carry, overflow = self._alu_sub(rd_value, rs_value, self.reg.flag_c)
            self._set_nzcv(result, carry, overflow)
            self.reg.set(rd, result)
        elif op == 0x7:  # ROR
            shift = rs_value & 0xFF
            if shift == 0:
                result = rd_value
            else:
                shift &= 31
                if shift == 0:
                    carry = (rd_value >> 31) != 0
                    result = rd_value
                else:
                    carry = ((rd_value >> (shift - 1)) & 1) != 0
                    result = ((rd_value >> shift) | (rd_value << (32 - shift))) & 0xFFFFFFFF
            self._set_nzc(result, carry)
            self.reg.set(rd, result)
            cycles = 2
        elif op == 0x8:  # TST
            result = rd_value & rs_value
            self._set_nz(result)
        elif op == 0x9:  # NEG
            result, carry, overflow = self._alu_sub(0, rs_value)
            self._set_nzcv(result, carry, overflow)
            self.reg.set(rd, result)
        elif op == 0xA:  # CMP
            result, carry, overflow = self._alu_sub(rd_value, rs_value)
            self._set_nzcv(result, carry, overflow)
        elif op == 0xB:  # CMN
            result, carry, overflow = self._alu_add(rd_value, rs_value)
            self._set_nzcv(result, carry, overflow)
        elif op == 0xC:  # ORR
            result = rd_value | rs_value
            self._set_nz(result)
            self.reg.set(rd, result)
        elif op == 0xD:  # MUL
            result = (rd_value * rs_value) & 0xFFFFFFFF
            self._set_nz(result)
            self.reg.set(rd, result)
            cycles = 2
        elif op == 0xE:  # BIC
            result = rd_value & (~rs_value)
            self._set_nz(result)
            self.reg.set(rd, result)
        else:  # MVN
            result = (~rs_value) & 0xFFFFFFFF
            self._set_nz(result)
            self.reg.set(rd, result)
        
        return cycles
    
    cdef int _format5_hireg_bx(self, uint16_t instruction):
        """ADD, CMP, MOV con registros altos, BX"""
        cdef int op = (instruction >> 8) & 0x3
        cdef bint h1 = (instruction & (1 << 7)) != 0
        cdef bint h2 = (instruction & (1 << 6)) != 0
        cdef int rs = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t rs_value, rd_value, result
        cdef bint carry, overflow
        
        if h2:
            rs += 8
        if h1:
            rd += 8
        
        rs_value = self.reg.get(rs)
        
        if op == 0b00:  # ADD
            rd_value = self.reg.get(rd)
            result = (rd_value + rs_value) & 0xFFFFFFFF
            self.reg.set(rd, result)
            if rd == 15:
                self.cpu.flush_pipeline()
                return 3
        elif op == 0b01:  # CMP
            rd_value = self.reg.get(rd)
            result, carry, overflow = self._alu_sub(rd_value, rs_value)
            self._set_nzcv(result, carry, overflow)
        elif op == 0b10:  # MOV
            self.reg.set(rd, rs_value)
            if rd == 15:
                self.cpu.flush_pipeline()
                return 3
        else:  # BX
            self.reg.thumb_mode = (rs_value & 1) != 0
            if self.reg.thumb_mode:
                self.reg.pc = rs_value & ~<uint32_t>1
            else:
                self.reg.pc = rs_value & ~<uint32_t>3
            self.cpu.flush_pipeline()
            return 3
        
        return 1
    
    cdef int _format6_pc_load(self, uint16_t instruction):
        """LDR Rd, [PC, #imm]"""
        cdef int rd = (instruction >> 8) & 0x7
        cdef uint32_t imm = (instruction & 0xFF) << 2
        cdef uint32_t pc = self.reg.pc & ~<uint32_t>3
        cdef uint32_t address = pc + imm
        cdef uint32_t value = self.mem.read_32(address)
        
        self.reg.set(rd, value)
        return 3
    
    cdef int _format7_load_store_reg(self, uint16_t instruction):
        """LDR, STR, LDRB, STRB con offset de registro"""
        cdef bint load = (instruction & (1 << 11)) != 0
        cdef bint byte_transfer = (instruction & (1 << 10)) != 0
        cdef int ro = (instruction >> 6) & 0x7
        cdef int rb = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t address = (self.reg.get(rb) + self.reg.get(ro)) & 0xFFFFFFFF
        cdef uint32_t value, misalign
        
        if load:
            if byte_transfer:
                value = self.mem.read_8(address)
            else:
                value = self.mem.read_32(address)
                misalign = address & 3
                if misalign:
                    value = ((value >> (misalign * 8)) | (value << (32 - misalign * 8))) & 0xFFFFFFFF
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd)
            if byte_transfer:
                self.mem.write_8(address, value & 0xFF)
            else:
                self.mem.write_32(address, value)
            return 2
    
    cdef int _format8_load_store_signed(self, uint16_t instruction):
        """STRH, LDSB, LDRH, LDSH"""
        cdef bint h_flag = (instruction & (1 << 11)) != 0
        cdef bint s_flag = (instruction & (1 << 10)) != 0
        cdef int ro = (instruction >> 6) & 0x7
        cdef int rb = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t address = (self.reg.get(rb) + self.reg.get(ro)) & 0xFFFFFFFF
        cdef uint32_t value
        
        if not s_flag and not h_flag:  # STRH
            value = self.reg.get(rd) & 0xFFFF
            self.mem.write_16(address, value)
            return 2
        elif not s_flag and h_flag:  # LDRH
            value = self.mem.read_16(address)
            self.reg.set(rd, value)
            return 3
        elif s_flag and not h_flag:  # LDSB
            value = self.mem.read_8(address)
            if value & 0x80:
                value |= 0xFFFFFF00
            self.reg.set(rd, value)
            return 3
        else:  # LDSH
            value = self.mem.read_16(address)
            if value & 0x8000:
                value |= 0xFFFF0000
            self.reg.set(rd, value)
            return 3
    
    cdef int _format9_load_store_imm(self, uint16_t instruction):
        """LDR, STR, LDRB, STRB con offset inmediato"""
        cdef bint byte_transfer = (instruction & (1 << 12)) != 0
        cdef bint load = (instruction & (1 << 11)) != 0
        cdef int offset = (instruction >> 6) & 0x1F
        cdef int rb = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t address, value, misalign
        
        if not byte_transfer:
            offset <<= 2
        
        address = (self.reg.get(rb) + offset) & 0xFFFFFFFF
        
        if load:
            if byte_transfer:
                value = self.mem.read_8(address)
            else:
                value = self.mem.read_32(address)
                misalign = address & 3
                if misalign:
                    value = ((value >> (misalign * 8)) | (value << (32 - misalign * 8))) & 0xFFFFFFFF
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd)
            if byte_transfer:
                self.mem.write_8(address, value & 0xFF)
            else:
                self.mem.write_32(address, value)
            return 2
    
    cdef int _format10_load_store_half(self, uint16_t instruction):
        """LDRH, STRH con offset inmediato"""
        cdef bint load = (instruction & (1 << 11)) != 0
        cdef int offset = ((instruction >> 6) & 0x1F) << 1
        cdef int rb = (instruction >> 3) & 0x7
        cdef int rd = instruction & 0x7
        cdef uint32_t address = (self.reg.get(rb) + offset) & 0xFFFFFFFF
        cdef uint32_t value
        
        if load:
            value = self.mem.read_16(address)
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd) & 0xFFFF
            self.mem.write_16(address, value)
            return 2
    
    cdef int _format11_sp_relative(self, uint16_t instruction):
        """LDR, STR relativo a SP"""
        cdef bint load = (instruction & (1 << 11)) != 0
        cdef int rd = (instruction >> 8) & 0x7
        cdef int offset = (instruction & 0xFF) << 2
        cdef uint32_t address = (self.reg.sp + offset) & 0xFFFFFFFF
        cdef uint32_t value
        
        if load:
            value = self.mem.read_32(address)
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd)
            self.mem.write_32(address, value)
            return 2
    
    cdef int _format12_load_address(self, uint16_t instruction):
        """ADD Rd, PC/SP, #imm"""
        cdef bint sp_flag = (instruction & (1 << 11)) != 0
        cdef int rd = (instruction >> 8) & 0x7
        cdef int offset = (instruction & 0xFF) << 2
        cdef uint32_t base, result
        
        if sp_flag:
            base = self.reg.sp
        else:
            base = self.reg.pc & ~<uint32_t>3
        
        result = (base + offset) & 0xFFFFFFFF
        self.reg.set(rd, result)
        return 1
    
    cdef int _format13_sp_offset(self, uint16_t instruction):
        """ADD SP, #imm o SUB SP, #imm"""
        cdef bint negative = (instruction & (1 << 7)) != 0
        cdef int offset = (instruction & 0x7F) << 2
        cdef uint32_t result
        
        if negative:
            result = (self.reg.sp - offset) & 0xFFFFFFFF
        else:
            result = (self.reg.sp + offset) & 0xFFFFFFFF
        
        self.reg.sp = result
        return 1
    
    cdef int _format14_push_pop(self, uint16_t instruction):
        """PUSH y POP"""
        cdef bint load = (instruction & (1 << 11)) != 0
        cdef bint pc_lr = (instruction & (1 << 8)) != 0
        cdef int rlist = instruction & 0xFF
        cdef int count = 0, i, cycles = 2
        cdef uint32_t address, value
        
        # Count bits
        for i in range(8):
            if rlist & (1 << i):
                count += 1
        if pc_lr:
            count += 1
        
        if load:  # POP
            address = self.reg.sp
            
            for i in range(8):
                if rlist & (1 << i):
                    value = self.mem.read_32(address)
                    self.reg.set(i, value)
                    address += 4
                    cycles += 1
            
            if pc_lr:
                value = self.mem.read_32(address)
                self.reg.thumb_mode = (value & 1) != 0
                self.reg.pc = value & ~<uint32_t>1
                self.cpu.flush_pipeline()
                address += 4
                cycles += 2
            
            self.reg.sp = address
        else:  # PUSH
            address = self.reg.sp - count * 4
            self.reg.sp = address
            
            for i in range(8):
                if rlist & (1 << i):
                    self.mem.write_32(address, self.reg.get(i))
                    address += 4
                    cycles += 1
            
            if pc_lr:
                self.mem.write_32(address, self.reg.lr)
                cycles += 1
        
        return cycles
    
    cdef int _format15_multiple(self, uint16_t instruction):
        """LDMIA, STMIA"""
        cdef bint load = (instruction & (1 << 11)) != 0
        cdef int rb = (instruction >> 8) & 0x7
        cdef int rlist = instruction & 0xFF
        cdef uint32_t address = self.reg.get(rb)
        cdef uint32_t value
        cdef int i, cycles = 2
        
        if load:
            for i in range(8):
                if rlist & (1 << i):
                    value = self.mem.read_32(address)
                    self.reg.set(i, value)
                    address += 4
                    cycles += 1
        else:
            for i in range(8):
                if rlist & (1 << i):
                    self.mem.write_32(address, self.reg.get(i))
                    address += 4
                    cycles += 1
        
        if not (load and (rlist & (1 << rb))):
            self.reg.set(rb, address)
        
        return cycles
    
    cdef int _format16_cond_branch(self, uint16_t instruction):
        """B{cond} label"""
        cdef int cond = (instruction >> 8) & 0xF
        cdef int32_t offset = instruction & 0xFF
        cdef uint32_t pc_at_execution, new_pc
        
        # Sign extend
        if offset & 0x80:
            offset |= <int32_t>0xFFFFFF00
        
        offset = offset << 1
        pc_at_execution = self.cpu._current_pc + 4
        
        if self.reg.check_condition(cond):
            new_pc = (pc_at_execution + offset) & 0xFFFFFFFF
            self.reg.pc = new_pc
            self.cpu.flush_pipeline()
            return 3
        
        return 1
    
    cdef int _format17_swi(self, uint16_t instruction):
        """SWI"""
        self.cpu.trigger_swi()
        return 3
    
    cdef int _format18_branch(self, uint16_t instruction):
        """B label (incondicional)"""
        cdef int32_t offset = instruction & 0x7FF
        cdef uint32_t pc_at_execution, new_pc
        
        # Sign extend
        if offset & 0x400:
            offset |= <int32_t>0xFFFFF800
        
        offset = offset << 1
        pc_at_execution = self.cpu._current_pc + 4
        
        new_pc = (pc_at_execution + offset) & 0xFFFFFFFF
        self.reg.pc = new_pc
        self.cpu.flush_pipeline()
        
        return 3
    
    cdef int _format19_long_branch(self, uint16_t instruction):
        """BL (dos instrucciones)"""
        cdef bint h_bit = (instruction & (1 << 11)) != 0
        cdef int32_t offset = instruction & 0x7FF
        cdef uint32_t pc_at_execution, next_instr, target
        
        if not h_bit:
            # Sign extend
            if offset & 0x400:
                offset |= <int32_t>0xFFFFF800
            
            pc_at_execution = self.cpu._current_pc + 4
            self.reg.lr = (pc_at_execution + (offset << 12)) & 0xFFFFFFFF
            return 1
        else:
            next_instr = (self.cpu._current_pc + 2) & 0xFFFFFFFF
            target = (self.reg.lr + (offset << 1)) & 0xFFFFFFFF
            
            self.reg.lr = next_instr | 1
            self.reg.pc = target
            self.cpu.flush_pipeline()
            
            return 3