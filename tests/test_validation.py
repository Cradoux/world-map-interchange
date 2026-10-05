"""Targeted validator behaviour beyond the committed invalid examples."""

import json
import os
import shutil
import zipfile

import numpy as np
import pytest

from conftest import EXAMPLES
from world_map_interchange import png, validate
from world_map_interchange.bundle import dump_json, rehash
from world_map_interchange.package import Limits

BASE = EXAMPLES / "valid" / "constant-fields"


@pytest.fixture
def pkg(tmp_path):
    target = tmp_path / "pkg"
    shutil.copytree(BASE, target)
    return target


def edit(pkg, fn, do_rehash=True):
    mpath = pkg / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    fn(manifest)
    mpath.write_text(dump_json(manifest), encoding="utf-8")
    if do_rehash:
        rehash(pkg)


def codes(target, **kw):
    return validate(target, **kw).codes()


def test_baseline_is_valid(pkg):
    assert validate(pkg).conformant


def test_manifest_with_bom_rejected(pkg):
    data = (pkg / "manifest.json").read_bytes()
    (pkg / "manifest.json").write_bytes(b"\xef\xbb\xbf" + data)
    assert codes(pkg) == {"manifest.json"}


def test_duplicate_json_keys_rejected(pkg):
    text = (pkg / "manifest.json").read_text(encoding="utf-8")
    text = text.replace('"format": "world-map-interchange",', '"format": "world-map-interchange", "format": "x",', 1)
    (pkg / "manifest.json").write_text(text, encoding="utf-8")
    assert codes(pkg) == {"manifest.json"}


def test_nan_literal_rejected(pkg):
    text = (pkg / "manifest.json").read_text(encoding="utf-8").replace('"min": 250.0', '"min": NaN', 1)
    (pkg / "manifest.json").write_text(text, encoding="utf-8")
    assert codes(pkg) == {"manifest.json"}


def test_future_version_reported_clearly(pkg):
    edit(pkg, lambda m: m.update(format_version="0.2.0"), do_rehash=False)
    assert codes(pkg) == {"version.unsupported"}


def test_schema_error_has_pointer(pkg):
    edit(pkg, lambda m: m["layers"][0].pop("units"), do_rehash=False)
    report = validate(pkg)
    assert report.codes() == {"schema.manifest"}
    assert any(i.location == "/layers/0" for i in report.errors)
    assert report.checks["semantics"] == "skipped"


def test_colour_management_chunk_warns(pkg):
    p = pkg / "maps" / "elevation.png"
    p.write_bytes(png.insert_chunk(p.read_bytes(), "gAMA", (45455).to_bytes(4, "big")))
    rehash(pkg)
    report = validate(pkg)
    assert report.conformant
    assert {i.code for i in report.warnings} == {"png.colour_management"}


def test_pixel_limit(pkg):
    assert "limit.pixels" in codes(pkg, limits=Limits(max_pixels=100))


def test_file_size_limit(pkg):
    assert "limit.file_size" in codes(pkg, limits=Limits(max_file_bytes=50))


def test_unreferenced_file_warns(pkg):
    (pkg / "maps" / "stray.png").write_bytes(b"x")
    (pkg / "README.md").write_text("allowed", encoding="utf-8")
    report = validate(pkg)
    assert report.conformant
    assert [i.file for i in report.warnings] == ["maps/stray.png"]


def test_non_portable_path(pkg):
    shutil.move(pkg / "maps" / "elevation.png", pkg / "maps" / "Elev ation.png")
    edit(pkg, lambda m: m["layers"][0].update(path="maps/Elev ation.png"), do_rehash=False)
    assert "schema.manifest" in codes(pkg)


def test_case_mismatch_is_missing_file(pkg):
    shutil.move(pkg / "maps" / "elevation.png", pkg / "maps" / "Elevation.png")
    assert "file.missing" in codes(pkg)


def test_wrong_directory_for_kind(pkg):
    edit(pkg, lambda m: m["layers"][2].update(path="previews/ocean.png"), do_rehash=False)
    assert codes(pkg) == {"schema.manifest"}


def test_quantity_kind_mismatch(pkg):
    edit(pkg, lambda m: m["layers"][2].update(quantity="lake_mask"))
    assert validate(pkg).conformant
    edit(pkg, lambda m: m["layers"][2].update(quantity="elevation"))
    assert "quantity.kind_mismatch" in codes(pkg)


def test_undeclared_datum(pkg):
    edit(pkg, lambda m: m["layers"][0]["qualifiers"].update(datum="geoid"))
    assert codes(pkg) == {"reference.missing"}


def test_land_clamped_requires_clamp_value(pkg):
    edit(pkg, lambda m: m["layers"][0]["qualifiers"].update(coverage="land_clamped"))
    assert codes(pkg) == {"qualifiers.invalid"}
    edit(pkg, lambda m: m["layers"][0]["qualifiers"].update(clamp_value=0.0))
    assert validate(pkg).conformant


def test_namespaced_qualifiers_are_allowed(pkg):
    edit(pkg, lambda m: m["layers"][0]["qualifiers"].update({"mytool:smoothing": 3}))
    assert validate(pkg).conformant


def test_reserved_namespace(pkg):
    def fn(m):
        m["layers"][1].update(quantity="wmi:thing", definition="x")
        m["layers"][1].pop("qualifiers")
    edit(pkg, fn)
    assert codes(pkg) == {"quantity.reserved_namespace"}


