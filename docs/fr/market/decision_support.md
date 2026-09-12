# Aide à la décision (`kadi.market.decision_support`)

La classe `Advisor` convertit les prévisions de prix et les données de
marché en recommandations opérationnelles : arbitrage spatial entre
marchés, décision de stockage et optimisation du portefeuille de cultures.

Elle est utilisée en interne par la façade `Market` et accessible via
`market.advisor`. Elle peut aussi être instanciée directement.

---

## Importation directe

```python
from kadi.market import Advisor
```

---

## Initialisation

`Advisor` est créée automatiquement par `Market` et est accessible via
`market.advisor`. Pour une instanciation directe :

```python
from kadi.market import Advisor, Forecasting, Logistics, Pricing

advisor = Advisor(
    forecast=Forecasting(),
    logistics=Logistics(),
    pricing=Pricing(),
)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `forecast` | `Forecasting` | `None` | Instance de prévision pour estimer les prix futurs |
| `logistics` | `Logistics` | `None` | Instance logistique pour les coûts de transport |
| `pricing` | `Pricing` | `None` | Instance de tarification pour les prix réels |

Si `pricing` est `None`, les méthodes utilisent un prix de repli de
300 XOF/kg avec `is_simulated=True` et `confidence_score=0.0`.

**Attributs publics :**

| Attribut | Type | Description |
|----------|------|-------------|
| `forecast` | `Forecasting` | Module de prévision de prix |
| `logistics` | `Logistics` | Module logistique |
| `pricing` | `Pricing` | Module de tarification |

---

## Méthodes

### `arbitrage(crop, m_from, to, qty)`

Évalue la rentabilité d'un transfert physique de marchandises entre deux
marchés.

**Formule :**

```
Gain net = (prix_destination - prix_origine) * 1000 * qty - cout_transport
```

Le seuil de rentabilité minimum est configurable dans `config.py`
(clé `logistics.seuil_rentabilite_pct`, défaut : 10%).

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
marche = kd.Market(lat=9.3, lon=2.3, location="Parakou", weather=weather)

# Est-il rentable de transporter 10 t de maïs de Parakou à Cotonou ?
decision = marche.advisor.arbitrage(
    crop="maize",
    m_from="Parakou",
    to="Cotonou",
    qty=10.0,
)

print(decision["recommandation"])           # 'TRANSPORTER' ou 'NE PAS TRANSPORTER'
print(f"Gain net total : {decision['gain_net_total_cfa']:,.0f} XOF")
print(f"Gain net       : {decision['gain_net_percent']:.1f} %")
print(f"Transport      : {decision['frais_logistiques_total']:,.0f} XOF")
print(f"Pluie prévue   : {decision['prob_pluie'] * 100:.0f} %")
print(f"Confiance      : {decision['confidence_score']:.2f}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture (ex: `'maize'`) |
| `m_from` | `str` | `'Parakou'` | Marché d'achat |
| `to` | `str` | `'Cotonou'` | Marché de vente |
| `qty` | `float` | `1.0` | Quantité à transporter en tonnes métriques |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `recommandation` | `str` | `'TRANSPORTER'` ou `'NE PAS TRANSPORTER'` |
| `gain_net_total_cfa` | `float` | Gain net total en XOF |
| `gain_net_percent` | `float` | Gain net en % du capital investi |
| `frais_logistiques_total` | `float` | Couts de transport totaux en XOF |
| `prix_origine_xof_kg` | `float` | Prix au marche d'achat en XOF/kg |
| `prix_destination_xof_kg` | `float` | Prix au marche de vente en XOF/kg |
| `is_simulated` | `bool` | True si les prix utilises sont fictifs |
| `confidence_score` | `float` | Score de confiance de la recommandation (0-1) |
| `prob_pluie` | `float` | Probabilite de pluie utilisee pour la logistique |

**Score de confiance :**

Calculé comme une combinaison pondérée de trois facteurs :

```
score = 0.5 * price_confidence
      + 0.3 * (0 si simulé, 1 si réel)
      + 0.2 * min(1, |gain_net_pct| / 30)
```

**Exceptions :**

Aucune exception levée en cas d'absence de données : la méthode retourne
un prix de repli de 300 XOF/kg avec `is_simulated=True`.

---

### `store_sell(crop, market, price, qty, months)`

Évalue s'il est plus rentable de stocker une récolte ou de la vendre
immédiatement.

**Formule d'espérance de gain nette par tonne :**

```
E = E[P(t+n)] - P(t) - C_stockage(n) - C_opportunite(n) - theta * Var(P)
```

Où :
- `C_stockage` = 3 200 XOF/tonne/mois (gardiennage, pertes, sacs)
- `C_opportunite` = 1.5%/mois du prix actuel (immobilisation de trésorerie)
- `theta` = 0.04 (coefficient d'aversion au risque)

```python
# Stocker 5 t d'igname pendant 3 mois ou vendre maintenant ?
stockage = marche.advisor.store_sell(
    crop="yam",
    market="Abomey",
    price=250_000.0,    # Prix actuel en XOF/tonne
    qty=5.0,
    months=3,
)

