import json

import numpy as np
import pytest

from conftest import EXAMPLES, valid_examples
from world_map_interchange import geometry, validate
from world_map_interchange.bundle import Bundle, pack

INVALID = json.loads((EXAMPLES / "invalid" / "expectations.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", valid_examples(), ids=lambda p: p.name)
def test_valid_examples_conform_without_warnings(path):
    report = validate(path)
    assert report.conformant, [i.render() for i in report.errors]
    assert not report.warnings, [i.render() for i in report.warnings]
    assert report.checks == {"container": "passed", "manifest": "passed", "schema": "passed", "semantics": "passed", "files": "passed"}


@pytest.mark.parametrize("path", valid_examples(), ids=lambda p: p.name)
def test_expected_values_decode(path):
    doc = json.loads((EXAMPLES / "expected" / f"{path.name}.json").read_text(encoding="utf-8"))
    assert doc["samples"]
    with Bundle(path) as bundle:
        cache = {}
        for s in doc["samples"]:
            lid = s["layer"]
            if lid not in cache:
                cache[lid] = (bundle.layer(lid), bundle.raw(lid), *bundle.read(lid))
            layer, raw, values, valid = cache[lid]
            r, c = s["row"], s["col"]
            assert bool(valid[r, c]) == s["valid"], s
            if "lat" in s:
                lat, lon = geometry.pixel_centre(bundle.grid(lid), r, c)
                assert lat == pytest.approx(s["lat"], abs=1e-6) and lon == pytest.approx(s["lon"], abs=1e-6)
            if not s["valid"]:
                continue
            if "value" in s:
                assert int(raw[r, c]) == s["pixel"], s
                assert abs(values[r, c] - s["value"]) <= s["tolerance"] * (1 + 1e-9), s
                assert layer["units"] == s["units"]
            elif "code" in s:
                assert int(values[r, c]) == s["code"]
            else:
                assert bool(values[r, c]) == s["mask"]


@pytest.mark.parametrize("name", sorted(INVALID))
def test_invalid_examples_fail_for_their_reason(name):
    expectation = INVALID[name]
    report = validate(EXAMPLES / "invalid" / expectation["target"])
    assert not report.conformant
    assert sorted(report.codes()) == sorted(expectation["error_codes"]), [i.render() for i in report.errors]


def test_every_invalid_target_has_an_expectation():
    targets = {p.name for p in (EXAMPLES / "invalid").iterdir() if p.name != "expectations.json"}
    assert targets == {e["target"] for e in INVALID.values()}


@pytest.mark.parametrize("path", valid_examples(), ids=lambda p: p.name)
def test_pack_round_trip(path, tmp_path):
    out = tmp_path / f"{path.name}.zip"
    pack(path, out)
    report = validate(out)
    assert report.conformant, [i.render() for i in report.errors]
    assert not report.warnings
    with Bundle(path) as a, Bundle(out) as b:
        assert a.manifest == b.manifest
        for layer in a.manifest["layers"]:
            if layer["kind"] == "reference":
                continue
            va, ma = a.read(layer["id"])
            vb, mb = b.read(layer["id"])
            assert np.array_equal(ma, mb)
            assert np.array_equal(va[ma], vb[mb])


def test_packed_examples_conform():
    for z in sorted((EXAMPLES / "packed").glob("*.zip")):
        assert validate(z).conformant, z


def test_rain_plus_snow_matches_total():
    with Bundle(EXAMPLES / "valid" / "climate-only") as b:
        rain, _ = b.read("rain-annual")
        snow, _ = b.read("snowfall-annual")
        total, _ = b.read("precip-annual")
        step = 4000.0 / 65535
        assert np.abs(rain + snow - total).max() <= 1.5 * step
        assert (total == 0).any(), "example should contain legitimate zero precipitation"
        for lid in ("rain-annual", "snowfall-annual", "precip-annual"):
            assert b.layer(lid)["time"] == b.layer("precip-annual")["time"]


def test_temperature_statistics_are_distinct_and_ordered():
    with Bundle(EXAMPLES / "valid" / "climate-only") as b:
        tmin, _ = b.read("t-annual-min")
        tcold, _ = b.read("t-coldest-period")
        tmean, _ = b.read("t-annual-mean")
        tmax, _ = b.read("t-annual-max")
        assert np.all(tmin <= tcold) and np.all(tcold <= tmean) and np.all(tmean <= tmax)
        assert tmin.min() < 0
        steps = {lid: b.layer(lid)["time"]["aggregation"] for lid in ("t-annual-min", "t-coldest-period", "t-annual-mean")}
        assert len({json.dumps(v) for v in steps.values()}) == 3


def test_seam_crossing_columns_are_adjacent():
    with Bundle(EXAMPLES / "valid" / "regional-seam") as b:
        g = b.grid("elevation")
    assert not geometry.wraps(g) and geometry.crosses_antimeridian(g)
    assert geometry.pixel_centre(g, 0, 19)[1] == pytest.approx(179.5)
    assert geometry.pixel_centre(g, 0, 20)[1] == pytest.approx(-179.5)
    assert geometry.pixel_centre(g, 0, 59)[1] == pytest.approx(-140.5)
    assert geometry.pixel_centre(g, 0, 0)[0] == pytest.approx(29.5)


def test_global_grid_has_no_duplicated_seam_column():
    g = {"type": "lonlat_regular", "width": 4, "height": 2, "bounds": {"west": -180, "east": 180, "north": 90, "south": -90}}
    lats, lons = geometry.centres(g)
    assert lons.tolist() == [-135.0, -45.0, 45.0, 135.0]
    assert lats.tolist() == [45.0, -45.0]
    assert geometry.wraps(g)


def test_multi_resolution_grids_are_aligned():
    with Bundle(EXAMPLES / "valid" / "multi-resolution") as b:
        grids = b.manifest["grids"]
    assert geometry.aligned(grids["g128"], grids["g32"])
    assert geometry.aligned(grids["g64"], grids["g32"])


def test_missing_versus_zero():
    with Bundle(EXAMPLES / "valid" / "missing-and-zero") as b:
        values, valid = b.read("precip-annual")
        raw = b.raw("precip-annual")
        assert valid[7, 5] and values[7, 5] == 0.0 and raw[7, 5] == 0
        assert not valid[3, 22] and raw[3, 22] == 0
        codes, cvalid = b.read("land-cover")
        assert cvalid[7, 5] and codes[7, 5] == 0
        _, nothing = b.read("snow-depth-max")
        assert not nothing.any()
        assert b.layer("snow-depth-max")["statistics"] == {"valid_count": 0}


def test_marine_biomes_are_preserved():
    with Bundle(EXAMPLES / "valid" / "biome-and-rock") as b:
        table = b.manifest["class_tables"]["example-biomes"]
        codes, _ = b.read("biome")
    marine = {c["code"] for c in table["classes"] if c.get("realm") == "marine"}
    assert marine == {0, 1}
    present = set(np.unique(codes).tolist())
    assert {0, 1} <= present
