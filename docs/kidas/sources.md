# Sources de données (`kadi.kidas.sources`)

Le sous-package `kadi.kidas.sources` regroupe toutes les classes permettant
de lire et d'écrire des données agricoles depuis différents formats. Chaque
classe concrète hérite de `Source`, la classe abstraite de base, et implémente
le même contrat : `read()`, `write()`, `info()`, `ping()`.

| Classe | Format | Extensions / Préfixe |
|--------|--------|-----------------------|
| `CSVSource` | Fichiers texte délimités | `.csv` |
| `ExcelSource` | Classeurs Excel | `.xlsx`, `.xls` |
| `JSONSource` | Fichiers JSON ou dicts Python | `.json` |
| `NetCDFSource` | Données grillées agrométéo | `.nc`, `.netcdf` |
| `APISource` | APIs REST HTTP | `http://`, `https://` |

---

## Import

```python
from kadi.kidas import CSVSource, ExcelSource, JSONSource, NetCDFSource, APISource

# ou depuis le sous-package directement
from kadi.kidas.sources import CSVSource
```

Les classes sont également réexportées depuis `kadi.io`. Voir
[Entrées et sorties](../io.md) pour la documentation des fonctions
`read_*`, `write_*` et `write`.

---

## `Source` (classe abstraite)

`Source` est l'interface commune à toutes les sources de données. Elle ne
s'instancie pas directement.

**Attributs communs :**

| Attribut | Type | Description |
|----------|------|-------------|
| `path` | `str` | Chemin local du fichier ou URI de la ressource |
| `kind` | `str` | Type de source : `'csv'`, `'excel'`, `'json'`, `'netcdf'`, `'api'` |
| `encoding` | `str` | Encodage des données (peut être `'auto'`) |
| `last_read` | `datetime` ou `None` | Horodatage de la dernière lecture réussie |

**Méthodes abstraites que chaque sous-classe implémente :**

- `read(**kwargs)` : lit les données et retourne un `pd.DataFrame`
- `write(data, **kwargs)` : écrit un DataFrame vers la source, retourne `bool`
- `info()` : retourne un `dict` de métadonnées
- `ping()` : retourne `True` si la source est accessible

---

## `CSVSource`

Source pour les fichiers CSV agricoles avec détection automatique de
l'encodage (via chardet), du délimiteur et du séparateur décimal.
Conçue pour les exports de capteurs IoT, de coopératives et des bases
de données nationales (INSAE, MAEP).

### Initialisation

```python
from kadi.kidas import CSVSource

# Détection automatique de tout
source = CSVSource("recoltes_2024.csv")

# Paramètres explicites
source = CSVSource(
    "export_insae.csv",
    encoding="latin-1",
    sep=";",
    decimal=",",
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `path` | `str` | - | Chemin vers le fichier CSV |
| `encoding` | `str` | `'auto'` | Encodage. `'auto'` : détecté via chardet |
| `sep` | `str` | `'auto'` | Délimiteur de colonnes. `'auto'` : auto-détecté |
| `decimal` | `str` | `'auto'` | Séparateur décimal. `'auto'` : inféré selon le délimiteur |

En mode `'auto'`, l'encodage est détecté sur un échantillon de 10 000 octets.
Le délimiteur est détecté par `csv.Sniffer` avec fallback par comptage
d'occurrences parmi `,`, `;`, `\t`, `|`. Si le délimiteur est `;`, le
séparateur décimal inféré est `,` (convention française).

### `read(n=None, skip=None)`

```python
df = source.read()

# 100 premières lignes
df = source.read(n=100)

# Ignorer 2 lignes de métadonnées en début de fichier
df = source.read(skip=2)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `n` | `int` ou `None` | `None` | Nombre maximum de lignes à lire |
| `skip` | `int` ou `None` | `None` | Lignes à ignorer en début de fichier (hors en-tête) |

Tente plusieurs encodages en fallback (`utf-8`, `latin-1`, `cp1252`) si la
lecture principale échoue.

**Retour :** `pd.DataFrame`
**Exceptions :** `ConnectError` si le fichier est inaccessible, `ReadError`
si tous les encodages échouent.

### `write(data, index=False)`

```python
source.write(df)
source.write(df, index=True)
```

Écrit en UTF-8 si l'encodage est `'auto'`. Utilise le délimiteur détecté ou
`,` par défaut.

