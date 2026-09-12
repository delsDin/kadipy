# Logistics (`kadi.market.logistics`)

The `Logistics` class models real logistics friction across Beninese trade corridors: transport costs, checkpoint harassment fees, and merchantable quality degradation of agricultural produce.

Since v1.2.0, it optionally integrates weather forecasts to dynamically adjust the road coefficient (`gamma_route`) and quality loss based on expected rain probability.

It is used internally by `Market` and accessible via `market.logistics`. It can also be instantiated directly.

---

## Direct Importing

```python
from kadi.market import Logistics
```

---

## Initialization

```python
from kadi.market import Logistics

# Without weather integration (V1 behavior)
logistics = Logistics()

# With weather integration (dynamic cost adjustment based on rain forecast)
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
logistics = Logistics(weather=weather)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `cache_file` | `str` | `None` | Path to JSON distance cache file. Default: `~/.kadi/osrm_cache.json` |
| `weather` | `Weather` | `None` | Weather session for climate cost adjustments. If None, no adjustment (V1 behavior) |

**Public Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `weather` | `Weather` | Injected weather session (or None) |
| `cache_file` | `str` | Distance cache file path |
| `cache` | `dict` | In-memory cache dictionary with keys `'coords'` and `'distances'` |

---

## Methods

### `transfer_cost(origine, destination, prix_carburant, crop)`

Calculates total transfer cost from an origin city to a destination city.

**Formula:**

```
C_transfer = C_info
           + Distance * (gamma_effective * P_fuel / 100 + mu_checkpoints)
           + C_quality(crop, distance, rain)
```

Where:
- `C_info` = fixed information search cost (phone calls, local travel), configurable in `config.py` (default: 5,000 XOF)
- `gamma_effective` = `gamma_route * (1 + alpha_rain * prob_rain)`: weather surcharge multiplier if a weather session is available
- `mu_checkpoints` = average checkpoint harassment fee per km (default: 15 XOF/km)
- `C_quality` = variable merchantable quality loss per crop type and weather condition

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
market = kd.Market(lat=9.3, lon=2.3, location="Parakou", weather=weather)

# Transfer cost with weather integration
cost = market.logistics.transfer_cost(
    origine="Parakou",
    destination="Cotonou",
    crop="maize",
)

print(f"Total cost        : {cost['total_cost_cfa']:,.0f} XOF")
print(f"Rain forecast     : {cost['prob_pluie'] * 100:.0f}%")
print(f"Effective gamma   : {cost['gamma_effectif']:.4f}")

# Breakdown details
d = cost["details"]
print(f"  Distance        : {d['distance_km']:.1f} km")
print(f"  Search cost     : {d['search_costs']:,.0f} XOF")
print(f"  Transport cost  : {d['transport_costs']:,.0f} XOF")
print(f"  Quality loss    : {d['quality_loss']:,.0f} XOF")
print(f"  Fuel price used : {d['fuel_price_used']:.0f} XOF/liter")
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `origine` | `str` | required | Departure city (e.g. `'Parakou'`) |
| `destination` | `str` | required | Arrival city (e.g. `'Cotonou'`) |
| `prix_carburant` | `float` | `None` | Fuel price in XOF per liter. If None, fetched automatically |
| `crop` | `str` | `None` | Transported crop code for quality loss calculation. If None, uses default factor |

**Returns:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `total_cost_cfa` | `float` | Total transfer cost in XOF |
| `prob_pluie` | `float` | Rain probability used (0.0 if no weather session) |
| `gamma_effectif` | `float` | Effective road coefficient applied |
| `details` | `dict` | Breakdown dictionary of each cost component |

**Keys in `details`:**

| Key | Description |
|-----|-------------|
| `distance_km` | Road distance in km |
| `search_costs` | Fixed information search cost (XOF) |
| `transport_costs` | Distance-based transport cost (fuel + checkpoints) (XOF) |
| `quality_loss` | Merchantable quality loss value (XOF) |
| `fuel_price_used` | Fuel price applied (XOF/liter) |
| `gamma_route_base` | Base road coefficient before weather adjustment |
| `gamma_effectif` | Final road coefficient after weather adjustment |
| `prob_pluie` | Rain probability used |
| `crop` | Crop code (`'_default'` if unspecified) |

**Quality Loss Factors by Crop (XOF/km/tonne):**

| Crop | Factor | Crop | Factor |
|------|--------|------|--------|
| `maize`, `sorghum`, `millet` | 5.0 | `cowpea`, `soybean` | 7.0 |
| `rice` | 6.0 | `yam` | 12.0 |
| `cassava` | 10.0 | `tomato` | 25.0 |
| `onion` | 20.0 | (default) | 8.0 |

Under rainy conditions, quality loss increases according to: `C_quality = factor * distance_km * (1 + beta_rain * prob_rain)`, where `beta_rain` is configurable in `config.py` (default: 0.5).

---

### `distance(origine, destination)`

Retrieves road distance between two Beninese cities.

**Cascade Strategy:**

1. Local cache (result from previous call, persisted in JSON file)
2. Nominatim geocoding (OpenStreetMap) + OSRM routing
3. Haversine fallback (great-circle distance multiplied by 1.3 tortuosity factor) if OSRM is unavailable
4. Default fallback of 100 km if geocoding fails

```python
d = market.logistics.distance("Parakou", "Cotonou")
print(f"Road distance : {d:.1f} km")

