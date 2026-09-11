# Logistique (`kadi.market.logistics`)

La classe `Logistics` modélise les frictions logistiques réelles sur les
corridors commerciaux béninois : coût de transport, tracasseries aux
postes de contrôle et dégradation de la qualité marchande des produits.

Depuis la v1.2.0, elle intègre optionnellement la météo pour ajuster
dynamiquement le coefficient de route (`gamma_route`) et la perte de
qualité selon la probabilité de pluie prévue.

Elle est utilisée en interne par `Market` et accessible via
`market.logistics`. Elle peut aussi être instanciée directement.

---

## Importation directe

```python
from kadi.market import Logistics
```

---

## Initialisation

```python
from kadi.market import Logistics

# Sans intégration météo (comportement V1)
logistics = Logistics()

# Avec intégration météo (ajustement dynamique du coût selon la pluie)
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
logistics = Logistics(weather=weather)
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `cache_file` | `str` | `None` | Chemin vers le fichier de cache JSON des distances. Par défaut : `~/.kadi/osrm_cache.json` |
| `weather` | `Weather` | `None` | Session météo pour l'ajustement climatique des coûts. Si None, aucun ajustement (comportement V1) |

**Attributs publics :**

| Attribut | Type | Description |
|----------|------|-------------|
| `weather` | `Weather` | Session météo injectée (ou None) |
| `cache_file` | `str` | Chemin du fichier de cache des distances |
| `cache` | `dict` | Cache en mémoire : clés `'coords'` et `'distances'` |

---

## Méthodes

### `transfer_cost(origine, destination, prix_carburant, crop)`

Calcule le coût total de transfert d'une ville à une autre.

**Formule :**

```
C_transfer = C_info
           + Distance * (gamma_effectif * P_carburant / 100 + mu_checkpoints)
           + C_qualite(culture, distance, pluie)
```

Où :
- `C_info` = coût fixe de recherche d'information (appels, déplacements),
  configurable dans `config.py` (défaut : 5 000 XOF)
- `gamma_effectif` = `gamma_route * (1 + alpha_pluie * prob_pluie)` :
  majoration météo si une session weather est disponible
- `mu_checkpoints` = coût moyen des tracasseries par km (défaut : 15 XOF/km)
- `C_qualite` = perte de valeur marchande variable par culture et météo

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
marche = kd.Market(lat=9.3, lon=2.3, location="Parakou", weather=weather)

# Coût de transfert avec intégration météo
cout = marche.logistics.transfer_cost(
    origine="Parakou",
    destination="Cotonou",
    crop="maize",
)

print(f"Coût total       : {cout['total_cost_cfa']:,.0f} XOF")
print(f"Pluie prévue     : {cout['prob_pluie'] * 100:.0f} %")
print(f"Gamma effectif   : {cout['gamma_effectif']:.4f}")

# Détail par poste
d = cout["details"]
print(f"  Distance       : {d['distance_km']:.1f} km")
print(f"  Coût info      : {d['search_costs']:,.0f} XOF")
print(f"  Transport      : {d['transport_costs']:,.0f} XOF")
print(f"  Perte qualité  : {d['quality_loss']:,.0f} XOF")
print(f"  Carburant      : {d['fuel_price_used']:.0f} XOF/litre")
```

**Paramètres :**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `origine` | `str` | requis | Ville de départ (ex: `'Parakou'`) |
| `destination` | `str` | requis | Ville d'arrivée (ex: `'Cotonou'`) |
| `prix_carburant` | `float` | `None` | Prix du litre d'essence en XOF. Si None, récupéré automatiquement |
| `crop` | `str` | `None` | Culture transportée, pour la perte de qualité. Si None, utilise le facteur par défaut |

**Retour :** `dict`

| Clé | Type | Description |
|-----|------|-------------|
| `total_cost_cfa` | `float` | Cout total du transfert en XOF |
| `prob_pluie` | `float` | Probabilite de pluie utilisee (0.0 si pas de météo) |
| `gamma_effectif` | `float` | Coefficient de route effectivement applique |
| `details` | `dict` | Sous-dictionnaire avec chaque composante du cout |

**Clés de `details` :**

| Clé | Description |
|-----|-------------|
| `distance_km` | Distance routiere en km |
| `search_costs` | Cout fixe de recherche d'information (XOF) |
| `transport_costs` | Cout lié à la distance (carburant + tracasseries) (XOF) |
| `quality_loss` | Perte de valeur marchande (XOF) |
| `fuel_price_used` | Prix du carburant utilise (XOF/litre) |
| `gamma_route_base` | Coefficient de base avant ajustement météo |
| `gamma_effectif` | Coefficient apres ajustement météo |
| `prob_pluie` | Probabilite de pluie utilisee |
| `crop` | Culture concernee (`'_default'` si non spécifiée) |

