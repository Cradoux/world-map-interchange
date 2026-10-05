"""Human-oriented package summaries (``wmi inspect``)."""

from __future__ import annotations

from . import geometry
from . import scalar as scalarmod
from .bundle import Bundle
from .package import Limits
from .validate import validate


def _time_summary(time: dict | None) -> str | None:
    if not time:
        return None
    if "instant" in time:
        inst = time["instant"]
        return f"instant year {inst['year']}" + (f" period {inst['period']}" if "period" in inst else "")
    s, e = time["span"]["start"], time["span"]["end"]
    span = f"{s['year']}{'/' + s['period'] if 'period' in s else ''}..{e['year']}{'/' + e['period'] if 'period' in e else ''}"
    steps = ", then ".join(
        f"{st['statistic']} over {st['over']}" + (f" within {st['within']}" if "within" in st else "") for st in time["aggregation"]
    )
    selected = f", periods {'+'.join(time['select_periods'])} only" if time.get("select_periods") else ""
    return f"{steps} [{span}{selected}, calendar {time['calendar']}]"


def summarize(target, *, limits: Limits | None = None, capabilities: dict | None = None) -> dict:
    report = validate(target, limits=limits, capabilities=capabilities)
    summary: dict = {"validation": report.to_dict()}
    if report.checks.get("schema") != "passed":
        return summary
    with Bundle(target, limits) as bundle:
        m = bundle.manifest
    world = m["world"]
    summary["package"] = m["package"]
    summary["world"] = {
        "id": world["id"],
        "name": world.get("name"),
        "radius_m": world["body"]["radius_m"],
        "radius_note": None if world["body"]["radius_m"] is not None else "unknown - do not assume Earth's radius",
        "vertical_datums": world.get("vertical_datums", {}),
    }
    summary["source"] = m.get("source")
    grids = {}
    for gid, g in m["grids"].items():
        if g["type"] != "lonlat_regular":
            grids[gid] = {"type": g["type"], "note": "extension geometry; not interpreted"}
            continue
        dlon, dlat = geometry.pixel_size(g)
        grids[gid] = {
            "type": g["type"],
            "size": f"{g['width']}x{g['height']}",
            "bounds": g["bounds"],
            "pixel_deg": [dlon, dlat],
            "wraps_longitude": geometry.wraps(g),
            "crosses_antimeridian": geometry.crosses_antimeridian(g),
            "first_centre_lat_lon": geometry.pixel_centre(g, 0, 0),
            "aligned_with": sorted(o for o, og in m["grids"].items() if o != gid and geometry.aligned(g, og)),
        }
    summary["grids"] = grids
    status = {s.id: s for s in report.layers}
    layers = []
    for layer in m["layers"]:
        entry = {
            "id": layer["id"],
            "kind": layer["kind"],
            "quantity": layer.get("quantity"),
            "grid": layer.get("grid"),
            "path": layer["path"],
            "support": status[layer["id"]].status if layer["id"] in status else None,
        }
        if layer["kind"] == "scalar":
            enc = layer["encoding"]
            entry["units"] = layer["units"]
            entry["encoding_range"] = [enc["min"], enc["max"]]
            try:
                entry["quantization_step"] = scalarmod.quantization_step(enc["min"], enc["max"])
            except scalarmod.EncodingRangeError:
                pass
            q = layer.get("qualifiers", {})
            if layer.get("quantity") == "elevation":
                datum = q.get("datum")
                sea = 0.0 if datum == "sea_level" else world.get("vertical_datums", {}).get(datum, {}).get("sea_level_m")
                sea_layer_units = None if sea is None else (sea / 1000.0 if layer["units"] == "km" else sea)
                if sea_layer_units is not None and enc["min"] <= sea_layer_units <= enc["max"]:
                    pixel = int(scalarmod.encode([sea_layer_units], enc["min"], enc["max"])[0])
                    entry["sea_level"] = {"value_m": sea, "derived_pixel": pixel, "note": "derived from the decode contract; informative only"}
        if layer["kind"] == "categorical":
            entry["class_table"] = layer["class_table"]
        if layer.get("qualifiers"):
            entry["qualifiers"] = layer["qualifiers"]
        t = _time_summary(layer.get("time"))
        if t:
            entry["time"] = t
        if layer["kind"] == "reference":
            entry["role"] = layer["role"]
            entry["registration"] = layer["registration"]
        entry["validity_mask"] = layer.get("validity_mask", {}).get("path")
        layers.append(entry)
    summary["layers"] = layers
    return summary


def render(summary: dict) -> str:
    lines = []
    v = summary["validation"]
    if "package" in summary:
        p, w = summary["package"], summary["world"]
        lines.append(f"Package  {p.get('title', p['id'])}")
        lines.append(f"  id {p['id']}; created {p['created']}; producer {p['producer']['name']} {p['producer']['version']}; license {p['license']}")
        radius = f"{w['radius_m']:.0f} m" if w["radius_m"] is not None else "unknown (do not assume Earth)"
        lines.append(f"World    {w.get('name') or w['id']} (id {w['id']}); sphere radius {radius}")
        src = summary.get("source") or {}
        if src:
            lines.append("Source   " + "; ".join(f"{k} {v2}" for k, v2 in src.items() if not isinstance(v2, dict)))
        lines.append("Grids")
        for gid, g in summary["grids"].items():
            if "size" not in g:
                lines.append(f"  {gid}: {g['type']} ({g['note']})")
                continue
            b = g["bounds"]
            flags = []
            if g["wraps_longitude"]:
                flags.append("wraps in longitude")
            if g["crosses_antimeridian"]:
                flags.append("crosses the antimeridian")
            if g["aligned_with"]:
                flags.append("aligned with " + ", ".join(g["aligned_with"]))
            lines.append(
                f"  {gid}: {g['size']} lon {b['west']}..{b['east']} lat {b['north']}..{b['south']} "
                f"({g['pixel_deg'][0]:.4g} x {g['pixel_deg'][1]:.4g} deg){'; ' + '; '.join(flags) if flags else ''}"
            )
        lines.append("Layers")
        for layer in summary["layers"]:
            head = f"  [{layer['support'] or '?':11}] {layer['id']}: {layer['kind']}"
            if layer.get("quantity"):
                head += f" {layer['quantity']}"
            if "units" in layer:
                head += f" [{layer['units']}] range {layer['encoding_range'][0]}..{layer['encoding_range'][1]} step {layer['quantization_step']:.3g}"
            if layer["kind"] == "reference":
                head += f" ({layer['role']}, {layer['registration']})"
            lines.append(head)
            if layer.get("time"):
                lines.append(f"      time: {layer['time']}")
            if layer.get("qualifiers"):
                lines.append("      qualifiers: " + ", ".join(f"{k}={val}" for k, val in layer["qualifiers"].items()))
            if layer.get("sea_level"):
                s = layer["sea_level"]
                lines.append(f"      sea level {s['value_m']} m -> pixel {s['derived_pixel']} (derived)")
            if layer.get("validity_mask"):
                lines.append(f"      validity: {layer['validity_mask']}")
    lines.append(f"Conformant: {'yes' if v['conformant'] else 'NO'} ({v['error_count']} errors, {v['warning_count']} warnings)")
    return "\n".join(lines)
