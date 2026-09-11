# kadi.market - Économie agricole

Le module `kadi.market` est le moteur d'analyse économique de KadiPy. Il
modélise le marché agricole béninois de façon dynamique et permet de
récupérer les prix réels (API HAPI HumData), de prévoir leur évolution,
d'évaluer les coûts logistiques réels et de produire des recommandations
d'arbitrage, de stockage et de portefeuille de cultures.

---

## Architecture

Le module est centré sur la classe `Market`, qui orchestre 4 sous-modules
spécialisés.

```
Market
├── pricing    : Pricing (acquisition, normalisation, anomalies, saisonnalité)
├── forecast   : Forecasting (prévisions par régression linéaire Fourier)
├── logistics  : Logistics (distances OSRM, coûts de transport, intégration météo)
└── advisor    : Advisor (arbitrage spatial, stockage, portefeuille de cultures)
```

Chaque sous-module peut être utilisé seul ou via la façade `Market`.

---

## Importation

```python
import kadi as kd

# Façade principale
from kadi.market import Market

# Sous-modules en accès direct
from kadi.market import Pricing, Forecasting, Logistics, Advisor
```

---

## Initialisation

```python
import kadi as kd

# Initialisation simple (données réelles de l'API HAPI HumData)
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou")

# Mode simulation (aucun appel réseau, données fictives claires)
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", sim=True)

# Avec intégration météo (ajustement dynamique des coûts logistiques)
weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)
```

**Paramètres :**

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lat` | `float` | requis | Latitude (entre 2.5° et 12.5° N) |
| `lon` | `float` | requis | Longitude (entre -1.5° et 4.0° E) |
| `location` | `str` | requis | Nom du marché (ex: `"Cotonou"`, `"Parakou"`) |
| `weather` | `Weather` | `None` | Instance météo pour l'ajustement climatique |
| `sim` | `bool` | `False` | Si True, force le mode simulation (aucune requête réseau) |

**Exceptions à l'initialisation :**

- `TypeError` : si `lat`, `lon` ou `location` ne sont pas du bon type.
- `ValueError` : si les coordonnées sont hors des bornes du Bénin, ou si
  `location` est vide.

---

## Attributs publics

| Attribut | Type | Description |
|----------|------|-------------|
| `lat` | `float` | Latitude de référence |
| `lon` | `float` | Longitude de référence |
| `location` | `str` | Nom du marché de référence |
| `sim` | `bool` | Mode simulation actif |
| `weather` | `Weather` | Session météo (None si non fournie) |
| `pricing` | `Pricing` | Sous-module de tarification |
| `forecast` | `Forecasting` | Sous-module de prévision |
| `logistics` | `Logistics` | Sous-module logistique |
| `advisor` | `Advisor` | Sous-module d'aide à la décision |

---

## Méthodes de la façade Market

### `price(crop, days, normalize, sim)`

Récupère, normalise et résume les prix d'une culture sur ce marché.

```python
resume = marche.price("maize", days=90)

print(f"Médiane     : {resume['prix_median']} XOF/kg")
print(f"Amplitude   : {resume['prix_min']} - {resume['prix_max']} XOF/kg")
print(f"Observations: {resume['nb_observations']}")
print(f"Confiance   : {resume['confidence_score']:.2f}")
print(f"Simulé      : {resume['is_sim']}")
```

**Retour :** `dict` avec les clés `crop`, `market`, `prix_median`,
`prix_min`, `prix_max`, `prix_moyen`, `nb_observations`, `nb_anomalies`,
`is_sim`, `confidence_score`, `source`, `donnees` (DataFrame complet).

---

### `predict(crop, ahead, confidence_interval, days, sim)`

Prédit le prix futur d'une culture par régression linéaire avec features
saisonnières (harmoniques de Fourier).

```python
prev = marche.predict("maize", ahead=30)

print(f"Prix prédit dans 30j : {prev['predicted_price']} XOF/kg")
print(f"Intervalle 90%       : [{prev['low_90']}, {prev['high_90']}]")
print(f"RMSE                 : {prev['rmse']} XOF/kg")
print(f"Points d'historique  : {prev['nb_history_pts']}")
```

**Retour :** `dict` avec `predicted_price`, `low_90`, `high_90`,
`confidence`, `model_used`, `rmse`, `is_sim`, `confidence_score`,
`nb_history_pts`, `ahead`, `crop`, `market`.

---

### `seasonality(crop, days, sim)`

Calcule les 12 indices saisonniers mensuels des prix d'une culture.

```python
saison = marche.seasonality("rice", days=730)

