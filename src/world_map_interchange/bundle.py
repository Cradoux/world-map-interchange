"""Producer and consumer helpers: read layers, write manifests, pack, rehash, sidecars."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np

from . import png as pngmod
from . import scalar as scalarmod
from .constants import FORMAT_VERSION, MANIFEST_NAME, SIDECAR_FORMAT, SIDECAR_SUFFIX
from .jsonutil import loads_strict
from .package import Limits, PackageError, open_package, portability_problem
from .report import Report

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def dump_json(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Bundle:
    """Read-only access to a package. Call ``validate`` first for untrusted input."""

    def __init__(self, target, limits: Limits | None = None):
        self.limits = limits or Limits()
        self._report = Report(target=str(target))
        self.source = open_package(target, self.limits, self._report)
        if self._report.errors:
            first = self._report.errors[0]
            self.source.close()
            raise PackageError(first.code, first.message, first.file)
        self.manifest = loads_strict(self.source.read(MANIFEST_NAME, self.limits.max_manifest_bytes))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        self.source.close()

    def layer(self, layer_id: str) -> dict:
        for layer in self.manifest["layers"]:
            if layer["id"] == layer_id:
                return layer
        raise KeyError(f"no layer {layer_id!r}")

    def grid(self, layer_id: str) -> dict:
        return self.manifest["grids"][self.layer(layer_id)["grid"]]

    def raw(self, layer_id: str) -> np.ndarray:
        layer = self.layer(layer_id)
        return pngmod.decode_pixels(self.source.read(layer["path"], self.limits.max_file_bytes))

    def validity(self, layer_id: str) -> np.ndarray | None:
        vm = self.layer(layer_id).get("validity_mask")
        if vm is None:
            return None
        return pngmod.decode_pixels(self.source.read(vm["path"], self.limits.max_file_bytes)) == 255

    def read(self, layer_id: str) -> tuple[np.ndarray, np.ndarray]:
        """Return (values, valid). Scalars are decoded to float64 physical units;
        categorical layers return class codes; masks return booleans."""
        layer = self.layer(layer_id)
        arr = self.raw(layer_id)
        valid = self.validity(layer_id)
        if valid is None:
            valid = np.ones(arr.shape[:2], dtype=bool)
        if layer["kind"] == "scalar":
            enc = layer["encoding"]
            return scalarmod.decode(arr, enc["min"], enc["max"]), valid
        if layer["kind"] == "mask":
            return arr == 255, valid
        return arr, valid


def _referenced_paths(manifest: dict) -> list[str]:
    paths = []
    for layer in manifest["layers"]:
        paths.append(layer["path"])
        if "validity_mask" in layer:
            paths.append(layer["validity_mask"]["path"])
    return sorted(set(paths))


def _safe_join(root: Path, rel: str) -> Path:
    problem = portability_problem(rel)
    if problem:
        raise PackageError("path.non_portable", f"path {rel!r} {problem}", rel)
    full = root.joinpath(*rel.split("/"))
    if full.is_symlink() or not full.resolve().is_relative_to(root.resolve()):
        raise PackageError("package.symlink", f"path {rel!r} resolves outside the package", rel)
    return full


def rehash(directory) -> list[str]:
    """Recompute sha256 values in a directory package's manifest. Returns changed paths."""
    root = Path(directory)
    mpath = root / MANIFEST_NAME
    manifest = loads_strict(mpath.read_bytes())
    changed = []

    def update(entry: dict) -> None:
        digest = sha256_bytes(_safe_join(root, entry["path"]).read_bytes())
        if entry.get("sha256") != digest:
            changed.append(entry["path"])
            entry["sha256"] = digest

    for layer in manifest["layers"]:
        update(layer)
        if "validity_mask" in layer:
            update(layer["validity_mask"])
    mpath.write_text(dump_json(manifest), encoding="utf-8", newline="\n")
    return sorted(set(changed))


def sidecar_for(manifest: dict, layer: dict) -> dict:
    out = {
        "format": SIDECAR_FORMAT,
        "format_version": manifest["format_version"],
        "generated_from": MANIFEST_NAME,
        "layer": layer,
    }
    if layer.get("grid"):
        out["grid"] = manifest["grids"][layer["grid"]]
    if layer.get("class_table"):
        out["class_table"] = manifest["class_tables"][layer["class_table"]]
    return out


def write_sidecars(directory) -> list[str]:
    """Generate '<image>.json' sidecars for every layer from the manifest."""
    root = Path(directory)
    manifest = loads_strict((root / MANIFEST_NAME).read_bytes())
    written = []
    for layer in manifest["layers"]:
        rel = layer["path"] + SIDECAR_SUFFIX
        _safe_join(root, rel).write_text(dump_json(sidecar_for(manifest, layer)), encoding="utf-8", newline="\n")
        written.append(rel)
    return written


def pack(directory, output, *, include_sidecars: bool = True) -> list[str]:
    """Write a deterministic ZIP containing the manifest and every referenced file.

    PNGs are stored (they are already compressed); JSON is deflated. The
    caller should validate the directory first.
    """
    root = Path(directory)
    manifest_bytes = (root / MANIFEST_NAME).read_bytes()
    manifest = loads_strict(manifest_bytes)
    names = [MANIFEST_NAME] + _referenced_paths(manifest)
    if include_sidecars:
        for layer in manifest["layers"]:
            rel = layer["path"] + SIDECAR_SUFFIX
            if _safe_join(root, rel).is_file():
                names.append(rel)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zf:
        for name in names:
            data = manifest_bytes if name == MANIFEST_NAME else _safe_join(root, name).read_bytes()
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED if name.endswith(".png") else zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return names


def new_manifest(*, package_id: str, created: str, producer: dict, license: str, world: dict, grids: dict, layers: list, **extra) -> dict:
    manifest = {
        "format": "world-map-interchange",
        "format_version": FORMAT_VERSION,
        "package": {"id": package_id, "created": created, "producer": producer, "license": license},
        "world": world,
    }
    for key in ("source", "calendars"):
        if key in extra:
            manifest[key] = extra.pop(key)
    manifest["grids"] = grids
    if "class_tables" in extra:
        manifest["class_tables"] = extra.pop("class_tables")
    manifest["layers"] = layers
    for key, value in extra.items():
        if key in ("title", "description", "attribution", "url"):
            manifest["package"][key] = value
        else:
            manifest[key] = value
    return manifest
