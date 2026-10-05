# Proposal: time-series packaging

**Status:** proposal, not in 0.1.0.

## What 0.1.0 can already do

Each layer is one 2D field. A monthly climatology can be expressed as one layer per period, each with
`select_periods: [<period>]` and aggregation `mean over timesteps within year`, then `mean over years`. This works, but it
is verbose, and consumers must reassemble the series themselves.

## Draft direction

Add a `series` record that groups layers explicitly:

```json
"series": {
  "t-monthly": {
    "quantity": "air_temperature",
    "axis": "period",
    "calendar": "aster",
    "members": [
      {"period": "thaw", "layer": "t-thaw"},
      {"period": "bloom", "layer": "t-bloom"}
    ]
  }
}
```

The members stay ordinary layers, so 0.1.0 consumers can still read each one. Alternative axes are `year` (one layer per
year) and `snapshot` (several simulation states, each with `time.instant`).

## Questions

- Do participating tools need climatological series (per period), year-by-year series, or simulation snapshots?
- Should members be required to share grid, units, encoding range and qualifiers?
- At what size should a scientific format (see [scientific-formats.md](scientific-formats.md)) be preferred over many PNGs?
