# Proposal: float32 rasters

**Status:** proposal, not in 0.1.0.

## Motivation

PNG16 linear packing gives 65 536 levels. That is ample for most worldbuilding maps (0.3 m steps over a 20 km elevation
range), but some cases want more:

- fields spanning many orders of magnitude (discharge, erosion rates);
- derivatives (slope, curvature) where quantisation noise is amplified;
- round trips through several tools, where requantising repeatedly accumulates error.

## Options

1. **Raw little-endian float32 with a small header** (for example `.f32` plus dimensions in the manifest). Trivial to read
   and write, but uncompressed unless the file is deflated inside the ZIP. NaN could denote invalid samples, but WMI would
   keep validity masks for consistency.
2. **TIFF / GeoTIFF float32.** Widely supported, but the format is large and has many variants. A strict profile would be
   needed (one strip or tile layout, no colour handling, specific compression).
3. **Split float into two PNG16 planes.** Avoids a new container, but is awkward and error-prone.
4. **NumPy `.npy`.** Simple and well specified, but Python-centric.

## Draft direction

Add a scalar encoding type, for example `f32le_raw` (row-major, north to south, little-endian IEEE-754 binary32), with
`width x height x 4` bytes and an explicit `byte_order`. Keep `units`, validity masks, statistics and hashes exactly as
for `png16_linear`. NaN in a valid sample would be an error.

## Questions

- Which participating tools would produce float32, and for which quantities?
- Is a dependency-free raw format preferred over TIFF?
- Should float64 also be allowed?
