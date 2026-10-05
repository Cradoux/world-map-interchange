# World Map Interchange (WMI)

**A proposed, open map-interchange format for worldbuilding and terrain tools.**
Status: **experimental draft 0.1.0, open for discussion.** This is not an established or endorsed standard.

WMI aims to give tools one portable package that holds whichever maps an application produces: elevation, climate, classes
and masks, plus optional visual references. The package carries enough metadata for another application to interpret the
numbers without reverse-engineering colour ramps.

- **Simple container.** An ordinary ZIP (or the same layout as a folder) with `manifest.json` and PNG files.
- **Numbers, not pictures.** Scalars are true 16-bit greyscale PNGs with an explicit linear decode range and units.
  Classes have explicit tables. Validity is a separate mask.
- **Explicit meaning.** A quantity registry distinguishes, for example, air from sea-surface temperature, terrain-level
  from sea-level-reduced values, rain from total precipitation, amounts from rates, and signed elevation from
  positive-down depth.
- **Nothing mandatory.** A climate-only package is valid. Whether a workflow *needs* height is up to the consumer.
- **Room for every tool.** Namespaced extensions keep producer-specific outputs and taxonomies, so tools need not claim
  semantics they don't share.

## About this proposal

The draft was started by the developer of [Dayside](#scope) as a basis for discussion with developers of other
worldbuilding, terrain and climate tools, including Rock3, Gleba and World Climate Lab. **Naming a tool here does not mean
its developer has endorsed this draft or committed to implementing it.** The goal is joint development with equal
technical input from each participating tool ([GOVERNANCE.md](GOVERNANCE.md)).

## Adding WMI to your software

WMI is meant to be built into existing tools: exporters, importers, or both. It is MIT licensed, so you can implement it
or reuse this repository's code, schemas and registry in open or closed source products (keep the licence notice with
copied files).

- **[Integration guide](docs/integration-guide.md)**: a step-by-step procedure for developers. Inventory your maps, map
  your geometry, implement export and import (Python library, CLI subprocess or native code in any language), test against
  the shared fixtures, and check against a definition of done.
