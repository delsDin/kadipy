# Rapport complet — État et intégrations de KadiPy

**Date :** 6 août 2026
**Version analysée :** branche `v1.1.0`
**Méthode :** lecture intégrale du code source + croisement de trois documents de référence (`analyse_00.md`, `analyse_1.0.0.md`, `suivi.md`)

Ce document est la synthèse unique du travail d'audit mené sur KadiPy. Il répond à deux questions : qu'est-ce qui a été fait, et qu'est-ce qu'il reste à faire ?

---

## Partie 1 — Ce qui a été fait : état de la v1.1.0

### 1.1 Bilan des corrections

Toutes les tâches identifiées dans `analyse_1.0.0.md` et tracées dans `suivi.md` sont confirmées dans le code source. Le cycle de correction de la v1.1.0 est complet.

| Problème corrigé | Localisation dans le code |
|------------------|--------------------------|
| Rapport `execute()` aligné sur la documentation | `kadi/kidas/pipeline.py` lignes 381-394 |
| Flag `is_simulated` propagé depuis la vraie source | `kadi/market/decision_support.py` |
| SPI calculé via loi Gamma avec correction de masse | `kadi/weather/risk.py` lignes 129-152 |
| Bornes GPS lues depuis `CONFIG` (non codées en dur) | `kadi/market/__init__.py` lignes 29-33 |
| `fix_dates()` accumule correctement les corrections | `kadi/kidas/cleaner.py` |
| Clé de cache sécurisée par SHA-256 dans `execute()` | `kadi/kidas/pipeline.py` lignes 323-326 |
| Alias `temperature_avg/mean` centralisé | `kadi/weather/data.py` méthode statique |
| Client WFP HAPI et taux de change dynamiques | `kadi/_sources/wfp_client.py` et `exchange_client.py` |
| Tests pour `kadi.cache` et `kadi.config` | `tests/test_cache.py` et `tests/test_config.py` |

### 1.2 État architectural

Le package est organisé en trois modules principaux :

- **`kadi.weather`** : façade `WeatherSession` orchestrant `Location`, `WeatherData`, `Phenology`, `Hydrology` et `RiskIndicators`. Les données viennent d'Open-Meteo (températures) et CHIRPS (précipitations historiques) avec cache SQLite et repli hors-ligne automatique.
- **`kadi.market`** : façade `Market` orchestrant `MarketPricing`, `MarketForecasting`, `MarketLogistics` et `DecisionSupport`. Les prix viennent de l'API HAPI HumData (PAM) avec fallback sur données simulées si l'identifiant n'est pas configuré.
- **`kadi.kidas`** : pipeline fluide `DataPipeline` avec auto-détection de source (CSV, Excel, JSON, NetCDF, API), nettoyage, validation et normalisation.

L'intégration météo-marché est en place (Phase 4) : un `WeatherSession` peut être injecté dans `Market` pour ajuster les coûts logistiques selon la probabilité de pluie.

---

## Partie 2 — Ce qui reste à faire

### 2.1 Intégrations critiques (à traiter avant publication)

Ces points créent des risques réels : données incorrectes, faille de sécurité, ou incohérence visible pour l'utilisateur.

---

#### C1 — Incrémenter la version du package

**Fichier :** `pyproject.toml` ligne 11

Le fichier déclare `version = "1.0.0"` alors que la branche s'appelle `v1.1.0` et que des corrections majeures ont été livrées.

```toml
# Corriger :
version = "1.1.0"
```

**Impact si ignoré :** Publication sur PyPI avec un numéro de version trompeuse. Les changelogs et tags Git seront incohérents.

---

#### C2 — Retirer l'identifiant personnel de `config.py`

**Fichier :** `kadi/config.py` ligne 264

La variable `HAPI_APP_IDENTIFIER` contient une valeur par défaut non nulle encodant l'adresse `kadipy:delsdenla.dev@gmail.com` en base64. Cette valeur est exposée publiquement dans le code source.

**Problèmes :**
1. Quiconque installe le package peut décoder cet identifiant.
2. L'utilisateur sans variable d'environnement utilise votre identifiant sans le savoir.

```python
# Corriger :
HAPI_APP_IDENTIFIER = os.environ.get("HAPI_APP_IDENTIFIER", "")
```

