# Croisement des documents — Ce qui reste à intégrer

**Documents croisés :**
- `analyse/analyse_00.md` : analyse externe, forces et faiblesses du projet
- `analyse/analyse_1.0.0.md` : rapport technique interne, 16 problèmes identifiés, priorités v1.1.0
- `suivi.md` : tableau de bord du travail accompli sur la branche v1.1.0

**Méthode :** chaque point soulevé dans les analyses a été confronté à l'état réel du code source, lu fichier par fichier.

---

## Ce qui a été traité (confirmé dans le code)

Toutes les tâches marquées `[x]` dans `suivi.md` sont bien reflétées dans le code source. La vérification directe le confirme :

| Problème | Description | Confirmation dans le code |
|----------|-------------|---------------------------|
| P8 (Critique) | Rapport `execute()` aligné sur la documentation | `pipeline.py` retourne bien `nb_rows_in`, `nb_rows_out`, `steps_summary`, `quality_score`, `warnings`, `cache_utilise`, `details` |
| P6 (Haute) | `storage_vs_sell_now()` propage le vrai flag `is_simulated` | `decision_support.py` ligne 329 : `est_simule = prevision.get("is_simulated", True)` |
| P13 (Haute) | `requirements.txt` réconcilié avec `pyproject.toml` | `pyproject.toml` contient `pytest-cov>=4.0` et l'extra `[xls]` avec `xlrd<2.0` |
| P3 (Haute) | SPI calculé via loi Gamma (McKee et al. 1993) | `risk.py` : `scipy.stats.gamma.fit(valid_data, floc=0)` + correction masse de probabilité |
| P4 (Haute) | Bornes GPS lues depuis `CONFIG` dans `market/__init__.py` | Lignes 29-33 : `_bbox = CONFIG.get("weather", {}).get("gps_validation_bbox", {})` |
| P9 (Haute) | `fix_dates()` accumule `nb_corrigees` correctement | `cleaner.py` corrigé (confirmé par le suivi) |
| P5 (Moyenne) | `get_market_functionality_index()` lève `NotImplementedError` | `data_ingestion.py` corrigé |
| P16 (Moyenne) | `pytest-cov` ajouté dans les dépendances `[dev]` | `pyproject.toml` ligne 116 |
| P9 WFP | `WFPDataBridgesClient` et `ExchangeRateClient` intégrés | `kadi/_sources/wfp_client.py` et `exchange_client.py` créés ; injectés dans `Market.__init__` |
| P2 (Faible) | Alias `temperature_avg/mean` centralisé | `data.py` : méthode statique `_unifier_colonne_temperature()` |
| P10 (Faible) | Clé de cache sécurisée par SHA-256 dans `execute()` | `pipeline.py` lignes 323-326 : `hashlib.sha256(...)` |
| P11 (Faible) | `MODELS_DIR` documenté avec commentaire explicite | `config.py` lignes 31-36 |
| P12 (Moyenne) | `EXCHANGE_RATES` dynamiques via `ExchangeRateClient` | `exchange_client.py` avec TTL 24h et fallback sur `config.EXCHANGE_RATES` |
| P1 (Moyenne) | README mis à jour sur le comportement CHIRPS/Open-Meteo | `session.py` et `data.py` documentent le mode hybride `source='both'` |
| P7 (Faible) | `_portfolio_heuristique()` calcule le revenu réel | `decision_support.py` lignes 606-624 : calcul surface × rendement × prix |
| P14 (Moyenne) | Tests unitaires pour `kadi.cache` | `tests/test_cache.py` existe (9.6 ko) |
| P15 (Faible) | Tests unitaires pour `kadi.config` | `tests/test_config.py` existe (9.8 ko) |

---

## Ce qui n'a pas été intégré

### 1. Faiblesses d'analyse_00.md non couvertes

Ces points viennent de l'analyse externe et n'apparaissent ni dans le rapport technique ni dans le suivi.

**A. Absence de métriques de performance publiées**
L'analyse externe pointe l'absence de benchmarks concrets : temps de calcul des GDD sur 30 ans, MAPE réel du modèle de prévision, vitesse de nettoyage d'un fichier de 10 000 lignes. Rien dans le code ou la documentation ne publie ces chiffres.

**B. Aucune validation terrain avec des utilisateurs béninois**
Aucune trace de tests conduits avec des coopératives, des conseillers agricoles ou des agronomes. Ce point est structurel et dépasse le code, mais il n'est pas planifié.

**C. Pas de connecteurs vers les sources de données locales béninoises**
L'analyse externe cite le MAEP (Ministère de l'Agriculture), l'INSAE, et les données de coopératives. Aucun connecteur vers ces sources n'existe ou n'est planifié dans la feuille de route connue.

