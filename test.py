import random
import io
import time

import math

from PIL import Image
import requests
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
    return img


cur_url = fetch_url()
if cur_url is None:
    raise RuntimeError("Unable to fetch initial image")

img = get_xkcd(cur_url)
#img.show()

x, y = img.size




