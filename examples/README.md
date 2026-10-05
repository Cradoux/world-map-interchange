# Examples

Everything here is **synthetic**: it is generated from analytic formulas by
[`scripts/generate_examples.py`](../scripts/generate_examples.py), and it contains no real-world data or third-party assets.
Examples are covered by the repository's MIT licence (their manifests declare `"license": "MIT"`).

Regenerate the examples with `uv run python scripts/generate_examples.py`. CI runs it with `--check` to confirm that the
committed files match the generator.

## Valid packages (`valid/`)

| Example | Demonstrates |
|---|---|
| [elevation-bathymetry](valid/elevation-bathymetry) | Signed elevation with bathymetry relative to sea level (0 m); positive-down `sea_floor_depth` with an ocean-only validity mask; ocean, lake and river masks; a registered colour preview and an unregistered legend; sidecars; source simulation/run/snapshot ids |
| [climate-only](valid/climate-only) | No height layer. Annual mean, mean annual minimum and maximum (timestep extremes), coldest-period mean (extremum of period means), single-period (Thaw) climatology, sea-level-reduced temperature and SST; rain, snowfall and total precipitation with matching periods; wettest-period total; fictional 400-day calendar with five unequal periods |
| [snow-and-soil](valid/snow-and-soil) | Snow depth, snow water equivalent, snow-cover fraction (continuous); volumetric soil moisture 0 to 0.1 m with frozen water excluded; a producer-specific bucket index as a namespaced extension (reported as `retained`) |
| [biome-and-rock](valid/biome-and-rock) | Categorical biome and lithology with namespaced class tables; warm and cold marine biomes kept as marine classes; code 0 a valid class; non-contiguous codes; `mode` resampling from a recorded 256x128 source; registered preview and colour key |
| [multi-resolution](valid/multi-resolution) | Three aligned global grids (128x64, 64x32, 32x16); elevation on a declared datum where sea level is +120 m; temperature in kelvin; precipitation in kg m-2 with source resolution and `area_mean` resampling recorded |
| [regional-seam](valid/regional-seam) | Regional grid from 160E to 140W (`west 160, east 220`) crossing the antimeridian |
| [missing-and-zero](valid/missing-and-zero) | Missing samples (validity mask) versus legitimate zero values (0 mm rainfall, code 0 "bare ground"); a shared validity mask; an entirely missing layer |
| [constant-fields](valid/constant-fields) | Constant elevation and temperature encoded with `encoding.min` equal to the value; an all-false mask |

Expected decoded values for sample pixels are in [EXPECTED.md](EXPECTED.md) and, in machine-readable form, in
[`expected/`](expected/). Scalar values are the pre-encoding values, which a decoder must reproduce within half a
quantisation step. Each entry also gives the exact expected pixel.

`packed/` contains two of the valid examples as ZIP archives, produced with `wmi pack`.

## Invalid packages (`invalid/`)

Each one fails for a single concrete reason, recorded with its expected error code in
[`invalid/expectations.json`](invalid/expectations.json). The tests require the validator to report **exactly** that set of
error codes.

| Example | Expected error |
|---|---|
| dimension-mismatch | `dimension.mismatch`: grid 20x8, image 16x8 |
| unknown-class-code | `class.unknown_code`: a pixel uses code 7, which is not in the table |
| inconsistent-units | `units.incompatible`: air temperature in `mm` |
| amount-with-mean-aggregation | `semantics.accumulation`: an amount described by a mean |
| temperature-without-elevation-reference | `qualifiers.invalid`: terrain or sea-level reference missing |
| incomplete-aggregation | `time.aggregation_incomplete`: year and period dimensions left unreduced |
| missing-grid-reference | `reference.missing`: undeclared grid |
| missing-file | `file.missing` |
| invalid-png-depth | `png.type`: scalar stored as 8-bit |
| png-transparency | `png.transparency`: `tRNS` in a data layer |
| bad-hash | `hash.mismatch` |
| inverted-encoding-range | `encoding.range`: min > max |
| mask-not-binary | `mask.values`: value 128 in a binary mask |
| interpolated-class-codes | `resampling.invalid_for_kind`: bilinear resampling of classes |
| seam-bounds-reversed | `grid.bounds`: east < west |
| sidecar-mismatch | `sidecar.mismatch`: sidecar disagrees with the manifest |
| statistics-inconsistent | `statistics.inconsistent` |
| reference-only | `package.no_data_layers`: a preview cannot stand in for data |
| unknown-quantity | `quantity.unknown`: unnamespaced id not in the registry |
| extension-without-definition | `quantity.definition_missing` |
| unsafe-archive-path.zip | `archive.unsafe_path`: `../escape.png` |
| absolute-archive-path.zip | `archive.unsafe_path`: `/tmp/...` and `C:/...` |
| duplicate-archive-entry.zip | `archive.duplicate_entry` |
| symlink-archive-entry.zip | `archive.symlink` |
| manifest-not-at-root.zip | `manifest.missing`: everything inside a `bundle/` folder |

The archive cases are crafted to be hostile. The validator inspects them without extracting anything. Don't unpack
them with tools that follow unsafe paths.

## Consumer profiles (`profiles/`)

Illustrative capability profiles for `wmi validate --consumer`. For example, validating `climate-only` against
`heightmap-importer.json` reports the package as conformant, with the workflow requirement "elevation" unmet.

## Producer code (`code/`)

[`write_climate_package.py`](code/write_climate_package.py) is a minimal, tested climate producer. See the
[WCL exporter quick-start](../docs/wcl-exporter-quickstart.md).
