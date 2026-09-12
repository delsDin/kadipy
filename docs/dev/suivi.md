# Suivi des tâches : KadiPy

**Dernière mise à jour :** 6 août 2026
**Sources :** audit du code source + croisement de trois documents de référence
(`analyse_00.md`, `analyse_1.0.0.md`, `suivi.md` v1.1.0)

**Légende :**
- `[x]` Terminé
- `[-]` En cours
- `[ ]` À faire
- `[~]` Reporté (version ultérieure précisée)

---

## État général du projet

| Version | Statut | Périmètre |
|---------|--------|-----------|
| v1.0.0 | Livrée | Version initiale avec 17 problèmes identifiés |
| v1.1.0 | Livrée | 17 corrections + API WFP + audit de sécurité et robustesse |
| v1.2.0 | Planifiée | Penman-Monteith, MAEP, notebook interactif |
| v2.0.0 | Planifiée | Prophet, interface web, transport multimodal |

---

## Partie A — Tâches v1.1.0 (terminées)

Toutes les tâches ci-dessous ont été vérifiées directement dans le code source.

### Corrections bloquantes

| # | Module | Sévérité | Description | Statut |
|---|--------|----------|-------------|--------|
| P8 | `kidas` | Critique | Rapport `execute()` aligné sur la documentation publique | `[x]` |
| P6 | `market` | Haute | `storage_vs_sell_now()` propage le vrai flag `is_simulated` | `[x]` |
| P13 | Infrastructure | Haute | `requirements.txt` réécrit comme alias vers `pyproject.toml` | `[x]` |
| P3 | `weather` | Haute | SPI calculé via loi Gamma (McKee et al. 1993) | `[x]` |
| P4 | `market` | Haute | Bornes GPS lues depuis `CONFIG` (non codées en dur) | `[x]` |
| P9 | `kidas` | Haute | `fix_dates()` accumule correctement le compteur de corrections | `[x]` |
| P5 | `market` | Moyenne | `get_market_functionality_index()` lève `NotImplementedError` | `[x]` |
| P16 | CI | Moyenne | `pytest-cov>=4.0` ajouté ; CI génère un rapport de couverture | `[x]` |

### Améliorations et nouvelles fonctionnalités

| # | Module | Description | Statut |
|---|--------|-------------|--------|
| P9-WFP | `market` | `WFPDataBridgesClient` + `ExchangeRateClient` intégrés dans `Market` | `[x]` |
| P2 | `weather` | Alias `temperature_avg/mean` centralisé dans `_unifier_colonne_temperature()` | `[x]` |
| P10 | `kidas` | Clé de cache sécurisée par SHA-256 dans `execute()` | `[x]` |
| P11 | Infrastructure | `MODELS_DIR` documenté avec commentaire explicite dans `config.py` | `[x]` |
| P12 | Infrastructure | `EXCHANGE_RATES` dynamiques via `ExchangeRateClient` (TTL 24h, fallback) | `[x]` |
| P1 | `weather` | README mis à jour : comportement hybride CHIRPS/Open-Meteo décrit | `[x]` |
| P7 | `market` | `_portfolio_heuristique()` calcule le revenu réel (surface * rendement * prix) | `[x]` |
| P14 | Tests | Tests unitaires `kadi.cache` ajoutés (`tests/test_cache.py`) | `[x]` |
| P15 | Tests | Tests unitaires `kadi.config` ajoutés (`tests/test_config.py`) | `[x]` |

---

## Partie B — Autres tâches v1.1.0 (critiques, découvertes lors de l'audit)

Ces points ont été découverts lors de l'audit approfondi du code source et sont désormais entièrement traités dans la version v1.1.0.

---

### C1 : Incrémenter la version du package

**Module :** Infrastructure
**Fichier :** `pyproject.toml` ligne 11
**Sévérité :** Haute

**Problème :**
Le fichier déclarait `version = "1.0.0"` alors que la branche est la v1.1.0 et que
toutes les corrections avaient été livrées.

**Action réalisée :**
```toml
version = "1.1.0"
```

**Statut : `[x]` Terminé**

---

### C2 : Retirer l'identifiant personnel de `config.py`

**Module :** Infrastructure
**Fichier :** `kadi/config.py` ligne ~264
**Sévérité :** Critique (sécurité)

**Problème :**
La variable `HAPI_APP_IDENTIFIER` contenait une valeur par défaut en base64 encodant
l'adresse personnelle `kadipy:delsdenla.dev@gmail.com`, exposant des données personnelles dans le dépôt public.

