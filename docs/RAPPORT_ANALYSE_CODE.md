# Rapport d'analyse du code — KadiPy

**Projet :** KadiPy — « le pandas de l'agriculture africaine »
**Version analysée :** 1.0.0 (branche `main`)
**Date :** 17 juillet 2026
**Périmètre :** ~11 800 lignes de Python (`kadi/`) + 238 tests unitaires

---

## 1. Synthèse

KadiPy est une bibliothèque Python mature et bien structurée, destinée à
l'analyse de données agricoles au Bénin et en Afrique de l'Ouest. Le code
est de **bonne qualité générale** : architecture claire en trois modules
métier, documentation abondante (docstrings et notebooks), gestion
d'erreurs soignée et une approche « offline-first » cohérente.

**Verdict global : solide, prêt pour la production sur son périmètre V1.**
Les points d'amélioration relevés sont mineurs (dette technique légère,
quelques incohérences de configuration), sans bug bloquant identifié.

| Critère | Évaluation |
|---|---|
| Architecture | ★★★★★ Excellente séparation des responsabilités |
| Lisibilité / documentation | ★★★★★ Docstrings complètes, code commenté en français |
| Tests | ★★★★☆ 238 tests passent ; couverture d'intégration réseau à confirmer |
| Gestion d'erreurs | ★★★★☆ Hiérarchie d'exceptions dédiée, fallbacks robustes |
| Cohérence configuration | ★★★☆☆ Quelques doublons / config morte |
| Sécurité | ★★★★★ Aucune fuite de secret, pas de code dangereux |

---

## 2. Architecture

Le paquet `kadi/` s'organise en trois modules métier indépendants,
orchestrés par des façades de haut niveau.

```
kadi/
├── __init__.py          # Version + logger racine + set_verbosity()
├── config.py            # Configuration centralisée (CONFIG, URLs, taux)
├── exceptions.py        # Hiérarchie d'exceptions KadiException
├── cache.py             # Cache SQLite global
├── _utils/              # Réseau (retry), coordonnées GPS
├── _sources/            # Connecteurs bas niveau (Open-Meteo, CHIRPS, SoilGrids)
│
├── weather/             # Météo & agronomie (façade : WeatherSession)
│   ├── data, location, phenology, hydrology, risk
│
├── market/              # Économie de marché (façade : Market)
│   ├── pricing, forecasting, logistics, decision_support
│   ├── data_ingestion (client WFP), backtesting, _cache, _normalization
│
└── kidas/               # Pipeline de données (façade : DataPipeline)
    ├── cleaner, validator, normalizer, cache, pipeline
    └── sources/         # csv, excel, json, netcdf, api
```

**Points forts de l'architecture :**

- **Pattern façade cohérent** : chaque module expose une classe unique
  (`WeatherSession`, `Market`, `DataPipeline`) qui masque la complexité
  des sous-modules. Le point d'entrée est clair pour l'utilisateur final.
- **Injection de dépendances** : `Market` injecte le `pricing` réel dans
  `DecisionSupport`, et un `WeatherSession` optionnel dans `MarketLogistics`
  (intégration météo/logistique « Phase 4 »). Découplage propre et testable.
- **Initialisation paresseuse** : `WeatherSession._ensure_components()` ne
  charge les données historiques/prévisions que lorsqu'un composant en a
  besoin — économie d'appels réseau bienvenue en mode offline-first.
- **Modules privés préfixés** (`_utils`, `_sources`, `_cache`) : la surface
  d'API publique est bien délimitée.

---

## 3. Qualité du code

### Points forts

- **Documentation exemplaire** : chaque fonction publique dispose d'une
  docstring structurée (Args / Returns / Raises / Exemples). Rare et
  précieux. Complétée par des notebooks pédagogiques dans `docs/`.
- **Validation des entrées** : les façades valident systématiquement types
  et bornes avant traitement (ex. `_valider_coordonnees`, `_valider_location`
  dans `market/__init__.py`), évitant les erreurs silencieuses.
- **Gestion d'erreurs mûre** : hiérarchie d'exceptions dédiée
  (`KadiException` → `DataSourceError`, `ValidationError`, `KidasReadError`…),
  avec des sous-classes spécifiques par module.
- **Robustesse réseau** : retry avec backoff exponentiel
  (`_utils/network.py`, `data_ingestion._get_with_retry`), distinction
  correcte entre erreurs temporaires (429/5xx → retry) et permanentes
  (401/403/404 → échec immédiat).
- **Mode dégradé transparent** : sans clé API WFP, le système bascule en
  données simulées avec un drapeau explicite `is_simulated=True` et un
  `confidence_score` bas. L'utilisateur est toujours informé de la fiabilité.
- **Propreté** : aucun `except:` nu, aucun `print()` dans le code de
  bibliothèque (uniquement dans docstrings/README), aucun `TODO/FIXME/HACK`
  laissé traîner. Logging via `logging.getLogger(__name__)` partout.
