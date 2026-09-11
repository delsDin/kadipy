# Façade météo (`kadi.weather.session`)

`Weather` est le point d'entrée principal du module `kadi.weather`.
Elle orchestre les composants internes (`Location`, `WeatherLoader`, `Phenology`,
`Hydrology`, `Risk`) et expose une API simple et unifiée pour toutes les
fonctionnalités météorologiques et agronomiques.

---

## Initialisation

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
```

**Paramètres :**

| Nom | Type | Obligatoire | Description |
|-----|------|-------------|-------------|
| `lat` | `float` | oui | Latitude en degrés décimaux |
| `lon` | `float` | oui | Longitude en degrés décimaux |
| `name` | `str` | non | Nom de la localité |
| `cache` | `str` | non | Répertoire de cache local |

Les paramètres `latitude`, `longitude` et `cache_dir` sont reconnus mais
dépréciés depuis la v1.2.0. Utilisez `lat`, `lon` et `cache` à la place.

**Attributs publics :**

| Attribut | Type | Description |
|----------|------|-------------|
| `location` | `Location` | Localisation associée |
| `loader` | `WeatherLoader` | Gestionnaire de données météorologiques |
| `phenology` | `Phenology` | Composant phénologique (chargé à la demande) |
| `hydrology` | `Hydrology` | Composant hydrologique (chargé à la demande) |
| `risk` | `Risk` | Composant indicateurs de risque (chargé à la demande) |
| `cache` | `str` | Répertoire de cache |

---

## Méthodes

### `forecast(days)`

Récupère les prévisions météorologiques court-terme depuis Open-Meteo.

```python
prevision = weather.forecast(days=5)

print(prevision["location"])
# {'name': 'Parakou', 'lat': 9.3, 'lon': 2.3}

for jour in prevision["data"][:3]:
    print(jour)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `days` | `int` | Depuis `CONFIG` | Nombre de jours de prévision (maximum 16) |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `location` | `dict` | `{'name', 'lat', 'lon'}` |
| `data` | `list[dict]` | Liste des jours avec variables météo |
| `source` | `str` | Source utilisée |
| `last_updated` | `str` | Horodatage ISO de la dernière mise à jour |

---

### `historical(metric, months, source)`

Retourne les séries météorologiques historiques depuis CHIRPS et Open-Meteo.

```python
# Toutes les variables sur 10 ans (défaut)
df = weather.historical()

# Seulement les précipitations sur 6 mois
df_pluie = weather.historical(metric="precipitation", months=6)

# Toutes les variables avec source explicite
df_complet = weather.historical(months=120, source="both")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `metric` | `str` | `'all'` | Filtre : `'temperature'`, `'precipitation'`, `'humidity'`, `'all'` |
| `months` | `int` | `120` | Nombre de mois d'historique |
| `source` | `str` | `None` | Source précipitations : `'chirps'`, `'openmeteo'`, `'both'`. Si None, utilise `CONFIG`. |

Le paramètre `months_back` est déprécié depuis la v1.2.0. Utilisez `months` à la place.

**Retour :** `pd.DataFrame` avec `DatetimeIndex`.

---

### `onset()`

Détecte la date de démarrage de la saison agricole selon la zone climatique.

```python
debut = weather.onset()

print(f"Démarrage S1 : {debut['onset_1']}")
print(f"Démarrage S2 : {debut['onset_2']}")   # None en zone Nord (unimodale)
print(f"Algorithme   : {debut['algorithm']}")
print(f"Confiance    : {debut['confidence']}")
```

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `onset_date` | `str` | Alias de `onset_1` (rétrocompatibilité) |
| `onset_1` | `str` | Date de début de la première saison (`YYYY-MM-DD`) |
| `onset_2` | `str` | Date de début de la deuxième saison, `None` en zone Nord |
| `algorithm` | `str` | Algorithme utilisé |
| `zone` | `str` | Zone climatique détectée |
| `confidence` | `float` | Indice de confiance |

L'algorithme dépend de la zone climatique de la localisation :

| Zone | Régime | Algorithme |
|------|--------|------------|
| Nord (> 9.5° N) | Unimodal | Sivakumar |
| Sud et Centre | Bimodal | Walter-Anyadike |

---

### `cessation()`

Détermine la date de fin des pluies utiles.

```python
fin = weather.cessation()