**Action effectuée :**
Remplacement de l'adresse personnelle par un identifiant générique de projet (`kadipy:requests@kadipy.com`, encodé en `a2FkaXB5OnJlcXVlc3RzQGthZGlweS5jb20=`). Cela permet d'interroger les données réelles de l'API HAPI HumData par défaut sans exposer de données personnelles.

**Statut : `[x]` Terminé**

---

### C3 : Corriger le stockage de `data_source` dans le cache SQLite

**Module :** `weather`
**Fichier :** `kadi/weather/data.py`
**Sévérité :** Haute (données incorrectes)

**Problème :**
Lors de la sauvegarde en cache SQLite, la colonne `data_source` était écrite en dur comme `"mock_api"` pour toutes les données.

**Action effectuée :**
La source réelle est désormais extraite dynamiquement depuis le DataFrame avant l'insertion SQL.

**Statut : `[x]` Terminé**

---

### C4 : Clarifier ou supprimer `data_ingestion.py`

**Module :** `market`
**Fichier :** `kadi/market/data_ingestion.py`
**Sévérité :** Moyenne (maintenabilité)

**Problème :**
Redondance entre l'ancien client `data_ingestion.py` et le nouveau client canonique `kadi._sources.wfp_client`.

**Action effectuée :**
1. Ajout d'une notice explicite de dépréciation dans l'en-tête de `data_ingestion.py` indiquant sa suppression prévue en v1.2.0 et redirigeant vers `kadi._sources.wfp_client`.
2. Conservation pour la rétrocompatibilité des tests unitaires du module market (389 tests au vert).

**Statut : `[x]` Terminé**

---

### C5 : Implémenter `soilgrids.py` avec l'API SoilGrids v2.0 (ISRIC)

**Module :** `weather`
**Fichier :** `kadi/_sources/soilgrids.py`
**Sévérité :** Haute (exactitude scientifique)

**Problème :**
L'implémentation originale ne faisait qu'une recherche dans un cache JSON local. Si le cache était absent, la fonction retournait silencieusement `"ferrugineux"` pour toutes les localisations.

**Action réalisée :**
`kadi/_sources/soilgrids.py` a été entièrement réécrit (340 lignes) avec :
1. Appel réel à l'API SoilGrids v2.0 (`/classification/query`)
2. Table de correspondance WRB vers types KadiPy adaptée à la pédologie béninoise
3. Stratégie en cascade : cache local JSON -> API SoilGrids -> fallback statique
4. Retry avec backoff exponentiel (3 tentatives)
5. 18 tests unitaires dans `tests/weather/test_soilgrids.py`

**Statut : `[x]` Terminé**

---

### C6 : Ajouter des tests pour le connecteur CHIRPS

**Module :** `weather`
**Fichier :** `kadi/_sources/chirps.py`
**Sévérité :** Haute (robustesse)

**Problème :**
Couverture de test incomplète sur la logique interne de téléchargement et d'extraction ponctuelle de rasters.

**Action réalisée :**
Ajout de tests unitaires complets dans `tests/weather/test_chirps.py` couvrant `_construire_url`, `_telecharger_et_decouper_raster` (succès, 404, erreurs réseau, nettoyage de fichier partiel) et `_extraire_valeur_ponctuelle`.
La couverture de `chirps.py` est passée de 54% à 89%.

**Statut : `[x]` Terminé**

---

## Partie C — Tâches v1.2.0 (stratégiques, planifiées)

Ces points renforcent la valeur scientifique et l'adoption du package.

---

### S1 : Activer Penman-Monteith dans le bilan hydrique

**Module :** `weather` | **Fichier :** `kadi/weather/hydrology.py` | **Horizon :** v1.2.0

**Contexte :**
La méthode `et0_fao56_penman()` est implémentée mais jamais appelée. Le bilan hydrique utilise exclusivement Hargreaves-Samani.

**Action :**
Ajouter un paramètre `method='hargreaves'|'penman'` à `compute_water_balance()`.

**Statut : `[~]` Reporté v1.2.0**

---

### S2 : Évaluer et améliorer le modèle de prévision de prix

**Module :** `market` | **Fichier :** `kadi/market/forecasting.py` | **Horizon :** v1.2.0

**Contexte :**
Calculer le MAPE réel sur des données WFP Bénin connues (backtesting) et intégrer Prophet si le MAPE dépasse 20%.

**Statut : `[~]` Reporté v1.2.0**

---

### S3 : Publication de métriques de performance

**Module :** Documentation | **Fichier :** `benchmarks/performance_report.ipynb` | **Horizon :** v1.2.0

**Statut : `[~]` Reporté v1.2.0**

