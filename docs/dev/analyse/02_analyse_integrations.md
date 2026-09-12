# Analyse des intégrations à faire — KadiPy

**Date :** 6 août 2026
**Base :** lecture directe du code source + croisement des trois documents de référence
**Branche analysée :** `v1.1.0`

---

## Contexte

Le package a traversé un cycle de correction solide. Les 17 points du rapport v1.0.0 sont traités. Ce document ne repart pas de zéro : il part de l'état actuel du code pour identifier ce qui est encore fragile, manquant ou risqué avant un déploiement ou une publication PyPI.

Les intégrations sont classées en deux niveaux : ce qui bloque la fiabilité immédiate, et ce qui renforce la valeur du produit à moyen terme.

---

## Partie 1 — Intégrations critiques à faire maintenant

Ces points créent des problèmes réels : données incorrectes, failles de sécurité, incohérences visibles pour l'utilisateur, ou risques à la publication.

---

### C1 — Incrémenter la version du package

**Fichier :** [`pyproject.toml`](file:///home/dels/Bureau/kadipy/pyproject.toml) ligne 11

**Problème :** Le fichier déclare `version = "1.0.0"` alors que la branche s'appelle `v1.1.0` et que des corrections majeures ont été livrées. Un utilisateur qui installe le package via PyPI recevra un package annoté `1.0.0` malgré toutes les améliorations.

**Action :**
```toml
version = "1.1.0"
```

**Risque si non traité :** Toute publication sur PyPI avec la version actuelle sera trompeuse. Les changelogs et les tags Git seront incohérents avec le numéro de version distribué.

---

### C2 — Retirer l'identifiant personnel de `config.py`

**Fichier :** [`kadi/config.py`](file:///home/dels/Bureau/kadipy/kadi/config.py) ligne 264

**Problème :** La variable `HAPI_APP_IDENTIFIER` contient une valeur par défaut non nulle :

```python
HAPI_APP_IDENTIFIER = os.environ.get("HAPI_APP_IDENTIFIER", "a2FkaXB5OmRlbHNkZW5sYS5kZXZAZ21haWwuY29t")
```

Ce bloc encode en base64 la chaîne `kadipy:delsdenla.dev@gmail.com`. C'est une adresse email personnelle codée en dur dans le code source public. Cela pose deux problèmes :

1. **Sécurité :** Quiconque installe le package peut décoder cet identifiant et usurper l'accès à l'API HAPI sous votre nom.
2. **Comportement trompeur :** Le client WFP n'entre jamais en mode simulation faute d'identifiant : il utilise toujours votre identifiant personnel. L'utilisateur qui n'a pas configuré `HAPI_APP_IDENTIFIER` pense travailler avec ses propres credentials, mais utilise les vôtres.

**Action :**
```python
HAPI_APP_IDENTIFIER = os.environ.get("HAPI_APP_IDENTIFIER", "")
```

La valeur vide force le mode simulation si l'utilisateur n'a pas configuré sa variable d'environnement, ce qui est le comportement documenté.

**Risque si non traité :** Exposition publique de credentials personnels dès la publication sur PyPI ou GitHub.

---

### C3 — Corriger le stockage de `data_source` dans le cache SQLite

**Fichier :** [`kadi/weather/data.py`](file:///home/dels/Bureau/kadipy/kadi/weather/data.py) ligne 222

**Problème :** Lors de la sauvegarde en cache SQLite, la colonne `data_source` est écrite en dur comme `"mock_api"` pour toutes les données, quelle que soit leur source réelle :

```python
cursor.execute("""
    INSERT INTO weather_data (...)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    ..., data_type, "mock_api",  # ← valeur en dur incorrecte
    1.0, now
))
```

Cela signifie que toutes les données météo stockées en cache, qu'elles viennent de CHIRPS, d'Open-Meteo ou d'un appel API réel, sont annotées `"mock_api"`. Le bénéfice de la colonne `data_source` dans le cache est perdu, et toute analyse de la provenance des données en cache sera faussée.

**Action :** Utiliser la variable `data_type` qui contient déjà `"historical"` ou `"forecast"`, et ajouter une variable `data_source_str` issue du contexte d'appel.

```python
# Valeur correcte : utiliser la source réelle depuis le DataFrame si disponible
source_val = "open-meteo"  # valeur par défaut
if "data_source" in data.columns:
    sources_uniques = data["data_source"].dropna().unique()
    if len(sources_uniques) > 0:
        source_val = sources_uniques[0]  # source dominante

cursor.execute("""INSERT INTO weather_data (...) VALUES (...)""",
    (..., data_type, source_val, 1.0, now))
```

**Risque si non traité :** Les données historiques CHIRPS en cache sont identifiées comme `"mock_api"`, ce qui invalide toute analyse de provenance ou de qualité des données.

---

### C4 — Clarifier le rôle de `data_ingestion.py`

**Fichier :** [`kadi/market/data_ingestion.py`](file:///home/dels/Bureau/kadipy/kadi/market/data_ingestion.py)

**Problème :** Ce fichier fait 25 485 octets. Avec l'intégration de `WFPDataBridgesClient`, ses responsabilités se recoupent probablement avec celles du nouveau client. Deux risques :

- Si des méthodes de `data_ingestion.py` sont encore utilisées en parallèle du nouveau client, il y a un risque de données incohérentes ou de comportements dupliqués.
- Si le fichier est mort (non importé), il alourdit inutilement le package.

**Action immédiate :** Vérifier les imports dans tous les fichiers du module `market`. Si `data_ingestion.py` n'est plus importé nulle part, le supprimer ou documenter explicitement son rôle résiduel.

**Risque si non traité :** Confusion pour tout contributeur ou mainteneur cherchant la source des données de marché.

---

### C5 — Vérifier `soilgrids.py` et son intégration dans `hydrology.py`

**Fichier :** [`kadi/_sources/soilgrids.py`](file:///home/dels/Bureau/kadipy/kadi/_sources/soilgrids.py) (1 580 octets)

**Problème :** Le module `hydrology.py` appelle `fetch_soil_type(lat, lon)` depuis `soilgrids.py` pour déterminer automatiquement le type de sol. Avec seulement 1 580 octets, cette implémentation est très légère pour une source de données géospatiale. Si la fonction retourne une valeur statique ou non documentée, le calcul du bilan hydrique sera silencieusement erroné pour des localisations dont le sol ne correspond pas au type retourné.

**Action :** Lire le contenu de `soilgrids.py`, vérifier si l'appel est réel (API SoilGrids) ou une valeur de repli statique, et documenter le comportement clairement dans la docstring de `Hydrology.__init__`.

**Risque si non traité :** Bilan hydrique calculé avec un type de sol incorrect sans aucun avertissement.

---

### C6 — Tests pour le connecteur CHIRPS

**Fichier :** [`kadi/_sources/chirps.py`](file:///home/dels/Bureau/kadipy/kadi/_sources/chirps.py)

**Problème :** `chirps.py` est complet (350 lignes, gestion du cache, téléchargement, découpage raster). Aucun test dédié n'a été identifié. Si une modification introduit une régression dans la logique de découpage ou de disponibilité des données, elle passera silencieusement.

**Action :** Créer `tests/weather/test_chirps.py` avec au minimum :
- Un test unitaire de `_chirps_disponible_pour()` avec des dates dans le passé et des dates récentes.
- Un test de `_construire_url()` sur une date donnée.
- Un test de `fetch_historical_precipitation()` avec un mock réseau simulant un raster valide.

**Risque si non traité :** La source de données la plus complexe du package n'est pas protégée par des tests, ce qui est particulièrement problématique pour une source dépendant d'une URL externe.

---

## Partie 2 — Intégrations à planifier pour plus tard

Ces points améliorent la valeur scientifique, l'adoption et la robustesse à long terme. Ils ne bloquent pas le fonctionnement actuel.

---

### P1 — Activer Penman-Monteith dans le bilan hydrique

**Fichier :** [`kadi/weather/hydrology.py`](file:///home/dels/Bureau/kadipy/kadi/weather/hydrology.py)

**Constat :** La méthode `et0_fao56_penman()` est pleinement implémentée (FAO-56, équation complète avec humidité, vent et rayonnement). Elle n'est jamais appelée. Le bilan hydrique utilise exclusivement Hargreaves-Samani, qui est une approximation.

**Valeur :** Penman-Monteith est la méthode de référence internationale (FAO-56). Pour les cultures à forte sensibilité hydrique (riz, tomate), la différence avec Hargreaves peut atteindre 15 à 25% sur l'ETo calculé. Activer Penman-Monteith permettrait à KadiPy de produire des estimations de bilan hydrique utilisables dans des rapports agronomiques officiels.

**Condition :** Nécessite que les données météo sources incluent humidité, vitesse du vent et rayonnement solaire. Open-Meteo fournit ces variables. Il faudra vérifier leur présence dans le DataFrame retourné par `fetch_historical()`.

**Horizon suggéré :** v1.2.0

---

### P2 — Modèle de prévision de prix plus robuste

**Fichier :** [`kadi/market/forecasting.py`](file:///home/dels/Bureau/kadipy/kadi/market/forecasting.py)

**Constat :** Le modèle actuel est une régression linéaire avec harmoniques de Fourier. C'est un bon point de départ, solide et interprétable. La feuille de route mentionne Prophet et LSTM pour les versions suivantes.

**Valeur :** Pour des marchés agricoles saisonniers comme ceux du Bénin, Prophet (développé par Meta pour les séries temporelles avec saisonnalité) est significativement plus précis sur des horizons de 30 à 90 jours. Une évaluation comparative avec le MAPE réel sur des données historiques béninoises permettrait de justifier objectivement ce choix.

**Recommandation :** Avant de coder Prophet ou LSTM, calculer le MAPE réel du modèle actuel sur les données WFP disponibles. Publier ce chiffre dans la documentation. C'est la métrique manquante depuis la v1.0.0.

**Horizon suggéré :** v1.2.0 (Prophet), v2.0.0 (LSTM si pertinent)

---

### P3 — Transport multimodal dans `logistics.py`

**Fichier :** [`kadi/market/logistics.py`](file:///home/dels/Bureau/kadipy/kadi/market/logistics.py)

**Constat :** Le module couvre uniquement le transport routier via OSRM + Nominatim. La feuille de route originale mentionne le transport fluvial. Les cours d'eau au Bénin (Ouémé, Mono, Couffo) sont utilisés pour le transport de cultures dans certaines régions.

**Valeur :** Faible pour la v1.x, car les données de distances et coûts fluviaux sont difficiles à obtenir et à modéliser. À prioriser uniquement si des partenaires terrain expriment ce besoin.

**Horizon suggéré :** v2.0.0 ou sur demande d'un partenaire terrain

---

### P4 — Connecteurs vers les données locales béninoises

**Constat :** KadiPy utilise exclusivement des sources internationales (Open-Meteo, CHIRPS, HAPI HumData, OSRM). Les données du MAEP (Ministère de l'Agriculture, de l'Élevage et de la Pêche), de l'INSAE (Institut National de la Statistique), et des coopératives béninoises ne sont pas intégrées.

**Valeur :** C'est la lacune la plus importante pour l'adoption locale. Un outil qui ignore les données officielles béninoises sera difficile à légitimer auprès des institutions et des partenaires terrain.

**Prochaine étape concrète :** Identifier si le MAEP ou l'INSAE exposent des données via une API ou un portail de données ouvertes. Un premier connecteur sous forme de `DataSource` kidas serait le vecteur naturel d'intégration.

**Horizon suggéré :** v1.2.0 (si données accessibles) ou v2.0.0

---

### P5 — Interface de visualisation ou notebook interactif

**Constat :** KadiPy est une bibliothèque Python pure. Un conseiller agricole ou un technicien de coopérative ne peut pas l'utiliser sans écrire du code.

**Valeur :** Critique pour l'adoption non-technique. Deux options envisageables :
1. **Notebook Jupyter interactif** : rapide à produire, adapté à un public ayant une formation technique minimale.
2. **Interface web légère** : plus complexe, mais utilisable sur mobile sur le terrain.

**Horizon suggéré :** v1.2.0 (notebook), v2.0.0 (interface web)

---

### P6 — Publication de métriques de performance

**Constat :** Ni la documentation, ni le README, ni les tests ne publient de métriques concrètes sur les performances du package : MAPE du modèle de prévision sur des données réelles, temps de nettoyage d'un fichier de 10 000 lignes, mémoire utilisée par le cache sur 5 ans de données CHIRPS.

**Valeur :** C'est la principale objection que rencontrera le package dans un contexte académique ou institutionnel. Sans ces chiffres, KadiPy reste une démonstration de concept solide, pas un outil validé.

**Action concrète :** Créer un notebook `benchmarks/performance_report.ipynb` publié dans le dépôt, avec des résultats reproductibles sur des données historiques WFP connues.

**Horizon suggéré :** v1.1.1 ou v1.2.0

---

### P7 — Feuille de route datée

**Constat :** La feuille de route ne contient pas de dates. Un contributeur externe ou un partenaire ne peut pas s'organiser autour du planning de KadiPy.

**Action :** Ajouter dans `CONTRIBUTING.md` ou dans un fichier `ROADMAP.md` un tableau avec les versions, leurs périmètres et leurs échéances estimées.

**Exemple :**
| Version | Périmètre | Échéance |
|---------|-----------|----------|
| v1.1.0 | Corrections + API WFP | Août 2026 |
| v1.2.0 | Penman-Monteith, MAEP, benchmarks | Décembre 2026 |
| v2.0.0 | Prophet, interface web | Juin 2027 |

**Horizon suggéré :** Avant toute publication externe

---

## Résumé exécutif

| # | Catégorie | Intégration | Horizon |
|---|-----------|-------------|---------|
| C1 | Critique | Incrémenter la version à `1.1.0` | Immédiat |
| C2 | Critique | Retirer l'identifiant personnel de `config.py` | Immédiat |
| C3 | Critique | Corriger `data_source` écrite `"mock_api"` dans le cache | Immédiat |
| C4 | Critique | Clarifier ou supprimer `data_ingestion.py` | Immédiat |
| C5 | Critique | Vérifier `soilgrids.py` et son comportement réel | Immédiat |
| C6 | Critique | Ajouter des tests pour le connecteur CHIRPS | Immédiat |
| P1 | Stratégique | Activer Penman-Monteith dans `water_balance()` | v1.2.0 |
| P2 | Stratégique | Évaluer et améliorer le modèle de prévision de prix | v1.2.0 |
| P3 | Stratégique | Transport multimodal (fluvial) dans `logistics.py` | v2.0.0 |
| P4 | Stratégique | Connecteurs données béninoises (MAEP, INSAE) | v1.2.0 |
| P5 | Stratégique | Interface de visualisation ou notebook | v1.2.0 |
| P6 | Stratégique | Publication de métriques de performance | v1.1.1 |
| P7 | Stratégique | Feuille de route datée dans `ROADMAP.md` | Avant publication |
