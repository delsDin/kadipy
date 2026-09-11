# Validator (`kadi.kidas.validator`)

`Validator` est la classe de validation qualité des données agricoles tabulaires
de KadiPy. Elle regroupe six vérifications ciblées : schéma, types pandas,
intervalles numériques, coordonnées GPS, unicité et intégrité référentielle.
Elle calcule également un score de qualité global sur trois dimensions :
complétude, cohérence et précision.

Chaque méthode de validation retourne un tuple `(bool, résultat)`, ce qui
permet d'inspecter le résultat ou d'interrompre le traitement immédiatement
en cas d'anomalie. Toutes les vérifications effectuées sont enregistrées dans
un rapport interne accessible via `report()`.

---

## Initialisation

```python
from kadi.kidas import Validator

validator = Validator(df)
```

`Validator` reçoit un `pandas.DataFrame`. Le DataFrame n'est pas copié : il
est conservé en référence et n'est jamais modifié par les méthodes de
validation.

**Exception :** `ValidationError` si l'argument fourni n'est pas un DataFrame.

---

## Méthodes de validation

### `check_schema(schema)`

Vérifie que le DataFrame contient les colonnes définies dans le schéma et que
leurs types correspondent.

```python
valide, erreurs = validator.check_schema({
    "culture":       "str",
    "rendement_kg":  "float",
    "date_recolte":  "datetime",
})

if not valide:
    for msg in erreurs:
        print(msg)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `schema` | `dict[str, str]` | Dictionnaire `nom_colonne` → `type attendu` |

**Types acceptés :**

| Valeur | Interprétation |
|--------|----------------|
| `'str'` ou `'string'` | Colonne de type texte (`object`) |
| `'int'` ou `'integer'` | Colonne entière |
| `'float'` | Colonne flottante |
| `'datetime'` | Colonne de type `datetime64` |
| `'bool'` | Colonne booléenne |

**Retour :** `tuple[bool, list[str]]`

- `True` si le schéma est valide, `False` sinon.
- Liste des messages d'erreur (vide si valide).

---

### `check_types(dtypes)`

Vérifie la conformité des types pandas réels pour chaque colonne, avec une
comparaison flexible (ex: `int64` et `int32` sont tous deux acceptés pour
`'int'`).

```python
valide, df_erreurs = validator.check_types({
    "culture":      "object",
    "rendement_kg": "float64",
    "date_recolte": "datetime64[ns]",
})

if not valide:
    print(df_erreurs)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `dtypes` | `dict[str, str]` | Dictionnaire `nom_colonne` → dtype pandas attendu |

**Retour :** `tuple[bool, pd.DataFrame]`

- `True` si tous les types correspondent.
- DataFrame des colonnes non conformes (vide si OK), avec les colonnes
  `colonne`, `dtype_attendu`, `dtype_reel`.

---

### `check_ranges(bounds)`

Vérifie que les valeurs numériques des colonnes spécifiées sont comprises dans
les intervalles indiqués. Les valeurs `NaN` sont ignorées.

```python
valide, df_hors_borne = validator.check_ranges({
    "temperature":   (-10, 50),
    "rendement_kg":  (0, 50000),
    "prix_xof_kg":   (0, 5000),
})

if not valide:
    print(f"{len(df_hors_borne)} ligne(s) hors intervalle.")
    print(df_hors_borne)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `bounds` | `dict[str, tuple]` | Dictionnaire `nom_colonne` → `(min, max)` |

Les bornes sont inclusives. Une colonne absente du DataFrame génère un
avertissement dans les logs et est ignorée sans erreur.

**Retour :** `tuple[bool, pd.DataFrame]`

- `True` si toutes les valeurs respectent les bornes.
- DataFrame des lignes hors-intervalle, toutes colonnes incluses (vide si OK).

---

### `check_coords(lat, lon, region='benin')`

Vérifie que les coordonnées GPS sont dans la bounding box de la région
spécifiée. Détecte également les inversions lat/lon accidentelles.

```python
valide, df_invalides = validator.check_coords(
    lat="latitude",
    lon="longitude",
)

# Avec la région par défaut ('benin') :
# latitude  ∈ [2.5,  12.5]
# longitude ∈ [-1.5,  4.0]

if not valide:
    print(f"{len(df_invalides)} coordonnée(s) invalide(s).")
```

Lorsque `region` est différente de `'benin'`, les bornes mondiales
`[-90, 90]` pour la latitude et `[-180, 180]` pour la longitude sont utilisées.

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lat` | `str` | - | Nom de la colonne de latitude |
| `lon` | `str` | - | Nom de la colonne de longitude |
| `region` | `str` | `'benin'` | Région de référence pour la bbox |

**Retour :** `tuple[bool, pd.DataFrame]`

- `True` si toutes les coordonnées sont dans la bbox.
- DataFrame des lignes avec des coordonnées hors-bbox (vide si OK).

**Exception :** `ValidationError` si l'une des colonnes `lat` ou `lon` est
absente du DataFrame.

---

### `check_unique(cols)`

