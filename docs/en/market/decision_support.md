# Decision Support (`kadi.market.decision_support`)

The `Advisor` class converts price forecasts and market data into operational recommendations: spatial arbitrage between markets, storage decision timing, and crop portfolio optimization.

It is used internally by the `Market` facade and accessible via `market.advisor`. It can also be instantiated directly.

---

## Direct Importing

```python
from kadi.market import Advisor
```

---

## Initialization

`Advisor` is created automatically by `Market` and is accessible via `market.advisor`. For direct instantiation:

```python
from kadi.market import Advisor, Forecasting, Logistics, Pricing

advisor = Advisor(
    forecast=Forecasting(),
    logistics=Logistics(),
    pricing=Pricing(),
)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `forecast` | `Forecasting` | `None` | Forecasting instance to estimate future prices |
| `logistics` | `Logistics` | `None` | Logistics instance for transport costs |
| `pricing` | `Pricing` | `None` | Pricing instance for real market prices |

If `pricing` is `None`, methods fall back to a default price of 300 XOF/kg with `is_simulated=True` and `confidence_score=0.0`.

**Public Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `forecast` | `Forecasting` | Price forecasting module |
| `logistics` | `Logistics` | Logistics module |
| `pricing` | `Pricing` | Pricing module |

---

## Methods

### `arbitrage(crop, m_from, to, qty)`

Evaluates the profitability of a physical merchandise transfer between two markets.

**Formula:**

```
Net Gain = (destination_price - origin_price) * 1000 * qty - transport_cost
```

The minimum profitability threshold is configurable in `config.py` (key `logistics.seuil_rentabilite_pct`, default: 10%).

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
market = kd.Market(lat=9.3, lon=2.3, location="Parakou", weather=weather)

# Is it profitable to transport 10 tonnes of maize from Parakou to Cotonou?
decision = market.advisor.arbitrage(
    crop="maize",
    m_from="Parakou",
    to="Cotonou",
    qty=10.0,
)

print(decision["recommandation"])           # 'TRANSPORTER' or 'NE PAS TRANSPORTER'
print(f"Total net gain: {decision['gain_net_total_cfa']:,.0f} XOF")
print(f"Net gain      : {decision['gain_net_percent']:.1f}%")
print(f"Transport cost: {decision['frais_logistiques_total']:,.0f} XOF")
print(f"Rain forecast : {decision['prob_pluie'] * 100:.0f}%")
print(f"Confidence    : {decision['confidence_score']:.2f}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `crop` | `str` | required | Crop code (e.g. `'maize'`) |
| `m_from` | `str` | `'Parakou'` | Purchase market |
| `to` | `str` | `'Cotonou'` | Sale market |
| `qty` | `float` | `1.0` | Quantity to transport in metric tonnes |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `recommandation` | `str` | `'TRANSPORTER'` or `'NE PAS TRANSPORTER'` |
| `gain_net_total_cfa` | `float` | Total net gain in XOF |
| `gain_net_percent` | `float` | Net gain as % of invested capital |
| `frais_logistiques_total` | `float` | Total transport costs in XOF |
| `prix_origine_xof_kg` | `float` | Purchase market price in XOF/kg |
| `prix_destination_xof_kg` | `float` | Sale market price in XOF/kg |
| `is_simulated` | `bool` | True if used prices are dummy/simulated |
| `confidence_score` | `float` | Recommendation confidence score (0-1) |
| `prob_pluie` | `float` | Rain probability used for logistics calculation |

**Confidence Score:**

Calculated as a weighted combination of three factors:

```
score = 0.5 * price_confidence
      + 0.3 * (0 if simulated, 1 if real)
      + 0.2 * min(1, |net_gain_pct| / 30)
```

**Exceptions:**

No exception is raised if data is missing: the method falls back to a default price of 300 XOF/kg with `is_simulated=True`.

---

### `store_sell(crop, market, price, qty, months)`

Evaluates whether it is more profitable to store a harvest or sell immediately.

**Net Expected Gain Formula per Tonne:**

```
E = E[P(t+n)] - P(t) - C_storage(n) - C_opportunity(n) - theta * Var(P)
```

Where:
- `C_storage` = 3,200 XOF/tonne/month (storage, loss, bags)
- `C_opportunity` = 1.5%/month of current price (working capital lock-up)
- `theta` = 0.04 (risk aversion coefficient)

```python
# Store 5 tonnes of yam for 3 months or sell now?
storage = market.advisor.store_sell(
    crop="yam",
    market="Abomey",
    price=250_000.0,    # Current price in XOF/tonne
    qty=5.0,
    months=3,
)

