# kidas — KadiPy Data Acquisition & Standardization

`kidas` est le module central de traitement des données agricoles dans KadiPy.
Il prend en charge le chargement, le nettoyage, la validation, la normalisation
et la mise en cache des données issues de fichiers ou d'APIs REST.

Le module est conçu pour les flux de données AgriTech béninois : fichiers CHIRPS,
relevés de marchés WFP VAM, enquêtes agricoles MAEP, archives TAMSAT et ERA5.

---

## Table des matières

1. [Installation et configuration](#installation-et-configuration)
2. [Architecture du module](#architecture-du-module)
3. [Sources de données](#sources-de-données)
   - [CSVDataSource](#csvdatasource)
   - [ExcelDataSource](#exceldatasource)
   - [JSONDataSource](#jsondatasource)
   - [NetCDFDataSource](#netcdfdatasource)
   - [APIDataSource](#apidatasource)
4. [Traitement des données](#traitement-des-données)
   - [DataCleaner](#datacleaner)
   - [DataValidator](#datavalidator)
   - [DataNormalizer](#datanormalizer)
5. [Infrastructure](#infrastructure)
   - [DataCache](#datacache)
   - [DataPipeline](#datapipeline)
6. [Fonction de haut niveau : load_and_clean](#fonction-de-haut-niveau--load_and_clean)
7. [Référence des exceptions](#référence-des-exceptions)
8. [Notebooks de référence](#notebooks-de-référence)

---

## Installation et configuration

Le module fait partie du package KadiPy. Pour l'utiliser, activez l'environnement
virtuel :

```bash
source .kadi_venv/bin/activate
```

Les dépendances principales sont déclarées dans `requirements.txt` :

| Dépendance | Usage |
|---|---|
| `pandas >= 2.0` | Manipulation des données tabulaires |
| `numpy` | Calculs numériques et détection d'outliers |
| `scipy` | Z-score pour la détection statistique d'outliers |
| `openpyxl` | Lecture des fichiers Excel (.xlsx) |
| `requests` | Appels aux APIs REST |
| `xarray` | Lecture des fichiers NetCDF (optionnel) |
| `shapely >= 2.0` | Géométries GPS (optionnel, pour `normalize_geometry`) |

Installation des dépendances optionnelles :

```bash
pip install xarray shapely>=2.0
```

---

## Architecture du module

```
kadi/kidas/
├── __init__.py          # Point d'entrée du package, expose l'API publique
├── sources/
│   ├── base.py          # Classe abstraite DataSource
│   ├── csv_source.py    # CSVDataSource
│   ├── excel_source.py  # ExcelDataSource
│   ├── json_source.py   # JSONDataSource
│   ├── netcdf_source.py # NetCDFDataSource (requiert xarray)
│   └── api_source.py    # APIDataSource
├── cleaner.py           # DataCleaner
├── validator.py         # DataValidator
├── normalizer.py        # DataNormalizer
├── cache.py             # DataCache (SQLite)
└── pipeline.py          # DataPipeline (orchestrateur)
```

Toutes les classes sont accessibles directement via le package :

```python
import kadi.kidas as kidas

source   = kidas.CSVDataSource('recoltes.csv')
cleaner  = kidas.DataCleaner(df)
pipeline = kidas.DataPipeline()
```

---

## Sources de données

Toutes les sources héritent de `DataSource` (classe abstraite définie dans
`sources/base.py`) et exposent les méthodes communes suivantes :

| Méthode | Retour | Description |
|---|---|---|
| `validate_connection()` | `bool` | Vérifie l'accessibilité de la source |
| `read(**kwargs)` | `DataFrame` ou `DataArray` | Lit et retourne les données |
| `write(data)` | `bool` | Écrit des données vers la source |
| `get_metadata()` | `dict` | Informations sur la source |

---

### CSVDataSource

**Module :** `kadi.kidas.sources.csv_source`

Lecture de fichiers CSV, TSV et TXT avec détection automatique du séparateur,
encodage configurable, et conversion des types numériques avec virgule décimale.

```python
from kadi.kidas.sources.csv_source import CSVDataSource

source = CSVDataSource(
    file_path='donnees/recoltes_2024.csv',
    encoding='utf-8',
    separator=',',        # Auto-détecté si None
    decimal='.',
)

df = source.read()
```

**Paramètres du constructeur :**

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `file_path` | `str` | obligatoire | Chemin vers le fichier CSV |
| `encoding` | `str` | `'utf-8'` | Encodage du fichier |
| `separator` | `str` ou `None` | `None` | Séparateur de colonnes, auto-détecté si `None` |
| `decimal` | `str` | `'.'` | Séparateur décimal |

**Méthodes spécifiques :**

| Méthode | Description |
|---|---|
| `get_schema()` | Retourne les noms et types de colonnes |
| `detect_encoding()` | Détecte l'encodage du fichier via `chardet` |

**Notebook de référence :** [`docs/kidas/01_csv_source.ipynb`](../../../docs/kidas/01_csv_source.ipynb)

---

### ExcelDataSource

**Module :** `kadi.kidas.sources.excel_source`

Lecture de fichiers Excel (.xls, .xlsx, .xlsm) avec sélection d'onglet,
détection de la ligne d'en-tête et lecture de métadonnées depuis plusieurs
feuilles.

```python
from kadi.kidas.sources.excel_source import ExcelDataSource

source = ExcelDataSource(
    file_path='donnees/prix_marche_2024.xlsx',
    sheet_name='Parakou',    # Nom ou index de l'onglet (0 = premier)
    header=0,                # Ligne d'en-tête (0-indexée)
)

df = source.read()
```

**Paramètres du constructeur :**

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `file_path` | `str` | obligatoire | Chemin vers le fichier Excel |
| `sheet_name` | `str` ou `int` | `0` | Onglet à lire |
| `header` | `int` | `0` | Numéro de la ligne d'en-tête |

**Méthodes spécifiques :**

| Méthode | Description |
|---|---|
| `list_sheets()` | Retourne la liste des noms d'onglets disponibles |
| `get_schema()` | Retourne le schéma de la feuille active |

**Notebook de référence :** [`docs/kidas/02_excel_source.ipynb`](../../../docs/kidas/02_excel_source.ipynb)

---

### JSONDataSource

**Module :** `kadi.kidas.sources.json_source`

Lecture de fichiers JSON locaux avec détection automatique de la structure
(tableau direct, clé `data`, clé `results`) et aplatissement des structures
imbriquées.

```python
from kadi.kidas.sources.json_source import JSONDataSource

source = JSONDataSource(
    file_path='donnees/stations_meteo.json',
    encoding='utf-8',
)

df = source.read()
```

**Structures JSON supportées :**

| Structure | Exemple | Traitement |
|---|---|---|
| Tableau direct | `[{...}, {...}]` | Converti directement en DataFrame |
| Clé `data` | `{"data": [...], "meta": {...}}` | Clé `data` extraite automatiquement |
| Clé `results` | `{"results": [...]}` | Clé `results` extraite automatiquement |
| Objet imbriqué | `{"station": {"lat": 6.36, ...}}` | Aplati avec `pandas.json_normalize` |

**Notebook de référence :** [`docs/kidas/03_json_source.ipynb`](../../../docs/kidas/03_json_source.ipynb)

---

### NetCDFDataSource

**Module :** `kadi.kidas.sources.netcdf_source`

Lecture de fichiers NetCDF agrométéorologiques (CHIRPS, TAMSAT, ERA5, GFS, SoilGrids)
avec extraction spatiale et temporelle. Requiert `xarray`.

```python
from kadi.kidas.sources.netcdf_source import NetCDFDataSource

source = NetCDFDataSource(
    file_path='chirps_benin_2024.nc',
    use_dask=False,    # True pour les fichiers > 500 Mo
)

# Extraction avec bbox Bénin par défaut (lat: 2.5-12.5, lon: -1.5-4.0)
da = source.read()

# Extraction d'une zone personnalisée
da_nord = source.read(
    lat_bounds=(9.0, 12.5),
    lon_bounds=(1.5, 4.0),
    time_bounds=('2024-01-01', '2024-06-30'),
)

# Conversion en DataFrame tabulaire
df = source.to_dataframe()
```

**Paramètres du constructeur :**

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `file_path` | `str` | obligatoire | Chemin vers le fichier `.nc` |
| `use_dask` | `bool` | `False` | Active le chargement paresseux Dask |

**Méthodes spécifiques :**

| Méthode | Retour | Description |
|---|---|---|
| `get_dimensions()` | `dict` | Dictionnaire `{dimension: taille}` |
| `to_dataframe()` | `DataFrame` | Convertit le dernier DataArray extrait |

**Bbox Bénin par défaut :** `lat in [2.5, 12.5]`, `lon in [-1.5, 4.0]`

**Notebook de référence :** [`docs/kidas/04_netcdf_source.ipynb`](../../../docs/kidas/04_netcdf_source.ipynb)

---

### APIDataSource

**Module :** `kadi.kidas.sources.api_source`

Acquisition de données depuis des APIs REST avec rate limiting, réessais
automatiques avec backoff exponentiel et authentification Bearer.

```python
from kadi.kidas.sources.api_source import APIDataSource

# API publique
source = APIDataSource(
    api_url='https://api.open-meteo.com/v1/forecast',
    rate_limit_per_sec=5.0,
)

# API privée avec authentification
source_prive = APIDataSource(
    api_url='https://api.maep.benin.gov/v1/prix',
    auth_token='votre_token_api',
    rate_limit_per_sec=2.0,
)

# Requête GET avec conversion automatique en DataFrame
df = source.read(params={
    'latitude': 6.36,
    'longitude': 2.42,
    'daily': 'precipitation_sum',
    'timezone': 'Africa/Abidjan',
    'forecast_days': 7,
})

# Requête GET brute (JSON non transformé)
reponse = source.fetch_with_retry(params={...}, max_retries=3, backoff_sec=1.0)

# Envoi POST
df_envoi = pd.DataFrame({'culture': ['maïs'], 'prix_xof': [350]})
succes = source.write(df_envoi)
```

**Paramètres du constructeur :**

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `api_url` | `str` | obligatoire | URL de base de l'API |
| `auth_token` | `str` ou `None` | `None` | Token Bearer pour les APIs privées |
| `rate_limit_per_sec` | `float` | `5.0` | Nombre maximum de requêtes par seconde |

**Clés JSON détectées automatiquement par `read()` :**

| Clé | APIs utilisatrices |
|---|---|
| `data` | FAO GIEWS, WFP VAM, MAEP |
| `results` | APIs REST standards |
| `items` | APIs de type catalogue |
| `records` | Exports Airtable, Notion |
| `features` | GeoJSON |

**Codes HTTP gérés par le backoff :**
`429` (rate limit), `500`, `502`, `503`, `504`

**Méthodes spécifiques :**

| Méthode | Description |
|---|---|
| `fetch_with_retry(params, max_retries, backoff_sec)` | Requête GET avec réessais |
| `get_schema()` | Configuration de la source (URL, auth, rate) |

**Notebook de référence :** [`docs/kidas/05_api_source.ipynb`](../../../docs/kidas/05_api_source.ipynb)

---

## Traitement des données

---

### DataCleaner

**Module :** `kadi.kidas.cleaner`

Nettoyage des données agricoles tabulaires. Toutes les méthodes retournent
le DataFrame modifié et mettent à jour le rapport interne. L'usage enchaîné
est possible.

```python
from kadi.kidas.cleaner import DataCleaner

cleaner = DataCleaner(df)

df_propre = (
    cleaner
    .remove_duplicates()
    .handle_missing_values(strategy='mean')
    .fix_dates(columns=['date_recolte'])
    .standardize_text(columns=['culture', 'marche'], case='lower')
)

outliers_df = cleaner.remove_outliers(method='iqr', threshold=1.5)[1]
rapport = cleaner.get_cleaning_report()
```

**Méthodes disponibles :**

| Méthode | Paramètres clés | Description |
|---|---|---|
| `remove_duplicates(subset, keep)` | `keep='first'` | Supprime les lignes dupliquées |
| `handle_missing_values(strategy, columns)` | `strategy='mean'` | Traite les valeurs manquantes |
| `remove_outliers(method, threshold, columns)` | `method='iqr'` | Détecte et isole les outliers |
| `fix_dates(columns, infer_format)` | - | Normalise les formats de dates |
| `standardize_text(columns, case)` | `case='lower'` | Normalise le texte |
| `remove_special_chars(columns, keep_chars)` | - | Supprime les caractères spéciaux |
| `detect_inconsistent_decimals(columns)` | - | Détecte les mélanges `.` et `,` |
| `get_cleaning_report()` | - | Retourne le rapport de nettoyage |

**Stratégies de traitement des valeurs manquantes :**

| Stratégie | Comportement |
|---|---|
| `'mean'` | Remplace les NaN par la moyenne de la colonne (colonnes numériques) |
| `'median'` | Remplace par la médiane |
| `'forward_fill'` | Propage la dernière valeur connue vers le bas |
| `'drop'` | Supprime les lignes contenant des NaN |

**Méthodes de détection des outliers :**

| Méthode | Description |
|---|---|
| `'iqr'` | Règle de Tukey : Q1 - 1.5 x IQR et Q3 + 1.5 x IQR |
| `'zscore'` | Seuil sur le Z-score standardisé (recommandé : 3.0) |
| `'mad'` | Median Absolute Deviation, robuste aux valeurs extrêmes |

**Notebook de référence :** [`docs/kidas/06_data_cleaner.ipynb`](../../../docs/kidas/06_data_cleaner.ipynb)

---

### DataValidator

**Module :** `kadi.kidas.validator`

Validation qualité des données agricoles avec calcul d'un score global
multicritère.

```python
from kadi.kidas.validator import DataValidator

validator = DataValidator(df)

# Validation du schéma
valide, erreurs = validator.validate_schema({
    'culture': 'str',
    'rendement_kg': 'float',
    'date_recolte': 'datetime',
})

# Validation des intervalles de valeurs
valide, hors_borne = validator.validate_ranges({
    'temperature': (-10, 50),
    'rendement_kg': (0, 50000),
})

# Validation des coordonnées GPS (bbox Bénin par défaut)
valide, invalides = validator.validate_coordinates(
    lat_col='latitude',
    lon_col='longitude',
    region='benin',
)

# Score de qualité global
score = validator.compute_quality_score()
print(score['overall'])  # Score global entre 0.0 et 1.0
```

**Méthodes disponibles :**

| Méthode | Retour | Description |
|---|---|---|
| `validate_schema(schema)` | `(bool, list[str])` | Vérifie colonnes et types |
| `validate_types(column_dtypes)` | `(bool, DataFrame)` | Vérifie les types pandas |
| `validate_ranges(column_bounds)` | `(bool, DataFrame)` | Vérifie les intervalles |
| `validate_coordinates(lat_col, lon_col, region)` | `(bool, DataFrame)` | Vérifie la bbox GPS |
| `validate_uniqueness(columns)` | `(bool, DataFrame)` | Vérifie l'unicité (clé primaire) |
| `validate_referential_integrity(fk_col, reference_set)` | `(bool, DataFrame)` | Vérifie les clés étrangères |
| `compute_quality_score()` | `dict` | Calcule le score de qualité |
| `get_validation_report()` | `dict` | Retourne le rapport complet |

**Calcul du score de qualité :**

| Dimension | Poids | Calcul |
|---|---|---|
| Complétude | 40% | Proportion de cellules non nulles |
| Cohérence | 35% | 1 - taux de doublons |
| Précision | 25% | 1.0 par défaut (extensible) |

**Types acceptés par `validate_schema()` :**
`'str'`, `'string'`, `'int'`, `'integer'`, `'float'`, `'datetime'`, `'bool'`

**Notebook de référence :** [`docs/kidas/07_data_validator.ipynb`](../../../docs/kidas/07_data_validator.ipynb)

---

### DataNormalizer

**Module :** `kadi.kidas.normalizer`

Normalisation des conventions de dénomination et des unités pour le contexte
agricole béninois.

```python
from kadi.kidas.normalizer import DataNormalizer

normalizer = DataNormalizer(df)

df_norm = (
    normalizer
    .normalize_column_names()                          # snake_case
    .normalize_crop_names(col='culture')               # codes FAO
    .normalize_units(unit_map={'production': 'tonne'}) # vers kg
    .normalize_market_names(col='marche')              # + GPS coords
    .normalize_currencies(col='prix', from_currency='USD', to_currency='XOF')
)

mapping = normalizer.get_normalization_mapping()
```

**Méthodes disponibles :**

| Méthode | Description |
|---|---|
| `normalize_column_names(style)` | Renomme les colonnes en snake_case |
| `normalize_units(unit_map)` | Convertit les valeurs vers le kilogramme |
| `normalize_currencies(col, from_currency, to_currency)` | Convertit les devises |
| `normalize_crop_names(col, target_standard)` | Mappe vers les codes FAO |
| `normalize_market_names(col, region)` | Mappe + ajoute `market_lat`/`market_lon` |
| `normalize_geometry(lat_col, lon_col)` | Crée la colonne `geometry` (shapely) |
| `get_normalization_mapping()` | Retourne l'historique des transformations |

**Cultures reconnues (codes FAO) :**

| Noms locaux acceptés | Code FAO |
|---|---|
| maïs, mais, maiz, corn | `maize` |
| niébé, niebe, haricot, cowpea | `cowpea` |
| igname, yam | `yam` |
| sorgho, sorghum | `sorghum` |
| riz, rice | `rice` |
| manioc, cassava | `cassava` |
| arachide, groundnut, peanut | `groundnut` |
| mil, millet | `millet` |
| soja, soybean | `soybean` |
| tomate, tomato | `tomato` |
| oignon, onion | `onion` |
| piment, pepper | `pepper` |
| fonio | `fonio` |

**Unités supportées (conversion vers kg) :**

| Unité | Facteur |
|---|---|
| `kg`, `kilogramme` | 1.0 |
| `tonne`, `t` | 1000.0 |
| `sac` (standard Bénin) | 100.0 |
| `sac_80kg` | 80.0 |
| `sac_50kg` | 50.0 |
| `tiya` (mesure locale) | 1.5 |
| `quintal` | 100.0 |
| `g`, `gramme` | 0.001 |

**Marchés béninois géolocalisés :** Dantokpa, Parakou, Bohicon, Kandi,
Natitingou, Malanville, Abomey, Porto-Novo, Lokossa.

**Notebook de référence :** [`docs/kidas/08_data_normalizer.ipynb`](../../../docs/kidas/08_data_normalizer.ipynb)

---

## Infrastructure

---

### DataCache

**Module :** `kadi.kidas.cache`

Cache SQLite persistant pour les DataFrames kidas. Stockage compressé
(pickle + zlib), versioning par hash SHA256, invalidation par âge.

```python
from kadi.kidas.cache import DataCache

cache = DataCache(
    cache_dir='~/.kadi/kidas_cache/',  # Répertoire par défaut
    max_age_days=365,
)

# Sauvegarde
cache.save('recoltes_2024_benin', df)

# Chargement
df_cached, metadata = cache.load('recoltes_2024_benin')
if df_cached is not None:
    print(f"{len(df_cached)} lignes chargées depuis le cache")

# Consultation
print(cache.get_cached_keys())
print(cache.get_cache_size())

# Invalidation
cache.invalidate('recoltes_2024_benin')
cache.invalidate_older_than(days=30)

# Historique des versions
historique = cache.get_history('recoltes_2024_benin')
```

**Méthodes disponibles :**

| Méthode | Retour | Description |
|---|---|---|
| `save(key, data, metadata)` | `bool` | Sauvegarde et compresse un DataFrame |
| `load(key, check_validity)` | `(DataFrame, dict)` | Charge et décompresse |
| `get_cached_keys()` | `list[str]` | Liste toutes les clés actives |
| `invalidate(key)` | `bool` | Supprime une entrée spécifique |
| `invalidate_older_than(days)` | `int` | Supprime les entrées trop anciennes |
| `get_cache_size()` | `dict` | Taille totale et nombre d'entrées |
| `clear()` | `bool` | Vide entièrement le cache |
| `get_history(key)` | `list[dict]` | Historique des versions d'une clé |

**Localisation du cache :** `~/.kadi/kidas_cache/kidas_cache.db`

Le cache kidas est distinct du cache global KadiPy (météo, marchés).

**Notebook de référence :** [`docs/kidas/09_data_cache.ipynb`](../../../docs/kidas/09_data_cache.ipynb)

---

### DataPipeline

**Module :** `kadi.kidas.pipeline`

Orchestrateur central du module kidas. Point d'entrée recommandé pour
les traitements complets. API fluide (chaînable).

```python
from kadi.kidas.pipeline import DataPipeline

pipeline = DataPipeline()

df, rapport = (
    pipeline
    .load_data('recolte_2024.xlsx')
    .add_cleaning_step('remove_duplicates')
    .add_cleaning_step('handle_missing_values', strategy='mean')
    .add_cleaning_step('fix_dates', columns=['date_recolte'])
    .add_validation_step({'culture': 'str', 'rendement_kg': 'float'})
    .add_normalization_step({'crops': 'culture', 'units': {'rendement_kg': 'sac'}})
    .execute(cache=True)
)

print(rapport['quality_score']['overall'])

# Export du rapport
pipeline.export_report('rapport_pipeline.json')
pipeline.export_report('rapport_pipeline.html')
```

**Auto-détection du type de source :**

| Extension | Type détecté |
|---|---|
| `.csv`, `.tsv`, `.txt` | `CSVDataSource` |
| `.xls`, `.xlsx`, `.xlsm` | `ExcelDataSource` |
| `.json` | `JSONDataSource` |
| `.nc`, `.nc4`, `.netcdf` | `NetCDFDataSource` |
| URL `http://` ou `https://` | `APIDataSource` |

**Méthodes de configuration du pipeline :**

| Méthode | Retour | Description |
|---|---|---|
| `load_data(source, **kwargs)` | `DataPipeline` | Configure la source |
| `add_cleaning_step(step_name, **params)` | `DataPipeline` | Ajoute une étape de nettoyage |
| `add_validation_step(schema)` | `DataPipeline` | Ajoute une étape de validation |
| `add_normalization_step(mappings)` | `DataPipeline` | Ajoute une étape de normalisation |
| `execute(cache)` | `(DataFrame, dict)` | Exécute le pipeline |
| `get_pipeline_config()` | `dict` | Retourne la configuration |
| `export_report(filepath)` | `bool` | Exporte le rapport (.json ou .html) |

**Étapes de nettoyage acceptées par `add_cleaning_step()` :**

| Nom d'étape | Paramètres optionnels |
|---|---|
| `'remove_duplicates'` | `subset`, `keep` |
| `'handle_missing_values'` | `strategy`, `columns` |
| `'remove_outliers'` | `method`, `threshold`, `columns` |
| `'fix_dates'` | `columns` |
| `'standardize_text'` | `columns`, `case` |
| `'remove_special_chars'` | `columns`, `keep_chars` |

**Clés de normalisation acceptées par `add_normalization_step()` :**

| Clé | Valeur | Effet |
|---|---|---|
| `'columns'` | `True` | Renomme les colonnes en snake_case |
| `'crops'` | Nom de colonne | Normalise vers les codes FAO |
| `'units'` | `{col: unite}` | Convertit vers le kilogramme |
| `'markets'` | Nom de colonne | Géolocalise les marchés |

**Notebook de référence :** [`docs/kidas/10_data_pipeline.ipynb`](../../../docs/kidas/10_data_pipeline.ipynb)

---

## Fonction de haut niveau : load_and_clean

Pour les usages simples, une fonction pré-configurée est disponible directement
depuis le package :

```python
import kadi.kidas as kidas

df, rapport = kidas.load_and_clean(
    source='recoltes_2024.csv',
    cache=True,
)

print(f"{len(df)} lignes chargées")
print(f"Score qualité : {rapport.get('quality_score', {}).get('overall', 'N/A')}")
```

Cette fonction crée un `DataPipeline` avec deux étapes de nettoyage standard :
suppression des doublons et imputation des valeurs manquantes par la moyenne.

---

## Référence des exceptions

Toutes les exceptions personnalisées de kidas sont définies dans
`kadi/exceptions.py` et héritent de `KidasBaseError`.

| Exception | Déclenchée par |
|---|---|
| `KidasReadError` | Erreur de lecture d'une source |
| `KidasWriteError` | Erreur d'écriture vers une source |
| `KidasConnectionError` | Fichier introuvable ou API inaccessible |
| `KidasCleaningError` | Stratégie ou paramètre invalide dans DataCleaner/DataNormalizer |
| `KidasValidationError` | Colonne manquante dans DataValidator |
| `KidasCacheError` | Erreur SQLite dans DataCache |
| `KidasPipelineError` | Configuration invalide ou étape inconnue dans DataPipeline |

---

## Notebooks de référence

Des notebooks Jupyter illustrent chaque composant avec des exemples complets
et des explications de sortie. Ils sont situés dans `docs/kidas/` :

| Notebook | Composant |
|---|---|
| [`00_index.ipynb`](../../../docs/kidas/00_index.ipynb) | Vue d'ensemble du module kidas |
| [`01_csv_source.ipynb`](../../../docs/kidas/01_csv_source.ipynb) | `CSVDataSource` |
| [`02_excel_source.ipynb`](../../../docs/kidas/02_excel_source.ipynb) | `ExcelDataSource` |
| [`03_json_source.ipynb`](../../../docs/kidas/03_json_source.ipynb) | `JSONDataSource` |
| [`04_netcdf_source.ipynb`](../../../docs/kidas/04_netcdf_source.ipynb) | `NetCDFDataSource` |
| [`05_api_source.ipynb`](../../../docs/kidas/05_api_source.ipynb) | `APIDataSource` |
| [`06_data_cleaner.ipynb`](../../../docs/kidas/06_data_cleaner.ipynb) | `DataCleaner` |
| [`07_data_validator.ipynb`](../../../docs/kidas/07_data_validator.ipynb) | `DataValidator` |
| [`08_data_normalizer.ipynb`](../../../docs/kidas/08_data_normalizer.ipynb) | `DataNormalizer` |
| [`09_data_cache.ipynb`](../../../docs/kidas/09_data_cache.ipynb) | `DataCache` |
| [`10_data_pipeline.ipynb`](../../../docs/kidas/10_data_pipeline.ipynb) | `DataPipeline` |

Pour exécuter un notebook, activez l'environnement virtuel et lancez Jupyter :

```bash
source .kadi_venv/bin/activate
jupyter notebook docs/kidas/
```
