# Weather Facade (`kadi.weather.session`)

`Weather` is the main entry point of the `kadi.weather` module. It orchestrates internal components (`Location`, `WeatherLoader`, `Phenology`, `Hydrology`, `Risk`) and exposes a simple, unified API for all weather and agronomic capabilities.

---

## Initialization

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lat` | `float` | yes | Latitude in decimal degrees |
| `lon` | `float` | yes | Longitude in decimal degrees |
| `name` | `str` | no | Locality name |
| `cache` | `str` | no | Local cache directory path |

The parameters `latitude`, `longitude`, and `cache_dir` are recognized but deprecated since v1.2.0. Use `lat`, `lon`, and `cache` instead.

**Public Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `location` | `Location` | Associated location instance |
| `loader` | `WeatherLoader` | Weather data loader instance |
| `phenology` | `Phenology` | Phenological component (loaded on demand) |
| `hydrology` | `Hydrology` | Hydrological component (loaded on demand) |
| `risk` | `Risk` | Risk indicators component (loaded on demand) |
| `cache` | `str` | Cache directory path |

---

## Methods

### `forecast(days)`

Retrieves short-term weather forecasts from Open-Meteo.

```python
forecast_data = weather.forecast(days=5)

print(forecast_data["location"])
# {'name': 'Parakou', 'lat': 9.3, 'lon': 2.3}

for day in forecast_data["data"][:3]:
    print(day)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `days` | `int` | From `CONFIG` | Number of forecast days (maximum 16) |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `location` | `dict` | `{'name', 'lat', 'lon'}` |
| `data` | `list[dict]` | List of daily dictionaries with weather variables |
| `source` | `str` | Source utilized |
| `last_updated` | `str` | ISO timestamp of last update |

---

### `historical(metric, months, source)`

Returns historical weather time series from CHIRPS and Open-Meteo.

```python
# All variables over 10 years (default)
df = weather.historical()

# Rainfall only over 6 months
df_rain = weather.historical(metric="precipitation", months=6)

# All variables with explicit source selection
df_full = weather.historical(months=120, source="both")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `metric` | `str` | `'all'` | Filter: `'temperature'`, `'precipitation'`, `'humidity'`, `'all'` |
| `months` | `int` | `120` | Number of historical months |
| `source` | `str` | `None` | Rainfall source: `'chirps'`, `'openmeteo'`, `'both'`. If None, uses `CONFIG`. |

The parameter `months_back` is deprecated since v1.2.0. Use `months` instead.

**Returns:** `pd.DataFrame` indexed by `DatetimeIndex`.

---

### `onset()`

Detects rainy season onset date based on climate zone regime.

```python
season_start = weather.onset()

print(f"Season 1 Onset : {season_start['onset_1']}")
print(f"Season 2 Onset : {season_start['onset_2']}")   # None in Nord zone (unimodal)
print(f"Algorithm      : {season_start['algorithm']}")
print(f"Confidence     : {season_start['confidence']}")
```

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `onset_date` | `str` | Alias for `onset_1` (backward compatibility) |
| `onset_1` | `str` | First rainy season start date (`YYYY-MM-DD`) |
| `onset_2` | `str` | Second rainy season start date, `None` in Nord zone |
| `algorithm` | `str` | Algorithm utilized |
| `zone` | `str` | Detected climate zone |
| `confidence` | `float` | Confidence index |

The algorithm used depends on the location climate zone:

| Zone | Regime | Algorithm |
|------|--------|-----------|
| Nord (> 9.5° N) | Unimodal | Sivakumar |
| Sud and Centre | Bimodal | Walter-Anyadike |

---

### `cessation()`

Determines effective rainy season end date.

```python
season_end = weather.cessation()

print(f"Season 1 End : {season_end['cessation_1']}")
print(f"Season 2 End : {season_end['cessation_2']}")   # None in Nord zone
print(f"Duration     : {season_end['duration_days']} days")
```

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `cessation_date` | `str` | Alias for `cessation_1` (backward compatibility) |
| `cessation_1` | `str` | First rainy season end date (`YYYY-MM-DD`) |
| `cessation_2` | `str` | Second rainy season end date, `None` in Nord zone |
| `duration_days` | `int` | Season duration in days (Nord zone) |
| `total_rainfall` | `float` | Annual rainfall total (mm) |
| `zone` | `str` | Climate zone |

---

### `gdd(crop, start, end)`

Calculates accumulated Growing Degree Days (GDD) since planting date. GDD measures thermal energy available for plant development.

```python
result = weather.gdd(
    crop="maize",
    start="2026-05-15",
    end="2026-09-30",   # Optional: defaults to today if None
)

print(f"Accumulated GDD : {result['gdd_accumulated']:.1f} degC.day")
print(f"Current stage   : {result['phenology_stage']}")
print(f"Cycle progress  : {result['pct_cycle']}%")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `crop` | `str` | required | Crop type: `'maize'`, `'rice'`, `'manioc'`, `'sorghum'`, `'tomato'` |
| `start` | `str` or `pd.Timestamp` | required | Planting date (`YYYY-MM-DD`) |
| `end` | `str` or `pd.Timestamp` | `None` | End date (defaults to today if None) |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `gdd_accumulated` | `float` | Accumulated GDD over the period |
| `crop` | `str` | Crop name |
| `gdd_total_cycle` | `int` | Total GDD required for full growth cycle |
| `pct_cycle` | `int` | Percentage of growth cycle completed |
| `phenology_stage` | `str` | Estimated phenological stage |

