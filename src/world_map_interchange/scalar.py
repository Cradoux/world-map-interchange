"""Linear PNG16 scalar encoding (``png16_linear``).

Decode contract (normative, see specification section 6.2)::

    value = encoding.min + pixel / 65535 * (encoding.max - encoding.min)

Encoding rounds to the nearest pixel, with exact ties rounded up
(towards the larger pixel value): ``pixel = floor(t * 65535 + 0.5)``.
Values whose rounded pixel would fall outside 0..65535 are rejected rather
than clipped.
"""

from __future__ import annotations

import math

import numpy as np

MAX_CODE = 65535


class EncodingRangeError(ValueError):
    """Raised when values cannot be represented with the requested range."""


def check_range(encoding_min: float, encoding_max: float) -> None:
    for name, value in (("encoding.min", encoding_min), ("encoding.max", encoding_max)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise EncodingRangeError(f"{name} must be a finite number, got {value!r}")
    if not encoding_min < encoding_max:
        raise EncodingRangeError(
            f"encoding.min ({encoding_min!r}) must be strictly less than encoding.max ({encoding_max!r})"
        )
    if not math.isfinite(float(encoding_max) - float(encoding_min)):
        raise EncodingRangeError("encoding.max - encoding.min overflows double precision")


def quantization_step(encoding_min: float, encoding_max: float) -> float:
    """Physical size of one pixel step."""
    check_range(encoding_min, encoding_max)
    return (float(encoding_max) - float(encoding_min)) / MAX_CODE


def encode(values, encoding_min: float, encoding_max: float, valid=None) -> np.ndarray:
    """Encode physical values to uint16 pixels.

    ``valid`` is an optional boolean array; invalid samples are written as 0
    and may contain NaN. Valid samples must be finite and representable.
    """
    check_range(encoding_min, encoding_max)
    v = np.asarray(values, dtype=np.float64)
    if valid is None:
        valid = np.ones(v.shape, dtype=bool)
    else:
        valid = np.asarray(valid, dtype=bool)
        if valid.shape != v.shape:
            raise ValueError(f"validity shape {valid.shape} does not match values shape {v.shape}")

    finite = np.isfinite(v)
    bad_finite = valid & ~finite
    if bad_finite.any():
        raise EncodingRangeError(
            f"{int(bad_finite.sum())} valid samples are NaN or infinite; mark them invalid in the validity mask"
        )

    lo = float(encoding_min)
    span = float(encoding_max) - lo
    safe = np.where(valid, v, lo)
    x = np.floor((safe - lo) / span * MAX_CODE + 0.5)
    outside = valid & ((x < 0) | (x > MAX_CODE))
    if outside.any():
        bad = safe[outside]
        raise EncodingRangeError(
            f"{int(outside.sum())} valid samples lie outside the encoding range "
            f"[{encoding_min!r}, {encoding_max!r}] (observed {bad.min()!r} to {bad.max()!r}); "
            "widen the range or mark the samples invalid - values are never clipped silently"
        )
    return np.where(valid, x, 0).astype(np.uint16)


def decode(pixels, encoding_min: float, encoding_max: float) -> np.ndarray:
    """Decode uint16 pixels to float64 physical values."""
    check_range(encoding_min, encoding_max)
    p = np.asarray(pixels)
    if p.dtype.kind not in "ui":
        raise TypeError("pixels must be an integer array")
    if p.size and (p.min() < 0 or p.max() > MAX_CODE):
        raise ValueError("pixels must lie in 0..65535")
    lo = float(encoding_min)
    hi = float(encoding_max)
    out = lo + (p.astype(np.float64) / MAX_CODE) * (hi - lo)
    # Guarantee the upper endpoint decodes exactly despite floating-point rounding.
    out[p == MAX_CODE] = hi
    return out


def choose_range(values, valid=None) -> tuple[float, float]:
    """Pick an encoding range covering the valid samples.

    Constant fields with value ``c`` return ``(c, c + delta)`` so that every
    sample encodes to pixel 0 and decodes to ``c`` exactly. Fields with no
    valid samples return ``(0.0, 1.0)``.
    """
    v = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(v) if valid is None else (np.asarray(valid, dtype=bool) & np.isfinite(v))
    if not mask.any():
        return 0.0, 1.0
    lo = float(v[mask].min())
    hi = float(v[mask].max())
    if lo == hi:
        delta = max(1.0, abs(lo) * 2.0**-20)
        return lo, lo + delta
    return lo, hi


def statistics(decoded: np.ndarray, valid: np.ndarray | None) -> dict:
    if valid is None:
        valid = np.ones(decoded.shape, dtype=bool)
    count = int(valid.sum())
    if count == 0:
        return {"valid_count": 0}
    vals = decoded[valid]
    return {
        "valid_count": count,
        "minimum": float(vals.min()),
        "maximum": float(vals.max()),
        "mean": float(vals.mean()),
    }
