# Proposals

These documents describe possible future extensions. They are **not part of 0.1.0** and do not block the working
PNG16/JSON draft. Each is a starting point for discussion. Please comment through
[proposal issues](https://github.com/Cradoux/world-map-interchange/issues/new?template=proposal.yml).

| Proposal | Summary |
|---|---|
| [float32-rasters.md](float32-rasters.md) | Exact floating-point layers for scientific precision |
| [projections-and-local-grids.md](projections-and-local-grids.md) | Planar, projected and non-rectangular global grids |
| [vector-fields.md](vector-fields.md) | Wind, currents and flow as paired components |
| [time-series.md](time-series.md) | Many periods or snapshots in one package |
| [scientific-formats.md](scientific-formats.md) | Relationship with netCDF, Zarr and GeoTIFF |

Until a proposal is adopted, producers can carry such data with **namespaced extension kinds or grid types** (spec
sections 6.7 and 8.5). Consumers then report it as unsupported rather than misreading it.
