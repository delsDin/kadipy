# Data Sources (`kadi.kidas.sources`)

The `kadi.kidas.sources` subpackage gathers all classes for reading and writing agricultural data from various formats. Each concrete class inherits from `Source`, the abstract base class, and implements the same contract: `read()`, `write()`, `info()`, `ping()`.

| Class | Format | Extensions / Prefix |
|-------|--------|---------------------|
| `CSVSource` | Delimited text files | `.csv` |
| `ExcelSource` | Excel workbooks | `.xlsx`, `.xls` |
| `JSONSource` | JSON files or Python dicts | `.json` |
| `NetCDFSource` | Gridded agrometeorological data | `.nc`, `.netcdf` |
| `APISource` | HTTP REST APIs | `http://`, `https://` |

---

## Import

```python
from kadi.kidas import CSVSource, ExcelSource, JSONSource, NetCDFSource, APISource

# or directly from the subpackage
from kadi.kidas.sources import CSVSource
```

The classes are also re-exported from `kadi.io`. See [Input and Output](../io.md) for documentation on `read_*`, `write_*`, and `write` functions.

---

## `Source` (Abstract Base Class)

`Source` is the shared interface for all data sources. It cannot be instantiated directly.

**Common Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Local file path or resource URI |
| `kind` | `str` | Source type: `'csv'`, `'excel'`, `'json'`, `'netcdf'`, `'api'` |
| `encoding` | `str` | Data encoding (can be `'auto'`) |
| `last_read` | `datetime` or `None` | Timestamp of the last successful read |

**Abstract Methods Implemented by Each Subclass:**

- `read(**kwargs)`: reads data and returns a `pd.DataFrame`
- `write(data, **kwargs)`: writes a DataFrame to the source, returns `bool`
- `info()`: returns a metadata `dict`
- `ping()`: returns `True` if the source is accessible

---

## `CSVSource`

Source for agricultural CSV files with automatic detection of encoding (via chardet), delimiter, and decimal separator. Designed for exports from IoT sensors, cooperatives, and national databases (INSAE, MAEP).

### Initialization

```python
from kadi.kidas import CSVSource

# Automatic detection of everything
source = CSVSource("recoltes_2024.csv")

# Explicit parameters
source = CSVSource(
    "export_insae.csv",
    encoding="latin-1",
    sep=";",
    decimal=",",
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Path to the CSV file |
| `encoding` | `str` | `'auto'` | Encoding. `'auto'`: detected via chardet |
| `sep` | `str` | `'auto'` | Column delimiter. `'auto'`: auto-detected |
| `decimal` | `str` | `'auto'` | Decimal separator. `'auto'`: inferred from delimiter |

In `'auto'` mode, encoding is detected from a 10,000-byte sample. Delimiter is detected by `csv.Sniffer` with fallback frequency counting among `,`, `;`, `\t`, `|`. If delimiter is `;`, the inferred decimal separator is `,` (French convention).

### `read(n=None, skip=None)`

```python
df = source.read()

# First 100 rows
df = source.read(n=100)

# Skip 2 metadata rows at file start
df = source.read(skip=2)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n` | `int` or `None` | `None` | Maximum number of rows to read |
| `skip` | `int` or `None` | `None` | Rows to skip at file start (excluding header) |

Tries multiple fallback encodings (`utf-8`, `latin-1`, `cp1252`) if primary reading fails.

**Returns:** `pd.DataFrame`
**Exceptions:** `ConnectError` if file is inaccessible, `ReadError` if all encodings fail.

### `write(data, index=False)`

```python
source.write(df)
source.write(df, index=True)
```

Writes in UTF-8 if encoding is `'auto'`. Uses detected delimiter or `,` by default.

**Returns:** `bool`
**Exception:** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'path': 'recoltes_2024.csv',
#   'kind': 'csv',
#   'encoding': 'utf-8',
#   'sep': ',',
#   'decimal': 'inferred',
#   'rows': 1500,
#   'cols': 8,
#   'size_kb': 42.31,
#   'last_read': '2024-09-01T10:23:45.123456'
# }
```

