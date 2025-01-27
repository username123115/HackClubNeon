import time
import random
import displayio

from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label

# Switch between using pygame wrapper and RGBMatrix
USE_PYGAME = False

if USE_PYGAME:
    from blinka_displayio_pygamedisplay import PyGameDisplay
    import pygame
    pygame.init()

    SCALE = 12
    display = PyGameDisplay(width=64 * SCALE, height=32 * SCALE)
    root = displayio.Group(scale = SCALE)
    display.show(root)

    font = bitmap_font.load_font("assets/5x7.bdf")

else:
    import board
    import framebufferio
    import rgbmatrix
    matrix = rgbmatrix.RGBMatrix(
    width=64, height=32, bit_depth=8,
    rgb_pins=[board.D6, board.D5, board.D9, board.D11, board.D10, board.D12],
    addr_pins=[board.A5, board.A4, board.A3, board.A2],
    clock_pin=board.D13, latch_pin=board.D0, output_enable_pin=board.D1)
    display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)
    display.auto_refresh = True

    font = bitmap_font.load_font("5x7.bdf")

    root = displayio.Group()
    display.root_group = root



A_ACTIVE = 0xb36b30
A_INACTIVE = 0xab7549

B_ACTIVE = 0x2e6ab3
B_INACTIVE = 0x4d6c91

COLOR_A = 1
COLOR_B = 2

INSTRUCTION_COLOR_OFFSET = 2

INITIALIZED_DATA_COLOR_OFFSET = INSTRUCTION_COLOR_OFFSET + 8
# grids can alternate colors everytime they've been written
INITIALIZED_DATA_COLOR_COUNT = 2

CORE_HEIGHT = 16
CORE_WIDTH = 64
LIMIT = 1 << 12


consoleA = label.Label(font, text = ">", color = A_ACTIVE)
consoleA.x = 5
consoleA.y = 32 - 12

consoleB = label.Label(font, text = ">", color = B_INACTIVE)
consoleB.x = 5
consoleB.y = 32 - 5


colors = 0x50CE99, 0x4BD2C7, 0xFF531F, 0xFB2335, 0xF6287E, 0xF22CC0, 0xDD31ED, 0x9E35E9, 0x643AE4, 0x3E4BE0, 0x4382DB, 0x47B3D7
core_palette = displayio.Palette(len(colors))
for i, color in enumerate(colors):
    core_palette[i] = color

background_palette = displayio.Palette(1)
background_palette[0] = 0x202025

status_palette = displayio.Palette(3)
status_palette.make_transparent(0)
status_palette[1] = 0x4BD2C7
status_palette[2] = 0xFF531F


core_bitmap = displayio.Bitmap(width = CORE_WIDTH, height = CORE_HEIGHT, value_count = len(colors))
status_bitmap = displayio.Bitmap(width = CORE_WIDTH, height = CORE_HEIGHT, value_count = 3)
background = displayio.Bitmap(width = 64, height = 32 - core_bitmap.height, value_count = 1)

core_tile = displayio.TileGrid(core_bitmap, pixel_shader = core_palette)
background_tile = displayio.TileGrid(background, pixel_shader = background_palette, y = core_bitmap.height)
status_tile = displayio.TileGrid(status_bitmap, pixel_shader = status_palette)

#following the corewar suggestions
# number of bits:   4      2     2  12  12
# fields:          type   mA    mB   A   B


root.append(core_tile)
root.append(background_tile)
root.append(status_tile)
root.append(consoleA)
root.append(consoleB)


class Instruction:
    def __init__(self, memory):
        self.opcode = (memory >> 28) & 0xf
        self.mode_a = (memory >> 26) & 0x3
        self.mode_b = (memory >> 24) & 0x3
        self.a = (memory >> 12) & 0xFFF
        self.b = memory & 0xFFF

    def valid(self):
        return (self.opcode <= 7) and (self.mode_a < 3) and (self.mode_b < 3)

    def get_mode(self, get_a = True):
        if get_a:
            return self.mode_a
        else:
            return self.mode_b
    def get_field(self, get_a = True):
        if get_a:
            return self.a
        else:
            return self.b


