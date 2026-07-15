# Module kadi.weather

Le module `weather` est le composant météorologique de KadiPy. Il fournit
une interface unifiée pour accéder aux données climatiques historiques et
prévisionnelles, et les transformer en indicateurs directement utiles pour
l'agriculture béninoise.

---

## Ce que fait ce module

Il ne se contente pas de télécharger de la donnée brute. Chaque appel
retourne un résultat interprétable par un agronome ou un conseiller agricole.

**Phénologie**

Détection automatique du démarrage et de la fin de la saison des pluies.
Le module choisit l'algorithme adapté à la zone géographique : Sivakumar
pour le régime unimodal du Nord, et Walter-Anyadike pour le régime bimodal
du Sud. Le calcul des degrés-jours de croissance (GDD) permet de suivre le
stade phénologique de la culture en cours.

**Hydrologie**

Modélisation du cycle de l'eau dans le sol selon les normes FAO-56.
L'évapotranspiration de référence (ET0) est calculée par la méthode
Hargreaves-Samani. Le bilan hydrique journalier est produit par culture
et par type de sol béninois.

**Risques climatiques**

Calcul d'indices de sécheresse (SPI, Markov, Exposant de Hurst) et
probabilité de pluie à court terme pour anticiper le lessivage des intrants
ou les risques de pertes de récolte.

**Fonctionnement hors ligne (offline-first)**

Un cache SQLite local stocke automatiquement les données téléchargées.
Si le terrain n'offre pas de connexion internet, le module utilise les
dernières données en cache de manière transparente.

---

## Architecture

Le module est construit autour d'une facade principale (`WeatherSession`)
qui orchestre le chargement des composants à la demande pour limiter la
consommation de mémoire et de bande passante.

```
WeatherSession
    |
    ├── Location          -> Coordonnées GPS + zone agro-écologique
    ├── WeatherData       -> Requêtes Open-Meteo / CHIRPS + cache SQLite
    ├── Phenology         -> Sivakumar, Walter-Anyadike, GDD
    ├── Hydrology         -> ET0 Hargreaves, bilan hydrique FAO
    └── RiskIndicators    -> SPI, Markov, probabilité de pluie
```

---

## Utilisation

### Initialisation

```python
from kadi.weather import WeatherSession

# Le module détecte automatiquement la zone agro-écologique
# depuis les coordonnées (Nord, Centre ou Sud Bénin).
session = WeatherSession(latitude=9.3333, longitude=2.6333, name="Parakou")
```

### Données brutes

```python
# Prévisions pour les 3 prochains jours
previsions = session.forecast(days=3)
print(previsions["data"])

# Historique des températures sur 1 mois
historique = session.historical(metric="temperature", months_back=1)
```

### Phénologie

```python
# Date estimée de démarrage de la saison des pluies
debut = session.onset()
print("Début estimé :", debut["onset_date"])

# Date estimée de fin de saison
fin = session.cessation()
print("Fin estimée  :", fin["cessation_date"])

# Suivi du stade phénologique du maïs semé le 1er mai
gdd = session.growing_degree_days(crop="maize", start_date="2026-05-01")
print("Stade phénologique :", gdd["phenology_stage"])
```

### Hydrologie

```python
# Bilan hydrique sur la période historique disponible
bilan = session.water_balance(crop="maize", soil_type="ferrugineux")
print(bilan[["precipitation", "ET0", "deficit_eau", "reserve_utile"]].tail())
```

### Risques et alertes

```python
# Probabilité de pluie et recommandation pour les 2 prochains jours
risque = session.rain_probability(days_ahead=2)
print("Recommandation :", risque["recommendation"])

# Indice de sécheresse sur 3 mois glissants
secheresse = session.drought_index(method="spi", window_months=3)
print("Sévérité :", secheresse["drought_severity"])
```

---

## Intégration avec kadi.market (Phase 4)

Le module weather est utilisé directement par `kadi.market` depuis la
Phase 4. La probabilité de pluie entre dans le calcul du coefficient
logistique (`gamma_route`) et dans le score de confiance des
recommandations d'arbitrage.

```python
from kadi.weather import WeatherSession
from kadi.market import Market

session = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
marche = Market(lat=9.30, lon=2.08, location="Parakou", weather_session=session)

risque = marche.assess_climate_risk(days_ahead=7)
print(risque["recommendation"])
```

---

## Zones agro-écologiques reconnues

| Zone | Latitude | Régime pluviométrique | Algorithme utilisé |
|------|----------|-----------------------|--------------------|
| Nord | > 9.5° N | Unimodal | Sivakumar |
| Centre | 7.5° - 9.5° N | Transition | Sivakumar |
| Sud | < 7.5° N | Bimodal | Walter-Anyadike |

---

## Dépendances

- `requests` : requêtes vers Open-Meteo et CHIRPS
- `pandas` / `numpy` : manipulation des séries temporelles
- `scipy` (optionnel) : calcul avancé de l'indice SPI

---

## Tests

```bash
pytest tests/test_weather/ -v
```

---

## Améliorations prévues

**Évapotranspiration Penman-Monteith (FAO-56)**
Remplacer Hargreaves-Samani par la méthode complète Penman-Monteith en
utilisant le rayonnement solaire et la vitesse du vent disponibles via
Open-Meteo.

**Bimodalité complète (Sud)**
Rendre l'algorithme Walter-Anyadike capable de retourner les deux saisons
séparément (`onset_1`, `cessation_1`, `onset_2`, `cessation_2`).

**SPI rigoureux**
Remplacer l'approximation Z-Score par l'ajustement d'une distribution Gamma
via `scipy.stats.gamma.fit`, conformément à la définition météorologique.

**Alertes climatiques extrêmes**
Ajouter une méthode `extreme_weather_alerts()` pour détecter les vagues de
chaleur (> 40 °C) et les précipitations diluviennes (> 50 mm/j).
