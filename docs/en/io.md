# kadi.io: Input and Output

The `kadi.io` module is the entry point for all data reading and writing operations in KadiPy. It covers local files (CSV, Excel, JSON, NetCDF) and REST APIs, with automatic format detection based on file extension or URL.

The source classes (`CSVSource`, `ExcelSource`, etc.) are defined in `kadi.kidas.sources` and re-exported here for direct access. The `read_*` and `write_*` functions are shortcuts that instantiate these classes and immediately call their `read()` or `write()` method.

---

## Quick Start

```python
import kadi as kd

# Reading
df = kd.read_csv("recoltes_2024.csv")
df = kd.read_excel("prix_marche.xlsx")
df = kd.read_json("campagne_2023.json")
df = kd.read_api("https://api.data.bj/agriculture/prices")

# Writing
kd.write_csv(df, "export.csv")
kd.write(df, "export.xlsx")       # Automatic format detection

# Inspection
kd.info("recoltes_2024.csv")      # Metadata without loading the full file
kd.ping("recoltes_2024.csv")      # Check if source is accessible
```

---

## Read Functions

These functions read data from a source and return a `pandas.DataFrame`. Each function accepts optional arguments passed down to the underlying source class.

### `read_csv(filepath, **kwargs)`

Reads a CSV file. Automatically detects encoding (via `chardet`), delimiter (`,`, `;`, tab, `|`), and decimal separator.

```python
import kadi as kd

df = kd.read_csv("recoltes_2024.csv")

# Override parameters if automatic detection is not sufficient
from kadi.io import CSVSource
df = CSVSource("export.csv", sep=";", decimal=",", encoding="latin-1").read()
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filepath` | `str` or `Path` | required | Path to the CSV file |
| `encoding` | `str` | `'auto'` | File encoding (`'utf-8'`, `'latin-1'`, etc.) |
| `sep` | `str` | `'auto'` | Column delimiter |
| `decimal` | `str` | `'auto'` | Decimal separator |
| `n` | `int` | `None` | Maximum number of rows to read |
| `skip` | `int` | `None` | Number of rows to skip at file start |

**Returns:** `pandas.DataFrame`

**Exceptions:** `ConnectError` if file is not found, `ReadError` if reading fails despite trying multiple encodings.

---

### `read_excel(filepath, **kwargs)`

Reads an Excel file (`.xlsx` or `.xls`).

```python
df = kd.read_excel("prix_marche.xlsx")

# Read a specific sheet
from kadi.io import ExcelSource
df = ExcelSource("rapport.xlsx", sheet="Parakou").read()
```

**Returns:** `pandas.DataFrame`

---

### `read_json(filepath, **kwargs)`

Reads a JSON file.

```python
df = kd.read_json("campagne_2023.json")
```

**Returns:** `pandas.DataFrame`

---

### `read_netcdf(filepath, **kwargs)`

Reads a NetCDF file (`.nc`, `.netcdf`). Requires optional dependencies `xarray` and `netCDF4`.

```python
df = kd.read_netcdf("chirps_2024.nc")
```

**Returns:** `xarray.Dataset` or `pandas.DataFrame` depending on options passed.

**Exception:** `ImportError` if `xarray` or `netCDF4` is not installed.

```bash
# Installing dependencies
pip install "kadipy[geospatial]"
```

---

### `read_api(url, params=None, **kwargs)`

Reads data from a REST API via a GET request.

