# Changelog

All notable changes to the specification, schemas, registry and reference tools. This project follows the
[compatibility policy](COMPATIBILITY.md). While versions are 0.x, minor releases may be incompatible.

## [0.1.0] - experimental draft (unreleased)

First public draft, for discussion.

### Specification
- Package layout as a ZIP or directory: `manifest.json`, `maps/`, `masks/` and `previews/`, with portable relative paths,
  no symlinks, no duplicate or case-colliding entries, and bounded-resource reading.
- Layer kinds: `scalar` (`png16_linear`), `categorical` (`png16_codes` plus class tables), `mask` (`png8_binary`, 255 = true),
  validity masks (PNG8, 0 = invalid, 255 = valid, absent = all valid), `reference` (registered or unregistered,
  non-numeric), and namespaced extension kinds.
- Scalar decode contract `min + p/65535 * (max - min)`; round-half-up encoding; no silent clipping; separate observed
  statistics; constant-field and entirely-missing-field rules; documented equivalence with scale/offset packing.
- PNG profile: colour type and bit depth per kind, no `tRNS` or animation in data layers, colour-management chunks
  ignored by consumers.
- Geometry: `lonlat_regular` grids on a declared sphere (radius may be unknown), pixel-edge bounds, exact centre formulas,
  north-to-south rows, seam wrapping without duplication, `east > 180` for antimeridian crossings, several aligned
  grids, and recorded source resolution and resampling. Other geometry must be reported, not guessed.
- Time: `fixed` and `proleptic_gregorian` calendars, including unequal periods and non-86 400 s days; time points; spans;
  ordered aggregation steps; `select_periods`; accumulation rules separating amounts from rates.
- Provenance: package id, world id, producer, creation time, simulation/run/snapshot ids, simulation time and source
  heightmap identity.
- Conformance kept separate from consumer support (`supported`, `retained` or `unsupported`) and from workflow requirements.
- SHA-256 for every payload, and optional sidecars generated from the authoritative manifest.

### Registry
- 22 quantities: elevation, sea-floor depth, ocean/lake/river masks, air/surface/sea-surface temperature,
  rainfall/precipitation/snowfall amounts and rates, snow depth, SWE, snow-cover fraction, volumetric soil moisture,
  soil moisture content, biome, lithology and land cover.

### Tools and examples
- `wmi` CLI: `validate`, `inspect`, `pack`, `rehash`, `sidecars`, `encode` and `decode`, with human-readable and JSON output.
- Eight synthetic valid examples, 25 invalid examples, consumer profiles and a tested climate producer script.
- CI: schema checks, semantic and file validation of all examples, unit tests, and generator and registry freshness checks.
