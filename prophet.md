# Intégration du modèle Prophet dans kadi.market

**Version cible :** v1.2.0 (Janvier 2027)

**Livraison intermédiaire :** Septembre 2026 (fonctionnalité principale dans kadi.market)

**Dernière mise à jour :** 15 août 2026

**Auteur :** Dels Dinla

---

## 1. Pourquoi intégrer Prophet ?

### Le problème du modèle actuel

KadiPy prédit les prix agricoles avec une régression linéaire enrichie
d'harmoniques de Fourier. Ce modèle a deux qualités importantes : il est
rapide à entraîner et ne nécessite aucune dépendance lourde. Il suffit
d'un historique de vingt points de prix pour produire une prévision avec
un intervalle de confiance et un RMSE calculé par validation croisée.

Cependant, ce modèle repose sur une hypothèse forte : la tendance des prix
évolue de façon linéaire et continue, et la saisonnalité se répète à
l'identique chaque année. Cette hypothèse n'est pas valide pour les marchés
agricoles béninois.

Trois situations concrètes illustrent cette limite :

**Les chocs de prix.** Une sécheresse prolongée au Nord-Bénin, une
fermeture de la frontière avec le Nigéria, ou une hausse brutale du prix
du carburant provoquent une rupture dans la tendance des prix. La régression
linéaire lisse ces ruptures : elle trace une droite moyenne sur l'ensemble
de l'historique, ce qui fausse les prévisions sur la période qui suit le
choc.

**Les saisons anormales.** L'arrivée tardive ou précoce des pluies modifie
la durée et l'amplitude du pic de récolte. La saisonnalité fixée par des
harmoniques ne peut pas s'adapter à ces décalages d'une année sur l'autre.

**Les données manquantes.** Les relevés WFP présentent parfois des trous
de plusieurs semaines, notamment sur les marchés secondaires. La régression
linéaire actuelle gère ces absences de façon mécanique, sans en tenir compte
dans l'incertitude des prévisions.

### Ce que Prophet apporte

Prophet est un modèle de prévision de séries temporelles développé par
l'équipe Data Science de Meta. Il est conçu précisément pour les données
métier qui présentent des tendances irrégulières, des saisonnalités fortes
et des événements ponctuels.

Son fonctionnement repose sur une décomposition additive de la série en
trois composantes indépendantes. La première est la tendance, modélisée
non pas par une droite unique mais par une succession de droites avec des
pentes différentes. Les points de changement de pente sont détectés
automatiquement à partir des données : c'est ce qui permet à Prophet de
s'adapter aux chocs de marché. La deuxième composante est la saisonnalité,
représentée par des séries de Fourier comme dans le modèle actuel, mais
dont les paramètres sont ajustés pour chaque année individuellement. La
troisième composante est l'effet des événements ponctuels, une liste de
dates spéciales auxquelles le modèle autorise une déviation temporaire
de la tendance normale.

Pour KadiPy, les avantages concrets sont les suivants. Prophet gère
nativement les données irrégulières et les trous dans la série, sans
nécessiter de rééchantillonnage préalable. Il produit des intervalles
de confiance bayésiens qui reflètent l'incertitude réelle du modèle,
plus larges après un choc et plus étroits en période stable. Il permet
d'ajouter des variables explicatives externes, comme les précipitations
CHIRPS déjà disponibles dans `kadi.weather`, pour améliorer la précision
sur les cultures sensibles à la sécheresse. Enfin, il fournit une
décomposition visuelle de la prévision (tendance, saisonnalité) qui peut
être communiquée aux utilisateurs non techniques.

---

## 2. Objectif de l'intégration

L'objectif est de remplacer la régression harmonique Fourier par Prophet
comme moteur principal de prévision dans `kadi.market.forecasting`, tout
en garantissant que les utilisateurs existants ne remarquent aucun
changement dans l'interface.

Concrètement, cela signifie que la méthode `predict_price()`, qui est
l'unique point d'entrée public du module de prévision, conserve exactement
la même signature et retourne exactement les mêmes clés de dictionnaire.
La seule différence visible sera la valeur de la clé `model_used`, qui
passera de `"linear_regression_fourier"` à `"prophet"` lorsque le nouveau
modèle est actif.

La régression harmonique n'est pas supprimée. Elle devient le modèle de
secours automatique dans trois situations : si Prophet n'est pas installé
dans l'environnement de l'utilisateur, si l'historique disponible contient
moins de trente observations (Prophet nécessite au moins deux cycles
saisonniers complets pour être fiable), ou si le mode simulation est activé
explicitement via `simulated=True`.

