import json

import numpy as np

from conftest import EXAMPLES
from world_map_interchange import validate
from world_map_interchange.cli import main
from world_map_interchange.resources import load_registry
from world_map_interchange.support import assess


def run(capsys, *argv):
    code = main(list(map(str, argv)))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_validate_exit_codes_and_json(capsys):
    code, out, _ = run(capsys, "validate", EXAMPLES / "valid" / "climate-only", "--json")
    assert code == 0
    doc = json.loads(out)
    assert doc["conformant"] is True and doc["error_count"] == 0
    code, out, _ = run(capsys, "validate", EXAMPLES / "invalid" / "bad-hash")
    assert code == 1
    assert "[hash.mismatch]" in out and "NOT CONFORMANT" in out


def test_inspect_human_and_json(capsys):
    code, out, _ = run(capsys, "inspect", EXAMPLES / "valid" / "elevation-bathymetry")
    assert code == 0
    assert "sea level 0.0 m -> pixel 37449 (derived)" in out
    assert "elevation-legend" in out and "unregistered" in out
    code, out, _ = run(capsys, "inspect", EXAMPLES / "valid" / "regional-seam", "--json")
    doc = json.loads(out)
    assert doc["grids"]["pacific-strip"]["crosses_antimeridian"] is True


def test_conformance_is_separate_from_consumer_requirements(capsys):
    profile = EXAMPLES / "profiles" / "heightmap-importer.json"
    code, out, _ = run(capsys, "validate", EXAMPLES / "valid" / "climate-only", "--consumer", profile, "--json")
    doc = json.loads(out)
    assert code == 0 and doc["conformant"] is True
    assert doc["consumer"]["requirements_met"] is False
    assert doc["consumer"]["required_quantities_missing"] == ["elevation"]
    assert {layer["status"] for layer in doc["layers"]} == {"unsupported"}


def test_supported_retained_unsupported():
    caps = json.loads((EXAMPLES / "profiles" / "climate-viewer.json").read_text(encoding="utf-8"))
    report = validate(EXAMPLES / "valid" / "snow-and-soil", capabilities=caps)
    status = {s.id: s.status for s in report.layers}
    assert status["snow-depth-max"] == "supported"
    assert status["bucket-index"] == "retained"
    caps["retain_unrecognised"] = False
    manifest = json.loads((EXAMPLES / "valid" / "snow-and-soil" / "manifest.json").read_text(encoding="utf-8"))
    layers, _ = assess(manifest, load_registry(), caps)
    assert {s.id: s.status for s in layers}["bucket-index"] == "unsupported"


def test_encode_decode_cli_round_trip(tmp_path, capsys):
    values = np.array([[-12.5, 0.0, np.nan], [3.25, 40.0, -60.0]])
    np.save(tmp_path / "t.npy", values)
    code, out, _ = run(capsys, "encode", tmp_path / "t.npy", tmp_path / "t.png", "--min", -60, "--max", 50,
                       "--mask-output", tmp_path / "t-valid.png")
    assert code == 0
    meta = json.loads(out)
    assert meta["invalid_samples"] == 1
    code, out, _ = run(capsys, "decode", tmp_path / "t.png", "--min", -60, "--max", 50, "-o", tmp_path / "back.npy")
    back = np.load(tmp_path / "back.npy")
    ok = np.isfinite(values)
    assert np.all(np.abs(back[ok] - values[ok]) <= 110 / 65535 / 2 + 1e-12)


def test_encode_refuses_out_of_range(tmp_path, capsys):
    np.save(tmp_path / "t.npy", np.array([[100.0]]))
    code, _, err = run(capsys, "encode", tmp_path / "t.npy", tmp_path / "t.png", "--min", 0, "--max", 50)
    assert code == 1 and "never clipped" in err


def test_decode_layer_sample(capsys):
    code, out, _ = run(capsys, "decode", EXAMPLES / "valid" / "missing-and-zero", "--layer", "precip-annual", "--sample", 3, 22)
    assert code == 0 and "invalid" in out
    code, out, _ = run(capsys, "decode", EXAMPLES / "valid" / "missing-and-zero", "--layer", "precip-annual", "--sample", 7, 5)
    assert "0.0 mm" in out


def test_pack_rehash_sidecars(tmp_path, capsys):
    import shutil

    pkg = tmp_path / "pkg"
    shutil.copytree(EXAMPLES / "valid" / "constant-fields", pkg)
    code, out, _ = run(capsys, "sidecars", pkg)
    assert code == 0 and (pkg / "maps" / "elevation.png.json").is_file()
    code, out, _ = run(capsys, "rehash", pkg)
    assert "Updated 0 hash" in out
    code, out, _ = run(capsys, "pack", pkg, tmp_path / "out.zip")
    assert code == 0 and validate(tmp_path / "out.zip").conformant
    (pkg / "maps" / "elevation.png").write_bytes((pkg / "maps" / "ocean.png").read_bytes())
    code, _, err = run(capsys, "pack", pkg, tmp_path / "bad.zip")
    assert code == 1 and "refusing" in err
