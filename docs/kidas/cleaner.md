# Nettoyage (`kadi.kidas.cleaner`)

`DataCleaner` nettoie les données agricoles brutes : doublons, valeurs
manquantes, valeurs aberrantes, problèmes d'encodage et normalisation des
textes.

---

## Initialisation

```python
from kadi.kidas import DataCleaner
import pandas as pd

df_brut = pd.read_csv("recoltes_2024.csv")
cleaner = DataCleaner(df_brut)
```

---

## Méthodes

### `remove_duplicates()`

Supprime les lignes identiques sur toutes les colonnes. Signale le nombre
de doublons trouvés dans le rapport.

```python
df_propre = cleaner.remove_duplicates()
```

---

### `handle_missing_values(strategy, columns)`

Impute ou supprime les valeurs manquantes selon la stratégie choisie.

```python
# Remplacement par la médiane (valeurs numériques)
df = cleaner.handle_missing_values(strategy="median")

# Remplacement par la moyenne
df = cleaner.handle_missing_values(strategy="mean")

# Suppression des lignes incomplètes
df = cleaner.handle_missing_values(strategy="drop")

# Appliquer uniquement sur des colonnes spécifiques
df = cleaner.handle_missing_values(
    strategy="median",
    columns=["rendement_kg", "superficie_ha"],
)
```

**Stratégies disponibles :**

| Stratégie | Description | Recommandée pour |
|-----------|-------------|-----------------|
| `'mean'` | Remplace par la moyenne de la colonne | Distributions normales |
| `'median'` | Remplace par la médiane | Distributions asymétriques (prix) |
| `'mode'` | Remplace par la valeur la plus fréquente | Variables catégorielles |
| `'drop'` | Supprime les lignes incomplètes | Quand les données manquantes sont nombreuses |
| `'ffill'` | Reporte la valeur précédente (séries temporelles) | Données de prix |
| `'bfill'` | Reporte la valeur suivante | Séries temporelles |

---

### `remove_outliers(method, threshold, columns)`

Identifie et supprime les valeurs aberrantes.

```python
# Méthode Z-Score (défaut : seuil 3.0)
df = cleaner.remove_outliers(method="zscore", threshold=3.0)

# Méthode IQR (plus robuste pour les distributions asymétriques)
df = cleaner.remove_outliers(method="iqr")

# Sur une colonne spécifique
df = cleaner.remove_outliers(
    method="zscore",
    threshold=2.5,
    columns=["prix_xof_kg"],
)
```

**Méthodes disponibles :**

| Méthode | Critère de suppression | Usage |
|---------|----------------------|-------|
| `'zscore'` | `|z| > threshold` (défaut : 3.0) | Distributions normales |
| `'iqr'` | En dehors de [Q1 − 1.5×IQR, Q3 + 1.5×IQR] | Distributions asymétriques |
| `'mad'` | Écart à la médiane > threshold × MAD | Très robuste aux outliers extrêmes |

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

**Transformations appliquées :**

| Transformation | Exemple avant | Exemple après |
|----------------|--------------|---------------|
| Suppression des accents | `"Maïs"` | `"Mais"` |
| Mise en minuscules | `"PARAKOU"` | `"parakou"` |
| Suppression des espaces | `"  Abomey  "` | `"abomey"` |
| Unification des tirets | `"Mono-Couffo"` | `"mono couffo"` |

---

### `fix_encoding()`

Corrige les problèmes d'encodage fréquents dans les fichiers béninois (UTF-8,
Latin-1, Windows-1252 mélangés).

```python
df = cleaner.fix_encoding()
```

---

## Exemple complet

```python
import pandas as pd
from kadi.kidas import DataCleaner

df = pd.read_csv("enquete_prix_2024.csv", encoding="latin-1")
cleaner = DataCleaner(df)

df_propre = (
    cleaner
    .fix_encoding()
    .remove_duplicates()
    .handle_missing_values(strategy="median", columns=["prix_xof_kg", "quantite_kg"])
    .remove_outliers(method="iqr", columns=["prix_xof_kg"])
    .normalize_text(columns=["culture", "marche"])
)

print(f"Avant : {len(df)} lignes")
print(f"Après : {len(df_propre)} lignes")
```

---

::: kadi.kidas.cleaner.DataCleaner
