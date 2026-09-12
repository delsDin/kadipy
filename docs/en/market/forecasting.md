# Price Forecasting (`kadi.market.forecasting`)

The `Forecasting` class predicts future crop prices based on historical price data. The model uses linear regression enriched with seasonal features (Fourier harmonics), trained on demand using the provided historical dataset. If historical data is insufficient (fewer than 20 observations), a clearly marked simulated fallback is returned.

---

## Direct Importing

```python
from kadi.market import Forecasting
```

---

## Initialization

`Forecasting` is created automatically by `Market` and is accessible via `market.forecast`. For direct instantiation:

```python
from kadi.market import Forecasting

forecast = Forecasting()
```

The module has no persistent state: the model is trained on each call to `predict()` using the provided data.

---

## Methods

### `predict(crop, market, ahead, ci, hist)`

Predicts future price for a crop at a given market location.

**Internal Pipeline:**

1. History validation (minimum 20 observations required). If insufficient, switches to simulated fallback.
2. Feature engineering: linear trend + 2 Fourier harmonics (annual and semi-annual cycles over 365 / 182.5 days).
3. Linear regression training on complete history.
4. RMSE calculation via time series cross-validation (TimeSeriesSplit, 3 folds).
5. Prediction interval calculation based on real RMSE, expanding with square root of time horizon.

```python
import kadi as kd

market = kd.Market(lat=9.3, lon=2.3, location="Parakou")

# Fetching price history
df = market.pricing.fetch("maize", "parakou", days=365)

# 30-day forecast with 90% confidence interval
prediction = market.forecast.predict(
    crop="maize",
    market="parakou",
    ahead=30,
    ci=0.9,
    hist=df,
)

print(f"Predicted price : {prediction['predicted_price']:.2f} XOF/kg")
print(f"Interval        : [{prediction['low_90']:.2f}, {prediction['high_90']:.2f}]")
print(f"RMSE            : {prediction['rmse']} XOF/kg")
print(f"Model           : {prediction['model_used']}")
print(f"History points  : {prediction['nb_history_pts']}")
print(f"Simulated       : {prediction['is_simulated']}")
print(f"Confidence      : {prediction['confidence_score']:.2f}")
```

Via the `Market` facade (full pipeline in a single call):

```python
# Market.predict() handles fetching history automatically
prediction = market.predict("maize", ahead=30, confidence_interval=0.9, days=365)

print(f"Predicted price in 30d : {prediction['predicted_price']} XOF/kg")
print(f"Horizon used           : {prediction['ahead']} days")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `crop` | `str` | required | Crop code (e.g. `'maize'`) |
| `market` | `str` | required | Normalized market name (e.g. `'cotonou'`) |
| `ahead` | `int` | `7` | Forecast horizon in days |
| `ci` | `float` | `0.9` | Confidence level: `0.9` (90%) or `0.95` (95%) |
| `hist` | `pd.DataFrame` | `None` | History DataFrame with `'date'` and `'price'` columns |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `predicted_price` | `float` | Predicted price in XOF/kg |
| `low_90` | `float` | Lower bound of confidence interval |
| `high_90` | `float` | Upper bound of confidence interval |
| `confidence` | `float` | Confidence level used (0.9 or 0.95) |
| `model_used` | `str` | `'linear_regression_fourier'` or `'fallback_simule'` |
| `rmse` | `float` | RMSE in XOF/kg (None if simulated fallback) |
| `is_simulated` | `bool` | True if source data is simulated |
| `confidence_score` | `float` | Reliability score (0.0 to 1.0) |
| `nb_history_pts` | `int` | Number of historical data points used |
| `days_ahead` | `int` | Forecast horizon used |

**Confidence Score:**

The confidence score is calculated as follows:

```
source_score = 0.10 if is_simulated else 0.85
volume_factor = min(1.0, nb_pts / 100.0)
confidence_score = source_score * (0.5 + 0.5 * volume_factor)
```

A score of `0.85` is the maximum achievable with real data.
A score of `0.0` indicates a fully simulated fallback.

**Simulated Fallback:**

Activated if `hist` is missing or contains fewer than 20 valid observations. Returns `predicted_price=300.0` XOF/kg with `is_simulated=True` and `confidence_score=0.0`. Must not be used for actual commercial decisions.

---

## Deprecated Method

| Legacy Method | Replaced By | Since |
|---------------|-------------|-------|
| `predict_price(crop, market, days_ahead, historique)` | `predict(crop, market, ahead, hist)` | v1.2.0 |

## Deprecated Class

| Legacy Class | Replaced By | Since |
|--------------|-------------|-------|
| `MarketForecasting` | `Forecasting` | v1.2.0 |

---

::: kadi.market.forecasting.Forecasting
