# Plan de refactoring — kadipy

## Objectif

Simplifier l'API publique du package kadipy en raccourcissant les chemins
d'importation, en uniformisant les noms des classes, méthodes et attributs
selon une convention inspirée de Pandas et de scikit-learn, et en éliminant
les doublons existants. Le code interne reste découpé de façon modulaire ;
seule l'interface exposée aux utilisateurs change.

---

## Résumé des changements

- 26 classes renommées ou fusionnées
- ~140 méthodes et attributs renommés
- 4 nouveaux chemins d'importation raccourcis (`kadi.io`, `kadi.kidas`)
- 1 doublon supprimé (`WFPDataBridgesClient` dans `market.data_ingestion`)
- 15 exceptions simplifiées (suffixe `Error` unifié, préfixe `Kidas` supprimé)

---

## Phase 0 — Préparation

Avant de toucher au code, il faut poser les bases pour travailler en sécurité.

- `[ ]` **0.1** Vérifier que toute la suite de tests passe sur la branche `main`.
  ```bash
  source .kadi_venv/bin/activate
  pytest --tb=short -q
  ```
- `[ ]` **0.2** Créer une branche dédiée.
  ```bash
  git checkout -b refactor/api-simplification
  ```
- `[ ]` **0.3** Installer `rope` (outil de refactoring Python) dans l'environnement.
  ```bash
  pip install rope
  ```
- `[ ]` **0.4** Prendre un snapshot du taux de couverture actuel pour le comparer
  en fin de phase.
  ```bash
  pytest --cov=kadi --cov-report=term-missing -q > .refactor_coverage_before.txt
  ```

---

## Phase 1 — Exceptions (`kadi/exceptions.py`)

Priorité haute : les exceptions sont importées partout dans le package. Les
corriger en premier simplifie toutes les phases suivantes.

### Règles
- Renommer `KadiException` en `KadiError`.
- Supprimer le préfixe `Kidas` de toutes les exceptions du même fichier.
- Fusionner `KidasValidationError` avec `ValidationError` et `KidasCacheError`
  avec `CacheError`.
- Renommer `InsufficientData` en `DataError`, `LocationNotFound` en
  `LocationError`, `CropNotFound` en `CropError`.

### Fichiers à modifier
- `[ ]` **1.1** `kadi/exceptions.py` : appliquer tous les renommages.
- `[ ]` **1.2** Chercher et remplacer toutes les occurrences dans le package.
  ```bash
  grep -rn "KadiException\|KidasReadError\|KidasWriteError\|KidasConnectionError\|KidasCleaningError\|KidasValidationError\|KidasCacheError\|KidasPipelineError\|InsufficientData\|LocationNotFound\|CropNotFound\|DataSourceError" kadi/ tests/
  ```
- `[ ]` **1.3** Lancer les tests pour valider.

---

## Phase 2 — Sources de données (`kadi/kidas/sources/`)

### Règles
- Renommer `DataSource` en `Source` (classe de base abstraite).
- Renommer les sous-classes : supprimer le suffixe `Data` (`CSVDataSource`
  devient `CSVSource`, etc.).
- Harmoniser les attributs : `source_path` -> `path`, `source_type` -> `kind`.
- Renommer les méthodes internes en anglais.
- Exposer toutes les sources dans `kadi/kidas/sources/__init__.py`.

### Fichiers à modifier

- `[ ]` **2.1** `kadi/kidas/sources/base.py` : renommer la classe et ses méthodes.
- `[ ]` **2.2** `kadi/kidas/sources/csv_source.py` : renommer classe et méthodes.
- `[ ]` **2.3** `kadi/kidas/sources/excel_source.py` : renommer classe et méthodes.
- `[ ]` **2.4** `kadi/kidas/sources/json_source.py` : renommer classe et méthodes.
- `[ ]` **2.5** `kadi/kidas/sources/netcdf_source.py` : renommer classe et méthodes.
- `[ ]` **2.6** `kadi/kidas/sources/api_source.py` : renommer classe et méthodes.
- `[ ]` **2.7** `kadi/kidas/sources/__init__.py` : exporter toutes les classes.
  ```python
  from .base import Source
  from .csv_source import CSVSource
  from .excel_source import ExcelSource
  from .json_source import JSONSource
  from .netcdf_source import NetCDFSource
  from .api_source import APISource
  ```
- `[ ]` **2.8** Lancer les tests.

---

## Phase 3 — Pipeline KIDAS (`kadi/kidas/`)

### Règles
- `DataCleaner` -> `Cleaner`, `DataValidator` -> `Validator`,
  `DataNormalizer` -> `Normalizer`, `DataCache` -> `Cache`,
  `DataPipeline` -> `Pipeline`.