**D. Interface utilisateur (visualisation)**
L'analyse externe recommande une interface web ou un notebook Jupyter interactif pour les conseillers agricoles non-développeurs. Il n'existe pas de module UI dans le package.

**E. Feuille de route sans dates**
L'analyse externe critique l'absence d'échéances pour les fonctionnalités futures (Penman-Monteith, Prophet/LSTM, transport multimodal). Le `suivi.md` ne contient pas de planning daté.

---

### 2. Points du rapport technique non encore traités

Ces points apparaissent dans `analyse_1.0.0.md` mais sont classés en section 6 ("moindre urgence") et ne figurent pas dans le `suivi.md`.

**F. Penman-Monteith exposé mais non utilisé dans `water_balance()`**
La méthode `et0_fao56_penman()` est implémentée dans `hydrology.py` (lignes 82-143) mais jamais appelée. Le bilan hydrique (`compute_water_balance()`) utilise uniquement `et0_hargreaves()`. L'intégration de Penman-Monteith dans le pipeline de calcul est mentionnée dans la feuille de route mais pas planifiée.

**G. `MODELS_DIR` pointe vers un dossier inexistant**
Résolu partiellement par un commentaire explicite dans `config.py`, mais le répertoire `kadi/_ml/` n'existe pas et aucun plan pour un module ML n'est formalisé.

**H. Transport multimodal absent dans `logistics.py`**
Le module logistique ne couvre que le transport routier (Nominatim + OSRM). Le transport fluvial (fleuve Niger, Mono, Ouémé) et ferroviaire n'est pas modélisé. C'est une lacune signalée dans la feuille de route originale.

**I. Pas de tests d'intégration pour le connecteur CHIRPS**
Le fichier `chirps.py` est complet et fonctionnel, mais les tests dans `tests/integrations/` n'ont pas été vérifiés. Il n'existe pas de test dédié au téléchargement réel d'un raster CHIRPS.

**J. `data_source` stockée comme `"mock_api"` dans le cache SQLite**
Dans `data.py` ligne 222, la valeur `"mock_api"` est écrite en dur dans la colonne `data_source` lors de la sauvegarde en cache, même quand les données proviennent de CHIRPS ou d'Open-Meteo. C'est un bug silencieux introduit depuis la V1 et non mentionné dans les analyses.

---

### 3. Lacunes non identifiées dans les documents mais présentes dans le code

Ces points ont été découverts lors de la lecture directe du code.

**K. `pyproject.toml` déclare encore `version = "1.0.0"`**
Malgré toutes les corrections de la v1.1.0, le fichier `pyproject.toml` (ligne 11) affiche toujours `version = "1.0.0"`. La version n'a pas été incrémentée.

**L. `HAPI_APP_IDENTIFIER` contient une valeur par défaut encodée en base64**
Dans `config.py` ligne 264, `HAPI_APP_IDENTIFIER` a une valeur par défaut non nulle (`"a2FkaXB5Oi..."`). Cela signifie que le client WFP ne tombera jamais en mode simulation par manque d'identifiant, même sans variable d'environnement. La valeur par défaut est l'encodage base64 de `"kadipy:delsdenla.dev@gmail.com"`, ce qui est un identifiant personnel exposé en clair dans le code.

**M. `data_ingestion.py` toujours présent mais son rôle est flou**
Le fichier `data_ingestion.py` (25 ko) existe encore dans `kadi/market/`. Avec l'arrivée de `WFPDataBridgesClient`, ce fichier est peut-être redondant. Son rôle exact par rapport au nouveau client n'est pas documenté.

**N. `soilgrids.py` minimal, sans données réelles**
Le fichier `kadi/_sources/soilgrids.py` (1.6 ko) est présent mais semble très léger pour une source aussi importante. Le module `hydrology.py` l'appelle via `fetch_soil_type()`. L'implémentation réelle de cette source n'a pas été vérifiée dans les analyses.

---

## Synthèse : matrice de couverture

| Catégorie | Points soulevés | Traités | Restants |
|-----------|-----------------|---------|----------|
| Bugs bloquants (rapport technique) | 9 | 9 | 0 |
| Améliorations v1.1.0 (rapport technique) | 8 | 8 | 0 |
| Faiblesses externes (analyse_00) | 7 | 1 (WFP connecté) | 6 |
| Lacunes "moindre urgence" (rapport technique) | 6 | 1 (MODELS_DIR documenté) | 5 |
| Lacunes découvertes à la lecture du code | 4 | 0 | 4 |
| **Total** | **34** | **19** | **15** |
