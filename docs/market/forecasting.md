# Prévisions de prix (`kadi.market.forecasting`)

La classe `Forecasting` prédit le prix futur d'une culture à partir de
l'historique de prix. Le modèle est une régression linéaire enrichie de
features saisonnières (harmoniques de Fourier), entraînée à la demande
sur les données fournies. Si l'historique est insuffisant (moins de 20
observations), un fallback simulé clairement signalé est retourné.

---

## Importation directe

```python
from kadi.market import Forecasting
```

---

## Initialisation

`Forecasting` est créée automatiquement par `Market` et accessible via
`market.forecast`. Pour une instanciation directe :

```python
from kadi.market import Forecasting

forecast = Forecasting()
```

Le module n'a pas d'état persistant : le modèle est entraîné à chaque
appel de `predict()` sur les données fournies.

---

## Méthodes

### `predict(crop, market, ahead, ci, hist)`

Prédit le prix futur d'une culture sur un marché donné.

**Pipeline interne :**

1. Validation de l'historique (minimum 20 points). Si insuffisant,
   bascule sur le fallback simulé.
2. Construction des features : tendance linéaire + 2 harmoniques de
   Fourier (annuelle et semi-annuelle sur 365/182.5 jours).
3. Entraînement d'une régression linéaire sur l'historique complet.
4. Calcul du RMSE par validation croisée temporelle (TimeSeriesSplit,
   3 folds).
5. Calcul de l'intervalle de prévision basé sur le RMSE réel, avec
   croissance en racine carrée du temps.

```python
import kadi as kd

marche = kd.Market(lat=9.3, lon=2.3, location="Parakou")

# Récupération de l'historique
df = marche.pricing.fetch("maize", "parakou", days=365)

# Prévision à 30 jours avec intervalle de confiance 90%
prev = marche.forecast.predict(
    crop="maize",
    market="parakou",
    ahead=30,
    ci=0.9,
    hist=df,
)

print(f"Prix prédit  : {prev['predicted_price']:.2f} XOF/kg")
print(f"Intervalle   : [{prev['low_90']:.2f}, {prev['high_90']:.2f}]")
print(f"RMSE         : {prev['rmse']} XOF/kg")
print(f"Modèle       : {prev['model_used']}")
print(f"Historique   : {prev['nb_history_pts']} points")
print(f"Simulé       : {prev['is_simulated']}")
print(f"Confiance    : {prev['confidence_score']:.2f}")
```

Via la façade Market (pipeline complet en un seul appel) :

```python
# Market.predict() gère automatiquement la récupération de l'historique
prev = marche.predict("maize", ahead=30, confidence_interval=0.9, days=365)

print(f"Prix prédit dans 30j : {prev['predicted_price']} XOF/kg")
print(f"Horizon utilisé      : {prev['ahead']} jours")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture (ex: `'maize'`) |
| `market` | `str` | requis | Nom normalisé du marché (ex: `'cotonou'`) |
| `ahead` | `int` | `7` | Horizon de prévision en jours |
| `ci` | `float` | `0.9` | Niveau de confiance : `0.9` (90%) ou `0.95` (95%) |
| `hist` | `pd.DataFrame` | `None` | Historique avec colonnes `'date'` et `'price'` |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `predicted_price` | `float` | Prix predit en XOF/kg |
| `low_90` | `float` | Borne inferieure de l'intervalle de confiance |
| `high_90` | `float` | Borne superieure de l'intervalle de confiance |
| `confidence` | `float` | Niveau de confiance utilise (0.9 ou 0.95) |
| `model_used` | `str` | `'linear_regression_fourier'` ou `'fallback_simule'` |
| `rmse` | `float` | RMSE en XOF/kg (None si fallback simule) |
| `is_simulated` | `bool` | True si les donnees source sont simulees |
| `confidence_score` | `float` | Score de fiabilite (0.0 a 1.0) |
| `nb_history_pts` | `int` | Nombre de points d'historique utilises |
| `days_ahead` | `int` | Horizon de prevision utilise |

**Score de confiance :**

Le score de confiance est calculé selon :

```
score_source = 0.10 si is_simulated, 0.85 sinon
facteur_volume = min(1.0, nb_pts / 100.0)
confidence_score = score_source * (0.5 + 0.5 * facteur_volume)
```

Un score de `0.85` est le maximum atteignable avec des données réelles.
Un score de `0.0` indique un fallback entièrement simulé.

**Fallback simulé :**

Activé si `hist` est absent ou contient moins de 20 observations valides.
Retourne `predicted_price=300.0` XOF/kg avec `is_simulated=True` et
`confidence_score=0.0`. Ne pas utiliser pour des décisions commerciales.

---

## Méthode dépréciée

| Ancienne méthode | Remplacée par | Depuis |
|------------------|---------------|--------|
| `predict_price(crop, market, days_ahead, historique)` | `predict(crop, market, ahead, hist)` | v1.2.0 |

## Classe dépréciée

| Ancien nom | Remplacé par | Depuis |
|------------|--------------|--------|
| `MarketForecasting` | `Forecasting` | v1.2.0 |

---

::: kadi.market.forecasting.Forecasting
