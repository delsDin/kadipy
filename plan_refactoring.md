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

## Phase 0 — Préparation (4/4 Terminé)

Avant de toucher au code, il faut poser les bases pour travailler en sécurité.

- `[x]` **0.1** Vérifier que toute la suite de tests passe sur la branche `main`.
  ```bash
  source .kadi_venv/bin/activate
  pytest --tb=short -q
  ```
- `[x]` **0.2** Créer une branche dédiée.
  ```bash
  git checkout -b refactor/api-simplification
  ```
- `[x]` **0.3** Installer `rope` (outil de refactoring Python) dans l'environnement.
  ```bash
  pip install rope
  ```
- `[x]` **0.4** Prendre un snapshot du taux de couverture actuel pour le comparer
  en fin de phase.
  ```bash
  pytest --cov=kadi --cov-report=term-missing -q > .refactor_coverage_before.txt
  ```

---

## Phase 1 — Exceptions (`kadi/exceptions.py`) (4/4 Terminé)

Priorité haute : les exceptions sont importées partout dans le package. Les
corriger en premier simplifie toutes les phases suivantes.

### Règles
- Renommer `KadiException` en `KadiError`.
- Supprimer le préfixe `Kidas` de toutes les exceptions du même fichier.
- Fusionner `KidasValidationError` avec `ValidationError` et `KidasCacheError`
  avec `CacheError`.
- Renommer `InsufficientData` en `DataError`, `LocationNotFound` en
  `LocationError`, `CropNotFound` en `CropError`.
- Ajouter un `DeprecationWarning` sur chaque ancien nom via `__getattr__`.

### Fichiers modifiés
- `[x]` **1.1** `kadi/exceptions.py` : appliquer tous les renommages.
- `[x]` **1.2** Chercher et remplacer toutes les occurrences dans le package.
  ```bash
  grep -rn "KadiException\|KidasReadError\|KidasWriteError\|KidasConnectionError\|KidasCleaningError\|KidasValidationError\|KidasCacheError\|KidasPipelineError\|InsufficientData\|LocationNotFound\|CropNotFound\|DataSourceError" kadi/ tests/
  ```
- `[x]` **1.3** Lancer les tests pour valider.
- `[x]` **1.4** Ajouter les `DeprecationWarning` via `__getattr__` dans `exceptions.py`.
  Les anciens noms continuent de fonctionner mais émettent un avertissement
  explicite indiquant le nouveau nom à utiliser et la version de suppression.
  Exemple du message émis :
  ```
  DeprecationWarning: kadi.exceptions.KadiException est obsolète et sera
  supprimé dans KadiPy v2.0. Utilisez kadi.exceptions.KadiError à la place.
  ```

> **Rétrocompatibilité** : Les anciens noms sont interceptés par `__getattr__`
> au niveau du module. Ils retournent la classe correcte mais émettent un
> `DeprecationWarning` pour guider la migration. Suppression prévue en v2.0.

---

## Phase 2 : Sources de données (`kadi/kidas/sources/`) (8/8 Terminé)

### Règles
- Renommer `DataSource` en `Source` (classe de base abstraite).
- Renommer les sous-classes : supprimer le suffixe `Data` (`CSVDataSource` devient `CSVSource`, etc.).
- Harmoniser les attributs : `source_path` -> `path`, `source_type` -> `kind`.
- Renommer les méthodes internes en anglais.
- Exposer toutes les sources de données dans `kadi/kidas/sources/__init__.py` et utiliser la syntaxe d'importation regroupée depuis ce sous-package.

### Fichiers modifiés

