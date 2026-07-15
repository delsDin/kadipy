# Prévisions de prix (`kadi.market.forecasting`)

Le module `MarketForecasting` anticipe l'évolution future des prix agricoles
en combinant un modèle de réseau de neurones (`MLPRegressor`) et une régression
linéaire. Il produit un prix prédit accompagné d'intervalles de confiance.

---

## Principe de fonctionnement

Le modèle s'entraîne sur l'historique des prix d'un marché et d'une culture
donnés. Les caractéristiques (`features`) utilisées pour la prédiction sont :

- Le mois de l'année (saisonnalité)
- Le jour de la semaine
- Le prix médian sur les 7, 14 et 30 derniers jours (inertie du marché)
- Le prix de la même période l'année précédente (effet annuel)

L'incertitude de la prédiction est représentée par le RMSE calculé sur les
données historiques, traduit en intervalles `low_90` et `high_90`.

---

## Initialisation

```python
from kadi.market.forecasting import MarketForecasting

forecasting = MarketForecasting()
```

Via la façade `Market` (recommandé) :

```python
from kadi.market import Market

marche = Market(lat=9.30, lon=2.08, location="Parakou")
# marche.forecasting est un MarketForecasting prêt à l'emploi
```

---

## Méthodes

### `predict_price(crop, market, days_ahead)`

Prédit le prix d'une culture sur un marché donné à un horizon futur.

```python
prevision = forecasting.predict_price(
    crop="maize",
    market="Parakou",
    days_ahead=30,
)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture (ex: `'maize'`) |
| `market` | `str` | requis | Nom du marché (ex: `'Parakou'`) |
| `days_ahead` | `int` | `30` | Horizon de prévision en jours |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `predicted_price` | `float` | Prix prédit en XOF/kg |
| `low_90` | `float` | Borne basse de l'intervalle de confiance à 90% |
| `high_90` | `float` | Borne haute de l'intervalle de confiance à 90% |
| `rmse` | `float` | Erreur quadratique moyenne historique |
| `crop` | `str` | Culture prédite |
| `market` | `str` | Marché de référence |
| `horizon_days` | `int` | Horizon de prévision utilisé |

---

## Exemples

### Prévision simple

```python
from kadi.market import Market

marche = Market(lat=9.30, lon=2.08, location="Parakou")

prevision = marche.forecasting.predict_price("rice", "Parakou", days_ahead=60)

print(f"Prix prévu dans 60 jours : {prevision['predicted_price']:.2f} XOF/kg")
print(f"Fourchette haute         : {prevision['high_90']:.2f} XOF/kg")
print(f"Fourchette basse         : {prevision['low_90']:.2f} XOF/kg")
```

### Prévision via la façade Market

La façade `Market` enrichit la prévision avec le cache SQLite et le contexte
du marché (lieu, date de calcul).

```python
prevision = marche.forecast_price("maize", days_ahead=90)

print(f"Marché     : {prevision['market']}")
print(f"Culture    : {prevision['crop']}")
print(f"Prix prévu : {prevision['predicted_price']:.2f} XOF/kg")
```

### Interprétation des intervalles

```python
prev = marche.forecasting.predict_price("cowpea", "Cotonou", days_ahead=30)

marge = prev['high_90'] - prev['low_90']
print(f"Incertitude sur le prix : ± {marge / 2:.2f} XOF/kg")

if prev['predicted_price'] > prev['rmse'] * 2:
    print("Prévision jugée fiable (signal fort devant le bruit)")
else:
    print("Prévision à prendre avec précaution (données insuffisantes)")
```

---

## Limites et perspectives

Le modèle actuel (V1) convient bien pour un prototype. Il présente les limites
suivantes que les versions futures adresseront :

| Limite | Amélioration envisagée |
|--------|------------------------|
| MLPRegressor généraliste | Modèles LSTM ou Facebook Prophet (séries temporelles) |
| Pas de saisonnalité explicite | Décomposition STL + cycle de soudure béninois |
| Pas de facteurs exogènes | Intégration du SPI et de l'indice de végétation NDVI |

---

::: kadi.market.forecasting.MarketForecasting
