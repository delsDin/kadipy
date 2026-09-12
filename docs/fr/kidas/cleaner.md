# Cleaner (`kadi.kidas.cleaner`)

`Cleaner` est la classe de nettoyage des données agricoles tabulaires de
KadiPy. Elle fournit six méthodes de nettoyage adaptées aux fichiers agricoles
béninois : doublons, valeurs manquantes, outliers statistiques, dates
hétérogènes, texte non normalisé et séparateurs décimaux mixtes.

Chaque méthode met à jour le DataFrame interne et retourne ce DataFrame, ce
qui permet d'enchaîner les appels en une seule expression.

---

## Initialisation

```python
from kadi.kidas import Cleaner

cleaner = Cleaner(df)
```

`Cleaner` reçoit un `pandas.DataFrame` et en crée une copie interne. Le
DataFrame original n'est jamais modifié.

**Exception :** `CleanError` si l'argument fourni n'est pas un DataFrame.

---

## Méthodes de nettoyage

### `drop_dupes(subset=None, keep='first')`

Supprime les lignes dupliquées.

```python
df_propre = cleaner.drop_dupes()

# Sur un sous-ensemble de colonnes
df_propre = cleaner.drop_dupes(subset=["culture", "marche", "date"])

# Garder la dernière occurrence plutôt que la première
df_propre = cleaner.drop_dupes(keep="last")
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `subset` | `list[str]` ou `None` | `None` | Colonnes à considérer pour la détection. `None` pour toutes. |
| `keep` | `str` | `'first'` | `'first'` : première occurrence, `'last'` : dernière, `False` : supprime tout |

**Retour :** `pd.DataFrame`

---

### `fill_missing(strategy='mean', cols=None)`

Traite les valeurs manquantes (NaN) selon une stratégie choisie. Seules les
colonnes numériques sont affectées par `'mean'` et `'median'`.

```python
# Imputation par la médiane sur toutes les colonnes numériques
df_propre = cleaner.fill_missing(strategy="median")

# Propagation temporelle sur des colonnes spécifiques
df_propre = cleaner.fill_missing(
    strategy="forward_fill",
    cols=["prix_xof_kg", "temperature"],
)

# Suppression des lignes incomplètes
df_propre = cleaner.fill_missing(strategy="drop")
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `strategy` | `str` | `'mean'` | Stratégie d'imputation : `'mean'`, `'median'`, `'forward_fill'`, `'drop'` |
| `cols` | `list[str]` ou `None` | `None` | Colonnes cibles. `None` pour toutes les colonnes. |

**Stratégies disponibles :**

| Valeur | Comportement |
|--------|-------------|
| `'mean'` | Remplace les NaN par la moyenne de chaque colonne numérique |
| `'median'` | Remplace les NaN par la médiane de chaque colonne numérique |
| `'forward_fill'` | Propage la dernière valeur connue vers le bas (`ffill` + `bfill` en secours) |
| `'drop'` | Supprime les lignes contenant au moins un NaN dans les colonnes cibles |

**Retour :** `pd.DataFrame`

**Exception :** `CleanError` si la stratégie fournie est inconnue.

---

### `drop_outliers(method='iqr', thresh=1.5, cols=None)`

Détecte et supprime les outliers statistiques sur les colonnes numériques.
Retourne un tuple : le DataFrame nettoyé et le DataFrame des lignes exclues.

