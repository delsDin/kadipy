# KadiPy

<div style="display: flex; justify-content: center;">
    <img src="img/logo.png" alt="KadiPy" width="300px">
</div>

**Le "pandas" de l'agriculture africaine.**

KadiPy est une bibliothèque Python conçue pour les agronomes, chercheurs
et développeurs travaillant sur les données agricoles au Bénin et en
Afrique de l'Ouest. Elle fournit une interface unifiée pour traiter les
données météorologiques, les prix de marché et les données de récoltes,
avec une approche hors ligne en premier (offline-first).

---

## Installation

```bash
pip install kadipy
```

Nécessite Python 3.9 ou supérieur.

---

## Modules disponibles

**kadi.market** : analyse économique des marchés agricoles béninois.
- Récupération des prix via l'API WFP DataBridges.
- Prévisions de prix par régression linéaire saisonnière.
- Calcul des coûts de transport avec données routières réelles (OSRM).
- Aide à la décision : arbitrage spatial, stockage stratégique, score de confiance.
- Backtesting des prévisions (MAE, RMSE, MAPE, précision directionnelle).

**kadi.weather** : données météorologiques et indicateurs agronomiques.
- Prévisions et historiques via Open-Meteo et CHIRPS.
- Phénologie : détection de la saison des pluies (Sivakumar, Walter-Anyadike), GDD.
- Hydrologie : évapotranspiration ET0 (Hargreaves-Samani), bilan hydrique FAO-56.
- Risques climatiques : indice de sécheresse (SPI), probabilité de pluie.

**kadi.kidas** : pipeline de traitement des données agricoles.
- Nettoyage : valeurs manquantes, doublons, valeurs aberrantes.
- Validation : types, plages de valeurs, rapport d'erreurs.
- Normalisation : noms de cultures, marchés, unités et coordonnées GPS.

---

## Démarrage rapide

```python
from kadi.weather import WeatherSession
from kadi.market import Market

# Données météo pour Parakou
session = WeatherSession(latitude=9.33, longitude=2.63, name="Parakou")
previsions = session.forecast(days=3)
print(previsions["data"])

# Analyse de marché
marche = Market(latitude=9.30, longitude=2.08, location="Parakou",
                weather_session=session)

# Recommandation d'arbitrage
resultat = marche.decision_support.arbitrage_decision(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0,
)
print(resultat["recommandation"])
print(f"Score de confiance : {resultat['confidence_score']:.0%}")
```

---

## Documentation

La documentation complète est disponible sur :
**https://delsDin.github.io/kadipy/**

---

## Contribution et support

- Dépôt GitHub : https://github.com/delsDin/kadipy
- Licence : MIT
- Python : >= 3.9