La dépendance à Prophet est déclarée comme optionnelle dans `pyproject.toml`.
Le coeur de KadiPy reste installable sans compiler de code C++, ce qui est
essentiel pour les utilisateurs qui travaillent sur des machines de terrain
avec des connexions lentes.

---

## 3. Planning des travaux

Le planning ci-dessous respecte l'échéance de septembre 2026 fixée dans
le ROADMAP pour la livraison de la fonctionnalité principale, et l'échéance
de janvier 2027 pour la version v1.2.0 complète qui intègre aussi
Penman-Monteith, le connecteur Google Sheets et les données TAMSAT.

### Semaine 1 : Préparation de l'environnement (1 au 7 septembre 2026)

La première semaine est entièrement consacrée à la mise en place technique
sans écrire une seule ligne de code dans le module de prévision.

L'objectif de cette semaine est de vérifier que Prophet peut être installé
proprement dans l'environnement virtuel `.kadi_venv` du projet et que son
installation ne crée aucun conflit de version avec les dépendances existantes
de KadiPy (pandas, numpy, scikit-learn, scipy). Prophet utilise le moteur
probabiliste PyStan en interne, qui requiert une compilation C++ lors de
la première installation.

Une fois l'installation vérifiée, `pyproject.toml` est mis à jour pour
déclarer Prophet comme dépendance optionnelle dans une nouvelle section
dédiée, de façon à ce que la commande `pip install "kadipy[prophet]"` soit
fonctionnelle. `requirements.txt` est également mis à jour avec un commentaire
clair indiquant le caractère optionnel de cette dépendance.

La compatibilité avec les quatre versions de Python supportées par KadiPy
(3.9, 3.10, 3.11 et 3.12) est vérifiée à cette étape.

**Livrable de la semaine :** `pyproject.toml` mis à jour, dépendance installée
et vérifiée sur les quatre versions de Python cibles.

### Semaine 2 : Intégration dans forecasting.py (8 au 14 septembre 2026)

C'est la semaine de travail principal. Elle concentre les modifications
dans le fichier `kadi/market/forecasting.py`.

La première modification est l'ajout d'un import conditionnel en tête de
fichier. Python tente d'importer Prophet au démarrage du module. Si la
bibliothèque n'est pas installée, l'import est intercepté silencieusement
et un drapeau interne signale que Prophet n'est pas disponible. Aucune
erreur n'est levée. Cette approche garantit que KadiPy reste utilisable
même sans Prophet.

La deuxième modification est l'ajout d'une méthode privée de conversion
des données. Prophet attend ses données dans un format particulier avec
deux colonnes nommées `ds` pour les dates et `y` pour les valeurs. Cette
méthode prend le DataFrame nettoyé produit par le modèle actuel et le
transforme dans ce format, ce qui évite de dupliquer la logique de
nettoyage déjà existante.

La troisième modification est l'ajout d'une méthode privée d'entraînement
et de prévision Prophet. Cette méthode instancie le modèle avec les
paramètres adaptés aux marchés agricoles béninois, l'entraîne sur
l'historique disponible, construit les dates futures à l'horizon demandé,
et extrait la prévision centrale ainsi que les bornes de l'intervalle de
confiance. La saisonnalité annuelle est activée pour capturer les cycles
de récolte. La saisonnalité hebdomadaire et journalière sont désactivées
car les données WFP sont des relevés ponctuels et non des séries
quotidiennes régulières.

La quatrième modification est l'ajout d'une méthode privée de validation
croisée adaptée à Prophet. La bibliothèque propose sa propre procédure de
validation croisée temporelle, différente de `TimeSeriesSplit` de
scikit-learn. Elle sera utilisée pour calculer le RMSE uniquement quand
l'historique dépasse soixante points, ce qui correspond à environ deux mois
de données hebdomadaires. En dessous de ce seuil, le RMSE n'est pas calculé
et retourne `NaN`, comme dans le comportement actuel.

La cinquième et dernière modification est la logique de sélection du modèle
dans `predict_price()`. La méthode vérifie si Prophet est disponible et si
l'historique est suffisamment long. Si les deux conditions sont remplies,
elle utilise le backend Prophet. Sinon, elle conserve exactement le chemin
de code actuel de la régression harmonique, sans aucune modification.

