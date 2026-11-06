"""Draw the project's book icon directly as a small PNG-backed Windows icon."""
from pathlib import Path
import struct
import zlib


def inside(x, y, polygon):
    hit = False
    previous = polygon[-1]
    for point in polygon:
        ax, ay = previous; bx, by = point
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
        previous = point
    return hit


size = 256
rows = bytearray()
for y in range(size):
    rows.append(0)
    for x in range(size):
        cx = min(max(x, 44), 211); cy = min(max(y, 44), 211)
        color = (37, 99, 235, 255) if (x-cx)**2 + (y-cy)**2 <= 34**2 else (0, 0, 0, 0)
        if inside(x, y, [(57, 65), (121, 87), (121, 198), (57, 176)]) or inside(x, y, [(135, 87), (199, 65), (199, 176), (135, 198)]):
            color = (255, 255, 255, 255)
        rows.extend(color)

def chunk(kind, content):
    return struct.pack('!I', len(content)) + kind + content + struct.pack('!I', zlib.crc32(kind + content))

png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(rows), 9)) + chunk(b'IEND', b'')
icon = struct.pack('<3H', 0, 1, 1) + struct.pack('<4B2H2I', 0, 0, 0, 0, 1, 32, len(png), 22) + png
target = Path(__file__).with_name('assets') / 'app.ico'
target.parent.mkdir(exist_ok=True)
target.write_bytes(icon)
