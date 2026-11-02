"""Image files beside the workspace database.

Outputs are checked before they count: a reply that is not a PNG, JPEG or WebP image is an
invalid output, not a completed job. The interface frames each image to the feed's shape, so the
stored file is the backend's own output and nothing is re-encoded.
"""
import struct
from pathlib import Path

from dungeon.images.adapters.base import AdapterError

TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'webp': 'image/webp'}
SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def directory(database) -> Path:
    path = database.path.parent / 'images'
    path.mkdir(parents=True, exist_ok=True)
    return path


def raw_directory(database) -> Path:
    path = directory(database) / 'raw'
    path.mkdir(parents=True, exist_ok=True)
    return path


def jpeg_size(data: bytes) -> tuple[int, int]:
    index = 2
    while index + 9 <= len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in SOF:
            height, width = struct.unpack('>HH', data[index + 5:index + 9])
            return width, height
        index += 2 + struct.unpack('>H', data[index + 2:index + 4])[0]
    raise ValueError('no frame header')


def webp_size(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b'VP8X':
        return 1 + int.from_bytes(data[24:27], 'little'), 1 + int.from_bytes(data[27:30], 'little')
    if chunk == b'VP8L':
        bits = int.from_bytes(data[21:25], 'little')
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b'VP8 ':
        width, height = struct.unpack('<HH', data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    raise ValueError('unknown WebP chunk')


def sniff(data: bytes) -> tuple[str, int, int]:
    """File type and dimensions from the header alone."""
    try:
        if data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR':
            width, height = struct.unpack('>II', data[16:24])
            return 'png', width, height
        if data[:3] == b'\xff\xd8\xff':
            return ('jpg', *jpeg_size(data))
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return ('webp', *webp_size(data))
    except (ValueError, struct.error, IndexError):
        pass
    raise AdapterError('invalid_output', 'The backend returned something that is not a PNG, JPEG or WebP image.')


def store(database, job_id, data: bytes) -> dict:
    kind, width, height = sniff(data)
    if not (0 < width <= 8192 and 0 < height <= 8192):
        raise AdapterError('invalid_output', 'The backend returned an image with unusable dimensions.')
    name = f'{job_id}.{kind}'
    target = directory(database) / name
    partial = target.with_suffix('.partial')
    partial.write_bytes(data)
    partial.replace(target)
    return {'file': name, 'width': width, 'height': height}


def path_of(database, name: str) -> Path:
    base = directory(database).resolve()
    path = (base / name).resolve()
    if path.parent != base or not path.is_file():
        raise FileNotFoundError(name)
    return path
