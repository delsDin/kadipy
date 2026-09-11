# Risques climatiques (`kadi.weather.risk`)

La classe `Risk` évalue les risques climatiques d'une localisation.
Elle calcule les indices de sécheresse (SPI, Markov, Hurst) et prédit
la probabilité de précipitation à court terme.

Elle est utilisée en interne par la façade `Weather`, mais peut aussi être
instanciée directement pour des analyses spécifiques.

---

## Importation directe

```python
from kadi.weather import Risk
```

---

## Initialisation

`Risk` n'est pas instanciée directement dans le cas courant : la façade
`Weather` la crée automatiquement à la première utilisation d'une méthode
de risque. Elle est alors accessible via `weather.risk`.

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")

# Accès direct au composant Risk après un premier appel
secheresse = weather.drought()
risk = weather.risk   # Instance Risk disponible
```

Pour une instanciation directe :

```python
from kadi.weather import Risk, Location
import pandas as pd

location = Location(lat=9.3, lon=2.3, name="Parakou")

# rainfall : pd.Series journalière indexée par date
# forecast : pd.DataFrame de prévisions météo

risk = Risk(location, rainfall, forecast)
```

**Attributs publics :**

| Attribut | Type | Description |
|----------|------|-------------|
| `location` | `Location` | Localisation associée |
| `rainfall` | `pd.Series` | Série historique de précipitations journalières |
| `forecast` | `pd.DataFrame` | Prévisions météorologiques |

---

## Méthodes

### `drought(method, window)`

Calcule l'indice de sécheresse avec la méthode spécifiée.

```python
# SPI sur une fenêtre de 3 mois
result = risk.drought(method="spi", window=3)
print(f"SPI 3 mois : {result['spi_3month']:.2f}")
print(f"Sévérité   : {result['drought_severity']}")

# Analyse Markov
result = risk.drought(method="markov")
print(f"P(sec|sec) : {result['markov_p_dry']:.2f}")

# Exposant de Hurst
result = risk.drought(method="hurst")
print(f"Hurst      : {result['hurst_exponent']:.2f}")

# Combinaison des trois méthodes
result = risk.drought(method="combined", window=3)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `method` | `str` | `'spi'` | Méthode parmi `'spi'`, `'markov'`, `'hurst'`, `'combined'` |
| `window` | `int` | `3` | Fenêtre d'accumulation en mois (utilisée par le SPI) |

**Retour :** `dict` - Les clés varient selon la méthode :

| Clé | Présente si | Description |
|-----|-------------|-------------|
| `spi_Nmonth` | `spi` ou `combined` | Valeur du SPI pour la fenêtre N |
| `drought_severity` | `spi` ou `combined` | Niveau de sévérité |
| `markov_p_dry` | `markov` ou `combined` | P(sec suivant | jour sec) |
| `hurst_exponent` | `hurst` ou `combined` | Exposant de Hurst H |

**Niveaux de sévérité SPI :**

| SPI | Sévérité |
|-----|----------|
| > 1.0 | `no_drought` (période humide) |
| -1.0 a 1.0 | `mild` (conditions normales) |
| -1.5 a -1.0 | `moderate` |
| < -1.5 | `severe` |

**Exceptions :**

- `ValidationError` : méthode non supportée.

---

### `spi(window)`

Calcule le Standardized Precipitation Index (SPI) selon McKee et al. (1993).

L'algorithme :

1. Calcul du cumul de précipitations sur la fenêtre temporelle.
2. Ajustement d'une loi Gamma sur les cumuls strictement positifs.
3. Correction de masse de probabilité pour les jours sans pluie.
4. Conversion en score SPI via la loi normale inverse.

```python
spi_val = risk.spi(window=3)
print(f"SPI 3 mois : {spi_val:.2f}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `window` | `int` | `3` | Fenêtre d'accumulation en mois |

**Retour :** `float` - Valeur du SPI arrondie à 2 décimales. Vaut `0.0` si
l'écart-type de la série est nul.

**Exceptions :**

- `DataError` : série vide, moins de 30 fenêtres calculées, moins de 10
  cumuls non nuls, ou échec de l'ajustement Gamma.

---

### `markov(thresh)`

Calcule les probabilités de transition de Markov entre jours secs et jours humides.

```python
trans = risk.markov(thresh=1.0)

