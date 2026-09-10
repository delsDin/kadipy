# Pipeline (`kadi.kidas.pipeline`)

`Pipeline` est l'orchestrateur central du module kidas. Il enchaîne les étapes
de nettoyage, validation et normalisation de manière déclarative, détecte
automatiquement le type de source depuis le chemin ou l'URL, et gère la mise
en cache des résultats via SQLite.

Son API est fluide : chaque méthode retourne l'instance courante, ce qui
permet d'enchaîner les appels sans variable intermédiaire.

---

## Initialisation

```python
from kadi.kidas import Pipeline

pipeline = Pipeline()
```

`Pipeline` s'initialise sans argument. La source et les étapes sont configurées
par méthodes chaînées.

---

## Méthodes de configuration

### `add_source(source, **kwargs)`

Configure la source de données du pipeline. Détecte automatiquement le type
de source depuis l'extension du fichier ou le préfixe de l'URL.

```python
pipeline.add_source("recoltes_2024.csv")
pipeline.add_source("rapport.xlsx", sheet="Parakou")
pipeline.add_source("https://api.data.bj/agriculture/prices")
```

Il est également possible de passer directement une instance `Source` :

```python
from kadi.io import CSVSource

source = CSVSource("recoltes.csv", sep=";", encoding="latin-1")
pipeline.add_source(source)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `source` | `str` ou `Source` | Chemin, URL ou instance `Source` |
| `**kwargs` | - | Arguments transmis au constructeur de la classe `Source` |

**Retour :** `Pipeline` (pour le chaînage).

**Alias court :** `load(source, **kwargs)`

---

### `add_step(step_name, schema_or_mappings=None, **params)`

Ajoute une étape de traitement à la file du pipeline. Le type de l'étape
(nettoyage, validation ou normalisation) est déterminé automatiquement selon
le nom passé.

```python
pipeline.add_step("drop_dupes")
pipeline.add_step("fill_missing", strategy="median")
pipeline.add_step("check_schema", {"culture": "str", "rendement_kg": "float"})
pipeline.add_step("norm_cols", {"crops": "culture"})
```

#### Étapes de nettoyage disponibles

| Nom | Description |
|-----|-------------|
| `'drop_dupes'` | Supprime les lignes dupliquées |
| `'fill_missing'` | Impute les valeurs manquantes (paramètre `strategy`) |
| `'drop_outliers'` | Supprime les valeurs aberrantes (paramètres `method`, `threshold`) |
| `'parse_dates'` | Normalise les colonnes de dates vers `datetime64` |
| `'norm_text'` | Normalise les chaînes de caractères (accents, casse, espaces) |
| `'strip_chars'` | Supprime les caractères spéciaux indésirables |

#### Étapes de validation disponibles

| Nom | Description |
|-----|-------------|
| `'check_schema'` | Vérifie les types de colonnes selon un schéma dict |
| `'check_types'` | Valide les types de données colonne par colonne |
| `'check_ranges'` | Contrôle que les valeurs numériques sont dans des plages définies |
| `'check_coords'` | Valide que les coordonnées GPS sont dans les limites du Bénin |
| `'check_unique'` | Vérifie l'unicité des valeurs dans les colonnes spécifiées |
| `'check_fk'` | Contrôle les contraintes de clé étrangère entre colonnes |

#### Étapes de normalisation disponibles

| Nom | Description |
|-----|-------------|
| `'norm_cols'` | Renomme les colonnes selon un dictionnaire de correspondances |
| `'convert_units'` | Convertit les unités (kg/tonne, ha/m2, etc.) |
| `'convert_currency'` | Convertit les devises via `ExchangeRateClient` |
| `'std_crops'` | Normalise les noms de cultures vers le référentiel KadiPy |
| `'std_markets'` | Normalise les noms de marchés |
| `'std_coords'` | Normalise les coordonnées GPS (format, arrondi) |

**Alias courts :**

- `clean(step, **params)` : alias pour les étapes de nettoyage
- `validate(schema, **params)` : alias pour `add_step('check_schema', schema)`
- `normalize(mappings, **params)` : alias pour `add_step('norm_cols', mappings)`

---

## Exécution

### `run(cache=True)`

Exécute toutes les étapes configurées dans l'ordre. Charge les données depuis
la source, applique chaque étape, met le résultat en cache si demandé.

```python
df, rapport = pipeline.run(cache=True)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cache` | `bool` | `True` | Tente un chargement depuis le cache avant la lecture, et sauvegarde le résultat après traitement |

**Retour :** `tuple[pd.DataFrame, dict]`

**Exceptions :**

- `PipelineError` : si aucune source n'a été configurée.
- `ReadError` : si la lecture de la source échoue.

#### Structure du rapport retourné

```python
df, rapport = pipeline.run()

