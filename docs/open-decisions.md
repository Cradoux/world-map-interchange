# Open decisions

This page lists choices made provisionally in draft 0.1.0 that need review by the participating developers, and topics
deliberately left for later. Each item should become a GitHub issue (label `decision`) when discussion starts. The
working PNG16/JSON draft does not wait on any of them.

Status key: **provisional** = in 0.1.0 but open to change; **deferred** = not in 0.1.0; **proposal** = drafted in
[proposals/](proposals/).

## A. Provisional choices in 0.1.0 that need review

| # | Topic | 0.1.0 choice | Alternatives to consider |
|---|---|---|---|
| A1 | Tie rounding in scalar encoding | Round half up: `floor(t*65535 + 0.5)` | Round half to even (numpy default) |
| A2 | Encoding fields | `encoding.min` / `encoding.max` endpoints only | `scale_factor` / `add_offset` (CF style); both forbidden together |
| A3 | Validity masks | Separate PNG8 file with 0/255, absent means all valid | Reserved pixel value (fill value); a 1-bit PNG; alpha channel |
| A4 | Binary mask depth | PNG8 0/255 | PNG 1-bit; PNG16 |
| A5 | Categorical depth | PNG16 only | Also allow PNG8 for small tables |
| A6 | Interlaced PNG | Allowed but discouraged (info) | Forbid for data layers |
| A7 | Colour-management chunks in data | Warning; consumers ignore | Make it an error |
| A8 | Grid bounds across the seam | `east > 180` (up to `west + 360`) | Allow `east < west` with a crossing flag |
| A9 | Body shape | Sphere only, radius may be `null` | Ellipsoid parameters; separate "mean radius" |
| A10 | Time model | Ordered `{statistic, over, within}` steps; calendars with named periods | CF-style `cell_methods` strings; ISO 8601 durations; day-of-year climatologies |
| A11 | Calendar kinds | `fixed` and `proleptic_gregorian` | CF calendars (`noleap`, `360_day`, ...), leap-year rules for fictional calendars |
| A12 | Accumulation rule | Amounts must start with `sum`; non-amounts may not use `sum` | Allow `sum` for derived quantities (degree days) via registry flag |
| A13 | Unit vocabulary | Small closed table in the registry | Full UDUNITS strings; per-quantity canonical units only |
| A14 | Elevation datums | `sea_level` built in; other datums declare `sea_level_m` | Time-varying sea level; geoid models |
| A15 | Elevation coverage | `full`, `land_clamped` (+`clamp_value`), `land_masked` | Separate quantities per coverage |
| A16 | Temperature height | `elevation_reference` qualifier on one quantity | Separate quantities for sea-level-reduced temperature |
| A17 | Class identity | Namespaced class ids, optional `realm` hint | Shared cross-tool biome vocabulary; published mapping tables |
| A18 | Support statuses | `supported` / `retained` / `unsupported` | Add `ignored`; per-qualifier partial support |
| A19 | Consumer profiles | Simple list of required quantity ids | Profiles with qualifier constraints (e.g. `coverage: full`) and named shared profiles |
| A20 | Sidecars | Optional `<image>.json` exact copies; manifest authoritative | Drop sidecars entirely; embed metadata in PNG `iTXt` |
| A21 | Archive extension | `.zip` recommended, none required | Register a dedicated extension / media type later |
| A22 | Package and world identity | Free-form ids, `urn:uuid:` recommended | Required UUIDs; content-addressed package ids |
| A23 | Resource limits | Validator defaults (2^28 pixels, 2 GiB/file) | Normative minimum limits every consumer must support |

## B. Deferred topics (proposals)

These are intentionally outside 0.1.0 and documented as proposals.

| Topic | Document |
|---|---|
| float32 / higher-precision rasters | [proposals/float32-rasters.md](proposals/float32-rasters.md) |
| Arbitrary projections, local planar grids, cube-sphere and icosahedral grids | [proposals/projections-and-local-grids.md](proposals/projections-and-local-grids.md) |
| Vector fields (wind, ocean currents, flow direction) | [proposals/vector-fields.md](proposals/vector-fields.md) |
| Time-series packaging (monthly/seasonal stacks, multiple snapshots) | [proposals/time-series.md](proposals/time-series.md) |
| Larger scientific formats (netCDF, Zarr, GeoTIFF/COG) | [proposals/scientific-formats.md](proposals/scientific-formats.md) |

## C. Process questions

- How are new registry quantities proposed and accepted? (Draft: [CONTRIBUTING.md](../CONTRIBUTING.md) and [GOVERNANCE.md](../GOVERNANCE.md).)
- Should the repository move to a neutral organisation once several tools participate?
- What evidence (for example, two independent implementations) is needed before a feature leaves "experimental"?
