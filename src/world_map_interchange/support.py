"""Consumer support assessment, kept separate from package conformance."""

from __future__ import annotations

from .constants import CORE_KINDS
from .report import LayerSupport

GENERIC_CAPABILITIES = {
    "consumer": {"name": "WMI reference tools (generic profile)"},
    "kinds": list(CORE_KINDS),
    "grid_types": ["lonlat_regular"],
    "quantities": "registry",
    "retain_unrecognised": True,
    "required_quantities": [],
}


def assess(manifest: dict, registry, capabilities: dict | None = None) -> tuple[list[LayerSupport], dict]:
    caps = capabilities or GENERIC_CAPABILITIES
    kinds = set(caps.get("kinds", []))
    grid_types = set(caps.get("grid_types", []))
    quantities = caps.get("quantities", [])
    known = set(registry.quantities) if quantities == "registry" else set(quantities)
    retain = bool(caps.get("retain_unrecognised", False))
    grids = manifest.get("grids", {})

    results: list[LayerSupport] = []
    for layer in manifest.get("layers", []):
        kind = layer.get("kind", "?")
        quantity = layer.get("quantity")
        hard: list[str] = []
        soft: list[str] = []
        if kind not in kinds:
            hard.append(f"layer kind {kind!r} is not supported by this consumer")
        grid_id = layer.get("grid")
        if grid_id is not None:
            grid = grids.get(grid_id)
            gtype = grid.get("type") if isinstance(grid, dict) else None
            if gtype not in grid_types:
                hard.append(f"grid type {gtype!r} is not supported; geometry will not be guessed")
        if kind != "reference" and quantity is not None and quantity not in known:
            if ":" in quantity:
                soft.append(f"extension quantity {quantity!r} is not interpreted by this consumer")
            else:
                soft.append(f"quantity {quantity!r} is not interpreted by this consumer")
        if hard:
            status, reasons = "unsupported", hard + soft
        elif soft:
            status, reasons = ("retained", soft) if retain else ("unsupported", soft)
        else:
            status, reasons = "supported", []
        results.append(LayerSupport(layer.get("id", "?"), kind, quantity, status, reasons))

    supported_quantities = {r.quantity for r in results if r.status == "supported"}
    missing = [q for q in caps.get("required_quantities", []) if q not in supported_quantities]
    consumer = {
        "name": caps.get("consumer", {}).get("name", "unnamed consumer"),
        "required_quantities_missing": missing,
        "requirements_met": not missing,
    }
    return results, consumer
