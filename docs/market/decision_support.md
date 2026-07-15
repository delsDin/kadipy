# Aide à la décision (`kadi.market.decision_support`)

Le module `DecisionSupport` traduit les données de prix, les prévisions et les
coûts logistiques en recommandations opérationnelles concrètes : faut-il
transporter ? stocker ? et comment répartir ses cultures ?

Depuis la Phase 4, chaque recommandation inclut un `confidence_score` (0 à 1)
et le module utilise `scipy.optimize.linprog` pour l'optimisation de portefeuille.

---

## Initialisation

Via la façade `Market` (recommandé — tous les modules sont connectés) :

```python
from kadi.market import Market

marche = Market(lat=9.30, lon=2.08, location="Parakou")
ds = marche.decision_support  # Module connecté au pricing et à la logistique
```

Ou directement pour des tests :

```python
from kadi.market.decision_support import DecisionSupport

ds = DecisionSupport(
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
| 0.0 – 0.3 | Données simulées, à titre indicatif uniquement |
| 0.3 – 0.6 | Données partielles, prudence conseillée |
| 0.6 – 0.8 | Données récentes WFP, recommandation fiable |
| 0.8 – 1.0 | Données fraîches + gain significatif, haute confiance |

---

## Méthodes

### `arbitrage_decision(crop, market_from, market_to, qty_tons)`

Évalue la rentabilité d'un transfert physique de marchandises entre deux marchés.

```python
decision = ds.arbitrage_decision(
    crop="maize",
    market_from="Parakou",
    market_to="Cotonou",
    qty_tons=10.0,
)

print(decision["recommandation"])        # "TRANSPORTER" ou "NE PAS TRANSPORTER"
print(f"Gain : {decision['gain_net_percent']:.1f}%")
print(f"Confiance : {decision['confidence_score']:.2f}")
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `crop` | `str` | Code de la culture (ex: `'maize'`) |
| `market_from` | `str` | Marché d'achat |
| `market_to` | `str` | Marché de vente |
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
# Horizon configurable (Phase 4)
decision_1m = ds.storage_vs_sell_now(
    crop="yam", market="Abomey",
    current_price=250_000.0, qty_tons=5.0,
    mois_stockage=1,    # Horizon 1 mois
)
decision_6m = ds.storage_vs_sell_now(
    crop="yam", market="Abomey",
    current_price=250_000.0, qty_tons=5.0,
    mois_stockage=6,    # Horizon 6 mois
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
| `is_simulated` | `bool` | Vrai si les prévisions sont fictives |
| `confidence_score` | `float` | Score de confiance de 0 à 1 |

**Composantes du coût de stockage :**

| Composante | Valeur |
|------------|--------|
| Gardiennage, pertes, sacs | 3 200 XOF/tonne/mois |
| Coût d'opportunité | 1.5%/mois du capital immobilisé |
| Pénalité de risque | theta × variance du prix prévu |

---

### `portfolio_optimization(available_land_ha, climate_forecast, market_forecast, rendements_t_ha)`

Optimise la répartition des cultures sur la surface disponible pour maximiser
le revenu attendu.

```python
decision = ds.portfolio_optimization(
    available_land_ha=10.0,
    climate_forecast={
        "drought_severity": "mild",    # 'no_drought', 'mild', 'moderate', 'severe'
        "secheresse_anticipee": False,
    },
    market_forecast={
        "maize": 285.0,    # XOF/kg
        "cowpea": 580.0,
        "sorghum": 210.0,
    },
)

print(f"Méthode : {decision['methode']}")  # 'scipy_linprog' ou 'heuristique'
print(f"Revenu attendu : {decision['revenu_attendu_cfa']:,.0f} XOF")
for culture, ha in decision["repartition_hectares"].items():
    print(f"  {culture} : {ha:.2f} ha")
```

**Modèle d'optimisation linéaire :**

```
Maximiser  : Σ (prix_i × rendement_i × x_i)
Contraintes:
    Σ x_i ≤ surface_totale
    x_i ≥ 0
    x_i ≤ 0.7 × surface_totale  (diversification minimale)
```

**Ajustements climatiques automatiques :**

| Sévérité de sécheresse | Effet sur les rendements |
|------------------------|--------------------------|
| `mild` / `no_drought` | Rendements nominaux |
| `moderate` | Rendement maïs × 0.85 |
| `severe` | Rendement maïs × 0.70, rendement niébé × 1.30 |

**Retour :**

| Clé | Type | Description |
|-----|------|-------------|
| `repartition_hectares` | `dict` | Hectares alloués par culture |
| `revenu_attendu_cfa` | `float` | Revenu total attendu en XOF |
| `recommandation` | `str` | Message explicatif |
| `methode` | `str` | `'scipy_linprog'` ou `'heuristique'` |
| `confidence_score` | `float` | Score de confiance de 0 à 1 |

Si `scipy` n'est pas disponible, un fallback heuristique est utilisé
automatiquement (répartition 50/30/20 maïs/soja/niébé, ajustée en cas de
sécheresse sévère).

---

## Rendements de référence au Bénin

Ces valeurs sont utilisées par défaut dans `portfolio_optimization`. Elles
peuvent être remplacées via le paramètre `rendements_t_ha`.

| Culture | Rendement (t/ha) | Source |
|---------|-----------------|--------|
| Maïs | 1.8 | FAO / INSAE Bénin |
| Sorgho | 1.2 | FAO / INSAE Bénin |
| Mil | 1.0 | FAO / INSAE Bénin |
| Riz | 2.5 | FAO / INSAE Bénin |
| Niébé | 0.7 | FAO / INSAE Bénin |
| Soja | 1.2 | FAO / INSAE Bénin |
| Igname | 8.0 | FAO / INSAE Bénin |
| Manioc | 12.0 | FAO / INSAE Bénin |

---

::: kadi.market.decision_support.DecisionSupport
