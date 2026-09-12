# Rapport d'analyse technique — KadiPy v1.0.0

**Date de l'analyse :** 25 juillet 2026

**Branche analysée :** `main`

**Périmètre :** code source complet du package (`kadi/`), tests (`tests/`),
configuration (`pyproject.toml`, `pytest.ini`, `config/`), documentation.

---

## 1. Présentation du projet

KadiPy est une bibliothèque Python conçue pour les agronomes et développeurs travaillant sur les données agricoles au Bénin et en Afrique de l'Ouest. Son positionnement est celui d'un « pandas de l'agriculture africaine », avec une approche offline-first pour les contextes de connectivité limitée.
Le package est structuré en trois modules principaux :
- **`kadi.weather`** : données météo, phénologie, hydrologie, indicateurs de risque
- **`kadi.market`** : prix des cultures, prévisions, logistique, aide à la décision
- **`kadi.kidas`** : pipeline de traitement des données agricoles locales (CSV, Excel, etc.)
L'infrastructure commune est assurée par `kadi.cache` (SQLite), `kadi.config` et `kadi.exceptions`.

---

## 2. Points forts du projet

Avant de présenter les problèmes, il est juste de reconnaître la qualité générale du travail accompli.

**Architecture cohérente.** Les trois modules suivent le même patron : une façade de haut niveau (`WeatherSession`, `Market`, `DataPipeline`) qui orchestre des sous-classes spécialisées. Cela facilite la navigation et la maintenance.

**Gestion des pannes réseau.** La logique offline-first est bien implémentée.
Chaque module dispose d'un mécanisme de repli en cascade : cache SQLite, puis données simulées avec `is_simulated=True`. Le flag est propagé à travers toute la chaîne d'appels, ce qui est une bonne pratique.

**Documentation interne.** Les docstrings sont présents sur la quasi-totalité des méthodes publiques et respectent une structure cohérente (Args, Returns, Raises). Les commentaires inline expliquent les choix techniques non évidents.

**Validation des entrées.** Le module `market` valide les coordonnées GPS et les types dès le constructeur. Le module `kidas` valide les types dans `DataCleaner`.

**Exceptions personnalisées.** La hiérarchie d'exceptions est bien pensée (`KadiException` vers `DataSourceError`, `CacheError`, `KidasReadError`, etc.). Elle permet à l'utilisateur d'attraper des erreurs de manière ciblée.

---

## 3. Analyse par module

### 3.1 Module `kadi.weather`

**Ce qui fonctionne bien :**

- L'API fluide de `WeatherSession` est agréable à utiliser.
- Le calcul de l'exposant de Hurst (R/S multi-échelle) est une implémentation sérieuse, bien commentée, avec une régression log-log correctement mise en oeuvre.
- `_normalize_data()` gère bien les valeurs aberrantes de température et l'interpolation sur les lacunes courtes.
- La combinaison Markov + API dans `rain_probability()` est une approche solide pour les zones à faible couverture réseau.

**Problèmes identifiés :**

*Problème 1 : La source CHIRPS est désactivée sans mention dans la documentation.*

Dans `session.py`, la source CHIRPS est commentée avec la mention « désactivé pour V1, réactivation prévue en V2 ». Mais le fichier `kadi/_sources/chirps.py` existe et n'est jamais importé. Le README annonce pourtant « Prévisions et historiques via Open-Meteo et CHIRPS ». C'est une inexactitude qui peut tromper les utilisateurs.

*Problème 2 : Alias `temperature_avg` / `temperature_mean` fragile.*

