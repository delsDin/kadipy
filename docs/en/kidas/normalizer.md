# Normalizer (`kadi.kidas.normalizer`)

`Normalizer` is the agricultural data normalization class of KadiPy, tailored for the Beninese context. It gathers six transformations: column name normalization to snake_case, unit conversion to kilograms, currency conversion, crop name standardization to FAO codes, market geocoding, and creation of Shapely GPS geometries.

Each method updates the internal DataFrame and returns it, allowing method chaining in a single expression. The history of applied transformations is accessible via `mappings()`.

---

## Initialization

```python
from kadi.kidas import Normalizer

normalizer = Normalizer(df)
```

`Normalizer` receives a `pandas.DataFrame` and creates an internal copy. The original DataFrame is never modified.

**Exception:** `CleanError` if the provided argument is not a DataFrame.

---

## Normalization Methods

### `norm_cols(style='snake_case')`

Normalizes DataFrame column names to snake_case: accent removal, replacing spaces, hyphens, and parentheses with underscores, converting to lowercase.

```python
# Before: ['Culture', 'Rendement (kg)', 'Température Min (°C)', 'Date Récolte']
df_norm = normalizer.norm_cols()
# After: ['culture', 'rendement_kg', 'temperature_min_c', 'date_recolte']
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `style` | `str` | `'snake_case'` | Target style. Only `'snake_case'` is currently supported. |

A style other than `'snake_case'` emits a log warning and the operation is still applied in snake_case.

**Returns:** `pd.DataFrame`

---

### `convert_units(unit_map)`

Converts numeric values of specified columns to kilograms, applying conversion factors from the internal reference table.

```python
df_norm = normalizer.convert_units({
    "production":  "tonne",
    "recolte":     "sac_100kg",
    "stock_local": "tiya",
})
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `unit_map` | `dict[str, str]` | Dictionary `column_name` -> `source_unit` |

**Supported Units:**

| Unit | Factor to kg |
|------|--------------|
| `'kg'`, `'kilogramme'` | 1.0 |
| `'tonne'`, `'tonnes'`, `'t'` | 1000.0 |
| `'sac_100kg'`, `'sac'` | 100.0 |
| `'sac_80kg'` | 80.0 |
| `'sac_50kg'` | 50.0 |
| `'tiya'` | 1.5 |
| `'quintal'` | 100.0 |
| `'boisseau'` | 27.2 |
| `'livre'` | 0.4536 |
| `'g'`, `'gramme'` | 0.001 |

The standard `'sac'` corresponds to the 100 kg bag used in Benin. The `'tiya'` is a local measure of approximately 1.5 kg depending on the crop. A column missing from the DataFrame emits a log warning and is ignored without raising an error.

**Returns:** `pd.DataFrame`

**Exception:** `CleanError` if a source unit is unknown.

---

### `convert_currency(col, from_='XOF', to='XOF', date=None)`

Converts monetary values of a column using a fixed exchange rate.

```python
# Conversion from USD to XOF
df_norm = normalizer.convert_currency(
    col="prix_usd",
    from_="USD",
    to="XOF",
)

# Conversion from EUR to XOF
df_norm = normalizer.convert_currency(
    col="valeur_export",
    from_="EUR",
    to="XOF",
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `col` | `str` | required | Name of the column to convert |
| `from_` | `str` | `'XOF'` | Source currency |
| `to` | `str` | `'XOF'` | Target currency |
| `date` | `str` or `None` | `None` | Reference date in `'YYYY-MM-DD'` format (unused in current version) |

**Available Exchange Rates (fixed, to XOF):**

| Currency | Rate to XOF |
|----------|-------------|
| `'XOF'` | 1.0 |
| `'EUR'` | 655.957 (WAEMU fixed rate) |
| `'USD'` | 600.0 |
| `'GBP'` | 750.0 |

If one of the currencies is not in this table, a warning is emitted and no conversion is applied.

> The current version uses fixed rates. Integration with a real-time exchange rate API is planned for phase 2 of the module.

**Returns:** `pd.DataFrame`

---

### `std_crops(col, std='fao')`

Normalizes crop names in a column to official FAO codes, handling local Beninese variants with or without accents.

```python
# Before: ['maïs', 'Niébé', 'MANIOC', 'yam', 'mais']
df_norm = normalizer.std_crops(col="culture")
# After: ['maize', 'cowpea', 'cassava', 'yam', 'maize']
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `col` | `str` | required | Name of the column containing crop names |
| `std` | `str` | `'fao'` | Target standard (`'fao'` uses official FAO codes) |

**Available Mappings:**

| Accepted Local Names | FAO Code |
|----------------------|----------|
| `'maïs'`, `'mais'`, `'maiz'`, `'corn'`, `'maize'` | `'maize'` |
| `'niébé'`, `'niebe'`, `'cowpea'`, `'haricot'` | `'cowpea'` |
| `'igname'`, `'yam'` | `'yam'` |
| `'sorgho'`, `'sorghum'` | `'sorghum'` |
| `'riz'`, `'rice'` | `'rice'` |
| `'manioc'`, `'cassava'` | `'cassava'` |
| `'arachide'`, `'groundnut'`, `'peanut'` | `'groundnut'` |
| `'mil'`, `'millet'` | `'millet'` |
| `'fonio'` | `'fonio'` |
| `'soja'`, `'soybean'` | `'soybean'` |
| `'tomate'`, `'tomato'` | `'tomato'` |
| `'oignon'`, `'onion'` | `'onion'` |
| `'piment'`, `'pepper'` | `'pepper'` |

