# Cleaner (`kadi.kidas.cleaner`)

`Cleaner` is the tabular agricultural data cleaning class of KadiPy. It provides six cleaning methods tailored for Beninese agricultural files: duplicates, missing values, statistical outliers, heterogeneous dates, unnormalized text, and mixed decimal separators.

Each method updates the internal DataFrame and returns that DataFrame, enabling method chaining in a single expression.

---

## Initialization

```python
from kadi.kidas import Cleaner

cleaner = Cleaner(df)
```

`Cleaner` receives a `pandas.DataFrame` and creates an internal copy. The original DataFrame is never modified.

**Exception:** `CleanError` if the provided argument is not a DataFrame.

---

## Cleaning Methods

### `drop_dupes(subset=None, keep='first')`

Removes duplicate rows.

```python
df_clean = cleaner.drop_dupes()

# On a subset of columns
df_clean = cleaner.drop_dupes(subset=["culture", "marche", "date"])

# Keep last occurrence instead of first
df_clean = cleaner.drop_dupes(keep="last")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subset` | `list[str]` or `None` | `None` | Columns to consider for duplicate detection. `None` for all columns. |
| `keep` | `str` | `'first'` | `'first'`: first occurrence, `'last'`: last occurrence, `False`: drop all duplicates |

**Returns:** `pd.DataFrame`

---

### `fill_missing(strategy='mean', cols=None)`

Handles missing values (NaN) according to a selected strategy. Only numeric columns are affected by `'mean'` and `'median'`.

```python
# Median imputation on all numeric columns
df_clean = cleaner.fill_missing(strategy="median")

# Temporal propagation on specific columns
df_clean = cleaner.fill_missing(
    strategy="forward_fill",
    cols=["prix_xof_kg", "temperature"],
)

# Remove incomplete rows
df_clean = cleaner.fill_missing(strategy="drop")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | `str` | `'mean'` | Imputation strategy: `'mean'`, `'median'`, `'forward_fill'`, `'drop'` |
| `cols` | `list[str]` or `None` | `None` | Target columns. `None` for all columns. |

**Available Strategies:**

| Value | Behavior |
|-------|----------|
| `'mean'` | Replaces NaNs with the mean of each numeric column |
| `'median'` | Replaces NaNs with the median of each numeric column |
| `'forward_fill'` | Propagates the last known value forward (`ffill` + fallback `bfill`) |
| `'drop'` | Removes rows containing at least one NaN in target columns |

**Returns:** `pd.DataFrame`

**Exception:** `CleanError` if provided strategy is unknown.

---

### `drop_outliers(method='iqr', thresh=1.5, cols=None)`

Detects and removes statistical outliers on numeric columns. Returns a tuple: the cleaned DataFrame and the DataFrame of excluded rows.

```python
# IQR method (default)
df_clean, df_outliers = cleaner.drop_outliers()

# Z-score with custom threshold
df_clean, df_outliers = cleaner.drop_outliers(method="zscore", thresh=3.0)

# MAD on targeted columns
df_clean, df_outliers = cleaner.drop_outliers(
    method="mad",
    thresh=3.5,
    cols=["prix_xof_kg", "rendement_kg"],
)

# Inspect excluded rows
print(f"{len(df_outliers)} outlier(s) detected")
print(df_outliers)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | `str` | `'iqr'` | Detection method: `'iqr'`, `'zscore'`, `'mad'` |
| `thresh` | `float` | `1.5` | Detection threshold (1.5 for IQR, 3.0 recommended for Z-score) |
| `cols` | `list[str]` or `None` | `None` | Numeric columns to analyze. `None` for all numeric columns. |

**Available Methods:**

| Value | Algorithm |
|-------|-----------|
| `'iqr'` | Tukey's rule: excludes values outside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]` |
| `'zscore'` | Excludes values whose standardized Z-score exceeds `thresh` |
| `'mad'` | Median Absolute Deviation, robust to skewed distributions |

**Returns:** `tuple[pd.DataFrame, pd.DataFrame]`: (cleaned DataFrame, outliers DataFrame)

**Exception:** `CleanError` if provided method is unknown.

---

### `parse_dates(cols=None, infer=True)`

Normalizes date columns to `datetime64`. Uses `pd.to_datetime` with pandas `"mixed"` mode (compatible with heterogeneous formats). Unparsable values are converted to `NaT` without raising an error.

```python
# Auto-detection on all object type columns
df_clean = cleaner.parse_dates()

# On specific columns
df_clean = cleaner.parse_dates(cols=["date_recolte", "date_saisie"])
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cols` | `list[str]` or `None` | `None` | Columns to convert. `None`: all `object` columns. |
| `infer` | `bool` | `True` | Infers format automatically (currently always active). |

**Returns:** `pd.DataFrame`

---

### `norm_text(cols=None, case='lower')`

Standardizes text columns: leading and trailing whitespace trimming, accent normalization (ASCII), and case application.

```python
# Lowercase normalization on all text columns
df_clean = cleaner.norm_text()

# Uppercase on specific columns
df_clean = cleaner.norm_text(cols=["culture", "marche"], case="upper")

# Title case
df_clean = cleaner.norm_text(cols=["marche"], case="title")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cols` | `list[str]` or `None` | `None` | Text columns. `None`: all `object` columns. |
| `case` | `str` | `'lower'` | Case: `'lower'`, `'upper'`, `'title'` |