Vérifie que la combinaison des colonnes spécifiées est unique sur l'ensemble
des lignes (équivalent d'une clé primaire composite).

```python
valide, df_doublons = validator.check_unique(
    cols=["culture", "marche", "date_recolte"]
)

if not valide:
    print(f"{len(df_doublons)} ligne(s) en doublon.")
    print(df_doublons)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `cols` | `list[str]` | Colonnes dont la combinaison doit être unique |

**Retour :** `tuple[bool, pd.DataFrame]`

- `True` si la combinaison est unique.
- DataFrame de toutes les occurrences impliquées dans un doublon (vide si OK).

---

### `check_fk(fk_col, ref)`

Vérifie l'intégrité référentielle d'une colonne : chaque valeur non-null doit
figurer dans l'ensemble de référence fourni.

```python
marches_valides = {"Cotonou", "Porto-Novo", "Parakou", "Bohicon"}

valide, df_manquants = validator.check_fk(
    fk_col="marche",
    ref=marches_valides,
)

if not valide:
    print(f"{len(df_manquants)} référence(s) inconnue(s).")
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `fk_col` | `str` | Nom de la colonne contenant la clé étrangère |
| `ref` | `set` | Ensemble des valeurs valides attendues |

**Retour :** `tuple[bool, pd.DataFrame]`

- `True` si toutes les valeurs sont dans l'ensemble de référence.
- DataFrame des lignes avec des valeurs absentes de la référence (vide si OK).

**Exception :** `ValidationError` si la colonne `fk_col` est absente.

---

### `quality_score()`

Calcule un score de qualité global et par dimension pour le DataFrame.

```python
score = validator.quality_score()

print(score["overall"])       # ex: 0.8742
print(score["completeness"])  # proportion de cellules non-null
print(score["consistency"])   # 1 - taux de doublons
print(score["accuracy"])      # 1.0 (extensible)
print(score["columns"])       # score de complétude par colonne
```

Le score global est une moyenne pondérée :

| Dimension | Poids | Calcul |
|-----------|-------|--------|
| Complétude | 40 % | Proportion de cellules non-null |
| Cohérence | 35 % | `1 - (nb_doublons / nb_lignes)` |
| Précision | 25 % | `1.0` par défaut (extensible) |

**Retour :** `dict` avec les clés :

| Clé | Type | Description |
|-----|------|-------------|
| `overall` | `float` | Score global ∈ [0.0, 1.0] |
| `completeness` | `float` | Score de complétude |
| `consistency` | `float` | Score de cohérence |
| `accuracy` | `float` | Score de précision |
| `columns` | `dict[str, float]` | Complétude par colonne |

---

### `report()`

Retourne le rapport complet des validations effectuées depuis l'initialisation
du `Validator`.

```python
validator.check_schema({"culture": "str", "rendement_kg": "float"})
validator.check_ranges({"rendement_kg": (0, 50000)})
validator.quality_score()

rapport = validator.report()
# {
#   "lignes": 1500,
#   "colonnes": 8,
#   "validations": [
#     {"type": "schema",  "valide": True,  "nb_erreurs": 0, "erreurs": []},
#     {"type": "ranges",  "valide": False, "hors_borne": 3},
#   ],
#   "quality_score": {
#     "overall": 0.9245,
#     ...
#   }
# }
```

| Clé | Type | Description |
|-----|------|-------------|
| `lignes` | `int` | Nombre de lignes du DataFrame à l'initialisation |
| `colonnes` | `int` | Nombre de colonnes à l'initialisation |
| `validations` | `list` | Résultats de chaque validation effectuée |
| `quality_score` | `dict` | Présent uniquement si `quality_score()` a été appelé |

**Retour :** `dict` (copie du rapport interne).

---

## Exemple complet

```python
import kadi as kd
from kadi.kidas import Validator

df = kd.read_csv("enquete_prix_2024.csv")
validator = Validator(df)

schema = {
    "culture":      "str",
    "marche":       "str",
    "date_recolte": "datetime",
    "rendement_kg": "float",
    "prix_xof_kg":  "float",
    "latitude":     "float",
    "longitude":    "float",
}

valide, erreurs = validator.check_schema(schema)
if not valide:
    for msg in erreurs:
        print(msg)

valide, df_hors_borne = validator.check_ranges({
    "rendement_kg": (0, 50000),
    "prix_xof_kg":  (0, 5000),
})

valide, df_coords = validator.check_coords(lat="latitude", lon="longitude")

score = validator.quality_score()
print(f"Score qualité : {score['overall']:.2%}")

rapport = validator.report()
```

---

## Utilisation dans un Pipeline

`Validator` est utilisé en interne par `Pipeline` lorsqu'on ajoute une étape
de validation via `add_step` ou `validate`.

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .add_source("enquete_prix_2024.csv")
    .add_step("check_schema", schema={"culture": "str", "rendement_kg": "float"})
    .add_step("check_ranges", bounds={"rendement_kg": (0, 50000)})
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
| `validate_schema()` | `check_schema()` |
| `validate_types()` | `check_types()` |
| `validate_ranges()` | `check_ranges()` |
| `validate_coordinates()` | `check_coords()` |
| `validate_uniqueness()` | `check_unique()` |
| `validate_referential_integrity()` | `check_fk()` |
| `compute_quality_score()` | `quality_score()` |
| `get_validation_report()` | `report()` |

De même, le nom de classe `DataValidator` est un alias de `Validator`.

---

::: kadi.kidas.validator.Validator