**Impact si ignoré :** Exposition de credentials personnels lors de la publication sur PyPI ou GitHub.

---

#### C3 — Corriger le stockage de `data_source` dans le cache SQLite

**Fichier :** `kadi/weather/data.py` ligne 222

La valeur `"mock_api"` est écrite en dur pour toutes les données sauvegardées en cache, quelle que soit leur source réelle (CHIRPS, Open-Meteo, etc.).

```python
# Corriger : utiliser la vraie source extraite du DataFrame
source_val = data["data_source"].dropna().iloc[0] if "data_source" in data.columns else "open-meteo"
cursor.execute("INSERT INTO weather_data (...) VALUES (...)", (..., data_type, source_val, ...))
```

**Impact si ignoré :** Données CHIRPS stockées avec la source `"mock_api"`. Toute analyse de provenance ou de qualité des données en cache est faussée.

---

#### C4 — Clarifier ou supprimer `data_ingestion.py`

**Fichier :** `kadi/market/data_ingestion.py` (25 485 octets)

Avec l'arrivée de `WFPDataBridgesClient`, ce fichier est probablement redondant. Sans audit explicite, il est impossible de savoir si des méthodes de ce fichier sont encore appelées en parallèle du nouveau client.

**Action :** Vérifier les imports dans tous les fichiers de `kadi/market/`. Si le fichier n'est plus importé, le supprimer. Sinon, documenter son rôle résiduel dans son en-tête.

**Impact si ignoré :** Confusion pour tout mainteneur ou contributeur. Risque de comportements dupliqués si les deux clients coexistent.

---

#### C5 — Vérifier `soilgrids.py` et son intégration dans `hydrology.py`

**Fichier :** `kadi/_sources/soilgrids.py` (1 580 octets)

`hydrology.py` appelle `fetch_soil_type(lat, lon)` pour déterminer automatiquement le type de sol. Avec 1 580 octets, cette implémentation est très légère. Si la fonction retourne une valeur statique ou incorrecte, le bilan hydrique sera silencieusement erroné.

**Action :** Lire le contenu de `soilgrids.py`, vérifier si l'appel est réel (API SoilGrids) ou une valeur de repli statique, et documenter le comportement.

**Impact si ignoré :** Bilan hydrique calculé avec un type de sol incorrect sans aucun avertissement visible.

---

#### C6 — Ajouter des tests pour le connecteur CHIRPS

**Fichier :** `kadi/_sources/chirps.py`

Le connecteur CHIRPS est la source de données la plus complexe du package (téléchargement de rasters GeoTIFF, découpage spatial, cache de fichiers, gestion du délai de 15 jours). Aucun test dédié n'existe.

**Tests minimaux à créer dans `tests/weather/test_chirps.py` :**
- Test de `_chirps_disponible_pour()` : vérifie qu'une date d'il y a 2 mois est disponible et qu'une date d'hier ne l'est pas.
- Test de `_construire_url()` : vérifie le format de l'URL pour une date donnée.
- Test de `fetch_historical_precipitation()` avec un mock HTTP simulant un raster valide.

**Impact si ignoré :** La source de données principale pour l'historique de précipitations n'est pas protégée par des tests. Une régression passera inaperçue.

---

### 2.2 Intégrations stratégiques (à planifier)

Ces points renforcent la valeur scientifique et l'adoption du package. Ils ne bloquent pas le fonctionnement actuel.

---

#### P1 — Activer Penman-Monteith dans le bilan hydrique

**Fichier :** `kadi/weather/hydrology.py`

`et0_fao56_penman()` est implémentée mais jamais appelée. Le bilan hydrique utilise exclusivement Hargreaves-Samani. Pour les cultures sensibles (riz, tomate), la différence avec Penman-Monteith peut atteindre 15 à 25% sur l'ETo calculé.

Open-Meteo fournit les variables nécessaires (humidité, vent, rayonnement solaire). L'intégration consiste à ajouter un paramètre `method='hargreaves'|'penman'` à `compute_water_balance()`.

**Horizon :** v1.2.0

---

#### P2 — Évaluer et améliorer le modèle de prévision de prix

**Fichier :** `kadi/market/forecasting.py`

