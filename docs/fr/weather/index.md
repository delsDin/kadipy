# Module weather (`kadi.weather`)

Le module `kadi.weather` fournit une interface unifiée pour acquérir, mettre
en cache et exploiter des données météorologiques agricoles. Il est conçu pour
le contexte béninois et s'appuie sur deux sources de données complémentaires :
Open-Meteo pour les prévisions et les températures, CHIRPS pour les
précipitations historiques.

Le point d'entrée principal est la façade `Weather`, qui initialise chaque
composant interne à la demande (chargement paresseux).

---

## Architecture

```
kadi.weather
├── Weather          - Façade principale (session.py)
├── Location         - Localisation GPS et zone agro-climatique (location.py)
├── WeatherLoader    - Acquisition et cache des données brutes (data.py)
├── Phenology        - Saisons, GDD, onset/cessation (phenology.py)
├── Hydrology        - Bilan hydrique, ET0 FAO-56 (hydrology.py)
└── Risk             - SPI, Markov, probabilité de pluie (risk.py)
```

Les composants `Phenology`, `Hydrology` et `Risk` ne sont instanciés que
lorsqu'une méthode les utilisant est appelée pour la première fois.

---

## Sources de données

| Source | Usage | Disponibilité |
|--------|-------|---------------|
| Open-Meteo | Prévisions (jusqu'à 16 jours) et températures historiques | API gratuite |
| CHIRPS | Précipitations historiques longues (depuis 1981, décalage ~15 jours) | API CHC |
| Cache SQLite | Stockage local et repli hors-ligne | `~/.kadi/cache.db` |

La source de précipitation pour les données historiques est configurable via
le paramètre `source` de `historical()` : `'openmeteo'`, `'chirps'` ou
`'both'`. Si `source` n'est pas fourni, la valeur définie dans `CONFIG` est
utilisée.

En mode `'both'`, CHIRPS couvre la période historique et Open-Meteo complète
les dates récentes non encore disponibles dans CHIRPS. La colonne `data_source`
du cache SQLite conserve la provenance de chaque observation.

---

## Zones agro-climatiques

La zone est détectée automatiquement à partir de la latitude par `Location`.

| Zone | Latitude | Régime pluviométrique |
|------|----------|-----------------------|
| `'Sud'` | `lat < 7.5` | Bimodal (deux saisons des pluies) |
| `'Centre'` | `7.5 <= lat < 9.0` | Bimodal |
| `'Nord'` | `lat >= 9.0` | Unimodal (une saison des pluies) |

La zone est stockée dans l'attribut `location.zone` et le régime dans
`location.regime`.

---

## Import

```python
import kadi as kd

# Façade principale
weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")

# Accès direct aux classes si nécessaire
from kadi.weather import Location, WeatherLoader
```

---

## `Weather` (façade principale)

### Initialisation

```python
weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")
```

| Paramètre | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| `lat` | `float` | Oui | Latitude en degrés décimaux |
| `lon` | `float` | Oui | Longitude en degrés décimaux |
| `name` | `str` | Non | Nom de la localité |
| `cache` | `str` | Non | Répertoire de cache (conservé pour la compatibilité de signature) |

`lat` et `lon` sont obligatoires : une `TypeError` est levée si l'un d'eux
est absent.

**Attributs instanciés à l'initialisation :**

| Attribut | Type | Description |
|----------|------|-------------|
| `location` | `Location` | Localisation associée |
| `cache` | `str` ou `None` | Répertoire de cache (paramètre conservé) |
| `loader` | `WeatherLoader` | Gestionnaire de données météo |
| `phenology` | `Phenology` ou `None` | Initialisé à la demande |
| `hydrology` | `Hydrology` ou `None` | Initialisé à la demande |
| `risk` | `Risk` ou `None` | Initialisé à la demande |

### `forecast(days=None)`

Récupère la prévision météorologique court-terme depuis Open-Meteo (ou le
cache si disponible et valide).

```python
prevision = weather.forecast(days=7)

print(prevision["location"]["name"])
for jour in prevision["data"]:
    print(jour["date"], jour["precipitation"])
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `days` | `int` ou `None` | Valeur de `CONFIG["weather"]["forecast_days_default"]` | Nombre de jours de prévision |

Le nombre de jours est plafonné à `CONFIG["weather"]["max_forecast_days"]`.

**Retour :** `dict` avec les clés :
- `'location'` : `dict` avec `'name'`, `'lat'`, `'lon'`
- `'data'` : liste de dicts (un par jour)
- `'source'` : source des données (`'open-meteo'` ou `'cached'`)
- `'last_updated'` : horodatage ISO de la réponse

### `historical(metric='all', months=120, source=None, months_back=None)`

Retourne les séries historiques météorologiques sous forme de DataFrame.

```python
# 24 mois, toutes les colonnes
df = weather.historical(months=24)

# Uniquement les précipitations
df_pluie = weather.historical(metric="precipitation", months=12)

# Forcer CHIRPS pour les précipitations
df_chirps = weather.historical(months=36, source="chirps")
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `metric` | `str` | `'all'` | Filtre de colonnes : `'temperature'`, `'precipitation'`, `'humidity'` ou `'all'` |
| `months` | `int` | `120` | Nombre de mois d'historique |
| `source` | `str` ou `None` | Valeur de `CONFIG` | Source de précipitation : `'chirps'`, `'openmeteo'` ou `'both'` |
| `months_back` | `int` ou `None` | `None` | Ancien nom de `months` (déprécié) |

**Retour :** `pd.DataFrame` avec `DatetimeIndex`.

### `gdd(crop, start, end=None)`

Calcule l'accumulation des degrés-jours de croissance (GDD) depuis la date de
semis jusqu'à `end` (ou aujourd'hui si non fournie).

