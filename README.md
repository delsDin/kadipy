<div align="center" style="padding-bottom: 40px">
  <img src="img/kadipy-long.png" alt="KadiPy" width="100%" height="300px">
  <br>
  <p><strong>Traitement, analyse et modélisation des données agricoles et économiques</strong></p>
</div>

# KadiPy : le "pandas" de l'agriculture africaine

**KadiPy** est une bibliothèque Python open source conçue pour les agronomes,
chercheurs et développeurs travaillant sur l'agriculture au Bénin et en Afrique
de l'Ouest. Elle offre une interface unifiée pour ingérer, nettoyer, analyser
et modéliser des données météorologiques, des prix de marchés agricoles, des
coûts logistiques et des séries de récoltes, avec un fonctionnement conçu en
priorité pour le mode hors ligne (offline-first).

---

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

---

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

---

## Démarrage rapide

### Lecture et inspection des données

```python
import kadi as kd

# Lecture automatique selon le format
df = kd.read_csv("recolte_2024.csv")
kd.info("recolte_2024.csv")     # Métadonnées : lignes, colonnes, types
kd.ping("recolte_2024.csv")     # Vérifie l'accessibilité du fichier
```

### Nettoyage et préparation

```python
import kadi as kd

df = kd.read_csv("enquete_prix_2024.csv")

cleaner = kd.Cleaner(df)
df_propre = (
    cleaner
    .fix_encoding()
    .drop_dupes()
    .fill_missing(strategy="median", columns=["prix_xof_kg", "quantite_kg"])
    .drop_outliers(method="iqr", columns=["prix_xof_kg"])
    .normalize_text(columns=["culture", "marche"])
)
```

### Analyse météorologique

```python
import kadi as kd

weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")

# Probabilité de pluie demain
prob = weather.rain_probability(days_ahead=1)
print(prob["recommendation"])

# Indice de sécheresse SPI sur 3 mois
secheresse = weather.drought_index(method="spi", window_months=3)
print(f"Sévérité : {secheresse['drought_severity']}")

# Démarrage de la saison des pluies
onset = weather.onset()
print(f"Début estimé : {onset['onset_date']}")
```

### Analyse de marché

```python
import kadi as kd

marche = kd.Market(lat=9.30, lon=2.08, location="Parakou")

# Prix du maïs sur 90 jours
resume = marche.price_crop("maize", days_back=90)
print(f"Prix médian : {resume['prix_median']} XOF/kg")
print(f"Source : {'réelle' if not resume['is_simulated'] else 'simulée'}")
```

### Intégration météo + marché

```python
import kadi as kd

weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)

# Décision d'arbitrage spatial
decision = marche.advisor.arbitrage(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0,
)
print(f"Recommandation : {decision['recommandation']}")
print(f"Gain net : {decision['gain_net_percent']:.1f}%")
print(f"Confiance : {decision['confidence_score']:.0%}")

# Risque climatique global (intègre les prévisions météo)
risque = marche.climate_risk(days_ahead=7)
print(risque["recommendation"])
```

### Pipeline complet de traitement

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .load("donnees_marche.xlsx")
    .clean("all")
    .validate({"culture": "str", "rendement_kg": "float"})
    .normalize({"crops": "culture"})
    .run(cache=True)
)

print(f"Score de qualité : {rapport.get('quality_score')}")
print(f"Lignes en sortie : {rapport['nb_rows_out']}")
```

---

## Vue d'ensemble des modules

| Module | Façade / Fonctions | Description |
|--------|---------------------|-------------|
| `kadi.io` | `read_csv`, `read_excel`, `read_json`, `read_netcdf`, `read_api`, `write`, `info`, `ping` | Entrées et sorties avec détection automatique du format |
| `kadi.weather` | `Weather`, `Location` | Météo, prévisions, historique et indicateurs agronomiques |
| `kadi.market` | `Market`, `Pricing`, `Forecasting`, `Logistics`, `Advisor` | Analyse économique, prix, logistique et aide à la décision |
| `kadi.kidas` | `Cleaner`, `Validator`, `Normalizer`, `Pipeline`, `Cache` | Traitement, contrôle qualité et persistance SQLite |

---

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

---

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

---

## Rétrocompatibilité

Les anciens noms de classes issus des versions antérieures à v1.2.0 sont
conservés et émettent un `DeprecationWarning` pour guider la migration :

| Ancien nom (avant v1.2.0) | Nouveau nom |
|---------------------------|-------------|
| `WeatherSession` | `Weather` |
| `DataCleaner` | `Cleaner` |
| `DataValidator` | `Validator` |
| `DataNormalizer` | `Normalizer` |
| `DataCache` | `Cache` |
| `DataPipeline` | `Pipeline` |
| `CSVDataSource` | `CSVSource` |

Ces anciens noms seront supprimés dans KadiPy v2.0.

---

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
