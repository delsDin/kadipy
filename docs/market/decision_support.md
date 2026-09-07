# Aide à la décision (`kadi.market.decision_support`)

Le module `Advisor` traduit les données de prix, les prévisions et les
coûts logistiques en recommandations opérationnelles concrètes : faut-il
transporter ? stocker ? et comment répartir ses cultures ?

Chaque recommandation inclut un `confidence_score` (0 à 1)
et le module utilise `scipy.optimize.linprog` pour l'optimisation de portefeuille.

---

## Initialisation

Via la façade `Market` (recommandé : tous les modules sont connectés) :

```python
import kadi as kd

marche = kd.Market(lat=9.30, lon=2.08, location="Parakou")
advisor = marche.advisor  # Module connecté au pricing et à la logistique
```

Ou directement pour des tests :

```python
from kadi.market.decision_support import Advisor

advisor = Advisor(
    forecasting_module=forecasting,
    logistics_module=logistics,
    pricing_module=pricing,
)
```

---

## Score de confiance

Toutes les recommandations incluent un `confidence_score` calculé selon :

```
score = 0.5 × confiance_prix
      + 0.3 × (0 si simulé, 1 si réel)
      + 0.2 × min(1, |gain_net| / 30%)
```

| Score | Interprétation |
|-------|----------------|
| 0.0 à 0.3 | Données simulées, à titre indicatif uniquement |
| 0.3 à 0.6 | Données partielles, prudence conseillée |
| 0.6 à 0.8 | Données récentes WFP, recommandation fiable |
| 0.8 à 1.0 | Données fraîches et gain significatif, haute confiance |

---

## Méthodes

### `arbitrage_decision(crop, origine, destination, qty_tons)`

Évalue la rentabilité d'un transfert physique de marchandises entre deux marchés.

```python
decision = advisor.arbitrage_decision(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0,
)

print(decision["recommandation"])
print(f"Gain : {decision['gain_net_percent']:.1f}%")
print(f"Confiance : {decision['confidence_score']:.2f}")
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `crop` | `str` | Code de la culture (ex: `'maize'`) |
| `origine` | `str` | Marché d'achat |
| `destination` | `str` | Marché de vente |
| `qty_tons` | `float` | Quantité à transporter en tonnes |

**Retour :**

| Clé | Type | Description |
|-----|------|-------------|
| `recommandation` | `str` | `'TRANSPORTER'` ou `'NE PAS TRANSPORTER'` |
| `gain_net_total_cfa` | `float` | Gain net total en XOF |
| `gain_net_percent` | `float` | Gain net en % du capital investi |
| `frais_logistiques_total` | `float` | Coûts de transport en XOF |
| `prix_origine_xof_kg` | `float` | Prix d'achat |
| `prix_destination_xof_kg` | `float` | Prix de vente |
| `is_simulated` | `bool` | Vrai si les prix utilisés sont fictifs |
| `confidence_score` | `float` | Score de confiance de 0 à 1 |
| `prob_pluie` | `float` | Probabilité de pluie utilisée par la logistique |

Le seuil de rentabilité minimum est de **10%** (configurable dans `config.py`).

---

### `storage_vs_sell_now(crop, market, current_price, qty_tons, mois_stockage)`

Évalue s'il est plus rentable de stocker ou de vendre immédiatement, en
comparant le prix futur estimé aux coûts de stockage et d'opportunité.

```python
decision_1m = advisor.storage_vs_sell_now(
    crop="yam", market="Abomey",
    current_price=250_000.0, qty_tons=5.0,
    mois_stockage=1,
)
decision_6m = advisor.storage_vs_sell_now(
    crop="yam", market="Abomey",
    current_price=250_000.0, qty_tons=5.0,
    mois_stockage=6,
)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture |
| `market` | `str` | requis | Nom du marché de référence |
| `current_price` | `float` | requis | Prix actuel en XOF/tonne |
| `qty_tons` | `float` | requis | Quantité disponible en tonnes |
| `mois_stockage` | `int` | `3` | Horizon de stockage en mois (configurable) |

**Retour :**

| Clé | Type | Description |
|-----|------|-------------|
| `recommandation_binaire` | `str` | `'STOCKER'` ou `'VENDRE IMMÉDIATEMENT'` |
| `marge_nette_cfa` | `float` | Espérance de gain total en XOF |
| `marge_nette_par_tonne` | `float` | Espérance de gain par tonne |
| `prix_futur_estime` | `float` | Prix prévu à l'horizon (XOF/tonne) |
| `horizon_mois` | `int` | Horizon de stockage effectivement utilisé |
| `is_simulated` | `bool` | `True` si les prévisions de prix proviennent du mode simulé. |
| `confidence_score` | `float` | Score de confiance de 0 à 1 |

---

### `portfolio_optimization(available_land_ha, climate_forecast, market_forecast, rendements_t_ha)`

Optimise la répartition des cultures sur la surface disponible pour maximiser
le revenu attendu.

```python
decision = advisor.portfolio_optimization(
    available_land_ha=10.0,
    climate_forecast={
        "drought_severity": "mild",
        "secheresse_anticipee": False,
    },
    market_forecast={
        "maize": 285.0,
        "cowpea": 580.0,
        "sorghum": 210.0,
    },
)

print(f"Méthode : {decision['methode']}")
print(f"Revenu attendu : {decision['revenu_attendu_cfa']:,.0f} XOF")
for culture, ha in decision["repartition_hectares"].items():
    print(f"  {culture} : {ha:.2f} ha")
```

**Retour :**

| Clé | Type | Description |
|-----|------|-------------|
| `repartition_hectares` | `dict` | Hectares alloués par culture |
| `revenu_attendu_cfa` | `float` | Revenu total attendu en XOF |
| `recommandation` | `str` | Message explicatif |
| `methode` | `str` | `'scipy_linprog'` ou `'heuristique'` |
| `confidence_score` | `float` | Score de confiance de 0 à 1 |

---

::: kadi.market.decision_support.Advisor

