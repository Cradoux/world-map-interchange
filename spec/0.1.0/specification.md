# World Map Interchange (WMI): Specification 0.1.0

**Status: experimental draft, open for discussion.** This document is a proposal for joint development by the developers of
worldbuilding and terrain tools. It is not an established or endorsed standard. Anything may change before 1.0, and minor
versions in the 0.x series may be incompatible (see [COMPATIBILITY.md](../../COMPATIBILITY.md)).

| | |
|---|---|
| Version | 0.1.0 (draft) |
| Manifest schema | [`schemas/0.1.0/manifest.schema.json`](../../schemas/0.1.0/manifest.schema.json) (JSON Schema Draft 2020-12) |
| Quantity registry | [`registry/0.1.0/quantities.json`](../../registry/0.1.0/quantities.json), rendered as [quantity-registry.md](quantity-registry.md) |
| Reference validator | `wmi validate` in this repository |
| Open questions | [docs/open-decisions.md](../../docs/open-decisions.md) |

Text marked **[Proposal]** is not part of the 0.1.0 conformance requirements. It records a direction under discussion.

---

## 1. Purpose and scope

WMI defines one portable package that carries whichever maps an application produces (elevation, climate, classes, masks
and visual references). It includes enough metadata for another application to interpret the numbers without
reverse-engineering colour ramps.

Goals of 0.1.0:

- A package format that is small and easy to implement: an ordinary ZIP archive, or the same layout as a plain directory,
  containing one JSON manifest and PNG rasters.
- Numeric meaning stated explicitly: quantity, units, encoding range, validity, time statistic and vertical reference.
- Producer-specific outputs kept through namespaces, without false claims of shared semantics.
- Conformance of a package kept separate from whether a particular application can use every layer.

Non-goals of 0.1.0: floating-point rasters, arbitrary map projections, vector fields, time-series packaging and
replacing scientific formats such as netCDF. These are recorded as proposals in [docs/proposals/](../../docs/proposals/).

No map type is mandatory. A package with only climate layers is as valid as one with only elevation. Whether a workflow
*requires* a particular quantity is a decision for the consumer or for a profile (section 4.3).

## 2. Conventions and terms

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, RECOMMENDED, MAY and OPTIONAL are to be interpreted as
described in RFC 2119 and RFC 8174 when, and only when, they appear in capitals.

| Term | Meaning |
|---|---|
| package | A ZIP archive or directory with `manifest.json` at its root. |
| producer | Software that writes packages. |
| consumer | Software that reads packages. |
| layer | One entry in `manifest.layers`, referring to one image file. |
| data layer | A layer of kind `scalar`, `categorical` or `mask`. |
| sample / pixel | One grid cell. "Pixel value" is the raw integer stored in the PNG. |
| valid sample | A sample marked valid by the layer's validity mask, or any sample if the layer has none. |
| registry quantity | A quantity id without a namespace prefix, defined in the quantity registry. |
| namespaced id | `namespace:name`, for producer-specific identifiers. |

## 3. Package structure

### 3.1 Layout [Required]

```
manifest.json        required, at the package root
maps/                data layers: scalar, categorical and mask rasters (and extension kinds)
masks/               validity masks only
previews/            reference images (non-numeric)
```

- A package MUST contain `manifest.json` at its root. In a ZIP, the root is the archive root, not a folder inside it.
- Layers MUST be stored in the directory for their kind: `maps/` for data layers and extension kinds, `masks/` for
  validity masks and `previews/` for reference images. Subdirectories are allowed below these.
- The same layout MUST be accepted both as a ZIP archive and as an unpacked directory. Both forms are equivalent.
- No file extension is mandated for the archive. `.zip` is RECOMMENDED.
- `README*`, `LICENSE*`, `LICENCE*`, `NOTICE*` and `CHANGELOG*` files MAY be placed at the root. Other files that the
  manifest does not reference SHOULD NOT be present, and validators report them as warnings.

### 3.2 Paths [Required]

All paths in the manifest are relative to the package root and use `/` as the separator. Every path MUST:

- start with `maps/`, `masks/` or `previews/`, as appropriate;
- consist of segments matching `[A-Za-z0-9][A-Za-z0-9._-]*`, with no segment ending in `.`;
- not contain `.` or `..` segments, empty segments, backslashes, colons, drive letters or a leading `/`;
- not use Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM0`-`COM9`, `LPT0`-`LPT9`) as segments;
- be at most 240 characters long.

Two files in one package MUST NOT have names that differ only by letter case. Paths are case-sensitive, and a consumer
MUST resolve a path exactly as written, even on case-insensitive file systems. Lower-case names are RECOMMENDED.

### 3.3 ZIP archives [Required]

- Entries MUST use compression method 0 (stored) or 8 (deflate). PNG files SHOULD be stored, because they are already
  compressed.
- Entries MUST NOT be encrypted.
- An archive MUST NOT contain two entries with the same name, or entries whose names are unsafe per section 3.2
  (absolute, `..`, backslash, drive letter or control characters).
- An archive MUST NOT contain symbolic-link entries.
- ZIP64 MAY be used for large archives.

### 3.4 Directory packages [Required]

A directory package MUST NOT contain symbolic links, junctions or other reparse points. Consumers MUST NOT follow links
that lead outside the package.

### 3.5 Safe reading [Required for consumers]

Consumers MUST treat packages as untrusted input:

- A consumer MUST NOT extract an entry whose name is unsafe, and SHOULD read entries in memory or into paths it
  constructs itself, rather than extracting the archive as a whole.
- A consumer MUST bound its resource use: number of entries, size per file, total expanded size, compression ratio
  and pixels per image. The reference validator defaults are 10 000 entries, 2 GiB per file, 16 GiB in total, a ratio
  of 1000:1 and 2^28 pixels. All of them are configurable.
- A consumer MUST check PNG dimensions from the header against its limits *before* decoding pixels.

## 4. Conformance

### 4.1 Package conformance

A package is **conformant** if it satisfies every MUST in this specification that applies to packages: the manifest
validates against the schema, satisfies the semantic rules, and every referenced file exists, matches its hash and
meets its kind's PNG and content rules. The reference validator reports this as `conformant: true`.

Warnings, such as colour-management chunks or unreferenced files, do not affect conformance.

### 4.2 Consumer support is separate from conformance

A conformant package may contain layers that a particular consumer cannot use. Consumers SHOULD report, per layer, one of:

| Status | Meaning |
|---|---|
| `supported` | The consumer understands the layer's kind, encoding, geometry and quantity, and can interpret it. |
| `retained` | The consumer can read and preserve the layer (bytes and metadata) but does not interpret its quantity, for example a namespaced extension. |
| `unsupported` | The consumer cannot use the layer, for example because of an unknown kind or unsupported geometry. |

A consumer MUST NOT reinterpret an unsupported layer as something else, for example by treating an unknown grid as
global latitude/longitude, or a reference image as data.

### 4.3 Profiles and workflow requirements

A consumer MAY require certain quantities (for example "elevation with `coverage: full`"). An unmet requirement means the
package is unsuitable for that workflow. It does not mean the package is invalid. The reference tools express this with
a capability profile ([`schemas/0.1.0/capabilities.schema.json`](../../schemas/0.1.0/capabilities.schema.json)).
Richer, shared profiles are an open topic.

## 5. Manifest

`manifest.json` MUST be UTF-8 JSON without a byte-order mark. It MUST NOT contain duplicate object keys or the
non-standard literals `NaN`, `Infinity` and `-Infinity`. All numbers MUST be finite. The manifest is the single authority
for every layer definition.

### 5.1 Top-level fields

| Field | Status | Description |
|---|---|---|
| `format` | required | The constant `"world-map-interchange"`. |
| `format_version` | required | `"0.1.0"` for this draft (pattern `0.1.x`). |
| `package` | required | Identity, creation, producer and licence (5.2). |
| `world` | required | World identity, body and vertical datums (5.3). |
| `source` | optional | Simulation, run and snapshot identity (5.4). |
| `calendars` | optional; required if any time is given | Calendar definitions keyed by local id (section 9). |
| `grids` | required, at least one | Grid definitions keyed by local id (section 8). |
| `class_tables` | optional; required for categorical layers | Class tables keyed by local id (section 11). |
| `layers` | required, at least one | Layer definitions (section 6). At least one MUST be a data layer. |
| `extensions` | optional | Namespaced producer metadata (section 13). |

Local ids (for grids, layers, calendars, class tables and periods) match `[a-z0-9][a-z0-9_.-]{0,63}`.

### 5.2 `package`

| Field | Status | Description |
|---|---|---|
| `id` | required | Globally unique package id. `urn:uuid:` is RECOMMENDED. |
| `created` | required | RFC 3339 date-time when the package was written, e.g. `2026-10-05T12:00:00Z`. This is wall-clock time, never simulation time. |
| `producer` | required | `{name, version, url?}` of the software that wrote the package. |
| `license` | required | SPDX licence expression for the package content (or `LicenseRef-...`). |
| `title`, `description`, `attribution`, `url` | optional | Human-readable information. |

Each package carries its own licence. Content contributed to this repository or shared between tools keeps the licence
its producer declares. The repository's MIT licence applies only to the repository's own original content.

### 5.3 `world`

| Field | Status | Description |
|---|---|---|
| `id` | required | Stable world identifier, shared by all packages describing the same world. |
| `name`, `description` | optional | |
| `body.shape` | required | `"sphere"` in 0.1.0. |
| `body.radius_m` | required (may be `null`) | Radius of the reference sphere in metres, or `null` if unknown. |
| `sea_level_description` | optional | What "sea level" means for this world and snapshot. |
| `vertical_datums` | optional | Additional vertical datums: `{id: {description, sea_level_m}}`. |

If `radius_m` is `null`, consumers MUST NOT substitute Earth's radius silently. A consumer that needs a radius MUST ask
the user or report that the radius is unknown.

The built-in datum `sea_level` always exists and MUST NOT be redeclared. Each declared datum MUST state `sea_level_m`,
the height of sea level above that datum in metres. Sea level is therefore always available in physical units: 0 m on
`sea_level`, and `sea_level_m` on any other datum.

### 5.4 `source`

All fields are optional: `simulation_id`, `run_id`, `snapshot_id`, `simulation_time` (a time point, section 9.2) and
`source_heightmap` (`{id?, sha256?, description?}`, identifying the heightmap a simulation was driven by). Simulation
time is unrelated to `package.created`.

## 6. Layers

### 6.1 Fields common to all layers

| Field | Status | Description |
|---|---|---|
| `id` | required | Unique local id within the package. |
| `kind` | required | `scalar`, `categorical`, `mask`, `reference`, or a namespaced extension kind. |
| `path` | required | Image path (section 3.2). Each file belongs to exactly one layer. |
| `sha256` | required | Lower-case hex SHA-256 of the file's bytes. |
| `quantity` | required for data layers | Registry quantity or namespaced extension quantity. |
| `grid` | required for data layers and registered references | Local id of a grid. Image dimensions MUST equal the grid's. |
| `title`, `description` | optional | |
| `definition` | required for extension quantities | What the values mean, in plain language. |
| `qualifiers` | per quantity | Quantity-specific metadata (section 10). |
| `time` | per quantity | Temporal meaning (section 9). |
| `validity_mask` | optional | `{path, sha256}` of a validity mask in `masks/` (6.5). |
| `source` | optional | Source resolution and resampling (8.6). |
| `provenance` | optional | `{producer?, derived_from?, notes?}` if the layer differs from the package producer or was derived from other layers. |
| `extensions` | optional | Namespaced metadata. |

### 6.2 `scalar`: continuous numeric values [Required]

Encoding type `png16_linear`. Fields: `units` (required), `encoding: {type: "png16_linear", min, max}` (required) and
`statistics` (optional).

**PNG.** A 16-bit greyscale PNG (colour type 0, bit depth 16). See section 7.

**Decode contract.** For a pixel value `p` in 0..65535:

```
value = encoding.min + p / 65535 * (encoding.max - encoding.min)
```

- `encoding.min` and `encoding.max` MUST be finite, with `encoding.min < encoding.max`, and their difference MUST be
  finite in IEEE-754 double precision.
- Decoders SHOULD compute in double precision. Results differing from the formula by a few units in the last place are
  acceptable. Decoders SHOULD return `encoding.max` exactly for `p = 65535` and `encoding.min` exactly for `p = 0`.
- `units` give the physical units of the decoded value. They MUST be allowed by the registry quantity (section 10).
- The pair (`min`, `max`) is the only authority. There are no separate scale, offset or "sea-level pixel" fields that
  could disagree with it.

**Encoding.** For a physical value `v`, with `t = (v - min) / (max - min)`:

```
p = floor(t * 65535 + 0.5)
```

This rounds to the nearest pixel. Exact ties round up, towards the larger pixel value. A value is representable only if
the resulting `p` lies in 0..65535. Producers MUST NOT clip values silently: a value outside the range is an error, to
be fixed by widening the range or marking the sample invalid. The worst-case round-trip error for valid samples is half a
quantisation step, `(max - min) / 65535 / 2`.

**Range choice.** The encoding range is a *packing* range. It need not equal the observed extrema. A fixed range shared by
related layers (for example -90 to 50 degC for every temperature statistic) is RECOMMENDED, because it makes layers directly
comparable. Producers choose the range to bound the quantisation step at the precision they need.

**Observed statistics.** `statistics: {valid_count?, minimum?, maximum?, mean?}` are optional facts about the valid
samples, in layer units. If present, they MUST agree with the decoded data: `valid_count` exactly, and the others within
half a quantisation step. They never affect decoding.

**Constant fields.** `encoding.min < encoding.max` still applies. Producers SHOULD set `encoding.min` to the constant
value `c` and choose any larger `encoding.max` (the reference helper uses `c + max(1, |c| x 2^-20)`). All pixels are then
0 and decode to exactly `c`. Using the quantity's usual shared range is also acceptable.

**Entirely missing fields.** If no sample is valid, the layer MUST have a validity mask with every sample 0, pixels SHOULD
be 0, `encoding` MUST still be a valid range, and `statistics` (if present) MUST be `{valid_count: 0}` with no
minimum, maximum or mean. Producers SHOULD omit such layers unless their total absence is itself informative.

**Non-finite values.** NaN and infinities cannot be encoded. Samples without a finite value MUST be marked invalid.

**Equivalence with scale/offset packing (informative).** `png16_linear` is the same as the common unsigned 16-bit
linear packing `value = packed * scale_factor + add_offset`, with `scale_factor = (max - min) / 65535` and
`add_offset = min`. The netCDF best-practices guidance describes this kind of packing. Unlike that guidance, WMI reserves no
pixel value as a fill value, because validity is carried separately. WMI stores endpoints rather than scale and offset, so
that the represented range is explicit and exact.

### 6.3 `categorical`: class codes [Required]

Encoding type `png16_codes`. Fields: `class_table` (required, the local id of a class table) and `encoding: {type: "png16_codes"}`.

- PNG: 16-bit greyscale. The pixel value is the class code (0..65535).
- Every **valid** sample's code MUST appear in the referenced class table. Invalid samples are ignored.
- Codes are labels, not numbers. Consumers MUST NOT interpolate, average or decode them through a min/max range, and
  producers MUST NOT have resampled them with interpolating methods (`bilinear`, `bicubic` or `area_mean`).
- Code 0 MAY be a real class. Whether a sample is valid is expressed only by the validity mask.
- `units` and `statistics` are not used.

### 6.4 `mask`: binary feature masks [Required]

Encoding type `png8_binary`.

- PNG: 8-bit greyscale. Every pixel MUST be exactly 0 or 255.
- **Polarity is fixed: 255 means true and 0 means false.** "True" is defined by the quantity, for example "the sample is
  ocean" for `ocean_mask`. Extension mask quantities MUST state their true condition in `definition`.
- A binary mask is not a fraction. Continuous fractions (for example `snow_cover_fraction`) are scalar layers with units
  `1`.
- Masks MUST NOT be resampled with interpolating methods.

Ocean, lake and river masks are distinct quantities. A lake is never ocean, and a river mask marks rasterised channels,
not water area.

### 6.5 Validity masks [Required]

- A validity mask is an 8-bit greyscale PNG in `masks/` with exactly two values: **0 = invalid** and **255 = valid**.
- Its dimensions MUST equal the dimensions of the grid of every layer that references it. Several layers MAY share one
  validity mask.
- If a layer has no `validity_mask`, **every sample is valid**.
- Pixel values at invalid samples carry no meaning. Producers SHOULD write 0, and consumers MUST ignore them.
- Validity means only "this sample has a value". It is not an ocean mask, a confidence score or a blending weight, and
  consumers MUST NOT use it as one. A sea-surface temperature layer that is invalid on land is not a land mask.
- PNG transparency (`tRNS` or alpha) MUST NOT be used to express validity in data layers.

### 6.6 `reference`: non-numeric images [Optional]

Fields: `role` (`preview`, `legend`, `colour_key`, `illustration` or `other`), `registration` (`registered` or
`unregistered`), and optional `depicts` (a list of layer ids).

- Reference images are explicitly **non-numeric**. A consumer MUST NOT derive data values from them, and a reference image
  never substitutes for a data layer. A package of only reference images is not conformant.
- `registered`: the image is spatially aligned with `grid`, and its dimensions MUST equal the grid's.
- `unregistered`: a whole illustration, legend or colour key with no spatial meaning, and `grid` MUST be absent.
- Any valid, non-animated PNG colour type is allowed. Colour-management chunks are permitted for references.

### 6.7 Extension kinds [Optional]

A namespaced `kind` (for example `mytool:float32_tile`) lets a producer carry an output that 0.1.0 cannot express. It
requires `quantity`, `definition`, `path` (in `maps/`) and `sha256`. Validators check only its hash. Consumers report it
as unsupported unless they recognise the namespace.

## 7. PNG requirements

WMI uses PNG as defined by the W3C PNG Third Edition specification. Data layers are images of numbers, not pictures.

| Requirement | Scalar / categorical | Mask / validity mask | Reference |
|---|---|---|---|
| Colour type | 0 (greyscale) | 0 (greyscale) | any |
| Bit depth | 16 | 8 | any valid |
| `tRNS` (transparency) | MUST NOT | MUST NOT | allowed |
| Animation (`acTL`, `fcTL`, `fdAT`) | MUST NOT | MUST NOT | MUST NOT |
| Colour-management chunks | SHOULD NOT (warning) | SHOULD NOT (warning) | allowed |
| `sBIT` | SHOULD NOT (warning); ignored | SHOULD NOT; ignored | allowed |
| Interlacing (Adam7) | allowed, non-interlaced RECOMMENDED | same | allowed |
| Data after `IEND` | SHOULD NOT (warning) | SHOULD NOT | SHOULD NOT |

- 16-bit samples are big-endian, as PNG requires. Consumers MUST read the raw sample values.
- **Colour management.** For data layers, consumers MUST ignore `gAMA`, `cHRM`, `sRGB`, `iCCP`, `cICP`, `mDCV`, `cLLI` and
  `sBIT`, and MUST NOT apply gamma correction, ICC transforms, tone mapping or bit-depth reduction. Producers SHOULD NOT
  write those chunks. Many image libraries add them by default, so producers should check their output.
- Images MUST NOT be palette (colour type 3), RGB or greyscale-with-alpha for data layers, even if every pixel is grey.
- Unknown critical chunks make a PNG invalid, as in the PNG specification. Text chunks (`tEXt`, `iTXt`, `zTXt`) are
  allowed and carry no WMI meaning.

## 8. Geometry

### 8.1 Grid records

Grids are declared once in `manifest.grids` and referenced by id from layers. A package MAY declare several grids,
including different resolutions of the same area. Every layer's image dimensions MUST equal its grid's `width` and
`height`.

### 8.2 `lonlat_regular` [Required]

A regular latitude/longitude grid on the spherical body declared in `world.body`.

| Field | Status | Description |
|---|---|---|
| `type` | required | `"lonlat_regular"` |
| `width`, `height` | required | Columns and rows (1..1 048 576). |
| `bounds.west`, `bounds.east` | required | Longitudes of the outer **pixel edges**, in degrees east. |
| `bounds.north`, `bounds.south` | required | Latitudes of the outer pixel edges, in degrees north. |
| `description` | optional | |

Rules:

- Rows run **north to south** (row 0 touches `north`), and columns run **west to east** (column 0 touches `west`).
- `-180 <= west < 180`, `west < east <= west + 360`, and `-90 <= south < north <= 90`.
- Pixel centres (0-based row `r` and column `c`):

  ```
  lon(c) = west  + (c + 0.5) * (east - west)   / width
  lat(r) = north - (r + 0.5) * (north - south) / height
  ```

  Longitudes MAY be normalised to [-180, 180) with `((lon + 180) mod 360) - 180`.
- **Wrapping.** If `east - west = 360`, the grid wraps: the east edge of the last column is the west edge of the first
  column. The seam is not duplicated: there is no extra column repeating column 0.
- **Regions crossing the antimeridian** MUST be written with `east > 180`. For example, a region from 170E to 170W is
  `west: 170, east: 190`. `east <= west` is invalid. This makes the column order and the crossing explicit.
- **Poles.** A global grid (`north: 90, south: -90`) has no row centred on a pole. Pixel rows are equal in angle, not
  in area.
- Spacing is uniform in degrees, so cells are not equal-area. Consumers that resample SHOULD weight by area where it matters.

### 8.3 The body and coordinate reference

The longitude and latitude are spherical coordinates on the declared sphere of radius `world.body.radius_m`. For
fictional worlds the location of 0 degrees longitude is the producer's choice and SHOULD be described in
`world.description`.

WMI grids are not EPSG:4326 and MUST NOT be labelled with Earth coordinate reference systems unless the world really is
Earth and the data really use that datum. Earth-based reference systems are out of scope for 0.1.0.

### 8.4 Alignment

Two grids are *aligned* if they have identical bounds and each grid's width and height divides the other's, or is
divided by it, so that pixel edges nest. Alignment is informative: it tells a consumer that block aggregation or
replication is exact. The reference `wmi inspect` reports it.

### 8.5 Unsupported geometry

A namespaced grid `type` (for example `mytool:local_planar`) is allowed so that producers can carry other geometries
without misrepresenting them. Consumers that do not understand a grid type MUST report its layers as unsupported and
MUST NOT guess a geometry. Planar and projected grids are proposals ([docs/proposals/projections-and-local-grids.md](../../docs/proposals/projections-and-local-grids.md)).

### 8.6 Source resolution and resampling

The delivered resolution is the grid's. A layer MAY describe where its data came from:

```json
"source": {"width": 256, "height": 128, "resampling": "mode", "description": "Majority vote from the 256x128 simulation grid"}
```

`resampling` is one of `none`, `nearest`, `mode`, `bilinear`, `bicubic`, `area_mean`, `minimum`, `maximum` or `other`.
If it is `other`, `notes` SHOULD explain it. Categorical layers and masks MUST NOT declare an interpolating method.

## 9. Time

### 9.1 Calendars

Calendars are declared in `manifest.calendars` and referenced by id. WMI does not assume twelve months or a 365-day year.

| `kind` | Fields | Meaning |
|---|---|---|
| `fixed` | `year_length_days` (required), `periods` (optional), `day_length_s` (optional, may be `null`), `leap_rule`, `description` | Every year has the same named periods. If `periods` are given, their `length_days` MUST sum to `year_length_days`. Periods may be unequal and any number. |
| `proleptic_gregorian` | `description` only | Earth's Gregorian calendar. Its periods are the months, with ids `jan`..`dec`. |

`day_length_s` is the length of one *calendar* day in SI seconds, which on fictional worlds need not be 86 400. Units
such as `mm d-1` always use a day of exactly 86 400 s, regardless of the world's day length.

### 9.2 Time points

`{calendar, year, period?, day?, label?}`. `year` is an integer and may be zero or negative. `day` is 1-based within
`period` if a period is given, otherwise within the year. Used for `source.simulation_time` and `time.instant`.

### 9.3 Layer time

A layer's `time` object takes one of two forms:

- **Instant:** `{calendar, instant: {year, period?, day?}}`. The layer is the state at that time.
- **Aggregated:** `{calendar, span, aggregation, select_periods?, timestep_s?, label?}`.
  - `span: {start: {year, period?}, end: {year, period?}}` is the inclusive range that the statistic covers.
  - `select_periods` (optional) restricts the underlying samples to the listed periods of each year before aggregation.
    For example, `["jan"]` with "mean over timesteps within year, mean over years" is a January climatology. Each id MUST
    exist in the calendar.
  - `aggregation` is an ordered list of reductions, applied first to last.

If `time` is absent, the layer describes the state at the package snapshot (`source.simulation_time`, if given).

### 9.4 Aggregation steps

Each step is `{statistic, over, within?}`:

- `statistic`: `mean`, `minimum`, `maximum`, `sum`, `median` or `standard_deviation`.
- `over`: `timesteps` (the native time series), `days`, `periods` or `years`.
- `within` (only for `over: timesteps` or `days`): `day`, `period`, `year` or `span`. It defines the groups that each
  reduction produces.

Validity rules, checked by the reference validator:

1. A reduction over `timesteps` MUST be the first step.
2. `over: days` either starts the sequence (for daily input) or follows a step `within: day`.
3. `over: periods` needs one value per period (a previous step `within: period`). `over: years` needs one value per year
   (or per period of each year).
4. After the last step, no dimension (year, period or day) may remain, so the result is a single value per sample.
5. Steps involving periods require a calendar that has periods.

Examples, with the 30-year span `{start: {year: 1}, end: {year: 30}}`:

| Meaning | `aggregation` |
|---|---|
| Annual mean (30-year climatology) | `mean over timesteps within year`, `mean over years` |
| Mean of annual timestep minima | `minimum over timesteps within year`, `mean over years` |
| Absolute minimum over 30 years | `minimum over timesteps within span` |
| Coldest-period (e.g. coldest-month) mean | `mean over timesteps within period`, `mean over years`, `minimum over periods` |
| Mean annual total (climatological) | `sum over timesteps within year`, `mean over years` |
| Wettest-period total | `sum over timesteps within period`, `mean over years`, `maximum over periods` |
| Total over one specific year | span `1203..1203`, `sum over timesteps within span` |
| Mean of one named period (e.g. January) | `select_periods: ["jan"]`, `mean over timesteps within year`, `mean over years` |

"Timestep extremes" (the hottest instant of the year) and "extremes of period means" (the hottest month's mean) are
therefore different aggregations, and both are explicit.

### 9.5 Amounts and rates

Quantities marked *accumulated* in the registry (`rainfall_amount`, `precipitation_amount` and `snowfall_amount`) MUST
have an aggregation whose first step is `sum` over timesteps or days, and no later step may be a sum. All other scalar
quantities MUST NOT use `sum`. Rates use the `*_rate` quantities with rate units. A mean rate and a mean total are
therefore never confused.

## 10. Quantities and qualifiers

### 10.1 Registry quantities

The registry ([quantity-registry.md](quantity-registry.md)) gives, for each quantity: definition, layer kind, allowed
units, temporal semantics, vertical reference, physically valid range and a JSON Schema for its `qualifiers`.

A layer using a registry quantity MUST:

- have the registry's kind;
- use one of its allowed units;
- have `qualifiers` that satisfy the registry's qualifier schema, ignoring namespaced qualifier keys;
- satisfy its temporal semantics (`snapshot`: no aggregation; `aggregated`: aggregation required);
- have valid decoded samples within the physically valid range, allowing half a quantisation step.

Every registry quantity is optional.

### 10.2 Height

- `elevation` is signed and positive up, relative to the datum named by `qualifiers.datum` (`sea_level`, or a declared
  datum). The `coverage` qualifier is required:
  - `full`: real values everywhere, including bathymetry;
  - `land_clamped`: terrain below `clamp_value` was replaced by `clamp_value`. Those samples are not real elevations, and
    `clamp_value` is required;
  - `land_masked`: samples below sea level are invalid, so a validity mask is expected.
- `sea_floor_depth` is bathymetry, **positive down**, relative to sea level, and valid only in the ocean. It is a
  different quantity from elevation, and both MAY appear in one package.
- Sea level in physical units is 0 m on `sea_level`, or `sea_level_m` on a declared datum. The pixel value that
  corresponds to sea level is *derived* from the decode contract (and shown by `wmi inspect`). It MUST NOT be stored as an
  independent field.

### 10.3 Temperature

`air_temperature` and `surface_temperature` require `elevation_reference`: `terrain` (at the actual surface elevation) or
`sea_level_reduced` (adjusted to sea level, optionally with `lapse_rate_K_per_m` and `reduction_method`).
`air_temperature` may give `height_above_surface_m`. `sea_surface_temperature` is a separate quantity, valid only over
ocean. The statistic and period come from `time`.

### 10.4 Precipitation and snow

Liquid-only `rainfall_*`, all-phase `precipitation_*` and solid-phase `snowfall_*` quantities are distinct, each as an
amount or a rate. Snowfall is liquid water equivalent. `snow_depth` is the physical thickness of the snowpack,
`snow_water_equivalent` is the water stored in it, and `snow_cover_fraction` is a continuous fraction from 0 to 1.

### 10.5 Soil moisture

`volumetric_soil_moisture` (m3 m-3) and `soil_moisture_content` (kg m-2) require `depth_top_m`, `depth_bottom_m`
(greater than top) and `frozen_water` (`included`, `excluded` or `unknown`). A model-specific index, such as a bucket
fullness, has no physical meaning in the registry. It MUST use a namespaced quantity with a `definition` and MUST NOT be
labelled as a registry soil-moisture quantity.

### 10.6 Extension quantities

A namespaced quantity (`namespace:name`) carries any other output. It MUST have a `definition`. Its `units` SHOULD come
from the registry unit table, and validators warn otherwise. Consumers that do not recognise it report it as retained or
unsupported, never as a registry quantity. The namespace `wmi` is reserved.

## 11. Class tables

```json
"class_tables": {
  "my-biomes": {
    "taxonomy": "mytool:biomes-v2",
    "classes": [
      {"code": 0, "id": "mytool:marine_cold", "label": "Cold marine", "realm": "marine", "color": "#1F4E79"},
      {"code": 1, "id": "mytool:marine_warm", "label": "Warm marine", "realm": "marine"}
    ]
  }
}
```

- `taxonomy` is a namespaced id for the producer's classification scheme. No common taxonomy is imposed, and producers
  MUST NOT force their classes into another tool's categories. For example, marine biomes stay marine classes.
- Each class has a unique `code` (0..65535) and a unique namespaced `id`. The id SHOULD stay stable across versions of
  the taxonomy, so that consumers can map classes reliably.
- `label` is human-readable. `color` (`#RRGGBB`) is an optional display hint and MUST NOT be used to identify classes.
- `realm` (`terrestrial`, `marine`, `freshwater` or `other`) is an optional coarse hint for consumers that need one.
- Codes need not be contiguous.