- `[x]` **2.1** `kadi/kidas/sources/base.py` : renommer classe et méthodes.
- `[x]` **2.2** `kadi/kidas/sources/csv_source.py` : renommer classe et méthodes.
- `[x]` **2.3** `kadi/kidas/sources/excel_source.py` : renommer classe et méthodes.
- `[x]` **2.4** `kadi/kidas/sources/json_source.py` : renommer classe et méthodes.
- `[x]` **2.5** `kadi/kidas/sources/netcdf_source.py` : renommer classe et méthodes.
- `[x]` **2.6** `kadi/kidas/sources/api_source.py` : renommer classe et méthodes.
- `[x]` **2.7** `kadi/kidas/sources/__init__.py` : exporter toutes les classes.
  ```python
  from kadi.kidas.sources import (
      Source,
      CSVSource,
      ExcelSource,
      JSONSource,
      APISource,
  )
  ```
- `[x]` **2.8** Lancer les tests (tous les tests `test_sources` et `test_csv_source` passent avec succès).

---

## Phase 3 — Pipeline KIDAS (`kadi/kidas/`) (7/7 Terminé)

### Règles
- `DataCleaner` -> `Cleaner`, `DataValidator` -> `Validator`,
  `DataNormalizer` -> `Normalizer`, `DataCache` -> `Cache`,
  `DataPipeline` -> `Pipeline`.
- Renommer les méthodes et attributs selon les propositions.
- Traduire en anglais tous les noms restants en français.
- Exposer les classes dans `kadi/kidas/__init__.py`.

### Fichiers modifiés

- `[x]` **3.1** `kadi/kidas/cleaner.py` : renommer classe `DataCleaner` -> `Cleaner` et méthodes (`drop_dupes`, `fill_missing`, `drop_outliers`, `parse_dates`, etc.).
- `[x]` **3.2** `kadi/kidas/validator.py` : renommer classe `DataValidator` -> `Validator` et méthodes (`check_schema`, `check_types`, `check_ranges`, etc.).
- `[x]` **3.3** `kadi/kidas/normalizer.py` : renommer classe `DataNormalizer` -> `Normalizer` et méthodes (`norm_cols`, `convert_units`, `std_crops`, etc.).
- `[x]` **3.4** `kadi/kidas/cache.py` : renommer classe `DataCache` -> `Cache` et méthodes (`set`, `get`, `keys`, `purge`, etc.).
- `[x]` **3.5** `kadi/kidas/pipeline.py` : renommer classe `DataPipeline` -> `Pipeline`, méthodes et ajouter raccourcis `load()`, `clean()`, `validate()`, `normalize()`.
- `[x]` **3.6** `kadi/kidas/__init__.py` : exporter toutes les classes (`Cleaner`, `Validator`, `Normalizer`, `Cache`, `Pipeline`, `load_clean`).
  ```python
  from .cleaner import Cleaner
  from .validator import Validator
  from .normalizer import Normalizer
  from .cache import Cache
  from .pipeline import Pipeline
  from .sources import (
      Source,
      CSVSource,
      ExcelSource,
      JSONSource,
      APISource,
      NetCDFSource,
  )
  ```
- `[x]` **3.7** Lancer les tests (`pytest tests/test_kidas/ -v` : 98/98 tests validés).

---

## Phase 4 : Clients externes (`kadi/_sources/`) (7/7 Terminé)

### Règles
- Renommer `WFPDataBridgesClient` en `WFPClient` dans `_sources/wfp_client.py`.
- Renommer `ExchangeRateClient` : conserver le nom, simplifier les méthodes internes en anglais.
- Renommer les fonctions du fichier `chirps.py` en anglais et simplifier.
- Renommer les fonctions du fichier `soilgrids.py` en anglais et simplifier.
- Rediriger et déprécier la classe dupliquée dans `kadi/market/data_ingestion.py` vers `kadi._sources.wfp_client.WFPClient`.
- Exposer les fonctions et classes dans `kadi/_sources/__init__.py`.
- Mettre en place la rétrocompatibilité via `_DEPRECATED` et `__getattr__`.

### Fichiers modifiés

