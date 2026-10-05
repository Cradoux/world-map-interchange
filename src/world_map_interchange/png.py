"""Minimal PNG structure inspection and deterministic writing.

Structure (signature, chunk order, CRCs, IHDR fields, ancillary chunks) is
checked here without decoding. Pixel decoding uses Pillow, which returns raw
samples and does not apply gamma or ICC colour transforms.
"""

from __future__ import annotations

import io
import struct
import zlib
from dataclasses import dataclass, field

import numpy as np

SIGNATURE = b"\x89PNG\r\n\x1a\n"

COLOUR_TYPES = {
    0: ("greyscale", (1, 2, 4, 8, 16), 1),
    2: ("truecolour", (8, 16), 3),
    3: ("indexed", (1, 2, 4, 8), 1),
    4: ("greyscale+alpha", (8, 16), 2),
    6: ("truecolour+alpha", (8, 16), 4),
}

COLOUR_MANAGEMENT_CHUNKS = ("gAMA", "cHRM", "sRGB", "iCCP", "cICP", "mDCV", "cLLI")
ANIMATION_CHUNKS = ("acTL", "fcTL", "fdAT")


class PngError(ValueError):
    pass


@dataclass
class PngInfo:
    width: int
    height: int
    bit_depth: int
    colour_type: int
    interlace: int
    chunks: list[str] = field(default_factory=list)
    trailing_bytes: int = 0

    @property
    def colour_type_name(self) -> str:
        return COLOUR_TYPES.get(self.colour_type, ("unknown",))[0]

    def has(self, chunk: str) -> bool:
        return chunk in self.chunks

    def describe(self) -> str:
        return f"{self.bit_depth}-bit {self.colour_type_name} (colour type {self.colour_type})"


def inspect_png(data: bytes) -> PngInfo:
    """Parse PNG chunk structure, verifying CRCs and IHDR. Raises PngError."""
    if not data.startswith(SIGNATURE):
        raise PngError("not a PNG file (bad signature)")
    pos = len(SIGNATURE)
    chunks: list[str] = []
    info: PngInfo | None = None
    seen_idat = False
    idat_ended = False
    seen_plte = False
    while True:
        if pos + 8 > len(data):
            raise PngError("truncated PNG: missing IEND chunk")
        length, ctype_raw = struct.unpack(">I4s", data[pos : pos + 8])
        if length > 0x7FFFFFFF:
            raise PngError("chunk length exceeds PNG limit")
        try:
            ctype = ctype_raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise PngError("chunk type is not ASCII") from exc
        if not ctype.isalpha():
            raise PngError(f"invalid chunk type {ctype_raw!r}")
        end = pos + 8 + length + 4
        if end > len(data):
            raise PngError(f"truncated {ctype} chunk")
        body = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : end])
        if zlib.crc32(ctype_raw + body) & 0xFFFFFFFF != crc:
            raise PngError(f"CRC mismatch in {ctype} chunk")

        if not chunks:
            if ctype != "IHDR" or length != 13:
                raise PngError("first chunk must be a 13-byte IHDR")
            w, h, depth, ctype_code, comp, filt, interlace = struct.unpack(">IIBBBBB", body)
            if w == 0 or h == 0 or w > 0x7FFFFFFF or h > 0x7FFFFFFF:
                raise PngError(f"invalid dimensions {w}x{h}")
            if ctype_code not in COLOUR_TYPES:
                raise PngError(f"invalid colour type {ctype_code}")
            if depth not in COLOUR_TYPES[ctype_code][1]:
                raise PngError(f"bit depth {depth} is not allowed for colour type {ctype_code}")
            if comp != 0 or filt != 0:
                raise PngError("unsupported compression or filter method")
            if interlace not in (0, 1):
                raise PngError(f"invalid interlace method {interlace}")
            info = PngInfo(w, h, depth, ctype_code, interlace)
        elif ctype == "IHDR":
            raise PngError("duplicate IHDR chunk")

        if ctype == "IDAT":
            if idat_ended:
                raise PngError("IDAT chunks are not consecutive")
            seen_idat = True
        elif seen_idat:
            idat_ended = True
        if ctype == "PLTE":
            seen_plte = True
        if ctype[0].isupper() and ctype not in ("IHDR", "PLTE", "IDAT", "IEND"):
            raise PngError(f"unknown critical chunk {ctype}")

        chunks.append(ctype)
        pos = end
        if ctype == "IEND":
            break

    assert info is not None
    if not seen_idat:
        raise PngError("PNG has no IDAT chunk")
    if info.colour_type == 3 and not seen_plte:
        raise PngError("indexed-colour PNG has no PLTE chunk")
    info.chunks = chunks
    info.trailing_bytes = len(data) - pos
    return info


