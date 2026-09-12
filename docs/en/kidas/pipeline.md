# Pipeline (`kadi.kidas.pipeline`)

`Pipeline` is the central orchestrator of the kidas module. It chains cleaning, validation, and normalization steps declaratively, automatically detects source type from file path or URL, and manages result caching via SQLite.

Its API is fluid: each method returns the current instance, allowing method chaining without intermediate variables.

---

## Initialization

```python
from kadi.kidas import Pipeline

pipeline = Pipeline()
```

`Pipeline` is initialized without arguments. Source and steps are configured via chained methods.

---

## Configuration Methods

### `add_source(source, **kwargs)`

Configures the pipeline data source. Automatically detects source type from file extension or URL prefix.

```python
pipeline.add_source("recoltes_2024.csv")
pipeline.add_source("rapport.xlsx", sheet="Parakou")
pipeline.add_source("https://api.data.bj/agriculture/prices")
```

It is also possible to pass a `Source` instance directly:

```python
from kadi.io import CSVSource

source = CSVSource("recoltes.csv", sep=";", encoding="latin-1")
pipeline.add_source(source)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | `str` or `Source` | Path, URL, or `Source` instance |
| `**kwargs` | - | Arguments passed to the `Source` class constructor |

**Returns:** `Pipeline` (for chaining).

**Short alias:** `load(source, **kwargs)`

---

### `add_step(step_name, schema_or_mappings=None, **params)`

Adds a processing step to the pipeline queue. Step type (cleaning, validation, or normalization) is automatically determined based on the step name passed.

```python
pipeline.add_step("drop_dupes")
pipeline.add_step("fill_missing", strategy="median")
pipeline.add_step("check_schema", {"culture": "str", "rendement_kg": "float"})
pipeline.add_step("norm_cols", {"crops": "culture"})
```

#### Available Cleaning Steps

| Name | Description |
|------|-------------|
| `'drop_dupes'` | Removes duplicate rows |
| `'fill_missing'` | Imputes missing values (`strategy` parameter) |
| `'drop_outliers'` | Removes statistical outliers (`method`, `threshold` parameters) |
| `'parse_dates'` | Normalizes date columns to `datetime64` |
| `'norm_text'` | Normalizes text strings (accents, case, whitespace) |
| `'strip_chars'` | Removes unwanted special characters |

#### Available Validation Steps

| Name | Description |
|------|-------------|
| `'check_schema'` | Verifies column types against a schema dict |
| `'check_types'` | Validates data types column by column |
| `'check_ranges'` | Checks that numeric values fall within defined ranges |
| `'check_coords'` | Validates that GPS coordinates are within Benin bounds |
| `'check_unique'` | Checks uniqueness of values in specified columns |
| `'check_fk'` | Checks foreign key constraints between columns |

#### Available Normalization Steps

| Name | Description |
|------|-------------|
| `'norm_cols'` | Renames columns according to a mapping dictionary |
| `'convert_units'` | Converts units (kg/tonne, ha/m2, etc.) |
| `'convert_currency'` | Converts currencies via `ExchangeRateClient` |
| `'std_crops'` | Normalizes crop names to KadiPy reference |
| `'std_markets'` | Normalizes market names |
| `'std_coords'` | Normalizes GPS coordinates (format, rounding) |

**Short Aliases:**

- `clean(step, **params)`: alias for cleaning steps
- `validate(schema, **params)`: alias for `add_step('check_schema', schema)`
- `normalize(mappings, **params)`: alias for `add_step('norm_cols', mappings)`

---

## Execution

### `run(cache=True)`

Executes all configured steps in order. Loads data from source, applies each step, and caches the result if requested.

```python
df, report = pipeline.run(cache=True)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cache` | `bool` | `True` | Attempts cache loading before reading, and saves result after processing |

**Returns:** `tuple[pd.DataFrame, dict]`

**Exceptions:**

- `PipelineError`: if no source was configured.
- `ReadError`: if reading source fails.

#### Returned Report Structure

```python
df, report = pipeline.run()

