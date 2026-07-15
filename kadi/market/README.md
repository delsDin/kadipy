# Module kadi.market

Ce module constitue le coeur d'analyse économique et de prévision des marchés de KadiPy. Il est conçu pour modéliser le marché agricole béninois de manière dynamique, en calculant les opportunités d'arbitrage (vente immédiate vs stockage, ou transfert de marchandises entre deux villes) en s'appuyant sur des données réelles et géospatiales.

Depuis la Phase 4, le module intègre directement les données météorologiques (`kadi.weather`) pour ajuster les coûts de transport, la perte de qualité des cultures et le score de confiance des recommandations.

---

## Architecture Détaillée

Le module est construit autour d'une façade principale (`Market`) qui orchestre 4 sous-modules spécialisés et un client d'ingestion de données robuste.

### 1. `kadi.market.data_ingestion` (Client WFP DataBridges)
Ce sous-module gère l'interface avec l'API publique du Programme Alimentaire Mondial (VAM DataBridges).
- **Récupération dynamique** : Télécharge les historiques de prix quotidiens, les identifiants officiels des marchés (ex: `Dantokpa`, `Savalou_Market`) et des cultures agricoles (`Maize`, `Rice`).
- **Endpoints utilisés** : `/Commodities/List`, `/Markets/List`, et `/MarketPrices/alldata`.
- **Résilience et Cache** : 
  - Les listes de marchés et de cultures sont sauvegardées dans `~/.kadi/wfp_cache.json` pour éviter des appels réseau inutiles.
  - Si le réseau est indisponible ou si l'API renvoie une erreur (ex: 401 Unauthorized en l'absence de clé valide), le module utilise silencieusement un **dictionnaire de secours local** (fallback) pour continuer à fonctionner.

### 2. `kadi.market.pricing` (Normalisation et Détection d'Anomalies)
Ce module nettoie et prépare les données brutes.
- **Normalisation** : Convertit systématiquement toutes les unités monétaires et de poids vers le standard `XOF/kg` (par exemple, 100 000 XOF/Tonne devient 100 XOF/kg).
- **Détection d'anomalies (Z-Score)** : Repère les flambées soudaines de prix. Une anomalie est levée si l'écart d'un prix par rapport à la moyenne dépasse 3 fois l'écart-type (`|z-score| > 3`).
- **Interpolation** : Utilise l'interpolation linéaire (`method='linear'`) pour combler automatiquement les trous dans les séries temporelles jusqu'à un maximum de 7 jours consécutifs.

### 3. `kadi.market.forecasting` (Prévisions par Machine Learning)
Anticipe les fluctuations futures des prix agricoles.
- **Algorithmes** : Combine un réseau de neurones (`MLPRegressor` avec architecture optimisée) et une régression linéaire standard de `scikit-learn` pour estimer la tendance.
- **Volatilité et Intervalles de Confiance** : En plus du prix prédit, calcule l'erreur absolue moyenne (MAE) historique pour générer des bornes de confiance (`low_90` et `high_90`), permettant de mesurer le risque.

### 4. `kadi.market.logistics` (Frictions, Routage et Coûts de Transport)
Le moteur logistique qui simule la réalité du terrain au Bénin.
- **Géocodage** : Traduit les noms de villes en coordonnées GPS via l'API Nominatim (OpenStreetMap).
- **Routage Routier (OSRM)** : Calcule la vraie distance routière via les serveurs publics OSRM. Les itinéraires sont mis en cache dans `~/.kadi/osrm_cache.json`.
- **Formule de Coût** : Calcule le coût de transfert total avec la formule :
  `C_transfer = Coûts d'information + (Distance * gamma_route * Prix du Carburant) + Perte de Qualité`
- **Intégration météo (Phase 4)** : Le coefficient `gamma_route` est ajusté automatiquement selon la probabilité de pluie fournie par `WeatherSession`. Les cultures périssables (tomate, oignon) voient leur coefficient de perte de qualité augmenté en cas de pluie.
- **Carburant Dynamique** : Récupéré via la variable d'environnement `BENIN_FUEL_PRICE`, avec un repli sur `config/fuel_prices.json` ou 680 XOF.

