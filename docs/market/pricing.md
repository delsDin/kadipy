# Tarification (`kadi.market.pricing`)

Le module `MarketPricing` gère l'ingestion, la normalisation et la détection
d'anomalies sur les données de prix agricoles. Il constitue la première couche
de traitement des données brutes de l'API WFP DataBridges.

---

## Rôle dans le pipeline

```
API WFP / Simulation
       |
  fetch_prices()          ← Récupère les données brutes
       |
  normalize_unit()        ← Convertit tout en XOF/kg
       |
  detect_anomalies()      ← Repère les flambées anormales
       |
  seasonality()           ← Calcule les 12 indices mensuels
```

---

## Initialisation

```python
from kadi.market.pricing import MarketPricing
from kadi.market.data_ingestion import WFPDataBridgesClient

client = WFPDataBridgesClient()
pricing = MarketPricing(wfp_client=client)
```

Via la façade `Market` (recommandé) :

```python
from kadi.market import Market

marche = Market(lat=9.30, lon=2.08, location="Parakou")
# marche.pricing est un MarketPricing prêt à l'emploi
```

---

## Méthodes

### `fetch_prices(crop, market, days_back)`

Récupère l'historique de prix pour une culture et un marché sur une période donnée.
La source est sélectionnée automatiquement selon la disponibilité.

```python
df = pricing.fetch_prices("maize", "parakou", days_back=90)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture : `'maize'`, `'rice'`, `'cowpea'`, etc. |
| `market` | `str` | requis | Nom du marché en minuscules : `'cotonou'`, `'parakou'` |
| `days_back` | `int` | `365` | Nombre de jours d'historique à récupérer |

**Retour :** `pd.DataFrame` avec les colonnes suivantes :

| Colonne | Type | Description |
|---------|------|-------------|
| `date` | `datetime` | Date de l'observation |
| `price` | `float` | Prix en XOF/kg (normalisé) |
| `unit` | `str` | Unité d'origine (ex: `"KG"`) |
| `is_simulated` | `bool` | `True` si les données sont fictives |
| `source` | `str` | Source : `"wfp-vam"` ou `"simulated"` |
| `confidence_score` | `float` | Score de fiabilité entre 0 et 1 |

---

### `normalize_unit(price, unit, currency)`

Convertit un prix brut vers le standard `XOF/kg`.

```python
# 100 000 XOF par tonne → 100 XOF/kg
prix_kg = pricing.normalize_unit(price=100_000, unit="T", currency="XOF")
```

**Conversions supportées :**

| Unité d'entrée | Facteur de conversion |
|---------------|----------------------|
| `"T"` (tonne) | ÷ 1 000 |
| `"KG"` | × 1 (inchangé) |
| `"100KG"` (sac) | ÷ 100 |
| `"50KG"` (sac) | ÷ 50 |
| Devises étrangères | × taux de change vers XOF |

---

### `detect_anomalies(df)`

Identifie les prix anormaux dans une série temporelle par la méthode du Z-Score.
Un prix est marqué comme anomalie si son écart à la moyenne dépasse 3 fois
l'écart-type (`|Z| > 3`).

```python
df_propre = pricing.detect_anomalies(df_prix)
anomalies = df_propre[df_propre["anomalie"] == True]
print(f"{len(anomalies)} anomalies détectées")
```

Les données des anomalies sont remplacées par interpolation linéaire sur au
maximum 7 jours consécutifs.

---

### `seasonality(historique)`

Calcule les 12 indices saisonniers mensuels sur la série de prix fournie.

```python
df_hist = pricing.fetch_prices("rice", "cotonou", days_back=730)
saisons = pricing.seasonality(historique=df_hist)

print(saisons["mois_pic"])    # Mois où l'indice dépasse 1.05
print(saisons["mois_creux"])  # Mois où l'indice est sous 0.95

for mois, indice in saisons["indices"].items():
    print(f"Mois {mois:02d} : {indice:.2f}")
```

**Retour :**

| Clé | Type | Description |
|-----|------|-------------|
| `indices` | `dict[int, float]` | Indices saisonniers par mois (1=jan … 12=déc) |
| `mois_pic` | `list[int]` | Mois avec indice > 1.05 (prix au-dessus de la moyenne) |
| `mois_creux` | `list[int]` | Mois avec indice < 0.95 (prix sous la moyenne) |
| `prix_moyen_global` | `float` | Prix moyen de référence en XOF/kg |
| `nb_observations` | `int` | Nombre total d'observations utilisées |
| `confiance` | `float` | Score de fiabilité de 0 à 1 |
| `is_simulated` | `bool` | Vrai si les données sous-jacentes sont simulées |

---

## Exemple complet

```python
from kadi.market import Market

marche = Market(lat=6.36, lon=2.41, location="Cotonou")

# Récupération et analyse des prix du riz
resume = marche.price_crop("rice", days_back=180)

print(f"Prix médian  : {resume['prix_median']:.2f} XOF/kg")
print(f"Prix minimum : {resume['prix_min']:.2f} XOF/kg")
print(f"Prix maximum : {resume['prix_max']:.2f} XOF/kg")
print(f"Anomalies    : {resume['nb_anomalies']}")
print(f"Confiance    : {resume['confidence_score']:.2f}")
```

---

## Codes de cultures supportés

| Code | Culture |
|------|---------|
| `maize` | Maïs |
| `rice` | Riz |
| `sorghum` | Sorgho |
| `millet` | Mil |
| `cowpea` | Niébé |
| `soybean` | Soja |
| `yam` | Igname |
| `cassava` | Manioc |
| `tomato` | Tomate |
| `onion` | Oignon |

---

::: kadi.market.pricing.MarketPricing
