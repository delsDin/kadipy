# Validator (`kadi.kidas.validator`)

`Validator` is the data quality validation class for tabular agricultural data in KadiPy. It gathers six targeted checks: schema, pandas data types, numeric ranges, GPS coordinates, uniqueness, and referential integrity. It also calculates an overall data quality score across three dimensions: completeness, consistency, and accuracy.

Each validation method returns a tuple `(bool, result)`, allowing you to inspect results or halt processing immediately if an anomaly is detected. All performed checks are recorded in an internal report accessible via `report()`.

---

## Initialization

```python
from kadi.kidas import Validator

validator = Validator(df)
```

`Validator` receives a `pandas.DataFrame`. The DataFrame is not copied: it is held by reference and is never mutated by validation methods.

**Exception:** `ValidationError` if the provided argument is not a DataFrame.

---

## Validation Methods

### `check_schema(schema)`

Verifies that the DataFrame contains the columns specified in the schema and that their data types match expectations.

```python
is_valid, errors = validator.check_schema({
    "culture":       "str",
    "rendement_kg":  "float",
    "date_recolte":  "datetime",
})

if not is_valid:
    for msg in errors:
        print(msg)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `schema` | `dict[str, str]` | Dictionary mapping `column_name` -> `expected_type` |

**Accepted Types:**

| Value | Interpretation |
|-------|----------------|
| `'str'` or `'string'` | Text column (`object` dtype) |
| `'int'` or `'integer'` | Integer column |
| `'float'` | Floating point column |
| `'datetime'` | `datetime64` column |
| `'bool'` | Boolean column |

**Returns:** `tuple[bool, list[str]]`

- `True` if the schema is valid, `False` otherwise.
- List of error messages (empty if valid).

---

## `check_types(dtypes)`

Verifies compliance of actual pandas data types for each column, using flexible type comparison (for example: `int64` and `int32` are both accepted for `'int'`).

```python
is_valid, df_errors = validator.check_types({
    "culture":      "object",
    "rendement_kg": "float64",
    "date_recolte": "datetime64[ns]",
})

if not is_valid:
    print(df_errors)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `dtypes` | `dict[str, str]` | Dictionary mapping `column_name` -> expected pandas dtype |

**Returns:** `tuple[bool, pd.DataFrame]`

- `True` if all types match.
- DataFrame of non-conforming columns (empty if OK), containing columns `colonne`, `dtype_attendu`, and `dtype_reel`.

---

## `check_ranges(bounds)`

Verifies that numeric values in specified columns fall within defined intervals. `NaN` values are ignored.

```python
is_valid, df_out_of_bounds = validator.check_ranges({
    "temperature":   (-10, 50),
    "rendement_kg":  (0, 50000),
    "prix_xof_kg":   (0, 5000),
})

if not is_valid:
    print(f"{len(df_out_of_bounds)} row(s) out of bounds.")
    print(df_out_of_bounds)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `bounds` | `dict[str, tuple]` | Dictionary mapping `column_name` -> `(min, max)` |

Bounds are inclusive. A column missing from the DataFrame logs a warning and is skipped without raising an error.

**Returns:** `tuple[bool, pd.DataFrame]`

- `True` if all values satisfy the bounds.
- DataFrame of out-of-bounds rows, including all columns (empty if OK).

---

## `check_coords(lat, lon, region='benin')`

Verifies that GPS coordinates lie within the bounding box of the specified region. Also detects accidental lat/lon inversions.

```python
is_valid, df_invalid = validator.check_coords(
    lat="latitude",
    lon="longitude",
)

# With the default region ('benin'):
# latitude  in [2.5,  12.5]
# longitude in [-1.5,  4.0]

if not is_valid:
    print(f"{len(df_invalid)} invalid coordinate(s).")
```

When `region` is set to something other than `'benin'`, worldwide bounding box defaults `[-90, 90]` for latitude and `[-180, 180]` for longitude are applied.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat` | `str` | - | Name of the latitude column |
| `lon` | `str` | - | Name of the longitude column |
| `region` | `str` | `'benin'` | Reference region for the bounding box |

**Returns:** `tuple[bool, pd.DataFrame]`

- `True` if all coordinates fall within the bounding box.
- DataFrame of rows with coordinates outside the bounding box (empty if OK).

**Exception:** `ValidationError` if either `lat` or `lon` column is missing from the DataFrame.

---

## `check_unique(cols)`

Verifies that the combination of specified columns is unique across all rows (equivalent to a composite primary key).

```python
is_valid, df_duplicates = validator.check_unique(
    cols=["culture", "marche", "date_recolte"]
)

if not is_valid:
    print(f"{len(df_duplicates)} duplicate row(s).")
    print(df_duplicates)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `cols` | `list[str]` | List of columns whose combined values must be unique |

**Returns:** `tuple[bool, pd.DataFrame]`

- `True` if the column combination is unique.
- DataFrame of all rows involved in duplicate combinations (empty if OK).

---

## `check_fk(fk_col, ref)`

Verifies referential integrity of a column: every non-null value must exist within the provided reference set.

```python
valid_markets = {"Cotonou", "Porto-Novo", "Parakou", "Bohicon"}