- `[x]` **4.1** `kadi/_sources/wfp_client.py` : renommer `WFPDataBridgesClient` en `WFPClient`, passer les méthodes internes en anglais et ajouter la table `_DEPRECATED`.
- `[x]` **4.2** `kadi/_sources/exchange_client.py` : simplifier les méthodes internes en anglais (`rates()`, `convert()`, `refresh()`) et ajouter la table `_DEPRECATED`.
- `[x]` **4.3** `kadi/_sources/chirps.py` : traduire et simplifier les fonctions internes (`_is_available`, `_cache_path`, `_build_url`, `_download_and_clip`, `_extract_point`) et ajouter `_DEPRECATED`.
- `[x]` **4.4** `kadi/_sources/soilgrids.py` : traduire et simplifier les fonctions internes (`_wrb_to_soil`, `_load_cache`, `_save_cache`, `_lookup_cache`, `_call_api`) et ajouter `_DEPRECATED`.
- `[x]` **4.5** `kadi/market/data_ingestion.py` : nettoyer la classe dupliquée et mettre en place la rétrocompatibilité vers `kadi._sources.wfp_client.WFPClient`.
- `[x]` **4.6** `kadi/_sources/__init__.py` : exporter `WFPClient`, `ExchangeRateClient`, `fetch_historical_precipitation`, `fetch_soil_type` et ajouter la table `_DEPRECATED`.
- `[x]` **4.7** Lancer les tests et vérifier le maintien de la rétrocompatibilité.

---

## Phase 5 — Module weather (`kadi/weather/`) (8/8 Terminé)

### Règles
- `WeatherSession` -> `Weather` (façade principale, exposée à `kadi.Weather`).
- `WeatherData` -> `WeatherLoader`.
- `RiskIndicators` -> `Risk`.
- `Location` : conserver le nom, abréger `latitude`/`longitude` en `lat`/`lon`.
- Renommer les méthodes et attributs selon les propositions.
- Toutes les méthodes internes encore en français passent en anglais.

### Fichiers modifié

- `[x]` **5.1** `kadi/weather/location.py`
- `[x]` **5.2** `kadi/weather/data.py`
- `[x]` **5.3** `kadi/weather/hydrology.py`
- `[x]` **5.4** `kadi/weather/phenology.py`
- `[x]` **5.5** `kadi/weather/risk.py`
- `[x]` **5.6** `kadi/weather/session.py` : renommer la classe en `Weather`.
- `[x]` **5.7** `kadi/weather/__init__.py` : exporter `Weather`.
  ```python
  from .session import Weather
  from .location import Location
  ```
- `[x]` **5.8** Lancer les tests.

---

## Phase 6 — Module market (`kadi/market/`) (7/7 Terminé)

### Règles
- `MarketPricing` -> `Pricing`, `MarketForecasting` -> `Forecasting`,
  `MarketLogistics` -> `Logistics`, `MarketBacktester` -> `Backtester`,
  `DecisionSupport` -> `Advisor`.
- Façade `Market` : conserver le nom, simplifier les méthodes et attributs.
- Renommer toutes les méthodes et attributs en français.
- Exposer dans `kadi/market/__init__.py`.

### Fichiers à modifier

- `[x]` **6.1** `kadi/market/pricing.py`
- `[x]` **6.2** `kadi/market/forecasting.py`
- `[x]` **6.3** `kadi/market/logistics.py`
- `[x]` **6.4** `kadi/market/decision_support.py`
- `[x]` **6.5** `kadi/market/backtesting.py`
- `[x]` **6.6** `kadi/market/__init__.py` : exposer toutes les classes internes. Pour les anciennes classes, utiliser la rétrocompatibilité, avec un tableau _DEPRECATED et la méthode __getattr__.
  ```python
  from .pricing import Pricing
  from .forecasting import Forecasting
  from .logistics import Logistics
  from .decision_support import Advisor
  from .backtesting import Backtester
  ```
- `[x]` **6.7** Lancer les tests.

---

## Phase 7 — Point d'entrée racine (`kadi/__init__.py`) (2/2 Terminé)

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

- `[x]` **7.1** `kadi/__init__.py` : ajouter les exports de premier niveau.
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
- `[x]` **7.2** Lancer les tests complets.

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
Phase 7 (__init__ racine & io) <-- dépend de toutes les phases
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
