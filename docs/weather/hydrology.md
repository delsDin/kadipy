# Hydrologie (`kadi.weather.hydrology`)

Le module `Hydrology` modélise le cycle de l'eau dans le sol selon les normes
de la FAO (publication FAO-56). Il calcule l'évapotranspiration de référence
(ET0) par la méthode Hargreaves-Samani et simule le bilan hydrique journalier.

---

## Évapotranspiration de référence (ET0)

L'ET0 représente la quantité d'eau évaporée et transpirée par une surface de
gazon bien alimentée en eau. C'est la référence à partir de laquelle on calcule
les besoins en eau de chaque culture (ETc = ET0 × Kc).

### Méthode Hargreaves-Samani

Cette méthode ne demande que les températures min et max, ce qui la rend
utilisable même quand le rayonnement solaire n'est pas disponible.

**Formule :**
```
ET0 = 0.0023 × Ra × (T_moy + 17.8) × (T_max - T_min)^0.5
```

Où `Ra` est le rayonnement extraterrestre (MJ/m²/jour), calculé à partir
de la latitude et du jour de l'année.

```python
et0 = session.et0_hargreaves(tmin=22.0, tmax=35.0, day_of_year=200)
print(f"ET0 : {et0:.2f} mm/jour")
```

---

## Bilan hydrique (FAO-56)

Le bilan hydrique suit l'eau disponible dans le sol au fil du temps, en
tenant compte des apports (pluie) et des pertes (évapotranspiration,
ruissellement).

**Équation journalière :**
```
ΔRU = Pluie - ETc - Ruissellement
RU_j+1 = max(0, min(RU_j + ΔRU, RU_max))
```

Où :
- `RU` = Réserve Utile en eau du sol (mm)
- `ETc` = Évapotranspiration de la culture = ET0 × Kc
- `RU_max` = Capacité maximale de rétention du sol

### Types de sols béninois supportés

| Code | Nom | RU max (mm) | Ksat (mm/h) |
|------|-----|-------------|-------------|
| `ferrugineux` | Sol ferrugineux tropical | 80 | 15 |
| `vertisol` | Vertisol argileux | 120 | 5 |
| `hydromorphe` | Sol hydromorphe | 150 | 2 |
| `sableux` | Sol sableux | 50 | 40 |

---

## Utilisation

### Bilan hydrique complet

```python
from kadi.weather import WeatherSession

session = WeatherSession(latitude=9.3333, longitude=2.6333, name="Parakou")

# Bilan hydrique pour le maïs sur sol ferrugineux
bilan = session.water_balance(crop="maize", soil_type="ferrugineux")

# Affichage des 14 derniers jours
print(bilan.tail(14)[[
    "precipitation", "ET0", "ETc", "deficit_eau", "reserve_utile", "runoff"
]])
```

### Interprétation des résultats

```python
import pandas as pd

# Jours en situation de stress hydrique (déficit > 5 mm)
stress = bilan[bilan["deficit_eau"] > 5.0]
print(f"Jours de stress hydrique : {len(stress)}")

# Calcul du déficit cumulé sur la saison
deficit_cumule = bilan["deficit_eau"].sum()
print(f"Déficit hydrique cumulé : {deficit_cumule:.1f} mm")

# Période critique (réserve utile < 20% de la capacité)
ru_max = 80  # mm pour sol ferrugineux
periode_critique = bilan[bilan["reserve_utile"] < ru_max * 0.2]
print(f"Jours critiques : {len(periode_critique)}")
```

### ET0 journalier direct

```python
# Calcul de l'ET0 pour un jour spécifique de l'année
# Jour 200 = 19 juillet (pic de saison des pluies)
et0_juillet = session.et0_hargreaves(
    tmin=22.0,
    tmax=35.0,
    day_of_year=200,
)
print(f"ET0 mi-juillet : {et0_juillet:.2f} mm/jour")

# Jour 365 = 31 décembre (saison sèche)
et0_decembre = session.et0_hargreaves(
    tmin=18.0,
    tmax=38.0,
    day_of_year=365,
)
print(f"ET0 fin décembre : {et0_decembre:.2f} mm/jour")
```

---

## Colonnes du DataFrame de bilan hydrique

| Colonne | Unité | Description |
|---------|-------|-------------|
| `precipitation` | mm | Précipitations journalières observées |
| `temperature_min` | °C | Température minimale |
| `temperature_max` | °C | Température maximale |
| `ET0` | mm | Évapotranspiration de référence (Hargreaves) |
| `Kc` | — | Coefficient cultural de la culture sélectionnée |
| `ETc` | mm | Évapotranspiration de la culture = ET0 × Kc |
| `deficit_eau` | mm | Manque d'eau journalier (max(0, ETc - Pluie)) |
| `reserve_utile` | mm | Eau disponible dans la réserve utile du sol |
| `runoff` | mm | Eau non infiltrée (ruissellement) |

---

## Perspectives

La version actuelle utilise Hargreaves-Samani, méthode robuste ne nécessitant
que les températures. La méthode Penman-Monteith (FAO-56 complète) sera
intégrée dans une version future en exploitant le rayonnement solaire et la
vitesse du vent disponibles via Open-Meteo.

---

::: kadi.weather.hydrology.Hydrology