- **[AGENTS.md](AGENTS.md)**: the same procedure as rules and key facts for AI coding agents, plus a
  [ready-made prompt](docs/integration-guide.md#12-handing-this-task-to-a-coding-agent) for handing the task to one.
  [llms.txt](llms.txt) indexes the documentation for LLM tools.
- **Fixtures**: [examples/expected/](examples/expected/) gives decoded values for sample pixels in every valid example,
  and [examples/invalid/](examples/invalid/) holds packages your reader must refuse. Both work for testing implementations in
  any language.

## Contents

| Path | What |
|---|---|
| [spec/0.1.0/specification.md](spec/0.1.0/specification.md) | Normative draft specification |
| [spec/0.1.0/quantity-registry.md](spec/0.1.0/quantity-registry.md) | Quantity registry (generated from [registry/0.1.0/quantities.json](registry/0.1.0/quantities.json)) |
| [schemas/0.1.0/](schemas/0.1.0/) | JSON Schema 2020-12: manifest, sidecar, registry, consumer capabilities, validation report |
| [docs/integration-guide.md](docs/integration-guide.md) / [AGENTS.md](AGENTS.md) | Adding WMI to existing software, for developers and coding agents |
| [docs/producer-guide.md](docs/producer-guide.md) / [docs/consumer-guide.md](docs/consumer-guide.md) | Producer and consumer rules in depth |
| [docs/wcl-exporter-quickstart.md](docs/wcl-exporter-quickstart.md) | Quick-start for numeric climate exports |
| [docs/open-decisions.md](docs/open-decisions.md) | Provisional choices that need review, and deferred topics |
| [docs/proposals/](docs/proposals/) | float32, projections, vector fields, time series, scientific formats |
| [examples/](examples/) | Synthetic valid and invalid packages, and [expected decoded values](examples/EXPECTED.md) |
| [src/world_map_interchange/](src/world_map_interchange/) | Reference Python package and `wmi` CLI |

## Quick start

Requires Python 3.10+. With [uv](https://docs.astral.sh/uv/), which uses the committed lock file for a reproducible
environment:

```bash
git clone https://github.com/Cradoux/world-map-interchange
cd world-map-interchange
uv sync --locked
uv run wmi validate examples/valid/climate-only
uv run wmi inspect examples/valid/elevation-bathymetry
uv run pytest
```

Or with pip:

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
wmi validate examples/packed/climate-only.zip
```

The runtime dependencies are only `numpy`, `pillow` and `jsonschema`. No GIS stack is required.

### CLI

```text
wmi validate PATH [--json] [--strict] [--consumer PROFILE.json]   check a folder or ZIP
wmi inspect  PATH [--json]                                        summarise grids, layers, time, derived sea level
wmi pack     DIR OUT.zip                                          validate, then write a deterministic ZIP
wmi rehash   DIR                                                  fill in SHA-256 values
wmi sidecars DIR                                                  write per-image JSON copies from the manifest
wmi encode   VALUES.npy|csv OUT.png --min A --max B | --auto-range encode physical values to PNG16 (never clips)
wmi decode   PKG --layer ID [--sample ROW COL] [-o out.npy|csv]    decode a layer (invalid samples become NaN)
```

`validate` exits with 0 if the package is conformant, 1 if not, and 2 on usage errors. `--json` emits a report matching
[`validation-report.schema.json`](schemas/0.1.0/validation-report.schema.json). The report keeps package conformance
separate from layer support (`supported`, `retained` or `unsupported`) for a given consumer profile.

### A package at a glance

```text
my-world.zip
├── manifest.json
├── maps/elevation.png         16-bit greyscale, value = min + p/65535 * (max - min)
├── maps/t-annual-mean.png
├── maps/biome.png             16-bit class codes, explained by a class table in the manifest
├── maps/ocean.png             8-bit mask, 255 = ocean
├── masks/ocean-only.png       8-bit validity, 0 = invalid, 255 = valid
└── previews/elevation.png     optional colour preview (never numeric data)
```

## What 0.1.0 supports

- ZIP or directory packages with safe-path, no-symlink and bounded-resource rules.
- Layer kinds: `scalar` (PNG16 linear), `categorical` (PNG16 codes and class tables), `mask` (PNG8 0/255), validity
  masks, and `reference` images (registered or unregistered).
- Regular latitude/longitude grids on a declared sphere (or one of unknown radius), with exact pixel-centre formulas,
  seam and antimeridian rules, and several aligned resolutions per package.
- Calendars, including fictional ones, plus explicit time statistics (annual means, timestep extremes, extremes of period
  means, totals and single-period climatologies).
- A registry for elevation, bathymetry, ocean, lake and river masks, temperatures, rain, total precipitation, snowfall,
  snow, soil moisture, biome, lithology and land cover.
- Namespaced extensions for quantities, kinds, grid types and metadata.
- SHA-256 integrity and optional generated sidecars.

Not in 0.1.0 (see [proposals](docs/proposals/)): float32 rasters, projections and planar grids, vector fields,
time-series packaging and scientific-format mappings.

## Scope

This repository is independent of any one application. It contains no application source code or private data, and every
example is synthetic. **Bulk import/export adapters for specific applications, including Dayside, are separate follow-up
work** and are not part of this repository.

## Contributing

Discussion is the main contribution at this stage. Please open an issue:
[proposal](https://github.com/Cradoux/world-map-interchange/issues/new?template=proposal.yml),
[ambiguity in the draft](https://github.com/Cradoux/world-map-interchange/issues/new?template=ambiguity.yml) or
[interoperability failure](https://github.com/Cradoux/world-map-interchange/issues/new?template=interoperability-failure.yml).
See [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md), [COMPATIBILITY.md](COMPATIBILITY.md) and
[CHANGELOG.md](CHANGELOG.md).

## Licence

[MIT](LICENSE), chosen for the widest possible adoption. It covers the specification, schemas, registry, reference code,
tests and synthetic examples. Implementing the format needs no permission. If you copy files from this repository into
your product, keep the MIT notice with them.

A WMI package's map data is licensed separately, by its producer, through the package's `package.license` field (an
SPDX expression). Datasets or packages contributed to discussions here keep the licence their contributors declare.

References: [CF Conventions](https://cfconventions.org/) (terminology only; WMI does not claim CF compliance),
[netCDF best practices](https://docs.unidata.ucar.edu/netcdf/NUG/best_practices.html), [PNG Third Edition](https://www.w3.org/TR/png-3/),
[JSON Schema 2020-12](https://json-schema.org/draft/2020-12).
