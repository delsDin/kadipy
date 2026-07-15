# Module kadi.market

Le module `market` est le composant d'analyse économique de KadiPy. Il
modélise les marchés agricoles béninois pour aider les agriculteurs,
groupements et conseillers à prendre de meilleures décisions : vendre
maintenant ou stocker, ici ou ailleurs.

Depuis la Phase 4, il intègre directement les données météorologiques
(`kadi.weather`) pour ajuster les coûts de transport et la fiabilité
des recommandations selon les conditions climatiques en cours.

---

## Architecture

Le module est organisé autour d'une facade principale (`Market`) qui
orchestre six sous-modules spécialisés.

```
Market
    |
    ├── data_ingestion    -> Client WFP DataBridges + cache local
    ├── pricing           -> Normalisation des prix + détection anomalies
    ├── forecasting       -> Prévision par régression linéaire saisonnière
    ├── logistics         -> Distance réelle, coûts de transport, météo
    ├── decision_support  -> Arbitrage, stockage, portfolio, confidence_score
    └── backtesting       -> Evaluation a posteriori des prévisions
```

---

## Sous-modules

### data_ingestion — Client WFP DataBridges

Interface avec l'API publique du Programme Alimentaire Mondial (VAM
DataBridges) pour récupérer les historiques de prix officiels.

- **Endpoints utilisés** : `/Commodities/List`, `/Markets/List`,
  `/MarketPrices/alldata`.
- **Cache local** : les listes de marchés et de cultures sont sauvegardées
  dans `~/.kadi/wfp_cache.json` pour limiter les appels réseau.
- **Fallback** : si la clé API est absente ou le réseau indisponible, le
  module utilise silencieusement un dictionnaire de secours local pour
  continuer à fonctionner.

### pricing — Normalisation et détection d'anomalies

Nettoie et prépare les données brutes avant toute analyse.

- **Normalisation** : convertit toutes les données vers l'unité standard
  `XOF/kg` (100 000 XOF/tonne devient 100 XOF/kg).
- **Détection d'anomalies (Z-Score)** : une alerte est levée si l'écart
  d'un prix dépasse 3 fois l'écart-type sur la période.
- **Interpolation** : comble les trous dans les séries temporelles jusqu'à
  7 jours consécutifs par interpolation linéaire.

### forecasting — Prévision de prix

Anticipe les fluctuations futures des prix agricoles.

- **Modèle** : régression linéaire avec features temporelles et
  saisonnières (harmoniques de Fourier), entraîné sur l'historique
  disponible.
- **Validation** : le RMSE est calculé par validation croisée temporelle
  (`TimeSeriesSplit`) pour évaluer la fiabilité de chaque prévision.
- **Intervalles de confiance** : chaque prévision inclut des bornes `low_90`
  et `high_90` pour mesurer le risque.
- **Fallback** : si l'historique est insuffisant (moins de 20 points), le
  module retourne une estimation simulée clairement signalée.

### logistics — Coûts de transport

Simule la réalité des déplacements de marchandises au Bénin.

- **Géocodage** : traduit les noms de villes en coordonnées GPS via
  l'API Nominatim (OpenStreetMap).
