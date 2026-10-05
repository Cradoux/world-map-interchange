# Consumer implementation guide

This guide explains how to read World Map Interchange (WMI) 0.1.0 packages safely and correctly. It is informative.
The [specification](../spec/0.1.0/specification.md) is normative.

## 1. Open the package safely

Treat every package as untrusted.

1. If the target is a directory, list files without following links. Reject symlinks and junctions.
2. If it is a ZIP, inspect the central directory **before reading anything**:
   - reject names that are absolute, contain `..`, backslashes, colons or control characters;
   - reject duplicate names and names that collide case-insensitively;
   - reject symlink entries (Unix mode `0o120000` in the external attributes), encrypted entries, and compression
     methods other than stored and deflate;
   - enforce limits on entry count, per-file size, total expanded size and compression ratio.
3. Read entries into memory, or into file names you construct yourself. Never call a generic "extract all".
4. Require `manifest.json` at the root. If it is inside a single folder, report that clearly rather than guessing.

The reference implementation is [`src/world_map_interchange/package.py`](../src/world_map_interchange/package.py).

## 2. Read the manifest

- Parse it as strict JSON: reject a BOM, duplicate keys and `NaN`/`Infinity`.
- Check `format == "world-map-interchange"` and that you implement `format_version`'s major.minor. During 0.x, reject
  other minor versions instead of guessing.
- Validate against [`schemas/0.1.0/manifest.schema.json`](../schemas/0.1.0/manifest.schema.json) (JSON Schema
  2020-12), then apply the semantic rules, or run `wmi validate --json` and read the report.

## 3. Decide what you can use

For each layer, determine its support status:

| Status | When |
|---|---|
| `supported` | You implement the kind, the grid type and the quantity (with the qualifiers you need). |
| `retained` | You can read and carry the layer, but do not interpret its quantity (for example a namespaced extension). |
| `unsupported` | Unknown kind, encoding or grid type. Do not guess. |

Report these statuses to the user **separately** from conformance. A climate-only package is conformant even if your
tool needs elevation. In that case report "elevation required by this workflow is missing", not "invalid file". Express
your needs as a capability profile (see [`examples/profiles/`](../examples/profiles/)) to get this report from
`wmi validate --consumer`.

Check qualifiers before declaring support. For example, a tool that needs real bathymetry should check
`elevation.qualifiers.coverage == "full"`. A tool that assumes temperatures at terrain height should check
`elevation_reference == "terrain"`, or apply the lapse rate itself.

## 4. Decode pixels

1. Before decoding, read `IHDR` and check the dimensions against your limits and against the layer's grid.
2. Check the colour type and bit depth for the kind (section 7 of the spec).
3. Decode raw samples. **Turn off every colour transform**: gamma, ICC, sRGB conversion and "auto-orient". Ignore `gAMA`,
   `cHRM`, `sRGB`, `iCCP`, `cICP`, `mDCV`, `cLLI` and `sBIT` in data layers.
4. Scalars: `value = min + p / 65535 * (max - min)` in double precision. Return `max` exactly for `p = 65535`.
5. Categorical: the pixel is the class code. Look it up in the class table. Never interpolate codes.
6. Masks: 255 is true and 0 is false. Any other value means the package is invalid.
7. Apply the validity mask: samples with 0 have no value, whatever their pixel says. If there is no mask, every sample is valid.

Libraries that are easy to misuse: some image loaders convert 16-bit to 8-bit by default, apply an embedded gamma, or
return RGBA. Always ask for "unchanged" or "any depth" decoding.

## 5. Units and conversion

Units come from the registry unit table, which gives a scale and offset to a canonical unit per dimension (for example
`degC` = K - 273.15). For water amounts, `mm` and `kg m-2` are numerically equal for liquid water. `mm d-1` uses a day of
86 400 s, not the world's own day.

## 6. Geometry

- Pixel centre of row `r` and column `c`: `lon = west + (c + 0.5) * (east - west) / width`,
  `lat = north - (r + 0.5) * (north - south) / height`.
- `east - west == 360` means the grid wraps: sample across the seam by wrapping column indices. Do not expect a
  duplicated seam column.
- `east > 180` means the region crosses the antimeridian. Normalise longitudes when comparing with your own grids.
- If `world.body.radius_m` is `null`, the radius is unknown. Ask, or keep values in angular units. Never assume
  6 371 km silently.
- Unknown grid types: mark the layers unsupported. Do not reinterpret them as latitude/longitude.

When resampling to your own grid, use area-aware methods for continuous fields and `nearest` or `mode` for classes and
masks. Resample the validity mask with the data, and treat partially valid cells conservatively.

## 7. Time

- `package.created` is when the file was written. Simulation time is in `source.simulation_time` and layer `time`.
- Read the aggregation list to understand the statistic. For example, `minimum over timesteps within year`, then
  `mean over years` is "mean annual minimum", which is not the same as the coldest-month mean.
- Calendars may have any number of unequal periods and any year length. Do not map periods to Earth months unless the
  calendar is `proleptic_gregorian`.

## 8. Heights and sea level

- With `datum: sea_level`, sea level is 0 in the layer's units. With a declared datum, elevation relative to sea level is
  `value - sea_level_m`, converted to layer units.
- `coverage: land_clamped` means samples equal to `clamp_value` may be clamped ocean, not real terrain. Use an ocean mask
  if one is present.
- `sea_floor_depth` is positive down. Do not mix it with elevation without changing the sign.

## 9. Classes

- Identify classes by `id` (stable and namespaced), not by colour, and preferably not by code alone.
- Map unknown taxonomies to your own explicitly, and tell the user which classes were unmapped. Use `realm` as a coarse
  fallback if helpful. Never drop marine classes into terrestrial bins silently.

## 10. Preserve what you do not understand

When rewriting a package, preserve `retained` layers, namespaced qualifiers and `extensions` objects unchanged. If you
modify a layer, regenerate its hash and any sidecar from the manifest.

## Consumer checklist

- [ ] Safe archive reading with bounded resources. No extraction of unsafe names, no links followed.
- [ ] Strict JSON, version check, and schema plus semantic validation (or `wmi validate`).
- [ ] Raw PNG samples with every colour transform disabled.
- [ ] Validity masks applied. Pixel 0 and code 0 treated as real values.
- [ ] Supported, retained and unsupported reported separately from conformance.
- [ ] Unknown radius, unknown geometry and unknown quantities reported, never defaulted.

## Scope note

Application-specific bulk import adapters (including for Dayside) are separate follow-up work.