print(f"P(sec  | sec précédent)    : {trans['p_dry_dry']:.2f}")
print(f"P(pluie | sec précédent)   : {trans['p_dry_wet']:.2f}")
print(f"P(sec  | pluie précédente) : {trans['p_wet_dry']:.2f}")
print(f"P(pluie | pluie précédente): {trans['p_wet_wet']:.2f}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `thresh` | `float` | `1.0` | Seuil en mm pour qualifier un jour de humide |

**Retour :** `dict`

| Clé | Description |
|-----|-------------|
| `p_dry_dry` | P(sec suivant / jour sec) |
| `p_dry_wet` | P(humide suivant / jour sec) |
| `p_wet_dry` | P(sec suivant / jour humide) |
| `p_wet_wet` | P(humide suivant / jour humide) |

**Exceptions :**

- `DataError` : série historique vide.

---

### `hurst(window)`

Calcule l'exposant de Hurst par la méthode de gamme rééchelonnée (R/S).

Un exposant `H > 0.5` indique une persistance climatique (mémoire longue) :
les périodes sèches ou humides ont tendance à se prolonger.

```python
h = risk.hurst(window=1095)
print(f"Exposant de Hurst : {h:.2f}")

if h > 0.5:
    print("Persistance climatique détectée (mémoire longue).")
elif h < 0.5:
    print("Comportement antipersistant.")
else:
    print("Marche aléatoire (pas de mémoire).")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `window` | `int` | `1095` | Taille maximale de la fenêtre d'analyse en jours (environ 3 ans) |

**Retour :** `float` - Exposant H, compris entre `0.01` et `0.99`.
Retourne `0.5` si la série est trop courte pour une régression fiable.

**Exceptions :**

- `DataError` : moins de 100 jours de données.

---

### `rain_prob(days, min_mm)`

Prévoit la probabilité de pluie pour les prochains jours.

Combine deux sources :

- Prévisions Open-Meteo (pondération 70 %).
- Probabilité de transition de Markov sur l'historique local (30 %).

```python
proba = risk.rain_prob(days=3, min_mm=1.0)

print(f"Demain        : {proba['tomorrow'] * 100:.0f} %")
print(f"Dans 2 jours  : {proba['2_days'] * 100:.0f} %")
print(f"Message       : {proba['message']}")
print(f"Recommandation: {proba['recommendation']}")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `days` | `int` | `1` | Nombre de jours à prévoir (1 à 7) |
| `min_mm` | `float` | `1.0` | Seuil de précipitation en mm pour qualifier un jour de humide |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `tomorrow` | `float` | Probabilité de pluie demain (si `days >= 1`) |
| `N_days` | `float` | Probabilité pour le jour N (N >= 2) |
| `message` | `str` | Phrase de synthèse avec le risque maximal |
| `recommendation` | `str` | Recommandation agronomique |

**Recommandations :**

| Risque maximal | Recommandation |
|----------------|----------------|
| > 70 % | Risque de lessivage élevé - repousser les traitements phytosanitaires |
| < 20 % | Conditions sèches attendues - bon moment pour les traitements |
| Autre | Vigilance recommandée pour les opérations au champ |

**Exceptions :**

- `DataError` : données de prévision absentes ou vides.

---

## Méthodes dépréciées

| Ancienne méthode | Remplacée par | Depuis |
|------------------|---------------|--------|
| `drought_index(method, window_months)` | `drought(method, window)` | v1.2.0 |
| `markov_transition(threshold_mm)` | `markov(thresh)` | v1.2.0 |
| `hurst_exponent(window)` | `hurst(window)` | v1.2.0 |
| `rain_probability(days_ahead, min_rainfall_mm)` | `rain_prob(days, min_mm)` | v1.2.0 |

## Attributs dépréciés

| Ancien attribut | Remplacé par | Depuis |
|-----------------|--------------|--------|
| `rainfall_historical` | `rainfall` | v1.2.0 |
| `forecast_data` | `forecast` | v1.2.0 |

---

::: kadi.weather.risk.Risk
