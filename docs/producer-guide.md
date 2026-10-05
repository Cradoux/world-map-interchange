# Producer implementation guide

This guide explains how to write World Map Interchange (WMI) 0.1.0 packages from any tool. It is informative. The
[specification](../spec/0.1.0/specification.md) is normative.

## 1. Decide what to export

Export the maps your tool actually computes. No quantity is mandatory. For each output, decide:

1. **Is there a registry quantity with exactly this meaning?** Check the [quantity registry](../spec/0.1.0/quantity-registry.md).
   Match the definition, not the name: "temperature" may be air, surface (skin) or sea-surface temperature, and may be
   at terrain height or reduced to sea level.
2. **If not, use a namespaced extension**, for example `mytool:erosion_index`, and write a `definition`. A precise extension
   is better than a registry quantity that only nearly fits. Consumers will report it as retained rather than misread it.
3. **What kind is it?** Continuous values are `scalar`, class codes are `categorical`, true/false is `mask`, and a
   picture is `reference`. Continuous fractions such as snow cover are scalars with units `1`, not masks.

## 2. Choose an encoding range (scalars)

Pixels are 16-bit. For range `[min, max]`, the quantisation step is `(max - min) / 65535` and the worst-case error is half a
step.

| Quantity | Suggested shared range | Step | Max error |
|---|---|---|---|
| Elevation incl. bathymetry | -11000 .. 9000 m | 0.305 m | 0.153 m |
| Air temperature (all statistics) | -90 .. 60 degC | 0.0023 K | 0.0011 K |
| Annual precipitation | 0 .. 10000 mm | 0.153 mm | 0.076 mm |
| Snow depth | 0 .. 20 m | 0.31 mm | 0.15 mm |
| Fractions (0..1) | 0 .. 1 | 1.5e-5 | 7.6e-6 |

Guidance:

- Use **fixed, shared ranges** for related layers (all temperature statistics, or rain, snow and total precipitation),
  so that a consumer can compare pixels directly and ranges stay stable between runs.
- Values outside the range are an error: the reference encoder raises rather than clipping. Widen the range, or mark
  those samples invalid if they are genuinely unknown.
- Do **not** store a "sea-level pixel" or a scale/offset alongside the range. The range is the only authority.
- Observed extrema go in the optional `statistics` block. They do not need to equal the range.

## 3. Mark missing data with a validity mask

- Write an 8-bit greyscale PNG in `masks/` with **255 = valid and 0 = invalid**. If every sample is valid, omit it.
- Several layers can share one mask, for example an "ocean" validity mask for sea-surface temperature and sea-floor depth.
- Write 0 into the data pixels at invalid samples. Consumers ignore those pixels.
- Never use a magic value (such as -9999 or pixel 0) to mean "missing". Pixel 0 is a real value (`encoding.min`) and code
  0 can be a real class.
- A validity mask is not an ocean mask. If you have an ocean mask, export it as an `ocean_mask` layer as well.

## 4. Write PNGs that contain only numbers

The most common interoperability failure is an image library being "helpful". Check that your output is:

- **Colour type 0 (greyscale)**, bit depth 16 for scalar and categorical layers, and 8 for masks. Not RGB, not palette and not
  greyscale with alpha.
- **Free of `gAMA`, `sRGB`, `iCCP`, `cHRM` and `sBIT` chunks.** Some libraries and editors add these. The validator warns,
  and consumers must ignore them, but it is cleaner not to write them.
- **Free of `tRNS`**: transparency is not validity.
- **Big-endian 16-bit**: PNG requires it, and libraries handle it, but hand-written encoders must byte-swap on
  little-endian machines.

Library notes (check against your versions):

| Library | Notes |
|---|---|
| Python `world_map_interchange.png.write_png` | Writes minimal PNGs with no ancillary chunks. |
| Pillow | Writing `I;16` works for greyscale 16-bit. Avoid mode `I` (32-bit) round trips and `convert()`. |
| OpenCV | `cv2.imwrite` with a `uint16` single-channel array writes 16-bit greyscale. Three-channel arrays are BGR. |
| libpng / lodepng / stb | Request `PNG_COLOR_TYPE_GRAY` with 16-bit depth explicitly, and do not call gamma or sRGB setters. |
| Image editors | Usually unsuitable for data layers: many convert to 8-bit or apply colour profiles. |