**Retour :** `bool`
**Exception :** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'path': 'recoltes_2024.csv',
#   'kind': 'csv',
#   'encoding': 'utf-8',
#   'sep': ',',
#   'decimal': 'inféré',
#   'rows': 1500,
#   'cols': 8,
#   'size_kb': 42.31,
#   'last_read': '2024-09-01T10:23:45.123456'
# }
```

### `ping()`

Vérifie que le fichier existe et est lisible en lecture. Retourne `bool`.

---

## `ExcelSource`

Source pour les fichiers Excel (`.xlsx`, `.xls`) avec détection automatique
de la ligne d'en-tête et résolution des cellules fusionnées par forward fill.
Adaptée aux rapports agricoles béninois avec communes et marchés fusionnés
sur plusieurs lignes.

### Initialisation

```python
from kadi.kidas import ExcelSource

source = ExcelSource("prix_marches_2024.xlsx")

# Feuille et en-tête explicites
source = ExcelSource("rapport.xlsx", sheet="Janvier", header=2)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `path` | `str` | - | Chemin vers le fichier Excel |
| `sheet` | `str` ou `int` | `0` | Feuille par défaut (nom ou index) |
| `header` | `str` ou `int` | `'auto'` | Ligne d'en-tête. `'auto'` : détectée automatiquement |

La détection d'en-tête inspecte les 15 premières lignes et retient la ligne
la plus dense (plus grand nombre de valeurs non-null).

### `sheets()`

Retourne la liste des noms de feuilles du classeur.

```python
feuilles = source.sheets()
# ['Janvier', 'Fevrier', 'Mars']
```

**Retour :** `list[str]`
**Exceptions :** `ConnectError`, `ReadError`

### `sheet_info(sheet)`

Retourne les métadonnées d'une feuille spécifique.

```python
meta = source.sheet_info("Janvier")
# {
#   'sheet': 'Janvier',
#   'rows': 245,
#   'cols': 6,
#   'columns': ['culture', 'marche', 'prix_xof_kg', ...]
# }
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `sheet` | `str` ou `int` | Nom ou index de la feuille à inspecter |

**Retour :** `dict`
**Exception :** `ReadError`

### `read(sheet=None)`

```python
df = source.read()

# Lire une feuille spécifique
df = source.read(sheet="Fevrier")
```

Applique un forward fill vertical sur toutes les colonnes pour résoudre
les cellules fusionnées, puis supprime les lignes entièrement vides.

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `sheet` | `str`, `int` ou `None` | `None` | Feuille à lire. `None` : utilise celle définie à l'initialisation |

**Retour :** `pd.DataFrame`
**Exceptions :** `ConnectError`, `ReadError`

### `write(data, sheet='Sheet1')`

```python
source.write(df, sheet="Export")
```

**Retour :** `bool`
**Exception :** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'path': 'prix_marches_2024.xlsx',
#   'kind': 'excel',
#   'sheets': ['Janvier', 'Fevrier'],
#   'active_sheet': 0,
#   'detected_header': 1,
#   'size_kb': 118.7,
#   'last_read': None
# }
```

### `ping()`

Vérifie que le fichier existe et est lisible en lecture. Retourne `bool`.

---

## `JSONSource`

Source pour les fichiers JSON plats ou imbriqués, tels que retournés par les
APIs agricoles (FAO, WFP VAM, MAEP). Supporte également un dictionnaire Python
fourni directement en mémoire.

### Initialisation

```python
from kadi.kidas import JSONSource

# Depuis un fichier
source = JSONSource("donnees_fao.json")

# Depuis un dictionnaire Python en mémoire
data = {"location": {"lat": 9.3, "lon": 2.4}, "crop": "maize"}
source = JSONSource(data)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `file_path_or_dict` | `str` ou `dict` | Chemin vers le fichier JSON ou dictionnaire Python |

Quand la source est un dictionnaire, `path` vaut `'<dict_en_memoire>'` et
`ping()` retourne toujours `True`.

### `flatten(obj, sep='.')`

Aplatit récursivement un objet JSON imbriqué en utilisant la notation pointée.

```python
obj = {"location": {"lat": 9.3, "lon": 2.4}, "crop": "maize"}
plat = source.flatten(obj)
# {"location.lat": 9.3, "location.lon": 2.4, "crop": "maize"}
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `obj` | `dict` | - | L'objet JSON à aplatir |
| `sep` | `str` | `'.'` | Séparateur entre les niveaux de clés |

Les listes sont indexées par leur position (`location.items.0`, `location.items.1`...).

**Retour :** `dict`

### `read(flatten=True)`

