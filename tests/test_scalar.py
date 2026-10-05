import math

import numpy as np
import pytest

from world_map_interchange import scalar


def half_step(lo, hi):
    return (hi - lo) / 65535 / 2


@pytest.mark.parametrize(
    "lo,hi",
    [(-90.0, 50.0), (-60.0, -10.0), (0.0, 4000.0), (-8000.0, 6000.0), (0.0, 1.0), (200.0, 320.0), (-1e-3, 1e-3), (-1e6, 1e6)],
)
def test_round_trip_within_half_step(lo, hi):
    rng = np.random.default_rng(1234)
    values = rng.uniform(lo, hi, size=(64, 128))
    values[0, 0] = lo
    values[0, 1] = hi
    decoded = scalar.decode(scalar.encode(values, lo, hi), lo, hi)
    err = np.abs(decoded - values)
    assert err.max() <= half_step(lo, hi) * (1 + 1e-9)


def test_negative_temperatures_round_trip():
    values = np.array([[-89.99, -40.0, -0.0001, 0.0, 12.345, 49.999]])
    decoded = scalar.decode(scalar.encode(values, -90.0, 50.0), -90.0, 50.0)
    assert np.all(np.abs(decoded - values) <= half_step(-90.0, 50.0))
    assert decoded[0, 1] < 0


def test_endpoints_are_exact():
    for lo, hi in [(-0.1, 0.3), (-90.0, 50.0), (1e-7, 3e-7), (-8000.0, 6000.0)]:
        pixels = scalar.encode([lo, hi], lo, hi)
        assert pixels.tolist() == [0, 65535]
        decoded = scalar.decode(pixels, lo, hi)
        assert decoded[0] == lo
        assert decoded[1] == hi


def test_ties_round_up():
    # With range 0..65535 one step is exactly 1, so x.5 values are exact ties.
    pixels = scalar.encode([0.5, 1.5, 2.5, 65534.5], 0.0, 65535.0)
    assert pixels.tolist() == [1, 2, 3, 65535]


def test_out_of_range_rejected_not_clipped():
    with pytest.raises(scalar.EncodingRangeError, match="never clipped"):
        scalar.encode([-91.0], -90.0, 50.0)
    with pytest.raises(scalar.EncodingRangeError):
        scalar.encode([50.01], -90.0, 50.0)


def test_values_within_half_step_of_endpoint_accepted():
    step = (50.0 + 90.0) / 65535
    pixels = scalar.encode([50.0 + 0.49 * step, -90.0 - 0.49 * step], -90.0, 50.0)
    assert pixels.tolist() == [65535, 0]


def test_nan_requires_invalid_mask():
    with pytest.raises(scalar.EncodingRangeError, match="validity mask"):
        scalar.encode([1.0, math.nan], 0.0, 2.0)
    pixels = scalar.encode([1.0, math.nan], 0.0, 2.0, valid=[True, False])
    assert pixels[1] == 0


@pytest.mark.parametrize("lo,hi", [(1.0, 1.0), (2.0, 1.0), (math.nan, 1.0), (0.0, math.inf), (-1.7e308, 1.7e308)])
def test_bad_ranges(lo, hi):
    with pytest.raises(scalar.EncodingRangeError):
        scalar.check_range(lo, hi)


def test_constant_field():
    values = np.full((4, 4), -5.0)
    lo, hi = scalar.choose_range(values)
    assert lo == -5.0 and hi > lo
    pixels = scalar.encode(values, lo, hi)
    assert np.all(pixels == 0)
    assert np.all(scalar.decode(pixels, lo, hi) == -5.0)


def test_entirely_missing_field():
    values = np.full((3, 3), np.nan)
    valid = np.zeros((3, 3), bool)
    lo, hi = scalar.choose_range(values, valid)
    assert (lo, hi) == (0.0, 1.0)
    assert np.all(scalar.encode(values, lo, hi, valid) == 0)
    assert scalar.statistics(scalar.decode(np.zeros((3, 3), np.uint16), lo, hi), valid) == {"valid_count": 0}


def test_scale_offset_equivalence():
    lo, hi = -8000.0, 6000.0
    scale_factor = (hi - lo) / 65535
    add_offset = lo
    pixels = np.arange(0, 65536, 997, dtype=np.uint16)
    assert np.allclose(scalar.decode(pixels, lo, hi), pixels * scale_factor + add_offset, rtol=0, atol=1e-9)