Run `wmi validate` on your output. It reports the exact colour type, bit depth and unwanted chunks.

## 5. Describe geometry precisely

- Use `lonlat_regular` with bounds at **outer pixel edges**, not pixel centres. A global 2048x1024 map has
  `west -180, east 180, north 90, south -90`, and its first pixel centre is at (89.912, -179.912).
- Row 0 is the northern edge. Flip your raster if your tool stores south-up.
- Do not repeat the seam column. If your engine stores width+1 columns with the last equal to the first, drop the last.
- For a region crossing the antimeridian, use `east > 180` (for example west 170, east 190).
- Declare `world.body.radius_m`, or `null` if your world has no defined radius. Do not write Earth's radius unless you
  mean it.
- Several resolutions are fine: declare one grid per resolution. If you downsampled, record the original size and method
  in the layer's `source`, and use `mode` or `nearest` for classes.

## 6. Describe time precisely

- Wall-clock creation time goes in `package.created`. Simulated time goes in `source.simulation_time` or layer `time`.
- Declare your calendar. A fictional calendar is `kind: fixed`, with your year length and named periods of any lengths.
  `proleptic_gregorian` is only for Earth dates.
- Express statistics as aggregation steps (specification section 9.4). Most climate exports need only the patterns
  "annual mean", "mean of annual minima/maxima", "coldest/warmest period mean" and "mean annual total".
- Precipitation and snowfall **amounts** start with `sum`. **Rates** use `*_rate` quantities with rate units and no `sum`.

## 7. Heights and sea level

- Prefer `elevation` with `datum: sea_level` and `coverage: full`, which gives signed values with bathymetry.
- If your heightmap is relative to some other zero (for example "sea level is at 1250 m on this map"), declare a datum in
  `world.vertical_datums` with `sea_level_m: 1250` and reference it. Consumers then compute elevation relative to sea
  level exactly.
- If your tool clamps oceans to sea level, say `coverage: land_clamped` with `clamp_value`. If it marks them missing,
  say `land_masked` and provide a validity mask.
- Positive-down depth is a separate quantity, `sea_floor_depth`. Do not put depth in an elevation layer.

## 8. Classes

- Keep your own taxonomy. Give it a namespaced `taxonomy` id and give each class a namespaced, stable `id`.
- Do not merge marine classes into terrestrial ones (or the reverse) to fit someone else's list. Mapping between
  taxonomies is the consumer's job, and an open topic for shared mapping tables.
- Colours are optional display hints. Ship a colour key as a reference image if you like.

## 9. Assemble, hash and pack

```bash
wmi rehash path/to/package      # fill in sha256 values
wmi sidecars path/to/package    # optional per-image JSON copies, generated from the manifest
wmi validate path/to/package    # must report CONFORMANT
wmi pack path/to/package out.zip
```

`wmi pack` validates first. It writes manifest and referenced files only, with PNGs stored uncompressed and fixed
timestamps, so the output is reproducible.

## 10. Producer checklist

- [ ] `manifest.json` at the root, UTF-8 without BOM and strict JSON.
- [ ] `package.id`, `created`, `producer` and `license` filled in. `world.id` stable across exports of the same world.
- [ ] Every scalar has `units` from the registry list and a finite `min < max` range. No silent clipping.
- [ ] Missing data marked only with validity masks (0/255).
- [ ] Data PNGs are greyscale 16-bit (8-bit for masks), without colour-management or transparency chunks.
- [ ] Grid bounds are pixel edges, rows run north to south, and there is no duplicated seam column.
- [ ] Radius declared or `null`, and never defaulted to Earth.
- [ ] Temperature has `elevation_reference`. Soil moisture has depth and frozen-water treatment. Amounts and rates are
      distinct.
- [ ] Extensions are namespaced and have definitions.
- [ ] `wmi validate` reports CONFORMANT with no warnings.

## Scope note

Bulk import/export adapters for specific applications (including Dayside) are separate follow-up work and not part of
this repository. This guide and the reference tools are meant to make such adapters straightforward to write.
