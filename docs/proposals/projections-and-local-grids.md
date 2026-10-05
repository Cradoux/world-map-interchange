# Proposal: projections, local planar grids and other global grids

**Status:** proposal, not in 0.1.0. Version 0.1.0 defines only `lonlat_regular` on a sphere.

## Why not in 0.1.0

Defining projections properly means choosing a projection vocabulary (PROJ strings, WKT2, or a small closed list),
handling ellipsoids, and stating datum behaviour for fictional bodies. Doing that badly is worse than not doing it:
consumers would guess. Version 0.1.0 therefore requires unsupported geometry to be **reported, not guessed**. A producer
may declare a namespaced grid type (for example `mytool:local_planar`), and consumers that do not recognise it mark its
layers unsupported.

## Candidate grid types

### `planar_regular` (local flat maps)

Many terrain tools work on a flat tile measured in metres with no planetary context.

```json
{"type": "planar_regular", "width": 4096, "height": 4096,
 "cell_size_m": [10.0, 10.0],
 "origin_m": {"x": 0.0, "y": 0.0}, "origin_corner": "north_west",
 "axis": {"x": "east", "y": "north"},
 "placement": null}
```

Open questions: Should rows still run north to south, or should `y` follow the image convention? How should a planar
tile optionally be placed on a planet (centre latitude and longitude, plus a projection)?

### `projected_regular`

A regular grid in a named projection on the declared body: equal-area cylindrical, Lambert azimuthal equal-area or polar
stereographic. Proposed as a small closed list with explicit parameters, rather than arbitrary PROJ strings, so that
fictional bodies do not inherit Earth defaults.

### Non-rectangular global grids

Cube-sphere faces, icosahedral or hexagonal grids and HEALPix. Possibly one image per face plus a face layout record.

## Questions

- Which participating tools work natively on planar tiles, cube-spheres or other layouts?
- Is a closed list of projections acceptable?
- Should 0.2 add only `planar_regular` first?
