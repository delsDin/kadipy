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
                        |
                    Pipeline             ← Chef d'orchestre
                        |
                        |
             ┌──────────┴──────────┐
             |                     |
             |                     |
         Cleaner               Validator
             |                     |
             |                     |
             └──────────┬──────────┘
                        |
                        |
                   Normalizer            ← Standardisation finale
                        |
                        |
                      Cache               ← Persistance SQLite
                        |
                        |
                DataFrame + Rapport
```

Chaque composant peut être utilisé seul ou enchaîné dans un pipeline.

---

## Démarrage rapide

### En une ligne avec `load_clean`

```python
import kadi.kidas as kidas

df, rapport = kidas.load_clean("recolte_2024.csv")
print(f"{len(df)} lignes chargées")
```

`load_clean` crée automatiquement un pipeline avec suppression des doublons
et imputation des valeurs manquantes par la moyenne.

### Avec `kadi.io` (lecture seule)

```python
import kadi as kd

df = kd.read_csv("recolte_2024.csv")
kd.info("recolte_2024.csv")
```

### Pipeline personnalisé

```python
from kadi.kidas import Pipeline

pipeline = Pipeline()

df, rapport = (
    pipeline
    .add_source("donnees_marche.xlsx")
    .add_step("drop_dupes")
    .add_step("fill_missing", strategy="median")
    .add_step("check_schema", {"culture": "str", "rendement_kg": "float"})
    .add_step("norm_cols", {"crops": "culture"})
    .run(cache=True)
)

print(rapport["steps_summary"])
print(f"Score qualité : {rapport.get('quality_score')}")
print(f"Lignes en sortie : {rapport['nb_rows_out']}")
```

### API fluide avec les alias courts

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .load("donnees_marche.xlsx")
    .clean("drop_dupes")
    .clean("fill_missing", strategy="median")
    .validate({"culture": "str", "rendement_kg": "float"})
    .normalize({"crops": "culture"})
    .run(cache=True)
)
```

---

## Formats de fichiers supportés

| Format | Extension | Classe source |
|--------|-----------|---------------|
| CSV | `.csv`, `.tsv`, `.txt` | `CSVSource` |
| Excel | `.xlsx`, `.xls`, `.xlsm` | `ExcelSource` |
| JSON | `.json` | `JSONSource` |
| NetCDF | `.nc`, `.nc4`, `.netcdf` | `NetCDFSource` |
| API REST | URL `http://` ou `https://` | `APISource` |

Le format est détecté automatiquement depuis l'extension ou le préfixe de l'URL.

---

## Rapport de pipeline

Chaque appel à `run()` retourne un rapport structuré :

```python
df, rapport = pipeline.add_source("recoltes.csv").add_step("check_schema", {"culture": "str"}).run()

# Nombre de lignes avant et après traitement
print(f"Avant : {rapport['nb_rows_in']} lignes")
print(f"Après : {rapport['nb_rows_out']} lignes")

# Liste des étapes appliquées
print(rapport["steps_summary"])

# Score de qualité (présent si une étape de validation a été exécutée)
if rapport.get("quality_score"):
    print(f"Score global : {rapport['quality_score']['overall']:.2f}")

# Avertissements de validation
for avertissement in rapport.get("warnings", []):
    print(avertissement)

# Données provenant du cache
print(f"Cache utilisé : {rapport['cache_utilise']}")
```

| Clé | Type | Description |
|-----|------|-------------|
| `nb_rows_in` | `int` | Nombre de lignes chargées depuis la source |
| `nb_rows_out` | `int` | Nombre de lignes après traitement |
| `steps_summary` | `list[str]` | Noms des étapes appliquées dans l'ordre |
| `quality_score` | `dict` ou `None` | Score qualité (généré par une étape de validation) |
| `warnings` | `list[str]` | Avertissements issus de la validation |
| `cache_utilise` | `bool` | `True` si les données ont été chargées depuis le cache |
| `details` | `dict` | Rapports internes détaillés de chaque étape |

---

## Sous-modules

- [Pipeline](pipeline.md) : Orchestration des étapes de traitement
- [Nettoyage (Cleaner)](cleaner.md) : Doublons, valeurs manquantes, outliers
- [Validation (Validator)](validator.md) : Règles de validation des données
- [Normalisation (Normalizer)](normalizer.md) : Standardisation des noms et unités
- [Sources de données](sources.md) : CSVSource, ExcelSource, JSONSource NetCDFSource, APISource
