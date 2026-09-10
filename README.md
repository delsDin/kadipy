<p align="right">
  <strong>Français</strong> | <a href="docs/README.EN.md">English</a>
</p>

<div align="center" style="padding-bottom: 40px">
  <img src="img/kadipy-long.png" alt="KadiPy" width="100%" height="400px">
  <br>
  <p><strong>Traitement, analyse et modélisation des données agricoles et économiques</strong></p>
</div>

----

# KadiPy : le "pandas" de l'agriculture africaine

**KadiPy** est une bibliothèque Python open source conçue pour les agronomes,
chercheurs et développeurs travaillant sur l'agriculture au Bénin et en Afrique
de l'Ouest. Elle offre une interface unifiée pour ingérer, nettoyer, analyser
et modéliser des données météorologiques, des prix de marchés agricoles, des
coûts logistiques et des séries de récoltes, avec un fonctionnement conçu en
priorité pour le mode hors ligne (offline-first).

<br/>

## Fonctionnalités principales

- **Ingestion et E/S unifiées (`kadi.io`)** : fonctions expressives `read_csv`,
  `read_excel`, `read_json`, `read_netcdf`, `read_api` avec détection automatique
  du format, et leurs équivalents en écriture (`write_csv`, `write_excel`, etc.).
  Les fonctions `write`, `info` et `ping` fonctionnent avec n'importe quel format.

- **Météorologie agronomique (`kadi.weather`)** : façade `Weather` pour les
  données météo historiques et prévisionnelles (CHIRPS + Open-Meteo), détection
  des saisons des pluies (Sivakumar, Walter-Anyadike), bilan hydrique des sols
  (FAO-56), évapotranspiration (ET0 Hargreaves-Samani) et indices de sécheresse
  (SPI, Markov, Hurst).

- **Économie agricole et marchés (`kadi.market`)** : façade `Market` pour le
  suivi des prix réels (WFP/HAPI HumData), prévisions de prix (`Forecasting`),
  calculs de coûts logistiques routiers (`Logistics`) et aide à la décision
  (`Advisor`) pour l'arbitrage spatial et le stockage stratégique.

- **Pipeline et standardisation (`kadi.kidas`)** : nettoyage des données brutes
  (`Cleaner`), validation de schémas (`Validator`), normalisation des noms de
  cultures et coordonnées GPS (`Normalizer`), persistance SQLite locale (`Cache`)
  et chaîne de traitement complète (`Pipeline`).


<br/>

## Installation

### Via PyPI

```bash
pip install kadipy
```

### Depuis les sources

```bash
git clone https://github.com/delsDin/kadipy.git
cd kadipy
pip install -e ".[dev]"
```

### Dépendances optionnelles

```bash
# Support des anciens fichiers Excel (.xls, antérieurs à 2003)
pip install "kadipy[xls]"

# Traitements géospatiaux (découpage de rasters CHIRPS)
pip install "kadipy[geospatial]"
```

### Configuration de l'environnement

Créez un fichier `.env` à la racine du projet pour activer les sources de données
réelles :

```env
# Clé API WFP DataBridges (facultatif : des données publiques HAPI HumData
# sont utilisées sans elle)
WFP_API_Token=votre_cle_ici

# Prix du carburant manuel en XOF/litre (facultatif)
BENIN_FUEL_PRICE=680
```

<br/>

## Vue d'ensemble des modules

| Module | Façade / Composants | Description |
|--------|---------------------|-------------|
| `kadi.io` | `read_csv`, `read_excel`, `read_json`, `read_netcdf`, `read_api`, `write`, `info`, `ping` | Entrées et sorties avec détection automatique du format |
| `kadi.weather` | `Weather`, `Location`, `Phenology`, `Hydrology`, `Risk` | Météo, prévisions, historique et indicateurs agronomiques |
| `kadi.market` | `Market`, `Pricing`, `Forecasting`, `Logistics`, `Advisor` | Analyse économique, prix, logistique et aide à la décision |
| `kadi.kidas` | `Cleaner`, `Validator`, `Normalizer`, `Pipeline`, `Cache` | Traitement, contrôle qualité et persistance SQLite |

<br/>

## Structure du projet

```
kadipy/
├── kadi/
│   ├── io/              # Entrées et sorties unifiées
│   ├── market/          # Économie agricole et marchés
│   ├── weather/         # Météorologie agronomique
│   ├── kidas/           # Pipeline de traitement et standardisation
│   ├── _sources/        # Clients externes (WFP, CHIRPS, SoilGrids)
│   ├── cache.py         # Cache SQLite partagé
│   ├── config.py        # Configuration centralisée
│   └── exceptions.py    # Exceptions personnalisées
├── tests/               # Suite de tests (pytest)
├── docs/                # Documentation MkDocs
├── examples/            # Notebooks d'exemples Jupyter
├── config/              # Fichiers de configuration
└── pyproject.toml       # Dépendances et métadonnées du package
```

<br/>

## Lancer les tests

```bash
# Exécution simple
pytest tests/ -q

# Avec rapport de couverture de code
pytest tests/ --cov=kadi --cov-report=term-missing
```

Les tests couvrent l'ensemble des modules (`io`, `market`, `weather`, `kidas`),
y compris les connecteurs distants sans dépendance réseau et les composants
d'infrastructure (`kadi.cache`, `kadi.config`). Aucune clé API n'est nécessaire
pour les exécuter. La CI GitHub Actions contrôle que la couverture globale reste
supérieure à **70 %**.

<br/>

## Rétrocompatibilité

Les anciens noms de classes issus des versions antérieures à v1.2.0 émettent un `DeprecationWarning` et seront supprimés dans KadiPy v2.0 :

| Ancien nom (avant v1.2.0) | Nouveau nom |
|---------------------------|-------------|
| `WeatherSession` | `Weather` |
| `DataCleaner` | `Cleaner` |
| `DataValidator` | `Validator` |
| `DataNormalizer` | `Normalizer` |
| `DataCache` | `Cache` |
| `DataPipeline` | `Pipeline` |
| `CSVDataSource` | `CSVSource` |

<br/>

## Zone géographique (v1.x)

KadiPy v1.x est conçu **exclusivement pour le Bénin**. La validation des
coordonnées GPS, les algorithmes phénologiques, les facteurs logistiques et les
données de prix sont calibrés pour le contexte béninois.

Le support d'autres pays d'Afrique de l'Ouest est prévu dans les versions futures.

---

## Documentation

La documentation complète (guides d'API, exemples) est disponible sur :
**https://delsDin.github.io/kadipy/**

---

## Licence et contribution

- **Licence** : MIT
- **Dépôt GitHub** : https://github.com/delsDin/kadipy
- **Compatibilité Python** : >= 3.9
- **Version courante** : 1.2.0