# Result automatically cached
d2 = market.logistics.distance("Cotonou", "Parakou")   # Returned from cache
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `origine` | `str` | Departure city name |
| `destination` | `str` | Arrival city name |

**Returns:** `float` - Estimated distance in kilometers.

The result is automatically cached in memory for the current session and saved to `cache_file` for future sessions.

---

## Weather Integration

When a `weather` instance is provided during initialization, transfer cost calculation is automatically adjusted:

```
gamma_effective = gamma_route * (1 + alpha_rain * prob_rain)
```

- `gamma_route`: base coefficient (configurable in `config.py`, default: 1.2)
- `alpha_rain`: weather surcharge intensity (default: 0.25)
- `prob_rain`: tomorrow's rain probability, fetched via `weather.rain_prob(days=1)`

Rain probability is fetched once per session (cached) to prevent redundant weather API calls.

**Example:**

With `prob_rain=0.8` and `alpha=0.25`, the road coefficient increases from 1.2 to `1.2 * (1 + 0.25 * 0.8) = 1.44`, representing a 20% surge in transport costs.

---

## Fuel Price Retrieval Strategy

The `transfer_cost()` method automatically retrieves fuel price using the following priority order:

| Priority | Source |
|----------|--------|
| 1 | `BENIN_FUEL_PRICE` environment variable |
| 2 | In-memory session cache (one query per session) |
| 3 | `config/fuel_prices.json` file hosted on GitHub |
| 4 | Fallback value from `config.py` (default: 680 XOF/liter) |

---

## Deprecated Methods

| Legacy Method | Replaced By | Since |
|---------------|-------------|-------|
| `calculate_transfer_cost(origine, destination)` | `transfer_cost(origine, destination)` | v1.2.0 |
| `get_distance(origine, destination)` | `distance(origine, destination)` | v1.2.0 |

## Deprecated Class

| Legacy Class | Replaced By | Since |
|--------------|-------------|-------|
| `MarketLogistics` | `Logistics` | v1.2.0 |

---

## Complete Example

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
market = kd.Market(lat=9.3, lon=2.3, location="Parakou", weather=weather)

# Compare transfer costs for two crops (tomato being highly perishable)
crops = ["maize", "tomato"]
for crop in crops:
    cost = market.logistics.transfer_cost("Parakou", "Cotonou", crop=crop)
    print(
        f"{crop:8s} -> {cost['total_cost_cfa']:,.0f} XOF "
        f"(quality loss: {cost['details']['quality_loss']:,.0f} XOF)"
    )

# Distance only
d = market.logistics.distance("Abomey", "Cotonou")
print(f"Abomey - Cotonou : {d:.1f} km")
```

---

::: kadi.market.logistics.Logistics