**Livrable de la semaine :** `kadi/market/forecasting.py` avec le backend
Prophet intégré, le fallback automatique opérationnel, et `model_used` correct
dans tous les cas.

### Semaine 3 : Backtesting comparatif et tests (15 au 21 septembre 2026)

Cette semaine a deux objectifs parallèles : étendre le backtester pour
permettre la comparaison des deux modèles, et écrire les tests unitaires
qui valident le comportement du nouveau code.

Pour le backtesting, le fichier `kadi/market/backtesting.py` reçoit un
nouveau paramètre optionnel qui permet de forcer le choix du modèle lors
d'une évaluation. Trois valeurs sont supportées : `auto` pour laisser
KadiPy choisir selon la disponibilité de Prophet (comportement par défaut),
`prophet` pour forcer Prophet, et `linear_regression_fourier` pour forcer
la régression harmonique. Chaque résultat de fenêtre d'évaluation inclut
désormais la clé `model_used` pour pouvoir tracer quelle version a été
utilisée lors du calcul des métriques. Ce mécanisme permettra de lancer
deux backtestings successifs sur le même historique et d'afficher côte à
côte les métriques des deux modèles.

Pour les tests unitaires, un nouveau fichier est créé dans
`tests/test_market/`. Il couvre les cas suivants : la conversion correcte
des données au format Prophet, la bascule automatique vers la régression
harmonique quand Prophet n'est pas installé (simulée par une modification
temporaire du drapeau interne), la vérification que `predict_price()` retourne
le bon `model_used` selon le modèle actif, et la vérification que le mode
simulation (`simulated=True`) ne déclenche jamais Prophet. Les tests unitaires
utilisent Prophet en mode simulé via `pytest-mock` pour éviter un entraînement
réel dans la suite de tests automatisés, ce qui maintiendrait la durée
d'exécution de la CI sous la minute.

Les tests du backtesting existants dans `test_backtesting.py` sont complétés
pour vérifier le nouveau paramètre de choix de modèle et la présence de la
clé `model_used` dans les résultats.

**Livrable de la semaine :** `backtesting.py` étendu, suite de tests complète,
tous les tests passent via `pytest tests/test_market/ -v`.

### Semaine 4 : Benchmarking et validation finale (22 au 30 septembre 2026)

La dernière semaine de septembre est consacrée à valider que Prophet
apporte effectivement une amélioration mesurable par rapport à la régression
harmonique sur les données réelles béninoises.

Un notebook de benchmarking est créé dans `examples_local/`. Il exécute
les deux modèles en parallèle sur cinq années de données historiques WFP
pour trois marchés représentatifs du Bénin : Cotonou pour le marché côtier,
Parakou pour le marché central du Nord, et Malanville pour le marché
transfrontalier. Les métriques produites pour chaque combinaison marché /
culture / modèle sont le MAPE (erreur de prévision en pourcentage), le RMSE
en XOF/kg, et la précision directionnelle (pourcentage de fois où le modèle
prédit correctement la direction de la variation de prix). La cible de
performance est un MAPE Prophet inférieur à 12% sur un horizon de trente
jours.

Le notebook documente également les points de rupture de tendance détectés
automatiquement par Prophet sur la série du maïs à Cotonou. Les périodes
de soudure (juin-juillet) et de récolte (octobre-novembre) doivent
apparaître comme des pics de saisonnalité, tandis que les chocs historiques
majeurs (sécheresse 2012, période COVID 2020, flambée des céréales 2022)
doivent correspondre à des changements de pente détectés dans la tendance.

Les résultats du benchmarking alimentent la section "Points de vigilance"
de `ROADMAP.md` avec des métriques réelles, remplaçant les points
d'interrogation du tableau prévisionnel.

**Livrable de la semaine :** notebook de benchmarking exécuté avec les
métriques réelles, `ROADMAP.md` mis à jour, item Prophet marqué comme livré.

---

## 4. Phase avancée : régresseurs climatiques (Novembre 2026 - Janvier 2027)

Cette phase s'inscrit dans le cycle v1.2.0 prévu en janvier 2027 et ne
fait pas partie de la livraison de septembre 2026.

Prophet accepte des variables explicatives externes, appelées régresseurs,
qui permettent d'améliorer la prévision en ajoutant une information
corrélée au phénomène modélisé. Pour les prix agricoles, la pluie est
le candidat naturel : une sécheresse prolongée réduit l'offre et fait
monter les prix avec un délai de quelques semaines.

