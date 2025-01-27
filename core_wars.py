import time
import random
import displayio

from blinka_displayio_pygamedisplay import PyGameDisplay
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label

import pygame
pygame.init()

font = bitmap_font.load_font("assets/5x7.bdf")

SCALE = 12
display = PyGameDisplay(width=64 * SCALE, height=32 * SCALE)

root = displayio.Group(scale = SCALE)

ALLOC_X = 64
ALLOC_Y = 25

CORE_SIZE = ALLOC_X * ALLOC_Y

A_ACTIVE = 0xb36b30
A_INACTIVE = 0xab7549

B_ACTIVE = 0x2e6ab3
B_INACTIVE = 0x4d6c91


consoleA = label.Label(font, text = ">", color = A_ACTIVE)
consoleA.x = 5
consoleA.y = 32 - 7

consoleB = label.Label(font, text = ">", color = B_INACTIVE)
consoleB.x = 35
consoleB.y = 32 - 7

core_display = displayio.Bitmap(width = 64, height = 25, value_count = 8)

#following the corewar suggestions
# number of bits:   4      2     2  12  12
# fields:          type   mA    mB   A   B


root.append(consoleA)
root.append(consoleB)

display.show(root)
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
        self.ip = (self.ip + value) % core_size

    def get_incr(self, value):
        return (self.ip + value) % core_size


class Core:
    GET_A = True
    GET_B = False

    def __init__(self, grid_x, grid_y):
        self.x = grid_x
        self.y = grid_y
        self.length = grid_x * grid_y
        self.memory = [0 for _ in range(self.length)]

        self.ip_a = IP(self.length)
        self.ip_b = IP(self.length)
        self.cur = ip_a
        self.run_a = True

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
            return (next_addr + val) % self.length
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
            second_addr = (next_addr + val) % self.length
            return self.memory[second_addr]
        else:
            return None

    def update(self):
        if self.run_a:
            self.cur = self.ip_a
        else:
            self.cur = self.ip_b

        self.instruction = Instruction(self.memory[self.cur.ip])

        self.a = self.field_value(GET_A)
        self.b = self.field_value(GET_B)

        self.aa = self.field_address(GET_A)
        self.ab = self.field_address(GET_B)


        #TODO: Write win/lose logic
        if self.violated:
            pass

        # advance to next instruction, then allow other process to execute
        if self.jumping:
            self.jumping = False
        else:
            self.cur.incr(1)

        # next turn
        self.run_a = not self.run_a

    def mov(self):
        v = self.a
        addr = self.ab
        if None in [v, addr]:
            self.violated = True
            return
        self.memory[addr] = v

    def add(self):
        x1, x2, addr = self.a, self.b, self.ab
        if (None in [x1, x2, addr]):
            self.violated = True
            return
        sum = x1 + x2
        self.memory[addr] = sum

    def sub(self):
        x1, x2, addr = self.a, self.b, self.ab
        if (None in [x1, x2, addr]):
            self.violated = True
            return
        diff = x2 - x1
        if (diff < 0):
            diff += (1 << 12)
            
        self.memory[addr] = diff

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
        a -= 1
        if (a < 0):
            a += (1 << 12)
        self.memory[l_a] = a

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

while True:
    time.sleep(0.01)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()




