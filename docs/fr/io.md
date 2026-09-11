# kadi.io : Entrées et sorties

Le module `kadi.io` est le point d'entrée pour toutes les opérations de lecture
et d'écriture de données dans KadiPy. Il couvre les fichiers locaux (CSV, Excel,
JSON, NetCDF) et les APIs REST, avec une détection automatique du format selon
l'extension ou l'URL.

Les classes sources (`CSVSource`, `ExcelSource`, etc.) sont définies dans
`kadi.kidas.sources` et réexportées ici pour un accès direct. Les fonctions
`read_*` et `write_*` sont des raccourcis qui instancient ces classes et
appellent leur méthode `read()` ou `write()` immédiatement.

---

## Démarrage rapide

```python
import kadi as kd

# Lecture
df = kd.read_csv("recoltes_2024.csv")
df = kd.read_excel("prix_marche.xlsx")
df = kd.read_json("campagne_2023.json")
df = kd.read_api("https://api.data.bj/agriculture/prices")

# Écriture
kd.write_csv(df, "export.csv")
kd.write(df, "export.xlsx")       # Détection automatique du format

# Inspection
kd.info("recoltes_2024.csv")      # Métadonnées sans charger le fichier
kd.ping("recoltes_2024.csv")      # Vérifie si la source est accessible
```

---

## Fonctions de lecture

Ces fonctions lisent les données depuis une source et retournent un
`pandas.DataFrame`. Chaque fonction accepte des arguments optionnels transmis
à la classe source sous-jacente.

### `read_csv(filepath, **kwargs)`

Lit un fichier CSV. Détecte automatiquement l'encodage (via `chardet`), le
délimiteur (`,`, `;`, tabulation, `|`) et le séparateur décimal.

```python
import kadi as kd

df = kd.read_csv("recoltes_2024.csv")

# Forcer les paramètres si la détection automatique ne suffit pas
from kadi.io import CSVSource
df = CSVSource("export.csv", sep=";", decimal=",", encoding="latin-1").read()
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `filepath` | `str` ou `Path` | requis | Chemin vers le fichier CSV |
| `encoding` | `str` | `'auto'` | Encodage du fichier (`'utf-8'`, `'latin-1'`, etc.) |
| `sep` | `str` | `'auto'` | Délimiteur de colonnes |
| `decimal` | `str` | `'auto'` | Séparateur décimal |
| `n` | `int` | `None` | Nombre maximum de lignes à lire |
| `skip` | `int` | `None` | Nombre de lignes à ignorer en début de fichier |

**Retour :** `pandas.DataFrame`

**Exceptions :** `ConnectError` si le fichier est introuvable, `ReadError`
si la lecture échoue malgré les tentatives avec plusieurs encodages.

---

### `read_excel(filepath, **kwargs)`

Lit un fichier Excel (`.xlsx` ou `.xls`).

```python
df = kd.read_excel("prix_marche.xlsx")

# Lire une feuille spécifique
from kadi.io import ExcelSource
df = ExcelSource("rapport.xlsx", sheet="Parakou").read()
```

**Retour :** `pandas.DataFrame`

---

### `read_json(filepath, **kwargs)`

Lit un fichier JSON.

```python
df = kd.read_json("campagne_2023.json")
```

**Retour :** `pandas.DataFrame`

---

### `read_netcdf(filepath, **kwargs)`

Lit un fichier NetCDF (`.nc`, `.netcdf`). Nécessite les dépendances optionnelles
`xarray` et `netCDF4`.

```python
df = kd.read_netcdf("chirps_2024.nc")
```

**Retour :** `xarray.Dataset` ou `pandas.DataFrame` selon les options passées.

**Exception :** `ImportError` si `xarray` ou `netCDF4` n'est pas installé.

```bash
# Installation des dépendances
pip install "kadipy[geospatial]"
```

---

### `read_api(url, params=None, **kwargs)`

Lit des données depuis une API REST via une requête GET.

```python
df = kd.read_api("https://api.data.bj/agriculture/prices")

