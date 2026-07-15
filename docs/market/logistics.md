# Logistique (`kadi.market.logistics`)

Le module `MarketLogistics` modélise les frictions du transport de marchandises
au Bénin : distances routières réelles, coûts en carburant, tracasseries aux
postes de contrôle et perte de qualité des produits. Depuis la Phase 4, il
intègre les prévisions météo pour ajuster ses calculs dynamiquement.

---

## Formule de coût de transfert

```
C_transfer = C_info
           + Distance × (gamma_effectif × P_carburant / 100 + mu_checkpoints)
           + C_qualite(culture, distance, pluie)
```

| Terme | Signification | Source |
|-------|---------------|--------|
| `C_info` | Coût fixe de recherche d'informations | `config.py` |
| `gamma_effectif` | Coefficient d'état des routes (dynamique) | Formule ci-dessous |
| `P_carburant` | Prix de l'essence en XOF/litre | Env, GitHub, repli |
| `mu_checkpoints` | Tracasseries policières par km | `config.py` |
| `C_qualite` | Perte de valeur marchande | Culture × distance × pluie |

### Ajustement météo (Phase 4)

Quand une `weather_session` est fournie :

```
gamma_effectif = gamma_base × (1 + alpha_pluie × prob_pluie)
```

- `gamma_base` = 1.2 (par défaut)
- `alpha_pluie` = 0.25 (majoration max de 25% si pluie certaine)
- `prob_pluie` = probabilité de pluie demain (0.0 à 1.0)

La perte de qualité dépend aussi de la culture et de la pluie :

```
C_qualite = facteur_culture × distance_km × (1 + beta_pluie × prob_pluie)
```

---

## Initialisation

```python
from kadi.market.logistics import MarketLogistics

# Sans météo (comportement V1)
logistics = MarketLogistics()

# Avec météo (Phase 4)
from kadi.weather import WeatherSession

ws = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
logistics = MarketLogistics(weather_session=ws)
```

Via la façade `Market` (recommandé) :

```python
from kadi.market import Market
from kadi.weather import WeatherSession

ws = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
marche = Market(lat=9.30, lon=2.08, location="Parakou", weather_session=ws)
# marche.logistics est un MarketLogistics avec météo injectée
```

---

## Méthodes

### `get_distance(origine, destination)`

Calcule la distance routière entre deux villes béninoises. Utilise OSRM pour
la vraie distance de conduite. Les résultats sont mis en cache dans
`~/.kadi/osrm_cache.json`.

```python
km = logistics.get_distance("Parakou", "Cotonou")
print(f"Distance réelle : {km:.1f} km")
```

**Stratégie de résolution :**

1. Cache local (évite les appels réseau répétés)
2. Géocodage Nominatim → routage OSRM
3. Fallback Haversine × 1.3 si OSRM est indisponible
4. 100 km par défaut si le géocodage échoue

---

### `calculate_transfer_cost(origine, destination, prix_carburant, crop)`

Calcule le coût total de transport d'un point A vers un point B.

```python
cout = logistics.calculate_transfer_cost(
    origine="Parakou",
    destination="Cotonou",
    crop="tomato",       # Optionnel — active la perte de qualité par culture
)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `origine` | `str` | requis | Ville de départ |
| `destination` | `str` | requis | Ville d'arrivée |
| `prix_carburant` | `float` | `None` | Prix de l'essence en XOF/litre (auto-récupéré si None) |
| `crop` | `str` | `None` | Culture transportée (influence la perte de qualité) |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `total_cost_cfa` | `float` | Coût total du transfert en XOF |
| `prob_pluie` | `float` | Probabilité de pluie utilisée (0 si sans météo) |
| `gamma_effectif` | `float` | Coefficient de route réellement appliqué |
| `details` | `dict` | Détail de chaque composante du coût |

**Détail du résultat :**

```python
# Exemple de retour complet
{
    "total_cost_cfa": 47_350.0,
    "prob_pluie": 0.82,
    "gamma_effectif": 1.446,
    "details": {
        "distance_km": 415.2,
        "search_costs": 5000.0,
        "transport_costs": 38_200.0,
        "quality_loss": 4150.0,
        "fuel_price_used": 680.0,
        "gamma_route_base": 1.2,
        "gamma_effectif": 1.446,
        "prob_pluie": 0.82,
        "crop": "tomato",
    }
}
```

---

## Facteurs de perte de qualité par culture

| Culture | Facteur (XOF/km/tonne) | Sensibilité |
|---------|------------------------|-------------|
| Maïs, Sorgho, Mil | 5.0 | Très faible (céréales sèches) |
| Riz | 6.0 | Faible |
| Niébé, Soja | 7.0 | Modérée |
| Manioc | 10.0 | Modérée |
| Igname | 12.0 | Élevée (sensible aux chocs) |
| Oignon | 20.0 | Très élevée |
| Tomate | 25.0 | Extrême (légume frais) |

Sous la pluie, la perte est majorée de 50% maximum (`beta_pluie = 0.5`).

---

## Prix du carburant

Le module récupère le prix de l'essence selon cette cascade :

1. Variable d'environnement `BENIN_FUEL_PRICE`
2. Fichier en ligne `config/fuel_prices.json` sur GitHub
3. Valeur de repli : 680 XOF/litre (configurable dans `config.py`)

```env
# .env — force le prix manuellement
BENIN_FUEL_PRICE=695
```

---

## Exemple complet avec météo

```python
from kadi.weather import WeatherSession
from kadi.market import Market

ws = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
marche = Market(lat=9.30, lon=2.08, location="Parakou", weather_session=ws)

# Coût pour transporter des tomates (culture périssable, sensible à la pluie)
cout = marche.logistics.calculate_transfer_cost(
    "Parakou", "Cotonou", crop="tomato"
)

print(f"Coût total          : {cout['total_cost_cfa']:,.0f} XOF")
print(f"Pluie demain        : {cout['prob_pluie'] * 100:.0f}%")
print(f"Gamma route effectif: {cout['gamma_effectif']:.3f}")
print(f"Perte qualité       : {cout['details']['quality_loss']:,.0f} XOF")
```

---

::: kadi.market.logistics.MarketLogistics
