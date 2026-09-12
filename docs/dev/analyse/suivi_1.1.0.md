# Suivi des tâches — KadiPy v1.1.0

**Source :** `analyse/analyse_1.0.0.md` — analyse du 25 juillet 2026

**Branche :** `v1.1.0`

**Légende :**
- `[x]` Terminé
- `[-]` En cours
- `[ ]` À faire
- `[~]` Reporté (v1.2.0 ou ultérieure)

---

## Priorité 1 — Corrections bloquantes pour la v1.1.0

### P1 — Bug critique : rapport de `execute()` incohérent avec la documentation

**Problème 8** | Module `kadi.kidas` | Sévérité : **Critique**

**Statut : `[x]` Résolu**

La structure du dictionnaire retourné par `DataPipeline.execute()` ne correspondait pas à la documentation.
Le code a été aligné sur le format canonique documenté (`nb_rows_in`, `nb_rows_out`, `steps_summary`, `quality_score`, `warnings`, `cache_utilise`, `details`).

**Fichiers modifiés :**
- `kadi/kidas/pipeline.py`
- `docs/kidas/index.md`, `docs/kidas/pipeline.md`
- `tests/test_kidas/test_processing.py`

---

### P2 — `storage_vs_sell_now()` force `is_simulated=True` sur des données réelles

**Problème 6** | Module `kadi.market` | Sévérité : **Haute**

**Statut : `[x]` Résolu**

La ligne `est_simule = True` qui écrasait le flag réel a été remplacée par
`est_simule = prevision.get("is_simulated", True)`. Le flag est maintenant propagé
depuis `predict_price()`. La valeur par défaut `True` est conservée si la clé est
absente, pour ne pas casser le comportement offline.

**Fichiers modifiés :**
- `kadi/market/decision_support.py` (ligne ~324)
- `docs/market/decision_support.md` (description du champ `is_simulated`)

**Action :**
```python
# Avant (incorrect)
est_simule = True  # Le module forecasting V1 reste un stub
# Après (correct)
est_simule = prevision.get("is_simulated", True)
```

**Fichier :** `kadi/market/decision_support.py` (ligne ~324)

---

### P3 — `requirements.txt` désynchronisé avec `pyproject.toml`

**Problème 13** | Infrastructure | Sévérité : **Haute**

**Statut : `[x]` Résolu**

`requirements.txt` a été réécrit comme un alias vers `pyproject.toml` (une seule ligne
`-e ".[dev]"`), ce qui élimine la désynchronisation à la source. `xlrd<2.0` a été
ajouté dans les dépendances optionnelles de `pyproject.toml` sous l'extra `[xls]`.
`dask` a été retiré (non importé dans le code de production).

