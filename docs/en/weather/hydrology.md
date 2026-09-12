# Hydrology (`kadi.weather.hydrology`)

The `Hydrology` class models soil water balance for an agricultural plot. It calculates reference evapotranspiration (ET0), daily runoff (SCS-CN), and the full water balance according to the FAO-56 standard.

It is used internally by the `Weather` facade, but can also be instantiated directly for specific analyses.

---

## Direct Import

```python
from kadi.weather import Hydrology
```

---

## Initialization

In standard use, `Hydrology` is created automatically by the `Weather` facade upon the first invocation of `water_balance()` or `et0_hargreaves()`. It is then accessible via `weather.hydrology`.

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Hydrology loaded on demand
balance = weather.water_balance(crop="maize", soil_type="ferrugineux")
hydrology = weather.hydrology   # Instance available
```

For direct instantiation:

```python
from kadi.weather import Hydrology, Location
import pandas as pd

location = Location(lat=9.3, lon=2.3, name="Parakou")

# rainfall : daily pd.Series of precipitation, indexed by date
# temperature : pd.DataFrame with columns 'temperature_min' and 'temperature_max'

hydrology = Hydrology(
    location,
    rainfall,
    temperature,
    soil_type="ferrugineux",
    crop="maize",
)
```

**Public Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `location` | `Location` | Plot location |
| `rainfall` | `pd.Series` | Daily precipitation series |
| `temperature` | `pd.DataFrame` | Temperature data (`temperature_min`, `temperature_max`) |
| `crop` | `str` | Crop type |
| `soil_type` | `str` | Soil type |
| `soil` | `dict` | Soil physical parameters |
| `balance` | `pd.DataFrame` | Water balance result (`None` prior to calculation) |

---

## Methods

### `water_balance()`

Simulates daily soil water balance according to the FAO-56 method.

Calculation includes:

1. Daily ET0 by Hargreaves-Samani.
2. Runoff by the SCS-CN method with AMC (Antecedent Moisture Condition) adjustment over the previous 5 days.
3. Crop evapotranspiration (ETc = ET0 x Kc).
4. Sequential balance: effective rainfall - ETc, capped at TAW (Total Available Water).

```python
balance = weather.water_balance(crop="maize", soil_type="ferrugineux")

# Last 7 days
print(balance.tail(7)[[
    "precip", "et0", "pluie_eff",
    "evapotransp", "deficit_eau", "reserve_utile", "stress_hydrique_index"
]])
```

This calculation is triggered via the `Weather` facade. To call it directly on the `Hydrology` instance (for example after modifying the crop):

```python
# Modifying crop and soil
weather.hydrology.crop = "rice"
weather.hydrology.soil_type = "ferrallitique"
weather.hydrology.soil = weather.hydrology.soil_params("ferrallitique")

# Recalculate
balance = weather.hydrology.water_balance()
```

**Returns:** `pd.DataFrame` with `DatetimeIndex`.

**Columns:**

| Column | Description |
|--------|-------------|
| `precip` | Observed precipitation (mm) |
| `et0` | ET0 by Hargreaves-Samani (mm/day) |
| `pluie_eff` | Effective rainfall after deducting runoff (mm) |
| `evapotransp` | ETc = ET0 x Kc for the crop (mm/day) |
| `deficit_eau` | Daily soil water deficit (mm) |
| `reserve_utile` | Available soil water = TAW - deficit (mm) |
| `stress_hydrique_index` | Water stress index = deficit / TAW (0 to 1) |

**Exceptions:**

- `DataError`: missing precipitation or temperature data.

---

### `et0_hargreaves(tmin, tmax, day_of_year)`

Calculates reference evapotranspiration (ET0) using the Hargreaves-Samani method. Alternative to Penman-Monteith when humidity, wind, and solar radiation data are unavailable.

```python
# Calculation for a given day
et0 = weather.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=180)
print(f"ET0 : {et0:.2f} mm/day")

# Direct call on Hydrology instance (also accepts numpy arrays)
import numpy as np
tmin_arr = np.array([20.0, 21.0, 19.0])
tmax_arr = np.array([33.0, 35.0, 32.0])
doy_arr  = np.array([150, 151, 152])
et0_arr = weather.hydrology.et0_hargreaves(tmin_arr, tmax_arr, doy_arr)
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tmin` | `float` or `np.ndarray` | Minimum temperature (degC) |
| `tmax` | `float` or `np.ndarray` | Maximum temperature (degC) |
| `day_of_year` | `int` or `np.ndarray` | Day of year (1 to 365) |

**Returns:** `float` or `np.ndarray` - ET0 in mm/day.

---

### `et0_fao56_penman(tmin, tmax, humidity, wind_speed, solar_rad)`

Calculates ET0 using the FAO-56 Penman-Monteith method. More accurate than Hargreaves as it integrates relative humidity, wind speed, and measured solar radiation.

```python
et0_pm = weather.hydrology.et0_fao56_penman(
    tmin=22.0,
    tmax=35.0,
    humidity=65.0,     # Relative humidity (%)
    wind_speed=2.5,    # Wind speed at 2 m (m/s)
    solar_rad=18.0,    # Solar radiation (MJ/m2/day)
)
print(f"Penman-Monteith ET0 : {et0_pm:.2f} mm/day")
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tmin` | `float` | Minimum temperature (degC) |
| `tmax` | `float` | Maximum temperature (degC) |
| `humidity` | `float` | Average relative humidity (%, between 0 and 100) |
| `wind_speed` | `float` | Wind speed measured at 2 m height (m/s) |
| `solar_rad` | `float` | Incident solar radiation (MJ/m2/day) |

**Returns:** `float` - ET0 in mm/day.

---

### `runoff_cn(precipitation, prior_5d_rain)`

Calculates daily runoff using the revised SCS-CN method, with adjustment based on antecedent moisture condition (AMC).

```python
runoff = weather.hydrology.runoff_cn(
    precipitation=35.0,
    prior_5d_rain=20.0,
)
print(f"Runoff : {runoff:.2f} mm")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `precipitation` | `float` | required | Daily precipitation (mm) |
| `prior_5d_rain` | `float` | `0.0` | 5-day prior accumulation (mm) for AMC adjustment |

