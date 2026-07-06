# Module kadi.market

Ce module constitue le cœur d'analyse économique et de prévision des marchés de KadiPy. Il est conçu pour modéliser le marché agricole béninois de manière dynamique, en calculant les opportunités d'arbitrage (vente immédiate vs stockage, ou transfert de marchandises entre deux villes) en s'appuyant sur des données réelles et géospatiales.

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
- **Géocodage** : Traduit les noms de villes en coordonnées GPS (latitude/longitude) via l'API Nominatim (OpenStreetMap).
- **Routage Routier (OSRM)** : Calcule la vraie distance routière de conduite (et non à vol d'oiseau) via les serveurs publics OSRM. Les itinéraires sont mis en cache dans `~/.kadi/osrm_cache.json`.
- **Formule de Coût** : Calcule le coût de transfert total avec la formule suivante :
  `C_transfer = Coûts d'information + (Distance * (État de la route * Prix du Carburant) + Tracasseries policières) + Perte de Qualité`
- **Carburant Dynamique** : Le prix de l'essence n'est pas codé en dur. Il est récupéré via la variable d'environnement `BENIN_FUEL_PRICE`. S'il est absent, il interroge un [fichier de configuration communautaire hébergé sur GitHub](https://raw.githubusercontent.com/delsDin/kadipy/main/config/fuel_prices.json), avec un repli mathématique à 680 XOF en cas d'échec total.

### 5. `kadi.market.decision_support` (Aide à la Décision)
Synthétise les données de tous les autres modules pour fournir une recommandation exploitable pour l'agriculteur.
- **Arbitrage Spatial** : Est-ce rentable de payer le transport pour vendre ailleurs ? Compare le bénéfice brut (Prix Destination - Prix Origine) au coût de transfert logistique total.
- **Stockage Stratégique** : Est-ce rentable d'attendre 3 mois ? Compare le prix projeté futur (Forecasting) au prix actuel additionné des coûts fixes et variables de stockage sur la période.

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

Bien que fonctionnel, ce module a vocation à évoluer pour être encore plus précis. Voici les grands axes de développement futurs :

1. **Intégration Météorologique Complète (`kadi.weather`)** :
   - Connecter le module logistique aux historiques et prévisions de précipitations.
   - Objectif : Dégrader automatiquement l'état des routes (`gamma_route`) et augmenter le coefficient de perte de qualité (`c_qualite_loss`) de manière exponentielle si le transport s'effectue en pleine saison des pluies.

2. **Modèles de Prévisions Avancés (Time-Series)** :
   - Remplacer le `MLPRegressor` actuel (qui convient bien pour un PoC) par des modèles taillés pour les séries temporelles saisonnières (ex: **Facebook Prophet**, ou réseaux **LSTM**).
   - Objectif : Mieux capturer les cycles récurrents comme la *période de soudure* annuelle béninoise.

3. **Graphes de Transport Multimodaux** :
   - Plutôt que d'estimer un simple trajet du Point A au Point B, permettre le calcul multi-étapes (ex: 20 km de piste en charrette tractée, puis 150 km de route asphaltée en camion).
   - Objectif : Rendre le module logistique pertinent même pour le "dernier kilomètre" en zone très enclavée.

4. **Modélisation Avancée du Stockage** :
   - Affiner l'aide à la décision en incluant le coût local des produits de fumigation (ex: Sofagrain) ou les risques d'infestation selon la durée.
   - Inclure la dynamique d'offre et de demande : si le modèle suggère à 10 000 agriculteurs de déstocker en même temps, anticiper la chute mathématique du prix sur le marché de destination.