rapport["nb_rows_in"]      # int   : lignes brutes chargées
rapport["nb_rows_out"]     # int   : lignes après traitement
rapport["steps_summary"]   # list  : noms des étapes dans l'ordre
rapport["quality_score"]   # dict | None : score qualité (si validation)
rapport["warnings"]        # list  : avertissements de validation
rapport["cache_utilise"]   # bool  : True si données issues du cache
rapport["details"]         # dict  : rapports internes de chaque étape
```

Le `quality_score` est un dict produit par `Validator`. Il est `None` si aucune
étape de validation n'a été configurée.

---

## Méthodes utilitaires

### `config()`

Retourne la configuration complète du pipeline : source configurée et liste
des étapes définies.

```python
cfg = pipeline.config()
print(f"Nombre d'étapes : {cfg['nb_steps']}")
for etape in cfg["steps"]:
    print(f"  {etape['type']} : {etape['nom']} ({etape['params']})")
```

**Retour :** `dict` avec les clés `source`, `nb_steps`, `steps`.

---

### `export(filepath)`

Exporte le rapport interne du pipeline dans un fichier JSON ou HTML selon
l'extension du chemin de destination.

```python
pipeline.export("rapport_pipeline.json")
pipeline.export("rapport_pipeline.html")
```

| Extension | Format |
|-----------|--------|
| `.json` | JSON indenté, encodé en UTF-8 |
| `.html` | Page HTML simple avec le JSON pré-formaté |

**Retour :** `True` si l'export réussit.

**Exception :** `PipelineError` si l'extension n'est pas supportée.

---

## Exemples complets

### Pipeline minimal

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .add_source("recoltes_2024.csv")
    .add_step("drop_dupes")
    .add_step("fill_missing", strategy="median")
    .run()
)
print(f"{rapport['nb_rows_in']} -> {rapport['nb_rows_out']} lignes")
```

### Pipeline avec validation et normalisation

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .add_source("enquete_prix_2024.xlsx")
    .add_step("drop_dupes")
    .add_step("fill_missing", strategy="median")
    .add_step("drop_outliers", method="iqr")
    .add_step("check_schema", {
        "culture":      "str",
        "marche":       "str",
        "prix_xof_kg":  "float",
        "date":         "datetime",
    })
    .add_step("std_crops", col="culture")
    .add_step("norm_cols", {"prix_xof_kg": "price_xof"})
    .run(cache=True)
)

if rapport.get("quality_score"):
    print(f"Score qualité : {rapport['quality_score']['overall']:.2f}")

for avertissement in rapport.get("warnings", []):
    print(avertissement)
```

### API fluide avec les alias courts

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .load("prix_2024.csv")
    .clean("drop_dupes")
    .clean("fill_missing", strategy="median")
    .validate({"culture": "str", "prix_xof_kg": "float"})
    .normalize({"crops": "culture"})
    .run(cache=True)
)
```

### Réutilisation d'une source existante

```python
from kadi.io import CSVSource
from kadi.kidas import Pipeline

source = CSVSource("export_maep.csv", sep=";", encoding="latin-1")

df, rapport = (
    Pipeline()
    .add_source(source)
    .add_step("drop_dupes")
    .add_step("parse_dates", cols=["date_recolte"])
    .run()
)
```

### Export du rapport

```python
pipeline = Pipeline()
df, rapport = (
    pipeline
    .add_source("donnees.csv")
    .add_step("check_schema", {"culture": "str"})
    .run()
)

pipeline.export("rapport.json")
```

---

## Comportement du cache

Le pipeline utilise un cache SQLite interne (géré par `Cache`). La clé de
cache est calculée par hachage SHA-256 du chemin de la source, tronqué à
16 caractères hexadécimaux.

Lorsque `cache=True` :

1. Le pipeline cherche une entrée existante dans le cache.
2. Si elle existe, les données sont retournées directement sans relire la source
   ni ré-exécuter les étapes.
3. Si elle n'existe pas, le pipeline exécute toutes les étapes et sauvegarde
   le résultat.

Le rapport indique si les données proviennent du cache via la clé `cache_utilise`.

Pour forcer une ré-exécution complète sans utiliser le cache :

```python
df, rapport = pipeline.run(cache=False)
```

---

## Rétrocompatibilité

Les anciens noms de méthodes émettent un `DeprecationWarning` et continuent
de fonctionner jusqu'à KadiPy v2.0 :

| Ancien nom (avant v1.2.0) | Nouveau nom |
|---------------------------|-------------|
| `load_data(source)` | `add_source(source)` ou `load(source)` |
| `add_cleaning_step(step)` | `add_step(step)` ou `clean(step)` |
| `add_validation_step(schema)` | `add_step('check_schema', schema)` ou `validate(schema)` |
| `add_normalization_step(mappings)` | `add_step('norm_cols', mappings)` ou `normalize(mappings)` |
| `execute(cache)` | `run(cache)` |
| `get_pipeline_config()` | `config()` |
| `export_report(filepath)` | `export(filepath)` |

---

::: kadi.kidas.pipeline.Pipeline