**AMC Adjustment:**

| Condition | Prior 5-day Rain | Adjusted CN |
|-----------|------------------|-------------|
| AMC I (dry) | < 12.5 mm | Reduced CN |
| AMC II (average) | 12.5 to 35.5 mm | Base CN |
| AMC III (wet) | > 35.5 mm | Increased CN |

**Returns:** `float` - Runoff in mm (0.0 if rainfall does not exceed initial abstraction).

---

### `soil_params(soil_type)`

Returns physical parameters for a Beninese soil.

```python
params = weather.hydrology.soil_params("ferrallitique")
print(f"TAW   : {params['taw']} mm")
print(f"CN    : {params['cn_amc2']}")
print(f"Ksat  : {params['ksat']} mm/day")
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `soil_type` | `str` | Soil type among supported values |

**Supported Soil Types:**

| Type | TAW (mm) | CN AMC II | Ksat (mm/day) |
|------|----------|-----------|---------------|
| `'ferrugineux'` | 100 | 82 | 15 |
| `'ferrallitique'` | 130 | 75 | 35 |
| `'sableux'` | 60 | 65 | 100 |
| `'limoneux'` | 150 | 78 | 10 |

**Returns:** `dict` with `taw`, `cn_amc2`, `ksat`.

**Exceptions:**

- `ValidationError`: unsupported soil type.

---

### `crop_kc(crop, stage)`

Returns crop coefficient (Kc) according to phenological stage. The Kc represents the ratio ETc / ET0 according to FAO-56 standard.

```python
kc = weather.hydrology.crop_kc("maize", "mid")
print(f"Mid-season Kc : {kc}")
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `crop` | `str` | Crop name |
| `stage` | `str` | Stage among `'ini'`, `'mid'`, `'end'` |

**Kc Coefficients by Crop and Stage:**

| Crop | Kc ini | Kc mid | Kc end |
|------|--------|--------|--------|
| `'maize'` | 0.30 | 1.20 | 0.35 |
| `'rice'` | 1.05 | 1.20 | 0.90 |
| `'manioc'` | 0.30 | 0.80 | 0.30 |
| `'sorghum'` | 0.30 | 1.00 | 0.55 |
| `'tomato'` | 0.60 | 1.15 | 0.70 |

**Returns:** `float` - Kc value.

**Exceptions:**

- `CropError`: unrecognized crop.

---

## Deprecated Methods

| Legacy Method | Replaced By | Since |
|---------------|-------------|-------|
| `compute_water_balance()` | `water_balance()` | v1.2.0 |
| `get_soil_params(soil_type)` | `soil_params(soil_type)` | v1.2.0 |
| `get_crop_coefficients(crop, stage)` | `crop_kc(crop, stage)` | v1.2.0 |

## Deprecated Attributes

| Legacy Attribute | Replaced By | Since |
|------------------|-------------|-------|
| `rainfall_data` | `rainfall` | v1.2.0 |
| `temperature_data` | `temperature` | v1.2.0 |
| `balance_result` | `balance` | v1.2.0 |

---

## Complete Example

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Full water balance
balance = weather.water_balance(crop="sorghum", soil_type="sableux")

# Water stress analysis over last 30 days
last_30d = balance.tail(30)
mean_stress = last_30d["stress_hydrique_index"].mean()
print(f"Average water stress (30d) : {mean_stress:.2f}")

# Single-day ET0
et0 = weather.et0_hargreaves(tmin=21.0, tmax=34.0, day_of_year=200)
print(f"Daily ET0 : {et0:.2f} mm/day")

# Soil parameters
params = weather.hydrology.soil_params("ferrugineux")
print(f"Max available water : {params['taw']} mm")

# Mid-season Kc
kc = weather.hydrology.crop_kc("sorghum", "mid")
print(f"ETc = ET0 x Kc = {et0:.2f} x {kc} = {et0 * kc:.2f} mm/day")
```

---

::: kadi.weather.hydrology.Hydrology