L'objectif de cette phase est de connecter les précipitations historiques
CHIRPS, déjà disponibles via `kadi.weather`, comme régresseur dans le
modèle Prophet. Cela nécessite de modifier la méthode `Market.predict_price()`
dans `kadi/market/__init__.py` pour transmettre les données de pluie
historiques au module de prévision, puis d'adapter la méthode d'entraînement
Prophet pour intégrer ce régresseur supplémentaire.

Ce couplage représente la première intégration fonctionnelle complète entre
`kadi.weather` et `kadi.market`, qui a jusqu'ici été limitée à l'ajustement
du coût logistique selon les prévisions météo.

---

## 5. Fichiers concernés par l'intégration

| Fichier | Nature de la modification |
|---------|--------------------------|
| `pyproject.toml` | Ajout de la section `prophet` dans les dépendances optionnelles |
| `requirements.txt` | Mention commentée de la dépendance optionnelle |
| `kadi/market/forecasting.py` | Import conditionnel de Prophet, trois nouvelles méthodes privées, logique de sélection du modèle dans `predict_price()` |
| `kadi/market/backtesting.py` | Paramètre de choix de modèle, clé `model_used` dans les résultats de chaque fenêtre |
| `kadi/market/__init__.py` | Propagation du choix de modèle (phase avancée, novembre 2026) |
| `tests/test_market/test_forecasting_prophet.py` | Nouveau fichier de tests unitaires pour le backend Prophet |
| `tests/test_market/test_backtesting.py` | Tests complémentaires pour le paramètre de choix de modèle |
| `examples_local/benchmark_prophet_vs_fourier.ipynb` | Notebook de benchmarking comparatif |
| `kadi/market/README.md` | Section dédiée au modèle Prophet |
| `ROADMAP.md` | Mise à jour de l'état de l'item Prophet |

---

## 6. Critères d'acceptation

L'intégration de septembre 2026 est considérée comme terminée quand
l'ensemble des conditions suivantes est satisfait.

L'installation de `kadipy[prophet]` se déroule sans erreur sur les quatre
versions de Python supportées par le projet (3.9 à 3.12).

La méthode `predict_price()` retourne `model_used` égal à `"prophet"` quand
Prophet est installé et l'historique contient trente observations ou plus.
Elle retourne `model_used` égal à `"linear_regression_fourier"` quand Prophet
n'est pas installé, et ce sans lever d'exception ni afficher d'avertissement
visible pour l'utilisateur.

L'ensemble des tests unitaires du module `kadi.market` passe sans erreur.
La couverture de tests du fichier `forecasting.py` reste au-dessus de 80%.

Le MAPE du modèle Prophet est inférieur à 12% sur les cinq marchés principaux
du Bénin, sur un horizon de trente jours, selon les résultats du notebook de
benchmarking exécuté sur les données WFP réelles.

---

## 7. Points de vigilance

**Performance dans la CI.** Un entraînement Prophet réel prend entre 200
millisecondes et une seconde. Le backtesting sur dix fenêtres glissantes
peut donc atteindre dix secondes de calcul. Les tests unitaires doivent
simuler Prophet via `pytest-mock` pour maintenir la durée d'exécution de
la suite de tests sous la minute.

**Verbosité de PyStan.** Le moteur probabiliste utilisé par Prophet en
interne génère des messages de diagnostic dans les logs. Ces messages
doivent être filtrés dans les tests et dans la CI pour éviter de polluer
les sorties.

**Priorité du mode simulation.** Le mode `simulated=True`, qui permet aux
utilisateurs de travailler sans connexion réseau, ne doit jamais déclencher
Prophet. Le fallback simulé existant s'active en priorité absolue, avant
toute vérification de la disponibilité de Prophet.

**Volume de l'historique.** Prophet nécessite au minimum deux cycles
saisonniers complets pour ajuster correctement sa composante de saisonnalité
annuelle. Pour les données hebdomadaires WFP, cela correspond à environ
cent observations (deux ans). La limite technique retenue est fixée à trente
points, ce qui est le minimum absolu. En dessous de cent observations,
l'intervalle de confiance Prophet sera plus large que celui de la régression
harmonique, ce qui est un comportement attendu et correct.

**Données TAMSAT et Penman-Monteith.** L'intégration de TAMSAT et de
Penman-Monteith, prévues également pour la v1.2.0, est indépendante de
Prophet. Ces deux fonctionnalités concernent `kadi.weather` et ne partagent
aucun fichier commun avec les modifications de `kadi.market` décrites
dans ce document.