```python
df = source.read()

# Sans aplatissement (pd.json_normalize direct)
df = source.read(flatten=False)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `flatten` | `bool` | `True` | Si `True`, aplatit chaque enregistrement avant conversion |

Accepte les réponses JSON de type `dict` (un seul enregistrement) ou `list`
(liste d'enregistrements).

**Retour :** `pd.DataFrame`
**Exceptions :** `ConnectError`, `ReadError`

### `write(data, orient='records')`

```python
source.write(df)
source.write(df, orient="index")
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `data` | `pd.DataFrame` | - | Données à écrire |
| `orient` | `str` | `'records'` | Orientation JSON : `'records'`, `'index'`, `'columns'`, `'values'` |

Écrit avec `force_ascii=False` et `indent=2`.

**Exception :** `WriteError` si la source est un dictionnaire en mémoire
(aucun fichier de destination).

**Retour :** `bool`

### `info()`

```python
print(source.info())
# {
#   'path': 'donnees_fao.json',
#   'kind': 'json',
#   'is_file': True,
#   'size_kb': 8.45,
#   'last_read': None
# }
```

### `ping()`

Pour une source fichier : vérifie l'existence et la lisibilité du fichier.
Pour une source dict : retourne toujours `True`. Retourne `bool`.

---

## `NetCDFSource`

Source pour les fichiers NetCDF agrométéorologiques (`.nc`), utilisés pour les
données CHIRPS (précipitations), TAMSAT (Afrique) et GFS (prévisions globales).
Utilise xarray comme moteur de lecture et supporte le chunking Dask pour les
grands fichiers.

> Dépendance : `xarray` et `netCDF4` doivent être installés.

### Initialisation

```python
from kadi.kidas import NetCDFSource

source = NetCDFSource("chirps_benin_2024.nc")

# Avec Dask pour les fichiers volumineux (> 500 Mo)
source = NetCDFSource("gfs_global_2024.nc", use_dask=True)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `path` | `str` | - | Chemin vers le fichier NetCDF |
| `use_dask` | `bool` | `False` | Active le chargement paresseux via Dask |

### `dims()`

Retourne les dimensions du dataset.

```python
dimensions = source.dims()
# {'lat': 240, 'lon': 360, 'time': 365}
```

**Retour :** `dict[str, int]`

### `read(lat_bounds=None, lon_bounds=None, time_bounds=None)`

Extrait un sous-ensemble spatial et temporel du fichier. Si aucune bounding
box n'est spécifiée, utilise par défaut la bbox du Bénin
(`lat∈[2.5, 12.5]`, `lon∈[-1.5, 4.0]`).

```python
# Extraction avec la bbox Bénin par défaut
da = source.read()

