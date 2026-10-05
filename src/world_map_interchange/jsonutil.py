from __future__ import annotations

import functools
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .resources import load_schema

SCHEMA_NAMES = (
    "manifest.schema.json",
    "sidecar.schema.json",
    "registry.schema.json",
    "capabilities.schema.json",
    "validation-report.schema.json",
)


class StrictJSONError(ValueError):
    pass


def loads_strict(data: bytes):
    """Parse UTF-8 JSON, rejecting BOMs, duplicate keys and NaN/Infinity."""
    if data.startswith(b"\xef\xbb\xbf"):
        raise StrictJSONError("file starts with a UTF-8 byte-order mark; write UTF-8 without BOM")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StrictJSONError(f"file is not valid UTF-8: {exc}") from exc

    def pairs_hook(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise StrictJSONError(f"duplicate object key {key!r}")
            obj[key] = value
        return obj

    def reject_constant(name):
        raise StrictJSONError(f"non-standard JSON constant {name} is not allowed")

    try:
        return json.loads(text, object_pairs_hook=pairs_hook, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise StrictJSONError(f"invalid JSON: {exc}") from exc


def pointer(*parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


@functools.lru_cache(maxsize=None)
def _ref_registry() -> Registry:
    resources = []
    for name in SCHEMA_NAMES:
        schema = load_schema(name)
        resources.append((schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


@functools.lru_cache(maxsize=None)
def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name), registry=_ref_registry())


def schema_errors(instance, name: str) -> list[tuple[str, str]]:
    """Return (json_pointer, message) pairs, most specific first."""
    out = []
    for err in sorted(validator(name).iter_errors(instance), key=lambda e: (list(map(str, e.absolute_path)), e.message)):
        msg = err.message
        if err.validator is False or msg.startswith("False schema"):
            prop = err.absolute_path[-1] if err.absolute_path else "value"
            msg = f"property {prop!r} is not allowed here"
        if len(msg) > 300:
            msg = msg[:297] + "..."
        out.append((pointer(*err.absolute_path), msg))
    return out