```python
resultat = weather.gdd(crop="maize", start="2026-05-15")
print(resultat["gdd_accumulated"])
print(resultat["phenology_stage"])
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `crop` | `str` | Culture cible (`'maize'`, `'rice'`, etc.) |
| `start` | `str` ou `pd.Timestamp` | Date de semis (format `YYYY-MM-DD`) |
| `end` | `str`, `pd.Timestamp` ou `None` | Date de fin. `None` : aujourd'hui |

**Retour :** `dict` (voir la documentation de [Phenology](phenology.md)).

### `onset()`

Détecte la date de démarrage de la saison agricole selon le régime climatique
de la zone.

```python
debut = weather.onset()
print(debut["onset_date"])
print(debut["method"])
```

**Retour :** `dict` (voir [Phenology](phenology.md)).

### `cessation()`

Détermine la date de fin des pluies utiles.

```python
fin = weather.cessation()
print(fin["cessation_date"])
```

**Retour :** `dict` (voir [Phenology](phenology.md)).

### `drought(method='spi', window=3, window_months=None)`

Calcule l'indice de sécheresse pour la localisation.

```python
sec = weather.drought(method="spi", window=3)
print(sec["spi_3month"])
print(sec["drought_severity"])
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `method` | `str` | `'spi'` | Méthode de calcul : `'spi'`, `'markov'`, `'hurst'`, `'combined'` |
| `window` | `int` | `3` | Fenêtre temporelle en mois |
| `window_months` | `int` ou `None` | `None` | Ancien nom de `window` (déprécié) |

**Retour :** `dict` (voir [Risk](risk.md)).

### `rain_prob(days=1, min_mm=1.0, days_ahead=None, min_rainfall_mm=None)`

Prévoit la probabilité de pluie sur les `days` prochains jours.

```python
prob = weather.rain_prob(days=3, min_mm=1.0)
print(prob["tomorrow"])          # probabilité demain (float entre 0 et 1)
print(prob["recommendation"])    # recommandation agronomique
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `days` | `int` | `1` | Nombre de jours futurs |
| `min_mm` | `float` | `1.0` | Seuil minimum de pluie en mm |
| `days_ahead` | `int` ou `None` | `None` | Ancien nom de `days` (déprécié) |
| `min_rainfall_mm` | `float` ou `None` | `None` | Ancien nom de `min_mm` (déprécié) |

**Retour :** `dict` (voir [Risk](risk.md)).

### `water_balance(crop='maize', soil_type='ferrugineux')`

Simule le bilan hydrique quotidien selon la méthode FAO-56.

```python
bilan = weather.water_balance(crop="maize", soil_type="ferrugineux")
print(bilan[["precipitation", "ET0", "deficit_eau", "reserve_utile"]].tail(14))
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `crop` | `str` | `'maize'` | Type de culture |
| `soil_type` | `str` | `'ferrugineux'` | Type de sol |

**Retour :** `pd.DataFrame` (voir [Hydrology](hydrology.md)).

### `et0_hargreaves(tmin, tmax, day_of_year)`

Calcule l'évapotranspiration de référence (ET0) par la méthode
Hargreaves-Samani.

