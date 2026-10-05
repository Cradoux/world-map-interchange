# Proposal: vector fields (wind, currents, flow)

**Status:** proposal, not in 0.1.0.

## Problem

Wind, ocean currents and surface flow are vectors. Storing speed and direction as two scalars is lossy for averaging
(the mean direction is not the mean of directions), and component conventions differ between tools:
"from" versus "to" directions, and grid-relative versus east/north components.

## Draft direction

- Add a layer kind `vector2`, referencing **two scalar component layers**: `eastward` and `northward`, in the same
  units and encoding conventions as other scalars. A wrapper layer would name the pair:

  ```json
  {"id": "wind-10m", "kind": "vector2", "quantity": "wind_velocity",
   "components": {"eastward": "wind-10m-u", "northward": "wind-10m-v"},
   "qualifiers": {"height_above_surface_m": 10}}
  ```

- Components are always east/north relative to the sphere, never grid-relative, for `lonlat_regular`.
- Registry entries would include `eastward_wind`, `northward_wind`, `eastward_sea_water_velocity` and
  `northward_sea_water_velocity`, related to CF names.
- Flow direction for rivers (D8 codes and similar) is categorical, not vector, and may need its own registry entry.

## Questions

- Which tools produce wind or currents today, and in what form (components, or speed plus direction)?
- Are time-mean vectors enough, or are statistics such as prevailing direction needed?
- Is a 0.1.0-compatible interim, two registry scalar quantities without a wrapper, enough to start?
