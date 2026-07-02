# KadiPy - Module Météorologique (`kadi.weather`)

Le module `weather` est l'un des piliers centraux de KadiPy. Il est conçu pour fournir aux agronomes, chercheurs et développeurs béninois une interface unifiée pour accéder à des données météorologiques historiques et prévisionnelles, ainsi qu'à des modélisations agronomiques avancées.

## Fonctionnalités Principales

Ce module ne se contente pas de télécharger de la donnée brute. Il la transforme en indicateurs métiers utiles pour l'agriculture africaine :
- **Phénologie** : Détection du démarrage (Onset) et de la fin (Cessation) de la saison des pluies en s'adaptant à la zone climatique (algorithme de Sivakumar pour le régime unimodal au Nord, et Walter-Anyadike pour le régime bimodal au Sud).
- **Hydrologie** : Modélisation du bilan hydrique des sols selon les normes de la FAO (méthode de Hargreaves-Samani pour l'évapotranspiration de référence ET0).
- **Risques Climatiques** : Calcul d'indices de sécheresse (SPI, Chaînes de Markov, Exposant de Hurst) et de probabilités de pluies pour alerter sur le lessivage des intrants.
- **Résilience (Offline-First)** : Un cache SQLite local transparent (`kadi.cache`) permet de stocker les historiques et prévisions. Si le terrain n'offre pas de connexion internet, le module utilise gracieusement les dernières données en cache.

## Architecture du Module

Le module est structuré autour d'une **Façade** (`WeatherSession`) qui orchestre le chargement paresseux (Lazy Loading) des autres composants pour économiser la RAM et la bande passante :

1. **`WeatherSession`** (`session.py`) : Le point d'entrée unique de l'utilisateur. 
2. **`Location`** (`location.py`) : Représente les coordonnées géographiques et détecte automatiquement la zone agro-écologique (Nord, Centre, Sud).
3. **`WeatherData`** (`data.py`) : Gère les requêtes vers les connecteurs (`_sources/open_meteo.py`, `_sources/chirps.py`) et interroge le cache local.
4. **`Phenology`** (`phenology.py`) : Algorithmes de détection du cycle de la mousson et calcul des degrés-jours de croissance (GDD).
5. **`Hydrology`** (`hydrology.py`) : Calculs liés à l'évapotranspiration, au ruissellement et au bilan hydrique.
6. **`RiskIndicators`** (`risk.py`) : Alertes climatiques à court terme et indices de sécheresse à long terme.

## 🚀 Guide d'Utilisation Rapide

Il n'est pas nécessaire d'instancier manuellement toutes les sous-classes. La `WeatherSession` simplifie tout le processus.

### Initialisation
```python
from kadi.weather import WeatherSession

# On initialise la session avec les coordonnées géographiques
# Le nom est optionnel. KadiPy va automatiquement identifier la zone climatique.
session = WeatherSession(latitude=9.3333, longitude=2.6333, name='Parakou')
```

### 1. Données Brutes (Prévisions et Historique)
```python
# Obtenir les prévisions pour les 3 prochains jours
forecast = session.forecast(days=3)
print(forecast['data'])

# Obtenir un mois d'historique de températures
hist_temp = session.historical(metric='temperature', months_back=1)
```

### 2. Phénologie (Saisons et Croissance)
```python
# Date de démarrage de la saison des pluies (Onset)
onset_info = session.onset()
print("Démarrage des pluies estimé :", onset_info['onset_date'])

# Date de fin de saison (Cessation)
cessation_info = session.cessation()
print("Fin de la saison des pluies :", cessation_info['cessation_date'])

# Calcul des Degrés-Jours de croissance pour le maïs semé le 1er Mai
gdd = session.growing_degree_days(crop='maize', start_date='2026-05-01')
print("Stade phénologique :", gdd['phenology_stage'])
```

### 3. Hydrologie (Eau dans le sol)
```python
# Bilan hydrique sur la période historique disponible
wb = session.water_balance(crop='maize', soil_type='ferrugineux')
print(wb[['precipitation', 'ET0', 'runoff', 'soil_moisture']].tail())
```

### 4. Risques et Alertes
```python
# Probabilité de pluie et recommandations pour les 2 prochains jours
rain_risk = session.rain_probability(days_ahead=2)
print("Recommandation :", rain_risk['recommendation'])

# Indice de sécheresse (Standardized Precipitation Index) sur 3 mois
drought = session.drought_index(method='spi', window_months=3)
print("Sévérité de la sécheresse :", drought['drought_severity'])
```

## 🧪 Tests et Documentation Interne
Le module est entièrement testé. Vous pouvez lancer la suite de tests (unitaires et intégration) avec `pytest` :
```bash
pytest tests/weather/
```

Pour une plongée en profondeur dans chaque classe, des **Notebooks Jupyter interactifs** sont disponibles dans le dossier `docs/weather/`. Ils documentent et exécutent les concepts mathématiques sous-jacents (Sivakumar, Hargreaves, GDD, etc.).

## Améliorations Futures (Roadmap)

Afin d'atteindre un niveau scientifique et une robustesse dignes des outils de production, voici les améliorations planifiées pour ce module :

1. **Bimodalité de la phénologie (Sud/Centre)**
   - *Objectif* : Gérer la petite et la grande saison des pluies.
   - *Amélioration* : Rendre l'algorithme Walter-Anyadike capable de détecter et renvoyer plusieurs onsets et cessations par an (`onset_1`, `cessation_1`, `onset_2`, `cessation_2`).

2. **Évapotranspiration via Penman-Monteith (FAO-56)**
   - *Objectif* : Obtenir un calcul de l'ET0 ultra-précis.
   - *Amélioration* : Remplacer l'actuel Hargreaves-Samani (qui ne demande que Tmin/Tmax) par Penman-Monteith en récupérant le rayonnement solaire et la vitesse du vent via Open-Meteo.

3. **Modélisation Avancée du SPI (Sécheresse)**
   - *Objectif* : Respecter la définition météorologique stricte.
   - *Amélioration* : Remplacer l'approximation du Z-Score par l'ajustement d'une distribution Gamma via `scipy.stats.gamma.fit`.

4. **Système d'Alertes Extrêmes**
   - *Objectif* : Prévenir les dégâts imminents sur les cultures.
   - *Amélioration* : Implémenter une méthode `extreme_weather_alerts()` pour détecter automatiquement dans les prévisions les vagues de chaleur (> 40°C) ou les précipitations diluviennes (> 50mm/j).

---
*README RÉDIGÉ PAR GEMINI 3.1 PRO*
---