def test_snapshot_quantity_cannot_be_aggregated(pkg):
    def fn(m):
        m["calendars"] = {"c": {"kind": "proleptic_gregorian"}}
        m["layers"][0]["time"] = {"calendar": "c", "span": {"start": {"year": 2000}, "end": {"year": 2001}},
                                  "aggregation": [{"statistic": "mean", "over": "timesteps", "within": "span"}]}
    edit(pkg, fn)
    assert codes(pkg) == {"semantics.time_forbidden"}


def test_gregorian_months_and_span_order(pkg):
    def fn(m):
        m["calendars"] = {"c": {"kind": "proleptic_gregorian"}}
        m["layers"][1]["time"] = {"calendar": "c", "span": {"start": {"year": 2001, "period": "mar"}, "end": {"year": 2000}},
                                  "aggregation": [{"statistic": "maximum", "over": "timesteps", "within": "span"}]}
    edit(pkg, fn)
    assert codes(pkg) == {"time.span_order"}


def test_period_aggregation_needs_periods(pkg):
    def fn(m):
        m["calendars"] = {"c": {"kind": "fixed", "year_length_days": 300}}
        m["layers"][1]["time"] = {"calendar": "c", "span": {"start": {"year": 1}, "end": {"year": 5}},
                                  "aggregation": [{"statistic": "mean", "over": "timesteps", "within": "period"},
                                                  {"statistic": "mean", "over": "years"},
                                                  {"statistic": "minimum", "over": "periods"}]}
    edit(pkg, fn)
    assert codes(pkg) == {"time.no_periods"}


def test_select_periods_must_exist(pkg):
    def fn(m):
        m["calendars"] = {"c": {"kind": "proleptic_gregorian"}}
        m["layers"][1]["time"] = {"calendar": "c", "span": {"start": {"year": 1991}, "end": {"year": 2020}},
                                  "select_periods": ["jan", "smarch"],
                                  "aggregation": [{"statistic": "mean", "over": "timesteps", "within": "year"},
                                                  {"statistic": "mean", "over": "years"}]}
    edit(pkg, fn)
    assert codes(pkg) == {"reference.missing"}


def test_calendar_period_sum(pkg):
    edit(pkg, lambda m: m.update(calendars={"c": {"kind": "fixed", "year_length_days": 10,
                                                  "periods": [{"id": "a", "length_days": 4}, {"id": "b", "length_days": 5}]}}))
    assert codes(pkg) == {"calendar.inconsistent"}


def test_physical_range_enforced(pkg):
    def fn(m):
        m["layers"][1]["encoding"].update(min=-300.0, max=-299.0)
        m["layers"][1].pop("statistics")
    p = pkg / "maps" / "t-snapshot.png"
    p.write_bytes(png.write_png(np.zeros((16, 32), np.uint16), 16))
    edit(pkg, fn)
    assert codes(pkg) == {"value.out_of_range"}


def test_extension_grid_reported_unsupported(pkg):
    def fn(m):
        m["grids"]["planar"] = {"type": "example:local_planar", "origin": [0, 0]}
        m["layers"][2]["grid"] = "planar"
    edit(pkg, fn)
    report = validate(pkg)
    assert report.conformant
    assert "grid.unsupported_type" in {i.code for i in report.warnings}
    status = {s.id: s.status for s in report.layers}
    assert status["ocean"] == "unsupported"


def test_shared_path_rejected(pkg):
    edit(pkg, lambda m: m["layers"][1].update(path=m["layers"][0]["path"]))
    assert "path.reused" in codes(pkg)


@pytest.mark.skipif(os.name == "nt", reason="creating symlinks on Windows needs extra privileges")
def test_directory_symlink_rejected(pkg, tmp_path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"x")
    os.symlink(outside, pkg / "maps" / "linked.png")
    assert "package.symlink" in codes(pkg)


def _zip(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data, method in entries:
            zf.writestr(zipfile.ZipInfo(name), data, compress_type=method)


def _entries(pkg):
    return [(p.relative_to(pkg).as_posix(), p.read_bytes(), zipfile.ZIP_STORED) for p in sorted(pkg.rglob("*")) if p.is_file()]


def test_zip_case_collision(pkg, tmp_path):
    z = tmp_path / "b.zip"
    _zip(z, _entries(pkg) + [("MAPS/elevation.png", b"x", zipfile.ZIP_STORED)])
    assert "path.case_collision" in codes(z)


def test_zip_bomb_ratio(pkg, tmp_path):
    z = tmp_path / "b.zip"
    _zip(z, _entries(pkg) + [("maps/huge.bin", b"\0" * 5_000_000, zipfile.ZIP_DEFLATED)])
    assert "limit.compression_ratio" in codes(z)


def test_zip_entry_limit(pkg, tmp_path):
    z = tmp_path / "b.zip"
    _zip(z, _entries(pkg))
    assert codes(z, limits=Limits(max_entries=2)) == {"limit.entries"}


def test_zip_unsupported_compression(pkg, tmp_path):
    z = tmp_path / "b.zip"
    _zip(z, _entries(pkg) + [("maps/x.bin", b"abc" * 100, zipfile.ZIP_BZIP2)])
    assert "archive.compression" in codes(z)


def test_not_a_zip(tmp_path):
    z = tmp_path / "x.zip"
    z.write_bytes(b"hello")
    assert codes(z) == {"archive.invalid"}


def test_missing_target(tmp_path):
    assert codes(tmp_path / "nope") == {"package.not_found"}
