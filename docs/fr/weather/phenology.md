# Phénologie (`kadi.weather.phenology`)

La classe `Phenology` gère l'analyse phénologique pour une localisation.
Elle détecte le début (`onset`) et la fin (`cessation`) de la saison agricole,
et calcule les degrés-jours de croissance (GDD) pour les principales cultures
de la zone béninoise.

Elle est utilisée en interne par la façade `Weather`, mais peut aussi être
instanciée directement.

---

## Importation directe

```python
from kadi.weather import Phenology
```

---

## Initialisation

Dans le cas courant, `Phenology` est créée automatiquement par la façade
`Weather` lors du premier appel à `onset()`, `cessation()` ou `gdd()`.
Elle est alors accessible via `weather.phenology`.

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Phenology chargée à la demande
debut = weather.onset()
phenology = weather.phenology   # Instance disponible
```

Pour une instanciation directe :

```python
from kadi.weather import Phenology, Location
import pandas as pd

location = Location(lat=9.3, lon=2.3, name="Parakou")

# rainfall  : pd.Series journalière de précipitations, indexée par date
# temperature : pd.DataFrame avec colonnes 'temperature_min' et 'temperature_max'

phenology = Phenology(location, rainfall, temperature)
```

**Attributs publics :**

| Attribut | Type | Description |
|----------|------|-------------|
| `location` | `Location` | Localisation de l'analyse |
| `rainfall` | `pd.Series` | Série de précipitations quotidiennes |
| `temperature` | `pd.DataFrame` | Données de température (`temperature_min`, `temperature_max`) |
| `onset_ts` | `pd.Timestamp` | Date d'onset calculée (`None` avant le premier appel) |
| `crop` | `dict` | Paramètres culturaux par culture |

---

## Méthodes

### `onset()`

Détecte la date de démarrage de la saison agricole.

L'algorithme utilisé dépend de la zone climatique de la localisation :

- **Zone Nord** (régime unimodal) : algorithme de Sivakumar. Cherche, à
  partir du 1er mai, la première séquence de 3 jours cumulant au moins
  20 mm, sans période sèche de plus de 7 jours sur les 30 jours suivants.
- **Zones Sud et Centre** (régime bimodal) : algorithme hybride
  Walter-Anyadike appliqué sur deux fenêtres saisonnières (S1 : janv-juil,
  S2 : août-déc).

```python
debut = weather.onset()

print(f"Début S1   : {debut['onset_1']}")
print(f"Début S2   : {debut['onset_2']}")   # None en zone Nord
print(f"Algorithme : {debut['algorithm']}")
print(f"Zone       : {debut['zone']}")
print(f"Confiance  : {debut['confidence']}")
```

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `onset_date` | `str` | Alias de `onset_1` (rétrocompatibilité) |
| `onset_1` | `str` | Date de début de la première saison (`YYYY-MM-DD`) |
| `onset_2` | `str` | Date de début de la deuxième saison, `None` en zone Nord |
| `algorithm` | `str` | Algorithme utilisé (`'Sivakumar'` ou `'Walter-Anyadike bimodal'`) |
| `zone` | `str` | Zone climatique (`'Nord'`, `'Centre'`, `'Sud'`) |
| `confidence` | `float` | Indice de confiance (0.80 bimodal, 0.85 unimodal) |

**Exceptions :**

- `DataError` : aucune donnée de précipitation disponible.

---

### `cessation()`

Détermine la date de fin des pluies utiles.

La cessation est définie comme le dernier jour à partir duquel le cumul
de pluie restant (calculé en sens inverse) descend sous 20 mm.

- **Zone Nord** : une unique date de cessation calculée à partir de septembre.
- **Zones Sud et Centre** : deux dates de cessation (S1 autour de
  mai-juillet, S2 autour d'octobre-décembre).

```python
fin = weather.cessation()

