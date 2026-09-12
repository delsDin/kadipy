# Weather Module (`kadi.weather`)

The `kadi.weather` module provides a unified interface to acquire, cache, and analyze agricultural weather data. Designed specifically for the Beninese context, it relies on two complementary data sources: Open-Meteo for short-term forecasts and temperature series, and CHIRPS for long-term historical rainfall.

The main entry point is the `Weather` facade, which initializes each internal component on demand (lazy loading).

---

## Architecture

```
kadi.weather
├── Weather          - Main facade (session.py)
├── Location         - GPS location and agro-climatic zone (location.py)
├── WeatherLoader    - Raw data acquisition and caching (data.py)
├── Phenology        - Seasons, GDD, onset/cessation (phenology.py)
├── Hydrology        - Water balance, FAO-56 ET0 (hydrology.py)
└── Risk             - SPI, Markov chains, rain probability (risk.py)
```

The `Phenology`, `Hydrology`, and `Risk` components are only instantiated when a method requiring them is called for the first time.

---

## Data Sources

| Source | Usage | Availability |
|--------|-------|--------------|
| Open-Meteo | Forecasts (up to 16 days) and historical temperatures | Free API |
| CHIRPS | Long historical rainfall (since 1981, ~15-day latency) | CHC API |
| SQLite Cache | Local storage and offline fallback | `~/.kadi/cache.db` |

The rainfall source for historical queries is configurable via the `source` parameter of `historical()`: `'openmeteo'`, `'chirps'`, or `'both'`. If `source` is omitted, the default value defined in `CONFIG` is applied.

In `'both'` mode, CHIRPS covers historical periods and Open-Meteo fills recent dates not yet published in CHIRPS. The `data_source` column in the SQLite cache records the provenance of each observation.

---

## Agro-Climatic Zones

The zone is automatically detected from latitude by `Location`.

| Zone | Latitude | Rainfall Regime |
|------|----------|-----------------|
| `'Sud'` | `lat < 7.5` | Bimodal (two rainy seasons) |
| `'Centre'` | `7.5 <= lat < 9.0` | Bimodal |
| `'Nord'` | `lat >= 9.0` | Unimodal (one rainy season) |

The zone is stored in attribute `location.zone` and the regime in `location.regime`.

---

## Importing

```python
import kadi as kd

# Main Facade
weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")

# Direct access to classes if needed
from kadi.weather import Location, WeatherLoader
```

---

## `Weather` (Main Facade)

### Initialization

```python
weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lat` | `float` | Yes | Latitude in decimal degrees |
| `lon` | `float` | Yes | Longitude in decimal degrees |
| `name` | `str` | No | Locality name |
| `cache` | `str` | No | Cache directory path (retained for signature compatibility) |

`lat` and `lon` are mandatory: a `TypeError` is raised if either is omitted.

**Attributes Instantiated at Initialization:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `location` | `Location` | Associated location instance |
| `cache` | `str` or `None` | Cache directory (retained parameter) |
| `loader` | `WeatherLoader` | Weather data loader instance |
| `phenology` | `Phenology` or `None` | Initialized on demand |
| `hydrology` | `Hydrology` or `None` | Initialized on demand |
| `risk` | `Risk` or `None` | Initialized on demand |

---

### `forecast(days=None)`

Retrieves short-term weather forecast from Open-Meteo (or valid local cache).

```python
forecast_data = weather.forecast(days=7)

print(forecast_data["location"]["name"])
for day in forecast_data["data"]:
    print(day["date"], day["precipitation"])
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | `int` or `None` | Value of `CONFIG["weather"]["forecast_days_default"]` | Number of forecast days |

The number of days is capped at `CONFIG["weather"]["max_forecast_days"]`.

**Returns:** `dict` containing keys:
- `'location'`: `dict` with `'name'`, `'lat'`, `'lon'`
- `'data'`: list of daily dictionaries
- `'source'`: data source (`'open-meteo'` or `'cached'`)
- `'last_updated'`: ISO response timestamp

---

### `historical(metric='all', months=120, source=None, months_back=None)`

Returns historical weather time series as a DataFrame.

```python
# 24 months, all metrics
df = weather.historical(months=24)

