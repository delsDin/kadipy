# kadi.kidas : Traitement et standardisation des données

Le module `kadi.kidas` est le pipeline de traitement des données agricoles de
KadiPy. Il prend en charge l'ingestion, le nettoyage, la validation et la
normalisation des données depuis n'importe quelle source.

**kidas** = *KadiPy Data Ingestion, Alignment and Standardization*

---

## Architecture

```
Source (CSV / Excel / JSON / NetCDF / API)
           |
        Pipeline        ← Chef d'orchestre
           |
    ┌──────┴──────┐
    |             |
 Cleaner      Validator
    |             |
    └──────┬──────┘
           |
      Normalizer        ← Standardisation finale
           |
        Cache           ← Persistance SQLite
           |
    DataFrame + Rapport
```

Chaque composant peut être utilisé indépendamment ou enchaîné dans un pipeline.

---

## Démarrage rapide

### En une ligne avec kadi.io

```python
import kadi as kd

# Lecture directe avec détection automatique du format
df = kd.read_csv("recolte_2024.csv")
kd.info(df)
```

### Pipeline personnalisé

```python
from kadi.kidas import Pipeline

pipeline = Pipeline()

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
| CSV | `.csv` | `CSVSource` |
| Excel | `.xlsx`, `.xls` | `ExcelSource` |
| JSON | `.json` | `JSONSource` |
| NetCDF | `.nc`, `.nc4` | `NetCDFSource` |
| API REST | URL HTTP/HTTPS | `APISource` |

Le format est détecté automatiquement depuis l'extension ou le préfixe de l'URL.

---

## Rapport de pipeline

Chaque exécution de pipeline retourne un rapport structuré :

```python
# L'ajout d'une étape de validation est nécessaire pour générer un quality_score
df, rapport = (
    pipeline.load_data("recoltes.csv")
    .add_validation_step({"culture": "str"})
    .execute()
)

print(rapport.keys())

# Score de qualité (généré par l'étape de validation)
if rapport.get("quality_score"):
    print(f"Score : {rapport['quality_score']}")

# Nombre de lignes finales
print(f"Lignes en sortie : {rapport['nb_rows_out']}")
```

---

## Sous-modules

- [Pipeline](pipeline.md) : Orchestration des étapes de traitement
- [Nettoyage (Cleaner)](cleaner.md) : Doublons, valeurs manquantes, outliers
- [Validation (Validator)](validator.md) : Règles de validation des données
- [Normalisation (Normalizer)](normalizer.md) : Standardisation des noms et unités

---

## Accès direct aux sources (kadi.io)

```python
import kadi as kd

# Lecture directe d'un CSV sans pipeline
df = kd.read_csv("recoltes_2024.csv")

# API REST
df_api = kd.read_api("https://api.data.bj/agriculture/prices")
```