```python
df = kd.read_api("https://api.data.bj/agriculture/prices")

# With query parameters
df = kd.read_api(
    "https://api.data.bj/agriculture/prices",
    params={"crop": "maize", "region": "parakou"},
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | required | REST API URL |
| `params` | `dict` | `None` | HTTP query parameters |

**Returns:** `pandas.DataFrame`

---

## Targeted Write Functions

These functions write a `pandas.DataFrame` to a file or API. They all return `True` if writing succeeds.

### `write_csv(data, filepath, **kwargs)`

```python
kd.write_csv(df, "export.csv")
```

Uses delimiter and encoding detected during reading if the source was read previously, or `,` / `utf-8` by default.

---

### `write_excel(data, filepath, **kwargs)`

```python
kd.write_excel(df, "export.xlsx")
```

---

### `write_json(data, filepath, **kwargs)`

```python
kd.write_json(df, "export.json")
```

---

### `write_netcdf(data, filepath, **kwargs)`

```python
kd.write_netcdf(df, "export.nc")
```

Same optional dependencies as `read_netcdf`.

---

### `write_api(data, url, **kwargs)`

Sends a DataFrame to a REST API endpoint.

```python
kd.write_api(df, "https://api.monservice.bj/upload")
```

---

## Generic Functions

These three functions accept any format and automatically detect the source to use based on file extension or URL prefix.

### Automatic Detection Table

| Extension or Prefix | Class Used |
|---------------------|------------|
| `.csv` | `CSVSource` |
| `.xlsx`, `.xls` | `ExcelSource` |
| `.json` | `JSONSource` |
| `.nc`, `.netcdf` | `NetCDFSource` |
| `http://`, `https://` | `APISource` |
| Other | `ValueError` |

---

### `write(data, filepath_or_url, **kwargs)`

Writes a DataFrame with automatic format detection.

```python
kd.write(df, "export.csv")
kd.write(df, "export.xlsx")
kd.write(df, "https://api.monservice.bj/upload")
```

---

### `info(filepath_or_url, **kwargs)`

Returns metadata of a source without loading all data into memory.

```python
meta = kd.info("recoltes_2024.csv")
print(meta)
# {
#   'path': 'recoltes_2024.csv',
#   'kind': 'csv',
#   'encoding': 'utf-8',
#   'sep': ',',
#   'decimal': '.',
#   'rows': 1240,
#   'cols': 8,
#   'size_kb': 42.5,
#   'last_read': None
# }
```

**Returns:** `dict` containing source metadata.

Returned keys vary depending on source type:

| Key | Description |
|-----|-------------|
| `path` | Source path or URL |
| `kind` | Source type: `'csv'`, `'excel'`, `'json'`, `'netcdf'`, `'api'` |
| `encoding` | Detected or configured encoding |
| `rows` | Number of data rows |
| `cols` | Number of columns |
| `size_kb` | File size in kilobytes (local files only) |
| `last_read` | ISO timestamp of last read, or `None` |

---

### `ping(filepath_or_url, **kwargs)`

Checks if a source is accessible without reading it.

```python
if kd.ping("recoltes_2024.csv"):
    df = kd.read_csv("recoltes_2024.csv")

# For an API
if kd.ping("https://api.data.bj/agriculture/prices"):
    df = kd.read_api("https://api.data.bj/agriculture/prices")
```

**Returns:** `True` if source is accessible, `False` otherwise.

For local files, checks that the file exists and is readable.
For APIs, checks that the endpoint responds without HTTP error.

---

## Accessing Source Classes

Classes `Source`, `CSVSource`, `ExcelSource`, `JSONSource`, `NetCDFSource`, and `APISource` are available directly from `kadi.io` for advanced usage.

```python
from kadi.io import CSVSource

source = CSVSource("recoltes.csv", sep=";", decimal=",")
df     = source.read(n=100)    # Read first 100 rows
meta   = source.info()         # Metadata
ok     = source.ping()         # Accessibility test
source.write(df, "copie.csv") # Rewriting
```

Source classes implement the abstract base class `Source`, which defines the shared contract: `read()`, `write()`, `info()`, `ping()`.

For complete documentation on each source class, see [kadi.kidas: Data Sources](kidas/sources.md).

---

## Root Level Access

All functions and classes from `kadi.io` are re-exported from `kadi` for direct access:

```python
import kadi as kd

# Equivalent to from kadi.io import ...
kd.read_csv(...)
kd.write(...)
kd.info(...)
kd.ping(...)
kd.CSVSource(...)
```

---

::: kadi.io
