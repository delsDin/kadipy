# kadi.weather — Météorologie agronomique

Le module `kadi.weather` fournit une interface unifiée pour accéder aux données
météo historiques et prévisionnelles, et les transformer en indicateurs
directement utiles pour l'agriculture béninoise : saisons, sécheresses, bilans
hydriques.

---

## Architecture

Le module est organisé autour d'une façade `WeatherSession` qui initialise
chaque composant uniquement quand il est nécessaire (chargement paresseux).

```
WeatherSession
├── Location        — Coordonnées GPS et zone agro-écologique
├── WeatherData     — Récupération et cache des données brutes
├── Phenology       — Saisons, GDD, onset/cessation
├── Hydrology       — Bilan hydrique, ET0 (FAO-56)
└── RiskIndicators  — SPI, Markov, probabilité de pluie
```

Les sources de données utilisées :

| Source | Usage | Accès |
|--------|-------|-------|
| Open-Meteo | Prévisions jusqu'à 16 jours | API gratuite |
| CHIRPS | Précipitations historiques (1981+) | API gratuite |
| Cache SQLite | Réutilisation hors-ligne | `~/.kadi/` |

---

## Zones agro-écologiques du Bénin

Le module détecte automatiquement la zone en fonction de la latitude :

| Zone | Latitude | Caractéristiques |
|------|---------|-----------------|
| Nord | > 9.5° N | Régime unimodal — algorithme Sivakumar |
| Centre | 7.5° – 9.5° N | Transition — algorithme adaptatif |
| Sud | < 7.5° N | Régime bimodal — algorithme Walter-Anyadike |

---

## Initialisation

```python
from kadi.weather import WeatherSession

# Parakou (Nord Bénin, régime unimodal)
session = WeatherSession(
    latitude=9.3333,
    longitude=2.6333,
    name="Parakou",
)

# Cotonou (Sud Bénin, régime bimodal)
session_sud = WeatherSession(
    latitude=6.3654,
    longitude=2.4183,
    name="Cotonou",
)
```

| Paramètre | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| `latitude` | `float` | Oui | Latitude en degrés décimaux |
| `longitude` | `float` | Oui | Longitude en degrés décimaux |
| `name` | `str` | Non | Nom de la localité (pour les messages) |
| `cache_dir` | `str` | Non | Dossier du cache. Défaut : `~/.kadi/` |

---

## Exemples complets

### 1. Prévisions météo

```python
# Prévision sur 7 jours
prevision = session.forecast(days=7)

print(f"Lieu : {prevision['location']['name']}")
for jour in prevision['data']:
    print(
        f"  {jour['date']} — Pluie : {jour['precipitation']:.1f} mm, "
        f"T min : {jour['temperature_min']:.1f}°C"
    )
```

### 2. Données historiques

```python
# 24 mois d'historique des précipitations
df_hist = session.historical(metric="precipitation", months_back=24)
print(df_hist.tail(10))

# Toutes les variables
df_complet = session.historical(months_back=12)
print(df_complet.columns.tolist())
# ['temperature_min', 'temperature_max', 'precipitation', 'humidity']
```

### 3. Phénologie

```python
# Démarrage de la saison des pluies
onset = session.onset()
print(f"Début estimé : {onset['onset_date']}")
print(f"Méthode      : {onset['method']}")

# Fin de la saison des pluies
cessation = session.cessation()
print(f"Fin estimée : {cessation['cessation_date']}")

# Degrés-jours de croissance pour le maïs (semé le 15 mai)
gdd = session.growing_degree_days(
    crop="maize",
    start_date="2026-05-15",
)
print(f"GDD accumulés   : {gdd['gdd_accumulated']:.1f}")
print(f"Stade phéno     : {gdd['phenology_stage']}")
```

### 4. Bilan hydrique

```python
# Bilan hydrique FAO-56 pour le maïs sur sol ferrugineux
bilan = session.water_balance(crop="maize", soil_type="ferrugineux")

# Le résultat est un DataFrame avec les colonnes clés
print(bilan[["precipitation", "ET0", "deficit_eau", "reserve_utile"]].tail(14))
```

### 5. Risques climatiques

```python
# Probabilité de pluie sur les 3 prochains jours
risque_pluie = session.rain_probability(days_ahead=3, min_rainfall_mm=1.0)
print(f"Pluie demain  : {risque_pluie['tomorrow'] * 100:.0f}%")
print(f"Recommandation : {risque_pluie['recommendation']}")

# Indice de sécheresse SPI (3 mois glissants)
secheresse = session.drought_index(method="spi", window_months=3)
print(f"SPI 3 mois : {secheresse['spi_3month']:.2f}")
print(f"Sévérité   : {secheresse['drought_severity']}")
```

---

## Cache hors-ligne

Toutes les données téléchargées sont stockées dans une base SQLite locale :

```
~/.kadi/
├── weather_data.db     ← Données historiques (CHIRPS + Open-Meteo)
└── weather_forecast.db ← Prévisions court-terme
```

Si le réseau est indisponible, le module utilise automatiquement les données
en cache sans lever d'erreur.

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

- [Session météo (WeatherSession)](session.md)
- [Phénologie](phenology.md)
- [Hydrologie](hydrology.md)
- [Risques climatiques](risk.md)