**Perte de qualité par culture (XOF/km/tonne) :**

| Culture | Facteur | Culture | Facteur |
|---------|---------|---------|---------|
| `maize`, `sorghum`, `millet` | 5.0 | `cowpea`, `soybean` | 7.0 |
| `rice` | 6.0 | `yam` | 12.0 |
| `cassava` | 10.0 | `tomato` | 25.0 |
| `onion` | 20.0 | (défaut) | 8.0 |

Sous la pluie, la perte de qualité est majorée : `C_qualite = facteur *
distance_km * (1 + beta_pluie * prob_pluie)`, avec `beta_pluie`
configurable dans `config.py` (défaut : 0.5).

---

### `distance(origine, destination)`

Récupère la distance routière entre deux villes béninoises.

**Stratégie en cascade :**

1. Cache local (résultat d'un appel précédent, persisté dans le fichier JSON)
2. Géocodage Nominatim (OpenStreetMap) + routage OSRM
3. Fallback Haversine (vol d'oiseau x 1.3) si OSRM est indisponible
4. Valeur de repli 100 km si le géocodage échoue

```python
d = marche.logistics.distance("Parakou", "Cotonou")
print(f"Distance routière : {d:.1f} km")

# Résultat mis en cache automatiquement
d2 = marche.logistics.distance("Cotonou", "Parakou")   # Retourné depuis le cache
```

**Paramètres :**

| Nom | Type | Description |
|-----|------|-------------|
| `origine` | `str` | Nom de la ville de départ |
| `destination` | `str` | Nom de la ville d'arrivée |

**Retour :** `float` - Distance estimée en kilomètres.

Le résultat est automatiquement mis en cache pour la session en cours
et sauvegardé dans `cache_file` pour les sessions ultérieures.

---

## Intégration météo

Quand une instance `weather` est fournie à l'initialisation, le calcul
du coût de transfert est ajusté automatiquement :

```
gamma_effectif = gamma_route * (1 + alpha_pluie * prob_pluie)
```

- `gamma_route` : coefficient de base (configurable dans `config.py`,
  défaut : 1.2)
- `alpha_pluie` : intensité de la majoration météo (défaut : 0.25)
- `prob_pluie` : probabilité de pluie demain, obtenue depuis
  `weather.rain_prob(days=1)`

La probabilité de pluie est calculée une seule fois par session (mise en
cache) pour éviter des appels répétés au module météo.

**Exemple :**

Avec `prob_pluie=0.8` et `alpha=0.25`, le coefficient de route passe de
1.2 à `1.2 * (1 + 0.25 * 0.8) = 1.44`, soit une majoration de 20% sur
le coût de transport.

---

## Prix du carburant

La méthode `transfer_cost()` récupère automatiquement le prix du
carburant selon la stratégie suivante :

| Priorité | Source |
|----------|--------|
| 1 | Variable d'environnement `BENIN_FUEL_PRICE` |
| 2 | Cache en mémoire (une seule requête par session) |
| 3 | Fichier `config/fuel_prices.json` sur GitHub |
| 4 | Valeur de repli depuis `config.py` (défaut : 680 XOF/litre) |

---

## Méthodes dépréciées

| Ancienne méthode | Remplacée par | Depuis |
|------------------|---------------|--------|
| `calculate_transfer_cost(origine, destination)` | `transfer_cost(origine, destination)` | v1.2.0 |
| `get_distance(origine, destination)` | `distance(origine, destination)` | v1.2.0 |

## Classe dépréciée

| Ancien nom | Remplacé par | Depuis |
|------------|--------------|--------|
| `MarketLogistics` | `Logistics` | v1.2.0 |

---

## Exemple complet

```python
import kadi as kd

weather = kd.Weather(lat=9.3, lon=2.3, name="Parakou")
marche = kd.Market(lat=9.3, lon=2.3, location="Parakou", weather=weather)

# Comparer le coût pour deux cultures (tomate plus sensible)
cultures = ["maize", "tomato"]
for crop in cultures:
    cout = marche.logistics.transfer_cost("Parakou", "Cotonou", crop=crop)
    print(
        f"{crop:8s} -> {cout['total_cost_cfa']:,.0f} XOF "
        f"(perte qualité : {cout['details']['quality_loss']:,.0f} XOF)"
    )

# Distance seule
d = marche.logistics.distance("Abomey", "Cotonou")
print(f"Abomey - Cotonou : {d:.1f} km")
```

---

::: kadi.market.logistics.Logistics
