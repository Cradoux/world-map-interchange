# Integration guide: adding WMI to existing software

This guide is for developers, and for coding agents working on their behalf, who want an existing application to
**export** World Map Interchange (WMI) packages, **import** them, or both. It is a step-by-step procedure with decision
points, code, tests and a definition of done. It is informative: where it disagrees with the
[specification](../spec/0.1.0/specification.md), the specification wins. Please report the disagreement as an
[ambiguity](https://github.com/Cradoux/world-map-interchange/issues/new?template=ambiguity.yml).

The [producer guide](producer-guide.md) and [consumer guide](consumer-guide.md) explain the rules in depth. This guide
tells you in what order to apply them inside an existing codebase. Coding agents should also read [AGENTS.md](../AGENTS.md).

> **Status.** WMI 0.1.0 is an experimental draft. Minor versions before 1.0 may be incompatible
> ([COMPATIBILITY.md](../COMPATIBILITY.md)). Keep your integration behind a version check, pin the version you
> implement, and expect to update it.

## Contents

1. [Licensing for adopters](#1-licensing-for-adopters)
2. [Choose an integration path](#2-choose-an-integration-path)
3. [Inventory your maps](#3-inventory-your-maps)
4. [Map your geometry](#4-map-your-geometry)
5. [Implement export](#5-implement-export)
6. [Implement import](#6-implement-import)
7. [Round trips and preservation](#7-round-trips-and-preservation)
8. [Test against the shared examples](#8-test-against-the-shared-examples)
9. [Native implementation notes](#9-native-implementation-notes-any-language)
10. [Definition of done](#10-definition-of-done)
11. [Keeping up with the draft](#11-keeping-up-with-the-draft)
12. [Handing this task to a coding agent](#12-handing-this-task-to-a-coding-agent)

---

## 1. Licensing for adopters

- **Implementing the format needs no permission.** You may read and write WMI packages in any software, open or closed
  source, commercial or not.
- **Everything in this repository is under the [MIT licence](../LICENSE):** the specification, schemas, registry,
  reference code, tests and synthetic examples. You may copy, modify and ship any of it, including inside proprietary
  products. If you copy substantial parts (for example the Python package, or the schema and registry files bundled
  into your installer), keep the copyright and licence notice with them, for example in your third-party notices file.
- **Packages carry their own licence.** `package.license` is an SPDX expression chosen by whoever produced the package.
  It governs the map data, not your software. When exporting, let the user choose the licence, or fill it in from your
  tool's terms for generated content. Don't silently write `MIT` for user worlds.
- **No endorsement is implied** in either direction. Implementing WMI doesn't make you a participant in its development,
  and the repository doesn't list tools as supporters without their developer's agreement.

## 2. Choose an integration path

| Path | When it fits | What you need |
|---|---|---|
| **A. Python library** | Your tool is Python, or has a Python build or pipeline step | `pip`/`uv` dependency on the reference package (numpy, pillow, jsonschema) |
| **B. CLI as a subprocess** | Any language; a Python runtime is acceptable on the user's machine or in your pipeline | `wmi` on `PATH`; parse `--json` reports; exchange `.npy`/`.csv` arrays |
| **C. Native implementation** | Engines, desktop apps, web apps, or anything that can't ship Python | ZIP reader/writer, PNG codec with true 16-bit greyscale, strict JSON parser, SHA-256 |
| **D. Native + reference validator in CI** | Recommended for C | Your native code ships; `wmi validate` checks its output in your test suite |

For most tools that can't embed Python, **D** is the best choice: write a small native reader and writer, and use the
reference validator only in tests and CI.

### Installing the reference package

There is no PyPI release yet. Install from Git and **pin a commit** (or a tag once one exists), so an upstream change to
the draft can't silently change your behaviour:

```bash
# pip
pip install "world-map-interchange @ git+https://github.com/Cradoux/world-map-interchange@<commit-sha>"

# uv (adds it to pyproject.toml and uv.lock)
uv add "world-map-interchange @ git+https://github.com/Cradoux/world-map-interchange@<commit-sha>"
```

Check the installation with `wmi --version` (it prints `wmi 0.1.0 (format draft 0.1.0)`). The schemas and the registry
are bundled inside the package. No repository checkout is needed at run time.

### Public Python API (0.1.0)

| Import | Purpose |
|---|---|
| `world_map_interchange.validate(path, *, limits=None, capabilities=None) -> Report` | Validate a folder or ZIP. `capabilities` is a profile dict (see `examples/profiles/`) |
| `Report.conformant`, `.errors`, `.warnings`, `.layers`, `.to_dict()` | Results. `.layers` holds per-layer support (`supported`, `retained` or `unsupported`) |
| `world_map_interchange.bundle.Bundle(path)` | Read a package: `.manifest`, `.layer(id)`, `.grid(id)`, `.read(id) -> (values, valid)` |
| `world_map_interchange.encode(values, min, max, valid=None)` / `decode(pixels, min, max)` | Scalar encoding (raises `EncodingRangeError` instead of clipping) |
| `world_map_interchange.choose_range(values, valid=None)` | A safe range when you have no fixed shared range |
| `world_map_interchange.png.write_png(array, bit_depth)` | Minimal PNG (greyscale, no ancillary chunks) |
| `world_map_interchange.bundle.rehash(dir)`, `write_sidecars(dir)`, `pack(dir, out_zip)`, `dump_json(obj)` | Assemble a package |
| `world_map_interchange.geometry.pixel_centre(grid, row, col)`, `centres(grid)`, `wraps(grid)` | Geometry helpers |

`Bundle` doesn't validate. **Always call `validate()` first on files from users.**

### CLI contract (for path B)

| Command | Output | Exit code |
|---|---|---|
| `wmi validate PKG --json [--consumer PROFILE.json]` | JSON report on stdout ([schema](../schemas/0.1.0/validation-report.schema.json)) | 0 conformant, 1 not conformant, 2 usage error |
| `wmi decode PKG --layer ID -o out.npy` (or `.csv`) | float64 array, rows north to south; invalid samples are `NaN`; masks as 0/1; class codes as numbers | 0 |
| `wmi encode values.npy out.png --min A --max B [--valid v.npy] [--mask-output m.png]` | PNG16 plus a JSON line with the encoding | 0, or 1 if values are out of range |
| `wmi rehash DIR`, `wmi sidecars DIR`, `wmi pack DIR OUT.zip` | Assemble a package; `pack` validates first | 0 on success, 1 if invalid |

Report fields that tools rely on: `conformant`, `issues[].severity`, `issues[].code` (stable codes, listed in spec
Appendix B), `issues[].message`, `issues[].file`, `issues[].location` (JSON Pointer), and `layers[].status` and
`.reasons`. Show `message` to users and branch on `code` in code.

## 3. Inventory your maps

Before writing code, fill in one row per map your tool computes or consumes. This table is the specification for your
adapter. Agents should produce it first and have a human confirm it.

| Internal name | Exact meaning | Kind | WMI quantity | Units | Qualifiers | Encoding range | Time | Grid | Missing data |
|---|---|---|---|---|---|---|---|---|---|
| `height` | Terrain height incl. sea floor, relative to sea level | scalar | `elevation` | m | `datum: sea_level`, `coverage: full` | -11000..9000 | none (snapshot) | `global` 2048x1024 | none |
| `temp_mean` | 2 m air temperature at terrain height, 30-year annual mean | scalar | `air_temperature` | degC | `elevation_reference: terrain`, `height_above_surface_m: 2` | -90..60 (shared) | span + annual-mean steps | `global` | none |
| `rain_year` | Liquid precipitation, mean annual total | scalar | `rainfall_amount` | mm | none | 0..10000 (shared) | span + `sum` then `mean` | `global` | none |
| `biome` | Our biome classes, 0..17 | categorical | `biome` | none | none | none | none | `global` | none |
| `erosion` | Our erosion index, 0..1, no physical meaning | scalar | `mytool:erosion_index` (+ definition) | 1 | none | 0..1 | none | `global` | ocean invalid |

How to fill it in:

- **Exact meaning** comes from reading the code that computes the field, not from its variable name. Note the height
  reference (terrain or sea level), the phase (rain, snow or both), amount or rate, and the statistic (mean of daily
  minima, coldest period mean and so on).
- **WMI quantity**: choose a registry quantity only if its definition in
  [quantity-registry.md](../spec/0.1.0/quantity-registry.md) matches exactly. Otherwise use `yourtool:name` with a
  `definition`. A namespaced id is always valid, and other tools will retain it rather than misread it.
- **Encoding range**: prefer fixed ranges shared by related layers (the [producer guide](producer-guide.md#2-choose-an-encoding-range-scalars)
  suggests some). Check that your tool's real extremes fit; the encoder refuses out-of-range values.
- **Missing data**: if your tool uses a sentinel (NaN, -9999, 0 over ocean), it becomes a validity mask on export,
  and the sentinel must not appear as a value.
- **Things you don't know** (planet radius, whether a "temperature" is sea-level reduced, which calendar periods mean
  what) are questions for the tool's developer. Don't fill them in by guessing.

## 4. Map your geometry

WMI 0.1.0 has one grid type: `lonlat_regular`, an equirectangular grid whose bounds are **pixel edges**, with **row 0
at the north edge** and **no duplicated seam column**. Convert from your internal layout like this:

| Your internal layout | Conversion on export | Inverse on import |
|---|---|---|
| Row 0 is the south edge | Flip rows (`array[::-1]`) | Flip rows |
| Longitudes 0..360 with column 0 at 0° | Either declare `west: 0, east: 360`, or roll columns by `width/2` and declare `-180..180` | Use bounds as given; normalise with `geometry.normalize_lon` |
| `width + 1` columns, last equal to first | Drop the last column | Append a copy of column 0 if your engine needs it |
| Bounds are pixel **centres** (first centre at -180) | Widen by half a pixel on every side | Narrow by half a pixel |
| `height + 1` rows that include both poles as points | Not a regular cell grid: resample to cells and record `source.resampling` | Resample, or reject with a clear message |
| Cube-sphere, icosahedral, mesh, planar or projected | **Not in 0.1.0.** Resample to lon/lat and record the source resolution and method, or wait for [projections](proposals/projections-and-local-grids.md) | Mark unsupported. Never reinterpret as lon/lat |
| Regional map crossing 180° | `west: 170, east: 190` (east may exceed 180) | Normalise longitudes before comparing |

Planet size: write `world.body.radius_m` if your world has one, and `null` if it doesn't. Never default to Earth's
radius. On import, if the radius is `null` and your tool needs one, ask the user.

Test your geometry with the **regional-seam** and **multi-resolution** examples (section 8): off-by-half-pixel and
flipped-row bugs show up immediately in the expected `lat`/`lon` and values.

## 5. Implement export

### Algorithm

1. **Collect** the arrays from your inventory, as `float64` (scalars), integer codes (categorical) or booleans (masks),
   shape `(height, width)`, laid out as in section 4.
2. **Validity**: for each scalar or categorical layer, build `valid` (true where the value is real). If every sample is
   valid, write no mask. Otherwise write a PNG8 to `masks/` (255 = valid, 0 = invalid) and set the data pixels at
   invalid samples to 0. Layers with identical validity can share one mask file.
3. **Encode** scalars with the inventory range: `p = floor((v - min) / (max - min) * 65535 + 0.5)` for valid samples.
   Out of range is an error: fix the range, don't clip.
4. **Write PNGs**: greyscale 16-bit for scalars and categorical layers, greyscale 8-bit for masks. No `gAMA`, `sRGB`,
   `iCCP`, `tRNS` or other ancillary chunks.
5. **Build the manifest**: `format`, `format_version: "0.1.0"`, `package` (id, created, producer, license), `world`
   (id, body), `grids`, optional `calendars`, `class_tables`, `source`, and then `layers` with `quantity`, `units`,
   `encoding`, `qualifiers`, `time` and `validity_mask` as applicable.
6. **Hash**: SHA-256 (lowercase hex) of every referenced file's exact bytes goes in its `sha256`.
7. **Validate** the folder (`wmi validate` in CI, or your native validator), then **pack** it as a ZIP: relative
   forward-slash paths, `manifest.json` at the root, PNGs stored, no directories or symlinks needed.

Identity rules: `package.id` is new for every export (`urn:uuid:<uuid4>`). `world.id` stays **the same** across exports
of the same world, so consumers can tell that two packages describe one world. `package.created` is the wall-clock UTC
time (`2026-10-05T12:00:00Z`). Simulated time belongs in `source.simulation_time` or layer `time`.

### Python (path A)

[`examples/code/write_climate_package.py`](../examples/code/write_climate_package.py) is a complete, tested exporter.
The core pattern:

```python
import numpy as np
from world_map_interchange import encode
from world_map_interchange.bundle import dump_json, rehash, pack
from world_map_interchange.png import write_png
from world_map_interchange import validate

def add_scalar(out, layers, layer_id, quantity, values, units, rng, valid=None, **fields):
    pixels = encode(values, rng[0], rng[1], valid)          # raises instead of clipping
    (out / "maps" / f"{layer_id}.png").write_bytes(write_png(pixels, 16))
    layer = {"id": layer_id, "kind": "scalar", "quantity": quantity, "grid": "global",
             "path": f"maps/{layer_id}.png", "sha256": "", "units": units,
             "encoding": {"type": "png16_linear", "min": rng[0], "max": rng[1]}, **fields}
    if valid is not None and not valid.all():
        mask_path = f"masks/{layer_id}-valid.png"
        (out / mask_path).write_bytes(write_png(np.where(valid, 255, 0).astype(np.uint8), 8))
        layer["validity_mask"] = {"path": mask_path, "sha256": ""}
    layers.append(layer)

# ... build `manifest` with these layers, then:
(out / "manifest.json").write_text(dump_json(manifest), encoding="utf-8", newline="\n")
rehash(out)                                  # fill in every sha256
report = validate(out)
if not report.conformant:
    raise RuntimeError("\n".join(issue.render() for issue in report.errors))
pack(out, out.with_suffix(".zip"))
```

### Any language (path B or C)

```text
for each layer in inventory:
    values, valid = tool.get_map(layer.internal_name)        # (H, W), row 0 = north
    if layer.kind == scalar:
        assert all(min <= v <= max for v, ok in zip(values, valid) if ok)
        pixels = [floor((v - min) / (max - min) * 65535 + 0.5) if ok else 0 ...]   # uint16
        write_png_gray16(pixels)                             # big-endian samples
    if layer.kind == categorical: pixels = codes (uint16); write_png_gray16
    if layer.kind == mask:        pixels = 255 if true else 0 (uint8); write_png_gray8
    if not all(valid): write_png_gray8(255 if ok else 0) to masks/
write manifest.json (UTF-8, no BOM, no NaN/Infinity, no duplicate keys)
sha256 every referenced file; write the hashes into the manifest
zip: manifest.json + referenced files, relative paths with "/"
```

### Export UI recommendations

- Let the user choose which layers to include and the package licence. Remember the choices.
- Show the validator's issues if a self-check fails. Never write a package your own validator rejects.
- Name the file `<world>-<date>.zip`. `.zip` is the recommended extension in 0.1.0.

## 6. Implement import

### Algorithm

1. **Open safely** ([consumer guide section 1](consumer-guide.md#1-open-the-package-safely)): enforce limits, reject
   unsafe or duplicate paths and symlinks, read entries into memory, and never call "extract all".
2. **Validate** (`validate()` or `wmi validate --json`, or your native checks). If it isn't conformant, show the issue
   messages and stop. Don't attempt partial recovery of non-conformant packages in 0.1.0.
3. **Check the version**: accept `format_version` 0.1.x only.
4. **Assess support** for each layer against what your tool understands: `supported`, `retained` (readable but not
   interpreted, such as other tools' extensions) or `unsupported`. Write a capability profile for your tool (copy one
   from [`examples/profiles/`](../examples/profiles/)) and pass it as `capabilities` or `--consumer`. The report then
   does this for you.
5. **Check workflow requirements separately**: if your tool needs elevation and the package has none, the package is
   still valid. Tell the user "this package has no elevation layer, which this import needs", not "invalid file".
6. **Check qualifiers** before using a layer. For example: elevation `coverage` (is bathymetry real?), temperature
   `elevation_reference` (do you need to apply a lapse rate?), soil moisture depths, and units (convert with the
   registry unit table).
7. **Decode** with every colour transform disabled. Scalars: `v = min + p / 65535 * (max - min)` (exactly `max` at
   65535). Apply the validity mask. Masks: 255 is true.
8. **Map to your internal layout** (inverse of section 4) and resample if needed: area-aware for scalars, `nearest` or
   `mode` for classes and masks, with the validity mask resampled alongside.
9. **Map classes** by `class_id` to your own taxonomy, with an explicit table. List unmapped classes to the user.
10. **Show an import summary**: layers imported, retained and skipped (with reasons), conversions applied, and
    assumptions the user had to confirm.

### Python (path A)

```python
from world_map_interchange import validate
from world_map_interchange.bundle import Bundle
import json

profile = json.load(open("my-tool-profile.json"))           # kinds, grid_types, quantities, required_quantities
report = validate(path, capabilities=profile)
if not report.conformant:
    raise ImportError("\n".join(i.render() for i in report.errors))

status = {s.id: s for s in report.layers}                   # supported / retained / unsupported
with Bundle(path) as pkg:
    for layer in pkg.manifest["layers"]:
        if status[layer["id"]].status != "supported":
            continue
        values, valid = pkg.read(layer["id"])               # float64 physical values, bool validity
        lat_lon = pkg.grid(layer["id"])                     # bounds, width, height
        tool.import_layer(layer, values, valid, lat_lon)
```

### CLI (path B)

```bash
wmi validate world.zip --json --consumer my-tool-profile.json > report.json   # exit 0 = conformant
wmi decode world.zip --layer elevation -o elevation.npy                        # NaN = invalid
```

Read `report.json` for layer statuses. Read `manifest.json` from the ZIP yourself for qualifiers, units and grids.

## 7. Round trips and preservation

If your tool imports a package and later exports the same world:

- keep `world.id` and the same layer ids for layers that keep their meaning;
- carry `retained` layers through unchanged, byte for byte with the same `sha256`, together with namespaced qualifiers
  and `extensions` objects;
- write a **new** `package.id` and `created`, and set `source` to describe your run;
- re-hash anything you modified, and regenerate sidecars from the manifest (or omit them).

Round-trip test: `import → export` of each valid example should validate, and decoded values of unmodified layers should
agree within the tolerances in section 8.

## 8. Test against the shared examples

The repository ships fixtures for exactly this. Use them from any language: copy or vendor the `examples/` folder at
your pinned commit (it's MIT licensed), or fetch it in CI.

### Reader tests: `examples/valid/*` and `examples/expected/*.json`

Each `expected/<name>.json` has a `package` path and a list of `samples`:

```json
{"layer": "precip-annual", "row": 7, "col": 5, "lat": 5.625, "lon": -118.125,
 "valid": true, "value": 0.0, "units": "mm", "pixel": 0, "tolerance": 0.0305}
{"layer": "biome", "row": 16, "col": 32, "valid": true, "code": 8, "class_id": "example:tropical_rainforest"}
{"layer": "ocean", "row": 0, "col": 0, "valid": true, "mask": true}
{"layer": "sea-floor-depth", "row": 32, "col": 64, "valid": false}
```

For every sample, your reader must produce `|decoded - value| <= tolerance` (scalars, in the stated `units`), the exact
`code` and `class_id` (categorical), the exact `mask`, and `valid: false` where stated. `pixel` is the exact stored value,
and `lat`/`lon` are the pixel centre (normalised to [-180, 180)). Check both to catch geometry and decode bugs.
[EXPECTED.md](../examples/EXPECTED.md) shows the same data as tables. `examples/packed/*.zip` are ZIP versions for testing
your archive path.

The examples are small, but they cover the cases integrations most often get wrong: legitimate zeros versus missing
data (`missing-and-zero`), constant fields (`constant-fields`), a non-zero sea level (`multi-resolution`), the
antimeridian (`regional-seam`), unequal fictional calendar periods (`climate-only`) and unrecognised extensions
(`snow-and-soil`).

### Rejection tests: `examples/invalid/*`

[`invalid/expectations.json`](../examples/invalid/expectations.json) maps each case to its target and expected error
codes. A native reader doesn't have to produce the same codes, but it **must refuse** every case. The archive cases
(`*.zip`) are deliberately hostile: process them only with your safe reader, never with an extracting tool.

### Writer tests

In your CI, export a small world with your tool and run:

```bash
wmi validate out/my-export.zip --strict     # warnings fail too
```

Also test edge cases from your own tool: an all-ocean world, a world with no climate, maximum resolution, and a map
containing your tool's missing-data sentinel.

### Example: a test in Python

```python
import json, pathlib, pytest
from world_map_interchange.bundle import Bundle   # or your own reader

ROOT = pathlib.Path("vendor/world-map-interchange/examples")

@pytest.mark.parametrize("case", sorted((ROOT / "expected").glob("*.json")), ids=lambda p: p.stem)
def test_reader_matches_expected(case):
    exp = json.loads(case.read_text())
    with Bundle(ROOT / "valid" / exp["example"]) as pkg:      # replace with your reader
        for s in exp["samples"]:
            values, valid = pkg.read(s["layer"])
            assert bool(valid[s["row"], s["col"]]) == s["valid"]
            if not s["valid"]:
                continue
            got = values[s["row"], s["col"]]
            if "value" in s:
                assert abs(got - s["value"]) <= s["tolerance"]
            elif "code" in s:
                assert int(got) == s["code"]
            else:
                assert bool(got) == s["mask"]
```

## 9. Native implementation notes (any language)

You need four building blocks. Most platforms have them already.

| Block | Requirement | Watch out for |
|---|---|---|
| ZIP | Read the central directory before data; stored and deflate methods; per-entry size limits | Libraries that extract to disk with entry names unchecked (path traversal) |
| PNG | Decode **greyscale 16-bit** and 8-bit **without conversion**; encode the same | Loaders that silently convert 16-bit to 8-bit, apply gamma or ICC profiles, or return RGBA. Engine texture importers often do all three |
| JSON | Strict: reject duplicate keys, NaN/Infinity and a BOM | Lenient parsers that keep the last duplicate key |
| SHA-256 | Over exact file bytes | Hashing decoded pixels instead of the file |

Byte-level facts:

- PNG 16-bit samples are **big-endian**. On little-endian machines, swap bytes when you build or read a raw buffer by hand.
- PNG rows run top to bottom, and the top is north. No flipping is needed unless your engine's textures are bottom-up
  (OpenGL convention).
- Decode in double precision: `v = min + p * ((max - min) / 65535)` is acceptable, but `min + (p / 65535) * (max - min)`
  with `p = 65535` mapping to exactly `max` is the reference.
- Encode with round half up. Ties are rare, and the expected `pixel` values in the fixtures were computed this way.

A quick check that your PNG path keeps all 16 bits: decode `examples/valid/climate-only`, layer `t-annual-mean`, row 24,
column 48. The pixel must be **52790**. A loader that drops to 8 bits gives 206, or 52942 (206 × 257) if it scales back up.

**Embedding the schemas and registry.** A native validator can reuse
[`schemas/0.1.0/manifest.schema.json`](../schemas/0.1.0/manifest.schema.json) with any JSON Schema 2020-12 library, and
[`registry/0.1.0/quantities.json`](../registry/0.1.0/quantities.json) for quantity, unit and qualifier checks. Ship
copies at your pinned version (MIT; keep the notice). Schema validation covers structure only. The semantic rules
(time reductions, accumulations, codes in class tables, mask values, hashes) are in specification sections 6 to 12.
The reference implementation is [`validate.py`](../src/world_map_interchange/validate.py), and the fixtures tell you
whether you got them right.

**Minimum viable native reader.** If you only import, you can start with: safe ZIP, strict JSON, version check, `lonlat_regular`
grids, `scalar` and `mask` kinds, validity masks, SHA-256 checks, and "unsupported" for everything else. Add categorical
and time handling as you need them. Report what you skip; don't fail on it.

## 10. Definition of done

Export:

- [ ] Inventory table reviewed by a human who knows the tool's science and conventions.
- [ ] Every exported layer has the registry quantity that matches exactly, or a namespaced extension with a definition.
- [ ] Qualifiers, units, time and validity are filled in from the inventory. Nothing is defaulted silently.
- [ ] `wmi validate --strict` passes on exports in CI, including edge-case worlds.
- [ ] Re-importing an export (into your tool, or with `wmi decode`) gives values within half a quantisation step.

Import:

- [ ] All `examples/valid` fixtures read with expected values, codes, masks and validity.
- [ ] All `examples/invalid` fixtures refused, including the hostile archives, with no files written outside your control.
- [ ] Layer support (supported, retained, unsupported) and missing workflow requirements are reported to the user
      separately from validity.
- [ ] Unknown radius, unknown geometry, unknown quantities and unmapped classes are reported, never defaulted.
- [ ] Version check rejects other 0.x minor versions.

Both:

- [ ] Third-party notices updated if you copied code, schemas or the registry.
- [ ] The WMI version you implement is recorded in your documentation, for example "imports and exports WMI 0.1.0 (experimental)".

## 11. Keeping up with the draft

- Watch the repository's releases and [CHANGELOG.md](../CHANGELOG.md). Every normative change is listed there.
- While WMI is 0.x, implement exactly one minor version and reject others with a clear message. After 1.0, newer minor
  versions are meant to be readable.
- Bring problems back: an [interoperability failure](https://github.com/Cradoux/world-map-interchange/issues/new?template=interoperability-failure.yml)
  with a minimal synthetic package is the most useful feedback the draft can get.

## 12. Handing this task to a coding agent

Copy this prompt, fill in the brackets, and give it to your agent together with access to your codebase. The agent
should read this guide and [AGENTS.md](../AGENTS.md) from the repository at the pinned commit.

```text
Add World Map Interchange (WMI) 0.1.0 [export | import | export and import] to this codebase.

Reference: https://github.com/Cradoux/world-map-interchange at commit [SHA].
Read AGENTS.md and docs/integration-guide.md there first, and follow the integration guide's steps in order.

Integration path: [A Python library | B CLI subprocess | C native | D native + wmi validate in CI].
Layers in scope: [e.g. elevation, ocean mask, annual temperature and precipitation, biome].
Package licence to offer users: [e.g. user's choice, default CC-BY-4.0].

Rules:
- First produce the map inventory table (guide section 3) and the geometry mapping (section 4) from this codebase,
  with file and line references for each claim, and stop for my review before writing adapter code.
- List every unknown (radius, height reference, calendar meaning, statistic, missing-data sentinel) as a question.
  Don't guess, and don't default to Earth values.
- Keep the adapter in its own module behind a version check for format_version 0.1.x.
- Add tests that use the repository's examples/valid + examples/expected fixtures (reader) and
  `wmi validate --strict` on our own exports (writer).
- Finish with: files changed, test results, the inventory table, open questions, and anything you marked unsupported.
```
