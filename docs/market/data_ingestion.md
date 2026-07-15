# Ingestion des données (`kadi.market.data_ingestion`)

Le module `WFPDataBridgesClient` gère la connexion à l'API WFP DataBridges
(Programme Alimentaire Mondial — VAM) et le cache local des données de prix.
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

Ajoutez votre clé API dans le fichier `.env` à la racine du projet :

```env
WFP_API_Token=votre_cle_api_wfp
```

Sans clé, le client bascule automatiquement sur le mode simulation :

```python
client = WFPDataBridgesClient()
print(client.token)   # "" si WFP_API_Token est absent du .env

df = client.get_market_prices("cotonou", "maize")
print(df["is_simulated"].iloc[0])  # True — données fictives
```

---

## Méthodes

### `get_market_prices(market, crop, days_back)`

Récupère les prix historiques pour un marché et une culture. Interroge le
cache SQLite en premier ; si les données sont absentes ou périmées, lance
un appel à l'API WFP.

```python
df = client.get_market_prices("parakou", "maize", days_back=90)
```

**Stratégie de sélection des données :**

| Étape | Condition | Action |
|-------|-----------|--------|
| 1 | Cache frais (< 7 jours) | Retourne depuis le cache SQLite |
| 2 | Token WFP disponible | Appel à l'API WFP DataBridges |
| 3 | API indisponible ou erreur | Génère des données simulées |

**Retour :** `pd.DataFrame` avec les colonnes `date`, `price`, `unit`,
`is_simulated`, `source`, `confidence_score`, `fetched_at`.

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
