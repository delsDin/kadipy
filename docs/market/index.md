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
├── data_ingestion   : Client WFP + cache SQLite
├── pricing          : Pricing (analyse des prix, anomalies, saisonnalité)
├── forecasting      : Forecasting (prévisions par régression)
├── logistics        : Logistics (distances, coûts de transport, météo)
└── advisor          : Advisor (arbitrage, stockage, portefeuille)
```

Chaque sous-module peut être utilisé seul ou via la façade `Market`.

---

## Initialisation

```python
import kadi as kd

# Initialisation simple
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou")

# Avec intégration météo
weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `lat` | `float` | Latitude (entre 2.5° et 12.5° N) |
| `lon` | `float` | Longitude (entre -1.5° et 4.0° E) |
| `location` | `str` | Nom du marché (ex: `"Cotonou"`, `"Parakou"`) |
| `env_file` | `str` | Chemin vers le fichier `.env` (Défaut : `".env"`) |
| `weather` | `Weather` | Instance météo optionnelle pour l'ajustement climatique |

---

## Exemples complets

### 1. Prix du marché

```python
# Résumé statistique des prix du maïs sur 90 jours
resume = marche.price_crop("maize", days_back=90)

print(f"Médiane : {resume['prix_median']} XOF/kg")
print(f"Tendance : {resume['prix_min']} à {resume['prix_max']} XOF/kg")
print(f"Données : {'simulées' if resume['is_simulated'] else 'réelles WFP'}")
print(f"Confiance : {resume['confidence_score']:.2f}")
```

### 2. Décision d'arbitrage spatial

```python
# "Est-il rentable de transporter 10 tonnes de maïs de Parakou à Cotonou ?"
decision = marche.advisor.arbitrage_decision(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0,
)

print(decision["recommandation"])
print(f"Gain net : {decision['gain_net_percent']:.1f}%")
print(f"Confiance : {decision['confidence_score']:.2f}")
```

### 3. Décision de stockage

```python
# "Vaut-il mieux stocker 5 tonnes d'igname pendant 3 mois ou vendre maintenant ?"
stockage = marche.advisor.storage_vs_sell_now(
    crop="yam",
    market="Abomey",
    current_price=250_000.0,
    qty_tons=5.0,
    mois_stockage=3,
)

print(stockage["recommandation_binaire"])
print(f"Marge estimée : {stockage['marge_nette_cfa']:,.0f} XOF")
print(f"Horizon : {stockage['horizon_mois']} mois")
```

### 4. Optimisation de portefeuille de cultures

```python
decision_port = marche.advisor.portfolio_optimization(
    available_land_ha=10.0,
    climate_forecast={"drought_severity": "mild"},
    market_forecast={"maize": 285.0, "cowpea": 580.0, "sorghum": 210.0},
)

print(f"Méthode : {decision_port['methode']}")
print(f"Revenu attendu : {decision_port['revenu_attendu_cfa']:,.0f} XOF")
for culture, ha in decision_port["repartition_hectares"].items():
    print(f"  {culture} : {ha:.1f} ha")
```

### 5. Évaluation du risque climatique

```python
# Disponible si l'instance weather a été fournie
risque = marche.assess_climate_risk(days_ahead=7)

if risque["weather_available"]:
    print(risque["recommendation"])
    print(f"Pluie demain : {risque['prob_pluie_j1'] * 100:.0f}%")
    print(f"Sécheresse : {risque['drought_severity']}")
```

---

## Accès aux données et boucle de fallback

Par défaut, KadiPy interroge l'API publique HAPI HumData (PAM/OCHA) et le cache SQLite local.
Aucune clé commerciale payante n'est nécessaire pour obtenir des données réelles de prix.

| Niveau | Source | `is_simulated` | `confidence_score` |
|--------|--------|----------------|-------------------|
| 1 | Cache SQLite local | `False` | Variable (score d'origine) |
| 2 | API HAPI HumData / VAM (PAM) | `False` | `0.9` |
| 3 | API WFP DataBridges (si clé `.env`) | `False` | `1.0` |
| 4 | Mode simulation (hors-ligne uniquement) | `True` | `0.1` |

En cas de coupure de réseau ou d'indisponibilité complète des serveurs distants, le module bascule automatiquement sur le mode simulation avec `is_simulated=True`.

---

## Sous-modules

- [Tarification (pricing)](pricing.md)
- [Prévisions (forecasting)](forecasting.md)
- [Logistique](logistics.md)
- [Aide à la décision](decision_support.md)
- [Ingestion des données](data_ingestion.md)

