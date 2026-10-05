# Quantity registry (experimental draft 0.1.0)

<!-- Generated from registry/0.1.0/quantities.json by scripts/render_registry.py. Do not edit by hand. -->

The machine-readable source of truth is [`registry/0.1.0/quantities.json`](../../registry/0.1.0/quantities.json).
This page is generated from it.

- Every quantity is optional. A bundle may contain any subset, and consumers decide which quantities a workflow requires.
- Quantity identifiers without a namespace are reserved for this registry. Tools use namespaced identifiers (for example 'mytool:soil_moisture_index') for anything else.
- Related CF standard names are informative. The definitions here are authoritative for WMI, and WMI bundles do not claim CF compliance.
- The unit 'd' always means 86400 SI seconds, never a local solar day of a fictional world.

## Contents

- [`elevation`](#elevation): Surface elevation (scalar)
- [`sea_floor_depth`](#sea_floor_depth): Sea-floor depth (bathymetry) (scalar)
- [`ocean_mask`](#ocean_mask): Ocean mask (mask)
- [`lake_mask`](#lake_mask): Lake mask (mask)
- [`river_mask`](#river_mask): River mask (mask)
- [`air_temperature`](#air_temperature): Near-surface air temperature (scalar)
- [`surface_temperature`](#surface_temperature): Surface (skin) temperature (scalar)
- [`sea_surface_temperature`](#sea_surface_temperature): Sea-surface temperature (scalar)
- [`rainfall_amount`](#rainfall_amount): Rainfall amount (liquid only) (scalar)
- [`rainfall_rate`](#rainfall_rate): Rainfall rate (liquid only) (scalar)
- [`precipitation_amount`](#precipitation_amount): Total precipitation amount (all phases) (scalar)
- [`precipitation_rate`](#precipitation_rate): Total precipitation rate (all phases) (scalar)
- [`snowfall_amount`](#snowfall_amount): Snowfall amount (liquid water equivalent) (scalar)
- [`snowfall_rate`](#snowfall_rate): Snowfall rate (liquid water equivalent) (scalar)
- [`snow_depth`](#snow_depth): Snow depth (scalar)
- [`snow_water_equivalent`](#snow_water_equivalent): Snow water equivalent (scalar)
- [`snow_cover_fraction`](#snow_cover_fraction): Snow-cover fraction (scalar)
- [`volumetric_soil_moisture`](#volumetric_soil_moisture): Volumetric soil moisture (scalar)
- [`soil_moisture_content`](#soil_moisture_content): Soil moisture content (scalar)
- [`biome`](#biome): Biome (categorical)
- [`lithology`](#lithology): Lithology / rock type (categorical)
- [`land_cover`](#land_cover): Land cover (categorical)

## Units

| unit | dimension | to canonical | description |
|---|---|---|---|
| `m` | length | x 1 | metre |
| `km` | length | x 1000 | kilometre |
| `cm` | length | x 0.01 | centimetre |
| `mm` | length | x 0.001 | millimetre (for water amounts: liquid water equivalent depth) |
| `K` | temperature | x 1 | kelvin |
| `degC` | temperature | x 1 + 273.15 | degree Celsius |
| `kg m-2` | areal_mass | x 1 | kilogram per square metre; for liquid water 1 kg m-2 corresponds to 1 mm depth |
| `kg m-2 s-1` | areal_mass_flux | x 1 | kilogram per square metre per second |
| `mm s-1` | length_rate | x 0.001 | millimetre (liquid water equivalent) per SI second |
| `mm h-1` | length_rate | x 2.77778e-07 | millimetre per hour (3600 s) |
| `mm d-1` | length_rate | x 1.15741e-08 | millimetre per day of exactly 86400 s |
| `1` | dimensionless | x 1 | dimensionless fraction or index |
| `m3 m-3` | volume_fraction | x 1 | cubic metre of water per cubic metre of soil |

## elevation

**Surface elevation**: scalar layer.

Signed vertical distance of the top of the solid surface above the vertical datum named by the 'datum' qualifier, positive upwards. On land this is the terrain surface; in the ocean it is the sea floor. If the datum is 'sea_level' the value is elevation relative to sea level, and sea level is exactly 0 m. If the datum is declared in world.vertical_datums, elevation relative to sea level is the value minus that datum's sea_level_m.

- Units: `m`, `km` (canonical `m`)
- Positive direction: up
- Temporal semantics: Snapshot: state at one time. Aggregation is not allowed.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Vertical reference: Required 'datum' qualifier. Sea level in physical units is 0 for 'sea_level', or the declared sea_level_m of another datum. Any pixel value corresponding to sea level is derived from the decode contract and is never stored as a separate authority.
- Related CF standard name (informative): `surface_altitude` (CF surface_altitude is relative to the geoid. WMI elevation uses an explicitly declared datum.)

| qualifier | status | values | meaning |
|---|---|---|---|
| `datum` | **required** | string | 'sea_level', or the id of an entry in world.vertical_datums. |
| `coverage` | **required** | `full` \| `land_clamped` \| `land_masked` | 'full': real values everywhere, including bathymetry below sea level. 'land_clamped': terrain below the clamp value was replaced by clamp_value, so samples equal to clamp_value are not real elevations. 'land_masked': sub-sea-level areas are marked invalid by the validity mask. |
| `clamp_value` | optional | number | Required for land_clamped. The value, in layer units relative to the datum, written in place of clamped terrain. |
| `surface` | optional | `top_of_solid_surface` \| `bedrock` \| `unspecified` | Whether ice sheets are included (top of solid surface) or removed (bedrock). |
| `lake_treatment` | optional | `lake_bed` \| `lake_surface` \| `unspecified` | Whether lake areas give the lake bed or the water surface. |

Conditional rule: `clamp_value` is required when `coverage` is `land_clamped`.

## sea_floor_depth

**Sea-floor depth (bathymetry)**: scalar layer.

Vertical distance of the sea floor below sea level, positive downwards. It is valid only where a sample is ocean, and land samples must be invalid. This quantity is distinct from elevation: a sea floor 3000 m below sea level has sea_floor_depth +3000 m and elevation -3000 m.

- Units: `m`, `km` (canonical `m`)
- Physically valid range (canonical units): 0 to +inf
- Positive direction: down
- Temporal semantics: Snapshot: state at one time. Aggregation is not allowed.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Vertical reference: Always relative to sea level, so sea level is 0 m depth.
- Related CF standard name (informative): `sea_floor_depth_below_sea_level`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## ocean_mask

**Ocean mask**: mask layer.

Binary mask. 255 means the sample is ocean (sea water connected to the world ocean, including marginal seas) and 0 means it is not. Lakes and rivers are never ocean. Use lake_mask and river_mask for those.

- Temporal semantics: Snapshot: state at one time. Aggregation is not allowed.
- Related CF standard name (informative): `sea_binary_mask`

| qualifier | status | values | meaning |
|---|---|---|---|
| `classification` | optional | `cell_centre` \| `majority` \| `any` \| `unspecified` | How a partially covered cell was classified. |

## lake_mask

**Lake mask**: mask layer.

Binary mask. 255 means the sample is an inland standing water body (lake or reservoir, fresh or saline) not connected to the ocean, and 0 means it is not.

- Temporal semantics: Snapshot: state at one time. Aggregation is not allowed.

| qualifier | status | values | meaning |
|---|---|---|---|
| `classification` | optional | `cell_centre` \| `majority` \| `any` \| `unspecified` |  |

## river_mask

**River mask**: mask layer.

Binary mask. 255 means the sample contains a rasterised river channel and 0 means it does not. Rivers are usually narrower than a cell, so this marks network presence, not channel area.

- Temporal semantics: Snapshot: state at one time. Aggregation is not allowed.

| qualifier | status | values | meaning |
|---|---|---|---|
| `rasterisation` | optional | string | How the network was rasterised, for example a minimum drainage-area threshold. |

## air_temperature

**Near-surface air temperature**: scalar layer.

Temperature of the air near the surface. The statistic (mean, minimum, maximum and so on) and its period are given by the layer's time block, or the value is a snapshot when time is absent.

- Units: `K`, `degC` (canonical `K`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Vertical reference: Required 'elevation_reference' qualifier: 'terrain' means the value applies at the actual surface elevation. 'sea_level_reduced' means it has been adjusted to sea level, for example with a lapse rate.
- Related CF standard name (informative): `air_temperature`

| qualifier | status | values | meaning |
|---|---|---|---|
| `elevation_reference` | **required** | `terrain` \| `sea_level_reduced` |  |
| `height_above_surface_m` | optional | number >= 0 | Measurement height above the surface, for example 2. |
| `lapse_rate_K_per_m` | optional | number | Lapse rate used for sea-level reduction, if constant. |
| `reduction_method` | optional | string |  |

## surface_temperature

**Surface (skin) temperature**: scalar layer.

Temperature of the surface itself (ground, ice, snow or water skin), not of the air above it.

- Units: `K`, `degC` (canonical `K`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Vertical reference: Required 'elevation_reference' qualifier, as for air_temperature.
- Related CF standard name (informative): `surface_temperature`

| qualifier | status | values | meaning |
|---|---|---|---|
| `elevation_reference` | **required** | `terrain` \| `sea_level_reduced` |  |
| `lapse_rate_K_per_m` | optional | number |  |
| `reduction_method` | optional | string |  |

## sea_surface_temperature

**Sea-surface temperature**: scalar layer.

Temperature of sea water near the ocean surface. Valid only for ocean samples, and land samples must be invalid. This is distinct from air temperature over the ocean.

- Units: `K`, `degC` (canonical `K`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Related CF standard name (informative): `sea_surface_temperature`

| qualifier | status | values | meaning |
|---|---|---|---|
| `depth_m` | optional | number >= 0 | Representative depth, if known. |

## rainfall_amount

**Rainfall amount (liquid only)**: scalar layer.

Accumulated liquid precipitation (rain and drizzle) only, expressed as liquid water depth or mass per area. The accumulation period is given by the first aggregation step, which must be a sum.

- Units: `mm`, `m`, `kg m-2` (canonical `kg m-2`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Aggregated: `time.span` and `time.aggregation` are required.
- Accumulated amount: the first aggregation step must be a `sum` over timesteps or days, and no later step may be a sum.
- Related CF standard name (informative): `rainfall_amount`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## rainfall_rate

**Rainfall rate (liquid only)**: scalar layer.

Rate of liquid precipitation as water depth or mass per area per time. Aggregation statistics apply to the rate itself (for example the mean rate), never a sum.

- Units: `kg m-2 s-1`, `mm s-1`, `mm h-1`, `mm d-1` (canonical `kg m-2 s-1`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Related CF standard name (informative): `rainfall_flux`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## precipitation_amount

**Total precipitation amount (all phases)**: scalar layer.

Accumulated precipitation of all phases (rain, snow, sleet, hail) as liquid water equivalent. The accumulation period is given by the first aggregation step, which must be a sum.

- Units: `mm`, `m`, `kg m-2` (canonical `kg m-2`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Aggregated: `time.span` and `time.aggregation` are required.
- Accumulated amount: the first aggregation step must be a `sum` over timesteps or days, and no later step may be a sum.
- Related CF standard name (informative): `precipitation_amount`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## precipitation_rate

**Total precipitation rate (all phases)**: scalar layer.

Rate of precipitation of all phases as liquid water equivalent.

- Units: `kg m-2 s-1`, `mm s-1`, `mm h-1`, `mm d-1` (canonical `kg m-2 s-1`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Related CF standard name (informative): `precipitation_flux`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## snowfall_amount

**Snowfall amount (liquid water equivalent)**: scalar layer.

Accumulated solid precipitation as liquid water equivalent. This is not the depth of fresh snow, and not snow depth on the ground. The first aggregation step must be a sum.

- Units: `mm`, `m`, `kg m-2` (canonical `kg m-2`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Aggregated: `time.span` and `time.aggregation` are required.
- Accumulated amount: the first aggregation step must be a `sum` over timesteps or days, and no later step may be a sum.
- Related CF standard name (informative): `snowfall_amount`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## snowfall_rate

**Snowfall rate (liquid water equivalent)**: scalar layer.

Rate of solid precipitation as liquid water equivalent.

- Units: `kg m-2 s-1`, `mm s-1`, `mm h-1`, `mm d-1` (canonical `kg m-2 s-1`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Related CF standard name (informative): `snowfall_flux`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## snow_depth

**Snow depth**: scalar layer.

Physical thickness of the snowpack on the ground. This is not water equivalent.

- Units: `m`, `cm`, `mm` (canonical `m`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Related CF standard name (informative): `surface_snow_thickness`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## snow_water_equivalent

**Snow water equivalent**: scalar layer.

Mass of water stored in the snowpack per unit area, or the equivalent liquid water depth.

- Units: `kg m-2`, `mm`, `m` (canonical `kg m-2`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Related CF standard name (informative): `surface_snow_amount`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## snow_cover_fraction

**Snow-cover fraction**: scalar layer.

Fraction of the cell area covered by snow, from 0 to 1. This is a continuous fraction, not a binary mask.

- Units: `1` (canonical `1`)
- Physically valid range (canonical units): 0 to 1
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Related CF standard name (informative): `surface_snow_area_fraction`

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## volumetric_soil_moisture

**Volumetric soil moisture**: scalar layer.

Volume of water per volume of soil within the declared soil layer.

- Units: `m3 m-3` (canonical `m3 m-3`)
- Physically valid range (canonical units): 0 to 1
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Vertical reference: Required depth_top_m and depth_bottom_m, measured below the surface.
- Related CF standard name (informative): `volume_fraction_of_condensed_water_in_soil`

| qualifier | status | values | meaning |
|---|---|---|---|
| `depth_top_m` | **required** | number >= 0 |  |
| `depth_bottom_m` | **required** | number > 0 |  |
| `frozen_water` | **required** | `included` \| `excluded` \| `unknown` | Whether soil ice counts as moisture. |

## soil_moisture_content

**Soil moisture content**: scalar layer.

Mass of water per unit area contained in the declared soil layer.

- Units: `kg m-2`, `mm` (canonical `kg m-2`)
- Physically valid range (canonical units): 0 to +inf
- Temporal semantics: Any: either a snapshot or an aggregation.
- Not an accumulation: `sum` is not allowed in its aggregation.
- Vertical reference: Required depth_top_m and depth_bottom_m, measured below the surface.
- Related CF standard name (informative): `mass_content_of_water_in_soil_layer`

| qualifier | status | values | meaning |
|---|---|---|---|
| `depth_top_m` | **required** | number >= 0 |  |
| `depth_bottom_m` | **required** | number > 0 |  |
| `frozen_water` | **required** | `included` \| `excluded` \| `unknown` |  |

## biome

**Biome**: categorical layer.

Biome or ecoregion class from the producer's own taxonomy, declared in the referenced class table. Marine, freshwater and terrestrial biomes may coexist in one table, and no common taxonomy is imposed.

- Temporal semantics: Any: either a snapshot or an aggregation.

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.

## lithology

**Lithology / rock type**: categorical layer.

Rock or sediment type class from the producer's own taxonomy, declared in the referenced class table.

- Temporal semantics: Snapshot: state at one time. Aggregation is not allowed.

| qualifier | status | values | meaning |
|---|---|---|---|
| `level` | optional | `surface` \| `bedrock` \| `unspecified` | Whether classes describe exposed surface material or underlying bedrock. |

## land_cover

**Land cover**: categorical layer.

Observed or simulated surface cover class (for example forest, bare rock, ice or water) from the producer's taxonomy. This is distinct from biome, which describes ecological or climatic potential.

- Temporal semantics: Any: either a snapshot or an aggregation.

No registry qualifiers. Namespaced qualifiers such as `mytool:note` are always allowed.
