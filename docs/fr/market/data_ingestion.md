# Ingestion des données (`kadi.market.data_ingestion`)

> [!WARNING]
> **Dépréciation (v1.1.0)** : Le module `kadi.market.data_ingestion` est déprécié depuis la version 1.1.0 et sa suppression est prévue pour la version 1.2.0. Pour tout nouveau code, utilisez directement le module canonique `kadi._sources.wfp_client` (ou la façade recommandée `kadi.market.Market`).

Le module `WFPDataBridgesClient` gère la connexion à l'API WFP DataBridges
(Programme Alimentaire Mondial : VAM) et le cache local des données de prix.
Il constitue la couche d'accès aux données du module `kadi.market`.

---

## Architecture du client

```
WFPDataBridgesClient
├── get_market_prices()     ← Récupère les prix d'un marché
├── get_commodities()       ← Liste les cultures disponibles
├── get_markets()           ← Liste les marchés disponibles
└── Cache SQLite            ← Stocke les résultats pour l'accès hors-ligne
```

---

## Initialisation

```python
from kadi.market.data_ingestion import WFPDataBridgesClient

# Le token est lu automatiquement depuis le fichier .env
client = WFPDataBridgesClient()
```

Via la façade `Market` (recommandé) :

```python
from kadi.market import Market

marche = Market(lat=9.30, lon=2.08, location="Parakou")
# marche.data_client est un WFPDataBridgesClient prêt à l'emploi
```

---

## Configuration requise

Le client d'ingestion utilise une API publique et gratuite par défaut (HAPI HumData de OCHA/PAM) et ne nécessite aucune clé payante pour récupérer des données réelles de prix.

Vous pouvez optionnellement spécifier vos propres identifiants dans le fichier `.env` :

```env
# Identifiant HAPI HumData (optionnel : valeur par défaut intégrée dans KadiPy)
HAPI_APP_IDENTIFIER=votre_identifiant_base64

# Clé commerciale WFP DataBridges (optionnelle)
WFP_API_Token=votre_cle_api_wfp
```

---

## Méthodes

### `get_market_prices(market, crop, days_back)`

Récupère les prix historiques pour un marché et une culture. Interroge la boucle de fallback à 4 niveaux.

```python
df = client.get_market_prices("parakou", "maize", days_back=90)
```

**Stratégie de sélection des données (boucle de fallback 4 niveaux) :**

| Étape | Condition | Source / Action | `is_simulated` | `confidence_score` |
|-------|-----------|-----------------|----------------|-------------------|
| 1 | Cache frais (< 7 jours) | Cache SQLite local | `False` | Variable (score d'origine) |
| 2 | Reseau OK (source publique) | API HAPI HumData / VAM (PAM) | `False` | `0.9` |
| 3 | Token WFP disponible | API WFP DataBridges | `False` | `1.0` |
| 4 | Reseau HS ou sources indisponibles | Simulation (bruit gaussien) | `True` | `0.1` |

**Retour :** `pd.DataFrame` avec les colonnes `date`, `price`, `unit`,
`is_simulated`, `source`, `confidence_score`, `fetched_at`.

---

### `get_market_functionality_index(market_id)`

Calcule l'indice de fonctionnalité d'un marché. Cette méthode lève une exception
`NotImplementedError` en v1.1.0 et sera disponible après l'intégration de la source de données FEWSNET.

```python
# Lève NotImplementedError en v1.1.0
try:
    index = client.get_market_functionality_index("parakou")
except NotImplementedError as e:
    print(e)  # get_market_functionality_index() n'est pas encore implémentée...
```

---

### Cache SQLite

Les données récupérées sont persistées dans `~/.kadi/market_prices.db`. La
durée de vie du cache est configurable dans `config.py` :

```python
CONFIG["market"]["cache_max_age_jours"] = 7  # défaut : 7 jours
```

Le module `kadi.market._cache` expose les fonctions de gestion du cache si
vous devez l'interroger directement :

```python
from kadi.market._cache import recuperer_prix, vider_cache

# Vérifier les données en cache pour le maïs à Cotonou
df_cache = recuperer_prix("cotonou", "maize", max_age_jours=30)

# Vider uniquement le cache de Cotonou/maïs
vider_cache("cotonou", "maize")
```

---

## Endpoints WFP utilisés

| Endpoint | Usage |
|----------|-------|
| `/Commodities/List` | Récupère les IDs officiels des cultures |
| `/Markets/List` | Récupère les IDs officiels des marchés |
| `/MarketPrices/alldata` | Historique de prix par marché et culture |

---

::: kadi.market.data_ingestion.WFPDataBridgesClient
