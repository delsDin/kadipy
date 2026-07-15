# Session météo (`kadi.weather.session`)

`WeatherSession` est le point d'entrée principal du module `kadi.weather`.
Elle orchestre les composants internes et expose une API simple pour toutes
les fonctionnalités météo et agronomiques.

---

## Méthodes

### `forecast(days)`

Récupère les prévisions météo court-terme depuis Open-Meteo.

```python
prevision = session.forecast(days=5)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `days` | `int` | Depuis `config.py` | Nombre de jours (maximum 16) |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `location` | `dict` | `{'name', 'lat', 'lon'}` |
| `data` | `list[dict]` | Liste des jours avec `temperature_min`, `temperature_max`, `precipitation` |
| `data_source` | `str` | Source utilisée (`'open-meteo'` ou `'cache'`) |
| `last_updated` | `str` | Horodatage ISO de la mise à jour |

---

### `historical(metric, months_back)`

Retourne les séries météo historiques depuis CHIRPS et Open-Meteo.

```python
# Seulement les précipitations sur 6 mois
df_pluie = session.historical(metric="precipitation", months_back=6)

# Toutes les variables sur 10 ans
df_complet = session.historical(months_back=120)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `metric` | `str` | `'all'` | Filtre : `'temperature'`, `'precipitation'`, `'humidity'`, `'all'` |
| `months_back` | `int` | `120` | Nombre de mois d'historique |

**Retour :** `pd.DataFrame` — Données indexées par date.

---

### `onset()`

Détecte la date de démarrage de la saison des pluies selon la zone climatique.

```python
onset = session.onset()
print(f"Démarrage : {onset['onset_date']}")
print(f"Méthode   : {onset['method']}")  # 'Sivakumar' ou 'Walter-Anyadike'
```

**Retour :** `dict` avec `onset_date`, `method`, `confidence`, `zone`.

L'algorithme utilisé dépend de la zone automatiquement détectée :
- **Nord (> 9.5° N)** : Sivakumar — saison unimodale
- **Sud (< 7.5° N)** : Walter-Anyadike — saison bimodale

---

### `cessation()`

Détermine la date de fin des pluies utiles.

```python
cessation = session.cessation()
print(f"Fin saison : {cessation['cessation_date']}")
```

**Retour :** `dict` avec `cessation_date`, `method`, `confidence`.

---

### `growing_degree_days(crop, start_date, end_date)`

Calcule l'accumulation de degrés-jours de croissance depuis la date de semis.
Les GDD mesurent l'énergie thermique disponible pour le développement de la plante.

```python
gdd = session.growing_degree_days(
    crop="maize",
    start_date="2026-05-15",   # Date de semis
    end_date="2026-09-30",     # Optionnel — jusqu'à aujourd'hui si None
)

print(f"GDD accumulés  : {gdd['gdd_accumulated']:.1f} °C·jour")
print(f"Stade phéno    : {gdd['phenology_stage']}")
print(f"Floraison dans : {gdd['days_to_flowering']} jours")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture (`'maize'`, `'rice'`, etc.) |
| `start_date` | `str` | requis | Date de semis au format `'YYYY-MM-DD'` |
| `end_date` | `str` | `None` | Date de fin (aujourd'hui si None) |

**Retour :** `dict` avec `gdd_accumulated`, `phenology_stage`, `crop`,
`start_date`, `days_to_flowering`, `days_to_maturity`.

---

### `rain_probability(days_ahead, min_rainfall_mm)`

Calcule la probabilité de pluie en combinant les prévisions Open-Meteo et
les fréquences historiques (chaînes de Markov).

```python
prob = session.rain_probability(days_ahead=3, min_rainfall_mm=1.0)

print(f"Demain     : {prob['tomorrow'] * 100:.0f}%")
print(f"Recommandation : {prob['recommendation']}")
print(f"Message        : {prob['message']}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `days_ahead` | `int` | `1` | Horizon de prévision en jours |
| `min_rainfall_mm` | `float` | `1.0` | Seuil de pluie significative en mm |

**Retour :** `dict` avec `tomorrow` (probabilité J+1), `message`,
`recommendation`.

---

### `drought_index(method, window_months)`

Calcule un indice de sécheresse sur les données historiques.

```python
drought = session.drought_index(method="spi", window_months=3)

print(f"SPI 3 mois  : {drought['spi_3month']:.2f}")
print(f"Sévérité    : {drought['drought_severity']}")
```

**Méthodes disponibles :**

| Méthode | Description |
|---------|-------------|
| `'spi'` | Standardized Precipitation Index (Z-score sur les précipitations) |
| `'markov'` | Probabilité de persistance de la sécheresse (Markov) |
| `'hurst'` | Exposant de Hurst — mémoire longue de la sécheresse |
| `'combined'` | Combinaison pondérée des 3 méthodes |

**Sévérités SPI :**

| SPI | Sévérité |
|-----|---------|
| > -0.5 | `no_drought` |
| -0.5 à -1.0 | `mild` |
| -1.0 à -1.5 | `moderate` |
| < -1.5 | `severe` |

---

### `water_balance(crop, soil_type)`

Simule le bilan hydrique quotidien du sol selon la méthode FAO-56, en
calculant l'évapotranspiration de référence (ET0) par Hargreaves-Samani.

```python
bilan = session.water_balance(crop="maize", soil_type="ferrugineux")
print(bilan.tail(7)[["precipitation", "ET0", "deficit_eau", "reserve_utile"]])
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | `'maize'` | Culture de référence (influence le Kc) |
| `soil_type` | `str` | `'ferrugineux'` | Type de sol béninois |

**Types de sols supportés :** `'ferrugineux'`, `'vertisol'`, `'hydromorphe'`,
`'sableux'`.

**Colonnes du DataFrame retourné :**

| Colonne | Description |
|---------|-------------|
| `precipitation` | Précipitations observées (mm) |
| `ET0` | Évapotranspiration de référence (mm) |
| `ETc` | Évapotranspiration de la culture (ET0 × Kc) |
| `deficit_eau` | Déficit hydrique journalier (mm) |
| `reserve_utile` | Eau disponible dans le sol (mm) |
| `runoff` | Ruissellement journalier (mm) |

---

### `et0_hargreaves(tmin, tmax, day_of_year)`

Calcule l'évapotranspiration de référence (ET0) pour un jour donné avec la
méthode Hargreaves-Samani.

```python
et0 = session.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=180)
print(f"ET0 : {et0:.2f} mm/jour")
```

---

::: kadi.weather.session.WeatherSession
