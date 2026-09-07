<div align="center", style="padding-bottom: 40px">
  <img src="img/kadipy-long.png" alt="KadiPy" width="100%", height="300px">
  <br>
  <p><strong>Traitement, analyse et modélisation des données agricoles et économiques</strong></p>
</div>

# KadiPy : Le "pandas" de l'agriculture africaine

**KadiPy** est une bibliothèque Python open source fournissant des structures de données et des outils d'analyse performants, flexibles et faciles à utiliser pour l'agriculture au Bénin et en Afrique de l'Ouest.

Elle offre une interface unifiée pour ingérer, nettoyer, analyser et modéliser les données météorologiques, les prix des marchés agricoles, les coûts logistiques et les séries de récoltes, avec un fonctionnement conçu en priorité pour le mode hors ligne (offline-first).

---

## Fonctionnalités principales

- **Ingestion et E/S unifiées (`kadi.io`)** : Fonctions d'entrée et sortie simples et expressives (`kd.read_csv`, `kd.read_excel`, `kd.read_json`, `kd.read_netcdf`, `kd.read_api`, `kd.write`, `kd.info`) avec détection automatique des formats.
- **Météorologie agronomique (`kadi.weather`)** : Précipitations et températures hybrides (CHIRPS + Open-Meteo), détection des saisons des pluies (Sivakumar, Walter-Anyadike), bilan hydrique des sols (FAO-56), calcul de l'évapotranspiration (ET0 Hargreaves) et indices de sécheresse (SPI).
- **Économie agricole & marchés (`kadi.market`)** : Suivi des prix de marché (WFP), prévisions de prix, calculs de coûts logistiques routiers et module d'aide à la décision (`Advisor`) pour l'arbitrage spatial et le stockage stratégique.
- **Pipeline & Standardisation (`kadi.kidas`)** : Nettoyage (`Cleaner`), validation de schémas (`Validator`), normalisation des noms de cultures et coordonnées GPS (`Normalizer`), et persistance locale sous SQLite (`Cache`).

---

## Installation

### Via PyPI

```bash
pip install kadipy
```

### Installation depuis les sources

```bash
git clone https://github.com/delsDin/kadipy.git
cd kadipy
pip install -e ".[dev]"
```

### Dépendances

**Dépendances principales :**
- `pandas` (>= 1.5.0)
- `numpy` (>= 1.21.0)
- `scipy` (>= 1.7.0)
- `requests` (>= 2.25.0)
- `python-dotenv` (>= 0.19.0)

**Dépendances optionnelles :**
- `xarray` & `netcdf4` : pour le support des fichiers NetCDF
- `openpyxl` & `xlrd` : pour la lecture des fichiers Excel (.xlsx, .xls)

---

## Démarrage rapide

```python
import kadi as kd

# 1. Chargement et inspection universelle des données
df = kd.read_csv("donnees_agricoles.csv")
kd.info(df)

# 2. Nettoyage et préparation avec Kidas
cleaner = kd.Cleaner(df)
df_clean = (
    cleaner
    .drop_dupes()
    .fill_missing(strategy="median")
    .drop_outliers(method="iqr")
)

# 3. Analyse météorologique pour Parakou
weather = kd.Weather(lat=9.33, lon=2.63, name="Parakou")
previsions = weather.forecast(days=5)
onset_date = weather.onset()
print(f"Début estimé de la saison des pluies : {onset_date['onset_date']}")

# 4. Modélisation économique et opportunités d'arbitrage
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)
decision = marche.advisor.arbitrage(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0,
)

print(f"Recommandation : {decision['recommandation']}")
print(f"Gain net estimé : {decision['gain_net_percent']:.1f}%")
print(f"Score de confiance : {decision['confidence_score']:.0%}")
```

---

## Vue d'ensemble des modules

| Module | Façade / Fonctions | Description |
|--------|---------------------|-------------|
| `kadi.io` | `read_csv`, `read_excel`, `read_json`, `write`, `info`, `ping` | Entrées et sorties unifiées avec détection automatique |
| `kadi.weather` | `Weather` | Interface météo, prévisions, historique et indicateurs agronomiques |
| `kadi.market` | `Market`, `Advisor` | Analyse économique, suivi des prix, logistique et aide à la décision |
| `kadi.kidas` | `Cleaner`, `Validator`, `Normalizer`, `Pipeline`, `Cache` | Traitement, contrôle de qualité et persistance SQLite |

---

## Documentation

La documentation officielle complète (tutoriels, guides d'API, exemples) est disponible sur :
**https://delsDin.github.io/kadipy/**

---

## Licence & Contribution

- **Licence** : MIT
- **Dépôt GitHub** : https://github.com/delsDin/kadipy
- **Compatibilité Python** : >= 3.9