Cross-taxonomy mappings are an open topic.

## 12. Integrity and sidecars

### 12.1 Hashes [Required]

Every layer and validity mask declares `sha256`, the lower-case hex SHA-256 digest of the exact file bytes. Consumers
SHOULD verify hashes, and validators MUST. The manifest itself is not hashed.

### 12.2 Sidecars [Optional]

As a convenience for tools that open single images, a producer MAY write `<image path>.json` next to an image (for example
`maps/elevation.png.json`) containing:

```json
{"format": "world-map-interchange-sidecar", "format_version": "0.1.0", "generated_from": "manifest.json",
 "layer": { ...exact copy of the manifest layer... }, "grid": { ...copy... }, "class_table": { ...copy, if any... }}
```

- Sidecars MUST be generated from the manifest. The `layer`, `grid` and `class_table` copies MUST be equal (as JSON
  values) to the manifest's.
- **The manifest is authoritative.** A sidecar that differs from it makes the package non-conformant. Consumers MUST
  NOT prefer a sidecar.
- Sidecars are not hashed and are not required.

## 13. Extensions and namespaces

- A namespace is `[a-z][a-z0-9-]{0,31}`. Tools SHOULD use their own name (for example `dayside`, `rock3`, `gleba` or
  `wcl`). Choosing a namespace does not imply that the tool has endorsed anything.
