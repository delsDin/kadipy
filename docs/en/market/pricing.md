# Pricing (`kadi.market.pricing`)

The `Pricing` class handles the acquisition, normalization, and analysis of agricultural market price data in Benin. It is used internally by the `Market` facade, but can also be instantiated directly.

---

## Direct Importing

```python
from kadi.market import Pricing
```

---

## Initialization

`Pricing` is created automatically by the `Market` facade and is accessible via `market.pricing`. For direct instantiation:

```python
from kadi.market import Pricing

# Without clients (automatic simulation mode)
pricing = Pricing()

# With WFP client and dynamic exchange rates
from kadi._sources import WFPClient, ExchangeRateClient
pricing = Pricing(
    wfp=WFPClient(),
    exchange=ExchangeRateClient(),
    sim=False,
)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `wfp` | `WFPClient` | `None` | WFP client for HAPI HumData API |
| `exchange` | `ExchangeRateClient` | `None` | Dynamic exchange rate client |
| `sim` | `bool` | `False` | If True, forces simulation mode for all methods |

**Public Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `client` | `WFPClient` | Injected WFP client (or None) |
| `sim` | `bool` | Active simulation mode flag |

---

## Methods

### `fetch(crop, market, days, sim)`

Retrieves historical prices for a crop at a given market location.

In real mode, queries the HAPI HumData API. In simulation mode (no client configured or `sim=True`), generates dummy prices following a normal distribution centered on 300 XOF/kg, explicitly tagged `sim=True` and `confidence_score=0.1`.

```python
import kadi as kd

market = kd.Market(lat=9.3, lon=2.3, location="Parakou")

# Fetching price history (real or simulated data)
df = market.pricing.fetch("maize", "parakou", days=365)

print(df.dtypes)
print(df.tail(5))
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `crop` | `str` | required | Crop code (e.g. `'maize'`, `'rice'`) |
| `market` | `str` | required | Normalized market name (e.g. `'cotonou'`) |
| `days` | `int` | `365` | Number of historical days to fetch |
| `sim` | `bool` | `None` | Overrides instance simulation mode if provided |

**Returns:** `pd.DataFrame`

| Column | Type | Description |
|--------|------|-------------|
| `date` | `datetime` | Observation date |
| `price` | `float` | Price in XOF/kg |
| `unit` | `str` | Original unit (e.g. `'XOF/kg'`) |
| `sim` | `bool` | True if dummy/simulated data |
| `source` | `str` | Data source identifier |
| `fetched_at` | `str` | ISO 8601 collection timestamp |
| `confidence_score` | `float` | Confidence score (0.0 to 1.0) |

---

### `convert_unit(value, unit, crop)`

Converts a price value to the standard unit XOF/kg.

```python
# XOF/Tonne -> XOF/kg
price_kg = market.pricing.convert_unit(180_000.0, "XOF/Tonne")
print(f"{price_kg:.2f} XOF/kg")   # 180.0 XOF/kg

# USD/kg -> XOF/kg (via Frankfurter exchange rate)
price_kg = market.pricing.convert_unit(0.45, "USD/kg")

# XOF/sac (bag weight depends on crop)
price_kg = market.pricing.convert_unit(14_000.0, "XOF/sac", crop="maize")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `float` | required | Price value to convert |
| `unit` | `str` | required | Original unit |
| `crop` | `str` | `None` | Crop code (for container weight lookups) |

**Supported Units:**

| Unit | Conversion |
|------|------------|
| `XOF/kg` | No conversion (target unit) |
| `XOF/Tonne` | Division by 1000 |
| `USD/kg` | Multiplication by USD/XOF rate |
| `EUR/kg` | Multiplication by EUR/XOF rate (fixed WAEMU peg) |
| `XOF/sac` | Division by bag weight in kg (crop-dependent) |
| `XOF/boisseau`, `XOF/tine`, `XOF/caisse` | Division by container weight |

If the unit is unknown, the value is returned unmodified.

**Returns:** `float` - Price in XOF/kg.

---

### `anomalies(series, z)`

Detects price anomalies in a series using the Z-score method.

```python
df = market.pricing.fetch("rice", "cotonou", days=180)
df = market.pricing.anomalies(df, z=3.0)

