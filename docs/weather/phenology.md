# Phénologie (`kadi.weather.phenology`)

Le module `Phenology` détecte les dates clés du cycle agricole (début et fin
de saison des pluies) et calcule les degrés-jours de croissance (GDD) pour
évaluer le stade phénologique des cultures.

---

## Algorithmes de détection de saison

Le Bénin présente deux régimes pluviométriques distincts. Le module choisit
l'algorithme adapté automatiquement selon la latitude.

### Régime unimodal — Nord (> 9.5° N) : Sivakumar

L'algorithme de Sivakumar définit le démarrage de la saison comme le premier
jour après le 1er mai où les précipitations sur 20 jours consécutifs dépassent
la moitié de l'ETP sur cette période, sans séquence sèche de plus de 7 jours.

**Critère de déclenchement :**
```
P_20j ≥ ETP_20j / 2  ET  max_séquence_sèche < 7 jours
```

### Régime bimodal — Sud (< 7.5° N) : Walter-Anyadike

L'algorithme de Walter-Anyadike détecte les deux saisons des pluies
caractéristiques du sud du Bénin (grande et petite saison) en analysant
les courbes de précipitations mensuelles lissées.

---

## Degrés-jours de croissance (GDD)

Les GDD mesurent l'énergie thermique accumulée depuis la date de semis. Chaque
culture a des températures de base (`T_base`) et de plateau (`T_max`) propres.

**Formule journalière :**
```
GDD_j = max(0, [(T_min_j + T_max_j) / 2] - T_base)
```

Si la température moyenne dépasse `T_max`, elle est plafonnée à `T_max` pour
éviter de surestimer la croissance.

**Températures de référence par culture :**

| Culture | T_base (°C) | T_max (°C) | GDD floraison | GDD maturité |
|---------|------------|-----------|--------------|-------------|
| Maïs | 10 | 34 | 620 | 1400 |
| Riz | 12 | 38 | 800 | 1600 |
| Sorgho | 10 | 34 | 700 | 1350 |
| Mil | 10 | 38 | 600 | 1200 |
| Niébé | 10 | 35 | 550 | 1100 |
| Soja | 10 | 36 | 700 | 1400 |
| Igname | 12 | 35 | 900 | 2000 |

---

## Utilisation via WeatherSession (recommandé)

```python
from kadi.weather import WeatherSession

session = WeatherSession(latitude=9.3333, longitude=2.6333, name="Parakou")

# Démarrage de la saison
onset = session.onset()
print(f"Début estimé : {onset['onset_date']}")
print(f"Méthode      : {onset['method']}")
print(f"Confiance    : {onset['confidence']}")

# Fin de la saison
cessation = session.cessation()
print(f"Fin estimée  : {cessation['cessation_date']}")

# Durée de la saison agricole
from datetime import datetime
debut = datetime.fromisoformat(onset['onset_date'])
fin = datetime.fromisoformat(cessation['cessation_date'])
print(f"Durée de la saison : {(fin - debut).days} jours")
```

---

## Calcul des GDD

```python
# Maïs semé le 15 mai, suivi jusqu'au 30 septembre
gdd = session.growing_degree_days(
    crop="maize",
    start_date="2026-05-15",
    end_date="2026-09-30",
)

print(f"GDD accumulés   : {gdd['gdd_accumulated']:.1f} °C·jour")
print(f"Stade phéno     : {gdd['phenology_stage']}")
print(f"Floraison dans  : {gdd['days_to_flowering']} jours")
print(f"Maturité dans   : {gdd['days_to_maturity']} jours")
```

**Stades phénologiques retournés pour le maïs :**

| Stade | GDD accumulés |
|-------|--------------|
| `germination` | 0 – 100 |
| `tallage` | 100 – 300 |
| `montaison` | 300 – 620 |
| `floraison` | 620 – 900 |
| `grain_remplissage` | 900 – 1 200 |
| `maturite` | > 1 200 |

---

## Interprétation agronomique

Les GDD permettent de planifier :

- **La date optimale de semis** pour maximiser l'utilisation des pluies.
- **La date de récolte estimée** pour anticiper le stockage.
- **Le risque de fin de cycle prématurée** si la cessation arrive avant la
  maturité de la culture.

```python
# Vérifier si la saison est assez longue pour la maturité du maïs
gdd_maturite_maize = 1400  # °C·jour

if gdd["gdd_accumulated"] < gdd_maturite_maize:
    manque = gdd_maturite_maize - gdd["gdd_accumulated"]
    print(f"Risque : il manque {manque:.0f} GDD pour la maturité complète.")
```

---

::: kadi.weather.phenology.Phenology
