# kadi.market - Économie agricole

Le module `kadi.market` est le moteur d'analyse économique de KadiPy. Il
modélise le marché agricole béninois de façon dynamique et permet de calculer
des opportunités d'arbitrage, des coûts logistiques réels, des prévisions de
prix et des recommandations de portefeuille de cultures.

---

## Architecture

Le module est centré sur la classe `Market`, qui orchestre 4 sous-modules
spécialisés et un client d'ingestion de données.

```
Market
├── data_ingestion   — Client WFP DataBridges + cache SQLite
├── pricing          — Normalisation, anomalies, saisonnalité
├── forecasting      — Prévisions par Machine Learning
├── logistics        — Distances, coûts de transport, météo (Phase 4)
└── decision_support — Arbitrage, stockage, portefeuille
```

Chaque sous-module peut être utilisé seul ou via la façade `Market`.

---

## Initialisation

```python
from kadi.market import Market

# Initialisation simple (données simulées si pas de clé WFP)
marche = Market(lat=9.30, lon=2.08, location="Parakou")

# Avec intégration météo (Phase 4)
from kadi.weather import WeatherSession

ws = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
marche = Market(lat=9.30, lon=2.08, location="Parakou", weather_session=ws)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `lat` | `float` | Latitude (entre 6.0° et 12.5° N) |
| `lon` | `float` | Longitude (entre 0.5° et 3.9° E) |
| `location` | `str` | Nom du marché (ex: `"Cotonou"`, `"Parakou"`) |
| `env_file` | `str` | Chemin vers le fichier `.env`. Défaut : `".env"` |
| `weather_session` | `WeatherSession` | Session météo optionnelle pour l'ajustement climatique |

---

## Exemples complets

### 1. Prix du marché

```python
# Résumé statistique des prix du maïs sur 90 jours
resume = marche.price_crop("maize", days_back=90)

print(f"Médiane : {resume['prix_median']} XOF/kg")
print(f"Tendance : {resume['prix_min']} → {resume['prix_max']} XOF/kg")
print(f"Données : {'simulées' if resume['is_simulated'] else 'réelles WFP'}")
print(f"Confiance : {resume['confidence_score']:.2f}")
```

### 2. Décision d'arbitrage spatial

```python
# "Est-il rentable de transporter 10 tonnes de maïs de Parakou à Cotonou ?"
decision = marche.decision_support.arbitrage_decision(
    crop="maize",
    market_from="Parakou",
    market_to="Cotonou",
    qty_tons=10.0,
)

print(decision["recommandation"])           # "TRANSPORTER" ou "NE PAS TRANSPORTER"
print(f"Gain net : {decision['gain_net_percent']:.1f}%")
print(f"Confiance : {decision['confidence_score']:.2f}")
```

### 3. Décision de stockage

```python
# "Vaut-il mieux stocker 5 tonnes d'igname pendant 3 mois ou vendre maintenant ?"
stockage = marche.decision_support.storage_vs_sell_now(
    crop="yam",
    market="Abomey",
    current_price=250_000.0,   # XOF/tonne
    qty_tons=5.0,
    mois_stockage=3,           # Horizon configurable (Phase 4)
)

print(stockage["recommandation_binaire"])   # "STOCKER" ou "VENDRE IMMÉDIATEMENT"
print(f"Marge estimée : {stockage['marge_nette_cfa']:,.0f} XOF")
print(f"Horizon : {stockage['horizon_mois']} mois")
```

### 4. Optimisation de portefeuille de cultures

```python
decision_port = marche.decision_support.portfolio_optimization(
    available_land_ha=10.0,
    climate_forecast={"drought_severity": "mild"},
    market_forecast={"maize": 285.0, "cowpea": 580.0, "sorghum": 210.0},
)

print(f"Méthode : {decision_port['methode']}")   # "scipy_linprog" ou "heuristique"
print(f"Revenu attendu : {decision_port['revenu_attendu_cfa']:,.0f} XOF")
for culture, ha in decision_port["repartition_hectares"].items():
    print(f"  {culture} : {ha:.1f} ha")
```

### 5. Évaluation du risque climatique

```python
# Disponible uniquement si weather_session a été fourni
risque = marche.assess_climate_risk(days_ahead=7)

if risque["weather_available"]:
    print(risque["recommendation"])
    print(f"Pluie demain : {risque['prob_pluie_j1'] * 100:.0f}%")
    print(f"Sécheresse : {risque['drought_severity']}")
```

---

## Comportement sans clé API WFP

Sans clé API, le module fonctionne entièrement avec des données simulées. Cela
permet de développer et tester toute la logique sans dépendance réseau.

| Indicateur | Valeur sans clé |
|------------|----------------|
| `is_simulated` | `True` |
| `confidence_score` | `0.1` |
| `source` | `"simulated"` |

Dès qu'une clé WFP est fournie dans `.env`, les données réelles remplacent
automatiquement les données simulées.

---

## Sous-modules

- [Tarification (pricing)](pricing.md)
- [Prévisions (forecasting)](forecasting.md)
- [Logistique](logistics.md)
- [Aide à la décision](decision_support.md)
- [Ingestion des données](data_ingestion.md)