class IP:
    def __init__(self, core_size, initial = 0):
        self.ip = initial
        self.size = core_size

    def incr(self, value):
        self.ip = ((self.ip + value) % LIMIT) % self.size

    def get_incr(self, value):
        return ((self.ip + value) % LIMIT) % self.size


class Core:
    GET_A = True
    GET_B = False

    def __init__(self, bitmap, status, text_a, text_b):
        self.bitmap = bitmap
        self.status = status
        self.x = bitmap.width
        self.y = bitmap.height

        self.length = self.x * self.y
        self.memory = [0 for _ in range(self.length)]

        self.text_a = text_a
        self.text_b = text_b

        self.ip_a = IP(self.length)
        self.ip_b = IP(self.length)
        self.cur = self.ip_a
        self.run_a = True

        self.xip_a = None
        self.xip_b = None


        self.ended = False

        self.instruction = None
        self.jumping = False

        # Executed a bad instruction?
        self.violated = False

        self.instructions = {
            1: self.mov,
            2: self.add,
            3: self.sub,
            4: self.jmp,
            5: self.jmz,
            6: self.djz,
            7: self.cmp
        }

    # Gets address specified by relative or indirect 
    def field_address(self, get_a = GET_A):
        mode = self.instruction.get_mode(get_a)
        field = self.instruction.get_field(get_a)

        if (mode == 1):
            return self.cur.get_incr(field)
        elif (mode == 2):
            next_addr = self.cur.get_incr(field)
            val = self.memory[next_addr]
            return ((next_addr + val) % LIMIT) % self.length
        else:
            return None

    # Gets content specified by immediate, relative, or indirect
    def field_value(self, get_a = GET_A):
        mode = self.instruction.get_mode(get_a)
        field = self.instruction.get_field(get_a)

        if (mode == 0):
            return field
        elif (mode == 1):
            return self.memory[self.cur.get_incr(field)]
        elif (mode == 2):
            next_addr = self.cur.get_incr(field)
            val = self.memory[next_addr]
            second_addr = ((next_addr + val) % LIMIT) % self.length
            return self.memory[second_addr]
        else:
            return None

    #disassemble current instruction, doesn't check for valid types
    def dissasemble(self):
        mnemonics = ["DAT", "MOV", "ADD", "SUB", "JMP", "JMZ", "DJZ", "CMP"]
        op = self.instruction.opcode
        if op < len(mnemonics):
            mnemonic = mnemonics[op]
        else:
            mnemonic = "???"
        modes = "# @?"
        fa = self.instruction.a
        fb = self.instruction.b
        #dumb heuristic for detecting negative integers
        if (fa - LIMIT) > -128:
            fa = fa - LIMIT
        if (fb - LIMIT) > -128:
            fb = fb - LIMIT

        a = modes[self.instruction.mode_a] + str(fa)
        b = modes[self.instruction.mode_b] + str(fb)
        r = f"{mnemonic} {a} {b}"
        return r

    def load_players(self, pa, pb):
        off_a = pa[0]
        ins_a = pa[1:]
        off_b = pb[0]
        ins_b =  pb[1:]

        if (len(ins_a) + len(ins_b)) >= self.length:
            raise ValueError("Programs loaded exceed maximum core memory")

        load_a = random.randrange(self.length)
        self.ip_a.ip = (load_a + off_a) % self.length
        self.load_memory(load_a, ins_a)

        remaining = (self.length - len(ins_a)) - len(ins_b)
        load_b = (load_a + len(ins_a) + random.randrange(remaining)) % self.length
        self.ip_b.ip = (load_b + off_b) % self.length
        self.load_memory(load_b, ins_b)

    def load_memory(self, base, instructions):
        for i, raw in enumerate(instructions):
            addr = (base + i) % self.length
            ins = Instruction(raw)
            if (ins.opcode not in self.instructions) and (ins.opcode):
                raise ValueError(f"Loaded bad instruction {ins.opcode}")

            self.memory[addr] = raw
            self.bitmap[addr] = ins.opcode + INSTRUCTION_COLOR_OFFSET

    # data is set, update the bitmap
    def set_map(self, addr):
        value = self.bitmap[addr]
        if value < INITIALIZED_DATA_COLOR_OFFSET:
            self.bitmap[addr] = INITIALIZED_DATA_COLOR_OFFSET
        else:
            off = value - INITIALIZED_DATA_COLOR_OFFSET
            new_off = (off + 1) % INITIALIZED_DATA_COLOR_COUNT
            self.bitmap[addr] = INITIALIZED_DATA_COLOR_OFFSET + new_off



    def update(self):
        if self.ended:
            if self.run_a:
                winner = self.text_a
            else:
                winner = self.text_b
            # goofy color rotate
            color = winner.color
            lsb = color & 1
            new = (lsb << 23) | (color >> 1)
            winner.color = new


            return

        if self.run_a:
            self.cur = self.ip_a
            if self.xip_a:
                self.status[self.xip_a] = 0
            self.xip_a = self.cur.ip
            self.status[self.xip_a] = 1
        else:
            self.cur = self.ip_b
            if self.xip_b:
                self.status[self.xip_b] = 0
            self.xip_b = self.cur.ip
            self.status[self.xip_b] = 2

        self.instruction = Instruction(self.memory[self.cur.ip])

        self.a = self.field_value(self.GET_A)
        self.b = self.field_value(self.GET_B)

        self.aa = self.field_address(self.GET_A)
        self.ab = self.field_address(self.GET_B)

        if self.instruction.opcode in self.instructions:
            text = self.dissasemble()
            if self.run_a:
                self.text_a.text = text
                self.text_a.color = A_ACTIVE
                self.text_b.color = B_INACTIVE
            else:
                self.text_b.text = text
                self.text_a.color = A_INACTIVE
                self.text_b.color = B_ACTIVE


            self.instructions[self.instruction.opcode]()

        else:
            self.violated = True


        #TODO: Write win/lose logic
        if self.violated:
            self.ended = True
            if self.run_a:
                self.text_a.color = A_INACTIVE
                self.text_b.color = B_ACTIVE
                self.text_b.text = "WIN"
            else:
                self.text_a.color = A_ACTIVE
                self.text_b.color = B_INACTIVE
                self.text_a.text = "WIN"

        # advance to next instruction, then allow other process to execute
        if self.jumping:
            self.jumping = False
        else:
            self.cur.incr(1)

        # next turn
        self.run_a = not self.run_a

        return True

    def mov(self):
        v = self.a
        addr = self.ab
        if None in [v, addr]:
            self.violated = True
            return
        self.memory[addr] = v
        self.set_map(addr)

    def add(self):
        x1, x2, addr = self.a, self.b, self.ab
        if (None in [x1, x2, addr]):
            self.violated = True
            return
        sum = (x1 + x2) % LIMIT
        self.memory[addr] = sum
        self.set_map(addr)

    def sub(self):
        x1, x2, addr = self.a, self.b, self.ab
        if (None in [x1, x2, addr]):
            self.violated = True
            return

        complement = LIMIT - x1
        diff = (x2 + complement) % LIMIT
            
        self.memory[addr] = diff
        self.set_map(addr)

    def jmp(self):
        addr = self.ab
        if addr is None:
            self.violated = True
            return
        self.jumping = True
        self.cur.ip = addr

    def jmz(self):
        a, addr = self.a, self.ab
        if (None in [a, addr]):
            self.violated = True
            return
        if (a == 0):
            self.jumping = True
            self.cur.ip = addr

    def djz(self):
        l_a, addr = self.aa, self.ab
        if (None in [l_a, addr]):
            self.violated = True
            return

        a = self.memory[l_a]

        # decrement a
        negative = LIMIT - 1
        a += negative
        a %= LIMIT

        self.memory[l_a] = a
        self.set_map(l_a)

        if (a == 0):
            self.jumping = True
            self.cur.ip = addr

    def cmp(self):
        a, b = self.a, self.b
        if (None in [a, b]):
            self.violated = True
            return
        if (a != b):
            self.jumping = True
            # skip next instruction
            self.cur.incr(2)
dwarf = [0x1, 0x1000000, 0x21004fff, 0x12000ffe, 0x41000ffe]


core = Core(core_bitmap, status_bitmap, consoleA, consoleB)
core.load_players(dwarf, dwarf)

end = time.monotonic()
accum = 0

while True:
    begin = time.monotonic()
    dt = begin - end
    accum += dt

    if (accum >= 0.05):
        accum = 0
        core.update()


    if USE_PYGAME:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
    end = time.monotonic()
    time.sleep(0.01)