### `ping()`

Checks if file exists and is readable. Returns `bool`.

---

## `ExcelSource`

Source for Excel files (`.xlsx`, `.xls`) with automatic header row detection and merged cell resolution via forward fill. Adapted for Beninese agricultural reports with municipalities and markets merged across multiple rows.

### Initialization

```python
from kadi.kidas import ExcelSource

source = ExcelSource("prix_marches_2024.xlsx")

# Explicit sheet and header
source = ExcelSource("rapport.xlsx", sheet="Janvier", header=2)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Path to the Excel file |
| `sheet` | `str` or `int` | `0` | Default sheet (name or index) |
| `header` | `str` or `int` | `'auto'` | Header row. `'auto'`: automatically detected |

Header detection inspects the first 15 rows and selects the densest row (highest count of non-null values).

### `sheets()`

Returns the list of sheet names in the workbook.

```python
sheets = source.sheets()
# ['Janvier', 'Fevrier', 'Mars']
```

**Returns:** `list[str]`
**Exceptions:** `ConnectError`, `ReadError`

### `sheet_info(sheet)`

Returns metadata for a specific sheet.

```python
meta = source.sheet_info("Janvier")
# {
#   'sheet': 'Janvier',
#   'rows': 245,
#   'cols': 6,
#   'columns': ['culture', 'marche', 'prix_xof_kg', ...]
# }
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `sheet` | `str` or `int` | Sheet name or index to inspect |

**Returns:** `dict`
**Exception:** `ReadError`

### `read(sheet=None)`

```python
df = source.read()

# Read a specific sheet
df = source.read(sheet="Fevrier")
```

Applies a vertical forward fill on all columns to resolve merged cells, then drops completely empty rows.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sheet` | `str`, `int`, or `None` | `None` | Sheet to read. `None`: uses sheet defined at initialization |

**Returns:** `pd.DataFrame`
**Exceptions:** `ConnectError`, `ReadError`

### `write(data, sheet='Sheet1')`

```python
source.write(df, sheet="Export")
```

**Returns:** `bool`
**Exception:** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'path': 'prix_marches_2024.xlsx',
#   'kind': 'excel',
#   'sheets': ['Janvier', 'Fevrier'],
#   'active_sheet': 0,
#   'detected_header': 1,
#   'size_kb': 118.7,
#   'last_read': None
# }
```

### `ping()`

Checks if file exists and is readable. Returns `bool`.

---

## `JSONSource`

Source for flat or nested JSON files, such as returned by agricultural APIs (FAO, WFP VAM, MAEP). Also supports an in-memory Python dictionary directly.

### Initialization

```python
from kadi.kidas import JSONSource

# From a file
source = JSONSource("donnees_fao.json")

# From an in-memory Python dictionary
data = {"location": {"lat": 9.3, "lon": 2.4}, "crop": "maize"}
source = JSONSource(data)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path_or_dict` | `str` or `dict` | Path to JSON file or Python dictionary |

When the source is a dictionary, `path` equals `'<dict_in_memory>'` and `ping()` always returns `True`.

### `flatten(obj, sep='.')`

Recursively flattens a nested JSON object using dot notation.

```python
obj = {"location": {"lat": 9.3, "lon": 2.4}, "crop": "maize"}
flat = source.flatten(obj)
# {"location.lat": 9.3, "location.lon": 2.4, "crop": "maize"}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `obj` | `dict` | required | JSON object to flatten |
| `sep` | `str` | `'.'` | Separator between key levels |

Lists are indexed by position (`location.items.0`, `location.items.1`...).

**Returns:** `dict`

### `read(flatten=True)`

```python
df = source.read()

# Without flattening (direct pd.json_normalize)
df = source.read(flatten=False)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `flatten` | `bool` | `True` | If `True`, flattens each record before conversion |

Accepts JSON responses of type `dict` (single record) or `list` (list of records).

**Returns:** `pd.DataFrame`
**Exceptions:** `ConnectError`, `ReadError`

### `write(data, orient='records')`

