# KadiPy

**KadiPy** est une bibliothèque Python conçue pour les agronomes, chercheurs et
développeurs travaillant sur l'agriculture béninoise. Son objectif est de simplifier
le traitement et l'analyse des données agricoles, qu'il s'agisse de données météo,
de prix de marché ou de récoltes.

> Pensez-y comme au "Pandas" de l'agriculture africaine.

---

## Ce que fait KadiPy

KadiPy regroupe quatre modules complémentaires qui couvrent l'ensemble du cycle
d'analyse des données agricoles.

### `kadi.io` - Ingestion et exportation unifiées

Fonctions d'entrée et sortie universelles (`read_csv`, `read_excel`, `read_json`, `read_netcdf`, `read_api`, `write`, `info`, `ping`).

### `kadi.market` - Économie agricole

Analyse des marchés agricoles béninois avec des données de prix réels (WFP) ou
simulées. Calcule les opportunités d'arbitrage via `Advisor`, les coûts logistiques via `Logistics`, les
prévisions de prix via `Forecasting` et l'analyse des prix via `Pricing`.

[Voir la documentation de kadi.market](market/index.md)

### `kadi.weather` - Météorologie agronomique

Interface unifiée via la façade `Weather` pour les données météo historiques et prévisionnelles. Calcule
les indices de sécheresse (`Risk`), les probabilités de pluie, les degrés-jours de croissance (`Phenology`)
et le bilan hydrique des sols (`Hydrology`).

[Voir la documentation de kadi.weather](weather/index.md)

### `kadi.kidas` - Traitement et standardisation des données

Pipeline complet d'ingestion, nettoyage (`Cleaner`), validation (`Validator`), normalisation (`Normalizer`),
gestion de cache (`Cache`) et chaîne de traitement (`Pipeline`).

[Voir la documentation de kadi.kidas](kidas/index.md)

---

## Installation

```bash
git clone https://github.com/delsDin/kadipy.git
cd kadipy

# Création de l'environnement virtuel
python -m venv .kadi_venv
source .kadi_venv/bin/activate

# Installation des dépendances via pyproject.toml
pip install -e ".[dev]"

# Optionnel : support des anciens fichiers Excel (.xls)
pip install -e ".[dev,xls]"
```

### Configuration de l'environnement

Créez un fichier `.env` à la racine du projet pour activer les sources de données réelles :

```env
# Clé API WFP DataBridges (facultatif - des données simulées sont utilisées sans elle)
WFP_API_Token=votre_cle_ici

# Prix du carburant manuel en XOF/litre (facultatif)
BENIN_FUEL_PRICE=680
```

---

## Démarrage rapide

### Lecture et inspection unifiées

```python
import kadi as kd

# Lecture automatique selon le format
df = kd.read_csv("recolte_2024.csv")
kd.info(df)
```

### Analyse de marché

```python
import kadi as kd

# Initialisation pour Parakou
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou")

# Résumé des prix du maïs sur 90 jours
resume = marche.price_crop("maize", days_back=90)
print(f"Prix médian : {resume['prix_median']} XOF/kg")
print(f"Source : {'réelle' if not resume['is_simulated'] else 'simulée'}")
```

### Analyse météo

```python
import kadi as kd

weather = kd.Weather(lat=9.3333, lon=2.6333, name="Parakou")

# Probabilité de pluie demain
risque = weather.rain_probability(days_ahead=1)
print(risque["recommendation"])

# Indice de sécheresse SPI sur 3 mois
secheresse = weather.drought_index(method="spi", window_months=3)
print(f"Sévérité : {secheresse['drought_severity']}")
```

### Intégration météo + marché

```python
import kadi as kd

# La session météo enrichit automatiquement les calculs logistiques
weather = kd.Weather(lat=9.30, lon=2.08, name="Parakou")
marche = kd.Market(lat=9.30, lon=2.08, location="Parakou", weather=weather)

# Le coût logistique tient compte de la pluie prévue
cout = marche.logistics.calculate_transfer_cost(
    "Parakou", "Cotonou", crop="tomato"
)
print(f"Coût de transfert : {cout['total_cost_cfa']} XOF")
print(f"Probabilité de pluie utilisée : {cout['prob_pluie'] * 100:.0f}%")

# Risque climatique global
risque_global = marche.assess_climate_risk(days_ahead=7)
print(risque_global["recommendation"])
```

### Traitement de données avec Pipeline

```python
import kadi.kidas as kidas

# Ingestion et nettoyage direct
cleaner = kidas.Cleaner()
df_clean = cleaner.drop_dupes(df)
```

---

## Lancer les tests

```bash
# Exécution simple des tests
pytest tests/ -q

# Exécution avec rapport de couverture de code
pytest tests/ --cov=kadi --cov-report=term-missing
```

Les tests couvrent l'ensemble des modules applicatifs (`io`, `market`, `weather`, `kidas`), y compris les connecteurs distants (`tests/weather/test_chirps.py` couvrant le code CHIRPS sans dépendance réseau) ainsi que les composants d'infrastructure internes `kadi.cache` (`tests/test_cache.py`) et `kadi.config` (`tests/test_config.py`). Aucune clé API n'est nécessaire pour les exécuter. La CI GitHub Actions contrôle automatiquement que la couverture globale du code reste supérieure à **70 %**.

---

## Structure du projet

```
kadipy/
├── kadi/
│   ├── io/              # Module d'entrées et sorties unifiées
│   ├── market/          # Module économie agricole
│   ├── weather/         # Module météorologie agronomique
│   ├── kidas/           # Module traitement et pipeline de données
│   ├── cache.py         # Cache SQLite partagé (testé via tests/test_cache.py)
│   ├── config.py        # Configuration centralisée (MODELS_DIR conservé pour v2.x ML)
│   └── exceptions.py    # Exceptions personnalisées
├── tests/               # Suite de tests (pytest)
├── docs/                # Cette documentation
├── config/              # Fichiers de configuration (prix carburant...)
└── pyproject.toml       # Source unique de vérité des dépendances
```

---

## Zone géographique (V1.0.0)

KadiPy V1.0.0 est conçu **exclusivement pour le Bénin**. La validation des
coordonnées GPS, les algorithmes phénologiques, les facteurs logistiques et les
données de prix sont calibrés pour le contexte béninois.

Le support d'autres pays d'Afrique de l'Ouest est prévu dans les versions futures.
