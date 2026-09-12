# KadiPy

**KadiPy** est une bibliothèque Python conçue pour les agronomes, chercheurs
et développeurs travaillant sur l'agriculture au Bénin et en Afrique de l'Ouest.
Son objectif est de simplifier le traitement et l'analyse des données agricoles,
qu'il s'agisse de données météo, de prix de marché ou de récoltes.

Pensez-y comme au "pandas" de l'agriculture africaine.

---

## Ce que fait KadiPy

KadiPy regroupe quatre modules complémentaires qui couvrent l'ensemble du cycle
d'analyse des données agricoles.

### `kadi.io` - Entrées et sorties

Fonctions de lecture et d'écriture universelles avec détection automatique du
format : `read_csv`, `read_excel`, `read_json`, `read_netcdf`, `read_api`,
`write_csv`, `write_excel`, ainsi que les fonctions génériques `write`, `info`
et `ping`.

[Voir la documentation de kadi.io](io.md)

### `kadi.market` - Économie agricole

Analyse des marchés agricoles béninois avec des données de prix réels (WFP/HAPI)
ou simulées. Calcule les opportunités d'arbitrage via `Advisor`, les coûts
logistiques via `Logistics`, les prévisions de prix via `Forecasting` et
l'analyse des prix via `Pricing`.

[Voir la documentation de kadi.market](market/index.md)

### `kadi.weather` - Météorologie agronomique

Interface unifiée via la façade `Weather` pour les données météo historiques et
prévisionnelles (CHIRPS + Open-Meteo). Calcule les indices de sécheresse
(`Risk`), les probabilités de pluie, les degrés-jours de croissance (`Phenology`)
et le bilan hydrique des sols (`Hydrology`).

[Voir la documentation de kadi.weather](weather/index.md)

### `kadi.kidas` - Traitement et standardisation des données

Pipeline complet d'ingestion, nettoyage (`Cleaner`), validation (`Validator`),
normalisation (`Normalizer`), gestion de cache (`Cache`) et chaîne de traitement
(`Pipeline`).

[Voir la documentation de kadi.kidas](kidas/index.md)

---

## Installation

```bash
git clone https://github.com/delsDin/kadipy.git
cd kadipy

python -m venv .kadi_venv
source .kadi_venv/bin/activate

pip install -e ".[dev]"

# Optionnel : support des anciens fichiers Excel (.xls)
pip install -e ".[dev,xls]"
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

df = kd.read_csv("recolte_2024.csv")
kd.info("recolte_2024.csv")
```

### Nettoyage des données

```python
import kadi as kd

df = kd.read_csv("enquete_prix_2024.csv")
cleaner = kd.Cleaner(df)

df_propre = (
    cleaner
    .fix_encoding()
    .drop_dupes()
    .fill_missing(strategy="median", columns=["prix_xof_kg"])
    .drop_outliers(method="iqr", columns=["prix_xof_kg"])
)
```

### Analyse météo

```python
import kadi as kd

weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")

risque = weather.rain_probability(days_ahead=1)
print(risque["recommendation"])

secheresse = weather.drought_index(method="spi", window_months=3)
print(f"Sévérité : {secheresse['drought_severity']}")
```

### Analyse de marché

```python
import kadi as kd

marche = kd.Market(lat=9.30, lon=2.08, location="Parakou")

resume = marche.price_crop("maize", days_back=90)
print(f"Prix médian : {resume['prix_median']} XOF/kg")
```

### Intégration météo + marché

```python
import kadi as kd

weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)

decision = marche.advisor.arbitrage_decision(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0,
)
print(f"Recommandation : {decision['recommandation']}")
print(f"Gain net : {decision['gain_net_percent']:.1f}%")
```

---

## Lancer les tests

```bash
pytest tests/ -q

# Avec rapport de couverture de code
pytest tests/ --cov=kadi --cov-report=term-missing
```

Les tests couvrent l'ensemble des modules (`io`, `market`, `weather`, `kidas`),
y compris les connecteurs distants sans dépendance réseau, et les composants
d'infrastructure (`kadi.cache`, `kadi.config`). Aucune clé API n'est nécessaire
pour les exécuter. La CI GitHub Actions contrôle que la couverture globale reste
supérieure à **70 %**.

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
├── docs/                # Cette documentation
├── examples/            # Notebooks d'exemples Jupyter
├── config/              # Fichiers de configuration
└── pyproject.toml       # Source unique de vérité des dépendances
```

---

## Zone géographique (v1.x)

KadiPy v1.x, v2.x est conçu **exclusivement pour le Bénin**. La validation des
coordonnées GPS, les algorithmes phénologiques, les facteurs logistiques et les
données de prix sont calibrés pour le contexte béninois.

Le support d'autres pays d'Afrique de l'Ouest est prévu dans les versions futures.
