# Feuille de route KadiPy

Ce document présente le planning des versions à venir de KadiPy.
Il est mis à jour à chaque cycle de release ou à la demande du commiters principaux.

**Dernière mise à jour :** 12 septembre 2026

---

## Versions publiées

### v1.0.0 — Juillet 2026

Première version publique. Les trois modules principaux sont fonctionnels :
`kadi.weather`, `kadi.market` et `kadi.kidas`. La gestion hors ligne (cache SQLite,
données simulées) est opérationnelle.

### v1.1.0 — Août 2026

Cycle de corrections et de nouvelles intégrations :

- Correction de 17 problèmes identifiés lors de l'audit de la v1.0.0
  (rapport de pipeline, flag `is_simulated`, SPI loi Gamma, bornes GPS, etc.)
- Intégration de l'API HAPI HumData (PAM) pour les prix de marché réels
- Intégration de l'API Frankfurter pour les taux de change dynamiques
- Réécriture de `soilgrids.py` avec l'API SoilGrids v2.0 (pédologie béninoise)
- Couverture de tests du connecteur CHIRPS portée à 89 %
- Rapport de couverture automatique dans la CI (seuil 70 %)

---

## Principales versions planifiées

| Version | Périmètre principal | Échéance estimée |
|---------|-------------------|-----------------|
| v1.2.0 | Penman-Monteith, connecteur Google Sheets, Prophet, données TAMSAT | Février 2027 |
| v1.3.0 | LSTM prix, détection d'anomalies ML, export HTML interactif, risque inondation | Avril 2027 |
| v2.0.0 | API REST publique, interface web et mobile, Docker | Août 2027 |
| v3.0.0 | couverture régionale, package R | Juillet 2028 |

---

## Planning détaillé par module avec échéance

---

### kadi.market

#### Intégration Prophet - octobre 2026

Remplacement de la régression harmonique actuelle par le modèle Prophet (Facebook)
pour capturer automatiquement les tendances et saisonnalités complexes des prix
agricoles. La régression de Fourier actuelle est une base solide, mais elle ne
gère pas les ruptures de tendance (chocs de prix, saisons anormales).

#### Modèle LSTM de prévision de prix - avril 2027

Réseau de neurones récurrents (LSTM) entraîné sur l'historique WFP complet
(2010-2026) pour les 20 marchés principaux du Bénin. Objectif : MAPE inférieur
à 10 % sur un horizon de 30 jours. La comparaison Prophet vs LSTM sera publiée
dans un notebook de benchmarks.


#### API REST publique - juillet 2027

Exposition des fonctionnalités de `kadi.market` via une API REST auto-hébergeable
construite avec FastAPI, avec documentation OpenAPI générée automatiquement.
Cela permettra aux startups AgriTech et aux organismes institutionnels de
consommer KadiPy sans installer Python.

---

### kadi.weather

#### Évapotranspiration Penman-Monteith FAO-56 - novembre 2026

Remplacement de la méthode Hargreaves-Samani par la méthode Penman-Monteith
FAO-56 complète pour plus de précision sur les cultures exigeantes (riz, tomate,
maraîchage). La méthode complète nécessite les données de vent et d'humidité,
désormais disponibles dans Open-Meteo. L'impact sur l'ETo calculé peut atteindre
15 à 25 % par rapport à Hargreaves-Samani.

#### Données TAMSAT haute résolution - janvier 2027

Intégration de TAMSAT (3 km de résolution au lieu de 25 km pour CHIRPS) pour
les prévisions sur petites parcelles. La résolution de 25 km de CHIRPS est
insuffisante pour les microclimats des zones de transition (plateau d'Abomey,
vallée de l'Ouémé). TAMSAT couvre l'Afrique de l'Ouest depuis 1983.

#### Modèle de risque d'inondation - avril 2027

Calcul du risque d'inondation pour les zones fluviales (bassin de l'Ouémé,
fleuve Niger) à partir des données CHIRPS et d'un modèle numérique de terrain
(MNT). Ce module répondra à un besoin identifié par les partenaires terrain
après les inondations de 2023 dans le département du Zou.

---

### kadi.kidas

#### Connecteur Google Sheets - février 2027

Source de données Google Sheets via l'API `gspread`. Idéal pour les coopératives
qui saisissent leurs données dans des tableurs partagés sans accès à une base
de données. Le connecteur s'intégrera dans le pipeline `DataPipeline` comme
n'importe quelle autre source (CSV, Excel, JSON).

#### Détection d'anomalies par Isolation Forest - mars 2027

Remplacement ou complément de la détection IQR actuelle par l'algorithme
Isolation Forest pour la détection d'anomalies dans les séries de prix agricoles.
L'Isolation Forest offre une meilleure précision que l'IQR sur les données
saisonnières où les valeurs extrêmes légitimes sont fréquentes.

#### Export de rapport HTML interactif - avril 2027

Génération d'un rapport HTML autonome avec Plotly à la place de l'export JSON
actuel. Le rapport inclura des visualisations des tendances, des boxplots de
prix par mois, et des heatmaps de qualité des données. Utilisable sans connexion
internet, depuis un navigateur de terrain.

---

### Général

#### Interface web et mobile - juin 2027

Développement d'une application web et mobile complète pour permettre aux acteurs
de terrain (conseillers agricoles, techniciens de coopératives) d'utiliser les
outils KadiPy sans écrire de code. Priorité accordée aux scénarios les plus
courants : consultation du prix de marché, alerte sécheresse, recommandation
de semis.

#### Mode microservice Docker - juillet 2027

Image Docker officielle pour déployer KadiPy comme microservice dans une
infrastructure AgriTech. Permettra une intégration simplifiée dans les systèmes
d'information existants des institutions partenaires (MAEP, INSAE, FAO Bénin).

#### Package R (kadipy-R) - février 2028

Portage des fonctionnalités principales en R pour les chercheurs et les
économistes agricoles qui travaillent dans l'écosystème R. Interface via
`reticulate` dans un premier temps, puis un wrapper natif R pour les fonctions
clés.

#### Couverture régionale (Niger, Nigéria, Burkina Faso, Togo) - Q2 2028

Extension du catalogue des marchés aux pays voisins du Bénin. Les données WFP
DataBridges sont disponibles pour ces trois pays. Cette extension permettra
d'analyser les corridors commerciaux transfrontaliers (Malanville-Gaya,
Cotonou-Lagos).

---

## Points de vigilance documentés

Les limites suivantes sont connues et seront adressées dans les versions futures :

- La détection d'onset Sivakumar est adaptée au Sahel mais moins précise
  pour les zones côtières humides (département du Littoral, Mono).
- Le modèle de prévision de prix ne prend pas en compte les chocs exogènes
  (crise politique, fermeture de frontière, catastrophe naturelle).
- Le cache SQLite peut devenir volumineux sur plusieurs années de données
  CHIRPS (estimation : 800 Mo pour 10 ans sur 50 localisations).
- KadiPy dépend de services externes (Open-Meteo, CHIRPS, WFP DataBridges,
  OSRM, Nominatim). Une défaillance de l'un de ces services peut dégrader
  les fonctionnalités en ligne, mais le mode hors ligne reste opérationnel.

---

## Comment contribuer

Les contributions sont bienvenues. Consultez [CONTRIBUTING.md](CONTRIBUTING.md)
pour les règles de style, les conventions de commit et le processus de revue.

Pour proposer une fonctionnalité ou signaler un problème :
[github.com/delsDin/kadipy/issues](https://github.com/delsDin/kadipy/issues)