print(f"Mois de pic   : {saison['mois_pic']}")
print(f"Mois de creux : {saison['mois_creux']}")
print(f"Confiance     : {saison['confiance']:.2f}")
```

**Retour :** voir [pricing.md](pricing.md), section `seasonality()`.

---

### `climate_risk(ahead)`

Évalue le risque climatique sur la localisation du marché.
Nécessite qu'une instance `weather` ait été fournie à l'initialisation.

```python
risque = marche.climate_risk(ahead=7)

if risque["weather_available"]:
    print(risque["recommendation"])
    print(f"Pluie demain  : {risque['prob_pluie_j1'] * 100:.0f} %")
    print(f"Sécheresse    : {risque['drought_severity']}")
```

**Retour :** `dict` avec `weather_available`, `prob_pluie`,
`drought_index`, `recommendation`, `prob_pluie_j1`, `drought_severity`.

---

## Exemples complets

### 1. Prix du marché

```python
import kadi as kd

marche = kd.Market(lat=9.30, lon=2.08, location="Parakou")

resume = marche.price("maize", days=90)
print(f"Médiane : {resume['prix_median']} XOF/kg")
print(f"Source  : {resume['source']}")
```

### 2. Arbitrage spatial

```python
# Est-il rentable de transporter 10 t de maïs de Parakou à Cotonou ?
decision = marche.advisor.arbitrage(
    crop="maize",
    m_from="Parakou",
    to="Cotonou",
    qty=10.0,
)
print(decision["recommandation"])
print(f"Gain net : {decision['gain_net_percent']:.1f} %")
print(f"Confiance: {decision['confidence_score']:.2f}")
```

### 3. Décision de stockage

```python
# Stocker 5 t d'igname pendant 3 mois ou vendre maintenant ?
stockage = marche.advisor.store_sell(
    crop="yam",
    market="Abomey",
    price=250_000.0,
    qty=5.0,
    months=3,
)
print(stockage["recommandation_binaire"])
print(f"Marge estimée : {stockage['marge_nette_cfa']:,.0f} XOF")
```

### 4. Optimisation du portefeuille de cultures

```python
decision_port = marche.advisor.optimize(
    land_ha=10.0,
    climate={"drought_severity": "mild"},
    market={"maize": 285.0, "cowpea": 580.0, "sorghum": 210.0},
)
print(f"Méthode        : {decision_port['methode']}")
print(f"Revenu attendu : {decision_port['revenu_attendu_cfa']:,.0f} XOF")
for culture, ha in decision_port["repartition_hectares"].items():
    print(f"  {culture} : {ha:.1f} ha")
```

### 5. Risque climatique

```python
weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)

risque = marche.climate_risk(ahead=7)
print(risque["recommendation"])
```

---

## Modes de données et boucle de fallback

| Niveau | Source | `is_sim` | `confidence_score` |
|--------|--------|----------|--------------------|
| 1 | Cache SQLite local | `False` | Variable (score d'origine) |
| 2 | API HAPI HumData (PAM/OCHA) | `False` | `0.9` |
| 3 | Mode simulation (aucun réseau) | `True` | `0.1` |

En mode simulation (`sim=True` ou absence de client WFP), les données
retournées sont clairement signalées `is_sim=True` et ne doivent pas
être utilisées pour des décisions commerciales réelles.

---

## Méthodes dépréciées

| Ancienne méthode | Remplacée par | Depuis |
|------------------|---------------|--------|
| `price_crop(crop, days_back)` | `price(crop, days)` | v1.2.0 |
| `predict_price(crop, days_ahead)` | `predict(crop, ahead)` | v1.2.0 |
| `assess_climate_risk(days_ahead)` | `climate_risk(ahead)` | v1.2.0 |

## Classes dépréciées

| Ancien nom | Remplacé par | Depuis |
|------------|--------------|--------|
| `MarketPricing` | `Pricing` | v1.2.0 |
| `MarketForecasting` | `Forecasting` | v1.2.0 |
| `MarketLogistics` | `Logistics` | v1.2.0 |
| `DecisionSupport` | `Advisor` | v1.2.0 |

---

## Sous-modules

- [Tarification (Pricing)](pricing.md)
- [Prévisions (Forecasting)](forecasting.md)
- [Logistique (Logistics)](logistics.md)
- [Aide à la décision (Advisor)](decision_support.md)