```python
eto = weather.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=180)
print(f"ET0 : {eto:.2f} mm/jour")
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `tmin` | `float` | Température minimale en degC |
| `tmax` | `float` | Température maximale en degC |
| `day_of_year` | `int` | Jour de l'année (1 à 365) |

**Retour :** `float` (ET0 en mm/jour).

---

## `Location`

Représente une position géographique au Bénin avec détection automatique
de la zone et du régime climatique.

### Initialisation

```python
from kadi.weather import Location

loc = Location(lat=9.3333, lon=2.6333, name="Parakou")
print(loc.zone)    # 'Nord'
print(loc.regime)  # 'unimodal'
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `lat` | `float` | Latitude en degrés décimaux |
| `lon` | `float` | Longitude en degrés décimaux |
| `name` | `str` | Nom de la localité (optionnel) |

Les coordonnées sont validées par rapport à la bounding box Bénin définie
dans `CONFIG["weather"]["gps_validation_bbox"]`. Une `LocationError` est levée
si les coordonnées sont en dehors de cette zone.

Si `name` n'est pas fourni, l'attribut vaut `'Point(lat, lon)'`.

**Attributs :**

| Attribut | Type | Description |
|----------|------|-------------|
| `lat` | `float` | Latitude |
| `lon` | `float` | Longitude |
| `name` | `str` | Nom de la localité |
| `zone` | `str` | Zone détectée : `'Sud'`, `'Centre'` ou `'Nord'` |
| `regime` | `str` | Régime détecté : `'bimodal'` ou `'unimodal'` |

### `climate()`

Retourne les paramètres climatiques par défaut pour la zone.

```python
params = loc.climate()
# {'Tbase': 10, 'onset_method': 'sivakumar'}
```

**Retour :** `dict` avec les clés `'Tbase'` et `'onset_method'`.

| Zone | `onset_method` |
|------|----------------|
| `'Sud'` | `'walter_anyadike'` |
| `'Centre'` | `'hybrid'` |
| `'Nord'` | `'sivakumar'` |

### `to_dict()`

Sérialise la localisation pour le cache.

```python
loc.to_dict()
# {'name': 'Parakou', 'lat': 9.3333, 'lon': 2.6333, 'zone': 'Nord', 'regime': 'unimodal'}
```

**Retour :** `dict`.

---

## `WeatherLoader`

Gère l'acquisition des données depuis les APIs, leur normalisation et leur
stockage dans le cache SQLite KadiPy (`~/.kadi/cache.db`).

En pratique, `WeatherLoader` est utilisé en interne par `Weather` via
`weather.loader`. Il est rarement instancié directement.

### Initialisation

```python
from kadi.weather import Location, WeatherLoader

loc = Location(lat=9.3333, lon=2.6333)
loader = WeatherLoader(loc)
```

`cache` est optionnel. Si fourni, il désigne le répertoire de cache passé par
la façade `Weather`. En pratique, `WeatherLoader` est instancié automatiquement
par `Weather` et rarement utilisé directement.

**Attributs :**

| Attribut | Type | Description |
|----------|------|-------------|
| `location` | `Location` | Localisation associée |
| `forecast` | `pd.DataFrame` ou `None` | Prévisions en mémoire |
| `historical` | `pd.DataFrame` ou `None` | Historique en mémoire |
| `source` | `str` | Source des dernières données chargées |

### `get_forecast(days=7, refresh=False)`

Récupère les prévisions en vérifiant d'abord le cache SQLite.

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `days` | `int` | `7` | Nombre de jours de prévision |
| `refresh` | `bool` | `False` | Si `True`, ignore le cache et force le rechargement |

La TTL du cache pour les prévisions est définie par
`CONFIG["weather"]["cache_ttl_forecast_hours"]`. En cas d'échec API, le cache
est utilisé si disponible, sinon une `OfflineError` est levée.

**Retour :** `pd.DataFrame` indexé par date.

### `get_historical(months=120, refresh=False, source=None)`

Récupère l'historique météo en combinant CHIRPS et Open-Meteo selon `source`.

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `months` | `int` | `120` | Nombre de mois d'historique |
| `refresh` | `bool` | `False` | Si `True`, ignore le cache |
| `source` | `str` ou `None` | Valeur de `CONFIG` | `'chirps'`, `'openmeteo'` ou `'both'` |

Tolérance de 5 jours sur le nombre de lignes avant de considérer le cache
incomplet. La TTL du cache est définie par
`CONFIG["weather"]["cache_ttl_historical_days"]`.