The method `growing_degree_days()` is deprecated since v1.2.0. Use `gdd()` instead.

---

### `drought(method, window)`

Calculates drought index over historical data.

```python
# SPI over a 3-month window (default)
drought_info = weather.drought(method="spi", window=3)

print(f"3-Month SPI     : {drought_info['spi_3month']:.2f}")
print(f"Severity        : {drought_info['drought_severity']}")

# Combined analysis (SPI + Markov + Hurst)
analysis = weather.drought(method="combined", window=3)
print(f"Markov P(dry|dry) : {analysis['markov_p_dry']:.2f}")
print(f"Hurst exponent    : {analysis['hurst_exponent']:.2f}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `method` | `str` | `'spi'` | Calculation method (see table below) |
| `window` | `int` | `3` | Time window in months (for SPI) |

**Available Methods:**

| Method | Description |
|--------|-------------|
| `'spi'` | Standardized Precipitation Index (McKee et al., 1993) |
| `'markov'` | Drought persistence probability (Markov chain) |
| `'hurst'` | Hurst exponent - long memory of drought |
| `'combined'` | Combination of all three methods |

The method `drought_index()` is deprecated since v1.2.0. Use `drought()` instead.

---

### `rain_prob(days, min_mm)`

Forecasts rain probability for upcoming days, combining Open-Meteo forecasts (70%) and historical Markov frequencies (30%).

```python
prob = weather.rain_prob(days=3, min_mm=1.0)

print(f"Tomorrow        : {prob['tomorrow'] * 100:.0f}%")
print(f"In 2 days       : {prob['2_days'] * 100:.0f}%")
print(f"Message         : {prob['message']}")
print(f"Recommendation  : {prob['recommendation']}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `days` | `int` | `1` | Number of days to forecast (1 to 7) |
| `min_mm` | `float` | `1.0` | Significant rainfall threshold in mm |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `tomorrow` | `float` | Tomorrow rain probability |
| `N_days` | `float` | Rain probability for day N (N >= 2) |
| `message` | `str` | Summary statement with maximum risk level |
| `recommendation` | `str` | Agronomic recommendation |

The method `rain_probability()` is deprecated since v1.2.0. Use `rain_prob()` instead.

---

### `water_balance(crop, soil_type)`

Simulates daily soil water balance according to the FAO-56 methodology. Reference evapotranspiration (ET0) is calculated via Hargreaves-Samani.

```python
wb = weather.water_balance(crop="maize", soil_type="ferrugineux")

print(wb.tail(7)[[
    "precip", "et0", "pluie_eff", "evapotransp",
    "deficit_eau", "reserve_utile", "stress_hydrique_index"
]])
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `crop` | `str` | `'maize'` | Reference crop |
| `soil_type` | `str` | `'ferrugineux'` | Beninese soil type |

**Supported Soil Types:** `'ferrugineux'`, `'ferrallitique'`, `'sableux'`, `'limoneux'`.

**Returned DataFrame Columns:**

| Column | Description |
|--------|-------------|
| `precip` | Observed precipitation (mm) |
| `et0` | Reference evapotranspiration (mm) |
| `pluie_eff` | Effective rainfall after runoff deduction (mm) |
| `evapotransp` | Crop evapotranspiration - ET0 x Kc (mm) |
| `deficit_eau` | Daily water deficit (mm) |
| `reserve_utile` | Available soil water reserve (mm) |
| `stress_hydrique_index` | Water stress index (0 to 1) |

---

### `et0_hargreaves(tmin, tmax, day_of_year)`

Calculates reference evapotranspiration (ET0) via Hargreaves-Samani for a given day. Useful for point calculations without running a full water balance.

```python
et0 = weather.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=180)
print(f"ET0 : {et0:.2f} mm/day")
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tmin` | `float` | Minimum temperature (degC) |
| `tmax` | `float` | Maximum temperature (degC) |
| `day_of_year` | `int` | Day of year (1 to 365) |

**Returns:** `float` - ET0 in mm/day.

---

## Complete Example

```python
import kadi as kd

# Initialization
weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Historical data
df = weather.historical(months=24)
print(df.head())

# 7-day forecast
forecast_data = weather.forecast(days=7)

# Current season phenology
start = weather.onset()
end = weather.cessation()
print(f"Season: {start['onset_1']} -> {end['cessation_1']}")

# GDD for maize planted May 15
gdd = weather.gdd(crop="maize", start="2026-05-15")
print(f"Progress: {gdd['pct_cycle']}% ({gdd['phenology_stage']})")

# Drought risk
drought_info = weather.drought(method="combined")
print(f"3-Month SPI: {drought_info['spi_3month']:.2f} - {drought_info['drought_severity']}")

# Rain probability
prob = weather.rain_prob(days=3)
print(prob["recommendation"])

# Water balance
wb = weather.water_balance(crop="maize", soil_type="ferrugineux")
print(wb[["precip", "reserve_utile", "stress_hydrique_index"]].tail(10))
```

---

::: kadi.weather.session.Weather
