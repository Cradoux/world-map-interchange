# Quick-start: numeric climate export (for World Climate Lab)

This page sketches how a climate tool such as World Climate Lab (WCL) could export numeric climate maps as a World Map
Interchange (WMI) 0.1.0 package. It is a **suggestion to support discussion**. It is not an agreed plan, and it does not
imply that WCL's developer has endorsed WMI or committed to implementing it. Mappings below are written as "if your model
produces X". Corrections from the WCL side are very welcome as
[issues](https://github.com/Cradoux/world-map-interchange/issues/new/choose).

A climate-only package is fully valid. No heightmap is needed. A consumer that requires height reports that as a
workflow requirement, not as a defect in the package.

## 1. What a first export needs

| If the model produces... | WMI quantity | Units | `time.aggregation` (with `span` = the climatology years) |
|---|---|---|---|
| Annual mean near-surface air temperature | `air_temperature` | `degC` or `K` | mean over timesteps within year, then mean over years |
| Mean of each year's lowest timestep temperature | `air_temperature` | same | **minimum** over timesteps within year, then mean over years |
| Mean of each year's highest timestep temperature | `air_temperature` | same | **maximum** over timesteps within year, then mean over years |
| Coldest month (period) mean | `air_temperature` | same | mean over timesteps within period, mean over years, **minimum over periods** |
| Warmest month (period) mean | `air_temperature` | same | mean over timesteps within period, mean over years, **maximum over periods** |
| Mean temperature of one named month (period) | `air_temperature` | same | `select_periods: ["<id>"]`; mean over timesteps within year, then mean over years |
| Sea-surface temperature | `sea_surface_temperature` | `degC` or `K` | as above. Mark land invalid with a validity mask. |
| Annual rainfall (liquid only) | `rainfall_amount` | `mm` or `kg m-2` | **sum** over timesteps within year, then mean over years |
| Annual snowfall (water equivalent) | `snowfall_amount` | `mm` or `kg m-2` | same as rainfall |
| Annual total precipitation (all phases) | `precipitation_amount` | `mm` or `kg m-2` | same as rainfall |
| Mean precipitation rate | `precipitation_rate` | `kg m-2 s-1`, `mm d-1`, ... | mean over timesteps within year, then mean over years |
| Soil water as a volume fraction of a layer | `volumetric_soil_moisture` | `m3 m-3` | any; qualifiers `depth_top_m`, `depth_bottom_m`, `frozen_water` |
| A model "wetness" or bucket index without physical units | `wcl:<name>` (extension) | `1` | any; **`definition` required** |
| Biome classes, including marine biomes | `biome` | (class table) | optional |
| Snow depth / snow water equivalent / snow cover | `snow_depth` / `snow_water_equivalent` / `snow_cover_fraction` | `m` / `kg m-2` / `1` | any |

The `wcl:` namespace is only a suggestion. Any namespace that identifies the tool works.

## 2. Decisions to state explicitly

These are the details most likely to be misread by another tool. Each one has a field:

1. **Temperature height reference.** Is the temperature at the actual terrain elevation (`elevation_reference: terrain`),
   or reduced to sea level (`sea_level_reduced`, ideally with `lapse_rate_K_per_m`)? This is required.
2. **Which statistic.** "Annual minimum" can mean the mean of daily or timestep minima, the coldest instant, or the coldest
   month's mean. Pick the aggregation that matches the computation. The table above covers the common cases.
3. **Climatology or single period.** A 30-year mean annual total uses `span` 1..30 with "sum within year, mean over
   years". The total for one specific year uses `span` 1203..1203 with "sum within span".
4. **Rain, snow and total.** Use the same `span`, `aggregation` and encoding range for all three. Consumers can then check
   that rain + snowfall is approximately total.
5. **Calendar.** If the model uses 12 equal months of 30 days, declare exactly that (`kind: fixed`, `year_length_days: 360`,
   twelve 30-day periods). For a fictional calendar, declare its real year length, period names and lengths, and
   `day_length_s`. For Earth runs on real dates, use `proleptic_gregorian`.
6. **Marine biomes.** Keep marine biome classes as they are in WCL's own taxonomy (with `realm: "marine"` if helpful).
   Nothing in WMI asks for them to be mapped into terrestrial categories.
7. **Soil moisture meaning.** If it is a physical volume fraction or mass, give the layer depth and frozen-water treatment.
   If it is a model index, export it as a namespaced extension with a definition.
8. **Planet radius.** Set `world.body.radius_m` if the model uses one. Otherwise use `null`. Do not default to Earth.

## 3. Minimal steps

```bash
git clone https://github.com/Cradoux/world-map-interchange
cd world-map-interchange
uv sync                                     # or: pip install -e .
uv run python examples/code/write_climate_package.py out/my-climate
uv run wmi validate out/my-climate
uv run wmi inspect out/my-climate
uv run wmi pack out/my-climate out/my-climate.zip
```

[`examples/code/write_climate_package.py`](../examples/code/write_climate_package.py) is a complete, tested producer for
annual mean, minimum and maximum temperature, rain, snowfall, total precipitation and an ocean mask. Replace its
synthetic arrays with model output. In outline:

```python
from world_map_interchange import encode
from world_map_interchange.png import write_png

pixels = encode(t_mean_degC, -90.0, 60.0, valid=None)        # raises instead of clipping
open("maps/t-mean.png", "wb").write(write_png(pixels, 16))    # 16-bit greyscale, no colour chunks
```

with this manifest entry:

```json
{
  "id": "t-mean", "kind": "scalar", "quantity": "air_temperature",
  "grid": "global", "path": "maps/t-mean.png", "sha256": "<filled by wmi rehash>",
  "units": "degC", "encoding": {"type": "png16_linear", "min": -90.0, "max": 60.0},
  "qualifiers": {"elevation_reference": "terrain", "height_above_surface_m": 2.0},
  "time": {"calendar": "model", "span": {"start": {"year": 1}, "end": {"year": 30}},
           "aggregation": [{"statistic": "mean", "over": "timesteps", "within": "year"},
                           {"statistic": "mean", "over": "years"}]}
}
```

Producers that do not use Python only need a 16-bit greyscale PNG writer, SHA-256 and JSON output. `wmi validate` can
check the result.

## 4. Suggested encoding ranges

Shared ranges keep layers comparable and stable between runs. See the [producer guide](producer-guide.md#2-choose-an-encoding-range-scalars).
For temperature, -90..60 degC gives a step of about 0.0023 K. For annual precipitation, 0..10000 mm gives a step of about
0.15 mm. Values outside the range are rejected, never clipped.

## 5. Validation checklist for a WCL export

- [ ] `wmi validate` reports CONFORMANT with no warnings.
- [ ] Every temperature layer has `elevation_reference` and the right aggregation.
- [ ] Rain, snowfall and total precipitation share `span`, `aggregation` and range.
- [ ] Sea-surface temperature has a validity mask that is invalid on land.
- [ ] The calendar matches the model (year length, periods and day length).
- [ ] Model-specific indices are namespaced and have definitions.
- [ ] `world.id` is stable, so that other tools can match exports of the same world.

## 6. Open questions for discussion

- Which exact statistics and periods does WCL compute, and are the aggregation patterns above enough to describe them?
- Does WCL need monthly or seasonal **series** (one value per period) rather than single summary layers? Time-series
  packaging is a [proposal](proposals/time-series.md). In 0.1.0, each period is a separate layer using
  `time.select_periods`.
- Would float32 rasters ([proposal](proposals/float32-rasters.md)) materially help, or is the 16-bit precision above
  sufficient?
- Does WCL's biome taxonomy have stable ids that could be published as a class table?