# Rainfall only
df_rain = weather.historical(metric="precipitation", months=12)

# Force CHIRPS for rainfall
df_chirps = weather.historical(months=36, source="chirps")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric` | `str` | `'all'` | Column filter: `'temperature'`, `'precipitation'`, `'humidity'`, or `'all'` |
| `months` | `int` | `120` | Number of historical months |
| `source` | `str` or `None` | `CONFIG` default | Rainfall source: `'chirps'`, `'openmeteo'`, or `'both'` |
| `months_back` | `int` or `None` | `None` | Legacy alias for `months` (deprecated) |

**Returns:** `pd.DataFrame` indexed by `DatetimeIndex`.

---

### `gdd(crop, start, end=None)`

Calculates accumulated Growing Degree Days (GDD) from planting date `start` to `end` (or today if omitted).

```python
result = weather.gdd(crop="maize", start="2026-05-15")
print(result["gdd_accumulated"])
print(result["phenology_stage"])
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `crop` | `str` | Target crop (`'maize'`, `'rice'`, etc.) |
| `start` | `str` or `pd.Timestamp` | Planting date (`YYYY-MM-DD` format) |
| `end` | `str`, `pd.Timestamp`, or `None` | End date. `None` defaults to today |

**Returns:** `dict` (see [Phenology](phenology.md) documentation).

---

### `onset()`

Detects rainy season onset date based on zone climate regime.

```python
season_start = weather.onset()
print(season_start["onset_date"])
print(season_start["method"])
```

**Returns:** `dict` (see [Phenology](phenology.md)).

---

### `cessation()`

Determines effective rainy season end date.

```python
season_end = weather.cessation()
print(season_end["cessation_date"])
```

**Returns:** `dict` (see [Phenology](phenology.md)).

---

### `drought(method='spi', window=3, window_months=None)`

Calculates drought index for the location.

```python
drought_info = weather.drought(method="spi", window=3)
print(drought_info["spi_3month"])
print(drought_info["drought_severity"])
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | `str` | `'spi'` | Calculation method: `'spi'`, `'markov'`, `'hurst'`, `'combined'` |
| `window` | `int` | `3` | Time window in months |
| `window_months` | `int` or `None` | `None` | Legacy alias for `window` (deprecated) |

**Returns:** `dict` (see [Risk](risk.md)).

---

### `rain_prob(days=1, min_mm=1.0, days_ahead=None, min_rainfall_mm=None)`

Forecasts rain probability over the next `days`.

```python
prob = weather.rain_prob(days=3, min_mm=1.0)
print(prob["tomorrow"])          # tomorrow rain probability (float 0.0 to 1.0)
print(prob["recommendation"])    # agronomic recommendation
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | `int` | `1` | Number of future days |
| `min_mm` | `float` | `1.0` | Minimum rainfall threshold in mm |
| `days_ahead` | `int` or `None` | `None` | Legacy alias for `days` (deprecated) |
| `min_rainfall_mm` | `float` or `None` | `None` | Legacy alias for `min_mm` (deprecated) |

**Returns:** `dict` (see [Risk](risk.md)).

---

### `water_balance(crop='maize', soil_type='ferrugineux')`

Simulates daily water balance using the FAO-56 methodology.

```python
wb = weather.water_balance(crop="maize", soil_type="ferrugineux")
print(wb[["precipitation", "ET0", "deficit_eau", "reserve_utile"]].tail(14))
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `crop` | `str` | `'maize'` | Crop type |
| `soil_type` | `str` | `'ferrugineux'` | Soil type |

**Returns:** `pd.DataFrame` (see [Hydrology](hydrology.md)).

---

### `et0_hargreaves(tmin, tmax, day_of_year)`

Calculates reference evapotranspiration (ET0) using the Hargreaves-Samani method.

```python
et0 = weather.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=180)
print(f"ET0 : {et0:.2f} mm/day")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `tmin` | `float` | Minimum temperature in degC |
| `tmax` | `float` | Maximum temperature in degC |
| `day_of_year` | `int` | Day of year (1 to 365) |

