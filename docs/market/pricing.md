# Tarification (`kadi.market.pricing`)

La classe `Pricing` gère l'acquisition, la normalisation et l'analyse
des données de prix de marché agricole au Bénin. Elle est utilisée en
interne par la façade `Market`, mais peut aussi être instanciée directement.

---

## Importation directe

```python
from kadi.market import Pricing
```

---

## Initialisation

`Pricing` est créée automatiquement par la façade `Market` et est
accessible via `market.pricing`. Pour une instanciation directe :

```python
from kadi.market import Pricing

# Sans client (mode simulation automatique)
pricing = Pricing()

# Avec client WFP et taux de change dynamiques
from kadi._sources import WFPClient, ExchangeRateClient
pricing = Pricing(
    wfp=WFPClient(),
    exchange=ExchangeRateClient(),
    sim=False,
)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `wfp` | `WFPClient` | `None` | Client WFP pour l'API HAPI HumData |
| `exchange` | `ExchangeRateClient` | `None` | Client de taux de change dynamiques |
| `sim` | `bool` | `False` | Si True, force le mode simulation pour toutes les méthodes |

**Attributs publics :**

| Attribut | Type | Description |
|----------|------|-------------|
| `client` | `WFPClient` | Client WFP injecté (ou None) |
| `sim` | `bool` | Mode simulation actif |

---

## Méthodes

### `fetch(crop, market, days, sim)`

Récupère les prix historiques d'une culture sur un marché.

En mode réel, interroge l'API HAPI HumData. En mode simulation (aucun
client configuré ou `sim=True`), génère des prix fictifs par distribution
normale centrée sur 300 XOF/kg, clairement marqués `sim=True` et
`confidence_score=0.1`.

```python
import kadi as kd

marche = kd.Market(lat=9.3, lon=2.3, location="Parakou")

# Récupération de l'historique (données réelles ou simulées)
df = marche.pricing.fetch("maize", "parakou", days=365)

print(df.dtypes)
print(df.tail(5))
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `crop` | `str` | requis | Code de la culture (ex: `'maize'`, `'rice'`) |
| `market` | `str` | requis | Nom normalisé du marché (ex: `'cotonou'`) |
| `days` | `int` | `365` | Nombre de jours d'historique |
| `sim` | `bool` | `None` | Surcharge le mode de l'instance |

**Retour :** `pd.DataFrame`

| Colonne | Type | Description |
|---------|------|-------------|
| `date` | `datetime` | Date de l'observation |
| `price` | `float` | Prix en XOF/kg |
| `unit` | `str` | Unité d'origine (ex: `'XOF/kg'`) |
| `sim` | `bool` | True si donnée fictive |
| `source` | `str` | Identifiant de la source |
| `fetched_at` | `str` | Horodatage ISO 8601 de la collecte |
| `confidence_score` | `float` | Score de confiance (0.0 a 1.0) |

---

### `convert_unit(value, unit, crop)`

Convertit une valeur de prix vers l'unité standard XOF/kg.

```python
# XOF/Tonne -> XOF/kg
prix_kg = marche.pricing.convert_unit(180_000.0, "XOF/Tonne")
print(f"{prix_kg:.2f} XOF/kg")   # 180.0 XOF/kg

# USD/kg -> XOF/kg (taux de change Frankfurter)
prix_kg = marche.pricing.convert_unit(0.45, "USD/kg")

# XOF/sac (poids depend de la culture)
prix_kg = marche.pricing.convert_unit(14_000.0, "XOF/sac", crop="maize")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `value` | `float` | requis | Valeur du prix à convertir |
| `unit` | `str` | requis | Unité d'origine |
| `crop` | `str` | `None` | Code de la culture (pour les poids de contenants) |

**Unités supportées :**

| Unité | Conversion |
|-------|------------|
| `XOF/kg` | Pas de conversion (unité cible) |
| `XOF/Tonne` | Division par 1000 |
| `USD/kg` | Multiplication par le taux USD/XOF |
| `EUR/kg` | Multiplication par le taux EUR/XOF (fixe UEMOA) |
| `XOF/sac` | Division par le poids du sac (culture-dépendant) |
| `XOF/boisseau`, `XOF/tine`, `XOF/caisse` | Division par le poids du contenant |

Si l'unité est inconnue, la valeur est retournée sans modification.

**Retour :** `float` - Prix en XOF/kg.

---

### `anomalies(series, z)`

Détecte les anomalies dans une série de prix par la méthode du Z-score.

```python
df = marche.pricing.fetch("rice", "cotonou", days=180)
df = marche.pricing.anomalies(df, z=3.0)