---

### S4 : Connecteurs vers les données béninoises locales

**Module :** `_sources` | **Horizon :** v1.2.0

**Statut : `[~]` Reporté v1.2.0**

---

### S5 : Interface de visualisation ou notebook interactif

**Module :** Nouveau | **Horizon :** v1.2.0 (notebook), v2.0.0 (interface web)

**Statut : `[~]` Reporté v1.2.0**

---

### S6 : Transport multimodal dans `logistics.py`

**Module :** `market` | **Fichier :** `kadi/market/logistics.py` | **Horizon :** v2.0.0

**Statut : `[~]` Reporté v2.0.0**

---

### S7 : Feuille de route datée dans `ROADMAP.md`

**Module :** Documentation | **Horizon :** Avant toute publication externe

**Statut : `[ ]` À faire**

---

## Tableau récapitulatif global

### Tâches v1.1.0 (toutes terminées)

| # | Module | Sévérité | Description courte | Statut |
|---|--------|----------|--------------------|--------|
| P8 | `kidas` | Critique | Rapport `execute()` aligné sur la documentation | `[x]` |
| P6 | `market` | Haute | `is_simulated` propagé depuis la vraie source | `[x]` |
| P13 | Infrastructure | Haute | `requirements.txt` réconcilié | `[x]` |
| P3 | `weather` | Haute | SPI via loi Gamma (McKee et al. 1993) | `[x]` |
| P4 | `market` | Haute | Bornes GPS lues depuis `CONFIG` | `[x]` |
| P9 | `kidas` | Haute | `fix_dates()` compteur corrigé | `[x]` |
| P5 | `market` | Moyenne | `get_market_functionality_index()` lève `NotImplementedError` | `[x]` |
| P16 | CI | Moyenne | `pytest-cov` ajouté + CI mise à jour | `[x]` |
| P9-WFP | `market` | N/A | API WFP DataBridges + taux de change dynamiques | `[x]` |
| P2 | `weather` | Faible | Alias `temperature_avg/mean` centralisé | `[x]` |
| P10 | `kidas` | Faible | Clé de cache SHA-256 | `[x]` |
| P11 | Infrastructure | Faible | `MODELS_DIR` documenté | `[x]` |
| P12 | Infrastructure | Moyenne | `EXCHANGE_RATES` dynamiques | `[x]` |
| P1 | `weather` | Moyenne | README mis à jour (CHIRPS/Open-Meteo) | `[x]` |
| P7 | `market` | Faible | `_portfolio_heuristique()` calcule un revenu réel | `[x]` |
| P14 | Tests | Moyenne | Tests `kadi.cache` ajoutés | `[x]` |
| P15 | Tests | Faible | Tests `kadi.config` ajoutés | `[x]` |

### Tâches v1.1.0 : audit complémentaire (toutes terminées)

| # | Module | Sévérité | Description courte | Statut |
|---|--------|----------|--------------------|--------|
| C1 | Infrastructure | Haute | Incrémenter la version à `1.1.0` dans `pyproject.toml` | `[x]` |
| C2 | Infrastructure | Critique | Retirer l'identifiant personnel de `config.py` | `[x]` |
| C3 | `weather` | Haute | Corriger `data_source` écrite `"mock_api"` dans le cache SQLite | `[x]` |
| C4 | `market` | Moyenne | Clarifier ou supprimer `data_ingestion.py` | `[x]` |
| C5 | `weather` | Haute | Client SoilGrids v2.0 + table WRB + tests | `[x]` |
| C6 | `weather` | Haute | Tests unitaires CHIRPS complétés (couverture 89%) | `[x]` |

### Tâches stratégiques (v1.2.0 et au-delà)

| # | Module | Description courte | Horizon | Statut |
|---|--------|--------------------|---------|--------|
| S1 | `weather` | Activer Penman-Monteith dans `compute_water_balance()` | v1.2.0 | `[~]` |
| S2 | `market` | Évaluer le MAPE réel + intégrer Prophet | v1.2.0 | `[~]` |
| S3 | Documentation | Publier métriques de performance dans un notebook | v1.2.0 | `[~]` |
| S4 | `_sources` | Connecteurs MAEP / INSAE | v1.2.0 | `[~]` |
| S5 | Nouveau | Notebook interactif pour utilisateurs terrain | v1.2.0 | `[~]` |
| S6 | `market` | Transport multimodal (fluvial) dans `logistics.py` | v2.0.0 | `[~]` |
| S7 | Documentation | Créer `ROADMAP.md` avec planning daté | Avant publication | `[ ]` |