report["nb_rows_in"]      # int   : raw rows loaded
report["nb_rows_out"]     # int   : rows after processing
report["steps_summary"]   # list  : step names in order
report["quality_score"]   # dict | None : quality score (if validation executed)
report["warnings"]        # list  : validation warnings
report["cache_utilise"]   # bool  : True if data originated from cache
report["details"]         # dict  : internal reports for each step
```

`quality_score` is a dict produced by `Validator`. It is `None` if no validation step was configured.

---

## Utility Methods

### `config()`

Returns full pipeline configuration: configured source and list of defined steps.

```python
cfg = pipeline.config()
print(f"Number of steps: {cfg['nb_steps']}")
for step in cfg["steps"]:
    print(f"  {step['type']}: {step['nom']} ({step['params']})")
```

**Returns:** `dict` with keys `source`, `nb_steps`, `steps`.

---

### `export(filepath)`

Exports internal pipeline report to a JSON or HTML file based on destination file extension.

```python
pipeline.export("rapport_pipeline.json")
pipeline.export("rapport_pipeline.html")
```

| Extension | Format |
|-----------|--------|
| `.json` | Indented JSON, UTF-8 encoded |
| `.html` | Simple HTML page with pre-formatted JSON |

**Returns:** `True` if export succeeds.

**Exception:** `PipelineError` if file extension is unsupported.

---

## Full Examples

### Minimal Pipeline

```python
from kadi.kidas import Pipeline

df, report = (
    Pipeline()
    .add_source("recoltes_2024.csv")
    .add_step("drop_dupes")
    .add_step("fill_missing", strategy="median")
    .run()
)
print(f"{report['nb_rows_in']} -> {report['nb_rows_out']} rows")
```

### Pipeline with Validation and Normalization

```python
from kadi.kidas import Pipeline

df, report = (
    Pipeline()
    .add_source("enquete_prix_2024.xlsx")
    .add_step("drop_dupes")
    .add_step("fill_missing", strategy="median")
    .add_step("drop_outliers", method="iqr")
    .add_step("check_schema", {
        "culture":      "str",
        "marche":       "str",
        "prix_xof_kg":  "float",
        "date":         "datetime",
    })
    .add_step("std_crops", col="culture")
    .add_step("norm_cols", {"prix_xof_kg": "price_xof"})
    .run(cache=True)
)

if report.get("quality_score"):
    print(f"Quality score: {report['quality_score']['overall']:.2f}")

for warning in report.get("warnings", []):
    print(warning)
```

### Fluid API with Short Aliases

```python
from kadi.kidas import Pipeline

df, report = (
    Pipeline()
    .load("prix_2024.csv")
    .clean("drop_dupes")
    .clean("fill_missing", strategy="median")
    .validate({"culture": "str", "prix_xof_kg": "float"})
    .normalize({"crops": "culture"})
    .run(cache=True)
)
```

### Reusing an Existing Source

```python
from kadi.io import CSVSource
from kadi.kidas import Pipeline

source = CSVSource("export_maep.csv", sep=";", encoding="latin-1")

df, report = (
    Pipeline()
    .add_source(source)
    .add_step("drop_dupes")
    .add_step("parse_dates", cols=["date_recolte"])
    .run()
)
```

### Report Export

```python
pipeline = Pipeline()
df, report = (
    pipeline
    .add_source("donnees.csv")
    .add_step("check_schema", {"culture": "str"})
    .run()
)

pipeline.export("rapport.json")
```

---

## Cache Behavior

The pipeline uses an internal SQLite cache (managed by `Cache`). The cache key is calculated via SHA-256 hash of the source path, truncated to 16 hexadecimal characters.

When `cache=True`:

1. Pipeline checks for an existing entry in cache.
2. If it exists, data is returned directly without re-reading the source or re-executing steps.
3. If it does not exist, pipeline executes all steps and saves the result.

The report indicates whether data originated from cache via the `cache_utilise` key.

To force complete re-execution without using cache:

```python
df, report = pipeline.run(cache=False)
```

---

## Backward Compatibility

Legacy method names emit a `DeprecationWarning` and continue to function until KadiPy v2.0:

| Legacy Name (before v1.2.0) | New Name |
|-----------------------------|----------|
| `load_data(source)` | `add_source(source)` or `load(source)` |
| `add_cleaning_step(step)` | `add_step(step)` or `clean(step)` |
| `add_validation_step(schema)` | `add_step('check_schema', schema)` or `validate(schema)` |
| `add_normalization_step(mappings)` | `add_step('norm_cols', mappings)` or `normalize(mappings)` |
| `execute(cache)` | `run(cache)` |
| `get_pipeline_config()` | `config()` |
| `export_report(filepath)` | `export(filepath)` |

---

::: kadi.kidas.pipeline.Pipeline