print(f"Fin S1 : {fin['cessation_1']}")
print(f"Fin S2 : {fin['cessation_2']}")   # None en zone Nord
print(f"Durée  : {fin['duration_days']} jours")
```

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `cessation_date` | `str` | Alias de `cessation_1` (rétrocompatibilité) |
| `cessation_1` | `str` | Date de fin de la première saison (`YYYY-MM-DD`) |
| `cessation_2` | `str` | Date de fin de la deuxième saison, `None` en zone Nord |
| `duration_days` | `int` | Durée de la saison en jours (zone Nord) |
| `total_rainfall` | `float` | Cumul annuel de précipitations (mm) |
| `zone` | `str` | Zone climatique |

---

### `gdd(crop, start, end)`

Calcule l'accumulation des degrés-jours de croissance (GDD) depuis la date de semis.
Les GDD mesurent l'énergie thermique disponible pour le développement de la plante.

```python
resultat = weather.gdd(
    crop="maize",
    start="2026-05-15",
    end="2026-09-30",   # Optionnel : aujourd'hui si None
)

print(f"GDD accumulés   : {resultat['gdd_accumulated']:.1f} degC.jour")
print(f"Stade actuel    : {resultat['phenology_stage']}")
print(f"Avancement      : {resultat['pct_cycle']} %")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Culture : `'maize'`, `'rice'`, `'manioc'`, `'sorghum'`, `'tomato'` |
| `start` | `str` ou `pd.Timestamp` | requis | Date de semis (`YYYY-MM-DD`) |
| `end` | `str` ou `pd.Timestamp` | `None` | Date de fin (aujourd'hui si None) |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `gdd_accumulated` | `float` | Cumul GDD sur la période |
| `crop` | `str` | Nom de la culture |
| `gdd_total_cycle` | `int` | GDD total requis pour le cycle complet |
| `pct_cycle` | `int` | Pourcentage du cycle accompli |
| `phenology_stage` | `str` | Stade phénologique estimé |

La méthode `growing_degree_days()` est dépréciée depuis la v1.2.0.
Utilisez `gdd()` à la place.

---

### `drought(method, window)`

Calcule l'indice de sécheresse sur les données historiques.

```python
# SPI sur une fenêtre de 3 mois (défaut)
secheresse = weather.drought(method="spi", window=3)

print(f"SPI 3 mois  : {secheresse['spi_3month']:.2f}")
print(f"Sévérité    : {secheresse['drought_severity']}")

# Analyse combinée (SPI + Markov + Hurst)
analyse = weather.drought(method="combined", window=3)
print(f"Markov P(sec|sec) : {analyse['markov_p_dry']:.2f}")
print(f"Exposant de Hurst : {analyse['hurst_exponent']:.2f}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `method` | `str` | `'spi'` | Méthode de calcul (voir tableau ci-dessous) |
| `window` | `int` | `3` | Fenêtre temporelle en mois (pour le SPI) |

**Méthodes disponibles :**

| Méthode | Description |
|---------|-------------|
| `'spi'` | Standardized Precipitation Index (McKee et al., 1993) |
| `'markov'` | Probabilité de persistance de sécheresse (chaîne de Markov) |
| `'hurst'` | Exposant de Hurst - mémoire longue de la sécheresse |
| `'combined'` | Combinaison des trois méthodes |

La méthode `drought_index()` est dépréciée depuis la v1.2.0.
Utilisez `drought()` à la place.

---

### `rain_prob(days, min_mm)`

Prévoit la probabilité de pluie pour les prochains jours, en combinant les
prévisions Open-Meteo (70 %) et les fréquences historiques de Markov (30 %).

```python
proba = weather.rain_prob(days=3, min_mm=1.0)

print(f"Demain          : {proba['tomorrow'] * 100:.0f} %")
print(f"Dans 2 jours    : {proba['2_days'] * 100:.0f} %")
print(f"Message         : {proba['message']}")
print(f"Recommandation  : {proba['recommendation']}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `days` | `int` | `1` | Nombre de jours à prévoir (1 à 7) |
| `min_mm` | `float` | `1.0` | Seuil de pluie significative en mm |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `tomorrow` | `float` | Probabilité de pluie demain |
| `N_days` | `float` | Probabilité pour le jour N (N >= 2) |
| `message` | `str` | Phrase de synthèse avec le risque maximal |
| `recommendation` | `str` | Recommandation agronomique |

La méthode `rain_probability()` est dépréciée depuis la v1.2.0.
Utilisez `rain_prob()` à la place.

---

### `water_balance(crop, soil_type)`

Simule le bilan hydrique quotidien du sol selon la méthode FAO-56.
L'évapotranspiration de référence (ET0) est calculée par Hargreaves-Samani.

```python
bilan = weather.water_balance(crop="maize", soil_type="ferrugineux")

print(bilan.tail(7)[[
    "precip", "et0", "pluie_eff", "evapotransp",
    "deficit_eau", "reserve_utile", "stress_hydrique_index"
]])
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | `'maize'` | Culture de référence |
| `soil_type` | `str` | `'ferrugineux'` | Type de sol béninois |

**Types de sols supportés :** `'ferrugineux'`, `'ferrallitique'`, `'sableux'`, `'limoneux'`.

**Colonnes du DataFrame retourné :**

| Colonne | Description |
|---------|-------------|
| `precip` | Précipitations observées (mm) |
| `et0` | Évapotranspiration de référence (mm) |
| `pluie_eff` | Pluie efficace après déduction du ruissellement (mm) |
| `evapotransp` | Évapotranspiration de la culture - ET0 x Kc (mm) |
| `deficit_eau` | Déficit hydrique journalier (mm) |
| `reserve_utile` | Eau disponible dans le sol (mm) |
| `stress_hydrique_index` | Indice de stress hydrique (0 à 1) |

---

### `et0_hargreaves(tmin, tmax, day_of_year)`

Calcule l'évapotranspiration de référence (ET0) par Hargreaves-Samani pour un
jour donné. Utile pour un calcul ponctuel sans passer par le bilan complet.

```python
et0 = weather.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=180)
print(f"ET0 : {et0:.2f} mm/jour")
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `tmin` | `float` | Température minimale (degC) |
| `tmax` | `float` | Température maximale (degC) |
| `day_of_year` | `int` | Jour de l'année (1 à 365) |

**Retour :** `float` - ET0 en mm/jour.

---

## Exemple complet

```python
import kadi as kd

# Initialisation
weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Données historiques
df = weather.historical(months=24)
print(df.head())

# Prévisions 7 jours
prevision = weather.forecast(days=7)

# Phénologie de la saison courante
debut = weather.onset()
fin = weather.cessation()
print(f"Saison : {debut['onset_1']} -> {fin['cessation_1']}")

# GDD pour le maïs semé le 15 mai
gdd = weather.gdd(crop="maize", start="2026-05-15")
print(f"Avancement : {gdd['pct_cycle']} % ({gdd['phenology_stage']})")

# Risque de sécheresse
s = weather.drought(method="combined")
print(f"SPI 3 mois : {s['spi_3month']:.2f} - {s['drought_severity']}")

# Probabilité de pluie
proba = weather.rain_prob(days=3)
print(proba["recommendation"])

# Bilan hydrique
bilan = weather.water_balance(crop="maize", soil_type="ferrugineux")
print(bilan[["precip", "reserve_utile", "stress_hydrique_index"]].tail(10))
```

---

::: kadi.weather.session.Weather
