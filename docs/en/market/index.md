# kadi.market - Agricultural Economics

The `kadi.market` module is the economic analysis engine of KadiPy. It dynamically models the Beninese agricultural market, enabling retrieval of real market prices (via the HAPI HumData API), forecasting price evolutions, evaluating real logistics costs, and producing actionable recommendations for spatial arbitrage, storage, and crop portfolio management.

---

## Architecture

The module is centered around the `Market` class, which orchestrates four specialized sub-modules:

```
Market
├── pricing    : Pricing (acquisition, normalization, anomalies, seasonality)
├── forecast   : Forecasting (linear regression with Fourier seasonality)
├── logistics  : Logistics (OSRM distances, transport costs, weather integration)
└── advisor    : Advisor (spatial arbitrage, storage, crop portfolio optimization)
```

Each sub-module can be used standalone or through the `Market` facade.

---

## Importing

```python
import kadi as kd

# Main Facade
from kadi.market import Market

# Direct sub-module access
from kadi.market import Pricing, Forecasting, Logistics, Advisor
```

---

## Initialization

```python
import kadi as kd

# Basic initialization (fetching real data via HAPI HumData API)
market = kd.Market(lat=9.30, lon=2.08, location="Parakou")

# Simulation mode (no network requests, clean dummy data)
market = kd.Market(lat=9.30, lon=2.08, location="Parakou", sim=True)

# With weather integration (dynamic logistics cost adjustments)
weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
market = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat` | `float` | required | Latitude (between 2.5° and 12.5° N) |
| `lon` | `float` | required | Longitude (between -1.5° and 4.0° E) |
| `location` | `str` | required | Market name (e.g. `"Cotonou"`, `"Parakou"`) |
| `weather` | `Weather` | `None` | Weather instance for climate adjustment |
| `sim` | `bool` | `False` | If True, forces simulation mode (no network requests) |

**Initialization Exceptions:**

- `TypeError`: if `lat`, `lon`, or `location` are of an incorrect data type.
- `ValueError`: if coordinates fall outside Benin bounding box, or if `location` is empty.

---

## Public Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `lat` | `float` | Reference latitude |
| `lon` | `float` | Reference longitude |
| `location` | `str` | Reference market name |
| `sim` | `bool` | Active simulation mode flag |
| `weather` | `Weather` | Weather session (`None` if not provided) |
| `pricing` | `Pricing` | Pricing sub-module |
| `forecast` | `Forecasting` | Forecasting sub-module |
| `logistics` | `Logistics` | Logistics sub-module |
| `advisor` | `Advisor` | Decision support sub-module |

---

## Market Facade Methods

### `price(crop, days, normalize, sim)`

Retrieves, normalizes, and summarizes market prices for a crop at this market location.

```python
summary = market.price("maize", days=90)

print(f"Median      : {summary['prix_median']} XOF/kg")
print(f"Range       : {summary['prix_min']} - {summary['prix_max']} XOF/kg")
print(f"Observations: {summary['nb_observations']}")
print(f"Confidence  : {summary['confidence_score']:.2f}")
print(f"Simulated   : {summary['is_sim']}")
```

**Returns:** `dict` containing keys `crop`, `market`, `prix_median`, `prix_min`, `prix_max`, `prix_moyen`, `nb_observations`, `nb_anomalies`, `is_sim`, `confidence_score`, `source`, `donnees` (full DataFrame).

---

### `predict(crop, ahead, confidence_interval, days, sim)`

Predicts future price for a crop using linear regression with seasonal features (Fourier harmonics).

```python
forecast = market.predict("maize", ahead=30)

print(f"Predicted price in 30d : {forecast['predicted_price']} XOF/kg")
print(f"90% Interval           : [{forecast['low_90']}, {forecast['high_90']}]")
print(f"RMSE                   : {forecast['rmse']} XOF/kg")
print(f"History data points    : {forecast['nb_history_pts']}")
```

**Returns:** `dict` containing `predicted_price`, `low_90`, `high_90`, `confidence`, `model_used`, `rmse`, `is_sim`, `confidence_score`, `nb_history_pts`, `ahead`, `crop`, `market`.

---

### `seasonality(crop, days, sim)`

