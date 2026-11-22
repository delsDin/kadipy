# Kidas

`kadi.kidas` charge, nettoie, valide et normalise des données tabulaires.
Installez KadiPy avec `pip install kadipy`.

## Sources de données

`Source` définit les méthodes communes `read()`, `write(data)`, `ping()`
et `info()`. Utilisez `ping()` pour vérifier l’accessibilité de la source et
`info()` pour consulter ses métadonnées.

```python
from kadi.kidas import APISource, CSVSource, ExcelSource, JSONSource, NetCDFSource

csv = CSVSource(path="donnees/recoltes.csv", sep=",", encoding="utf-8")
excel = ExcelSource(path="donnees/prix.xlsx", sheet="Parakou")
json = JSONSource("donnees/stations.json")
netcdf = NetCDFSource("donnees/chirps.nc")
api = APISource("https://api.open-meteo.com/v1/forecast")

if csv.ping():
    print(csv.info())
    df = csv.read()
```

`NetCDFSource.read()` renvoie un `xarray.DataArray`. Utilisez
`NetCDFSource.to_df()` pour obtenir un DataFrame. Le support NetCDF
nécessite `xarray` et un moteur compatible.

## Nettoyage, validation et normalisation

```python
from kadi.kidas import Cleaner, Normalizer, Validator

cleaner = Cleaner(df)
cleaner.drop_dupes()
clean = cleaner.fill_missing(strategy="median", cols=["rendement_kg"])

normalizer = Normalizer(clean)
normalizer.norm_cols()
normalized = normalizer.std_crops(col="culture")

validator = Validator(normalized)
valid, errors = validator.check_schema({"culture": "str", "rendement_kg": "float"})
score = validator.quality_score()
```

Appelez les méthodes de transformation successives sur l’instance de
`Cleaner` ou de `Normalizer`. Elles mettent à jour son DataFrame et
renvoient le résultat de l’étape.

## Pipeline et cache

```python
from kadi.kidas import Cache, Pipeline, load_clean

df_clean, report = load_clean("donnees/recoltes.csv", cache=False)

pipeline = (
    Pipeline()
    .load("donnees/recoltes.csv")
    .add_step("drop_dupes")
    .add_step("norm_cols")
    .add_step("std_crops", col="culture")
)
df_final, report = pipeline.run(cache=False)
print(report["steps_summary"])
pipeline.export("rapport.json")

cache = Cache()
cache.set("recoltes_nettoyees", df_final)
df_cached, metadata = cache.get("recoltes_nettoyees")
```

## Exceptions

Les exceptions publiques héritent de `KadiError`. Les plus courantes sont
`ConnectError` (connexion), `ReadError` (lecture), `WriteError` (écriture),
`CleanError` (nettoyage), `ValidationError` (validation), `CacheError`
(cache) et `PipelineError` (configuration ou exécution du pipeline).

## Rétrocompatibilité

Les imports explicites des alias historiques, tels que `CSVDataSource`,
`DataPipeline` et `load_and_clean`, restent disponibles avec un
`DeprecationWarning`. Les nouveaux exemples utilisent `CSVSource`,
`Pipeline` et `load_clean`.

## Notebooks de référence

| Notebook | Composant |
|---|---|
| [`00_index.ipynb`](../../examples/kidas/00_index.ipynb) | Vue d'ensemble du module kidas |
| [`01_csv_source.ipynb`](../../examples/kidas/01_csv_source.ipynb) | `CSVSource` |
| [`02_excel_source.ipynb`](../../examples/kidas/02_excel_source.ipynb) | `ExcelSource` |
| [`03_json_source.ipynb`](../../examples/kidas/03_json_source.ipynb) | `JSONSource` |
| [`04_netcdf_source.ipynb`](../../examples/kidas/04_netcdf_source.ipynb) | `NetCDFSource` |
| [`05_api_source.ipynb`](../../examples/kidas/05_api_source.ipynb) | `APISource` |
| [`06_data_cleaner.ipynb`](../../examples/kidas/06_data_cleaner.ipynb) | `Cleaner` |
| [`07_data_validator.ipynb`](../../examples/kidas/07_data_validator.ipynb) | `Validator` |
| [`08_data_normalizer.ipynb`](../../examples/kidas/08_data_normalizer.ipynb) | `Normalizer` |
| [`09_data_cache.ipynb`](../../examples/kidas/09_data_cache.ipynb) | `Cache` |
| [`10_data_pipeline.ipynb`](../../examples/kidas/10_data_pipeline.ipynb) | `Pipeline` |

Pour exécuter un notebook, activez l'environnement virtuel et lancez Jupyter :

```bash
source .kadi_venv/bin/activate
jupyter notebook examples/kidas/
```
