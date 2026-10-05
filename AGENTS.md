# AGENTS.md

Instructions for AI coding agents. Humans are welcome to read this too. It is a compact, rule-first version of the
documentation, written for agents that either **work on this repository** or **integrate WMI into another codebase**.

World Map Interchange (WMI) is an **experimental 0.1.0 draft** format for exchanging georeferenced world maps
(elevation, climate, classes, masks) between worldbuilding and terrain tools. It is under the MIT licence. It is
a proposal for joint development, **not an established or endorsed standard**. Never describe any tool or developer
as endorsing or implementing it unless their developer has said so publicly.

## Where things are

| Need | File |
|---|---|
| Normative rules | `spec/0.1.0/specification.md` (Appendix B lists validator issue codes) |
| Quantities, units, qualifiers | `registry/0.1.0/quantities.json` (human-readable: `spec/0.1.0/quantity-registry.md`, generated) |
| JSON Schemas (2020-12) | `schemas/0.1.0/*.schema.json` |
| How to add WMI to an existing tool | `docs/integration-guide.md`: **follow it step by step** |
| Producer and consumer rules explained | `docs/producer-guide.md`, `docs/consumer-guide.md` |
| Unresolved choices, deferred features | `docs/open-decisions.md`, `docs/proposals/` |
| Reference implementation | `src/world_map_interchange/` (`validate.py`, `bundle.py`, `scalar.py`, `png.py`, `package.py`) |
| Test fixtures | `examples/valid/`, `examples/expected/*.json`, `examples/invalid/` + `expectations.json`, `examples/packed/` |
| Working exporter example | `examples/code/write_climate_package.py` |

## Facts you must get right

These are the details implementations most often get wrong. The specification is authoritative.

- Package: ZIP or folder; `manifest.json` at the root; data in `maps/`, validity in `masks/`, pictures in `previews/`.
  Relative `/` paths only.
- No quantity is mandatory. At least one non-reference layer is required.
- **Scalar** layers are PNG greyscale 16-bit. `value = min + p / 65535 * (max - min)` (exactly `max` at 65535).
  Encoding: `p = floor((v - min) / (max - min) * 65535 + 0.5)`. Out-of-range values are an error; never clip.
  `min < max` always, even for constant fields.
- **Categorical** layers are PNG greyscale 16-bit class codes, explained by `class_tables`. Code 0 is a real class.
  Never interpolate codes.
- **Mask** layers are PNG greyscale 8-bit; 255 = true and 0 = false; other values are invalid.
- **Validity masks** are PNG greyscale 8-bit in `masks/`; 255 = valid and 0 = invalid; absent means all valid. Never use a
  sentinel value for missing data. Pixel 0 is a real value.
- Data PNGs have no `tRNS` and no animation. Ignore `gAMA`/`sRGB`/`iCCP`/`cHRM`/`sBIT`, and never apply colour transforms.
  16-bit samples are big-endian.
- Grid `lonlat_regular`: bounds are **pixel edges**; row 0 = north; no duplicated seam column; `east - west == 360`
  wraps; `east > 180` crosses the antimeridian. Pixel centre:
  `lon = west + (c + 0.5) * (east - west) / width`, `lat = north - (r + 0.5) * (north - south) / height`.
- `world.body.radius_m` may be `null` (unknown). **Never default to Earth's radius.**
- Elevation needs qualifiers `datum` and `coverage`. Air temperature needs `elevation_reference`. Soil moisture needs
  depths and `frozen_water`. Precipitation **amounts** use aggregation starting with `sum`; **rates** use `*_rate`
  quantities.
- Time statistics are ordered aggregation steps `{statistic, over, within}` on a declared calendar. Fictional calendars
  (`kind: fixed`) may have unequal periods and non-86 400 s days.
- Unregistered quantities must be namespaced (`tool:name`) with a `definition`. The `wmi:` namespace is reserved.
- Consumers report each layer as `supported`, `retained` or `unsupported`, **separately** from conformance. A
  climate-only package is valid even if a workflow needs elevation.
- Every referenced file has a SHA-256 (lowercase hex). Manifest JSON is strict: no BOM, no duplicate keys, no NaN.
- `format_version` 0.1.x only. Reject other 0.x minor versions.

## Task A: integrating WMI into another codebase

Follow `docs/integration-guide.md` in order. In summary:

1. **Investigate before writing code.** Find where the target tool stores each map, its array layout (row order,
   longitude origin, seam column, centre or edge bounds), units, missing-data sentinels, calendar and statistics.
   Cite file paths and line numbers.
2. **Produce the inventory table** (guide section 3) and the **geometry mapping** (section 4). **Stop and ask the human to
   confirm them.** They encode scientific meaning that you can't verify alone.
3. **Ask; don't guess.** Ask about anything uncertain: radius, terrain or sea-level temperature, whether "precipitation"
   includes snow, which statistic a field holds, what a calendar period means, and the package licence to offer users.
   An honest `null`, a namespaced extension or "unsupported" is always better than a plausible guess.
4. **Choose the path** (Python library, CLI subprocess, native, or native plus `wmi validate` in CI) with the human. Pin
   the reference package to a commit:
   `pip install "world-map-interchange @ git+https://github.com/Cradoux/world-map-interchange@<sha>"`.
5. **Implement in an isolated module**, behind a `format_version` check. Don't restructure unrelated code.
6. **Test with the shared fixtures**: readers must match every sample in `examples/expected/*.json` and refuse every
   case in `examples/invalid/`. Writers must pass `wmi validate --strict` on real exports. Treat the hostile archives in
   `examples/invalid/*.zip` as untrusted: never extract them with a generic tool.
7. **Report**: files changed, the inventory table, test results, open questions, and anything marked unsupported or
   retained.

Licensing: implementing the format needs no permission. If you copy code, schemas or the registry into the target
project, keep the MIT notice (for example in a third-party notices file). A package's own `package.license` is the data
licence. Don't hard-code `MIT` for users' worlds.

Don't add the target tool to this repository's documentation, and don't open issues or pull requests here on the human's
behalf, unless they ask you to.

## Task B: working on this repository

Setup and checks (all must pass before you finish):

```bash
uv sync --locked
uv run pytest -q
uv run python scripts/generate_examples.py --check
uv run python scripts/render_registry.py --check
```

Rules:

- **Keep these in agreement in the same change**: specification text, schemas, registry, validator, examples, and
  `CHANGELOG.md`. See [CONTRIBUTING.md](CONTRIBUTING.md).
- **Generated files are never edited by hand.** Edit `scripts/generate_examples.py` and run it to change anything in
  `examples/valid`, `examples/invalid`, `examples/expected`, `examples/packed` or `examples/EXPECTED.md`. Edit
  `registry/0.1.0/quantities.json` and run `scripts/render_registry.py` to change `spec/0.1.0/quantity-registry.md`.
- Each invalid example must fail for **exactly one** reason, recorded in `examples/invalid/expectations.json`.
- New validator checks need an issue code (listed in spec Appendix B), a test, and preferably an invalid example.
- Mark unagreed material **[Proposal]** and list it in `docs/open-decisions.md`. Don't present provisional choices as
  settled.
- Dependencies stay minimal (`numpy`, `pillow`, `jsonschema`). Python 3.10+ compatibility is required. CI runs Linux
  and Windows on 3.10 to 3.13.
- Content must stay synthetic and redistributable: no real or private world data, proprietary code, credentials, local
  paths or third-party assets.
- Governance: don't appoint maintainers, grant access, invite people or contact developers on anyone's behalf.
