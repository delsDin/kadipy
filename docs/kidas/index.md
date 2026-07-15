# kadi.kidas — Traitement et standardisation des données

Le module `kadi.kidas` est le pipeline de traitement des données agricoles de
KadiPy. Il prend en charge l'ingestion, le nettoyage, la validation et la
normalisation des données depuis n'importe quelle source.

**kidas** = *KadiPy Data Ingestion, Alignment and Standardization*

---

## Architecture

```
Source (CSV / Excel / JSON / NetCDF / API)
           |
      DataPipeline       ← Chef d'orchestre
           |
    ┌──────┴──────┐
    |             |
DataCleaner  DataValidator
    |             |
    └──────┬──────┘
           |
    DataNormalizer        ← Standardisation finale
           |
      DataCache           ← Persistance SQLite
           |
    DataFrame + Rapport
```

Chaque composant peut être utilisé indépendamment ou enchaîné dans un pipeline.

---

## Démarrage rapide

### En une ligne

```python
import kadi.kidas as kidas

# Chargement, nettoyage automatique et cache
df, rapport = kidas.load_and_clean("recolte_2024.csv")

print(f"Lignes chargées : {len(df)}")
print(f"Score qualité   : {rapport['quality_score']['overall']:.2f}")
```

### Pipeline personnalisé

```python
from kadi.kidas import DataPipeline

pipeline = DataPipeline()

df, rapport = (
    pipeline
    .load_data("donnees_marche.xlsx")
    .add_cleaning_step("remove_duplicates")
    .add_cleaning_step("handle_missing_values", strategy="median")
    .add_validation_step({
        "culture": "str",
        "rendement_kg": "float",
        "latitude": "float",
    })
    .add_normalization_step({"crops": "culture"})
    .execute(cache=True)
)

print(rapport["steps_summary"])
```

---

## Formats de fichiers supportés

| Format | Extension | Classe source |
|--------|-----------|---------------|
| CSV | `.csv` | `CSVDataSource` |
| Excel | `.xlsx`, `.xls` | `ExcelDataSource` |
| JSON | `.json` | `JSONDataSource` |
| NetCDF | `.nc`, `.nc4` | `NetCDFDataSource` |
| API REST | URL HTTP/HTTPS | `APIDataSource` |

Le format est détecté automatiquement depuis l'extension ou le préfixe de l'URL.

---

## Rapport de pipeline

Chaque exécution de pipeline retourne un rapport structuré :

```python
df, rapport = pipeline.load_data("recoltes.csv").execute()

print(rapport.keys())
# dict_keys(['steps_summary', 'quality_score', 'warnings', 'nb_rows_in', 'nb_rows_out'])

# Score de qualité global (0 à 1)
print(f"Score : {rapport['quality_score']['overall']:.2f}")

# Avertissements de validation
for warning in rapport["warnings"]:
    print(f"  ! {warning}")
```

---

## Sous-modules

- [Pipeline](pipeline.md) — Orchestration des étapes de traitement
- [Nettoyage (DataCleaner)](cleaner.md) — Doublons, valeurs manquantes, outliers
- [Validation (DataValidator)](validator.md) — Règles de validation des données
- [Normalisation (DataNormalizer)](normalizer.md) — Standardisation des noms et unités

---

## Accès direct aux sources

```python
from kadi.kidas import CSVDataSource, ExcelDataSource, APIDataSource

# Lecture directe d'un CSV sans pipeline
source = CSVDataSource("recoltes_2024.csv")
df = source.read()

# API REST
source_api = APIDataSource("https://api.data.bj/agriculture/prices")
df_api = source_api.read()
```
