# KadiPy

**KadiPy** is a Python library designed for agronomists, researchers, and developers working on agriculture in Benin and West Africa. Its objective is to simplify the processing and analysis of agricultural data, whether weather data, market prices, or harvest yields.

Think of it as the "pandas" of African agriculture.

---

## What KadiPy Does

KadiPy combines four complementary modules covering the entire agricultural data analysis lifecycle.

### `kadi.io` - Input and Output

Universal read and write functions with automatic format detection: `read_csv`, `read_excel`, `read_json`, `read_netcdf`, `read_api`, `write_csv`, `write_excel`, as well as generic functions `write`, `info`, and `ping`.

[View kadi.io documentation](io.md)

### `kadi.market` - Agricultural Economics

Analysis of Beninese agricultural markets using real price data (WFP/HAPI) or simulated data. Calculates arbitrage opportunities via `Advisor`, logistics costs via `Logistics`, price forecasts via `Forecasting`, and price analysis via `Pricing`.

[View kadi.market documentation](market/index.md)

### `kadi.weather` - Agronomic Meteorology

Unified interface via the `Weather` facade for historical and forecast weather data (CHIRPS + Open-Meteo). Calculates drought indices (`Risk`), rainfall probabilities, growing degree days (`Phenology`), and soil water balance (`Hydrology`).

[View kadi.weather documentation](weather/index.md)

### `kadi.kidas` - Data Processing and Standardization

Complete pipeline for ingestion, cleaning (`Cleaner`), validation (`Validator`), normalization (`Normalizer`), cache management (`Cache`), and processing chain (`Pipeline`).

[View kadi.kidas documentation](kidas/index.md)

---

## Installation

```bash
git clone https://github.com/delsDin/kadipy.git
cd kadipy

python -m venv .kadi_venv
source .kadi_venv/bin/activate

pip install -e ".[dev]"

# Optional: support for legacy Excel files (.xls)
pip install -e ".[dev,xls]"
```

### Environment Configuration

Create a `.env` file at the root of the project to enable real data sources:

```env
# WFP DataBridges API Key (optional: public HAPI HumData data is used without it)
WFP_API_Token=your_key_here

# Manual fuel price in XOF/liter (optional)
BENIN_FUEL_PRICE=680
```

---

## Quick Start

### Reading and Inspecting Data

```python
import kadi as kd

df = kd.read_csv("recolte_2024.csv")
kd.info("recolte_2024.csv")
```

### Data Cleaning

```python
import kadi as kd

df = kd.read_csv("enquete_prix_2024.csv")
cleaner = kd.Cleaner(df)

df_clean, df_outliers = (
    cleaner
    .norm_text()
    .drop_dupes()
    .fill_missing(strategy="median", cols=["prix_xof_kg"])
    .drop_outliers(method="iqr", cols=["prix_xof_kg"])
)
```

### Weather Analysis

```python
import kadi as kd

weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")

risk = weather.rain_prob(days=1)
print(risk["recommendation"])

drought = weather.drought(method="spi", window=3)
print(f"Severity: {drought['drought_severity']}")
```

### Market Analysis

```python
import kadi as kd

market = kd.Market(lat=9.30, lon=2.08, location="Parakou")

summary = market.price("maize", days=90)
print(f"Median price: {summary['prix_median']} XOF/kg")
```

### Weather + Market Integration

```python
import kadi as kd

weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
market = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)

decision = market.advisor.arbitrage(
    crop="maize",
    m_from="Parakou",
    to="Cotonou",
    qty=10.0,
)
print(f"Recommendation: {decision['recommandation']}")
print(f"Net gain: {decision['gain_net_percent']:.1f}%")
```

---

## Running Tests

```bash
pytest tests/ -q

# With code coverage report
pytest tests/ --cov=kadi --cov-report=term-missing
```

The tests cover all modules (`io`, `market`, `weather`, `kidas`), including remote connectors without network dependencies, and infrastructure components (`kadi.cache`, `kadi.config`). No API key is required to run them. GitHub Actions CI verifies that overall coverage remains above **70%**.

---

## Project Structure

```
kadipy/
├── kadi/
│   ├── io/              # Unified input and output
│   ├── market/          # Agricultural economics and markets
│   ├── weather/         # Agronomic meteorology
│   ├── kidas/           # Processing and standardization pipeline
│   ├── _sources/        # External clients (WFP, CHIRPS, SoilGrids)
│   ├── cache.py         # Shared SQLite cache
│   ├── config.py        # Centralized configuration
│   └── exceptions.py    # Custom exceptions
├── tests/               # Test suite (pytest)
├── docs/                # Documentation
├── examples/            # Jupyter example notebooks
├── config/              # Configuration files
└── pyproject.toml       # Single source of truth for dependencies
```

---

## Geographic Area (v1.x)

KadiPy v1.x, v2.x is designed **exclusively for Benin**. GPS coordinate validation, phenological algorithms, logistical factors, and price data are calibrated for the Beninese context.

Support for other West African countries is planned for future releases.
