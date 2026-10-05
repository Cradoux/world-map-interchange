import json

import pytest
from jsonschema import Draft202012Validator

from conftest import EXAMPLES, ROOT, valid_examples
from world_map_interchange import validate
from world_map_interchange.jsonutil import SCHEMA_NAMES, schema_errors
from world_map_interchange.resources import load_registry, load_schema

SCHEMA_DIR = ROOT / "schemas" / "0.1.0"


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_schemas_are_valid_draft_2020_12(name):
    schema = load_schema(name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_schema_directory_matches_known_names():
    assert sorted(p.name for p in SCHEMA_DIR.glob("*.json")) == sorted(SCHEMA_NAMES)


def test_registry_validates_and_qualifier_schemas_are_valid():
    data = json.loads((ROOT / "registry" / "0.1.0" / "quantities.json").read_text(encoding="utf-8"))
    assert schema_errors(data, "registry.schema.json") == []
    reg = load_registry()
    for name, q in reg.quantities.items():
        Draft202012Validator.check_schema(q["qualifiers"])
        if q["kind"] == "scalar":
            assert q["canonical_unit"] in q["units"], name
            dimensions = {reg.units[u]["dimension"] for u in q["units"]}
            # Water amounts may be given as depth or mass per area (1 mm = 1 kg m-2 for liquid water).
            assert len(dimensions) == 1 or dimensions in (
                {"length", "areal_mass"},
                {"length_rate", "areal_mass_flux"},
            ), (name, dimensions)


@pytest.mark.parametrize("path", valid_examples(), ids=lambda p: p.name)
def test_example_manifests_match_schema(path):
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    assert schema_errors(manifest, "manifest.schema.json") == []


@pytest.mark.parametrize("path", valid_examples(), ids=lambda p: p.name)
def test_example_sidecars_match_schema(path):
    for side in path.rglob("*.png.json"):
        assert schema_errors(json.loads(side.read_text(encoding="utf-8")), "sidecar.schema.json") == []


def test_reports_match_report_schema():
    targets = valid_examples() + [EXAMPLES / "invalid" / "unsafe-archive-path.zip", EXAMPLES / "invalid" / "bad-hash"]
    for target in targets:
        assert schema_errors(validate(target).to_dict(), "validation-report.schema.json") == [], target


def test_profiles_match_capabilities_schema():
    for profile in sorted((EXAMPLES / "profiles").glob("*.json")):
        assert schema_errors(json.loads(profile.read_text(encoding="utf-8")), "capabilities.schema.json") == [], profile


def test_unit_conversion():
    reg = load_registry()
    assert reg.convert(0.0, "degC", "K") == pytest.approx(273.15)
    assert reg.convert(1.0, "mm d-1", "mm s-1") == pytest.approx(1 / 86400)
    with pytest.raises(ValueError):
        reg.convert(1.0, "mm", "K")