print(stockage["recommandation_binaire"])   # 'STOCKER' ou 'VENDRE IMMÉDIATEMENT'
print(f"Marge nette totale   : {stockage['marge_nette_cfa']:,.0f} XOF")
print(f"Marge par tonne      : {stockage['marge_nette_par_tonne']:,.0f} XOF")
print(f"Prix futur estimé    : {stockage['prix_futur_estime']:,.0f} XOF/tonne")
print(f"Horizon              : {stockage['horizon_mois']} mois")
print(f"Confiance            : {stockage['confidence_score']:.2f}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture |
| `market` | `str` | `'Parakou'` | Marche de référence pour la prévision |
| `price` | `float` | `300000.0` | Prix actuel en XOF par tonne |
| `qty` | `float` | `1.0` | Quantité en tonnes |
| `months` | `int` | `None` | Horizon de stockage en mois. Si None, lit la valeur de config.py (défaut : 3 mois) |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `recommandation_binaire` | `str` | `'STOCKER'` ou `'VENDRE IMMEDIATEMENT'` |
| `marge_nette_cfa` | `float` | Esperance de gain total en XOF |
| `marge_nette_par_tonne` | `float` | Esperance de gain par tonne |
| `prix_futur_estime` | `float` | Prix prevu a l'horizon (XOF/tonne) |
| `horizon_mois` | `int` | Horizon de stockage utilise |
| `is_simulated` | `bool` | True si les donnees de prevision sont simulees |
| `confidence_score` | `float` | Score de confiance (0-1) |

Si aucun module `forecast` n'est disponible, la méthode applique une
hypothèse conservative de hausse de 15% sur le prix actuel.

---

### `optimize(land_ha, climate, market, yields)`

Optimise la répartition des cultures sur la surface disponible.

Utilise `scipy.optimize.linprog` (méthode HiGHS) pour maximiser le
revenu attendu sous contraintes de surface et de diversification. Si
scipy n'est pas disponible, un fallback heuristique est appliqué.

**Modèle d'optimisation :**

```
Maximiser : sum(prix_i * rendement_i * x_i)
Sous       : sum(x_i) <= land_ha
             0 <= x_i <= 0.7 * land_ha  (diversification minimale 30%)
```

**Ajustements climatiques (clé `drought_severity`) :**

| Severite | Effet |
|----------|-------|
| `'severe'` | rendement niébé * 1.3, maïs et riz * 0.7 |
| `'moderate'` | rendement maïs * 0.85 |
| `'mild'` ou `'no_drought'` | pas d'ajustement |

```python
# Optimisation avec conditions climatiques modérées
decision_port = marche.advisor.optimize(
    land_ha=10.0,
    climate={"drought_severity": "mild"},
    market={"maize": 285.0, "cowpea": 580.0, "sorghum": 210.0},
)

print(f"Méthode        : {decision_port['methode']}")
print(f"Revenu attendu : {decision_port['revenu_attendu_cfa']:,.0f} XOF")
print(f"Confiance      : {decision_port['confidence_score']:.2f}")
for culture, ha in decision_port["repartition_hectares"].items():
    print(f"  {culture} : {ha:.1f} ha")

# Cas de sécheresse sévère (favorise le niébé)
decision_sec = marche.advisor.optimize(
    land_ha=5.0,
    climate={"drought_severity": "severe"},
    market={"maize": 285.0, "cowpea": 620.0, "sorghum": 210.0},
)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `land_ha` | `float` | `1.0` | Surface arable disponible en hectares |
| `climate` | `dict` | `None` | Prévisions climatiques (voir tableau ci-dessous) |
| `market` | `dict` | `None` | Prix médians actuels par culture en XOF/kg |
| `yields` | `dict` | `None` | Rendements attendus en t/ha. Si None, utilise les rendements de référence FAO/INSAE Bénin |

**Clés de `climate` :**

| Clé | Type | Description |
|-----|------|-------------|
| `drought_severity` | `str` | Severite : `'no_drought'`, `'mild'`, `'moderate'`, `'severe'` |
| `secheresse_anticipee` | `bool` | Rétrocompatibilité V1 : True = severity `'severe'` |
| `prob_pluie_7j` | `float` | Probabilite de pluie sur 7 jours |

**Rendements de référence (FAO/INSAE Bénin) :**

| Culture | Rendement (t/ha) |
|---------|-----------------|
| `maize` | 1.8 |
| `sorghum` | 1.2 |
| `millet` | 1.0 |
| `rice` | 2.5 |
| `cowpea` | 0.7 |
| `soybean` | 1.2 |
| `yam` | 8.0 |
| `cassava` | 12.0 |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `repartition_hectares` | `dict[str, float]` | Surface allouée par culture (ha) |
| `revenu_attendu_cfa` | `float` | Revenu total attendu en XOF |
| `recommandation` | `str` | Texte explicatif de la décision |
| `methode` | `str` | `'scipy_linprog'` ou `'heuristique'` |
| `confidence_score` | `float` | Score de confiance (0.75 conditions normales, 0.55 sécheresse, 0.3 heuristique) |

**Fallback heuristique :**

Activé si scipy est absent ou si aucune culture n'a de prix connu. La
répartition par défaut est : maïs 50%, soja 30%, niébé 20%. En cas de
sécheresse sévère : maïs 30%, soja 30%, niébé 40%.

---

## Méthodes dépréciées

| Ancienne méthode | Remplacée par | Depuis |
|------------------|---------------|--------|
| `arbitrage_decision(crop, origine, destination, qty_tons)` | `arbitrage(crop, m_from, to, qty)` | v1.2.0 |
| `storage_vs_sell_now(crop, market, current_price, qty_tons, mois_stockage)` | `store_sell(crop, market, price, qty, months)` | v1.2.0 |
| `portfolio_optimization(available_land_ha, climate_forecast, market_forecast)` | `optimize(land_ha, climate, market)` | v1.2.0 |

## Classe dépréciée

| Ancien nom | Remplacé par | Depuis |
|------------|--------------|--------|
| `DecisionSupport` | `Advisor` | v1.2.0 |

---

::: kadi.market.decision_support.Advisor
