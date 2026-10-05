"""Render registry/0.1.0/quantities.json to spec/0.1.0/quantity-registry.md.

    uv run python scripts/render_registry.py          # write
    uv run python scripts/render_registry.py --check  # fail if the committed file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "registry" / "0.1.0" / "quantities.json"
TARGET = ROOT / "spec" / "0.1.0" / "quantity-registry.md"

TEMPORAL = {
    "snapshot": "Snapshot: state at one time. Aggregation is not allowed.",
    "aggregated": "Aggregated: `time.span` and `time.aggregation` are required.",
    "any": "Any: either a snapshot or an aggregation.",
}


def qualifier_rows(schema: dict) -> list[str]:
    required = set(schema.get("required", []))
    rows = []
    for name, spec in schema.get("properties", {}).items():
        if "enum" in spec:
            kind = " \\| ".join(f"`{v}`" for v in spec["enum"])
        else:
            kind = spec.get("type", "any")
            if "minimum" in spec:
                kind += f" >= {spec['minimum']}"
            if "exclusiveMinimum" in spec:
                kind += f" > {spec['exclusiveMinimum']}"
        rows.append(f"| `{name}` | {'**required**' if name in required else 'optional'} | {kind} | {spec.get('description', '')} |")
    return rows


def render() -> str:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    out = [
        "# Quantity registry (experimental draft 0.1.0)",
        "",
        "<!-- Generated from registry/0.1.0/quantities.json by scripts/render_registry.py. Do not edit by hand. -->",
        "",
        "The machine-readable source of truth is [`registry/0.1.0/quantities.json`](../../registry/0.1.0/quantities.json).",
        "This page is generated from it.",
        "",
    ]
    out += [f"- {note}" for note in data["notes"]]
    out += ["", "## Contents", ""]
    for name, q in data["quantities"].items():
        out.append(f"- [`{name}`](#{name.replace('_', '_')}): {q['title']} ({q['kind']})")
    out += ["", "## Units", "", "| unit | dimension | to canonical | description |", "|---|---|---|---|"]
    for unit, u in data["units"].items():
        conv = f"x {u['scale']:g}" + (f" + {u['offset']:g}" if u["offset"] else "")
        out.append(f"| `{unit}` | {u['dimension']} | {conv} | {u['description']} |")
    out.append("")
    for name, q in data["quantities"].items():
        out += [f"## {name}", "", f"**{q['title']}**: {q['kind']} layer.", "", q["definition"], ""]
        if q["kind"] == "scalar":
            out.append(f"- Units: {', '.join(f'`{u}`' for u in q['units'])} (canonical `{q['canonical_unit']}`)")
            lo, hi = q["valid_range"]
            if lo is not None or hi is not None:
                out.append(f"- Physically valid range (canonical units): {lo if lo is not None else '-inf'} to {hi if hi is not None else '+inf'}")
        if "positive" in q:
            out.append(f"- Positive direction: {q['positive']}")
        out.append(f"- Temporal semantics: {TEMPORAL[q['temporal']]}")
        if q["accumulation"]:
            out.append("- Accumulated amount: the first aggregation step must be a `sum` over timesteps or days, and no later step may be a sum.")
        elif q["kind"] == "scalar":
            out.append("- Not an accumulation: `sum` is not allowed in its aggregation.")
        if q.get("vertical_reference"):
            out.append(f"- Vertical reference: {q['vertical_reference']}")
        rel = q.get("related", {})
        if rel.get("cf_standard_name"):
            note = f" ({rel['note']})" if rel.get("note") else ""
            out.append(f"- Related CF standard name (informative): `{rel['cf_standard_name']}`{note}")
        rows = qualifier_rows(q["qualifiers"])
        if rows:
            out += ["", "| qualifier | status | values | meaning |", "|---|---|---|---|", *rows]
        else:
            out += ["", "No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed."]
        if "then" in q["qualifiers"]:
            out += ["", "Conditional rule: `clamp_value` is required when `coverage` is `land_clamped`."]
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            print(f"{TARGET.relative_to(ROOT)} is stale; run: uv run python scripts/render_registry.py")
            return 1
        print("Quantity registry page is up to date.")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