**Fichiers modifiés :**
- `requirements.txt` (réécrit)
- `pyproject.toml` (ajout de l'extra `xls`)

---

### P4 — SPI approximé par Z-score au lieu d'une loi Gamma

**Problème 3** | Module `kadi.weather` | Sévérité : **Haute**

**Statut : `[x]` Résolu**

La méthode `spi()` dans `risk.py` utilisait une approximation Z-score pour
calculer l'indice SPI. Elle a été remplacée par la méthode standard de
McKee et al. (1993) :

1. Ajustement d'une loi Gamma sur les cumuls non nuls via
   `scipy.stats.gamma.fit(valid_data, floc=0)`.
2. Application d'une correction de masse de probabilité pour les jours
   sans pluie (cumul nul).
3. Conversion en score SPI via `scipy.stats.norm.ppf`.

La signature publique de `spi()` est inchangée. La méthode lève maintenant
`InsufficientData` si le nombre de cumuls non nuls est inférieur à 10.

**Fichiers modifiés :**
- `kadi/weather/risk.py` (méthode `spi()`, lignes 62-153)
- `tests/weather/test_risk.py` (nouveaux tests: signe du SPI, cas limites Gamma)

---

### P5 — Bornes GPS du module `market` dupliquées en dur

**Problème 4** | Module `kadi.market` | Sévérité : **Haute**

**Statut : `[x]` Résolu**

Les constantes `_LAT_MIN`, `_LAT_MAX`, `_LON_MIN`, `_LON_MAX` étaient
définies en dur dans `market/__init__.py` avec des valeurs différentes de
celles de `config.py` (incohérence réelle : `min_lat` valait 6.0 au lieu de
2.5, `min_lon` valait 0.5 au lieu de -1.5). Elles sont maintenant lues
depuis `CONFIG["weather"]["gps_validation_bbox"]` avec des valeurs de repli.

**Action réalisée :**
```python
from kadi.config import CONFIG

_bbox = CONFIG.get("weather", {}).get("gps_validation_bbox", {})
_LAT_MIN = _bbox.get("min_lat", 2.5)
_LAT_MAX = _bbox.get("max_lat", 12.5)
_LON_MIN = _bbox.get("min_lon", -1.5)
_LON_MAX = _bbox.get("max_lon", 4.0)
```

**Fichiers modifiés :**
- `kadi/market/__init__.py` (lignes 21-30)
- `tests/test_market/test_market_components.py` (ajout de
  `test_market_bornes_gps_issues_de_config`, mise à jour commentaires)

---

### P6 — `fix_dates()` accumule un mauvais compteur de dates corrigées

**Problème 9** | Module `kadi.kidas` | Sévérité : **Haute**

**Statut : `[x]` Résolu**

Dans `cleaner.py`, la variable `nb_corrigees` était calculée mais jamais utilisée.
Le compteur accumulait `nb_avant` (total des valeurs non-null avant parsing) au
lieu du nombre réel de conversions réussies. Si une colonne avait 100 valeurs et
80 étaient parsées avec succès, le rapport affichait 100 au lieu de 80.

**Action réalisée :**
```python
# Avant (incorrect)
nb_corrigees = int(nb_avant - (nb_avant - nb_apres))  # toujours = nb_apres
nb_dates_corrigees += nb_avant                         # mauvais compteur
# Après (correct)
nb_corrigees = int(nb_apres)
nb_dates_corrigees += nb_corrigees
```

**Fichiers modifiés :**
- `kadi/kidas/cleaner.py` (lignes ~360-363)
- `tests/test_kidas/test_processing.py` (ajout de `test_fix_dates_compteur_toutes_converties`,
  `test_fix_dates_compteur_conversions_partielles`, `test_fix_dates_colonne_inexistante_ne_plante_pas`)

---

### P7 — `get_market_functionality_index()` retourne toujours 7.9

**Problème 5** | Module `kadi.market` | Sévérité : **Moyenne**

**Statut : `[x]` Résolu**

La méthode retournait `7.9` en dur sans aucun calcul. Elle a été remplacée par
une `NotImplementedError` explicite avec un message orientant vers la future
source FEWSNET. La docstring a été mise à jour en cohérence.

**Action réalisée :**
```python
raise NotImplementedError(
    "get_market_functionality_index() n'est pas encore implémentée. "
    "Elle sera disponible après intégration de la source FEWSNET."
)
```

**Fichiers modifiés :**
- `kadi/market/data_ingestion.py` (lignes ~601-625)
- `tests/test_market/test_market_components.py` (ajout de
  `test_get_market_functionality_index_leve_not_implemented`,
  `test_get_market_functionality_index_message_fewsnet`)

---

### P8 — Pas de rapport de couverture `pytest-cov` dans la CI

**Problème 16** | CI / GitHub Actions | Sévérité : **Moyenne**

**Statut : `[x]` Résolu**

`pytest-cov>=4.0` a été ajouté dans les dépendances `[dev]` de `pyproject.toml`.
Le workflow CI a été mis à jour pour générer un rapport de couverture avec un
seuil minimal de 70 %, et un rapport XML pour Codecov (optionnel, Python 3.11 uniquement).

**Fichiers modifiés :**
- `pyproject.toml` (ajout de `pytest-cov>=4.0` dans `[dev]`)
- `.github/workflows/tests.yml` (étape 4 mise à jour, étape 5 Codecov ajoutée)

---

### P9 — Intégration transparente de l'API WFP DataBridges (nouvelle fonctionnalité v1.1.0)

**Nouvelle fonctionnalité** | Module `kadi.market` | Sévérité : N/A

**Statut : `[x]` Résolu**

Deux clients API ont été créés et intégrés dans le module `kadi.market` :

**1. `ExchangeRateClient`** — Taux de change dynamiques via Frankfurter (`api.frankfurter.dev`) :
- L'API est appelée pour les paires XOF/USD et XOF/EUR.
- Cache mémoire TTL 24h pour éviter les appels redondants.
- Fallback automatique sur `config.EXCHANGE_RATES` en mode hors ligne.
- `EXCHANGE_RATES_DEFAULT` supprimé de `_normalization.py` : source unique dans `config.py`.

**2. `WFPDataBridgesClient`** (HAPI HumData) — Prix de marché réels via l'API HAPI :
- Appelle l'endpoint `food-prices-market-monitor` de l'API HAPI.
- Identifiant lu exclusivement depuis `HAPI_APP_IDENTIFIER` (variable d'environnement).
- Pagination automatique, retry avec backoff exponentiel.
- Normalisation des colonnes HAPI vers le format interne KadiPy.
- Fallback : données simulées avec `is_simulated=True` si identifiant absent ou réseau indisponible.

Les deux clients sont injectés automatiquement dans `Market` à l'instanciation.

**Fichiers créés :**
- `kadi/_sources/exchange_client.py` (nouveau)
- `kadi/_sources/wfp_client.py` (nouveau)
- `tests/test_market/test_exchange_client.py` (nouveau)
- `tests/test_market/test_wfp_client.py` (nouveau)

**Fichiers modifiés :**
- `kadi/config.py` (ajout `FRANKFURTER_API_URL`, `HAPI_API_URL`, `HAPI_APP_IDENTIFIER` ; mise à jour `EXCHANGE_RATES`)
- `kadi/market/__init__.py` (injection des deux clients, suppression `env_file`)
- `kadi/market/pricing.py` (ajout `exchange_client`, import depuis `config.py`)
- `kadi/market/_normalization.py` (suppression `EXCHANGE_RATES_DEFAULT`)

---

## Priorité 2 — Autres améliorations pour la v1.1.0

| # | Problème | Module | Sévérité | Description courte | Statut |
|---|---------|--------|----------|--------------------|--------|
| 2 | `weather` | `weather` | Faible | Alias `temperature_avg/mean` centralisé dans `_unifier_colonne_temperature()` | `[x]` |
| 10 | `kidas` | `kidas` | Faible | Clé de cache SHA-256 dans `execute()` | `[x]` |
| 11 | `config` | Infrastructure | Faible | `MODELS_DIR` documenté (option B : commentaire explicite conservé) | `[x]` |
| 12 | `config` | Infrastructure | Moyenne | `EXCHANGE_RATES` statiques — partiellement résolu en P9 via `ExchangeRateClient` | `[x]` |
| 1 | `weather` | `weather` | Moyenne | README mis à jour : comportement hybride CHIRPS/Open-Meteo décrit | `[x]` |
| 7 | `market` | `market` | Faible | Revenu `_portfolio_heuristique()` calculé (surface × rendement × prix) | `[x]` |
| 14 | `tests` | Tests | Moyenne | Tests unitaires `kadi.cache` ajoutés (`tests/test_cache.py`) | `[x]` |
| 15 | `tests` | Tests | Faible | Tests unitaires `kadi.config` ajoutés (`tests/test_config.py`) | `[x]` |

---

## Tableau récapitulatif global

| # | Module | Sévérité | Description courte | Statut |
|---|--------|----------|--------------------|--------|
| 8 | `kidas` | Critique | Rapport `execute()` incohérent avec la documentation | `[x]` |
| 6 | `market` | Haute | `storage_vs_sell_now()` force `is_simulated=True` | `[x]` |
| 13 | `config` | Haute | `requirements.txt` désynchronisé avec `pyproject.toml` | `[x]` |
| 3 | `weather` | Haute | SPI approximé par Z-score au lieu d'une loi Gamma | `[x]` |
| 4 | `market` | Haute | Bornes GPS dupliquées en dur au lieu de lire `CONFIG` | `[x]` |
| 9 | `kidas` | Haute | `nb_dates_corrigees` calculé incorrectement dans `fix_dates()` | `[x]` |
| 5 | `market` | Moyenne | `get_market_functionality_index()` retourne toujours 7.9 | `[x]` |
| 16 | CI | Moyenne | Pas de rapport `pytest-cov` dans la CI | `[x]` |
| — | `market` | N/A | Intégration API WFP DataBridges (v1.1.0) | `[x]` |
| 2 | `weather` | Faible | Alias `temperature_avg/mean` centralisé dans `_unifier_colonne_temperature()` | `[x]` |
| 10 | `kidas` | Faible | Clé de cache sécurisée par SHA-256 dans `execute()` | `[x]` |
| 11 | `config` | Faible | `MODELS_DIR` documenté (commentaire explicite, option B) | `[x]` |
| 12 | `config` | Moyenne | `EXCHANGE_RATES` statiques — résolu via `ExchangeRateClient` (P9) | `[x]` |
| 1 | `weather` | Moyenne | README mis à jour : comportement hybride CHIRPS/Open-Meteo décrit | `[x]` |
| 7 | `market` | Faible | Revenu `_portfolio_heuristique()` calculé au lieu de valeur magique | `[x]` |
| 14 | `tests` | Moyenne | `kadi.cache` testé directement (`tests/test_cache.py`) | `[x]` |
| 15 | `tests` | Faible | `kadi.config` testé (structure, chemins, env vars) | `[x]` |

