import random
import io
import time

import math

import board
import displayio
import framebufferio
import rgbmatrix

from PIL import Image
import requests

import adafruit_display_text.label
import terminalio

displayio.release_displays()


def fetch_url(day = None):
    url = 'https://xkcd.com'
    if day is not None:
        url = f"https://xkcd.com/{day}/"
    r = requests.get(url)
    if r.status_code == 200:
        lines = str(r.content).split("\\n")
        for line in lines:
            if "og:image" in line:
                #print(line)
                url_begin = line.find('https://')
                if (url_begin < 0):
                    return None
                sub_str = line[url_begin:]
                end = sub_str.find('"')
                if (end < 0):
                    return None
                img_url = sub_str[:end]
                return img_url
                
    return None

def get_xkcd(url):
    r = requests.get(url)
    stream = io.BytesIO(r.content)
    img = Image.open(stream)
    ox, oy = img.size
    scale = max(ox / 64, oy / 32)
    nx, ny = math.floor(ox / scale), math.floor(oy / scale)
    img.thumbnail((nx, ny))
    return img.convert('RGB')

def get_bmp(img):
    raw = io.BytesIO()
    img.save(raw, "BMP")
    bmp = displayio.OnDiskBitmap(raw)
    return bmp

# bit_depth=1 is used here because we only use primary colors, and it makes
# the animation run a bit faster because RGBMatrix isn't taking over the CPU
# as often.
matrix = rgbmatrix.RGBMatrix(
    width=64, height=32, bit_depth=8,
    rgb_pins=[board.D6, board.D5, board.D9, board.D11, board.D10, board.D12],
    addr_pins=[board.A5, board.A4, board.A3, board.A2],
    clock_pin=board.D13, latch_pin=board.D0, output_enable_pin=board.D1)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)

# Put each line of text into a Group, then show that group.

cur_url = fetch_url(3041)
if cur_url is None:
    raise RuntimeError("Unable to fetch initial image")

xkcd = get_xkcd(cur_url)
b = get_bmp(xkcd)

tile = displayio.TileGrid(b, pixel_shader = b.pixel_shader)

g = displayio.Group()
g.append(tile)

display.root_group = g

print(cur_url)
while True:
    display.refresh(minimum_frames_per_second=0)