### 5. `kadi.market.decision_support` (Aide à la Décision)
Synthétise les données de tous les autres modules pour fournir une recommandation exploitable.
- **Arbitrage Spatial** : Compare le bénéfice brut (Prix Destination - Prix Origine) au coût de transfert logistique total.
- **Stockage Stratégique** : Compare le prix projeté futur au prix actuel, en tenant compte des coûts de stockage et d'un horizon configurable (`mois_stockage`).
- **Score de Confiance (Phase 4)** : Chaque recommandation inclut un `confidence_score` (0 à 1) composite : qualité de l'historique, RMSE du modèle et probabilité de pluie.
- **Optimisation de Portfolio (scipy)** : `portfolio_optimization()` utilise `scipy.optimize.linprog` si disponible, avec un fallback heuristique.

### 6. `kadi.market.backtesting` (Évaluation a posteriori)
Mesure la qualité des prévisions sur des données historiques réelles.
- **Principe** : Fenêtres glissantes sur l'historique, prévision simulée, comparaison avec les prix observés.
- **Métriques** : MAE, RMSE, MAPE et précision directionnelle (proportion de hausses/baisses correctement prédites).

---

## Utilisation de base

Plutôt que d'appeler les sous-modules séparément, la classe `Market` agit comme un guichet central.

```python
from kadi.market import Market

# Initialisation du marché localisé (exemple: agriculteur à Parakou)
marche = Market(latitude=9.30, longitude=2.08, location="Parakou")

# --- 1. Tester l'arbitrage spatial ---
# "Est-ce que je gagne plus d'argent en allant vendre 10 tonnes de maïs à Cotonou ?"
resultat_arbitrage = marche.decision_support.arbitrage_decision(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0
)

print(resultat_arbitrage['recommandation'])
print(f"Bénéfice net estimé : {resultat_arbitrage['gain_net_percent']}%")


# --- 2. Obtenir le coût détaillé du trajet (Module Logistique) ---
couts_trajet = marche.logistics.calculate_transfer_cost(
    origine="Parakou", 
    destination="Malanville"
)

# Affiche la vraie distance routière récupérée par OSRM
print(f"Distance: {couts_trajet['details']['distance_km']} km") 
# Affiche le coût total en incluant l'essence dynamique et les tracasseries
print(f"Coût de transfert: {couts_trajet['total_cost_cfa']} XOF")


# --- 3. Faire une prévision de prix (Module Forecasting) ---
prevision = marche.forecasting.predict_price(
    crop="maize",
    market="Parakou",
    days_ahead=30
)

print(f"Prix prévu dans 30 jours: {prevision['predicted_price']} XOF/kg")
print(f"Pire scénario possible: {prevision['low_90']} XOF/kg")
```

---

## Configuration de l'environnement

Pour un fonctionnement optimal (récupération des données réelles au lieu des fallbacks), renseignez le fichier `.env` à la racine de votre projet :

```env
# (Optionnel) Clé API de l'ONU pour récupérer les vrais historiques de prix
WFP_API_Token=votre_cle_api_ici

# (Optionnel) Force manuellement le prix de l'essence. S'il est omis, KadiPy
# tentera de lire config/fuel_prices.json depuis le web.
BENIN_FUEL_PRICE=680
```

## Dépendances

Le module requiert les librairies suivantes (listées dans `requirements.txt`) :
- `pandas` (Manipulation de séries temporelles)
- `numpy` (Calculs mathématiques et Z-Score)
- `scikit-learn` (Modèles de Machine Learning MLP et Regression)
- `requests` (Appels aux API WFP, Nominatim, OSRM et GitHub)

---

## Améliorations Futures

Bien que fonctionnel, ce module a vocation à évoluer pour être encore plus précis :

1. **Modèles de Prévisions Avancés (Time-Series)** :
   - Remplacer la régression linéaire actuelle par des modèles taillés pour les séries temporelles saisonnières (ex: Facebook Prophet ou réseaux LSTM).
   - Objectif : Mieux capturer les cycles récurrents comme la période de soudure annuelle béninoise.

2. **Graphes de Transport Multimodaux** :
   - Plutôt qu'un simple trajet A-B, permettre le calcul multi-étapes (ex: 20 km de piste en charrette, puis 150 km de route en camion).
   - Objectif : Rendre le module logistique pertinent même pour le dernier kilomètre en zone enclavée.

3. **Modélisation Avancée du Stockage** :
   - Inclure le coût des produits de fumigation (ex: Sofagrain) ou les risques d'infestation selon la durée.
   - Anticiper la chute du prix si de nombreux agriculteurs déstockent simultanément.
