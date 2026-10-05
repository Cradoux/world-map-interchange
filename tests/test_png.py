import numpy as np
import pytest

from world_map_interchange import png


def test_write_and_read_16_bit():
    arr = (np.arange(64 * 32, dtype=np.uint32).reshape(32, 64) * 31 % 65536).astype(np.uint16)
    arr[0, 0], arr[0, 1] = 0, 65535
    data = png.write_png(arr, 16)
    info = png.inspect_png(data)
    assert (info.width, info.height, info.bit_depth, info.colour_type, info.interlace) == (64, 32, 16, 0, 0)
    assert not any(info.has(c) for c in png.COLOUR_MANAGEMENT_CHUNKS)
    out = png.decode_pixels(data)
    assert out.dtype == np.uint16
    assert np.array_equal(out, arr)


def test_write_and_read_8_bit_and_rgb():
    mask = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    assert np.array_equal(png.decode_pixels(png.write_png(mask, 8)), mask)
    rgb = np.zeros((2, 3, 3), dtype=np.uint8)
    rgb[..., 1] = 200
    info = png.inspect_png(png.write_png(rgb, 8))
    assert info.colour_type == 2


def test_big_endian_byte_order_is_raw():
    data = png.write_png(np.array([[0x0102]], dtype=np.uint16), 16)
    assert png.decode_pixels(data)[0, 0] == 0x0102


def test_crc_corruption_detected():
    data = bytearray(png.write_png(np.zeros((4, 4), np.uint16), 16))
    data[20] ^= 0xFF
    with pytest.raises(png.PngError, match="CRC|dimensions|bit depth|colour type"):
        png.inspect_png(bytes(data))


def test_not_png():
    with pytest.raises(png.PngError, match="signature"):
        png.inspect_png(b"GIF89a....")


def test_truncated():
    data = png.write_png(np.zeros((4, 4), np.uint16), 16)
    with pytest.raises(png.PngError):
        png.inspect_png(data[:-6])


def test_ancillary_chunk_insertion_detected():
    data = png.insert_chunk(png.write_png(np.zeros((2, 2), np.uint16), 16), "gAMA", (45455).to_bytes(4, "big"))
    info = png.inspect_png(data)
    assert info.has("gAMA")
    assert np.array_equal(png.decode_pixels(data), np.zeros((2, 2)))
