# Guide de contribution à KadiPy

Merci de l'intérêt que vous portez à KadiPy ! Ce guide explique comment
contribuer au projet de façon structurée et cohérente avec les standards
adoptés.

---

## Table des matières

1. [Code de conduite](#code-de-conduite)
2. [Environnement de développement](#environnement-de-développement)
3. [Workflow de contribution](#workflow-de-contribution)
4. [Standards de code](#standards-de-code)
5. [Tests](#tests)
6. [Documentation](#documentation)
7. [Signaler un bug](#signaler-un-bug)
8. [Proposer une fonctionnalité](#proposer-une-fonctionnalité)

---

## Code de conduite

Ce projet est publié sous un esprit de collaboration ouverte et
respectueuse. Toute communication, qu'elle soit dans les issues, les Pull
Requests ou les discussions, doit rester professionnelle et bienveillante.
Les contributions offensantes ou discriminatoires ne seront pas tolérées.

---

## Environnement de développement

### Prérequis

- Python 3.9 ou supérieur
- Git
- Un compte GitHub

### Mise en place

1. Commencez par créer un fork du dépôt sur GitHub en cliquant sur le
   bouton **Fork** en haut à droite de la page du projet.

2. Clonez votre fork sur votre machine locale :

   ```bash
   git clone https://github.com/delsDin/kadipy.git
   cd kadipy
   ```

3. Créez et activez un environnement virtuel :

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

4. Installez le package en mode éditable avec les dépendances de
   développement :

   ```bash
   pip install -e ".[dev]"
   ```

5. Vérifiez que tous les tests passent avant de commencer à travailler :

   ```bash
   pytest tests/ -v
   ```

---

## Workflow de contribution

Toute modification du code passe par une Pull Request. Voici les étapes
à suivre :

1. Créez une branche dédiée à votre modification (ne travaillez jamais
   directement sur `main`) :

   ```bash
   git checkout -b type/description-courte
   ```

   Exemples de noms de branches : `feat/prix-horaire`, `fix/bug-osrm`,
   `docs/guide-installation`.

2. Faites vos modifications, en commitant régulièrement avec des messages
   clairs (voir la section suivante).

3. Poussez votre branche vers votre fork :

   ```bash
   git push origin type/description-courte
   ```

4. Ouvrez une Pull Request vers la branche `main` du dépôt officiel.
   Donnez-lui un titre clair et remplissez la description avec :
   - L'objectif de la modification.
   - Les tests ajoutés ou modifiés.
   - Toute information utile pour la revue.

### Format des messages de commit

Nous utilisons la convention [Conventional Commits](https://www.conventionalcommits.org/).
Chaque message doit respecter ce format :

```
type(scope): description courte en français

Corps optionnel avec plus de détails sur le pourquoi du changement.
```

Les types acceptés sont :

| Type       | Usage                                                        |
|------------|--------------------------------------------------------------|
| `feat`     | Nouvelle fonctionnalité                                      |
| `fix`      | Correction d'un bug                                          |
| `docs`     | Modification de la documentation uniquement                  |
| `test`     | Ajout ou correction de tests                                 |
| `refactor` | Reformulation du code sans changement de comportement        |
| `build`    | Modification des fichiers de configuration ou de build       |
| `ci`       | Modification des workflows GitHub Actions                    |
| `chore`    | Maintenance générale (mise à jour de dépendances, etc.)      |

---

## Standards de code

### PEP 8

Tout le code doit respecter les règles de style PEP 8. Formatez votre
code avec `black` ou `ruff` avant de soumettre une Pull Request :

```bash
black kadi/ tests/
```

### Commentaires

Chaque instruction non triviale doit être commentée avec une explication
claire, en français, de son rôle. Évitez les commentaires redondants
qui se contentent de répéter ce que le code fait.

### Docstrings

Chaque fonction publique et chaque classe doivent avoir une docstring en
français respectant le format Google Style :

```python
def calculer_distance(origine: str, destination: str) -> float:
    """Calcule la distance routière entre deux marchés béninois.

    Utilise l'API OSRM (Project-OSRM) pour obtenir la distance
    réelle par la route. Lève une erreur réseau si l'API est
    inaccessible.

    Args:
        origine (str): Nom du marché d'origine (ex: "Parakou").
        destination (str): Nom du marché de destination (ex: "Cotonou").

    Returns:
        float: Distance en kilomètres.

    Raises:
        requests.Timeout: Si l'API OSRM ne répond pas.
        ValueError: Si l'un des noms de marché est inconnu.

    Exemple:
        >>> calculer_distance("Parakou", "Cotonou")
        408.5
    """
```

---

## Tests

Tout nouveau code doit être accompagné de tests unitaires. Nous utilisons
`pytest`.

- Les tests sont dans le dossier `tests/`, organisés par module.
- Les appels réseau doivent être mockés avec `responses` ou
  `requests-mock` pour garantir que les tests fonctionnent sans connexion.
- Visez une couverture des cas nominaux et des cas d'erreur.

Pour lancer les tests :

```bash
# Tous les tests
pytest tests/ -v

# Un module spécifique
pytest tests/test_market/ -v

# Avec affichage de la couverture de code
pytest tests/ --cov=kadi --cov-report=term-missing
```

---

## Documentation

La documentation est générée automatiquement à partir des docstrings
via `mkdocstrings`. Pour prévisualiser la documentation en local pendant
que vous travaillez :

```bash
mkdocs serve
```

Rendez-vous ensuite sur `http://127.0.0.1:8000/kadipy/`.

Si vous ajoutez un nouveau module ou une nouvelle méthode publique
importante, pensez à mettre à jour le fichier de documentation
correspondant dans `docs/`.

---

## Signaler un bug

Avant de créer une issue, vérifiez qu'un rapport similaire n'existe pas
déjà dans la liste des
[issues ouvertes](https://github.com/delsDin/kadipy/issues).

Pour signaler un bug, ouvrez une nouvelle issue en utilisant le modèle
"Bug report" et renseignez :

- La version de KadiPy concernée (`import kadi; print(kadi.__version__)`).
- La version de Python et du système d'exploitation.
- Les étapes exactes pour reproduire le problème.
- Le comportement attendu et le comportement observé.
- Le message d'erreur complet (traceback).

---

## Proposer une fonctionnalité

Nous accueillons volontiers les propositions de nouvelles fonctionnalités,
en particulier celles orientées vers les besoins du terrain agricole au
Bénin et en Afrique de l'Ouest.

Ouvrez une issue avec le modèle "Feature request" en expliquant :

- Le problème concret que la fonctionnalité résoudrait.
- La solution que vous envisagez.
- Les alternatives que vous avez considérées.

Une discussion préalable en issue est recommandée avant de commencer à
coder une fonctionnalité majeure, afin d'aligner la direction technique.

---

Merci pour votre contribution. Chaque amélioration compte pour rendre
KadiPy plus utile aux agriculteurs et aux acteurs du secteur agricole
béninois.
