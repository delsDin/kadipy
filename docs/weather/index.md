# kadi.weather - Météorologie agronomique

Le module `kadi.weather` fournit une interface unifiée pour accéder aux données
météo historiques et prévisionnelles, et les transformer en indicateurs
directement utiles pour l'agriculture béninoise : saisons, sécheresses, bilans
hydriques.

---

## Architecture

Le module est organisé autour d'une façade `Weather` qui initialise
chaque composant uniquement quand il est nécessaire (chargement paresseux).

```
Weather
├── Location        - Coordonnées GPS et zone agro-écologique
├── WeatherLoader   - Récupération et cache des données brutes
├── Phenology       - Saisons, GDD, onset/cessation
├── Hydrology       - Bilan hydrique, ET0 (FAO-56)
└── Risk            - SPI, Markov, probabilité de pluie
```

Les sources de données utilisées (mode hybride `source='both'`) :

| Source | Usage | Accès |
|--------|-------|-------|
| CHIRPS | Précipitations historiques longues (1981 à J-15) | Rasters GeoTIFF / API CHC |
| Open-Meteo | Prévisions (15 jours) et températures historiques | API gratuite |
| SoilGrids v2.0 | Classification pédologique WRB pour le bilan hydrique | API ISRIC (`rest.isric.org`) |
| Cache SQLite / JSON | Stockage local et réutilisation hors-ligne | `~/.kadi/` |

Les colonnes de température sont automatiquement normalisées pour produire `temperature_mean`.
La source d'origine de chaque observation est préservée dynamiquement dans la colonne `data_source` du cache SQLite (`~/.kadi/cache.db`).

---

## Zones agro-écologiques du Bénin

Le module détecte automatiquement la zone en fonction de la latitude :

| Zone | Latitude | Caractéristiques |
|------|---------|-----------------|
| Nord | > 9.5° N | Régime unimodal : algorithme Sivakumar |
| Centre | 7.5° à 9.5° N | Transition : algorithme adaptatif |
| Sud | < 7.5° N | Régime bimodal : algorithme Walter-Anyadike |

---

## Initialisation

```python
import kadi as kd

# Parakou (Nord Bénin, régime unimodal)
weather = kd.Weather(
    lat=9.3333,
    lon=2.6333,
    name="Parakou",
)

# Cotonou (Sud Bénin, régime bimodal)
weather_sud = kd.Weather(
    lat=6.3654,
    lon=2.4183,
    name="Cotonou",
)
```

| Paramètre | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| `lat` | `float` | Oui | Latitude en degrés décimaux |
| `lon` | `float` | Oui | Longitude en degrés décimaux |
| `name` | `str` | Non | Nom de la localité |
| `cache_dir` | `str` | Non | Dossier du cache (Défaut : `~/.kadi/`) |

---

## Exemples complets

### 1. Prévisions météo

```python
# Prévision sur 7 jours
prevision = weather.forecast(days=7)

print(f"Lieu : {prevision['location']['name']}")
for jour in prevision['data']:
    print(
        f"  {jour['date']} - Pluie : {jour['precipitation']:.1f} mm, "
        f"T min : {jour['temperature_min']:.1f}°C"
    )
```

### 2. Données historiques

```python
# 24 mois d'historique des précipitations
df_hist = weather.historical(metric="precipitation", months_back=24)
print(df_hist.tail(10))

# Toutes les variables
df_complet = weather.historical(months_back=12)
print(df_complet.columns.tolist())
```

### 3. Phénologie

```python
# Démarrage de la saison des pluies
onset = weather.onset()
print(f"Début estimé : {onset['onset_date']}")
print(f"Méthode      : {onset['method']}")

# Fin de la saison des pluies
cessation = weather.cessation()
print(f"Fin estimée : {cessation['cessation_date']}")

# Degrés-jours de croissance pour le maïs
gdd = weather.growing_degree_days(
    crop="maize",
    start_date="2026-05-15",
)
print(f"GDD accumulés   : {gdd['gdd_accumulated']:.1f}")
print(f"Stade phéno     : {gdd['phenology_stage']}")
```

### 4. Bilan hydrique

```python
# Bilan hydrique FAO-56 pour le maïs sur sol ferrugineux
bilan = weather.water_balance(crop="maize", soil_type="ferrugineux")

# Le résultat est un DataFrame avec les colonnes clés
print(bilan[["precipitation", "ET0", "deficit_eau", "reserve_utile"]].tail(14))
```

### 5. Risques climatiques

```python
# Probabilité de pluie sur les 3 prochains jours
risque_pluie = weather.rain_probability(days_ahead=3, min_rainfall_mm=1.0)
print(f"Pluie demain  : {risque_pluie['tomorrow'] * 100:.0f}%")
print(f"Recommandation : {risque_pluie['recommendation']}")

# Indice de sécheresse SPI (3 mois glissants)
secheresse = weather.drought_index(method="spi", window_months=3)
print(f"SPI 3 mois : {secheresse['spi_3month']:.2f}")
print(f"Sévérité   : {secheresse['drought_severity']}")
```

---

## Cache hors-ligne

Toutes les données téléchargées sont stockées dans une base SQLite locale (`~/.kadi/cache.db`).
Si le réseau est indisponible, le module utilise automatiquement les données en cache sans lever d'erreur.

---

## Cultures supportées pour la phénologie et le bilan hydrique

| Code | Culture | Kc (moyen) |
|------|---------|-----------|
| `maize` | Maïs | 1.15 |
| `rice` | Riz | 1.20 |
| `sorghum` | Sorgho | 1.05 |
| `millet` | Mil | 0.95 |
| `cowpea` | Niébé | 0.95 |
| `soybean` | Soja | 1.10 |
| `yam` | Igname | 0.90 |
| `cassava` | Manioc | 0.85 |

---

## Sous-modules

- [Façade Météo (Weather)](session.md)
- [Phénologie](phenology.md)
- [Hydrologie](hydrology.md)
- [Risques climatiques](risk.md)

