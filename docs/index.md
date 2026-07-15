# KadiPy

**KadiPy** est une bibliothèque Python conçue pour les agronomes, chercheurs et
développeurs travaillant sur l'agriculture béninoise. Son objectif est de simplifier
le traitement et l'analyse des données agricoles, qu'il s'agisse de données météo,
de prix de marché ou de récoltes.

> Pensez-y comme au "Pandas" de l'agriculture africaine.

---

## Ce que fait KadiPy

KadiPy regroupe trois modules complémentaires qui couvrent l'ensemble du cycle
d'analyse des données agricoles.

### `kadi.market` - Économie agricole

Analyse des marchés agricoles béninois avec des données de prix réels (WFP) ou
simulées. Calcule les opportunités d'arbitrage, les coûts logistiques, les
prévisions de prix et l'optimisation de portefeuille de cultures.

[Voir la documentation de kadi.market](market/index.md)

### `kadi.weather` - Météorologie agronomique

Interface unifiée pour les données météo historiques et prévisionnelles. Calcule
les indices de sécheresse, les probabilités de pluie, les degrés-jours de croissance
et le bilan hydrique des sols selon la méthode FAO-56.

[Voir la documentation de kadi.weather](weather/index.md)

### `kadi.kidas` - Traitement et standardisation des données

Pipeline complet d'ingestion, nettoyage, validation et normalisation. Lit les
fichiers CSV, Excel, JSON, NetCDF et les API REST. Produit des données prêtes à
l'analyse.

[Voir la documentation de kadi.kidas](kidas/index.md)

---

## Installation

```bash
git clone https://github.com/delsDin/kadipy.git
cd kadipy

# Création de l'environnement virtuel
python -m venv .kadi_venv
source .kadi_venv/bin/activate

# Installation des dépendances
pip install -r requirements.txt
```

### Configuration de l'environnement

Créez un fichier `.env` à la racine du projet pour activer les sources de données réelles :

```env
# Clé API WFP DataBridges (facultatif — des données simulées sont utilisées sans elle)
WFP_API_Token=votre_cle_ici

# Prix du carburant manuel en XOF/litre (facultatif)
BENIN_FUEL_PRICE=680
```

---

## Démarrage rapide

### Analyse de marché

```python
from kadi.market import Market

# Initialisation pour Parakou
marche = Market(lat=9.30, lon=2.08, location="Parakou")

# Résumé des prix du maïs sur 90 jours
resume = marche.price_crop("maize", days_back=90)
print(f"Prix médian : {resume['prix_median']} XOF/kg")
print(f"Source : {'réelle' if not resume['is_simulated'] else 'simulée'}")
```

### Analyse météo

```python
from kadi.weather import WeatherSession

session = WeatherSession(latitude=9.3333, longitude=2.6333, name="Parakou")

# Probabilité de pluie demain
risque = session.rain_probability(days_ahead=1)
print(risque["recommendation"])

# Indice de sécheresse SPI sur 3 mois
secheresse = session.drought_index(method="spi", window_months=3)
print(f"Sévérité : {secheresse['drought_severity']}")
```

### Intégration météo + marché

```python
from kadi.weather import WeatherSession
from kadi.market import Market

# La session météo enrichit automatiquement les calculs logistiques
ws = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
marche = Market(lat=9.30, lon=2.08, location="Parakou", weather_session=ws)

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

### Traitement de données

```python
import kadi.kidas as kidas

# Chargement et nettoyage en une ligne
df, rapport = kidas.load_and_clean("recolte_2024.csv")
print(f"{len(df)} lignes chargées")
print(f"Score qualité : {rapport['quality_score']['overall']:.2f}")
```

---

## Lancer les tests

```bash
pytest tests/ -q
```

Les tests couvrent les 3 modules avec des mocks pour les appels réseau. Aucune
clé API n'est nécessaire pour les faire passer.

---

## Structure du projet

```
kadipy/
├── kadi/
│   ├── market/          # Module économie agricole
│   ├── weather/         # Module météorologie agronomique
│   ├── kidas/           # Module traitement des données
│   ├── cache.py         # Cache SQLite partagé
│   ├── config.py        # Configuration centralisée
│   └── exceptions.py    # Exceptions personnalisées
├── tests/               # Suite de tests (pytest)
├── docs/                # Cette documentation
├── config/              # Fichiers de configuration (prix carburant...)
└── requirements.txt
```

---

## Zone géographique (V1.0.0)

KadiPy V1.0.0 est conçu **exclusivement pour le Bénin**. La validation des
coordonnées GPS, les algorithmes phénologiques, les facteurs logistiques et les
données de prix sont calibrés pour le contexte béninois.

Le support d'autres pays d'Afrique de l'Ouest est prévu dans les versions futures.
