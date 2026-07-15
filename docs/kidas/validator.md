# Validation (`kadi.kidas.validator`)

`DataValidator` vérifie la cohérence et la qualité des données agricoles
selon un schéma défini. Il produit un rapport d'anomalies sans modifier
les données.

---

## Principe

La validation est non-destructive : elle ne supprime ni ne modifie les
données. Elle signale les problèmes dans un rapport structuré et retourne
un score de qualité global.

```python
from kadi.kidas import DataValidator

validator = DataValidator(df)
rapport = validator.validate(schema={
    "culture": "str",
    "rendement_kg_ha": "float",
    "latitude": "float",
})
```

---

## Méthodes

### `validate(schema)`

Valide les colonnes du DataFrame selon le schéma fourni.

```python
rapport = validator.validate(schema={
    "culture": "str",           # Type de la colonne
    "rendement_kg": "float",    # Valeur numérique obligatoire
    "date_recolte": "date",     # Format date
    "superficie_ha": "float",
    "is_organic": "bool",
})
```

**Types supportés :**

| Type | Vérification effectuée |
|------|----------------------|
| `'str'` | Colonne non numérique, valeurs non nulles |
| `'int'` | Entiers, pas de valeurs non entières |
| `'float'` | Nombres réels, détection de `-inf`/`inf` |
| `'bool'` | Seulement `True` / `False` |
| `'date'` | Format ISO 8601 ou datetime pandas |

---

### `check_ranges(rules)`

Vérifie que les valeurs numériques se trouvent dans des plages acceptables.

```python
rapport = validator.check_ranges({
    "rendement_kg_ha": (0, 20_000),   # Entre 0 et 20 t/ha
    "superficie_ha": (0.01, 5_000),   # Entre 10 m² et 5000 ha
    "prix_xof_kg": (10, 10_000),      # Entre 10 et 10 000 XOF/kg
    "latitude": (6.0, 12.5),          # Bornes Bénin
    "longitude": (0.5, 3.9),          # Bornes Bénin
})
```

---

### `check_referential(column, allowed_values)`

Vérifie que les valeurs d'une colonne appartiennent à un référentiel défini.

```python
cultures_valides = [
    "maize", "rice", "sorghum", "millet", "cowpea",
    "soybean", "yam", "cassava", "tomato", "onion",
]
rapport = validator.check_referential("culture", allowed_values=cultures_valides)

# Valider les communes béninoises
communes_benin = ["Cotonou", "Parakou", "Abomey", "Natitingou", ...]
rapport = validator.check_referential("commune", allowed_values=communes_benin)
```

---

## Rapport de validation

```python
rapport = validator.validate(schema={...})

# Score de qualité (0 à 1)
print(f"Score global : {rapport['quality_score']['overall']:.2f}")

# Résumé par colonne
for col, details in rapport["columns"].items():
    if details["errors"] > 0:
        print(f"  {col} : {details['errors']} erreurs — {details['error_type']}")

# Liste complète des avertissements
for avertissement in rapport["warnings"]:
    print(f"  Attention : {avertissement}")

# Lignes problématiques (index dans le DataFrame)
print(f"Lignes avec erreurs : {rapport['invalid_row_indices']}")
```

**Structure du rapport :**

| Clé | Type | Description |
|-----|------|-------------|
| `quality_score` | `dict` | Scores par dimension et score global |
| `columns` | `dict` | Rapport par colonne (nb erreurs, type d'erreur) |
| `warnings` | `list[str]` | Liste des avertissements |
| `invalid_row_indices` | `list[int]` | Index des lignes problématiques |
| `nb_rows_validated` | `int` | Nombre de lignes validées |

---

## Exemple complet

```python
import pandas as pd
from kadi.kidas import DataValidator

df = pd.read_csv("recoltes_enquete.csv")

validator = DataValidator(df)

# Étape 1 : validation des types
rapport_types = validator.validate(schema={
    "culture": "str",
    "rendement_kg": "float",
    "date_recolte": "date",
    "commune": "str",
})

# Étape 2 : validation des plages de valeurs
rapport_ranges = validator.check_ranges({
    "rendement_kg": (0, 50_000),
    "superficie_m2": (100, 50_000_000),
})

# Étape 3 : validation référentielle
rapport_ref = validator.check_referential("culture", [
    "maize", "rice", "sorghum", "millet", "cowpea", "yam",
])

print(f"Types OK    : {rapport_types['quality_score']['overall']:.2f}")
print(f"Plages OK   : {rapport_ranges['quality_score']['overall']:.2f}")
print(f"Référentiel : {rapport_ref['quality_score']['overall']:.2f}")
```

---

::: kadi.kidas.validator.DataValidator