def decode_pixels(data: bytes) -> np.ndarray:
    """Decode raw samples with Pillow. Returns uint8/uint16 arrays.

    Greyscale images return (height, width); colour images return
    (height, width, channels). No colour management is applied.
    """
    from PIL import Image

    previous = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None  # dimensions are bounded by our own limits beforehand
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            mode = img.mode
            arr = np.array(img)
    except Exception as exc:  # Pillow raises a variety of exception types
        raise PngError(f"pixel data could not be decoded: {exc}") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous
    if mode in ("I;16", "I;16B", "I;16L", "I"):
        if arr.size and (arr.min() < 0 or arr.max() > 65535):
            raise PngError("decoded 16-bit samples out of range")
        return arr.astype(np.uint16, copy=False)
    if mode in ("L", "1"):
        return arr.astype(np.uint8, copy=False)
    return arr


def write_png(array, bit_depth: int, colour_type: int | None = None, text: dict | None = None) -> bytes:
    """Write a non-interlaced PNG with no colour-management chunks.

    Output is deterministic for a given zlib implementation.
    """
    arr = np.asarray(array)
    if arr.ndim == 2:
        channels = 1
    elif arr.ndim == 3 and arr.shape[2] in (1, 2, 3, 4):
        channels = arr.shape[2]
    else:
        raise ValueError("array must be (h, w) or (h, w, channels)")
    if colour_type is None:
        colour_type = {1: 0, 2: 4, 3: 2, 4: 6}[channels]
    if COLOUR_TYPES[colour_type][2] != channels:
        raise ValueError(f"colour type {colour_type} needs {COLOUR_TYPES[colour_type][2]} channels")
    if bit_depth not in (8, 16):
        raise ValueError("only 8- and 16-bit output is supported")
    maxval = (1 << bit_depth) - 1
    if arr.size and (arr.min() < 0 or arr.max() > maxval):
        raise ValueError(f"samples must lie in 0..{maxval}")
    height, width = arr.shape[:2]
    dtype = ">u2" if bit_depth == 16 else "u1"
    samples = np.ascontiguousarray(arr.astype(dtype)).reshape(height, -1).view(np.uint8)
    rows = np.zeros((height, samples.shape[1] + 1), dtype=np.uint8)
    rows[:, 1:] = samples
    compressed = zlib.compress(rows.tobytes(), 9)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    out = [SIGNATURE, chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, colour_type, 0, 0, 0))]
    for key, value in (text or {}).items():
        out.append(chunk(b"tEXt", key.encode("latin-1") + b"\x00" + value.encode("latin-1")))
    out.append(chunk(b"IDAT", compressed))
    out.append(chunk(b"IEND", b""))
    return b"".join(out)


def insert_chunk(data: bytes, kind: str, body: bytes) -> bytes:
    """Insert an ancillary chunk directly after IHDR (used to build test fixtures)."""
    pos = len(SIGNATURE) + 8 + 13 + 4
    raw = kind.encode("ascii")
    ch = struct.pack(">I", len(body)) + raw + body + struct.pack(">I", zlib.crc32(raw + body) & 0xFFFFFFFF)
    return data[:pos] + ch + data[pos:]