# Extraction sur une région personnalisée
da = source.read(
    lat_bounds=(6.0, 12.5),
    lon_bounds=(1.0, 4.0),
    time_bounds=("2024-01-01", "2024-06-30"),
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lat_bounds` | `tuple[float, float]` ou `None` | bbox Bénin | Intervalle de latitude `(lat_min, lat_max)` |
| `lon_bounds` | `tuple[float, float]` ou `None` | bbox Bénin | Intervalle de longitude `(lon_min, lon_max)` |
| `time_bounds` | `tuple[str, str]` ou `None` | `None` | Intervalle temporel au format ISO `('YYYY-MM-DD', 'YYYY-MM-DD')` |

Détecte automatiquement les noms de dimensions lat/lon dans le dataset
(compatibles avec `'lat'`, `'latitude'`, `'y'`, etc.). Lit la première
variable de données si le dataset en contient plusieurs.

**Retour :** `xr.DataArray`
**Exceptions :** `ConnectError`, `ReadError`

### `to_df()`

Convertit le dernier `DataArray` extrait par `read()` en `pd.DataFrame`.
Si `read()` n'a pas encore été appelé, effectue une lecture avec la bbox Bénin.

```python
da = source.read()
df = source.to_df()
# Colonnes : lat, lon, time, <nom_variable>
```

**Retour :** `pd.DataFrame`
**Exception :** `ReadError`

### `write(data)`

Convertit le DataFrame en `xr.Dataset` via `from_dataframe()` et le sauvegarde
au format NetCDF.

**Retour :** `bool`
**Exception :** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'path': 'chirps_benin_2024.nc',
#   'kind': 'netcdf',
#   'dimensions': {'lat': 240, 'lon': 360, 'time': 365},
#   'variables': ['precip'],
#   'use_dask': False,
#   'size_kb': 45230.0,
#   'last_read': None
# }
```

### `ping()`

Vérifie que le fichier existe et est lisible en lecture. Retourne `bool`.

---

## `APISource`

Source pour les APIs REST agricoles et climatiques (Open-Meteo, WFP VAM,
FAO, SoilGrids). Intègre le rate limiting et un mécanisme de réessai avec
backoff exponentiel.

### Initialisation

```python
from kadi.kidas import APISource

# API publique
source = APISource("https://api.open-meteo.com/v1/forecast")

# API authentifiée avec limite de débit personnalisée
source = APISource(
    "https://api.wfp.org/vam-data-bridges/1.0",
    token="mon_token_bearer",
    rate_limit=2.0,
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `url` | `str` | - | URL de base de l'endpoint API |
| `token` | `str` ou `None` | `None` | Jeton Bearer pour les APIs authentifiées |
| `rate_limit` | `float` | `5.0` | Nombre maximum de requêtes par seconde |

### `fetch(params, retries=3, backoff=5.0)`

Effectue une requête GET avec réessais et backoff exponentiel.

```python
donnees = source.fetch(
    params={"latitude": 6.36, "longitude": 2.42},
    retries=3,
    backoff=5.0,
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `params` | `dict` | - | Paramètres de la requête GET (query string) |
| `retries` | `int` | `3` | Nombre maximum de tentatives en cas d'échec |
| `backoff` | `float` | `5.0` | Délai de base en secondes entre les réessais (doublé à chaque tentative, plafonné à 60 s) |

Les codes HTTP réessayables sont : `429`, `500`, `502`, `503`, `504`.

**Retour :** `dict` (réponse JSON parsée)
**Exceptions :** `ConnectError` si l'API est inaccessible, `ReadError`
si la réponse n'est pas un JSON valide.

### `read(params=None)`

Effectue une requête GET et normalise la réponse en DataFrame.

```python
df = source.read({
    "latitude": 6.36,
    "longitude": 2.42,
    "daily": "temperature_2m_max",
})
```

Cherche automatiquement une clé standard dans la réponse dict (`'data'`,
`'results'`, `'items'`, `'records'`, `'features'`). Si aucune n'est trouvée,
utilise le dict entier comme unique enregistrement.

**Retour :** `pd.DataFrame`
**Exceptions :** `ConnectError`, `ReadError`

### `write(data)`

Envoie le DataFrame vers l'API via une requête POST au format JSON
(`orient='records'`).

**Retour :** `bool`
**Exception :** `WriteError`

### `info()`

```python
print(source.info())
# {
#   'url': 'https://api.open-meteo.com/v1/forecast',
#   'kind': 'api',
#   'requires_auth': False,
#   'rate_limit': 5.0,
#   'last_read': None
# }
```

### `ping()`

Effectue une requête HEAD légère. Retourne `True` si le code de réponse
est inférieur à 500 (l'API répond, même avec une erreur 4xx). Retourne
`False` si la connexion échoue complètement.

---

## Exemple complet

```python
import kadi as kd
from kadi.kidas import CSVSource, ExcelSource, JSONSource, NetCDFSource, APISource

# CSV avec détection automatique
source_csv = CSVSource("recoltes_2024.csv")
if source_csv.ping():
    df = source_csv.read()
    print(source_csv.info())

# Excel multi-feuilles
source_excel = ExcelSource("prix_marches.xlsx")
for feuille in source_excel.sheets():
    df = source_excel.read(sheet=feuille)
    print(f"{feuille} : {len(df)} lignes")

# JSON imbriqué
source_json = JSONSource("donnees_fao.json")
df = source_json.read(flatten=True)

# NetCDF agrométéo
source_nc = NetCDFSource("chirps_benin_2024.nc")
da = source_nc.read(lat_bounds=(2.5, 12.5), lon_bounds=(-1.5, 4.0))
df = source_nc.to_df()

# API REST
source_api = APISource("https://api.open-meteo.com/v1/forecast")
df = source_api.read({
    "latitude": 6.36,
    "longitude": 2.42,
    "daily": "temperature_2m_max",
})
```

---

## Rétrocompatibilité

Les anciens noms de classes émettent un `DeprecationWarning` et continuent
de fonctionner jusqu'à KadiPy v2.0 :

| Ancien nom (avant v1.2.0) | Nouveau nom |
|---------------------------|-------------|
| `DataSource` | `Source` |
| `CSVDataSource` | `CSVSource` |
| `ExcelDataSource` | `ExcelSource` |
| `JSONDataSource` | `JSONSource` |
| `NetCDFDataSource` | `NetCDFSource` |
| `APIDataSource` | `APISource` |

---

::: kadi.kidas.sources.base.Source
::: kadi.kidas.sources.csv_source.CSVSource
::: kadi.kidas.sources.excel_source.ExcelSource
::: kadi.kidas.sources.json_source.JSONSource
::: kadi.kidas.sources.netcdf_source.NetCDFSource
::: kadi.kidas.sources.api_source.APISource