Dans `data.py`, les colonnes `temperature_avg` (issue du cache) et `temperature_mean` (issue de l'API) sont gérées par des alias conditionnels à plusieurs endroits. Cette duplication est une source d'erreurs futures si l'on ajoute une nouvelle source de données.

*Problème 3 : SPI calculé via un Z-score, pas via une loi Gamma.*

Dans `risk.py` ligne 88, un commentaire admet explicitement que le SPI est calculé par approximation (Z-score) plutôt que par la méthode standard (ajustement d'une loi Gamma via `scipy.stats.gamma.fit`). Pour un outil destiné à des agronomes, cette approximation peut produire des valeurs incorrectes, surtout en période sèche ou dans les régions où la distribution des pluies est fortement asymétrique.

---

### 3.2 Module `kadi.market`

**Ce qui fonctionne bien :**

- Le pipeline `Market.price_crop()` est complet : récupération, normalisation, détection d'anomalies, interpolation, statistiques.
- La propagation du flag `is_simulated` à travers toute la chaîne est exemplaire.
- Le module `backtesting.py` est bien conçu : fenêtres glissantes, MAE, RMSE, MAPE, précision directionnelle. La séparation entre `run()` et `summary_report()` est une bonne décision d'API.
- L'intégration météo (Phase 4) pour ajuster `gamma_route` en fonction de la pluie prévue est une idée pertinente, bien exécutée.

**Problèmes identifiés :**

*Problème 4 : Bornes géographiques non centralisées dans `market/__init__.py`.*

Les constantes `_LAT_MIN = 6.0`, `_LAT_MAX = 12.5`, `_LON_MIN = 0.5`, `_LON_MAX = 3.9` sont définies en dur dans `market/__init__.py` lignes 22 à 25, au lieu de lire depuis `CONFIG["weather"]["gps_validation_bbox"]`. Cela duplique la configuration et risque de créer des incohérences si les bornes sont mises à jour dans `config.py`.

*Problème 5 : `get_market_functionality_index()` retourne une valeur codée en dur.*

Dans `data_ingestion.py` ligne 615 environ, la méthode retourne toujours `7.9` sans aucun calcul réel. Cette méthode est exposée publiquement, mais n'a aucune utilité concrète pour l'utilisateur en l'état. Il faut soit la supprimer, soit la déclarer explicitement comme non implémentée avec une `NotImplementedError`.

*Problème 6 : `storage_vs_sell_now()` force `is_simulated=True` même avec données réelles.*

Dans `decision_support.py`, ligne 324, le code force `est_simule = True` avec le commentaire « Le module forecasting V1 reste un stub », écrasant le flag réel retourné par `predict_price()`. Cela signifie que même avec un historique WFP réel, la recommandation de stockage est toujours marquée comme simulée, ce qui est trompeur pour l'utilisateur.

*Problème 7 : Valeur de repli `revenu_attendu_cfa` codée en dur dans `_portfolio_heuristique()`.*

Dans `decision_support.py` ligne 582, le revenu de repli est `1_500_000.0` XOF sans aucun calcul sous-jacent. Cette valeur sans contexte peut induire en erreur l'utilisateur qui lirait ce champ sans consulter le flag `methode: 'heuristique'`.

---

### 3.3 Module `kadi.kidas`

**Ce qui fonctionne bien :**

- L'auto-détection du type de source (CSV, Excel, JSON, NetCDF, API) par extension est solide et extensible.

- `DataCleaner` implémente toutes les stratégies utiles : IQR, Z-score, MAD.

- Le rapport de nettoyage est structuré et journalise chaque opération.

- Le pipeline fluide (`source().clean().validate().normalize()`) est agréable à utiliser.

**Problème connu et documenté :**

*Problème 8 : Incohérence entre `execute()` et la documentation (bug.md)(déjà corrigé).*

C'est le bug déjà consigné dans `bug.md`. La documentation indique que `execute()` retourne un rapport avec les clés `steps_summary`, `quality_score`, `warnings`, `nb_rows_in`, `nb_rows_out`. Le code retourne en réalité un dictionnaire avec les clés `source`, `etapes_appliquees`, `nettoyage`, `validation`, `normalisation`, `cache_utilise`, `lignes_finales`. Le champ `quality_score` n'est présent que si une étape de validation est incluse dans le pipeline.
Ce bug est bloquant pour tout utilisateur qui s'appuie sur la documentation.

**Autres problèmes :**

*Problème 9 : `nb_dates_corrigees` calculé incorrectement dans `fix_dates()`.*

Dans `cleaner.py` lignes 362 à 363 :

```python
nb_corrigees = int(nb_avant - (nb_avant - nb_apres))  # Toujours egal a nb_apres
nb_dates_corrigees += nb_avant                         # On accumule nb_avant, pas nb_corrigees
```

La variable `nb_corrigees` est calculée mais jamais utilisée. Le rapport accumule `nb_avant` au lieu du nombre réel de dates converties. C'est un bug silencieux : le rapport de nettoyage affiche un chiffre gonflé.

*Problème 10 : Clé de cache non sécurisée dans `execute()`.*

Dans `pipeline.py`, la clé de cache est construite à partir du chemin brut du fichier source. Si le chemin contient des caractères spéciaux, cela peut provoquer des collisions de clés ou des erreurs d'encodage. Un hachage SHA256 du chemin serait plus robuste.

---

### 3.4 Infrastructure commune (`cache.py`, `config.py`, `exceptions.py`)

**Problème 11 : `MODELS_DIR` pointe vers un dossier inexistant.**

Dans `config.py` ligne 33 environ :

```python
MODELS_DIR = Path(__file__).parent / "_ml" / "models"
```

Le répertoire `kadi/_ml/` n'existe pas dans le dépôt. `MODELS_DIR` n'est référencé nulle part dans le code de production. C'est une configuration morte qui laisse entendre qu'un module ML était prévu mais jamais livré.

**Problème 12 : `EXCHANGE_RATES` statiques sans mise à jour automatique.**

Dans `config.py`, le commentaire indique « Mise à jour quotidienne prévue » mais aucun mécanisme n'est implémenté. Les taux XOF/USD et XOF/EUR utilisés dans `pricing.py` sont donc figés à leur valeur d'initialisation.

**Problème 13 : `requirements.txt` désynchronisé avec `pyproject.toml`.**

Le fichier `requirements.txt` déclare `xlrd<2.0` et `dask>=2023.1`, qui sontabsents de `pyproject.toml`. Or `pyproject.toml` est la source de vérité pour`pip install kadipy`. Un utilisateur installant le package via PyPI n'aura ni la lecture des fichiers `.xls` anciens, ni le support Dask. Ce fichier est probablement un résidu de développement créant une confusion sur les dépendances réelles.

---

### 3.5 Tests

La couverture est globalement satisfaisante pour un projet V1 :

- `tests/test_market/` : 3 fichiers (composants, intégration, backtesting)
- `tests/test_kidas/` : 4 fichiers (sources CSV, traitement, pipeline)
- `tests/weather/` : 7 fichiers (par composant)

**Manques identifiés :**

*Problème 14 : Absence de tests directs pour `kadi.cache`.*

Les fonctions `get_connection()` et `init_db()` de `kadi/cache.py` ne sont pas testées directement. Elles sont le socle du mode offline-first et méritent des tests unitaires avec une base de données temporaire (`tmp_path`).

*Problème 15 : Pas de test pour `kadi.config`.*

Aucun test ne vérifie que la configuration se charge correctement ou que les variables d'environnement (ex: `OPENMETEO_API_URL`) surchargent bien les valeurs par défaut.

*Problème 16 : Absence de mesure de couverture dans la CI.*

Il n'y a pas de rapport de couverture (`pytest-cov`) dans le workflow GitHub Actions. Il est impossible de savoir quelle proportion du code est actuellement couverte par les tests ou de détecter une régression de couverture.

---

## 4. Tableau récapitulatif

| # | Module | Sévérité | Description courte |
|---|--------|----------|--------------------|
| 1 | `weather` | Moyenne | CHIRPS annoncé dans le README mais désactivé sans mention |
| 2 | `weather` | Faible | Alias `temperature_avg/mean` dupliqué dans plusieurs fichiers |
| 3 | `weather` | Haute | SPI approximé par Z-score plutôt que par loi Gamma |
| 4 | `market` | Haute | Bornes GPS dupliquées en dur au lieu de lire `CONFIG` |
| 5 | `market` | Moyenne | `get_market_functionality_index()` retourne toujours 7.9 |
| 6 | `market` | Haute | `storage_vs_sell_now()` force `is_simulated=True` sur données réelles |
| 7 | `market` | Faible | Valeur magique `1_500_000` codée en dur dans le fallback heuristique |
| 8 | `kidas` | Critique | Structure du rapport de `execute()` ne correspond pas à la documentation |
| 9 | `kidas` | Haute | `nb_dates_corrigees` calculé incorrectement dans `fix_dates()` |
| 10 | `kidas` | Faible | Clé de cache non hachée, risque de collision avec chemins spéciaux |
| 11 | `config` | Faible | `MODELS_DIR` pointe vers `kadi/_ml/` qui n'existe pas |
| 12 | `config` | Moyenne | `EXCHANGE_RATES` statiques, mise à jour prévue non implémentée |
| 13 | `config` | Haute | `requirements.txt` désynchronisé avec `pyproject.toml` |
| 14 | `tests` | Moyenne | `kadi.cache` non testé directement |
| 15 | `tests` | Faible | `kadi.config` non testé |
| 16 | `CI` | Moyenne | Pas de rapport de couverture pytest-cov dans la CI |

---

## 5. Améliorations urgentes pour la version 1.1.0

Les corrections sont classées par ordre de priorité décroissante.

---

### Priorité 1 — Corriger le bug du rapport de pipeline (Problème 8)

C'est le seul bug critique qui peut bloquer des utilisateurs directement. La documentation et le code produisent des structures différentes pour le rapport de `execute()`. Il faut choisir une structure définitive et aligner les deux.

**Action recommandée :** adopter la structure documentée (plus lisible) et modifier le code de `execute()` dans `pipeline.py` pour la produire :

```python
rapport = {
    "nb_rows_in": lignes_avant,
    "nb_rows_out": len(self._df),
    "steps_summary": [e["nom"] for e in self._etapes],
    "quality_score": self._rapports.get("quality_score"),
    "warnings": [],
    "cache_utilise": False,
    "details": {
        "source": self._rapports["source"],
        "nettoyage": self._rapports["nettoyage"],
        "validation": self._rapports["validation"],
        "normalisation": self._rapports["normalisation"],
    }
}
```

---

### Priorité 2 — Corriger `storage_vs_sell_now()` (Problème 6)

Dans `decision_support.py`, supprimer la ligne qui force `est_simule = True` apres l'appel a `predict_price()`. Le flag doit etre propage depuis le resultat :

```python
# Avant (incorrect)
est_simule = True  # Le module forecasting V1 reste un stub
# Apres (correct)
est_simule = prevision.get("is_simulated", True)
```

---

### Priorité 3 — Reconcilier `requirements.txt` et `pyproject.toml` (Problème 13)

Supprimer `requirements.txt` ou le regenerer a partir de `pyproject.toml`. Si `xlrd` est necessaire pour les vieux fichiers `.xls` l'ajouter dans les dependances optionnelles de `pyproject.toml` :

```toml
[project.optional-dependencies]
xls = ["xlrd<2.0"]
```

---

### Priorité 4 — Corriger le SPI (Problème 3)

Remplacer l'approximation Z-score par un ajustement de loi Gamma dans `risk.py`. `scipy.stats` est deja une dependance du projet.

```python
from scipy.stats import gamma as gamma_dist
valid_data = rolling_sum[rolling_sum > 0]
shape, loc, scale = gamma_dist.fit(valid_data, floc=0)
prob_cumul = gamma_dist.cdf(current_val, shape, loc=loc, scale=scale)
# Conversion en score SPI via la loi normale inverse
from scipy.stats import norm
spi_val = norm.ppf(prob_cumul)
```

---

### Priorité 5 — Centraliser les bornes GPS du module `market` (Problème 4)

Dans `market/__init__.py`, remplacer les constantes en dur par une lecture depuis `CONFIG` :

```python
_bbox = CONFIG.get("weather", {}).get("gps_validation_bbox", {})
_LAT_MIN = _bbox.get("min_lat", 6.0)
_LAT_MAX = _bbox.get("max_lat", 12.5)
_LON_MIN = _bbox.get("min_lon", 0.5)
_LON_MAX = _bbox.get("max_lon", 3.9)
```

---

### Priorité 6 — Corriger `fix_dates()` dans `DataCleaner` (Problème 9)

```python
# Avant (incorrect)
nb_corrigees = int(nb_avant - (nb_avant - nb_apres))  # toujours = nb_apres
nb_dates_corrigees += nb_avant                         # mauvais compteur
# Apres (correct)
nb_corrigees = int(nb_apres)   # nombre de dates effectivement converties
nb_dates_corrigees += nb_corrigees
```

---

### Priorité 7 — Supprimer ou declarer `get_market_functionality_index()` (Problème 5)

Lever une `NotImplementedError` explicite jusqu'a ce qu'une vraie source de donnees soit integree :

```python
def get_market_functionality_index(self, market_id: str) -> float:
    raise NotImplementedError(
        "get_market_functionality_index() n'est pas encore implementee. "
        "Elle sera disponible apres integration de la source FEWSNET."
    )
```

---

### Priorité 8 — Ajouter `pytest-cov` a la CI (Problème 16)

Ajouter dans le workflow GitHub Actions :

```yaml
- name: Lancer les tests avec couverture
  run: |
    pytest tests/ --cov=kadi --cov-report=xml --cov-report=term-missing
```

Un seuil minimal peut etre fixe avec `--cov-fail-under=70` pour detecter
toute regression.

---

### Priorité 9 — Intégration transparente de l'API WFP DataBridges (Nouvelle fonctionnalité v1.1.0)

Dans la version 1.1.0, l'API WFP (World Food Programme DataBridges) sera directement intégrée pour le chargement des données de prix réelles. L'utilisateur n'aura pas besoin d'inscrire ou d'injecter une clé API personnelle (`WFP_API_Token`). Le client gérera automatiquement l'accès transparent aux endpoints publics ou l'utilisation d'un jeton par défaut embarqué.

---

## 6. Problemes de moindre urgence (V1.2.0 ou ulterieure)

Ces points ne bloquent pas le fonctionnement actuel.

- **Problème 2** : refactorer l'alias `temperature_avg/mean` en une seule colonne canonique avec une migration du cache SQLite si necessaire.

- **Problème 10** : securiser la cle de cache dans `execute()` avec `hashlib.sha256(path.encode()).hexdigest()[:16]`.

- **Problème 11** : supprimer `MODELS_DIR` de `config.py` ou creer le dossier `kadi/_ml/models/` et le documenter.

- **Problème 12** : mettre en place une mise a jour des taux de change via un fichier JSON heberge, similaire au mecanisme deja en place pour les prix du carburant dans `logistics.py`.

- **Problème 1** : mettre a jour le README pour retirer la mention de CHIRPS ou ajouter une note explicite « fonctionnalite en cours de developpement ».

- **Problème 7** : remplacer la valeur magique `1_500_000` dans `_portfolio_heuristique()` par un calcul base sur les prix et rendements de reference.

- **Problèmes 14 et 15** : ecrire des tests unitaires pour `kadi.cache` et `kadi.config` en utilisant des fixtures `tmp_path` et `monkeypatch`.

---

## 7. Conclusion

KadiPy v1.0.0 est un package sérieux et bien architecturé pour un premier release. Les trois modules fonctionnent ensemble de façon cohérente, la gestion du mode hors ligne est une vraie valeur ajoutée, et la qualité de la documentation interne est au-dessus de la moyenne des projets open source de cette taille.

Les corrections prioritaires pour la v1.1.0 se concentrent sur trois axes :

1. **Exactitude des données :** le bug du rapport de pipeline (Problème 8), le flag `is_simulated` incorrectement force (Problème 6), et le compteur de dates errone (Problème 9) induisent les utilisateurs en erreur sur la qualite des donnees qu'ils traitent.

2. **Accès direct aux données WFP :** intégration de l'API WFP sans nécessiter de clé utilisateur, permettant un chargement instantané des données de marché réelles.

3. **Coherence de la configuration :** la desynchronisation entre `requirements.txt` et `pyproject.toml` (Problème 13) peut creer des problemes d'installation chez les utilisateurs finaux.

La correction de l'exactitude scientifique du SPI (Problème 3) et la centralisation des bornes GPS (Problème 4) peuvent suivre sans urgence absolue, mais sont importantes pour la credibilite du package aupres des agronomes et chercheurs qui constituent le public cible.