```python
source.write(df)
source.write(df, orient="index")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `pd.DataFrame` | required | Data to write |
| `orient` | `str` | `'records'` | JSON orientation: `'records'`, `'index'`, `'columns'`, `'values'` |

Writes with `force_ascii=False` and `indent=2`.

**Exception:** `WriteError` if source is an in-memory dictionary (no destination file).

**Returns:** `bool`

### `info()`

```python
print(source.info())
# {
#   'path': 'donnees_fao.json',
#   'kind': 'json',
#   'is_file': True,
#   'size_kb': 8.45,
#   'last_read': None
# }
```

### `ping()`

For file source: checks existence and readability.
For dict source: always returns `True`. Returns `bool`.

---

## `NetCDFSource`

Source for agrometeorological NetCDF files (`.nc`), used for CHIRPS (precipitation), TAMSAT (Africa), and GFS (global forecasts) data. Uses xarray as reading engine and supports Dask chunking for large files.

> Dependency: `xarray` and `netCDF4` must be installed.

### Initialization

```python
from kadi.kidas import NetCDFSource

source = NetCDFSource("chirps_benin_2024.nc")

# With Dask for large files (> 500 MB)
source = NetCDFSource("gfs_global_2024.nc", use_dask=True)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Path to the NetCDF file |
| `use_dask` | `bool` | `False` | Enables lazy loading via Dask |

### `dims()`

Returns dataset dimensions.

```python
dimensions = source.dims()
# {'lat': 240, 'lon': 360, 'time': 365}
```

**Returns:** `dict[str, int]`

### `read(lat_bounds=None, lon_bounds=None, time_bounds=None)`

Extracts a spatial and temporal subset of the file. If no bounding box is specified, defaults to the Benin bbox (`lat in [2.5, 12.5]`, `lon in [-1.5, 4.0]`).

```python
# Extraction with default Benin bbox
da = source.read()

# Extraction on a custom region
da = source.read(
    lat_bounds=(6.0, 12.5),
    lon_bounds=(1.0, 4.0),
    time_bounds=("2024-01-01", "2024-06-30"),
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat_bounds` | `tuple[float, float]` or `None` | Benin bbox | Latitude interval `(lat_min, lat_max)` |
| `lon_bounds` | `tuple[float, float]` or `None` | Benin bbox | Longitude interval `(lon_min, lon_max)` |
| `time_bounds` | `tuple[str, str]` or `None` | `None` | Time interval in ISO format `('YYYY-MM-DD', 'YYYY-MM-DD')` |

Automatically detects lat/lon dimension names in the dataset (compatible with `'lat'`, `'latitude'`, `'y'`, etc.). Reads the first data variable if dataset contains multiple variables.

**Returns:** `xr.DataArray`
**Exceptions:** `ConnectError`, `ReadError`

### `to_df()`

Converts the last `DataArray` extracted by `read()` to a `pd.DataFrame`. If `read()` has not been called yet, performs a read with the Benin bbox.

```python
da = source.read()
df = source.to_df()
# Columns: lat, lon, time, <variable_name>
```

**Returns:** `pd.DataFrame`
**Exception:** `ReadError`

### `write(data)`

Converts the DataFrame to `xr.Dataset` via `from_dataframe()` and saves it in NetCDF format.

**Returns:** `bool`
**Exception:** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'path': 'chirps_benin_2024.nc',
#   'kind': 'netcdf',
#   'dimensions': {'lat': 240, 'lon': 360, 'time': 365},
#   'variables': ['precip'],
#   'use_dask': False,
#   'size_kb': 45230.0,
#   'last_read': None
# }
```

### `ping()`

Checks if file exists and is readable. Returns `bool`.

---

## `APISource`

Source for agricultural and climate REST APIs (Open-Meteo, WFP VAM, FAO, SoilGrids). Features rate limiting and retry mechanism with exponential backoff.

### Initialization

```python
from kadi.kidas import APISource

# Public API
source = APISource("https://api.open-meteo.com/v1/forecast")