- Renommer les méthodes et attributs selon les propositions.
- Traduire en anglais tous les noms restants en français.
- Exposer les classes dans `kadi/kidas/__init__.py`.

### Fichiers à modifier

- `[ ]` **3.1** `kadi/kidas/cleaner.py`
- `[ ]` **3.2** `kadi/kidas/validator.py`
- `[ ]` **3.3** `kadi/kidas/normalizer.py`
- `[ ]` **3.4** `kadi/kidas/cache.py`
- `[ ]` **3.5** `kadi/kidas/pipeline.py`
- `[ ]` **3.6** `kadi/kidas/__init__.py` : exporter toutes les classes.
  ```python
  from .cleaner import Cleaner
  from .validator import Validator
  from .normalizer import Normalizer
  from .cache import Cache
  from .pipeline import Pipeline
  from .sources import Source, CSVSource, ExcelSource, JSONSource, NetCDFSource, APISource
  ```
- `[ ]` **3.7** Lancer les tests.

---

## Phase 4 — Clients externes (`kadi/_sources/`)

### Règles
- Renommer `WFPDataBridgesClient` en `WFPClient` dans `_sources/wfp_client.py`.
- Renommer `ExchangeRateClient` : conserver le nom, simplifier les méthodes
  internes (en anglais).
- Supprimer la classe `WFPDataBridgesClient` dans `kadi/market/data_ingestion.py`
  et la remplacer par un import depuis `kadi._sources.wfp_client`.

### Fichiers à modifier

- `[ ]` **4.1** `kadi/_sources/wfp_client.py` : renommer classe et méthodes.
- `[ ]` **4.2** `kadi/_sources/exchange_client.py` : méthodes en anglais.
- `[ ]` **4.3** `kadi/market/data_ingestion.py` : supprimer la classe dupliquée,
  importer `WFPClient` depuis `kadi._sources.wfp_client`.
- `[ ]` **4.4** Vérifier tous les imports qui référencent `WFPDataBridgesClient`.
  ```bash
  grep -rn "WFPDataBridgesClient\|data_ingestion" kadi/ tests/
  ```
- `[ ]` **4.5** Lancer les tests.

---

## Phase 5 — Module weather (`kadi/weather/`)

### Règles
- `WeatherSession` -> `Weather` (façade principale, exposée à `kadi.Weather`).
- `WeatherData` -> `WeatherLoader`.
- `RiskIndicators` -> `Risk`.
- `Location` : conserver le nom, abréger `latitude`/`longitude` en `lat`/`lon`.
- Renommer les méthodes et attributs selon les propositions.
- Toutes les méthodes internes encore en français passent en anglais.

### Fichiers à modifier

- `[ ]` **5.1** `kadi/weather/location.py`
- `[ ]` **5.2** `kadi/weather/data.py`
- `[ ]` **5.3** `kadi/weather/hydrology.py`
- `[ ]` **5.4** `kadi/weather/phenology.py`
- `[ ]` **5.5** `kadi/weather/risk.py`
- `[ ]` **5.6** `kadi/weather/session.py` : renommer la classe en `Weather`.
- `[ ]` **5.7** `kadi/weather/__init__.py` : exporter `Weather`.
  ```python
  from .session import Weather
  from .location import Location
  ```
- `[ ]` **5.8** Lancer les tests.

---

## Phase 6 — Module market (`kadi/market/`)

### Règles
- `MarketPricing` -> `Pricing`, `MarketForecasting` -> `Forecasting`,
  `MarketLogistics` -> `Logistics`, `MarketBacktester` -> `Backtester`,
  `DecisionSupport` -> `Advisor`.
- Façade `Market` : conserver le nom, simplifier les méthodes et attributs.
- Renommer toutes les méthodes et attributs en français.
- Exposer dans `kadi/market/__init__.py`.

### Fichiers à modifier

- `[ ]` **6.1** `kadi/market/pricing.py`
- `[ ]` **6.2** `kadi/market/forecasting.py`
- `[ ]` **6.3** `kadi/market/logistics.py`
- `[ ]` **6.4** `kadi/market/decision_support.py`
- `[ ]` **6.5** `kadi/market/backtesting.py`
- `[ ]` **6.6** `kadi/market/__init__.py` : exposer toutes les classes internes.
  ```python
  from .pricing import Pricing
  from .forecasting import Forecasting
  from .logistics import Logistics
  from .decision_support import Advisor
  from .backtesting import Backtester
  ```
- `[ ]` **6.7** Lancer les tests.

---

## Phase 7 — Point d'entrée racine (`kadi/__init__.py`)

