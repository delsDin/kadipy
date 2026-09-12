# Hydrologie (`kadi.weather.hydrology`)

La classe `Hydrology` modélise le bilan hydrique du sol pour une parcelle
agricole. Elle calcule l'évapotranspiration de référence (ET0), le
ruissellement journalier (SCS-CN) et le bilan hydrique complet selon
la norme FAO-56.

Elle est utilisée en interne par la façade `Weather`, mais peut aussi être
instanciée directement pour des analyses spécifiques.

---

## Importation directe

```python
from kadi.weather import Hydrology
```

---

## Initialisation

Dans le cas courant, `Hydrology` est créée automatiquement par la façade
`Weather` lors du premier appel à `water_balance()` ou `et0_hargreaves()`.
Elle est alors accessible via `weather.hydrology`.

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Hydrology chargée à la demande
bilan = weather.water_balance(crop="maize", soil_type="ferrugineux")
hydrology = weather.hydrology   # Instance disponible
```

Pour une instanciation directe :

```python
from kadi.weather import Hydrology, Location
import pandas as pd

location = Location(lat=9.3, lon=2.3, name="Parakou")

# rainfall    : pd.Series journalière de précipitations, indexée par date
# temperature : pd.DataFrame avec colonnes 'temperature_min' et 'temperature_max'

hydrology = Hydrology(
    location,
    rainfall,
    temperature,
    soil_type="ferrugineux",
    crop="maize",
)
```

**Attributs publics :**

| Attribut | Type | Description |
|----------|------|-------------|
| `location` | `Location` | Localisation de la parcelle |
| `rainfall` | `pd.Series` | Série de précipitations quotidiennes |
| `temperature` | `pd.DataFrame` | Données de température (`temperature_min`, `temperature_max`) |
| `crop` | `str` | Type de culture |
| `soil_type` | `str` | Type de sol |
| `soil` | `dict` | Paramètres physiques du sol |
| `balance` | `pd.DataFrame` | Résultat du bilan hydrique (`None` avant calcul) |

---

## Méthodes

### `water_balance()`

Simule le bilan hydrique quotidien du sol selon la méthode FAO-56.

Le calcul comprend :

1. ET0 journalier par Hargreaves-Samani.
2. Ruissellement par la méthode SCS-CN avec ajustement AMC (Antecedent
   Moisture Condition) sur les 5 jours précédents.
3. Évapotranspiration de la culture (ETc = ET0 x Kc).
4. Bilan séquentiel : pluie efficace - ETc, plafonné à TAW (Total
   Available Water).

```python
bilan = weather.water_balance(crop="maize", soil_type="ferrugineux")

# Derniers 7 jours
print(bilan.tail(7)[[
    "precip", "et0", "pluie_eff",
    "evapotransp", "deficit_eau", "reserve_utile", "stress_hydrique_index"
]])
```

Ce calcul est déclenché via la façade `Weather`. Pour l'appeler directement
sur l'instance `Hydrology` (par exemple après avoir modifié la culture) :

```python
# Modification de la culture et du sol
weather.hydrology.crop = "rice"
weather.hydrology.soil_type = "ferrallitique"
weather.hydrology.soil = weather.hydrology.soil_params("ferrallitique")

# Recalcul
bilan = weather.hydrology.water_balance()
```

**Retour :** `pd.DataFrame` avec `DatetimeIndex`.

**Colonnes :**

| Colonne | Description |
|---------|-------------|
| `precip` | Précipitations observées (mm) |
| `et0` | ET0 par Hargreaves-Samani (mm/jour) |
| `pluie_eff` | Pluie efficace après déduction du ruissellement (mm) |
| `evapotransp` | ETc = ET0 x Kc de la culture (mm/jour) |
| `deficit_eau` | Déficit hydrique journalier dans le sol (mm) |
| `reserve_utile` | Eau disponible dans le sol = TAW - déficit (mm) |
| `stress_hydrique_index` | Indice de stress hydrique = déficit / TAW (0 a 1) |

**Exceptions :**

- `DataError` : données de précipitation ou de température manquantes.

---

### `et0_hargreaves(tmin, tmax, day_of_year)`

Calcule l'évapotranspiration de référence (ET0) par la méthode
Hargreaves-Samani. Alternative à Penman-Monteith lorsque les données
d'humidité, de vent et de rayonnement solaire sont indisponibles.

```python
# Calcul pour un jour donné
et0 = weather.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=180)
print(f"ET0 : {et0:.2f} mm/jour")

# Appel direct sur l'instance Hydrology (accepte aussi des arrays numpy)
import numpy as np
tmin_arr = np.array([20.0, 21.0, 19.0])
tmax_arr = np.array([33.0, 35.0, 32.0])
doy_arr  = np.array([150, 151, 152])
et0_arr = weather.hydrology.et0_hargreaves(tmin_arr, tmax_arr, doy_arr)
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `tmin` | `float` ou `np.ndarray` | Température minimale (degC) |
| `tmax` | `float` ou `np.ndarray` | Température maximale (degC) |
| `day_of_year` | `int` ou `np.ndarray` | Jour de l'année (1 a 365) |

**Retour :** `float` ou `np.ndarray` - ET0 en mm/jour.

---

### `et0_fao56_penman(tmin, tmax, humidity, wind_speed, solar_rad)`

Calcule l'ET0 par la méthode FAO-56 Penman-Monteith. Plus précise que
Hargreaves car elle intègre l'humidité relative, la vitesse du vent et le
rayonnement solaire mesuré.