**Returns:** `float` (ET0 in mm/day).

---

## `Location`

Represents a geographic position in Benin with automatic detection of agro-climatic zone and rainfall regime.

### Initialization

```python
from kadi.weather import Location

loc = Location(lat=9.3333, lon=2.6333, name="Parakou")
print(loc.zone)    # 'Nord'
print(loc.regime)  # 'unimodal'
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `lat` | `float` | Latitude in decimal degrees |
| `lon` | `float` | Longitude in decimal degrees |
| `name` | `str` | Optional locality name |

Coordinates are validated against the Benin GPS bounding box defined in `CONFIG["weather"]["gps_validation_bbox"]`. A `LocationError` is raised if coordinates fall outside this region.

If `name` is omitted, the attribute defaults to `'Point(lat, lon)'`.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `lat` | `float` | Latitude |
| `lon` | `float` | Longitude |
| `name` | `str` | Locality name |
| `zone` | `str` | Detected zone: `'Sud'`, `'Centre'`, or `'Nord'` |
| `regime` | `str` | Detected regime: `'bimodal'` or `'unimodal'` |

---

### `climate()`

Returns default climate parameters for the zone.

```python
params = loc.climate()
# {'Tbase': 10, 'onset_method': 'sivakumar'}
```

**Returns:** `dict` containing keys `'Tbase'` and `'onset_method'`.

| Zone | `onset_method` |
|------|----------------|
| `'Sud'` | `'walter_anyadike'` |
| `'Centre'` | `'hybrid'` |
| `'Nord'` | `'sivakumar'` |

---

### `to_dict()`

Serializes location for caching.

```python
loc.to_dict()
# {'name': 'Parakou', 'lat': 9.3333, 'lon': 2.6333, 'zone': 'Nord', 'regime': 'unimodal'}
```

**Returns:** `dict`.

---

## `WeatherLoader`

Manages API data acquisition, normalization, and persistence in the local SQLite cache (`~/.kadi/cache.db`).

In practice, `WeatherLoader` is used internally by `Weather` via `weather.loader`. It is rarely instantiated directly.

### Initialization

```python
from kadi.weather import Location, WeatherLoader

loc = Location(lat=9.3333, lon=2.6333)
loader = WeatherLoader(loc)
```

`cache` is optional. If provided, it overrides the cache directory passed by the `Weather` facade.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `location` | `Location` | Associated location instance |
| `forecast` | `pd.DataFrame` or `None` | In-memory forecast DataFrame |
| `historical` | `pd.DataFrame` or `None` | In-memory historical DataFrame |
| `source` | `str` | Source identifier of last loaded dataset |

---

### `get_forecast(days=7, refresh=False)`

Fetches weather forecast checking SQLite cache first.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | `int` | `7` | Number of forecast days |
| `refresh` | `bool` | `False` | If `True`, bypasses cache and forces refresh |

Cache TTL for forecasts is configured via `CONFIG["weather"]["cache_ttl_forecast_hours"]`. On API failure, cache is returned if valid, otherwise an `OfflineError` is raised.

**Returns:** `pd.DataFrame` indexed by date.

---

### `get_historical(months=120, refresh=False, source=None)`

Fetches historical weather data combining CHIRPS and Open-Meteo according to `source`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `months` | `int` | `120` | Number of historical months |
| `refresh` | `bool` | `False` | If `True`, bypasses cache |
| `source` | `str` or `None` | `CONFIG` default | `'chirps'`, `'openmeteo'`, or `'both'` |

A 5-day row count tolerance is allowed before marking cache incomplete. Cache TTL is configured via `CONFIG["weather"]["cache_ttl_historical_days"]`.

**Returns:** `pd.DataFrame` indexed by date.

---

### Data Normalization Pipeline

`WeatherLoader` automatically normalizes each DataFrame via `_normalize()`:

1. Converts `'date'` column to `DatetimeIndex`.
2. Filters temperature outliers outside `[-5, 55] degC`.
3. Enforces non-negative precipitation values.
4. Computes `'data_quality'` column (ratio of populated critical columns).
5. Applies linear interpolation on short gaps (up to 3 consecutive days).
6. Fills residual missing precipitation values with `0.0`.
7. Ensures presence of `'temperature_mean'` column via `_unify_temp()`: calculated as `(temperature_min + temperature_max) / 2`, or aliased from `temperature_avg` if base columns are missing.

---

## Offline Cache

All downloaded data is stored in the KadiPy SQLite database (`~/.kadi/cache.db`, table `weather_data`). If network is offline, the module automatically uses cached data without raising errors (unless cache is empty, in which case `OfflineError` is raised).

The `data_source` column in the cache table records the provenance of each observation: `'chirps'`, `'open-meteo'`, or a hybrid combination.

---

## Complete Example

```python
import kadi as kd