- **Routage réel (OSRM)** : calcule la distance routière effective (pas à
  vol d'oiseau) via les serveurs publics OSRM. Les résultats sont mis en
  cache dans `~/.kadi/osrm_cache.json`.
- **Formule de coût** :
  `C_transfer = Info + (Distance × gamma_route × Carburant) + Perte qualité`
- **Intégration météo (Phase 4)** : le coefficient `gamma_route` est
  automatiquement dégradé selon la probabilité de pluie fournie par
  `WeatherSession`. Les cultures périssables (tomate, oignon) voient leur
  coefficient de perte de qualité augmenter en cas de pluie.
- **Prix du carburant dynamique** : récupéré depuis la variable
  d'environnement `BENIN_FUEL_PRICE`, puis depuis `config/fuel_prices.json`,
  avec un repli à 680 XOF/litre.

### decision_support — Aide à la décision

Synthétise les données de tous les autres modules pour produire une
recommandation exploitable.

- **Arbitrage spatial** : compare le bénéfice brut (prix destination moins
  prix origine) au coût total de transfert logistique.
- **Stockage stratégique** : compare le prix projeté futur au prix actuel
  additionné des coûts de stockage, sur un horizon configurable
  (`mois_stockage`).
- **Score de confiance (Phase 4)** : chaque recommandation inclut un
  `confidence_score` composite (0 à 1), calculé à partir de la qualité de
  l'historique, du RMSE du modèle et de la probabilité de pluie.
- **Optimisation de portfolio** : `portfolio_optimization()` utilise
  `scipy.optimize.linprog` si disponible, avec un fallback heuristique.

### backtesting — Evaluation a posteriori

Mesure la qualité des prévisions sur des données historiques réelles.

- **Principe** : fenêtres glissantes sur l'historique, prévision simulée
  à chaque point de coupure, comparaison avec les prix réellement observés.
- **Métriques** : MAE, RMSE, MAPE et précision directionnelle (proportion
  de hausses et de baisses correctement prédites).

---

## Utilisation rapide

```python
from kadi.market import Market

# Initialisation du marché (agriculteur à Parakou)
marche = Market(latitude=9.30, longitude=2.08, location="Parakou")

# Arbitrage spatial : vaut-il mieux vendre à Cotonou ?
resultat = marche.decision_support.arbitrage_decision(
    crop="maize",
    origine="Parakou",
    destination="Cotonou",
    qty_tons=10.0,
)
print(resultat["recommandation"])
print(f"Bénéfice net estimé : {resultat['gain_net_percent']}%")

# Coût de transport détaillé
cout = marche.logistics.calculate_transfer_cost(
    origine="Parakou",
    destination="Malanville",
)
print(f"Distance       : {cout['details']['distance_km']} km")
print(f"Coût total     : {cout['total_cost_cfa']} XOF")

# Prévision de prix à 30 jours
prevision = marche.forecasting.predict_price(
    crop="maize", market="Parakou", days_ahead=30
)
print(f"Prix prévu     : {prevision['predicted_price']} XOF/kg")
print(f"Pire scénario  : {prevision['low_90']} XOF/kg")
```

### Avec intégration météo (Phase 4)

```python
from kadi.weather import WeatherSession
from kadi.market import Market

session = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
marche = Market(lat=9.30, lon=2.08, location="Parakou", weather_session=session)

risque = marche.assess_climate_risk(days_ahead=7)
print(risque["recommendation"])
```

---

## Configuration

Renseignez le fichier `.env` à la racine du projet pour activer les
données réelles :

```env
# Clé API WFP DataBridges (optionnel, fallback local si absent)
WFP_API_Token=votre_cle_api_ici

# Prix de l'essence en XOF/litre (optionnel, 680 par défaut)
BENIN_FUEL_PRICE=680
```

---

## Dépendances

- `pandas` / `numpy` : manipulation des séries temporelles
- `scikit-learn` : régression linéaire, validation croisée
- `requests` : appels API WFP, Nominatim, OSRM
- `scipy` (optionnel) : optimisation de portfolio

---

## Tests

```bash
# Suite complète
pytest tests/test_market/ -v

# Backtesting uniquement
pytest tests/test_market/test_backtesting.py -v
```

---

## Améliorations prévues

**Modèles de prévision avancés**
Remplacer la régression linéaire par des modèles taillés pour les séries
saisonnières (Facebook Prophet, LSTM) pour mieux capturer la période de
soudure annuelle béninoise.

**Transport multimodal**
Permettre les trajets multi-étapes (piste en charrette puis route asphaltée)
pour modéliser le dernier kilomètre en zone enclavée.

**Modélisation avancée du stockage**
Inclure le coût des produits de fumigation (Sofagrain) et anticiper la
chute de prix en cas de destockage simultané à grande échelle.
