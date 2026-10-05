"""Locate bundled schemas and the quantity registry.

Wheels carry copies under ``_data``; source checkouts and editable installs
read the canonical files at the repository root.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from .constants import FORMAT_VERSION

_PACKAGE_DIR = Path(__file__).resolve().parent


def _data_root(kind: str) -> Path:
    bundled = _PACKAGE_DIR / "_data" / kind
    if bundled.is_dir():
        return bundled
    repo = _PACKAGE_DIR.parent.parent / kind
    if repo.is_dir():
        return repo
    raise FileNotFoundError(f"cannot locate WMI {kind} directory")


def schema_path(name: str, version: str = FORMAT_VERSION) -> Path:
    return _data_root("schemas") / version / name


@functools.lru_cache(maxsize=None)
def load_schema(name: str, version: str = FORMAT_VERSION) -> dict:
    with open(schema_path(name, version), encoding="utf-8") as fh:
        return json.load(fh)


@functools.lru_cache(maxsize=None)
def load_registry(version: str = FORMAT_VERSION) -> "Registry":
    with open(_data_root("registry") / version / "quantities.json", encoding="utf-8") as fh:
        return Registry(json.load(fh))


class Registry:
    def __init__(self, data: dict):
        self.data = data
        self.version = data["registry_version"]
        self.units: dict[str, dict] = data["units"]
        self.quantities: dict[str, dict] = data["quantities"]

    def quantity(self, name: str) -> dict | None:
        return self.quantities.get(name)

    def to_canonical(self, value: float, unit: str) -> float:
        u = self.units[unit]
        return value * u["scale"] + u["offset"]

    def from_canonical(self, value: float, unit: str) -> float:
        u = self.units[unit]
        return (value - u["offset"]) / u["scale"]

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        a, b = self.units[from_unit], self.units[to_unit]
        if a["dimension"] != b["dimension"]:
            raise ValueError(f"cannot convert {from_unit!r} ({a['dimension']}) to {to_unit!r} ({b['dimension']})")
        return self.from_canonical(self.to_canonical(value, from_unit), to_unit)
