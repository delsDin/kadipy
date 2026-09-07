# Nettoyage (`kadi.kidas.cleaner`)

`Cleaner` nettoie les données agricoles brutes : doublons, valeurs
manquantes, valeurs aberrantes, problèmes d'encodage et normalisation des
textes.

---

## Initialisation

```python
from kadi.kidas import Cleaner
import pandas as pd

df_brut = pd.read_csv("recoltes_2024.csv")
cleaner = Cleaner(df_brut)
```

---

## Méthodes

### `drop_dupes()`

Supprime les lignes identiques sur toutes les colonnes.

```python
df_propre = cleaner.drop_dupes()
```

---

### `fill_missing(strategy, columns)`

Impute ou supprime les valeurs manquantes selon la stratégie choisie.

```python
# Remplacement par la médiane (valeurs numériques)
df = cleaner.fill_missing(strategy="median")

# Remplacement par la moyenne
df = cleaner.fill_missing(strategy="mean")

# Suppression des lignes incomplètes
df = cleaner.fill_missing(strategy="drop")

# Appliquer uniquement sur des colonnes spécifiques
df = cleaner.fill_missing(
    strategy="median",
    columns=["rendement_kg", "superficie_ha"],
)
```

**Stratégies disponibles :**

| Stratégie | Description | Recommandée pour |
|-----------|-------------|-----------------|
| `'mean'` | Remplace par la moyenne de la colonne | Distributions normales |
| `'median'` | Remplace par la médiane | Distributions asymétriques |
| `'mode'` | Remplace par la valeur la plus fréquente | Variables catégorielles |
| `'drop'` | Supprime les lignes incomplètes | Données très lacunaires |
| `'ffill'` | Reporte la valeur précédente | Séries temporelles |
| `'bfill'` | Reporte la valeur suivante | Séries temporelles |

---

### `drop_outliers(method, threshold, columns)`

Identifie et supprime les valeurs aberrantes.

```python
# Méthode Z-Score (défaut : seuil 3.0)
df = cleaner.drop_outliers(method="zscore", threshold=3.0)

# Méthode IQR (plus robuste)
df = cleaner.drop_outliers(method="iqr")

# Sur une colonne spécifique
df = cleaner.drop_outliers(
    method="zscore",
    threshold=2.5,
    columns=["prix_xof_kg"],
)
```

**Méthodes disponibles :**

| Méthode | Critère de suppression | Usage |
|---------|----------------------|-------|
| `'zscore'` | `|z| > threshold` (défaut : 3.0) | Distributions normales |
| `'iqr'` | En dehors de [Q1 - 1.5×IQR, Q3 + 1.5×IQR] | Distributions asymétriques |
| `'mad'` | Écart à la médiane > threshold × MAD | Outliers extrêmes |

---

### `normalize_text(columns)`

Standardise les chaînes de caractères : suppression des accents, conversion
en minuscules, suppression des espaces superflus.

```python
# Normalise toutes les colonnes textuelles automatiquement
df = cleaner.normalize_text()

# Normalise uniquement les colonnes spécifiées
df = cleaner.normalize_text(columns=["culture", "commune", "region"])
```

---

### `fix_encoding()`

Corrige les problèmes d'encodage fréquents dans les fichiers béninois (UTF-8,
Latin-1, Windows-1252 mélangés).

```python
df = cleaner.fix_encoding()
```

---

### `parse_dates(columns)`

Normalise les colonnes de dates hétérogènes vers le type `datetime64`.

```python
df = cleaner.parse_dates(columns=["date_recolte"])
```

---

## Exemple complet

```python
import pandas as pd
from kadi.kidas import Cleaner

df = pd.read_csv("enquete_prix_2024.csv", encoding="latin-1")
cleaner = Cleaner(df)

df_propre = (
    cleaner
    .fix_encoding()
    .drop_dupes()
    .fill_missing(strategy="median", columns=["prix_xof_kg", "quantite_kg"])
    .drop_outliers(method="iqr", columns=["prix_xof_kg"])
    .normalize_text(columns=["culture", "marche"])
)

print(f"Avant : {len(df)} lignes")
print(f"Après : {len(df_propre)} lignes")
```

---

::: kadi.kidas.cleaner.Cleaner