Le modèle actuel (régression linéaire + harmoniques de Fourier) est solide et interprétable. Avant d'aller vers Prophet ou LSTM, la priorité est de calculer le MAPE réel sur des données historiques WFP disponibles et de publier ce chiffre dans la documentation. C'est la métrique manquante depuis la v1.0.0.

**Horizon :** v1.2.0 (évaluation + Prophet), v2.0.0 (LSTM si pertinent)

---

#### P3 — Connecteurs vers les données béninoises locales

**Contexte :** KadiPy utilise exclusivement des sources internationales. Les données du MAEP et de l'INSAE ne sont pas intégrées.

**Valeur :** C'est la lacune la plus importante pour l'adoption locale. Un outil qui ignore les données officielles béninoises sera difficile à légitimer auprès des institutions.

**Prochaine étape :** Vérifier si le MAEP ou l'INSAE exposent des données via une API ou un portail de données ouvertes. Un connecteur sous forme de `DataSource` kidas est le vecteur naturel d'intégration.

**Horizon :** v1.2.0 (si données accessibles) ou v2.0.0

---

#### P4 — Interface de visualisation ou notebook interactif

**Contexte :** KadiPy est une bibliothèque Python pure. Un conseiller agricole ou un technicien de coopérative ne peut pas l'utiliser sans écrire du code.

**Options :**
1. Notebook Jupyter interactif : rapide à produire, adapté à un public avec formation technique minimale.
2. Interface web légère : plus complexe mais utilisable sur mobile terrain.

**Horizon :** v1.2.0 (notebook), v2.0.0 (interface web)

---

#### P5 — Publication de métriques de performance

**Contexte :** Ni la documentation, ni le README, ni les tests ne publient de métriques concrètes : MAPE du modèle, temps de nettoyage d'un fichier de 10 000 lignes, mémoire utilisée par le cache sur 5 ans de données CHIRPS.

**Action :** Créer `benchmarks/performance_report.ipynb` avec des résultats reproductibles sur des données historiques WFP connues.

**Horizon :** v1.1.1 ou v1.2.0

---

#### P6 — Feuille de route datée

**Contexte :** La feuille de route ne contient pas de dates. Un contributeur ou un partenaire ne peut pas s'organiser autour du planning de KadiPy.

**Action :** Créer un fichier `ROADMAP.md` avec un tableau versions / périmètres / échéances.

| Version | Périmètre | Échéance estimée |
|---------|-----------|-----------------|
| v1.1.0 | Corrections + API WFP | Août 2026 |
| v1.2.0 | Penman-Monteith, MAEP, benchmarks, notebook | Décembre 2026 |
| v2.0.0 | Prophet, interface web, transport multimodal | Juin 2027 |

**Horizon :** Avant toute publication externe

---

## Matrice de priorisation complète

| # | Intégration | Urgence | Impact | Effort | Horizon |
|---|-------------|---------|--------|--------|---------|
| C1 | Incrémenter la version à 1.1.0 | Immédiate | Fiabilité publication | Très faible | Maintenant |
| C2 | Retirer l'identifiant personnel de `config.py` | Immédiate | Sécurité | Très faible | Maintenant |
| C3 | Corriger `data_source` dans le cache SQLite | Immédiate | Qualité des données | Faible | Maintenant |
| C4 | Clarifier ou supprimer `data_ingestion.py` | Immédiate | Maintenabilité | Faible | Maintenant |
| C5 | Vérifier `soilgrids.py` | Immédiate | Exactitude scientifique | Moyen | Maintenant |
| C6 | Tests pour le connecteur CHIRPS | Immédiate | Robustesse | Moyen | Maintenant |
| P1 | Activer Penman-Monteith | Planifiée | Précision agronomique | Faible | v1.2.0 |
| P2 | Améliorer le modèle de prévision de prix | Planifiée | Crédibilité | Moyen | v1.2.0 |
| P3 | Connecteurs MAEP / INSAE | Planifiée | Adoption locale | Élevé | v1.2.0 |
| P4 | Interface de visualisation | Planifiée | Adoption non-technique | Élevé | v1.2.0 |
| P5 | Métriques de performance publiées | Planifiée | Crédibilité académique | Moyen | v1.1.1 |
| P6 | Feuille de route datée | Planifiée | Gouvernance | Très faible | Avant publication |