**Returns:** `pd.DataFrame`

---

### `strip_chars(cols=None, keep='')`

Removes special characters from text columns. Preserves only alphanumeric characters, spaces, and characters explicitly listed in `keep`.

```python
# Complete removal of special characters
df_clean = cleaner.strip_chars()

# Preserving hyphen (useful for plot codes like "PAR-001")
df_clean = cleaner.strip_chars(cols=["code_parcelle"], keep="-")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cols` | `list[str]` or `None` | `None` | Text columns. `None`: all `object` columns. |
| `keep` | `str` | `''` | Characters not to remove (e.g. `'-'`, `'_.'`) |

**Returns:** `pd.DataFrame`

---

### `check_decimals(cols=None)`

Detects co-existence of `.` and `,` decimal separators in text columns. Useful for diagnosing export files mixing French and English conventions. Does not modify the DataFrame.

```python
report = cleaner.check_decimals(cols=["prix_xof_kg", "rendement"])

# Example output
# {
#   "prix_xof_kg": {
#     "has_dot": True,
#     "has_comma": True,
#     "mixed": True,
#     "count_dot": 42,
#     "count_comma": 8
#   }
# }

for column, info in report.items():
    if info["mixed"]:
        print(f"Mixed separators detected in '{column}': {info['count_dot']} dots, {info['count_comma']} commas")
```

| Returned Key | Type | Description |
|--------------|------|-------------|
| `has_dot` | `bool` | Presence of `.` separator in the column |
| `has_comma` | `bool` | Presence of `,` separator in the column |
| `mixed` | `bool` | `True` if both co-exist |
| `count_dot` | `int` | Number of values with `.` as decimal |
| `count_comma` | `int` | Number of values with `,` as decimal |

**Returns:** `dict[str, dict]` (one entry per analyzed column). Does not modify `self.df`.

---

### `report()`

Returns the full report of cleaning operations performed since `Cleaner` initialization.

```python
cleaner = Cleaner(df)
cleaner.drop_dupes()
cleaner.fill_missing(strategy="median")
cleaner.drop_outliers(method="iqr")

report = cleaner.report()
# {
#   "lignes_initiales": 1500,
#   "lignes_finales": 1421,
#   "colonnes_initiales": 8,
#   "colonnes_finales": 8,
#   "doublons_supprimes": 23,
#   "nan_traites": 14,
#   "outliers_detectes": 42,
#   "dates_corrigees": 0,
#   "operations": [...]
# }
```

| Key | Type | Description |
|-----|------|-------------|
| `lignes_initiales` | `int` | Number of rows before any cleaning |
| `lignes_finales` | `int` | Number of rows after cleaning |
| `colonnes_initiales` | `int` | Number of columns at initialization |
| `colonnes_finales` | `int` | Number of columns after cleaning |
| `doublons_supprimes` | `int` | Total duplicates removed |
| `nan_traites` | `int` | Total missing values handled |
| `outliers_detectes` | `int` | Total outliers removed |
| `dates_corrigees` | `int` | Total date values converted |
| `operations` | `list` | Detailed history of each operation |

---

## Full Chained Example

```python
import kadi as kd
from kadi.kidas import Cleaner

df = kd.read_csv("enquete_prix_2024.csv")
cleaner = Cleaner(df)

# Method chaining for steps returning a DataFrame
cleaner.drop_dupes(subset=["culture", "marche", "date"])
cleaner.fill_missing(strategy="median", cols=["prix_xof_kg", "quantite_kg"])
cleaner.norm_text(cols=["culture", "marche"])
cleaner.parse_dates(cols=["date"])

# drop_outliers returns a tuple: explicit unpacking required
df_clean, df_outliers = cleaner.drop_outliers(method="iqr", cols=["prix_xof_kg"])

report = cleaner.report()
print(f"Rows: {report['lignes_initiales']} -> {report['lignes_finales']}")
print(f"Extracted outliers: {len(df_outliers)}")
```

> `drop_outliers` returns a `tuple` rather than just the DataFrame. It cannot be chained directly with other methods.

---

## Usage in a Pipeline

`Cleaner` is used internally by `Pipeline` when adding a cleaning step via `add_step` or `clean`.

```python
from kadi.kidas import Pipeline

df, report = (
    Pipeline()
    .add_source("recoltes.csv")
    .add_step("drop_dupes")
    .add_step("fill_missing", strategy="median")
    .add_step("drop_outliers", method="iqr")
    .add_step("norm_text")
    .run()
)
```

For pipeline documentation, see [Pipeline](pipeline.md).

---

## Backward Compatibility

Legacy method names emit a `DeprecationWarning` and continue to function until KadiPy v2.0:

| Legacy Name (before v1.2.0) | New Name |
|-----------------------------|----------|
| `remove_duplicates()` | `drop_dupes()` |
| `handle_missing_values()` | `fill_missing()` |
| `remove_outliers()` | `drop_outliers()` |
| `fix_dates()` | `parse_dates()` |
| `standardize_text()` | `norm_text()` |
| `remove_special_chars()` | `strip_chars()` |
| `detect_inconsistent_decimals()` | `check_decimals()` |
| `get_cleaning_report()` | `report()` |

Likewise, the class name `DataCleaner` is an alias of `Cleaner`.

---

::: kadi.kidas.cleaner.Cleaner