- Namespaced ids are allowed for quantities, layer kinds, grid types, taxonomies, class ids and qualifier keys, and as
  keys of `extensions` objects at manifest and layer level.
- Consumers MUST ignore namespaced content they do not recognise and SHOULD preserve it when rewriting a package.
- Namespaced content MUST NOT change the meaning of standard fields.
- The namespace `wmi` is reserved for future versions of this specification.

## 14. Versioning

`format_version` follows semantic versioning. While the major version is 0, a minor-version change may be incompatible,
and consumers MUST reject versions whose major.minor they do not implement. Patch versions are compatible. See
[COMPATIBILITY.md](../../COMPATIBILITY.md).

## 15. Relationship to other specifications (informative)

- **CF Conventions and NUG.** WMI borrows terminology from CF (standard names, cell methods, `scale_factor`/`add_offset`
  packing and binary masks) and follows the netCDF best-practices advice to state units and packing explicitly. WMI
  packages are not netCDF files, and **WMI does not claim CF compliance**. The registry's related CF names are hints
  for mapping, not equivalences.
- **PNG (W3C, Third Edition).** WMI is a profile of PNG usage: section 7 restricts which PNG features data layers may use.
- **JSON Schema Draft 2020-12.** Structural rules are machine-checkable with the published schemas. Semantic rules
  (cross-references, units, aggregation and file contents) need the validator or an equivalent implementation.