# Avec des paramètres de requête
df = kd.read_api(
    "https://api.data.bj/agriculture/prices",
    params={"crop": "maize", "region": "parakou"},
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `url` | `str` | requis | URL de l'API REST |
| `params` | `dict` | `None` | Paramètres de requête HTTP |

**Retour :** `pandas.DataFrame`

---

## Fonctions d'écriture ciblées

Ces fonctions écrivent un `pandas.DataFrame` vers un fichier ou une API.
Elles retournent toutes `True` si l'écriture réussit.

### `write_csv(data, filepath, **kwargs)`

```python
kd.write_csv(df, "export.csv")
```

Utilise le délimiteur et l'encodage détectés lors de la lecture si la source
a été lue au préalable, ou `,` / `utf-8` par défaut.

---

### `write_excel(data, filepath, **kwargs)`

```python
kd.write_excel(df, "export.xlsx")
```

---

### `write_json(data, filepath, **kwargs)`

```python
kd.write_json(df, "export.json")
```

---

### `write_netcdf(data, filepath, **kwargs)`

```python
kd.write_netcdf(df, "export.nc")
```

Même dépendance optionnelle que `read_netcdf`.

---

### `write_api(data, url, **kwargs)`

Envoie un DataFrame vers un endpoint d'API REST.

```python
kd.write_api(df, "https://api.monservice.bj/upload")
```

---

## Fonctions génériques

Ces trois fonctions acceptent n'importe quel format et détectent
automatiquement la source à utiliser selon l'extension du fichier ou le
préfixe de l'URL.

### Table de détection automatique

| Extension ou préfixe | Classe utilisée |
|----------------------|-----------------|
| `.csv` | `CSVSource` |
| `.xlsx`, `.xls` | `ExcelSource` |
| `.json` | `JSONSource` |
| `.nc`, `.netcdf` | `NetCDFSource` |
| `http://`, `https://` | `APISource` |
| Autre | `ValueError` |

---

### `write(data, filepath_or_url, **kwargs)`

Écrit un DataFrame avec détection automatique du format.

```python
kd.write(df, "export.csv")
kd.write(df, "export.xlsx")
kd.write(df, "https://api.monservice.bj/upload")
```

---

### `info(filepath_or_url, **kwargs)`

Retourne les métadonnées d'une source sans charger toutes les données en
mémoire.

```python
meta = kd.info("recoltes_2024.csv")
print(meta)
# {
#   'path': 'recoltes_2024.csv',
#   'kind': 'csv',
#   'encoding': 'utf-8',
#   'sep': ',',
#   'decimal': '.',
#   'rows': 1240,
#   'cols': 8,
#   'size_kb': 42.5,
#   'last_read': None
# }
```

**Retour :** `dict` contenant les métadonnées de la source.

Les clés retournées varient selon le type de source :

| Clé | Description |
|-----|-------------|
| `path` | Chemin ou URL de la source |
| `kind` | Type de source : `'csv'`, `'excel'`, `'json'`, `'netcdf'`, `'api'` |
| `encoding` | Encodage détecté ou configuré |
| `rows` | Nombre de lignes de données |
| `cols` | Nombre de colonnes |
| `size_kb` | Taille du fichier en kilo-octets (fichiers locaux uniquement) |
| `last_read` | Horodatage ISO de la dernière lecture, ou `None` |

---

### `ping(filepath_or_url, **kwargs)`

Vérifie qu'une source est accessible sans la lire.

```python
if kd.ping("recoltes_2024.csv"):
    df = kd.read_csv("recoltes_2024.csv")

# Pour une API
if kd.ping("https://api.data.bj/agriculture/prices"):
    df = kd.read_api("https://api.data.bj/agriculture/prices")
```

**Retour :** `True` si la source est accessible, `False` sinon.

Pour les fichiers locaux, vérifie que le fichier existe et est lisible.
Pour les APIs, vérifie que l'endpoint répond sans erreur HTTP.

---

## Accès aux classes sources

Les classes `Source`, `CSVSource`, `ExcelSource`, `JSONSource`,
`NetCDFSource` et `APISource` sont disponibles directement depuis `kadi.io`
pour une utilisation avancée.

```python
from kadi.io import CSVSource

source = CSVSource("recoltes.csv", sep=";", decimal=",")
df     = source.read(n=100)    # Lire les 100 premières lignes
meta   = source.info()         # Métadonnées
ok     = source.ping()         # Test d'accessibilité
source.write(df, "copie.csv") # Réécriture
```

Les classes sources sont des implémentations de la classe abstraite `Source`,
qui définit le contrat commun : `read()`, `write()`, `info()`, `ping()`.

Pour la documentation complète de chaque classe source, voir
[kadi.kidas : Sources de données](kidas/sources.md).

---

## Accès depuis le niveau racine

Toutes les fonctions et classes de `kadi.io` sont réexportées depuis `kadi`
pour un accès direct :

```python
import kadi as kd

# Équivalent à from kadi.io import ...
kd.read_csv(...)
kd.write(...)
kd.info(...)
kd.ping(...)
kd.CSVSource(...)
```

---

::: kadi.io