```python
# Méthode IQR (défaut)
df_propre, df_outliers = cleaner.drop_outliers()

# Z-score avec seuil personnalisé
df_propre, df_outliers = cleaner.drop_outliers(method="zscore", thresh=3.0)

# MAD sur des colonnes ciblées
df_propre, df_outliers = cleaner.drop_outliers(
    method="mad",
    thresh=3.5,
    cols=["prix_xof_kg", "rendement_kg"],
)

# Inspecter les lignes exclues
print(f"{len(df_outliers)} outlier(s) détecté(s)")
print(df_outliers)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `method` | `str` | `'iqr'` | Méthode de détection : `'iqr'`, `'zscore'`, `'mad'` |
| `thresh` | `float` | `1.5` | Seuil de détection (1.5 pour IQR, 3.0 recommandé pour Z-score) |
| `cols` | `list[str]` ou `None` | `None` | Colonnes numériques à analyser. `None` pour toutes. |

**Méthodes disponibles :**

| Valeur | Algorithme |
|--------|-----------|
| `'iqr'` | Règle de Tukey : exclut les valeurs hors de `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]` |
| `'zscore'` | Exclut les valeurs dont le Z-score standardisé dépasse `thresh` |
| `'mad'` | Median Absolute Deviation, robuste aux distributions asymétriques |

**Retour :** `tuple[pd.DataFrame, pd.DataFrame]` : (DataFrame nettoyé, DataFrame des outliers)

**Exception :** `CleanError` si la méthode fournie est inconnue.

---

### `parse_dates(cols=None, infer=True)`

Normalise les colonnes de dates en `datetime64`. Utilise `pd.to_datetime`
avec le mode `"mixed"` de pandas (compatibilité avec les formats hétérogènes).
Les valeurs non parsables sont converties en `NaT` sans erreur.

```python
# Auto-détection sur toutes les colonnes de type objet
df_propre = cleaner.parse_dates()

# Sur des colonnes spécifiques
df_propre = cleaner.parse_dates(cols=["date_recolte", "date_saisie"])
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cols` | `list[str]` ou `None` | `None` | Colonnes à convertir. `None` : toutes les colonnes `object`. |
| `infer` | `bool` | `True` | Infère le format automatiquement (actuellement toujours actif). |

**Retour :** `pd.DataFrame`

---

### `norm_text(cols=None, case='lower')`

Standardise le texte des colonnes : suppression des espaces en début et fin
de chaîne, normalisation des accents (ASCII), et application de la casse.

```python
# Normalisation minuscule sur toutes les colonnes texte
df_propre = cleaner.norm_text()

# Majuscules sur des colonnes spécifiques
df_propre = cleaner.norm_text(cols=["culture", "marche"], case="upper")

# Casse titre
df_propre = cleaner.norm_text(cols=["marche"], case="title")
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cols` | `list[str]` ou `None` | `None` | Colonnes texte. `None` : toutes les colonnes `object`. |
| `case` | `str` | `'lower'` | Casse : `'lower'`, `'upper'`, `'title'` |

**Retour :** `pd.DataFrame`

---

### `strip_chars(cols=None, keep='')`

Supprime les caractères spéciaux des colonnes texte. Conserve uniquement les
caractères alphanumériques, les espaces et les caractères explicitement listés
dans `keep`.

```python
# Suppression complète des caractères spéciaux
df_propre = cleaner.strip_chars()

# Préservation du tiret (utile pour des codes de parcelle type "PAR-001")
df_propre = cleaner.strip_chars(cols=["code_parcelle"], keep="-")
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cols` | `list[str]` ou `None` | `None` | Colonnes texte. `None` : toutes les colonnes `object`. |
| `keep` | `str` | `''` | Caractères à ne pas supprimer (ex: `'-'`, `'_.'`) |

**Retour :** `pd.DataFrame`

---

### `check_decimals(cols=None)`

Détecte la coexistence de séparateurs décimaux `.` et `,` dans les colonnes
texte. Utile pour diagnostiquer les exports mixant les conventions française
et anglaise. Ne modifie pas le DataFrame.

```python
rapport = cleaner.check_decimals(cols=["prix_xof_kg", "rendement"])

# Exemple de retour
# {
#   "prix_xof_kg": {
#     "has_dot": True,
#     "has_comma": True,
#     "mixed": True,
#     "count_dot": 42,
#     "count_comma": 8
#   }
# }

for colonne, info in rapport.items():
    if info["mixed"]:
        print(f"Melange detecte dans '{colonne}' : {info['count_dot']} points, {info['count_comma']} virgules")
