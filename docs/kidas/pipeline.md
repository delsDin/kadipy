# Pipeline (`kadi.kidas.pipeline`)

`Pipeline` est le chef d'orchestre du module kidas. Il enchaîne
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
from kadi.kidas import Pipeline

pipeline = Pipeline()
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

**Paramètre :** `source` : chemin de fichier ou URL.

---

### `add_cleaning_step(step_name, **kwargs)`

Ajoute une étape de nettoyage à la file d'exécution.

```python
pipeline.add_cleaning_step("remove_duplicates")
pipeline.add_cleaning_step("handle_missing_values", strategy="median")
pipeline.add_cleaning_step("remove_outliers", method="zscore", threshold=3.0)
pipeline.add_cleaning_step("normalize_text", columns=["culture", "marche"])
```

---

### `add_validation_step(schema)`

Ajoute une étape de validation qui vérifie les types et contraintes des colonnes.

```python
pipeline.add_validation_step({
    "culture": "str",
    "rendement_kg": "float",
    "date_recolte": "date",
    "latitude": "float",
})
```

---

### `add_normalization_step(mapping)`

Ajoute une étape de normalisation qui standardise les noms de colonnes.

```python
pipeline.add_normalization_step({
    "crops": "culture",
    "markets": "ville",
    "gps": ["latitude", "longitude"],
})
```

---

### Raccourcis fluides (`load`, `clean`, `validate`, `normalize`)

Le pipeline propose également des méthodes raccourcies pour construire la chaîne plus rapidement :

```python
df, rapport = (
    Pipeline()
    .load("enquete.csv")
    .clean()
    .validate({"culture": "str"})
    .normalize({"crops": "culture"})
    .execute()
)
```

---

### `execute(cache)`

Exécute toutes les étapes enregistrées et retourne le résultat.

```python
df, rapport = pipeline.execute(cache=True)
```

---

## Exemple complet

```python
from kadi.kidas import Pipeline

pipeline = Pipeline()

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
    })
    .add_normalization_step({
        "crops": "culture",
        "gps": ["latitude", "longitude"],
    })
    .execute(cache=True)
)

print(f"Données prêtes : {len(df)} lignes, {len(df.columns)} colonnes")
```

---

::: kadi.kidas.pipeline.Pipeline

