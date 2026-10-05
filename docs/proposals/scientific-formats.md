# Proposal: relationship with larger scientific formats

**Status:** proposal, not in 0.1.0.

## Position

WMI is deliberately small: a ZIP, JSON and PNG, implementable in any language without a GIS stack. It is not meant to
replace netCDF, Zarr or GeoTIFF, which handle large, multidimensional and high-precision data far better.

## Possible directions

1. **Lossless mapping documents.** Describe how a WMI package maps to a netCDF file with CF-style metadata (dimensions,
   `scale_factor`/`add_offset`, `cell_methods` and masks), and back. Useful for climate tools that already write netCDF.
   It would state precisely what does not map. For example, fictional calendars need CF's custom calendar attributes, and
   WMI qualifiers become non-standard attributes.
2. **External payloads.** Allow a layer to reference a netCDF or Zarr variable inside the package, using a namespaced
   kind first, then a standard kind if adopted.
3. **Converters only.** Keep the format unchanged and provide reference converters.

Any mapping must not claim that a WMI package is CF-compliant. Only a converted netCDF file can be checked against CF.

## Questions

- Which participating tools already read or write netCDF, GeoTIFF or Zarr?
- Is a converter (option 3) enough for now?