- **Gestion des secrets** : `_charger_token()` lit le token depuis
  l'environnement puis un `.env`, sans jamais le journaliser — aucune fuite.

### Points d'amélioration (mineurs)

1. **Configuration morte** — `config.py:33` définit
   `MODELS_DIR = .../_ml/models`, mais le dossier `kadi/_ml/` **n'existe pas**
   et `MODELS_DIR` n'est référencé nulle part ailleurs. À supprimer ou à
   documenter comme réservé pour une évolution future.

2. **Incohérence entre boîtes géographiques (GPS bbox)** — trois définitions
   coexistent :
   - `config.py` → `weather.gps_validation_bbox` : lat [2.5, 12.5]
   - `config.py` → `kidas.gps_validation_bbox` : Afrique de l'Ouest élargie
   - `market/__init__.py:22-25` → constantes **codées en dur** `_LAT_MIN=6.0`…
     au lieu de lire `CONFIG`.

   Le module `market` réimplémente ses propres bornes plutôt que de
   s'appuyer sur la configuration centralisée. À harmoniser pour éviter
   qu'un point valide dans un module soit rejeté dans un autre.

3. **`requirements.txt` et `pyproject.toml` désynchronisés** —
   `requirements.txt` déclare `xlrd<2.0` et `dask>=2023.1` **absents** de
   `pyproject.toml`. Or `pyproject.toml` est la source de vérité pour
   l'installation via `pip install kadipy`. Résultat : un utilisateur final
   n'aura ni `xlrd` (lecture `.xls`) ni `dask`. À réconcilier — idéalement
   supprimer `requirements.txt` au profit du seul `pyproject.toml`, ou le
   régénérer à partir de celui-ci.

4. **`EXCHANGE_RATES` statique** — les taux de change (`config.py:212`) sont
   codés en dur avec un commentaire « Mise à jour quotidienne prévue » non
   implémenté. Acceptable en V1, mais à surveiller (les taux XOF/USD dérivent).

5. **Volume de `except Exception`** — plusieurs modules capturent
   `Exception` largement (jusqu'à 6 occurrences dans `data_ingestion.py`,
   `logistics.py`). C'est cohérent avec la stratégie de repli défensive,
   mais quelques-uns pourraient cibler des exceptions plus précises pour ne
   pas masquer de vrais bugs.

---

## 4. Tests et CI

- **238 tests unitaires passent** (12 s) après installation des dépendances.
  Bonne couverture des trois modules (`test_market/`, `test_kidas/`,
  `weather/`), incluant des tests de performance et d'intégration mockés.
- **Tests d'intégration réseau** (`tests/integrations/`, marqueur
  `integration`) : présents mais non exécutés dans cette analyse (dépendent
  d'appels externes). Bon réflexe de les isoler via un marqueur pytest.
- **CI GitHub Actions bien conçue** :
  - `tests.yml` : matrice Python 3.9 → 3.12, sur push et PR.
  - `publish.yml` : publication PyPI via **Trusted Publishing (OIDC)**,
    sans secret stocké — excellente pratique de sécurité.
  - `docs.yml` : publication MkDocs + `mike` (versionnage de doc).
  - Les permissions des workflows sont restreintes au minimum
    (`contents: read`), suite au correctif de scan de code (alerte #1).

**Suggestion :** ajouter une mesure de couverture (`pytest-cov`) au workflow
`tests.yml` pour suivre l'évolution dans le temps.

---

## 5. Sécurité

Aucun problème de sécurité identifié :

- Pas de secret en dur ; le token WFP est lu depuis l'environnement/`.env`
  et **jamais journalisé**.
- Publication PyPI en OIDC (pas de token PyPI stocké).
- Pas d'exécution dynamique (`eval`/`exec`), pas de désérialisation non sûre
  exposée à des entrées externes.
- Permissions CI minimales.

---

## 6. Recommandations priorisées

| Priorité | Action | Effort |
|---|---|---|
| 🔴 Haute | Réconcilier `requirements.txt` ↔ `pyproject.toml` (xlrd, dask) | Faible |
| 🟠 Moyenne | Supprimer `MODELS_DIR`/`_ml` mort ou créer le dossier | Faible |
| 🟠 Moyenne | Centraliser les bornes GPS de `market` dans `CONFIG` | Faible |
| 🟡 Basse | Ajouter `pytest-cov` à la CI | Faible |
| 🟡 Basse | Rendre `EXCHANGE_RATES` configurable / dynamique | Moyen |
| 🟡 Basse | Cibler certaines `except Exception` trop larges | Moyen |

---

## 7. Conclusion

KadiPy est un projet **bien conçu, bien documenté et bien testé**, avec une
architecture claire et des choix d'ingénierie solides (façades, injection de
dépendances, mode offline-first, CI OIDC). La dette technique est faible et
concerne surtout des incohérences de configuration sans impact fonctionnel
majeur. Le traitement des cinq recommandations ci-dessus renforcerait la
maintenabilité sans remettre en cause l'existant.
