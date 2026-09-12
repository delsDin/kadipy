# Phenology (`kadi.weather.phenology`)

The `Phenology` class manages phenological analysis for a location. It detects the start (`onset`) and end (`cessation`) of the agricultural season, and calculates growing degree days (GDD) for key crops in the Benin region.

It is used internally by the `Weather` facade, but can also be instantiated directly.

---

## Direct Import

```python
from kadi.weather import Phenology
```

---

## Initialization

In standard use, `Phenology` is created automatically by the `Weather` facade upon the first invocation of `onset()`, `cessation()`, or `gdd()`. It is then accessible via `weather.phenology`.

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Phenology loaded on demand
start_info = weather.onset()
phenology = weather.phenology   # Instance available
```

For direct instantiation:

```python
from kadi.weather import Phenology, Location
import pandas as pd

location = Location(lat=9.3, lon=2.3, name="Parakou")

# rainfall : daily pd.Series of precipitation, indexed by date
# temperature : pd.DataFrame with columns 'temperature_min' and 'temperature_max'

phenology = Phenology(location, rainfall, temperature)
```

**Public Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `location` | `Location` | Location of the analysis |
| `rainfall` | `pd.Series` | Daily precipitation series |
| `temperature` | `pd.DataFrame` | Temperature data (`temperature_min`, `temperature_max`) |
| `onset_ts` | `pd.Timestamp` | Calculated onset date (`None` prior to first call) |
| `crop` | `dict` | Crop parameters by crop |

---

## Methods

### `onset()`

Detects the start date of the agricultural season.

The algorithm used depends on the climate zone of the location:

- **North Zone** (unimodal regime): Sivakumar algorithm. Searches starting May 1st for the first 3-day sequence accumulating at least 20 mm, without a dry period of more than 7 days over the following 30 days.
- **South and Center Zones** (bimodal regime): hybrid Walter-Anyadike algorithm applied over two seasonal windows (S1: Jan-Jul, S2: Aug-Dec).

```python
start_info = weather.onset()

print(f"S1 Start   : {start_info['onset_1']}")
print(f"S2 Start   : {start_info['onset_2']}")   # None in North zone
print(f"Algorithm  : {start_info['algorithm']}")
print(f"Zone       : {start_info['zone']}")
print(f"Confidence : {start_info['confidence']}")
```

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `onset_date` | `str` | Alias for `onset_1` (backwards compatibility) |
| `onset_1` | `str` | Start date of the first season (`YYYY-MM-DD`) |
| `onset_2` | `str` | Start date of the second season, `None` in North zone |
| `algorithm` | `str` | Algorithm used (`'Sivakumar'` or `'Walter-Anyadike bimodal'`) |
| `zone` | `str` | Climate zone (`'Nord'`, `'Centre'`, `'Sud'`) |
| `confidence` | `float` | Confidence index (0.80 bimodal, 0.85 unimodal) |

**Exceptions:**

- `DataError`: no precipitation data available.

---

### `cessation()`

Determines the end date of effective rainfall.

Cessation is defined as the last day from which the remaining rainfall accumulation (calculated in reverse) falls below 20 mm.

- **North Zone**: a single cessation date calculated from September.
- **South and Center Zones**: two cessation dates (S1 around May-July, S2 around October-December).

```python
end_info = weather.cessation()

print(f"S1 End            : {end_info['cessation_1']}")
print(f"S2 End            : {end_info['cessation_2']}")   # None in North zone
print(f"Season duration   : {end_info['duration_days']} days")
print(f"Annual total rain : {end_info['total_rainfall']:.0f} mm")
```

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `cessation_date` | `str` | Alias for `cessation_1` (backwards compatibility) |
| `cessation_1` | `str` | End date of the first season (`YYYY-MM-DD`) |
| `cessation_2` | `str` | End date of the second season, `None` in North zone |
| `duration_days` | `int` | Duration of main season in days (North zone) |
| `total_rainfall` | `float` | Annual total precipitation in mm |
| `zone` | `str` | Climate zone |

**Exceptions:**

- `DataError`: no precipitation data available.

---

### `gdd(crop, start, end)`

Calculates accumulated Growing Degree Days (GDD) for a crop since the sowing date.

Daily GDD is calculated as:

```
GDD = max(0, (Tmax + Tmin) / 2 - Tbase)
```

where `Tbase` is the base temperature of the crop (threshold below which the plant does not grow).

```python
# GDD for maize sown on May 15
result = weather.gdd(crop="maize", start="2026-05-15")

print(f"Accumulated GDD : {result['gdd_accumulated']:.1f} degC.day")
print(f"Cycle completed : {result['pct_cycle']} %")
print(f"Current stage   : {result['phenology_stage']}")

# With an explicit end date
result = weather.gdd(
    crop="rice",
    start="2026-06-01",
    end="2026-10-15",
)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `crop` | `str` | required | Crop name |
| `start` | `str` or `pd.Timestamp` | required | Sowing date (`YYYY-MM-DD`) |
| `end` | `str` or `pd.Timestamp` | `None` | End date (today if None) |

**Supported Crops:**

| Crop | Base Temp (degC) | Total Required GDD |
|------|------------------|--------------------|
| `'maize'` | 10 | 1300 |
| `'rice'` | 10 | 1500 |
| `'manioc'` | 14 | 3000 |
| `'sorghum'` | 10 | 1400 |
| `'tomato'` | 10 | 1000 |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `gdd_accumulated` | `float` | GDD accumulation over period |
| `crop` | `str` | Crop name |
| `gdd_total_cycle` | `int` | Total GDD required for full cycle |
| `pct_cycle` | `int` | Percentage of cycle completed (0 to 100) |
| `phenology_stage` | `str` | Estimated stage: `'vegetative'`, `'tasseling/flowering'`, `'maturity'` |

**Exceptions:**

- `CropError`: unrecognized crop.
- `DataError`: insufficient temperature data over the period.

The `growing_degree_days()` method is deprecated since v1.2.0. Use `gdd()` instead.

---

## Deprecated Attributes

| Legacy Attribute | Replaced By | Since |
|------------------|-------------|-------|
| `rainfall_data` | `rainfall` | v1.2.0 |
| `temperature_data` | `temperature` | v1.2.0 |
| `onset_date` | `onset_ts` | v1.2.0 |
| `crop_params` | `crop` | v1.2.0 |

---

## Complete Example

```python
import kadi as kd

weather = kd.Weather(lat=6.4, lon=2.4, name="Cotonou")

# Season start and end (bimodal regime for South)
start_info = weather.onset()
end_info = weather.cessation()

print(f"S1 Season : {start_info['onset_1']} -> {end_info['cessation_1']}")
print(f"S2 Season : {start_info['onset_2']} -> {end_info['cessation_2']}")

# GDD for maize
gdd = weather.gdd(crop="maize", start=start_info["onset_1"])
print(f"Progress : {gdd['pct_cycle']} % - {gdd['phenology_stage']}")
```

---

::: kadi.weather.phenology.Phenology
