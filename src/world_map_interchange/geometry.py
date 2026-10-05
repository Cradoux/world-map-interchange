"""Regular longitude/latitude grid geometry (``lonlat_regular``).

Rows run north to south and columns west to east. Bounds are the outer
pixel edges. For row ``r`` (0-based) and column ``c``::

    lon(c) = west  + (c + 0.5) * (east - west)   / width
    lat(r) = north - (r + 0.5) * (north - south) / height

``east`` is always greater than ``west``. A region crossing the
antimeridian uses ``east > 180`` (for example west 170, east 190). A grid
whose longitude span is exactly 360 degrees wraps, and its last column is
adjacent to its first. No seam column is duplicated.
"""

from __future__ import annotations

import numpy as np


def normalize_lon(lon):
    """Map longitudes to [-180, 180)."""
    return (np.asarray(lon, dtype=np.float64) + 180.0) % 360.0 - 180.0


def lon_span(grid: dict) -> float:
    b = grid["bounds"]
    return float(b["east"]) - float(b["west"])


def wraps(grid: dict) -> bool:
    return abs(lon_span(grid) - 360.0) < 1e-9


def crosses_antimeridian(grid: dict) -> bool:
    b = grid["bounds"]
    return not wraps(grid) and b["east"] > 180.0


def pixel_size(grid: dict) -> tuple[float, float]:
    b = grid["bounds"]
    return lon_span(grid) / grid["width"], (b["north"] - b["south"]) / grid["height"]


def pixel_centre(grid: dict, row: int, col: int, normalize: bool = True) -> tuple[float, float]:
    """(lat, lon) of a pixel centre. Longitude is normalised to [-180, 180) by default."""
    b = grid["bounds"]
    dlon, dlat = pixel_size(grid)
    lon = b["west"] + (col + 0.5) * dlon
    lat = b["north"] - (row + 0.5) * dlat
    return float(lat), float(normalize_lon(lon) if normalize else lon)


def centres(grid: dict, normalize: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Arrays of row latitudes (height,) and column longitudes (width,)."""
    b = grid["bounds"]
    dlon, dlat = pixel_size(grid)
    lons = b["west"] + (np.arange(grid["width"]) + 0.5) * dlon
    lats = b["north"] - (np.arange(grid["height"]) + 0.5) * dlat
    return lats, (normalize_lon(lons) if normalize else lons)


def aligned(a: dict, b: dict) -> bool:
    """True if both grids have identical bounds and one's pixel edges nest in the other's."""
    if a.get("type") != "lonlat_regular" or b.get("type") != "lonlat_regular":
        return False
    if a["bounds"] != b["bounds"]:
        return False
    for key in ("width", "height"):
        big, small = max(a[key], b[key]), min(a[key], b[key])
        if big % small:
            return False
    return True