References: [NUG best practices](https://docs.unidata.ucar.edu/netcdf/NUG/best_practices.html),
[CF Conventions](https://cfconventions.org/), [PNG Third Edition](https://www.w3.org/TR/png-3/),
[JSON Schema 2020-12](https://json-schema.org/draft/2020-12).

## 16. Security considerations

Packages come from other people's tools and may be crafted. In summary: never extract unsafe names, never follow links,
bound all sizes before allocating, verify hashes before trusting content, treat text fields as untrusted strings, and do
not execute anything from a package. WMI defines no executable content.

---

## Appendix A: Minimal conformant manifest

```json
{
  "format": "world-map-interchange",
  "format_version": "0.1.0",
  "package": {
    "id": "urn:uuid:00000000-0000-4000-8000-000000000000",
    "created": "2026-10-05T12:00:00Z",
    "producer": {"name": "example-tool", "version": "1.0"},
    "license": "CC-BY-4.0"
  },
  "world": {"id": "example:my-world", "body": {"shape": "sphere", "radius_m": null}},
  "grids": {
    "global": {"type": "lonlat_regular", "width": 1024, "height": 512,
               "bounds": {"west": -180, "east": 180, "north": 90, "south": -90}}
  },
  "layers": [
    {
      "id": "elevation", "kind": "scalar", "quantity": "elevation",
      "grid": "global", "path": "maps/elevation.png", "sha256": "<64 hex digits>",
      "units": "m", "encoding": {"type": "png16_linear", "min": -11000, "max": 9000},
      "qualifiers": {"datum": "sea_level", "coverage": "full"}
    }
  ]
}
```

## Appendix B: Reference validator issue codes (informative)

| Code | Meaning |
|---|---|
| `archive.unsafe_path`, `archive.symlink`, `archive.duplicate_entry`, `archive.encrypted`, `archive.compression`, `archive.invalid`, `archive.corrupt` | ZIP container problems |
| `package.symlink`, `package.not_found`, `package.no_data_layers`, `package.unreferenced_file` (warning) | Package problems |
| `path.non_portable`, `path.reused`, `path.case_collision` | Path rules |
| `limit.entries`, `limit.file_size`, `limit.total_size`, `limit.compression_ratio`, `limit.pixels` | Resource bounds exceeded |
| `manifest.missing`, `manifest.json`, `version.format`, `version.unsupported`, `schema.manifest` | Manifest problems |
| `reference.missing` | Unknown grid, class table, calendar, period, datum or depicted layer |
| `grid.bounds`, `grid.unsupported_type` (warning) | Geometry |
| `calendar.inconsistent`, `calendar.duplicate_period`, `time.span_order`, `time.aggregation_order`, `time.aggregation_incomplete`, `time.no_periods` | Time |
| `quantity.unknown`, `quantity.kind_mismatch`, `quantity.definition_missing`, `quantity.reserved_namespace`, `units.incompatible`, `units.unrecognised` (warning), `qualifiers.invalid` | Quantities |
| `semantics.accumulation`, `semantics.time_required`, `semantics.time_forbidden`, `validity.expected` (warning) | Semantic consistency |
| `encoding.range`, `statistics.inconsistent`, `value.out_of_range` | Scalar encoding and values |
| `class.unknown_code`, `class.duplicate_code`, `class.duplicate_id` | Class tables |
| `mask.values`, `resampling.invalid_for_kind`, `resampling.undocumented` (warning) | Masks and resampling |
| `file.missing`, `hash.mismatch` | Integrity |
| `png.invalid`, `png.type`, `png.transparency`, `png.animated`, `png.colour_management` (warning), `png.sbit` (warning), `png.trailing_data` (warning), `png.interlaced` (info) | PNG |
| `dimension.mismatch` | Image and grid dimensions differ |
| `sidecar.invalid`, `sidecar.mismatch` | Sidecars |
