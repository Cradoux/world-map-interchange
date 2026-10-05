"""Package validation: container safety, schema, semantics and file contents."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import numpy as np
from jsonschema import Draft202012Validator

from . import png as pngmod
from . import scalar as scalarmod
from .constants import (
    DATA_KINDS,
    FORMAT_NAME,
    INTERPOLATING_RESAMPLING,
    MANIFEST_NAME,
    RESERVED_NAMESPACES,
    SIDECAR_SUFFIX,
)
from .jsonutil import StrictJSONError, loads_strict, pointer, schema_errors
from .package import Limits, PackageError, PackageSource, find_nested_manifest, open_package, portability_problem
from .report import Report
from .resources import Registry, load_registry
from .support import assess

GREGORIAN_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
ROOT_DOC = re.compile(r"^(README|LICENSE|LICENCE|NOTICE|CHANGELOG)([._-][A-Za-z0-9._-]*)?$", re.IGNORECASE)


@dataclass
class Context:
    manifest: dict
    registry: Registry
    report: Report
    source: PackageSource
    limits: Limits
    validity_cache: dict = field(default_factory=dict)
    referenced: set = field(default_factory=set)


def validate(target, *, limits: Limits | None = None, capabilities: dict | None = None) -> Report:
    """Validate a package directory or ZIP archive and return a Report."""
    limits = limits or Limits()
    report = Report(target=str(target))
    try:
        source = open_package(target, limits, report)
    except PackageError as exc:
        report.error(exc.code, str(exc), file=exc.file)
        report.checks["container"] = "failed"
        return report
    try:
        _run(source, report, limits, capabilities)
    finally:
        source.close()
    return report


def load_manifest(source: PackageSource, report: Report, limits: Limits) -> dict | None:
    if not source.exists(MANIFEST_NAME):
        nested = find_nested_manifest(source)
        hint = f"; found {nested!r} - manifest.json must be at the package root, not inside a folder" if nested else ""
        report.error("manifest.missing", f"no manifest.json at the package root{hint}")
        return None
    try:
        data = source.read(MANIFEST_NAME, limits.max_manifest_bytes)
        manifest = loads_strict(data)
    except PackageError as exc:
        report.error(exc.code, str(exc), file=MANIFEST_NAME)
        return None
    except StrictJSONError as exc:
        report.error("manifest.json", f"manifest.json is not valid strict JSON: {exc}", file=MANIFEST_NAME)
        return None
    if not isinstance(manifest, dict):
        report.error("manifest.json", "manifest.json must contain a JSON object", file=MANIFEST_NAME)
        return None
    return manifest


def _run(source: PackageSource, report: Report, limits: Limits, capabilities: dict | None) -> None:
    report.checks["container"] = "failed" if report.errors else "passed"
    manifest = load_manifest(source, report, limits)
    if manifest is None:
        report.checks["manifest"] = "failed"
        return
    report.checks["manifest"] = "passed"

    fmt = manifest.get("format")
    version = manifest.get("format_version")
    report.format_version = version if isinstance(version, str) else None
    if fmt != FORMAT_NAME:
        report.error("version.format", f"'format' must be {FORMAT_NAME!r}, found {fmt!r}", location="/format")
        report.checks["schema"] = "skipped"
        return
    if not isinstance(version, str) or not re.match(r"^0\.1\.(0|[1-9][0-9]*)$", version):
        report.error(
            "version.unsupported",
            f"format_version {version!r} is not supported by these tools (supported: 0.1.x); "
            "minor versions may be incompatible while the draft is 0.x",
            location="/format_version",
        )
        report.checks["schema"] = "skipped"
        return

    errors = schema_errors(manifest, "manifest.schema.json")
    for loc, msg in errors:
        report.error("schema.manifest", msg, location=loc or "/", file=MANIFEST_NAME)
    if errors:
        report.checks["schema"] = "failed"
        report.checks["semantics"] = "skipped"
        report.checks["files"] = "skipped"
        return
    report.checks["schema"] = "passed"

    registry = load_registry()
    ctx = Context(manifest, registry, report, source, limits)

    before = len(report.errors)
    check_semantics(ctx)
    report.checks["semantics"] = "failed" if len(report.errors) > before else "passed"

    before = len(report.errors)
    check_files(ctx)
    check_sidecars(ctx)
    check_unreferenced(ctx)
    report.checks["files"] = "failed" if len(report.errors) > before else "passed"

    report.layers, report.consumer = assess(manifest, registry, capabilities)


# ---------------------------------------------------------------- semantics


def check_semantics(ctx: Context) -> None:
    m, r = ctx.manifest, ctx.report
    grids = m["grids"]
    calendars = m.get("calendars", {})
    tables = m.get("class_tables", {})

    for gid, g in grids.items():
        loc = pointer("grids", gid)
        if g["type"] == "lonlat_regular":
            b = g["bounds"]
            if not b["east"] > b["west"]:
                r.error(
                    "grid.bounds",
                    f"grid {gid!r}: east ({b['east']}) must be greater than west ({b['west']}); "
                    "express a region crossing the antimeridian with east > 180, e.g. west 170, east 190",
                    location=loc + "/bounds",
                )
            elif b["east"] - b["west"] > 360 + 1e-9:
                r.error("grid.bounds", f"grid {gid!r}: longitude span exceeds 360 degrees", location=loc + "/bounds")
            if not b["north"] > b["south"]:
                r.error("grid.bounds", f"grid {gid!r}: north must be greater than south", location=loc + "/bounds")
        else:
            r.warning(
                "grid.unsupported_type",
                f"grid {gid!r} uses extension geometry {g['type']!r}; the reference tools will not interpret it",
                location=loc,
            )

    for cid, cal in calendars.items():
        loc = pointer("calendars", cid)
        periods = cal.get("periods")
        if periods:
            ids = [p["id"] for p in periods]
            dups = sorted({i for i in ids if ids.count(i) > 1})
            if dups:
                r.error("calendar.duplicate_period", f"calendar {cid!r} repeats period ids {dups}", location=loc + "/periods")
            total = sum(p["length_days"] for p in periods)
            year = cal["year_length_days"]
            if abs(total - year) > 1e-9 * max(1.0, year):
                r.error(
                    "calendar.inconsistent",
                    f"calendar {cid!r}: periods sum to {total} days but year_length_days is {year}",
                    location=loc,
                )

    for tid, table in tables.items():
        loc = pointer("class_tables", tid)
        codes = [c["code"] for c in table["classes"]]
        ids = [c["id"] for c in table["classes"]]
        for label, values in (("codes", codes), ("ids", ids)):
            dups = sorted({v for v in values if values.count(v) > 1}, key=str)
            if dups:
                r.error(f"class.duplicate_{label[:-1]}", f"class table {tid!r} repeats {label} {dups}", location=loc + "/classes")

    sim = m.get("source", {}).get("simulation_time")
    if sim:
        _check_time_point(ctx, sim, pointer("source", "simulation_time"), sim["calendar"])

    layer_ids = [layer["id"] for layer in m["layers"]]
    seen_ids: set[str] = set()
    seen_paths: dict[str, str] = {}
    validity_paths: set[str] = set()
    for layer in m["layers"]:
        if "validity_mask" in layer:
            validity_paths.add(layer["validity_mask"]["path"])

    if not any(layer["kind"] != "reference" for layer in m["layers"]):
        r.error("package.no_data_layers", "a package needs at least one data layer; reference images do not substitute for numeric data", location="/layers")

    for i, layer in enumerate(m["layers"]):
        loc = pointer("layers", i)
        lid = layer["id"]
        if lid in seen_ids:
            r.error("layer.duplicate_id", f"layer id {lid!r} is used more than once", location=loc + "/id")
        seen_ids.add(lid)

        path = layer["path"]
        problem = portability_problem(path)
        if problem:
            r.error("path.non_portable", f"layer {lid!r} path {path!r} {problem}", location=loc + "/path")
        if path in seen_paths:
            r.error("path.reused", f"layers {seen_paths[path]!r} and {lid!r} share the file {path!r}", location=loc + "/path")
        if path in validity_paths:
            r.error("path.reused", f"{path!r} is used both as a layer and as a validity mask", location=loc + "/path")
        seen_paths[path] = lid
        if "validity_mask" in layer:
            vpath = layer["validity_mask"]["path"]
            problem = portability_problem(vpath)
            if problem:
                r.error("path.non_portable", f"validity mask path {vpath!r} {problem}", location=loc + "/validity_mask/path")

        if "grid" in layer and layer["grid"] not in grids:
            r.error("reference.missing", f"layer {lid!r} refers to undeclared grid {layer['grid']!r}", location=loc + "/grid")
        if layer["kind"] == "categorical" and layer["class_table"] not in tables:
            r.error(
                "reference.missing",
                f"layer {lid!r} refers to undeclared class table {layer['class_table']!r}",
                location=loc + "/class_table",
            )
        for j, dep in enumerate(layer.get("depicts", [])):
            if dep not in layer_ids:
                r.error("reference.missing", f"reference {lid!r} depicts unknown layer {dep!r}", location=f"{loc}/depicts/{j}")
        for j, dep in enumerate(layer.get("provenance", {}).get("derived_from", [])):
            if dep not in layer_ids:
                r.warning("reference.missing", f"layer {lid!r} is derived from {dep!r}, which is not in this package", location=f"{loc}/provenance/derived_from/{j}")

        if "time" in layer:
            _check_time(ctx, layer["time"], loc + "/time")

        kind = layer["kind"]
        if kind == "reference":
            continue
        if kind not in DATA_KINDS:
            r.info("layer.extension_kind", f"layer {lid!r} has extension kind {kind!r}; only its hash is checked", location=loc + "/kind")
        _check_quantity(ctx, layer, loc)

        if kind == "scalar":
            enc = layer["encoding"]
            try:
                scalarmod.check_range(enc["min"], enc["max"])
            except scalarmod.EncodingRangeError as exc:
                r.error("encoding.range", f"layer {lid!r}: {exc}", location=loc + "/encoding")
        resampling = layer.get("source", {}).get("resampling")
        if kind in ("categorical", "mask") and resampling in INTERPOLATING_RESAMPLING:
            r.error(
                "resampling.invalid_for_kind",
                f"layer {lid!r}: {kind} data must not be resampled with {resampling!r}; class codes and masks cannot be interpolated "
                "(use 'nearest' or 'mode')",
                location=loc + "/source/resampling",
            )
        if resampling == "other" and "notes" not in layer.get("source", {}):
            r.warning("resampling.undocumented", f"layer {lid!r}: resampling 'other' should be explained in source.notes", location=loc + "/source")


def _calendar_periods(cal: dict) -> list[str]:
    if cal["kind"] == "proleptic_gregorian":
        return list(GREGORIAN_MONTHS)
    return [p["id"] for p in cal.get("periods", [])]


def _check_time_point(ctx: Context, point: dict, loc: str, calendar_id: str) -> None:
    cal = ctx.manifest.get("calendars", {}).get(calendar_id)
    if cal is None:
        ctx.report.error("reference.missing", f"undeclared calendar {calendar_id!r}", location=loc + "/calendar")
        return
    if "period" in point and point["period"] not in _calendar_periods(cal):
        ctx.report.error("reference.missing", f"calendar {calendar_id!r} has no period {point['period']!r}", location=loc + "/period")


def _check_time(ctx: Context, time: dict, loc: str) -> None:
    r = ctx.report
    cal_id = time["calendar"]
    cal = ctx.manifest.get("calendars", {}).get(cal_id)
    if cal is None:
        r.error("reference.missing", f"undeclared calendar {cal_id!r}", location=loc + "/calendar")
        return
    periods = _calendar_periods(cal)
    if "instant" in time:
        _check_time_point(ctx, {**time["instant"], "calendar": cal_id}, loc + "/instant", cal_id)
        return

    span = time["span"]
    keys = []
    for end in ("start", "end"):
        point = span[end]
        idx = 0
        if "period" in point:
            if point["period"] not in periods:
                r.error("reference.missing", f"calendar {cal_id!r} has no period {point['period']!r}", location=f"{loc}/span/{end}/period")
            else:
                idx = periods.index(point["period"])
        elif end == "end":
            idx = len(periods)
        keys.append((point["year"], idx))
    if keys[0] > keys[1]:
        r.error("time.span_order", "time span starts after it ends", location=loc + "/span")
    for j, pid in enumerate(time.get("select_periods", [])):
        if pid not in periods:
            r.error("reference.missing", f"calendar {cal_id!r} has no period {pid!r}", location=f"{loc}/select_periods/{j}")

    hierarchy = {"day": ["year", "period", "day"], "period": ["year", "period"], "year": ["year"], "span": []}
    dims: list[str] | None = None
    for k, step in enumerate(time["aggregation"]):
        sloc = f"{loc}/aggregation/{k}"
        over, within = step["over"], step.get("within")
        if (within == "period" or over == "periods") and not periods:
            r.error("time.no_periods", f"calendar {cal_id!r} declares no periods, so 'period' aggregation is undefined", location=sloc)
            return
        if over == "timesteps":
            if k != 0:
                r.error("time.aggregation_order", "a reduction over timesteps must be the first aggregation step", location=sloc)
                return
            dims = list(hierarchy[within])
        elif over == "days":
            if within == "day":
                r.error("time.aggregation_order", "'over days within day' is not meaningful", location=sloc)
                return
            if k != 0 and dims != hierarchy["day"]:
                r.error("time.aggregation_order", "'over days' must follow a step 'within day'", location=sloc)
                return
            dims = list(hierarchy[within])
        elif over == "periods":
            if dims is None or "period" not in dims or "day" in dims:
                r.error("time.aggregation_order", "'over periods' needs a previous step that produced one value per period", location=sloc)
                return
            dims.remove("period")
        elif over == "years":
            if dims is None or "year" not in dims or "day" in dims:
                r.error("time.aggregation_order", "'over years' needs a previous step that produced one value per year (or per period of each year)", location=sloc)
                return
            dims.remove("year")
    if dims:
        r.error(
            "time.aggregation_incomplete",
            f"aggregation leaves the {'/'.join(dims)} dimension(s) unreduced; add a final step such as "
            "{'statistic': 'mean', 'over': 'years'}, or use 'within': 'span' for a single-period value",
            location=loc + "/aggregation",
        )


def _check_quantity(ctx: Context, layer: dict, loc: str) -> None:
    r, reg = ctx.report, ctx.registry
    lid, kind, q = layer["id"], layer["kind"], layer["quantity"]
    quals = layer.get("qualifiers", {})

    if ":" in q:
        ns = q.split(":", 1)[0]
        if ns in RESERVED_NAMESPACES:
            r.error("quantity.reserved_namespace", f"namespace {ns!r} is reserved for future registry use", location=loc + "/quantity")
        if "definition" not in layer:
            r.error(
                "quantity.definition_missing",
                f"extension quantity {q!r} needs a 'definition' explaining what the values mean",
                location=loc,
            )
        if kind == "scalar" and layer["units"] not in reg.units:
            r.warning("units.unrecognised", f"units {layer['units']!r} are not in the registry unit table", location=loc + "/units")
        return

    entry = reg.quantity(q)
    if entry is None:
        r.error(
            "quantity.unknown",
            f"{q!r} is not a registry quantity; use a namespaced extension id such as 'mytool:{q}' with a definition",
            location=loc + "/quantity",
        )
        return
    if entry["kind"] != kind:
        r.error("quantity.kind_mismatch", f"quantity {q!r} must be a {entry['kind']} layer, not {kind}", location=loc + "/kind")
        return

    if kind == "scalar" and layer["units"] not in entry["units"]:
        r.error(
            "units.incompatible",
            f"layer {lid!r}: units {layer['units']!r} are not valid for {q!r} (allowed: {', '.join(entry['units'])})",
            location=loc + "/units",
        )

    core = {k: v for k, v in quals.items() if ":" not in k}
    for err in Draft202012Validator(entry["qualifiers"]).iter_errors(core):
        r.error("qualifiers.invalid", f"layer {lid!r} ({q}): {err.message}", location=loc + "/qualifiers" + pointer(*err.absolute_path))

    if "datum" in core and isinstance(core["datum"], str):
        datum = core["datum"]
        if datum != "sea_level" and datum not in ctx.manifest["world"].get("vertical_datums", {}):
            r.error("reference.missing", f"layer {lid!r} uses undeclared vertical datum {datum!r}", location=loc + "/qualifiers/datum")
    top, bottom = core.get("depth_top_m"), core.get("depth_bottom_m")
    if isinstance(top, (int, float)) and isinstance(bottom, (int, float)) and not bottom > top:
        r.error("qualifiers.invalid", f"layer {lid!r}: depth_bottom_m must be greater than depth_top_m", location=loc + "/qualifiers")

    steps = layer.get("time", {}).get("aggregation")
    if entry["temporal"] == "aggregated" and not steps:
        r.error(
            "semantics.time_required",
            f"{q!r} is defined over a period; declare time.span and time.aggregation (for example a sum over timesteps within year)",
            location=loc,
        )
    if entry["temporal"] == "snapshot" and steps:
        r.error("semantics.time_forbidden", f"{q!r} is a snapshot quantity and cannot carry an aggregation", location=loc + "/time")
    if steps:
        stats = [s["statistic"] for s in steps]
        if entry["accumulation"]:
            if stats[0] != "sum" or steps[0]["over"] not in ("timesteps", "days"):
                r.error(
                    "semantics.accumulation",
                    f"{q!r} is an accumulated amount: the first aggregation step must be a sum over timesteps or days "
                    "(for a mean rate use the corresponding *_rate quantity)",
                    location=loc + "/time/aggregation/0",
                )
            if "sum" in stats[1:]:
                r.error("semantics.accumulation", f"{q!r}: only the first aggregation step may be a sum", location=loc + "/time/aggregation")
        elif "sum" in stats:
            r.error(
                "semantics.accumulation",
                f"{q!r} is not an accumulated quantity and cannot be summed over time; use the matching *_amount quantity",
                location=loc + "/time/aggregation",
            )

    needs_validity = {
        "sea_floor_depth": "land samples must be invalid",
        "sea_surface_temperature": "land samples must be invalid",
    }
    if q == "elevation" and core.get("coverage") == "land_masked":
        needs_validity["elevation"] = "coverage 'land_masked' implies sub-sea-level samples are invalid"
    if q in needs_validity and "validity_mask" not in layer:
        r.warning("validity.expected", f"layer {lid!r} ({q}) has no validity mask, but {needs_validity[q]}", location=loc)


# ---------------------------------------------------------------- files


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(ctx: Context, path: str, loc: str) -> bytes | None:
    ctx.referenced.add(path)
    try:
        return ctx.source.read(path, ctx.limits.max_file_bytes)
    except PackageError as exc:
        ctx.report.error(exc.code, str(exc), location=loc, file=path)
        return None


def _check_hash(ctx: Context, data: bytes, declared: str, path: str, loc: str) -> None:
    actual = _sha256(data)
    if actual != declared:
        ctx.report.error(
            "hash.mismatch",
            f"SHA-256 of {path!r} is {actual}, but the manifest declares {declared}",
            location=loc,
            file=path,
        )


def _inspect(ctx: Context, data: bytes, path: str, loc: str) -> pngmod.PngInfo | None:
    try:
        info = pngmod.inspect_png(data)
    except pngmod.PngError as exc:
        ctx.report.error("png.invalid", f"{path!r} is not a valid PNG: {exc}", location=loc, file=path)
        return None
    if info.trailing_bytes:
        ctx.report.warning("png.trailing_data", f"{path!r} has {info.trailing_bytes} bytes after IEND", file=path)
    if any(info.has(c) for c in pngmod.ANIMATION_CHUNKS):
        ctx.report.error("png.animated", f"{path!r} is an animated PNG; only single images are allowed", file=path)
    return info


def _check_data_png(ctx: Context, info: pngmod.PngInfo, path: str, loc: str, bit_depth: int, what: str) -> bool:
    r = ctx.report
    ok = True
    if info.colour_type != 0 or info.bit_depth != bit_depth:
        r.error(
            "png.type",
            f"{what} {path!r} must be a {bit_depth}-bit greyscale PNG (colour type 0, bit depth {bit_depth}); found {info.describe()}",
            location=loc,
            file=path,
        )
        ok = False
    if info.has("tRNS"):
        r.error("png.transparency", f"{path!r} has a tRNS chunk; data layers express validity only through validity masks", file=path)
        ok = False
    cm = [c for c in pngmod.COLOUR_MANAGEMENT_CHUNKS if info.has(c)]
    if cm:
        r.warning(
            "png.colour_management",
            f"{path!r} contains colour-management chunks {cm}; consumers must ignore them and read raw samples, "
            "and producers should not write them to data layers",
            file=path,
        )
    if info.has("sBIT"):
        r.warning("png.sbit", f"{path!r} has an sBIT chunk; all {bit_depth} bits are significant for data layers and sBIT is ignored", file=path)
    if info.interlace:
        r.info("png.interlaced", f"{path!r} is Adam7-interlaced; allowed, but non-interlaced is recommended", file=path)
    return ok


def _grid_shape(ctx: Context, grid_id: str | None) -> tuple[int, int] | None:
    grid = ctx.manifest["grids"].get(grid_id) if grid_id else None
    if grid and grid.get("type") == "lonlat_regular":
        return grid["height"], grid["width"]
    return None


def _decode(ctx: Context, data: bytes, info: pngmod.PngInfo, path: str) -> np.ndarray | None:
    if info.width * info.height > ctx.limits.max_pixels:
        ctx.report.error(
            "limit.pixels",
            f"{path!r} has {info.width * info.height} pixels, above the {ctx.limits.max_pixels} limit; contents not checked",
            file=path,
        )
        return None
    try:
        return pngmod.decode_pixels(data)
    except pngmod.PngError as exc:
        ctx.report.error("png.invalid", f"{path!r}: {exc}", file=path)
        return None


def _load_validity(ctx: Context, layer: dict, loc: str, shape: tuple[int, int] | None) -> tuple[bool, np.ndarray | None]:
    """Returns (ok, mask). mask None with ok True means 'all valid'."""
    vm = layer.get("validity_mask")
    if vm is None:
        return True, None
    path = vm["path"]
    vloc = loc + "/validity_mask"
    if path not in ctx.validity_cache:
        data = _read(ctx, path, vloc)
        entry = {"data": data, "mask": None, "ok": False}
        ctx.validity_cache[path] = entry
        if data is not None:
            info = _inspect(ctx, data, path, vloc)
            if info is not None and _check_data_png(ctx, info, path, vloc, 8, "validity mask"):
                arr = _decode(ctx, data, info, path)
                if arr is not None:
                    bad = sorted(set(np.unique(arr).tolist()) - {0, 255})
                    if bad:
                        ctx.report.error(
                            "mask.values",
                            f"validity mask {path!r} contains values {bad[:10]}; only 0 (invalid) and 255 (valid) are allowed",
                            file=path,
                        )
                    else:
                        entry["mask"] = arr == 255
                        entry["ok"] = True
    entry = ctx.validity_cache[path]
    if entry["data"] is not None:
        _check_hash(ctx, entry["data"], vm["sha256"], path, vloc + "/sha256")
    if not entry["ok"]:
        return False, None
    mask = entry["mask"]
    if shape is not None and mask.shape != shape:
        ctx.report.error(
            "dimension.mismatch",
            f"validity mask {path!r} is {mask.shape[1]}x{mask.shape[0]} but layer {layer['id']!r} uses a {shape[1]}x{shape[0]} grid",
            location=vloc,
            file=path,
        )
        return False, None
    return True, mask


def check_files(ctx: Context) -> None:
    for i, layer in enumerate(ctx.manifest["layers"]):
        loc = pointer("layers", i)
        path = layer["path"]
        data = _read(ctx, path, loc + "/path")
        if data is None:
            continue
        _check_hash(ctx, data, layer["sha256"], path, loc + "/sha256")
        kind = layer["kind"]
        if kind not in DATA_KINDS and kind != "reference":
            continue
        info = _inspect(ctx, data, path, loc + "/path")
        if info is None:
            continue
        shape = _grid_shape(ctx, layer.get("grid"))
        if shape is not None and (info.height, info.width) != shape:
            ctx.report.error(
                "dimension.mismatch",
                f"{path!r} is {info.width}x{info.height} pixels but grid {layer['grid']!r} is {shape[1]}x{shape[0]}",
                location=loc,
                file=path,
            )
            continue
        if kind == "reference":
            if info.width * info.height <= ctx.limits.max_pixels:
                _decode(ctx, data, info, path)
            continue

        depth = 8 if kind == "mask" else 16
        if not _check_data_png(ctx, info, path, loc, depth, f"{kind} layer"):
            continue
        arr = _decode(ctx, data, info, path)
        if arr is None:
            continue
        ok, valid = _load_validity(ctx, layer, loc, shape or arr.shape)
        if not ok:
            continue
        valid_count = int(arr.size if valid is None else valid.sum())
        if valid_count == 0:
            ctx.report.info("layer.all_invalid", f"layer {layer['id']!r} has no valid samples", location=loc)

        if kind == "mask":
            bad = sorted(set(np.unique(arr).tolist()) - {0, 255})
            if bad:
                ctx.report.error(
                    "mask.values",
                    f"binary mask {path!r} contains values {bad[:10]}; only 0 (false) and 255 (true) are allowed",
                    location=loc,
                    file=path,
                )
        elif kind == "categorical":
            _check_codes(ctx, layer, loc, arr, valid)
        elif kind == "scalar":
            _check_scalar_values(ctx, layer, loc, arr, valid)


def _check_codes(ctx: Context, layer: dict, loc: str, arr: np.ndarray, valid: np.ndarray | None) -> None:
    table = ctx.manifest.get("class_tables", {}).get(layer["class_table"])
    if table is None:
        return
    known = {c["code"] for c in table["classes"]}
    present = arr if valid is None else arr[valid]
    codes, counts = np.unique(present, return_counts=True)
    unknown = [(int(c), int(n)) for c, n in zip(codes, counts) if int(c) not in known]
    if unknown:
        listed = ", ".join(f"{c} ({n} samples)" for c, n in unknown[:10])
        ctx.report.error(
            "class.unknown_code",
            f"layer {layer['id']!r} uses class codes not in table {layer['class_table']!r}: {listed}",
            location=loc,
            file=layer["path"],
        )


def _check_scalar_values(ctx: Context, layer: dict, loc: str, arr: np.ndarray, valid: np.ndarray | None) -> None:
    enc = layer["encoding"]
    try:
        decoded = scalarmod.decode(arr, enc["min"], enc["max"])
    except (scalarmod.EncodingRangeError, ValueError):
        return
    half = scalarmod.quantization_step(enc["min"], enc["max"]) / 2
    observed = scalarmod.statistics(decoded, valid)
    declared = layer.get("statistics")
    r = ctx.report
    if declared:
        if "valid_count" in declared and declared["valid_count"] != observed["valid_count"]:
            r.error(
                "statistics.inconsistent",
                f"layer {layer['id']!r}: statistics.valid_count is {declared['valid_count']} but {observed['valid_count']} samples are valid",
                location=loc + "/statistics/valid_count",
            )
        for key in ("minimum", "maximum", "mean"):
            if key not in declared:
                continue
            if observed["valid_count"] == 0:
                r.error("statistics.inconsistent", f"layer {layer['id']!r}: statistics.{key} given but no sample is valid", location=loc + "/statistics")
                continue
            tol = half + 1e-9 * max(1.0, abs(declared[key]))
            if abs(declared[key] - observed[key]) > tol:
                r.error(
                    "statistics.inconsistent",
                    f"layer {layer['id']!r}: statistics.{key} is {declared[key]} but the decoded data give {observed[key]:.6g} "
                    f"(tolerance {tol:.3g})",
                    location=loc + "/statistics/" + key,
                )
    q = ctx.registry.quantity(layer["quantity"])
    if q and q["kind"] == "scalar" and observed["valid_count"] and layer["units"] in q["units"]:
        lo, hi = q["valid_range"]
        unit = layer["units"]
        for bound, value, cmp in (("minimum", lo, lambda v, b: v < b), ("maximum", hi, lambda v, b: v > b)):
            if value is None:
                continue
            limit = ctx.registry.from_canonical(value, unit)
            obs = observed[bound]
            tol = half + 1e-9 * max(1.0, abs(limit))
            if cmp(obs, limit - tol if bound == "minimum" else limit + tol):
                r.error(
                    "value.out_of_range",
                    f"layer {layer['id']!r}: valid samples reach {obs:.6g} {unit}, outside the physical range of {layer['quantity']!r}",
                    location=loc,
                    file=layer["path"],
                )


def check_sidecars(ctx: Context) -> None:
    m = ctx.manifest
    for i, layer in enumerate(m["layers"]):
        spath = layer["path"] + SIDECAR_SUFFIX
        if not ctx.source.exists(spath):
            continue
        loc = pointer("layers", i)
        data = _read(ctx, spath, loc)
        if data is None:
            continue
        try:
            sidecar = loads_strict(data)
        except StrictJSONError as exc:
            ctx.report.error("sidecar.invalid", f"{spath!r}: {exc}", file=spath)
            continue
        errs = schema_errors(sidecar, "sidecar.schema.json")
        for sloc, msg in errs:
            ctx.report.error("sidecar.invalid", msg, location=sloc, file=spath)
        if errs:
            continue
        if sidecar["layer"] != layer:
            ctx.report.error("sidecar.mismatch", f"{spath!r} layer definition differs from the manifest (manifest is authoritative)", location=loc, file=spath)
        grid = m["grids"].get(layer.get("grid")) if layer.get("grid") else None
        if sidecar.get("grid") != grid:
            ctx.report.error("sidecar.mismatch", f"{spath!r} grid differs from the manifest", location=loc, file=spath)
        table = m.get("class_tables", {}).get(layer.get("class_table")) if layer.get("class_table") else None
        if sidecar.get("class_table") != table:
            ctx.report.error("sidecar.mismatch", f"{spath!r} class table differs from the manifest", location=loc, file=spath)
        if sidecar["format_version"] != m["format_version"]:
            ctx.report.error("sidecar.mismatch", f"{spath!r} format_version differs from the manifest", file=spath)


def check_unreferenced(ctx: Context) -> None:
    referenced = set(ctx.referenced) | {MANIFEST_NAME}
    for name in ctx.source.files():
        if name in referenced:
            continue
        if "/" not in name and ROOT_DOC.match(name):
            continue
        ctx.report.warning("package.unreferenced_file", f"{name!r} is not referenced by the manifest", file=name)