```

| Clé retournée | Type | Description |
|---------------|------|-------------|
| `has_dot` | `bool` | Présence du séparateur `.` dans la colonne |
| `has_comma` | `bool` | Présence du séparateur `,` dans la colonne |
| `mixed` | `bool` | `True` si les deux coexistent |
| `count_dot` | `int` | Nombre de valeurs avec `.` comme décimale |
| `count_comma` | `int` | Nombre de valeurs avec `,` comme décimale |

**Retour :** `dict[str, dict]` (une entrée par colonne analysée). Ne modifie pas `self.df`.

---

### `report()`

Retourne le rapport complet des opérations de nettoyage effectuées depuis
l'initialisation du `Cleaner`.

```python
cleaner = Cleaner(df)
cleaner.drop_dupes()
cleaner.fill_missing(strategy="median")
cleaner.drop_outliers(method="iqr")

rapport = cleaner.report()
# {
#   "lignes_initiales": 1500,
#   "lignes_finales": 1421,
#   "colonnes_initiales": 8,
#   "colonnes_finales": 8,
#   "doublons_supprimes": 23,
#   "nan_traites": 14,
#   "outliers_detectes": 42,
#   "dates_corrigees": 0,
#   "operations": [...]
# }
```

| Clé | Type | Description |
|-----|------|-------------|
| `lignes_initiales` | `int` | Nombre de lignes avant tout nettoyage |
| `lignes_finales` | `int` | Nombre de lignes après nettoyage |
| `colonnes_initiales` | `int` | Nombre de colonnes à l'initialisation |
| `colonnes_finales` | `int` | Nombre de colonnes après nettoyage |
| `doublons_supprimes` | `int` | Total des doublons supprimés |
| `nan_traites` | `int` | Total des valeurs manquantes traitées |
| `outliers_detectes` | `int` | Total des outliers supprimés |
| `dates_corrigees` | `int` | Total des valeurs de dates converties |
| `operations` | `list` | Historique détaillé de chaque opération |

---

## Exemple complet enchaîné

```python
import kadi as kd
from kadi.kidas import Cleaner

df = kd.read_csv("enquete_prix_2024.csv")
cleaner = Cleaner(df)

# Enchaînement des étapes retournant un DataFrame
cleaner.drop_dupes(subset=["culture", "marche", "date"])
cleaner.fill_missing(strategy="median", cols=["prix_xof_kg", "quantite_kg"])
cleaner.norm_text(cols=["culture", "marche"])
cleaner.parse_dates(cols=["date"])

# drop_outliers retourne un tuple : capture explicite requise
df_propre, df_outliers = cleaner.drop_outliers(method="iqr", cols=["prix_xof_kg"])

rapport = cleaner.report()
print(f"Lignes : {rapport['lignes_initiales']} -> {rapport['lignes_finales']}")
print(f"Outliers extraits : {len(df_outliers)}")
```

> `drop_outliers` retourne un `tuple` et non le DataFrame seul. Il ne peut pas
> être enchaîné directement avec d'autres méthodes.

---

## Utilisation dans un Pipeline

`Cleaner` est utilisé en interne par `Pipeline` lorsqu'on ajoute une étape
de nettoyage via `add_step` ou `clean`.

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .add_source("recoltes.csv")
    .add_step("drop_dupes")
    .add_step("fill_missing", strategy="median")
    .add_step("drop_outliers", method="iqr")
    .add_step("norm_text")
    .run()
)
```

Pour la documentation du pipeline, voir [Pipeline](pipeline.md).

---

## Rétrocompatibilité

Les anciens noms de méthodes émettent un `DeprecationWarning` et continuent
de fonctionner jusqu'à KadiPy v2.0 :

| Ancien nom (avant v1.2.0) | Nouveau nom |
|---------------------------|-------------|
| `remove_duplicates()` | `drop_dupes()` |
| `handle_missing_values()` | `fill_missing()` |
| `remove_outliers()` | `drop_outliers()` |
| `fix_dates()` | `parse_dates()` |
| `standardize_text()` | `norm_text()` |
| `remove_special_chars()` | `strip_chars()` |
| `detect_inconsistent_decimals()` | `check_decimals()` |
| `get_cleaning_report()` | `report()` |

De même, le nom de classe `DataCleaner` est un alias de `Cleaner`.

---

::: kadi.kidas.cleaner.Cleaner