Cette phase expose l'API simplifiée de premier niveau, qui sera le point
d'entrée principal pour les utilisateurs du package.

### Cible d'utilisation après refactoring

```python
import kadi as kd

# Météo et agronomie
ws = kd.Weather(lat=12.5, lon=-1.5, name="Ouagadougou")

# Marchés
mk = kd.Market(lat=12.5, lon=-1.5, location="Ouagadougou", weather_session=ws)

# Traitement de données
df = kd.read_csv("donnees.csv")
cleaned = kd.Cleaner(df).drop_dupes().fill_missing().report()
pipeline = kd.Pipeline().load("source.csv").clean("all").run()

# Accès aux sous-modules
from kadi.market import Pricing, Forecasting, Logistics
from kadi.weather import Weather, Location
from kadi.kidas import Cleaner, Validator, Normalizer, Pipeline, Cache
```

### Fichiers à modifier

- `[ ]` **7.1** `kadi/__init__.py` : ajouter les exports de premier niveau.
  ```python
  from .weather.session import Weather
  from .market import Market
  from .kidas import Cleaner, Validator, Normalizer, Pipeline, Cache
  from .kidas.sources import CSVSource, ExcelSource, JSONSource, NetCDFSource, APISource

  # Fonctions de lecture rapide (style Pandas)
  def read_csv(path, **kwargs):
      return CSVSource(path, **kwargs).read()

  def read_excel(path, **kwargs):
      return ExcelSource(path, **kwargs).read()

  def read_json(path, **kwargs):
      return JSONSource(path, **kwargs).read()
  ```
- `[ ]` **7.2** Lancer les tests complets.

---

## Phase 8 — Tests et documentation

### Tests

- `[ ]` **8.1** Mettre à jour tous les imports dans `tests/` pour utiliser les
  nouveaux noms.
- `[ ]` **8.2** Ajouter des tests spécifiques pour les nouvelles fonctions de
  premier niveau (`read_csv`, `read_excel`, `read_json`).
- `[ ]` **8.3** Vérifier la couverture finale.
  ```bash
  pytest --cov=kadi --cov-report=term-missing -q > .refactor_coverage_after.txt
  diff .refactor_coverage_before.txt .refactor_coverage_after.txt
  ```
- `[ ]` **8.4** Vérifier le respect des règles PEP8.
  ```bash
  flake8 kadi/ --max-line-length=88
  ```

### Documentation

- `[ ]` **8.5** Mettre à jour le `README.md` avec les nouveaux exemples
  d'utilisation.
- `[ ]` **8.6** Mettre à jour la documentation dans `docs/` si elle existe.
- `[ ]` **8.7** Vérifier que toutes les docstrings des classes et méthodes
  renommées sont mises à jour (en français, selon les règles du projet).

---

## Phase 9 — Finalisation

- `[ ]` **9.1** Lancer la suite de tests complète une dernière fois.
  ```bash
  pytest -v
  ```
- `[ ]` **9.2** Vérifier la liste des exports publics dans chaque `__init__.py`.
- `[ ]` **9.3** Créer un commit propre.
  ```bash
  git add -A
  git commit -m "refactor: simplification de l'API publique (noms et chemins)"
  ```
- `[ ]` **9.4** Ouvrir une Pull Request vers `main` pour revue.

---

## Ordre de priorité des phases

```
Phase 0 (préparation)
    |
    v
Phase 1 (exceptions) <-- dépendance transversale
    |
    v
Phase 2 (sources)
    |
    v
Phase 3 (pipeline kidas)  <-- dépend de Phase 2
    |
    v
Phase 4 (clients _sources) <-- dépend de Phase 1
    |
    v
Phase 5 (weather) <-- dépend de Phase 1, 4
    |
    v
Phase 6 (market)  <-- dépend de Phase 1, 4, 5
    |
    v
Phase 7 (__init__ racine) <-- dépend de toutes les phases
    |
    v
Phase 8 (tests + docs)
    |
    v
Phase 9 (finalisation)
```

---

## Risques et points d'attention

| Risque | Mitigation |
|---|---|
| Casser des imports dans des scripts utilisateurs externes | Ajouter des alias de compatibilité avec `DeprecationWarning` si le package est publié |
| `WFPDataBridgesClient` dupliqué : deux comportements légèrement différents | Bien analyser les différences avant fusion (Phase 4) |
| Méthodes de calcul avec des noms scientifiques (`et0_hargreaves`, `runoff_cn`, etc.) | Ces noms sont intentionnellement conservés tels quels |
| Couverture de tests insuffisante sur certains modules | Comparer les rapports avant/après (Phase 8.3) |