print(f"Fin S1         : {fin['cessation_1']}")
print(f"Fin S2         : {fin['cessation_2']}")   # None en zone Nord
print(f"Durée saison   : {fin['duration_days']} jours")
print(f"Cumul annuel   : {fin['total_rainfall']:.0f} mm")
```

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `cessation_date` | `str` | Alias de `cessation_1` (rétrocompatibilité) |
| `cessation_1` | `str` | Date de fin de la première saison (`YYYY-MM-DD`) |
| `cessation_2` | `str` | Date de fin de la deuxième saison, `None` en zone Nord |
| `duration_days` | `int` | Durée de la saison principale en jours (zone Nord) |
| `total_rainfall` | `float` | Cumul annuel de précipitations en mm |
| `zone` | `str` | Zone climatique |

**Exceptions :**

- `DataError` : aucune donnée de précipitation disponible.

---

### `gdd(crop, start, end)`

Calcule l'accumulation des degrés-jours de croissance (GDD) pour une culture
depuis la date de semis.

Le GDD journalier est calculé comme :

```
GDD = max(0, (Tmax + Tmin) / 2 - Tbase)
```

où `Tbase` est la température de base de la culture (seuil en dessous duquel
la plante ne se développe pas).

```python
# GDD pour le maïs semé le 15 mai
resultat = weather.gdd(crop="maize", start="2026-05-15")

print(f"GDD accumulés  : {resultat['gdd_accumulated']:.1f} degC.jour")
print(f"Cycle accompli : {resultat['pct_cycle']} %")
print(f"Stade actuel   : {resultat['phenology_stage']}")

# Avec une date de fin explicite
resultat = weather.gdd(
    crop="rice",
    start="2026-06-01",
    end="2026-10-15",
)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Nom de la culture |
| `start` | `str` ou `pd.Timestamp` | requis | Date de semis (`YYYY-MM-DD`) |
| `end` | `str` ou `pd.Timestamp` | `None` | Date de fin (aujourd'hui si None) |

**Cultures supportées :**

| Culture | Temp. base (degC) | GDD total requis |
|---------|-------------------|------------------|
| `'maize'` | 10 | 1300 |
| `'rice'` | 10 | 1500 |
| `'manioc'` | 14 | 3000 |
| `'sorghum'` | 10 | 1400 |
| `'tomato'` | 10 | 1000 |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `gdd_accumulated` | `float` | Cumul GDD sur la période |
| `crop` | `str` | Nom de la culture |
| `gdd_total_cycle` | `int` | GDD total requis pour le cycle complet |
| `pct_cycle` | `int` | Pourcentage du cycle accompli (0 à 100) |
| `phenology_stage` | `str` | Stade estimé : `'vegetative'`, `'tasseling/flowering'`, `'maturity'` |

**Exceptions :**

- `CropError` : culture non reconnue.
- `DataError` : données de température insuffisantes sur la période.

La méthode `growing_degree_days()` est dépréciée depuis la v1.2.0.
Utilisez `gdd()` à la place.

---

## Attributs dépréciés

| Ancien attribut | Remplacé par | Depuis |
|-----------------|--------------|--------|
| `rainfall_data` | `rainfall` | v1.2.0 |
| `temperature_data` | `temperature` | v1.2.0 |
| `onset_date` | `onset_ts` | v1.2.0 |
| `crop_params` | `crop` | v1.2.0 |

---

## Exemple complet

```python
import kadi as kd

weather = kd.Weather(lat=6.4, lon=2.4, name="Cotonou")

# Démarrage et fin de saison (régime bimodal pour le Sud)
debut = weather.onset()
fin = weather.cessation()

print(f"Saison S1 : {debut['onset_1']} -> {fin['cessation_1']}")
print(f"Saison S2 : {debut['onset_2']} -> {fin['cessation_2']}")

# GDD pour le maïs
gdd = weather.gdd(crop="maize", start=debut["onset_1"])
print(f"Avancement : {gdd['pct_cycle']} % - {gdd['phenology_stage']}")
```

---

::: kadi.weather.phenology.Phenology
