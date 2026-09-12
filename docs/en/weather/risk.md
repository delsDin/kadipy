# Climate Risks (`kadi.weather.risk`)

The `Risk` class evaluates climate risks for a given location. It calculates drought indices (SPI, Markov, Hurst) and forecasts short-term precipitation probability.

It is used internally by the `Weather` facade, but can also be instantiated directly for custom analysis.

---

## Direct Importing

```python
from kadi.weather import Risk
```

---

## Initialization

`Risk` is typically not instantiated directly: the `Weather` facade creates it automatically upon the first invocation of a risk method, accessible via `weather.risk`.

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Direct access to the Risk component after an initial risk query
drought_info = weather.drought()
risk = weather.risk   # Risk instance available
```

For direct instantiation:

```python
from kadi.weather import Risk, Location
import pandas as pd

location = Location(lat=9.3, lon=2.3, name="Parakou")

# rainfall : daily pd.Series indexed by date
# forecast : weather forecast pd.DataFrame

risk = Risk(location, rainfall, forecast)
```

**Public Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `location` | `Location` | Associated location instance |
| `rainfall` | `pd.Series` | Daily historical rainfall series |
| `forecast` | `pd.DataFrame` | Weather forecast DataFrame |

---

## Methods

### `drought(method, window)`

Calculates the drought index using the specified method.

```python
# 3-month window SPI
result = risk.drought(method="spi", window=3)
print(f"3-Month SPI : {result['spi_3month']:.2f}")
print(f"Severity    : {result['drought_severity']}")

# Markov analysis
result = risk.drought(method="markov")
print(f"P(dry|dry)  : {result['markov_p_dry']:.2f}")

# Hurst exponent
result = risk.drought(method="hurst")
print(f"Hurst       : {result['hurst_exponent']:.2f}")

# Combination of all three methods
result = risk.drought(method="combined", window=3)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `method` | `str` | `'spi'` | Calculation method among `'spi'`, `'markov'`, `'hurst'`, `'combined'` |
| `window` | `int` | `3` | Accumulation window in months (used by SPI) |

**Returns:** `dict` - Keys vary based on selected method:

| Key | Present if | Description |
|-----|------------|-------------|
| `spi_Nmonth` | `spi` or `combined` | SPI score for window N |
| `drought_severity` | `spi` or `combined` | Severity classification |
| `markov_p_dry` | `markov` or `combined` | P(dry next | dry day) |
| `hurst_exponent` | `hurst` or `combined` | Hurst exponent H |

**SPI Severity Levels:**

| SPI | Severity |
|-----|----------|
| > 1.0 | `no_drought` (wet period) |
| -1.0 to 1.0 | `mild` (normal conditions) |
| -1.5 to -1.0 | `moderate` |
| < -1.5 | `severe` |

**Exceptions:**

- `ValidationError`: unsupported calculation method.

---

### `spi(window)`

Calculates the Standardized Precipitation Index (SPI) following McKee et al. (1993).

Algorithm:

1. Rolling precipitation sum over specified time window.
2. Gamma distribution fitting on strictly positive rainfall sums.
3. Probability mass correction for zero-rain days.
4. Inverse normal cumulative distribution transformation to output SPI score.

```python
spi_val = risk.spi(window=3)
print(f"3-Month SPI : {spi_val:.2f}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `window` | `int` | `3` | Accumulation window in months |

**Returns:** `float` - SPI score rounded to 2 decimal places. Returns `0.0` if series standard deviation is zero.

**Exceptions:**

- `DataError`: empty series, fewer than 30 calculated windows, fewer than 10 non-zero rainfall sums, or Gamma distribution fit failure.

---

### `markov(thresh)`

Calculates Markov transition probabilities between dry and wet days.

```python
trans = risk.markov(thresh=1.0)

print(f"P(dry  | previous dry) : {trans['p_dry_dry']:.2f}")
print(f"P(wet  | previous dry) : {trans['p_dry_wet']:.2f}")
print(f"P(dry  | previous wet) : {trans['p_wet_dry']:.2f}")
print(f"P(wet  | previous wet) : {trans['p_wet_wet']:.2f}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `thresh` | `float` | `1.0` | Rainfall threshold in mm to classify a day as wet |

**Returns:** `dict`

| Key | Description |
|-----|-------------|
| `p_dry_dry` | P(dry next / dry day) |
| `p_dry_wet` | P(wet next / dry day) |
| `p_wet_dry` | P(dry next / wet day) |
| `p_wet_wet` | P(wet next / wet day) |

**Exceptions:**

- `DataError`: empty historical series.

---

### `hurst(window)`

Calculates the Hurst exponent using the rescaled range (R/S) method.

An exponent `H > 0.5` indicates climate persistence (long memory): dry or wet spells tend to persist over time.

```python
h = risk.hurst(window=1095)
print(f"Hurst exponent : {h:.2f}")

if h > 0.5:
    print("Climate persistence detected (long memory).")
elif h < 0.5:
    print("Antipersistent behavior.")
else:
    print("Random walk (no memory).")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `window` | `int` | `1095` | Maximum analysis window size in days (approx. 3 years) |

**Returns:** `float` - Exponent H bounded in range `0.01` to `0.99`. Returns `0.5` if series is too short for reliable regression.

**Exceptions:**

- `DataError`: fewer than 100 days of data.

---

### `rain_prob(days, min_mm)`

Forecasts rain probability for upcoming days.

Combines two sources:

- Open-Meteo forecast API (70% weight).
- Markov transition probability from local historical data (30% weight).

```python
prob = risk.rain_prob(days=3, min_mm=1.0)

print(f"Tomorrow       : {prob['tomorrow'] * 100:.0f}%")
print(f"In 2 days      : {prob['2_days'] * 100:.0f}%")
print(f"Message        : {prob['message']}")
print(f"Recommendation : {prob['recommendation']}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `days` | `int` | `1` | Number of forecast days (1 to 7) |
| `min_mm` | `float` | `1.0` | Rainfall threshold in mm to classify a day as wet |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `tomorrow` | `float` | Rain probability for tomorrow (if `days >= 1`) |
| `N_days` | `float` | Rain probability for day N (N >= 2) |
| `message` | `str` | Summary phrase indicating maximum risk |
| `recommendation` | `str` | Agronomic recommendation |

**Recommendations:**

| Maximum Risk | Recommendation |
|--------------|----------------|
| > 70% | High leaching risk - postpone chemical applications |
| < 20% | Dry conditions expected - optimal window for chemical treatments |
| Other | Caution recommended for field operations |

**Exceptions:**

- `DataError`: forecast data missing or empty.

---

## Deprecated Methods

| Legacy Method | Replaced By | Since |
|---------------|-------------|-------|
| `drought_index(method, window_months)` | `drought(method, window)` | v1.2.0 |
| `markov_transition(threshold_mm)` | `markov(thresh)` | v1.2.0 |
| `hurst_exponent(window)` | `hurst(window)` | v1.2.0 |
| `rain_probability(days_ahead, min_rainfall_mm)` | `rain_prob(days, min_mm)` | v1.2.0 |

## Deprecated Attributes

| Legacy Attribute | Replaced By | Since |
|------------------|-------------|-------|
| `rainfall_historical` | `rainfall` | v1.2.0 |
| `forecast_data` | `forecast` | v1.2.0 |

---

::: kadi.weather.risk.Risk