# Authenticated API with custom rate limit
source = APISource(
    "https://api.wfp.org/vam-data-bridges/1.0",
    token="my_bearer_token",
    rate_limit=2.0,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | required | Base URL of the API endpoint |
| `token` | `str` or `None` | `None` | Bearer token for authenticated APIs |
| `rate_limit` | `float` | `5.0` | Maximum number of requests per second |

### `fetch(params, retries=3, backoff=5.0)`

Performs a GET request with retries and exponential backoff.

```python
data = source.fetch(
    params={"latitude": 6.36, "longitude": 2.42},
    retries=3,
    backoff=5.0,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `params` | `dict` | required | GET request query parameters |
| `retries` | `int` | `3` | Maximum number of attempts on failure |
| `backoff` | `float` | `5.0` | Base delay in seconds between retries (doubled each attempt, capped at 60 s) |

Retryable HTTP status codes are: `429`, `500`, `502`, `503`, `504`.

**Returns:** `dict` (parsed JSON response)
**Exceptions:** `ConnectError` if API is unreachable, `ReadError` if response is not valid JSON.

### `read(params=None)`

Performs a GET request and normalizes the response to a DataFrame.

```python
df = source.read({
    "latitude": 6.36,
    "longitude": 2.42,
    "daily": "temperature_2m_max",
})
```

Automatically searches for a standard key in dict response (`'data'`, `'results'`, `'items'`, `'records'`, `'features'`). If none is found, uses the whole dict as a single record.

**Returns:** `pd.DataFrame`
**Exceptions:** `ConnectError`, `ReadError`

### `write(data)`

Sends the DataFrame to the API via a POST request in JSON format (`orient='records'`).

**Returns:** `bool`
**Exception:** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'url': 'https://api.open-meteo.com/v1/forecast',
#   'kind': 'api',
#   'requires_auth': False,
#   'rate_limit': 5.0,
#   'last_read': None
# }
```

### `ping()`

Performs a lightweight HEAD request. Returns `True` if HTTP status code is below 500 (API responds, even with 4xx error). Returns `False` if connection fails completely.

---

## Full Example

```python
import kadi as kd
from kadi.kidas import CSVSource, ExcelSource, JSONSource, NetCDFSource, APISource

# CSV with automatic detection
source_csv = CSVSource("recoltes_2024.csv")
if source_csv.ping():
    df = source_csv.read()
    print(source_csv.info())

# Multi-sheet Excel
source_excel = ExcelSource("prix_marches.xlsx")
for sheet in source_excel.sheets():
    df = source_excel.read(sheet=sheet)
    print(f"{sheet}: {len(df)} rows")

# Nested JSON
source_json = JSONSource("donnees_fao.json")
df = source_json.read(flatten=True)

# Agrometeorological NetCDF
source_nc = NetCDFSource("chirps_benin_2024.nc")
da = source_nc.read(lat_bounds=(2.5, 12.5), lon_bounds=(-1.5, 4.0))
df = source_nc.to_df()

# REST API
source_api = APISource("https://api.open-meteo.com/v1/forecast")
df = source_api.read({
    "latitude": 6.36,
    "longitude": 2.42,
    "daily": "temperature_2m_max",
})
```

---

## Backward Compatibility

Legacy class names emit a `DeprecationWarning` and continue to function until KadiPy v2.0:

| Legacy Name (before v1.2.0) | New Name |
|-----------------------------|----------|
| `DataSource` | `Source` |
| `CSVDataSource` | `CSVSource` |
| `ExcelDataSource` | `ExcelSource` |
| `JSONDataSource` | `JSONSource` |
| `NetCDFDataSource` | `NetCDFSource` |
| `APIDataSource` | `APISource` |

---

::: kadi.kidas.sources.base.Source
::: kadi.kidas.sources.csv_source.CSVSource
::: kadi.kidas.sources.excel_source.ExcelSource
::: kadi.kidas.sources.json_source.JSONSource
::: kadi.kidas.sources.netcdf_source.NetCDFSource
::: kadi.kidas.sources.api_source.APISource