**Retour :** `pd.DataFrame` indexé par date.

### Normalisation des données

`WeatherLoader` normalise automatiquement chaque DataFrame via `_normalize()` :

1. Conversion de la colonne `'date'` en `DatetimeIndex`.
2. Filtrage des températures aberrantes (hors `[-5, 55] degC`).
3. Remise à zéro des précipitations négatives.
4. Calcul de la colonne `'data_quality'` (proportion de colonnes critiques
   renseignées).
5. Interpolation linéaire sur les lacunes courtes (maximum 3 jours).
6. Remplissage résiduel des précipitations manquantes à `0.0`.
7. Garantie de la colonne `'temperature_mean'` via `_unify_temp()` :
   calculée par `(temperature_min + temperature_max) / 2`, ou aliasée depuis
   `temperature_avg` si les colonnes de base sont absentes.

---

## Cache hors-ligne

Toutes les données téléchargées sont stockées dans la base SQLite KadiPy
(`~/.kadi/cache.db`, table `weather_data`). Si le réseau est indisponible,
le module utilise automatiquement les données en cache sans lever d'erreur
(sauf si le cache est vide, auquel cas une `OfflineError` est levée).

La colonne `data_source` du cache conserve la provenance de chaque
observation : `'chirps'`, `'open-meteo'`, ou une combinaison des deux.

---

## Exemple complet

```python
import kadi as kd

# Initialisation pour Cotonou (Sud, régime bimodal)
weather = kd.Weather(lat=6.3654, lon=2.4183, name="Cotonou")

# Prévisions sur 5 jours
prevision = weather.forecast(days=5)
for jour in prevision["data"]:
    print(jour["date"], jour["precipitation"], jour["temperature_min"])

# 12 mois d'historique (source hybride par défaut)
df = weather.historical(months=12)
print(df.columns.tolist())

# Démarrage de la saison
debut = weather.onset()
print(debut["onset_date"], debut["method"])

# GDD pour le maïs
gdd = weather.gdd(crop="maize", start="2026-05-15")
print(gdd["gdd_accumulated"], gdd["phenology_stage"])

# Bilan hydrique
bilan = weather.water_balance(crop="maize", soil_type="ferrugineux")
print(bilan[["precipitation", "ET0", "deficit_eau"]].tail(7))

# Sécheresse SPI-3
sec = weather.drought(method="spi", window=3)
print(sec["spi_3month"], sec["drought_severity"])

# Probabilité de pluie demain
prob = weather.rain_prob(days=1, min_mm=1.0)
print(prob["tomorrow"], prob["recommendation"])
```

---

## Rétrocompatibilité

Les anciens noms de classes et de paramètres émettent un `DeprecationWarning`
et continuent de fonctionner jusqu'à KadiPy v2.0.

**Classes :**

| Ancien nom | Nouveau nom |
|------------|-------------|
| `WeatherSession` | `Weather` |
| `WeatherData` | `WeatherLoader` |
| `RiskIndicators` | `Risk` |

**Paramètres de `Weather.__init__()` :**

| Ancien paramètre | Nouveau paramètre |
|------------------|-------------------|
| `latitude` | `lat` |
| `longitude` | `lon` |
| `cache_dir` | `cache` |

**Méthodes de `Weather` :**

| Ancienne méthode | Nouvelle méthode |
|------------------|-----------------|
| `growing_degree_days(crop, start_date, end_date)` | `gdd(crop, start, end)` |
| `drought_index(method, window_months)` | `drought(method, window)` |
| `rain_probability(days_ahead, min_rainfall_mm)` | `rain_prob(days, min_mm)` |

**Attributs de `Weather` :**

| Ancien attribut | Nouvel attribut |
|-----------------|-----------------|
| `cache_dir` | `cache` |
| `weather_data` | `loader` |
| `risk_indicators` | `risk` |

**Paramètres de `Weather.historical()` :**

| Ancien paramètre | Nouveau paramètre |
|------------------|-------------------|
| `months_back` | `months` |

---

## Sous-modules

- [Phénologie](phenology.md) : onset, cessation, GDD
- [Hydrologie](hydrology.md) : bilan hydrique, ET0
- [Risques climatiques](risk.md) : SPI, Markov, probabilité de pluie

::: kadi.weather.session.Weather
::: kadi.weather.location.Location
::: kadi.weather.data.WeatherLoader
