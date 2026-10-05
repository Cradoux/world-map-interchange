# Compatibility and versioning policy

## Format versions

`format_version` uses semantic versioning, `MAJOR.MINOR.PATCH`.

| Change | 0.x (experimental) | 1.0 and later |
|---|---|---|
| PATCH (0.1.0 to 0.1.1) | Clarifications, new examples, bug fixes in schemas that bring them in line with the text. Packages valid before remain valid. | Same |
| MINOR (0.1 to 0.2) | **May be incompatible.** Fields may be renamed or removed, and rules may tighten. | Backwards-compatible additions only: new optional fields, quantities or layer kinds. Old packages remain valid. |
| MAJOR | Not used before 1.0 | Incompatible changes |

Consumers MUST reject a `format_version` whose major.minor they do not implement during 0.x, rather than guess. From 1.0,
consumers SHOULD accept newer minor versions and report unknown optional content as unsupported or retained.

## Registry

- Registry quantity ids, once published in a tagged version, are never reused with a different meaning.
- Before 1.0, quantities may be renamed or split. The changelog records the mapping.
- From 1.0, quantities may be deprecated but not removed or redefined.
- Adding units or optional qualifiers is a compatible change. Making a qualifier required is not.

## Schemas and reference tools

- Schemas live under `schemas/<format_version>/` and are immutable after a version is tagged. Fixes go into a new patch
  version.
- The reference Python package's version matches the newest format version it implements. Its CLI flags and JSON report
  fields follow the same rules as the format: they may change in 0.x, and only additively after 1.0.
- `report_version` in the JSON validation report identifies the report schema.

## Extensions

Namespaced content (`namespace:name`) is outside these guarantees. Each namespace owner is responsible for their own
compatibility. A namespaced feature adopted into the standard gets a new, unnamespaced id. The namespaced form stays
valid as an extension.