nb_anomalies = df["is_anomaly"].sum()
print(f"Detected anomalies: {nb_anomalies}")
print(df[df["is_anomaly"]][["date", "price"]])
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `series` | `pd.DataFrame` | required | DataFrame containing a `'price'` column |
| `z` | `float` | `3.0` | Z-score threshold (3 = 99.7% of normal distribution) |

**Returns:** `pd.DataFrame` - Input DataFrame with an added boolean column `is_anomaly`.

---

### `fill_gaps(series, max_gap)`

Fills missing values in a price series using linear interpolation, capped at a configurable number of consecutive days.

```python
df = market.pricing.fetch("sorghum", "natitingou", days=365)
df = market.pricing.fill_gaps(df, max_gap=7)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `series` | `pd.DataFrame` | required | DataFrame containing a `'price'` column |
| `max_gap` | `int` | `7` | Maximum consecutive days to interpolate |

Gaps larger than `max_gap` consecutive days remain `NaN`.

**Returns:** `pd.DataFrame` - DataFrame with short gaps filled.

---

### `source(series)`

Identifies the data source of a price series.

```python
df = market.pricing.fetch("maize", "parakou", days=90)
src = market.pricing.source(df)
print(f"Source: {src}")   # 'wfp-vam' or 'simulated'
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `series` | `pd.DataFrame` | DataFrame returned by `fetch()` |

**Returns:** `str` - `'wfp-vam'`, `'ratin'`, `'scrape-local'`, or `'simulated'`.

---

### `seasonality(historique, min_observations_par_mois)`

Calculates 12 monthly seasonal price indices for agricultural produce using the ratio-to-mean method.

An index greater than 1 indicates a high-price month (lean/hungry season). An index lower than 1 indicates a cheap month (post-harvest season).

```python
df = market.pricing.fetch("maize", "parakou", days=730)
season = market.pricing.seasonality(df)

print(f"Peak month    : {season['mois_pic']}")
print(f"Trough month  : {season['mois_creux']}")
print(f"Average price : {season['prix_moyen_global']:.2f} XOF/kg")
print(f"Confidence    : {season['confiance']:.2f}")

# Index per month
for month, index in season["indices"].items():
    if index:
        print(f"  Month {month:2d} : {index:.3f}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `historique` | `pd.DataFrame` | required | DataFrame with `'date'` and `'price'` columns |
| `min_observations_par_mois` | `int` | `2` | Minimum observations required to include a month |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `indices` | `dict[int, float]` | Monthly seasonal indices (1 to 12). None if insufficient data |
| `mois_pic` | `list[int]` | Months where index exceeds 1.05 (5% above mean) |
| `mois_creux` | `list[int]` | Months where index is below 0.95 |
| `prix_moyen_global` | `float` | Average price over entire period (XOF/kg) |
| `prix_moyen_par_mois` | `dict[int, float]` | Raw average price per month |
| `nb_observations` | `int` | Total count of valid observations |
| `nb_mois_couverts` | `int` | Count of months meeting `min_observations_par_mois` |
| `confiance` | `float` | Confidence score (0.0 to 1.0) |
| `sim` | `bool` | True if history contains simulated data |
| `message` | `str` | Warning message if data is insufficient. None otherwise |

**Exceptions:**

- `ValueError`: if historical DataFrame is empty, or missing `'date'` / `'price'` columns.

---

## Deprecated Methods

| Legacy Method | Replaced By | Since |
|---------------|-------------|-------|
| `fetch_prices(crop, market, days_back)` | `fetch(crop, market, days)` | v1.2.0 |
| `normalize_units(value, unit)` | `convert_unit(value, unit)` | v1.2.0 |
| `detect_anomalies(series, threshold)` | `anomalies(series, z)` | v1.2.0 |
| `interpolate_gaps(series, max_gap)` | `fill_gaps(series, max_gap)` | v1.2.0 |
| `get_data_source(series)` | `source(series)` | v1.2.0 |

---

::: kadi.market.pricing.Pricing
