"""
Instrucciones THUMB (16-bit) para el ARM7TDMI
Implementa el set completo de instrucciones THUMB
"""
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .arm7tdmi import ARM7TDMI


class ThumbInstructions:
    """
    Decodificador y ejecutor de instrucciones THUMB
    
    Las instrucciones THUMB son versiones comprimidas de 16-bit
    de las instrucciones ARM de 32-bit.
    """
    
    def __init__(self, cpu: 'ARM7TDMI'):
        self.cpu = cpu
        self.reg = cpu.registers
        self.mem = cpu.memory
    
    # ===== Utilidades =====
    
    def _alu_add(self, a: int, b: int, carry_in: bool = False) -> Tuple[int, bool, bool]:
        """Suma con flags"""
        a &= 0xFFFFFFFF
        b &= 0xFFFFFFFF
        result = a + b + int(carry_in)
        
        carry = result > 0xFFFFFFFF
        result &= 0xFFFFFFFF
        
        overflow = bool(((a ^ result) & (b ^ result)) >> 31)
        
        return result, carry, overflow
    
    def _alu_sub(self, a: int, b: int, carry_in: bool = True) -> Tuple[int, bool, bool]:
        """Resta con flags"""
        a &= 0xFFFFFFFF
        b &= 0xFFFFFFFF
        result = a - b - (0 if carry_in else 1)
        
        carry = (a >= b) if carry_in else (a > b)
        result &= 0xFFFFFFFF
        
        overflow = bool(((a ^ b) & (a ^ result)) >> 31)
        
        return result, carry, overflow
    
    def _set_nz(self, value: int) -> None:
        """Establece flags N y Z"""
        self.reg.flag_n = bool(value & 0x80000000)
        self.reg.flag_z = (value == 0)
    
    def _set_nzc(self, value: int, carry: bool) -> None:
        """Establece flags N, Z y C"""
        self._set_nz(value)
        self.reg.flag_c = carry
    
    def _set_nzcv(self, value: int, carry: bool, overflow: bool) -> None:
        """Establece todos los flags"""
        self._set_nz(value)
        self.reg.flag_c = carry
        self.reg.flag_v = overflow
    
    # ===== Decodificación Principal =====
    
    def execute(self, instruction: int) -> int:
        """
        Ejecuta una instrucción THUMB
        
        Returns:
            Ciclos consumidos
        """
        # Decodificar según los bits superiores
        
        # Format 1: Move shifted register (000xx)
        if (instruction >> 13) == 0b000:
            op = (instruction >> 11) & 0x3
            if op != 0b11:  # No es Format 2
                return self._format1_shift(instruction)
            else:
                return self._format2_add_sub(instruction)
        
        # Format 3: Move/Compare/Add/Sub immediate (001xx)
        if (instruction >> 13) == 0b001:
            return self._format3_immediate(instruction)
        
        # Format 4: ALU operations (010000)
        if (instruction >> 10) == 0b010000:
            return self._format4_alu(instruction)
        
        # Format 5: Hi register / BX (010001)
        if (instruction >> 10) == 0b010001:
            return self._format5_hireg_bx(instruction)
        
        # Format 6: PC-relative load (01001)
        if (instruction >> 11) == 0b01001:
            return self._format6_pc_load(instruction)
        
        # Format 7: Load/Store register offset (0101xx0)
        if (instruction >> 12) == 0b0101 and not (instruction & (1 << 9)):
            return self._format7_load_store_reg(instruction)
        
        # Format 8: Load/Store sign-extended (0101xx1)
        if (instruction >> 12) == 0b0101 and (instruction & (1 << 9)):
            return self._format8_load_store_signed(instruction)
        
        # Format 9: Load/Store immediate offset (011xx)
        if (instruction >> 13) == 0b011:
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
        
        # Format 16: Conditional branch (1101xxxx) excepto 1101111x
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
        
        # Instrucción no reconocida
        return 1
    
    # ===== Format 1: Move Shifted Register =====
    
    def _format1_shift(self, instruction: int) -> int:
        """LSL, LSR, ASR con offset inmediato"""
        op = (instruction >> 11) & 0x3
        offset = (instruction >> 6) & 0x1F
        rs = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        rs_value = self.reg.get(rs)
        carry = self.reg.flag_c
        
        if op == 0b00:  # LSL
            if offset == 0:
                result = rs_value
            else:
                carry = bool((rs_value >> (32 - offset)) & 1)
                result = (rs_value << offset) & 0xFFFFFFFF
                
        elif op == 0b01:  # LSR
            if offset == 0:
                offset = 32
            if offset == 32:
                carry = bool(rs_value >> 31)
                result = 0
            else:
                carry = bool((rs_value >> (offset - 1)) & 1)
                result = rs_value >> offset
                
        else:  # ASR (op == 0b10)
            if offset == 0:
                offset = 32
            if offset >= 32:
                carry = bool(rs_value >> 31)
                result = 0xFFFFFFFF if carry else 0
            else:
                carry = bool((rs_value >> (offset - 1)) & 1)
                result = rs_value >> offset
                if rs_value & 0x80000000:
                    result |= (0xFFFFFFFF << (32 - offset)) & 0xFFFFFFFF
        
        self.reg.set(rd, result)
        self._set_nzc(result, carry)
        
        return 1
    
    # ===== Format 2: Add/Subtract =====
    
    def _format2_add_sub(self, instruction: int) -> int:
        """ADD/SUB con registro o inmediato de 3 bits"""
        imm_flag = bool(instruction & (1 << 10))
        sub_flag = bool(instruction & (1 << 9))
        rn_or_imm = (instruction >> 6) & 0x7
        rs = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        rs_value = self.reg.get(rs)
        operand = rn_or_imm if imm_flag else self.reg.get(rn_or_imm)
        
        if sub_flag:
            result, carry, overflow = self._alu_sub(rs_value, operand)
        else:
            result, carry, overflow = self._alu_add(rs_value, operand)
        
        self.reg.set(rd, result)
        self._set_nzcv(result, carry, overflow)
        
        return 1
    
    # ===== Format 3: Move/Compare/Add/Sub Immediate =====
    
    def _format3_immediate(self, instruction: int) -> int:
        """MOV, CMP, ADD, SUB con inmediato de 8 bits"""
        op = (instruction >> 11) & 0x3
        rd = (instruction >> 8) & 0x7
        imm = instruction & 0xFF
        
        rd_value = self.reg.get(rd)
        
        if op == 0b00:  # MOV
            result = imm
            self.reg.set(rd, result)
            self._set_nz(result)
            
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
    
    # ===== Format 4: ALU Operations =====
    
    def _format4_alu(self, instruction: int) -> int:
        """Operaciones ALU entre registros bajos"""
        op = (instruction >> 6) & 0xF
        rs = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        rd_value = self.reg.get(rd)
        rs_value = self.reg.get(rs)
        
        carry = self.reg.flag_c
        overflow = self.reg.flag_v
        cycles = 1
        
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
                carry = bool((rd_value >> (32 - shift)) & 1)
                result = (rd_value << shift) & 0xFFFFFFFF
            elif shift == 32:
                carry = bool(rd_value & 1)
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
                carry = bool((rd_value >> (shift - 1)) & 1)
                result = rd_value >> shift
            elif shift == 32:
                carry = bool(rd_value >> 31)
                result = 0
            else:
                carry = False
                result = 0
            self._set_nzc(result, carry)
            self.reg.set(rd, result)
            cycles = 2
            
        elif op == 0x4:  # ASR
            shift = rs_value & 0xFF
            sign = rd_value >> 31
            if shift == 0:
                result = rd_value
            elif shift < 32:
                carry = bool((rd_value >> (shift - 1)) & 1)
                result = rd_value >> shift
                if sign:
                    result |= (0xFFFFFFFF << (32 - shift)) & 0xFFFFFFFF
            else:
                carry = bool(sign)
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
                    carry = bool(rd_value >> 31)
                    result = rd_value
                else:
                    carry = bool((rd_value >> (shift - 1)) & 1)
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
            # C flag is destroyed (unpredictable)
            self.reg.set(rd, result)
            cycles = 2  # Variable en realidad
            
        elif op == 0xE:  # BIC
            result = rd_value & ~rs_value
            self._set_nz(result)
            self.reg.set(rd, result)
            
        else:  # MVN (0xF)
            result = ~rs_value & 0xFFFFFFFF
            self._set_nz(result)
            self.reg.set(rd, result)
        
        return cycles
    
    # ===== Format 5: Hi Register / BX =====
    
    def _format5_hireg_bx(self, instruction: int) -> int:
        """ADD, CMP, MOV con registros altos, BX"""
        op = (instruction >> 8) & 0x3
        h1 = bool(instruction & (1 << 7))
        h2 = bool(instruction & (1 << 6))
        rs = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        # Añadir 8 si es registro alto
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
            self.reg.thumb_mode = bool(rs_value & 1)
            
            if self.reg.thumb_mode:
                self.reg.pc = rs_value & ~1
            else:
                self.reg.pc = rs_value & ~3
            
            self.cpu.flush_pipeline()
            return 3
        
        return 1
    
    # ===== Format 6: PC-relative Load =====
    
    def _format6_pc_load(self, instruction: int) -> int:
        """LDR Rd, [PC, #imm]"""
        rd = (instruction >> 8) & 0x7
        imm = (instruction & 0xFF) << 2
        
        # PC está alineado a word y apunta 4 bytes adelante
        pc = (self.reg.pc & ~3)
        address = pc + imm
        
        value = self.mem.read_32(address)
        self.reg.set(rd, value)
        
        return 3
    
    # ===== Format 7: Load/Store Register Offset =====
    
    def _format7_load_store_reg(self, instruction: int) -> int:
        """LDR, STR, LDRB, STRB con offset de registro"""
        load = bool(instruction & (1 << 11))
        byte_transfer = bool(instruction & (1 << 10))
        ro = (instruction >> 6) & 0x7
        rb = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        address = (self.reg.get(rb) + self.reg.get(ro)) & 0xFFFFFFFF
        
        if load:
            if byte_transfer:
                value = self.mem.read_8(address)
            else:
                value = self.mem.read_32(address)
                # Rotación para accesos no alineados
                misalign = address & 3
                if misalign:
                    value = ((value >> (misalign * 8)) | 
                            (value << (32 - misalign * 8))) & 0xFFFFFFFF
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd)
            if byte_transfer:
                self.mem.write_8(address, value & 0xFF)
            else:
                self.mem.write_32(address, value)
            return 2
    
    # ===== Format 8: Load/Store Sign-Extended =====
    
    def _format8_load_store_signed(self, instruction: int) -> int:
        """STRH, LDSB, LDRH, LDSH"""
        h_flag = bool(instruction & (1 << 11))
        s_flag = bool(instruction & (1 << 10))
        ro = (instruction >> 6) & 0x7
        rb = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        address = (self.reg.get(rb) + self.reg.get(ro)) & 0xFFFFFFFF
        
        if not s_flag and not h_flag:  # STRH
            value = self.reg.get(rd) & 0xFFFF
            self.mem.write_16(address, value)
            return 2
            
        elif not s_flag and h_flag:  # LDRH
            value = self.mem.read_16(address)
            self.reg.set(rd, value)
            return 3
            
        elif s_flag and not h_flag:  # LDSB (Load Sign-extended Byte)
            value = self.mem.read_8(address)
            if value & 0x80:
                value |= 0xFFFFFF00
            self.reg.set(rd, value)
            return 3
            
        else:  # LDSH (Load Sign-extended Halfword)
            value = self.mem.read_16(address)
            if value & 0x8000:
                value |= 0xFFFF0000
            self.reg.set(rd, value)
            return 3
    
    # ===== Format 9: Load/Store Immediate Offset =====
    
    def _format9_load_store_imm(self, instruction: int) -> int:
        """LDR, STR, LDRB, STRB con offset inmediato"""
        byte_transfer = bool(instruction & (1 << 12))
        load = bool(instruction & (1 << 11))
        offset = (instruction >> 6) & 0x1F
        rb = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        if not byte_transfer:
            offset <<= 2  # Word offset
        
        address = (self.reg.get(rb) + offset) & 0xFFFFFFFF
        
        if load:
            if byte_transfer:
                value = self.mem.read_8(address)
            else:
                value = self.mem.read_32(address)
                misalign = address & 3
                if misalign:
                    value = ((value >> (misalign * 8)) | 
                            (value << (32 - misalign * 8))) & 0xFFFFFFFF
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd)
            if byte_transfer:
                self.mem.write_8(address, value & 0xFF)
            else:
                self.mem.write_32(address, value)
            return 2
    
    # ===== Format 10: Load/Store Halfword =====
    
    def _format10_load_store_half(self, instruction: int) -> int:
        """LDRH, STRH con offset inmediato"""
        load = bool(instruction & (1 << 11))
        offset = ((instruction >> 6) & 0x1F) << 1  # Halfword offset
        rb = (instruction >> 3) & 0x7
        rd = instruction & 0x7
        
        address = (self.reg.get(rb) + offset) & 0xFFFFFFFF
        
        if load:
            value = self.mem.read_16(address)
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd) & 0xFFFF
            self.mem.write_16(address, value)
            return 2
    
    # ===== Format 11: SP-Relative Load/Store =====
    
    def _format11_sp_relative(self, instruction: int) -> int:
        """LDR, STR relativo a SP"""
        load = bool(instruction & (1 << 11))
        rd = (instruction >> 8) & 0x7
        offset = (instruction & 0xFF) << 2
        
        address = (self.reg.sp + offset) & 0xFFFFFFFF
        
        if load:
            value = self.mem.read_32(address)
            self.reg.set(rd, value)
            return 3
        else:
            value = self.reg.get(rd)
            self.mem.write_32(address, value)
            return 2
    
    # ===== Format 12: Load Address =====
    
    def _format12_load_address(self, instruction: int) -> int:
        """ADD Rd, PC/SP, #imm"""
        sp_flag = bool(instruction & (1 << 11))
        rd = (instruction >> 8) & 0x7
        offset = (instruction & 0xFF) << 2
        
        if sp_flag:
            base = self.reg.sp
        else:
            base = self.reg.pc & ~3  # PC alineado
        
        result = (base + offset) & 0xFFFFFFFF
        self.reg.set(rd, result)
        
        return 1
    
    # ===== Format 13: Add Offset to SP =====
    
    def _format13_sp_offset(self, instruction: int) -> int:
        """ADD SP, #imm o SUB SP, #imm"""
        negative = bool(instruction & (1 << 7))
        offset = (instruction & 0x7F) << 2
        
        if negative:
            result = (self.reg.sp - offset) & 0xFFFFFFFF
        else:
            result = (self.reg.sp + offset) & 0xFFFFFFFF
        
        self.reg.sp = result
        
        return 1
    
    # ===== Format 14: Push/Pop =====
    
    def _format14_push_pop(self, instruction: int) -> int:
        """PUSH y POP"""
        load = bool(instruction & (1 << 11))
        pc_lr = bool(instruction & (1 << 8))
        rlist = instruction & 0xFF
        
        # Contar registros
        count = bin(rlist).count('1') + int(pc_lr)
        
        cycles = 2
        
        if load:  # POP
            address = self.reg.sp
            
            for i in range(8):
                if rlist & (1 << i):
                    value = self.mem.read_32(address)
                    self.reg.set(i, value)
                    address += 4
                    cycles += 1
            
            if pc_lr:  # Pop PC
                value = self.mem.read_32(address)
                # En THUMB, bit 0 se usa para cambio de modo
                self.reg.thumb_mode = bool(value & 1)
                self.reg.pc = value & ~1
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
            
            if pc_lr:  # Push LR
                self.mem.write_32(address, self.reg.lr)
                cycles += 1
        
        return cycles
    
    # ===== Format 15: Multiple Load/Store =====
    
    def _format15_multiple(self, instruction: int) -> int:
        """LDMIA, STMIA"""
        load = bool(instruction & (1 << 11))
        rb = (instruction >> 8) & 0x7
        rlist = instruction & 0xFF
        
        address = self.reg.get(rb)
        cycles = 2
        
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
        
        # Writeback siempre ocurre (excepto si Rb está en la lista en LDMIA)
        if not (load and (rlist & (1 << rb))):
            self.reg.set(rb, address)
        
        return cycles
    
    # ===== Format 16: Conditional Branch =====

    def _format16_cond_branch(self, instruction: int) -> int:
        """B{cond} label"""
        cond = (instruction >> 8) & 0xF
        offset = instruction & 0xFF
        
        # Sign extend offset de 8 bits
        if offset & 0x80:
            offset |= 0xFFFFFF00
        
        # Convertir a signed
        if offset >= 0x80000000:
            offset = offset - 0x100000000
        
        # Offset en bytes (multiplicar por 2)
        offset = offset << 1
        
        # PC durante ejecución = dirección instrucción + 4
        pc_at_execution = self.cpu._current_pc + 4
        
        if self.reg.check_condition(cond):
            new_pc = (pc_at_execution + offset) & 0xFFFFFFFF
            self.reg.pc = new_pc
            self.cpu.flush_pipeline()
            return 3
        
        return 1
    
    # ===== Format 17: Software Interrupt =====
    
    def _format17_swi(self, instruction: int) -> int:
        """SWI"""
        # comment = instruction & 0xFF  # Número del SWI
        self.cpu.trigger_swi()
        return 3
    
    # ===== Format 18: Unconditional Branch =====

    def _format18_branch(self, instruction: int) -> int:
        """B label (incondicional)"""
        offset = instruction & 0x7FF
        
        # Sign extend offset de 11 bits
        if offset & 0x400:
            offset |= 0xFFFFF800
        
        # Convertir a signed
        if offset >= 0x80000000:
            offset = offset - 0x100000000
        
        # Offset en bytes (multiplicar por 2)
        offset = offset << 1
        
        # PC durante ejecución = dirección instrucción + 4
        pc_at_execution = self.cpu._current_pc + 4
        
        new_pc = (pc_at_execution + offset) & 0xFFFFFFFF
        self.reg.pc = new_pc
        self.cpu.flush_pipeline()
        
        return 3

    # ===== Format 19: Long Branch with Link =====

    def _format19_long_branch(self, instruction: int) -> int:
        """BL (llamada a función, dos instrucciones)"""
        h_bit = bool(instruction & (1 << 11))
        offset = instruction & 0x7FF
        
        if not h_bit:
            # Primera instrucción: LR = PC + 4 + (offset << 12)
            # Sign extend offset de 11 bits
            if offset & 0x400:
                offset |= 0xFFFFF800
            
            # PC durante ejecución = dirección instrucción + 4
            pc_at_execution = self.cpu._current_pc + 4
            
            self.reg.lr = (pc_at_execution + (offset << 12)) & 0xFFFFFFFF
            return 1
            
        else:
            # Segunda instrucción: 
            # temp = next instruction address
            # PC = LR + (offset << 1)
            # LR = temp | 1
            
            next_instr = (self.cpu._current_pc + 2) & 0xFFFFFFFF
            
            target = (self.reg.lr + (offset << 1)) & 0xFFFFFFFF
            
            self.reg.lr = next_instr | 1  # Bit 0 indica THUMB
            self.reg.pc = target
            self.cpu.flush_pipeline()
            
            return 3