is_valid, df_missing = validator.check_fk(
    fk_col="marche",
    ref=valid_markets,
)

if not is_valid:
    print(f"{len(df_missing)} unknown reference(s).")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `fk_col` | `str` | Name of the column holding foreign key values |
| `ref` | `set` | Set of expected valid reference values |

**Returns:** `tuple[bool, pd.DataFrame]`

- `True` if all values are present in the reference set.
- DataFrame of rows with values missing from the reference set (empty if OK).

**Exception:** `ValidationError` if column `fk_col` is missing.

---

## `quality_score()`

Calculates an overall quality score and scores per dimension for the DataFrame.

```python
score = validator.quality_score()

print(score["overall"])       # ex: 0.8742
print(score["completeness"])  # non-null cell ratio
print(score["consistency"])   # 1 - duplicate ratio
print(score["accuracy"])      # 1.0 (extensible)
print(score["columns"])       # completeness score per column
```

The overall score is a weighted average:

| Dimension | Weight | Calculation |
|-----------|--------|-------------|
| Completeness | 40% | Proportion of non-null cells |
| Consistency | 35% | `1 - (nb_duplicates / total_rows)` |
| Accuracy | 25% | `1.0` by default (extensible) |

**Returns:** `dict` with keys:

| Key | Type | Description |
|-----|------|-------------|
| `overall` | `float` | Overall score in range [0.0, 1.0] |
| `completeness` | `float` | Completeness score |
| `consistency` | `float` | Consistency score |
| `accuracy` | `float` | Accuracy score |
| `columns` | `dict[str, float]` | Completeness score per column |

---

## `report()`

Returns the complete validation report accumulated since the initialization of `Validator`.

```python
validator.check_schema({"culture": "str", "rendement_kg": "float"})
validator.check_ranges({"rendement_kg": (0, 50000)})
validator.quality_score()

report = validator.report()
# {
#   "lignes": 1500,
#   "colonnes": 8,
#   "validations": [
#     {"type": "schema",  "valide": True,  "nb_erreurs": 0, "erreurs": []},
#     {"type": "ranges",  "valide": False, "hors_borne": 3},
#   ],
#   "quality_score": {
#     "overall": 0.9245,
#     ...
#   }
# }
```

| Key | Type | Description |
|-----|------|-------------|
| `lignes` | `int` | Number of DataFrame rows at initialization |
| `colonnes` | `int` | Number of DataFrame columns at initialization |
| `validations` | `list` | Log of each performed validation |
| `quality_score` | `dict` | Present only if `quality_score()` was invoked |

**Returns:** `dict` (copy of internal report).

---

## Complete Example

```python
import kadi as kd
from kadi.kidas import Validator

df = kd.read_csv("enquete_prix_2024.csv")
validator = Validator(df)

schema = {
    "culture":      "str",
    "marche":       "str",
    "date_recolte": "datetime",
    "rendement_kg": "float",
    "prix_xof_kg":  "float",
    "latitude":     "float",
    "longitude":    "float",
}

is_valid, errors = validator.check_schema(schema)
if not is_valid:
    for msg in errors:
        print(msg)

is_valid, df_out_of_bounds = validator.check_ranges({
    "rendement_kg": (0, 50000),
    "prix_xof_kg":  (0, 5000),
})

is_valid, df_coords = validator.check_coords(lat="latitude", lon="longitude")

score = validator.quality_score()
print(f"Quality score: {score['overall']:.2%}")

report = validator.report()
```

---

## Usage in a Pipeline

`Validator` is used internally by `Pipeline` when adding a validation step via `add_step` or `validate`.

```python
from kadi.kidas import Pipeline

df, report = (
    Pipeline()
    .add_source("enquete_prix_2024.csv")
    .add_step("check_schema", schema={"culture": "str", "rendement_kg": "float"})
    .add_step("check_ranges", bounds={"rendement_kg": (0, 50000)})
    .run()
)
```

For pipeline documentation, see [Pipeline](pipeline.md).

---

## Backward Compatibility

Legacy method names emit a `DeprecationWarning` and continue to function until KadiPy v2.0:

| Legacy Name (before v1.2.0) | New Name |
|-----------------------------|----------|
| `validate_schema()` | `check_schema()` |
| `validate_types()` | `check_types()` |
| `validate_ranges()` | `check_ranges()` |
| `validate_coordinates()` | `check_coords()` |
| `validate_uniqueness()` | `check_unique()` |
| `validate_referential_integrity()` | `check_fk()` |
| `compute_quality_score()` | `quality_score()` |
| `get_validation_report()` | `report()` |

Similarly, class name `DataValidator` is an alias for `Validator`.

---

::: kadi.kidas.validator.Validator
