<p align="right">
  <a href="../README.md">Français</a> | <strong>English</strong>
</p>

<div align="center" style="padding-bottom: 40px">
  <img src="../img/kadipy-long.png" alt="KadiPy" width="100%" height="400px">
  <br>
  <p><strong>Processing, analysis, and modeling of agricultural and economic data</strong></p>
</div>

----

# KadiPy: the "pandas" of African agriculture

**KadiPy** is an open-source Python library designed for agronomists,
researchers, and developers working on agriculture in Benin and West
Africa. It offers a unified interface to ingest, clean, analyze,
and model weather data, agricultural market prices, road logistics costs,
and crop yield series, built with an offline-first architecture.

<br/>

## Key Features

- **Unified Ingestion and I/O (`kadi.io`)**: expressive functions `read_csv`,
  `read_excel`, `read_json`, `read_netcdf`, `read_api` with automatic format
  detection, and their writing counterparts (`write_csv`, `write_excel`, etc.).
  The `write`, `info`, and `ping` functions work seamlessly with any format.

- **Agronomic Meteorology (`kadi.weather`)**: `Weather` facade for historical
  and forecast weather data (CHIRPS + Open-Meteo), rainy season onset detection
  (Sivakumar, Walter-Anyadike), soil water balance (FAO-56), evapotranspiration
  (ET0 Hargreaves-Samani), and drought indices (SPI, Markov, Hurst).

- **Agricultural Economics and Markets (`kadi.market`)**: `Market` facade for
  tracking real prices (WFP/HAPI HumData), price forecasting (`Forecasting`),
  road logistics cost calculations (`Logistics`), and decision support
  (`Advisor`) for spatial arbitrage and strategic storage.

- **Pipeline and Standardization (`kadi.kidas`)**: raw data cleaning
  (`Cleaner`), schema validation (`Validator`), crop name and GPS coordinate
  normalization (`Normalizer`), local SQLite persistence (`Cache`), and end-to-end
  processing chain (`Pipeline`).

<br/>

## Installation

### Via PyPI

```bash
pip install kadipy
```

### From Source

```bash
git clone https://github.com/delsDin/kadipy.git
cd kadipy
pip install -e ".[dev]"
```

### Optional Dependencies

```bash
# Support for legacy Excel files (.xls, pre-2003)
pip install "kadipy[xls]"

# Geospatial processing (CHIRPS raster clipping)
pip install "kadipy[geospatial]"
```

### Environment Configuration

Create a `.env` file at the root of the project to enable live data sources:

```env
# WFP DataBridges API key (optional: public HAPI HumData data is used without it)
WFP_API_Token=your_token_here

# Manual fuel price in XOF/liter (optional)
BENIN_FUEL_PRICE=680
```

<br/>

## Module Overview

| Module | Facade / Components | Description |
|--------|---------------------|-------------|
| `kadi.io` | `read_csv`, `read_excel`, `read_json`, `read_netcdf`, `read_api`, `write`, `info`, `ping` | Input and output with automatic format detection |
| `kadi.weather` | `Weather`, `Location`, `Phenology`, `Hydrology`, `Risk` | Weather, forecasts, historical data, and agronomic indicators |
| `kadi.market` | `Market`, `Pricing`, `Forecasting`, `Logistics`, `Advisor` | Economic analysis, prices, logistics, and decision support |
| `kadi.kidas` | `Cleaner`, `Validator`, `Normalizer`, `Pipeline`, `Cache` | Processing, quality control, and SQLite persistence |

<br/>

## Project Structure

```
kadipy/
├── kadi/
│   ├── io/              # Unified input and output
│   ├── market/          # Agricultural economics and markets
│   ├── weather/         # Agronomic meteorology
│   ├── kidas/           # Processing pipeline and standardization
│   ├── _sources/        # External clients (WFP, CHIRPS, SoilGrids)
│   ├── cache.py         # Shared SQLite cache
│   ├── config.py        # Centralized configuration
│   └── exceptions.py    # Custom exceptions
├── tests/               # Test suite (pytest)
├── docs/                # MkDocs documentation
├── examples/            # Jupyter example notebooks
├── config/              # Configuration files
└── pyproject.toml       # Package dependencies and metadata
```

<br/>

## Running Tests

```bash
# Basic execution
pytest tests/ -q

# With code coverage report
pytest tests/ --cov=kadi --cov-report=term-missing
```

Tests cover all modules (`io`, `market`, `weather`, `kidas`), including remote connectors with network-free mocking and infrastructure components (`kadi.cache`, `kadi.config`). No API key is required to run them. GitHub Actions CI ensures global coverage stays above **70%**.

<br/>

## Backward Compatibility

Legacy class names from versions prior to v1.2.0 issue a `DeprecationWarning` and will be removed in KadiPy v2.0:

| Legacy Name (pre-v1.2.0) | New Name |
|--------------------------|----------|
| `WeatherSession` | `Weather` |
| `DataCleaner` | `Cleaner` |
| `DataValidator` | `Validator` |
| `DataNormalizer` | `Normalizer` |
| `DataCache` | `Cache` |
| `DataPipeline` | `Pipeline` |
| `CSVDataSource` | `CSVSource` |

<br/>

## Geographic Scope (v1.x)

KadiPy v1.x is designed **exclusively for Benin**. GPS coordinate validation, phenological algorithms, logistics parameters, and price datasets are calibrated for the Beninese context.

Support for other West African countries is planned for future releases.

---

## Documentation

Full documentation (API guides, examples) is available at:
**https://delsDin.github.io/kadipy/**

---

## License and Contribution

- **License**: MIT
- **GitHub Repository**: https://github.com/delsDin/kadipy
- **Python Compatibility**: >= 3.9
- **Current Version**: 1.2.0