nb = df["is_anomaly"].sum()
print(f"Anomalies détectées : {nb}")
print(df[df["is_anomaly"]][["date", "price"]])
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `series` | `pd.DataFrame` | requis | DataFrame avec une colonne `'price'` |
| `z` | `float` | `3.0` | Seuil du Z-score (3 = 99.7% de la distribution) |

**Retour :** `pd.DataFrame` - DataFrame d'entrée avec une colonne
booléenne `is_anomaly` ajoutée.

---

### `fill_gaps(series, max_gap)`

Comble les valeurs manquantes dans une série de prix par interpolation
linéaire, limitée à un nombre configurable de jours consécutifs.

```python
df = marche.pricing.fetch("sorghum", "natitingou", days=365)
df = marche.pricing.fill_gaps(df, max_gap=7)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `series` | `pd.DataFrame` | requis | DataFrame avec une colonne `'price'` |
| `max_gap` | `int` | `7` | Nombre maximum de jours à interpoler |

Les trous de plus de `max_gap` jours consécutifs restent `NaN`.

**Retour :** `pd.DataFrame` - DataFrame avec les trous courts comblés.

---

### `source(series)`

Identifie la source des données d'une série de prix.

```python
df = marche.pricing.fetch("maize", "parakou", days=90)
src = marche.pricing.source(df)
print(f"Source : {src}")   # 'wfp-vam' ou 'simulated'
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `series` | `pd.DataFrame` | DataFrame retourné par `fetch()` |

**Retour :** `str` - `'wfp-vam'`, `'ratin'`, `'scrape-local'` ou
`'simulated'`.

---

### `seasonality(historique, min_observations_par_mois)`

Calcule les 12 indices saisonniers mensuels des prix agricoles par la
méthode des ratios.

Un indice supérieur à 1 indique un mois de prix élevés (période de
soudure). Inférieur à 1 indique un mois bon marché (période post-récolte).

```python
df = marche.pricing.fetch("maize", "parakou", days=730)
saison = marche.pricing.seasonality(df)

print(f"Mois de pic   : {saison['mois_pic']}")
print(f"Mois de creux : {saison['mois_creux']}")
print(f"Prix moyen    : {saison['prix_moyen_global']:.2f} XOF/kg")
print(f"Confiance     : {saison['confiance']:.2f}")

# Indice par mois
for mois, indice in saison["indices"].items():
    if indice:
        print(f"  Mois {mois:2d} : {indice:.3f}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `historique` | `pd.DataFrame` | requis | DataFrame avec colonnes `'date'` et `'price'` |
| `min_observations_par_mois` | `int` | `2` | Observations minimales pour inclure un mois |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `indices` | `dict[int, float]` | Indices saisonniers par mois (1 a 12). None si données insuffisantes |
| `mois_pic` | `list[int]` | Mois dont l'indice depasse 1.05 (5% au-dessus de la moyenne) |
| `mois_creux` | `list[int]` | Mois dont l'indice est sous 0.95 |
| `prix_moyen_global` | `float` | Prix moyen sur toute la periode (XOF/kg) |
| `prix_moyen_par_mois` | `dict[int, float]` | Prix brut moyen par mois |
| `nb_observations` | `int` | Nombre total d'observations valides |
| `nb_mois_couverts` | `int` | Mois avec au moins `min_observations_par_mois` entrees |
| `confiance` | `float` | Score de confiance (0.0 a 1.0) |
| `sim` | `bool` | True si l'historique contient des donnees simulees |
| `message` | `str` | Avertissement si donnees insuffisantes. None sinon |

**Exceptions :**

- `ValueError` : historique vide, ou colonnes `'date'` / `'price'` absentes.

---

## Méthodes dépréciées

| Ancienne méthode | Remplacée par | Depuis |
|------------------|---------------|--------|
| `fetch_prices(crop, market, days_back)` | `fetch(crop, market, days)` | v1.2.0 |
| `normalize_units(value, unit)` | `convert_unit(value, unit)` | v1.2.0 |
| `detect_anomalies(series, threshold)` | `anomalies(series, z)` | v1.2.0 |
| `interpolate_gaps(series, max_gap)` | `fill_gaps(series, max_gap)` | v1.2.0 |
| `get_data_source(series)` | `source(series)` | v1.2.0 |

---

::: kadi.market.pricing.Pricing