Calculates 12 monthly seasonal price indices for a crop.

```python
season = market.seasonality("rice", days=730)

print(f"Peak month   : {season['mois_pic']}")
print(f"Trough month : {season['mois_creux']}")
print(f"Confidence   : {season['confiance']:.2f}")
```

**Returns:** see [pricing.md](pricing.md), section `seasonality()`.

---

### `climate_risk(ahead)`

Evaluates climate risk for the market location. Requires a `weather` instance passed during initialization.

```python
risk = market.climate_risk(ahead=7)

if risk["weather_available"]:
    print(risk["recommendation"])
    print(f"Rain prob (day 1): {risk['prob_pluie_j1'] * 100:.0f}%")
    print(f"Drought severity : {risk['drought_severity']}")
```

**Returns:** `dict` containing `weather_available`, `prob_pluie`, `drought_index`, `recommendation`, `prob_pluie_j1`, `drought_severity`.

---

## Complete Examples

### 1. Market Prices

```python
import kadi as kd

market = kd.Market(lat=9.30, lon=2.08, location="Parakou")

summary = market.price("maize", days=90)
print(f"Median : {summary['prix_median']} XOF/kg")
print(f"Source : {summary['source']}")
```

### 2. Spatial Arbitrage

```python
# Is it profitable to transport 10 tonnes of maize from Parakou to Cotonou?
decision = market.advisor.arbitrage(
    crop="maize",
    m_from="Parakou",
    to="Cotonou",
    qty=10.0,
)
print(decision["recommandation"])
print(f"Net gain  : {decision['gain_net_percent']:.1f}%")
print(f"Confidence: {decision['confidence_score']:.2f}")
```

### 3. Storage Decision

```python
# Store 5 tonnes of yam for 3 months or sell now?
storage = market.advisor.store_sell(
    crop="yam",
    market="Abomey",
    price=250_000.0,
    qty=5.0,
    months=3,
)
print(storage["recommandation_binaire"])
print(f"Estimated margin : {storage['marge_nette_cfa']:,.0f} XOF")
```

### 4. Crop Portfolio Optimization

```python
portfolio_decision = market.advisor.optimize(
    land_ha=10.0,
    climate={"drought_severity": "mild"},
    market={"maize": 285.0, "cowpea": 580.0, "sorghum": 210.0},
)
print(f"Method          : {portfolio_decision['methode']}")
print(f"Expected revenue: {portfolio_decision['revenu_attendu_cfa']:,.0f} XOF")
for crop, ha in portfolio_decision["repartition_hectares"].items():
    print(f"  {crop} : {ha:.1f} ha")
```

### 5. Climate Risk

```python
weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
market = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)

risk = market.climate_risk(ahead=7)
print(risk["recommendation"])
```

---

## Data Modes and Fallback Loop

| Level | Source | `is_sim` | `confidence_score` |
|-------|--------|----------|--------------------|
| 1 | Local SQLite Cache | `False` | Variable (original score) |
| 2 | HAPI HumData API (WFP/OCHA) | `False` | `0.9` |
| 3 | Simulation Mode (no network) | `True` | `0.1` |

In simulation mode (`sim=True` or absent WFP API credentials), returned data is explicitly tagged `is_sim=True` and must not be used for actual commercial decisions.

---

## Deprecated Methods

| Legacy Method | Replaced By | Since |
|---------------|-------------|-------|
| `price_crop(crop, days_back)` | `price(crop, days)` | v1.2.0 |
| `predict_price(crop, days_ahead)` | `predict(crop, ahead)` | v1.2.0 |
| `assess_climate_risk(days_ahead)` | `climate_risk(ahead)` | v1.2.0 |

## Deprecated Classes

| Legacy Class | Replaced By | Since |
|--------------|-------------|-------|
| `MarketPricing` | `Pricing` | v1.2.0 |
| `MarketForecasting` | `Forecasting` | v1.2.0 |
| `MarketLogistics` | `Logistics` | v1.2.0 |
| `DecisionSupport` | `Advisor` | v1.2.0 |

---

## Sub-modules

- [Pricing](pricing.md)
- [Forecasting](forecasting.md)
- [Logistics](logistics.md)
- [Decision Support (Advisor)](decision_support.md)
