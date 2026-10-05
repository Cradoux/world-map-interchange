"""Minimal climate-only producer using the reference library.

    uv run python examples/code/write_climate_package.py out/my-climate
    uv run wmi validate out/my-climate
    uv run wmi pack out/my-climate out/my-climate.zip

Replace the synthetic arrays with your model's output. Arrays are (rows, cols),
row 0 at the north edge, column 0 at the west edge, with no duplicated seam column.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from world_map_interchange import encode
from world_map_interchange.bundle import dump_json, rehash
from world_map_interchange.png import write_png

WIDTH, HEIGHT = 360, 180
TEMP_RANGE = (-90.0, 60.0)       # degC, shared by every temperature statistic
PRECIP_RANGE = (0.0, 10000.0)    # mm per year, shared by rain, snow and total


def synthetic_fields():
    lat = np.radians(90 - (np.arange(HEIGHT) + 0.5) * 180 / HEIGHT)[:, None]
    lon = np.radians(-180 + (np.arange(WIDTH) + 0.5) * 360 / WIDTH)[None, :]
    t_mean = 27 - 52 * np.sin(lat) ** 2 + 0 * lon
    precip = np.maximum(0, 400 + 2000 * np.exp(-(lat / 0.2) ** 2) + 500 * np.sin(2 * lon))
    snow = precip * np.clip((2 - t_mean) / 12, 0, 1)
    ocean = np.sin(2 * lon + 0.5) * np.cos(lat) < -0.2
    return t_mean, t_mean - 12, t_mean + 9, precip - snow, snow, precip, ocean


def main(out_dir: str) -> None:
    out = Path(out_dir)
    for sub in ("maps", "masks"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    t_mean, t_min, t_max, rain, snow, total, ocean = synthetic_fields()

    calendar = {
        "kind": "fixed",
        "description": "Replace with the model calendar. Periods may be unequal and any number.",
        "day_length_s": 86400,
        "year_length_days": 360,
        "periods": [{"id": f"p{i:02d}", "length_days": 30} for i in range(1, 13)],
    }
    span = {"start": {"year": 1}, "end": {"year": 30}}

    def time(steps, label):
        return {"calendar": "model", "label": label, "span": span, "aggregation": steps}

    annual_mean = [{"statistic": "mean", "over": "timesteps", "within": "year"}, {"statistic": "mean", "over": "years"}]
    annual_min = [{"statistic": "minimum", "over": "timesteps", "within": "year"}, {"statistic": "mean", "over": "years"}]
    annual_max = [{"statistic": "maximum", "over": "timesteps", "within": "year"}, {"statistic": "mean", "over": "years"}]
    annual_total = [{"statistic": "sum", "over": "timesteps", "within": "year"}, {"statistic": "mean", "over": "years"}]
    temperature_qualifiers = {"elevation_reference": "terrain", "height_above_surface_m": 2.0}

    layers = []

    def scalar(layer_id, quantity, values, units, rng, steps, label, qualifiers=None):
        (out / "maps" / f"{layer_id}.png").write_bytes(write_png(encode(values, *rng), 16))
        layer = {
            "id": layer_id, "kind": "scalar", "quantity": quantity, "grid": "global",
            "path": f"maps/{layer_id}.png", "sha256": "", "units": units,
            "encoding": {"type": "png16_linear", "min": rng[0], "max": rng[1]},
            "time": time(steps, label),
        }
        if qualifiers:
            layer["qualifiers"] = qualifiers
        layers.append(layer)

    scalar("t-mean", "air_temperature", t_mean, "degC", TEMP_RANGE, annual_mean, "30-year annual mean", temperature_qualifiers)
    scalar("t-min", "air_temperature", t_min, "degC", TEMP_RANGE, annual_min, "Mean annual minimum", temperature_qualifiers)
    scalar("t-max", "air_temperature", t_max, "degC", TEMP_RANGE, annual_max, "Mean annual maximum", temperature_qualifiers)
    scalar("rain", "rainfall_amount", rain, "mm", PRECIP_RANGE, annual_total, "Mean annual rainfall")
    scalar("snowfall", "snowfall_amount", snow, "mm", PRECIP_RANGE, annual_total, "Mean annual snowfall (LWE)")
    scalar("precip", "precipitation_amount", total, "mm", PRECIP_RANGE, annual_total, "Mean annual precipitation")

    (out / "maps" / "ocean.png").write_bytes(write_png(np.where(ocean, 255, 0).astype(np.uint8), 8))
    layers.append({"id": "ocean", "kind": "mask", "quantity": "ocean_mask", "grid": "global",
                   "path": "maps/ocean.png", "sha256": "", "encoding": {"type": "png8_binary"}})

    manifest = {
        "format": "world-map-interchange",
        "format_version": "0.1.0",
        "package": {
            "id": f"urn:uuid:{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "producer": {"name": "example-climate-model", "version": "0.0.1"},
            "license": "CC-BY-4.0",
        },
        "world": {"id": "example:my-world", "body": {"shape": "sphere", "radius_m": None}},
        "source": {"run_id": "run-1"},
        "calendars": {"model": calendar},
        "grids": {"global": {"type": "lonlat_regular", "width": WIDTH, "height": HEIGHT,
                             "bounds": {"west": -180.0, "east": 180.0, "north": 90.0, "south": -90.0}}},
        "layers": layers,
    }
    (out / "manifest.json").write_text(dump_json(manifest), encoding="utf-8", newline="\n")
    rehash(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/my-climate")