Unrecognized names are kept in lowercase without accents. A missing column emits a warning and is ignored.

**Returns:** `pd.DataFrame`

---

### `std_markets(col, region='benin')`

Normalizes market names in a column and adds two columns `market_lat` and `market_lon` with official GPS coordinates.

```python
# Before: ['Dantokpa', 'PARAKOU', 'Bohicon']
df_norm = normalizer.std_markets(col="marche")
# After: 'marche' column unchanged, + 'market_lat' and 'market_lon' columns
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `col` | `str` | required | Name of the column containing market names |
| `region` | `str` | `'benin'` | Reference region for market dictionary |

**Referenced Markets (Benin):**

| Market | Latitude | Longitude | City |
|--------|----------|-----------|------|
| `dantokpa`, `cotonou` | 6.366 | 2.437 | Cotonou |
| `parakou` | 9.337 | 2.629 | Parakou |
| `bohicon` | 7.181 | 2.067 | Bohicon |
| `kandi` | 11.133 | 2.940 | Kandi |
| `natitingou` | 10.303 | 1.381 | Natitingou |
| `malanville` | 11.867 | 3.383 | Malanville |
| `abomey` | 7.183 | 1.983 | Abomey |
| `porto-novo` | 6.497 | 2.627 | Porto-Novo |
| `lokossa` | 6.617 | 1.717 | Lokossa |

Matching is partial: `'Marché de Parakou'` will be matched to `'parakou'`. Unrecognized markets receive `None` for lat and lon. A missing column emits a warning and is ignored.

**Returns:** `pd.DataFrame` with added `market_lat` and `market_lon` columns.

---

### `std_coords(lat=None, lon=None)`

Creates a `geometry` column containing `shapely.geometry.Point` objects from latitude and longitude columns.

```python
df_norm = normalizer.std_coords(lat="latitude", lon="longitude")
# 'geometry' column added: Point(lon, lat) for each row
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat` | `str` or `None` | `None` | Latitude column name |
| `lon` | `str` or `None` | `None` | Longitude column name |

If `lat` or `lon` is `None` or refers to a missing column in the DataFrame, a log warning is emitted and the DataFrame is returned unchanged.

Rows with `NaN` latitude or longitude receive `None` in the `geometry` column.

If the `shapely` package is not installed, a warning is emitted and the DataFrame is returned unchanged.

> Optional dependency: `shapely >= 2.0`. Install it with `pip install shapely>=2.0`.

**Returns:** `pd.DataFrame` with added `geometry` column.

---

### `mappings()`

Returns the full history of applied normalizations since `Normalizer` initialization.

```python
normalizer.norm_cols()
normalizer.std_crops(col="culture")
normalizer.convert_units({"production": "tonne"})

hist = normalizer.mappings()
# {
#   "colonnes": {"Rendement (kg)": "rendement_kg", ...},
#   "unites":   {"production": {"unite_source": "tonne", "facteur_kg": 1000.0, "unite_cible": "kg"}},
#   "cultures": {"maïs": "maize", "Niébé": "cowpea"},
#   "marches":  {},
#   "devises":  {},
# }
```

| Key | Type | Content |
|-----|------|---------|
| `colonnes` | `dict` | `old_name` -> `new_name` for each renamed column |
| `unites` | `dict` | `column` -> `{unite_source, facteur_kg, unite_cible}` |
| `cultures` | `dict` | `local_name` -> `fao_code` for each match found |
| `marches` | `dict` | Empty in current version |
| `devises` | `dict` | `column` -> `{from, to, taux}` |

**Returns:** `dict` (copy of internal history).

---

## Full Chained Example

```python
import kadi as kd
from kadi.kidas import Normalizer

df = kd.read_csv("recoltes_2024.csv")
normalizer = Normalizer(df)

df_norm = (
    normalizer
    .norm_cols()
    .std_crops(col="culture")
    .convert_units({"rendement_kg": "sac_100kg", "production": "tonne"})
    .std_markets(col="marche")
    .std_coords(lat="latitude", lon="longitude")
)

hist = normalizer.mappings()
print(f"Renamed columns: {len(hist['colonnes'])}")
print(f"Normalized crops: {len(hist['cultures'])}")
print(f"Converted units: {len(hist['unites'])}")
```

---

## Usage in a Pipeline

`Normalizer` is used internally by `Pipeline` when adding a normalization step via `add_step` or `normalize`.

```python
from kadi.kidas import Pipeline

df, report = (
    Pipeline()
    .add_source("recoltes_2024.csv")
    .add_step("norm_cols")
    .add_step("std_crops", col="culture")
    .add_step("convert_units", unit_map={"rendement_kg": "sac_100kg"})
    .run()
)
```

For pipeline documentation, see [Pipeline](pipeline.md).

---

## Backward Compatibility

Legacy method names emit a `DeprecationWarning` and continue to function until KadiPy v2.0:

| Legacy Name (before v1.2.0) | New Name |
|-----------------------------|----------|
| `normalize_column_names()` | `norm_cols()` |
| `normalize_units()` | `convert_units()` |
| `normalize_currencies()` | `convert_currency()` |
| `normalize_crop_names()` | `std_crops()` |
| `normalize_market_names()` | `std_markets()` |
| `normalize_geometry()` | `std_coords()` |
| `get_normalization_mapping()` | `mappings()` |

Likewise, the class name `DataNormalizer` is an alias of `Normalizer`.

---

::: kadi.kidas.normalizer.Normalizer