print(storage["recommandation_binaire"])   # 'STOCKER' or 'VENDRE IMMÉDIATEMENT'
print(f"Total net margin   : {storage['marge_nette_cfa']:,.0f} XOF")
print(f"Margin per tonne   : {storage['marge_nette_par_tonne']:,.0f} XOF")
print(f"Estimated future P : {storage['prix_futur_estime']:,.0f} XOF/tonne")
print(f"Horizon            : {storage['horizon_mois']} months")
print(f"Confidence         : {storage['confidence_score']:.2f}")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `crop` | `str` | required | Crop code |
| `market` | `str` | `'Parakou'` | Reference market for forecasting |
| `price` | `float` | `300000.0` | Current price in XOF per tonne |
| `qty` | `float` | `1.0` | Quantity in tonnes |
| `months` | `int` | `None` | Storage horizon in months. If None, reads default from config.py (default: 3 months) |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `recommandation_binaire` | `str` | `'STOCKER'` or `'VENDRE IMMEDIATEMENT'` |
| `marge_nette_cfa` | `float` | Total expected net gain in XOF |
| `marge_nette_par_tonne` | `float` | Expected net gain per tonne |
| `prix_futur_estime` | `float` | Predicted price at horizon (XOF/tonne) |
| `horizon_mois` | `int` | Storage horizon used |
| `is_simulated` | `bool` | True if forecast data is simulated |
| `confidence_score` | `float` | Confidence score (0-1) |

If no `forecast` module is available, the method applies a conservative 15% increase assumption on the current price.

---

### `optimize(land_ha, climate, market, yields)`

Optimizes crop allocation over available arable land.

Uses `scipy.optimize.linprog` (HiGHS method) to maximize expected revenue under land capacity and diversification constraints. If scipy is unavailable, a heuristic fallback is applied.

**Optimization Model:**

```
Maximize: sum(price_i * yield_i * x_i)
Subject to: sum(x_i) <= land_ha
            0 <= x_i <= 0.7 * land_ha  (minimum 30% diversification)
```

**Climate Adjustments (key `drought_severity`):**

| Severity | Effect |
|----------|--------|
| `'severe'` | cowpea yield * 1.3, maize and rice * 0.7 |
| `'moderate'` | maize yield * 0.85 |
| `'mild'` or `'no_drought'` | no adjustment |

```python
# Optimization under mild climate conditions
portfolio_decision = market.advisor.optimize(
    land_ha=10.0,
    climate={"drought_severity": "mild"},
    market={"maize": 285.0, "cowpea": 580.0, "sorghum": 210.0},
)

print(f"Method          : {portfolio_decision['methode']}")
print(f"Expected revenue: {portfolio_decision['revenu_attendu_cfa']:,.0f} XOF")
print(f"Confidence      : {portfolio_decision['confidence_score']:.2f}")
for crop, ha in portfolio_decision["repartition_hectares"].items():
    print(f"  {crop} : {ha:.1f} ha")

# Severe drought scenario (favors cowpea)
drought_decision = market.advisor.optimize(
    land_ha=5.0,
    climate={"drought_severity": "severe"},
    market={"maize": 285.0, "cowpea": 620.0, "sorghum": 210.0},
)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `land_ha` | `float` | `1.0` | Available arable land in hectares |
| `climate` | `dict` | `None` | Climate forecast dictionary (see table below) |
| `market` | `dict` | `None` | Current median prices per crop in XOF/kg |
| `yields` | `dict` | `None` | Expected yields in t/ha. If None, uses FAO/INSAE Benin reference yields |

**Keys in `climate`:**

| Key | Type | Description |
|-----|------|-------------|
| `drought_severity` | `str` | Severity: `'no_drought'`, `'mild'`, `'moderate'`, `'severe'` |
| `secheresse_anticipee` | `bool` | V1 backward compatibility: True maps to severity `'severe'` |
| `prob_pluie_7j` | `float` | 7-day rain probability |

**Reference Yields (FAO/INSAE Benin):**

| Crop | Yield (t/ha) |
|------|--------------|
| `maize` | 1.8 |
| `sorghum` | 1.2 |
| `millet` | 1.0 |
| `rice` | 2.5 |
| `cowpea` | 0.7 |
| `soybean` | 1.2 |
| `yam` | 8.0 |
| `cassava` | 12.0 |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `repartition_hectares` | `dict[str, float]` | Allocated land per crop (ha) |
| `revenu_attendu_cfa` | `float` | Total expected revenue in XOF |
| `recommandation` | `str` | Explanatory text of the decision |
| `methode` | `str` | `'scipy_linprog'` or `'heuristique'` |
| `confidence_score` | `float` | Confidence score (0.75 normal, 0.55 drought, 0.3 heuristic) |

**Heuristic Fallback:**

Activated if scipy is missing or if no crop has a known price. Default allocation is: maize 50%, soybean 30%, cowpea 20%. Under severe drought: maize 30%, soybean 30%, cowpea 40%.

---

## Deprecated Methods

| Legacy Method | Replaced By | Since |
|---------------|-------------|-------|
| `arbitrage_decision(crop, origine, destination, qty_tons)` | `arbitrage(crop, m_from, to, qty)` | v1.2.0 |
| `storage_vs_sell_now(crop, market, current_price, qty_tons, mois_stockage)` | `store_sell(crop, market, price, qty, months)` | v1.2.0 |
| `portfolio_optimization(available_land_ha, climate_forecast, market_forecast)` | `optimize(land_ha, climate, market)` | v1.2.0 |

## Deprecated Class

| Legacy Class | Replaced By | Since |
|--------------|-------------|-------|
| `DecisionSupport` | `Advisor` | v1.2.0 |

---

::: kadi.market.decision_support.Advisor