```python
et0_pm = weather.hydrology.et0_fao56_penman(
    tmin=22.0,
    tmax=35.0,
    humidity=65.0,     # Humidité relative (%)
    wind_speed=2.5,    # Vitesse du vent a 2 m (m/s)
    solar_rad=18.0,    # Rayonnement solaire (MJ/m2/jour)
)
print(f"ET0 Penman-Monteith : {et0_pm:.2f} mm/jour")
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `tmin` | `float` | Température minimale (degC) |
| `tmax` | `float` | Température maximale (degC) |
| `humidity` | `float` | Humidité relative moyenne (%, entre 0 et 100) |
| `wind_speed` | `float` | Vitesse du vent à 2 m de hauteur (m/s) |
| `solar_rad` | `float` | Rayonnement solaire incident (MJ/m2/jour) |

**Retour :** `float` - ET0 en mm/jour.

---

### `runoff_cn(precipitation, prior_5d_rain)`

Calcule le ruissellement quotidien par la méthode révisée SCS-CN, avec
ajustement selon l'humidité antécédente (AMC).

```python
runoff = weather.hydrology.runoff_cn(
    precipitation=35.0,
    prior_5d_rain=20.0,
)
print(f"Ruissellement : {runoff:.2f} mm")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `precipitation` | `float` | requis | Précipitation du jour (mm) |
| `prior_5d_rain` | `float` | `0.0` | Cumul des 5 jours précédents (mm) pour l'ajustement AMC |

**Ajustement AMC :**

| Condition | Pluie 5j précédents | CN ajusté |
|-----------|---------------------|-----------|
| AMC I (sec) | < 12.5 mm | CN réduit |
| AMC II (moyen) | 12.5 a 35.5 mm | CN de base |
| AMC III (humide) | > 35.5 mm | CN augmenté |

**Retour :** `float` - Ruissellement en mm (0.0 si la pluie ne dépasse pas
l'abstraction initiale).

---

### `soil_params(soil_type)`

Retourne les paramètres physiques d'un sol béninois.

```python
params = weather.hydrology.soil_params("ferrallitique")
print(f"TAW   : {params['taw']} mm")
print(f"CN    : {params['cn_amc2']}")
print(f"Ksat  : {params['ksat']} mm/j")
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `soil_type` | `str` | Type de sol parmi les valeurs supportées |

**Types de sols supportés :**

| Type | TAW (mm) | CN AMC II | Ksat (mm/j) |
|------|----------|-----------|-------------|
| `'ferrugineux'` | 100 | 82 | 15 |
| `'ferrallitique'` | 130 | 75 | 35 |
| `'sableux'` | 60 | 65 | 100 |
| `'limoneux'` | 150 | 78 | 10 |

**Retour :** `dict` avec `taw`, `cn_amc2`, `ksat`.

**Exceptions :**

- `ValidationError` : type de sol non pris en charge.

---

### `crop_kc(crop, stage)`

Retourne le coefficient cultural (Kc) selon le stade phénologique.
Le Kc représente le rapport ETc / ET0 selon la norme FAO-56.

```python
kc = weather.hydrology.crop_kc("maize", "mid")
print(f"Kc milieu de cycle : {kc}")
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `crop` | `str` | Nom de la culture |
| `stage` | `str` | Stade parmi `'ini'`, `'mid'`, `'end'` |

**Coefficients Kc par culture et stade :**

| Culture | Kc ini | Kc mid | Kc end |
|---------|--------|--------|--------|
| `'maize'` | 0.30 | 1.20 | 0.35 |
| `'rice'` | 1.05 | 1.20 | 0.90 |
| `'manioc'` | 0.30 | 0.80 | 0.30 |
| `'sorghum'` | 0.30 | 1.00 | 0.55 |
| `'tomato'` | 0.60 | 1.15 | 0.70 |

**Retour :** `float` - Valeur du Kc.

**Exceptions :**

- `CropError` : culture non reconnue.

---

## Méthodes dépréciées

| Ancienne méthode | Remplacée par | Depuis |
|------------------|---------------|--------|
| `compute_water_balance()` | `water_balance()` | v1.2.0 |
| `get_soil_params(soil_type)` | `soil_params(soil_type)` | v1.2.0 |
| `get_crop_coefficients(crop, stage)` | `crop_kc(crop, stage)` | v1.2.0 |

## Attributs dépréciés

| Ancien attribut | Remplacé par | Depuis |
|-----------------|--------------|--------|
| `rainfall_data` | `rainfall` | v1.2.0 |
| `temperature_data` | `temperature` | v1.2.0 |
| `balance_result` | `balance` | v1.2.0 |

---

## Exemple complet

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Bilan hydrique complet
bilan = weather.water_balance(crop="sorghum", soil_type="sableux")

# Analyse du stress hydrique sur les 30 derniers jours
derniers_30j = bilan.tail(30)
stress_moyen = derniers_30j["stress_hydrique_index"].mean()
print(f"Stress hydrique moyen (30j) : {stress_moyen:.2f}")

# ET0 ponctuel
et0 = weather.et0_hargreaves(tmin=21.0, tmax=34.0, day_of_year=200)
print(f"ET0 du jour : {et0:.2f} mm/jour")

# Paramètres du sol
params = weather.hydrology.soil_params("ferrugineux")
print(f"Réserve utile max : {params['taw']} mm")

# Kc en plein cycle
kc = weather.hydrology.crop_kc("sorghum", "mid")
print(f"ETc = ET0 x Kc = {et0:.2f} x {kc} = {et0 * kc:.2f} mm/jour")
```

---

::: kadi.weather.hydrology.Hydrology