# Initialization for Cotonou (Sud zone, bimodal regime)
weather = kd.Weather(lat=6.3654, lon=2.4183, name="Cotonou")

# 5-day forecast
forecast_data = weather.forecast(days=5)
for day in forecast_data["data"]:
    print(day["date"], day["precipitation"], day["temperature_min"])

# 12-month history (hybrid source by default)
df = weather.historical(months=12)
print(df.columns.tolist())

# Season onset date
start = weather.onset()
print(start["onset_date"], start["method"])

# GDD calculation for maize
gdd = weather.gdd(crop="maize", start="2026-05-15")
print(gdd["gdd_accumulated"], gdd["phenology_stage"])

# Daily water balance
wb = weather.water_balance(crop="maize", soil_type="ferrugineux")
print(wb[["precipitation", "ET0", "deficit_eau"]].tail(7))

# SPI-3 drought index
drought_info = weather.drought(method="spi", window=3)
print(drought_info["spi_3month"], drought_info["drought_severity"])

# Tomorrow rain probability
prob = weather.rain_prob(days=1, min_mm=1.0)
print(prob["tomorrow"], prob["recommendation"])
```

---

## Backward Compatibility

Legacy class and parameter names emit a `DeprecationWarning` and continue to function until KadiPy v2.0.

**Classes:**

| Legacy Name | New Name |
|-------------|----------|
| `WeatherSession` | `Weather` |
| `WeatherData` | `WeatherLoader` |
| `RiskIndicators` | `Risk` |

**`Weather.__init__()` Parameters:**

| Legacy Parameter | New Parameter |
|------------------|---------------|
| `latitude` | `lat` |
| `longitude` | `lon` |
| `cache_dir` | `cache` |

**`Weather` Methods:**

| Legacy Method | New Method |
|---------------|------------|
| `growing_degree_days(crop, start_date, end_date)` | `gdd(crop, start, end)` |
| `drought_index(method, window_months)` | `drought(method, window)` |
| `rain_probability(days_ahead, min_rainfall_mm)` | `rain_prob(days, min_mm)` |

**`Weather` Attributes:**

| Legacy Attribute | New Attribute |
|------------------|---------------|
| `cache_dir` | `cache` |
| `weather_data` | `loader` |
| `risk_indicators` | `risk` |

**`Weather.historical()` Parameters:**

| Legacy Parameter | New Parameter |
|------------------|---------------|
| `months_back` | `months` |

---

## Sub-modules

- [Phenology](phenology.md): onset, cessation, GDD
- [Hydrology](hydrology.md): water balance, ET0
- [Climate Risks (Risk)](risk.md): SPI, Markov chains, rain probability

::: kadi.weather.session.Weather
::: kadi.weather.location.Location
::: kadi.weather.data.WeatherLoader
