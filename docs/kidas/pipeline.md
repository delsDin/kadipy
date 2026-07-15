# Pipeline (`kadi.kidas.pipeline`)

`DataPipeline` est le chef d'orchestre du module kidas. Il enchaîne
les étapes de chargement, nettoyage, validation et normalisation dans un
flux de traitement configurable et reproductible.

---

## Principe

Le pipeline suit un pattern de construction en chaîne (*fluent interface*) :
chaque méthode retourne l'objet pipeline lui-même, ce qui permet d'enchaîner
les appels de manière lisible.

```
load_data()
    → add_cleaning_step()
    → add_validation_step()
    → add_normalization_step()
    → execute()
    → (DataFrame, rapport)
```

---

## Initialisation

```python
from kadi.kidas import DataPipeline

pipeline = DataPipeline()
```

---

## Méthodes

### `load_data(source)`

Charge les données depuis une source. Le format est détecté automatiquement.

```python
pipeline.load_data("recoltes_2024.csv")         # CSV
pipeline.load_data("marches_prix.xlsx")         # Excel
pipeline.load_data("capteurs_meteo.json")        # JSON
pipeline.load_data("donnees_sol.nc")             # NetCDF
pipeline.load_data("https://api.data.bj/...")   # API REST
```

**Paramètre :** `source` — chemin de fichier ou URL.

---

### `add_cleaning_step(step_name, **kwargs)`

Ajoute une étape de nettoyage à la file d'exécution.

```python
pipeline.add_cleaning_step("remove_duplicates")
pipeline.add_cleaning_step("handle_missing_values", strategy="median")
pipeline.add_cleaning_step("remove_outliers", method="zscore", threshold=3.0)
pipeline.add_cleaning_step("normalize_text", columns=["culture", "marche"])
```

**Étapes disponibles :**

| Nom | Paramètres | Description |
|-----|-----------|-------------|
| `remove_duplicates` | — | Supprime les lignes dupliquées |
| `handle_missing_values` | `strategy`: `'mean'`, `'median'`, `'drop'` | Impute ou supprime les valeurs manquantes |
| `remove_outliers` | `method`: `'zscore'`/`'iqr'`, `threshold` | Supprime les valeurs aberrantes |
| `normalize_text` | `columns`: liste | Nettoie accents, majuscules, espaces |
| `fix_encoding` | — | Corrige les problèmes d'encodage |

---

### `add_validation_step(schema)`

Ajoute une étape de validation qui vérifie les types et contraintes des colonnes.

```python
pipeline.add_validation_step({
    "culture": "str",         # Doit être une chaîne
    "rendement_kg": "float",  # Doit être un nombre
    "date_recolte": "date",   # Doit être une date
    "latitude": "float",      # Doit être un flottant
})
```

**Types supportés :** `'str'`, `'int'`, `'float'`, `'bool'`, `'date'`.

La validation ne bloque pas l'exécution. Les erreurs sont collectées dans le
rapport de pipeline sous la clé `warnings`.

---

### `add_normalization_step(mapping)`

Ajoute une étape de normalisation qui standardise les noms de colonnes.

```python
pipeline.add_normalization_step({
    "crops": "culture",        # Normalise la colonne "culture" vers les codes KadiPy
    "markets": "ville",        # Normalise les noms de marchés
    "gps": ["latitude", "longitude"],  # Valide et normalise les coordonnées GPS
})
```

---

### `execute(cache)`

Exécute toutes les étapes enregistrées et retourne le résultat.

```python
df, rapport = pipeline.execute(cache=True)
```

**Paramètre :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `cache` | `bool` | `True` | Si True, met en cache le résultat dans SQLite |

**Retour :** `tuple[pd.DataFrame, dict]`

---

## Rapport de pipeline

```python
df, rapport = pipeline.execute()

# Nombre de lignes en entrée et en sortie
print(f"Lignes en entrée : {rapport['nb_rows_in']}")
print(f"Lignes en sortie : {rapport['nb_rows_out']}")
print(f"Lignes supprimées: {rapport['nb_rows_in'] - rapport['nb_rows_out']}")

# Score de qualité global (0 à 1)
qualite = rapport["quality_score"]
print(f"Score global     : {qualite['overall']:.2f}")
print(f"Score complétude : {qualite.get('completeness', 'N/A')}")
print(f"Score cohérence  : {qualite.get('consistency', 'N/A')}")

# Résumé de chaque étape
for etape in rapport["steps_summary"]:
    print(f"  [{etape['step']}] {etape['status']} — {etape.get('detail', '')}")

# Avertissements de validation
for avertissement in rapport["warnings"]:
    print(f"  Attention : {avertissement}")
```

---

## Exemple complet avec toutes les étapes

```python
from kadi.kidas import DataPipeline

pipeline = DataPipeline()

df, rapport = (
    pipeline
    .load_data("enquete_agriculteurs_2024.csv")
    .add_cleaning_step("fix_encoding")
    .add_cleaning_step("remove_duplicates")
    .add_cleaning_step("normalize_text", columns=["culture", "commune"])
    .add_cleaning_step("handle_missing_values", strategy="median")
    .add_cleaning_step("remove_outliers", method="iqr")
    .add_validation_step({
        "culture": "str",
        "rendement_kg_ha": "float",
        "superficie_ha": "float",
        "commune": "str",
        "latitude": "float",
        "longitude": "float",
    })
    .add_normalization_step({
        "crops": "culture",
        "gps": ["latitude", "longitude"],
    })
    .execute(cache=True)
)

print(f"Données prêtes : {len(df)} lignes, {len(df.columns)} colonnes")
print(f"Score qualité  : {rapport['quality_score']['overall']:.2f} / 1.0")
```

---

::: kadi.kidas.pipeline.DataPipeline
