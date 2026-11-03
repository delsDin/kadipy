"""
Tests unitaires pour le module config/scrap_fuel.py.

Ces tests vérifient les fonctions de récupération, d'analyse et de sauvegarde
des prix des carburants sans effectuer d'appels réseau réels.
"""

import json
from pathlib import Path

import pytest
import responses as responses_lib

# Import du module à tester (chemin résolu depuis la racine du projet)
from config.scrap_fuel import (
    URL_BENIN_FUEL,
    fetch_html_content,
    get_benin_fuel_prices,
    parse_fuel_prices,
    save_fuel_prices,
)

# Contenu HTML minimal simulant un tableau de prix valide
HTML_TABLEAU_VALIDE = """
<html>
<body>
  <table>
    <tbody>
      <tr>
        <th>Gasoline</th>
        <td class="value">Jun 2026</td>
        <td class="value">725 XOF</td>
        <td class="value">1.24 USD</td>
      </tr>
      <tr>
        <th>Diesel</th>
        <td class="value">Jun 2026</td>
        <td class="value">750 XOF</td>
        <td class="value">1.28 USD</td>
      </tr>
      <tr>
        <th>Kerosene</th>
        <td class="value">Jun 2026</td>
        <td class="value">600 XOF</td>
        <td class="value">1.03 USD</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""

# Contenu HTML vide (sans tableau)
HTML_SANS_TABLEAU = "<html><body><p>Aucune donnée disponible.</p></body></html>"


# --- Tests de la fonction fetch_html_content ---


@responses_lib.activate
def test_fetch_html_content_succes():
    """Vérifie que fetch_html_content retourne le HTML en cas de réponse 200."""
    # Simulation d'une réponse HTTP 200 avec un corps HTML factice
    responses_lib.add(
        responses_lib.GET,
        URL_BENIN_FUEL,
        body="<html><body>OK</body></html>",
        status=200,
    )

    # Appel de la fonction et vérification du résultat
    resultat = fetch_html_content(URL_BENIN_FUEL)

    assert "OK" in resultat


@responses_lib.activate
def test_fetch_html_content_erreur_404():
    """Vérifie que fetch_html_content lève une exception en cas d'erreur HTTP 404."""
    import requests

    # Simulation d'une réponse HTTP 404
    responses_lib.add(
        responses_lib.GET,
        URL_BENIN_FUEL,
        status=404,
    )

    # L'appel doit lever une exception HTTPError
    with pytest.raises(requests.exceptions.HTTPError):
        fetch_html_content(URL_BENIN_FUEL)


# --- Tests de la fonction parse_fuel_prices ---


def test_parse_fuel_prices_tableau_valide():
    """Vérifie que parse_fuel_prices extrait correctement les données d'un tableau valide."""
    # Passage d'un HTML factice avec trois lignes de données
    resultats = parse_fuel_prices(HTML_TABLEAU_VALIDE)

    # On attend exactement trois carburants extraits
    assert len(resultats) == 3

    # Vérification des clés présentes dans le premier dictionnaire retourné
    premier = resultats[0]
    assert "fuel" in premier
    assert "date" in premier
    assert "price_xof" in premier
    assert "price_usd" in premier

    # Vérification des valeurs extraites pour l'essence
    assert premier["fuel"] == "Gasoline"
    assert "725" in premier["price_xof"]


def test_parse_fuel_prices_sans_tableau():
    """Vérifie que parse_fuel_prices retourne une liste vide quand il n'y a pas de tableau."""
    # Passage d'un HTML sans tableau
    resultats = parse_fuel_prices(HTML_SANS_TABLEAU)

    # La liste de résultats doit être vide
    assert resultats == []


def test_parse_fuel_prices_inclut_petrole_lampant():
    """Vérifie que le pétrole lampant (Kerosene) est bien extrait du tableau."""
    resultats = parse_fuel_prices(HTML_TABLEAU_VALIDE)

    # Recherche du pétrole lampant dans les résultats
    noms = [r["fuel"].lower() for r in resultats]
    assert any("kerosene" in nom for nom in noms)


# --- Tests de la fonction save_fuel_prices ---


def test_save_fuel_prices_ecrit_json(tmp_path):
    """Vérifie que save_fuel_prices écrit correctement le fichier JSON."""
    # Données brutes simulées issues du scraping
    donnees_brutes = [
        {"fuel": "Gasoline", "date": "Jun 2026", "price_xof": "725 XOF", "price_usd": "1.24"},
        {"fuel": "Diesel", "date": "Jun 2026", "price_xof": "750 XOF", "price_usd": "1.28"},
        {"fuel": "Kerosene", "date": "Jun 2026", "price_xof": "600 XOF", "price_usd": "1.03"},
    ]

    # Chemin temporaire pour le fichier JSON de sortie
    chemin_sortie = tmp_path / "fuel_prices.json"

    # Appel de la fonction de sauvegarde
    succes = save_fuel_prices(donnees_brutes, output_path=chemin_sortie)

    # Vérification que la fonction retourne True
    assert succes is True

    # Vérification que le fichier a bien été créé
    assert chemin_sortie.exists()

    # Lecture et validation du contenu du fichier JSON
    with open(chemin_sortie, encoding="utf-8") as f:
        contenu = json.load(f)

    # La structure doit contenir la clé "benin"
    assert "benin" in contenu

    benin = contenu["benin"]

    # Vérification des trois carburants
    assert benin["essence"] == 725
    assert benin["gasoil"] == 750
    assert benin["petrole_lampant"] == 600

    # Vérification des métadonnées
    assert "last_updated" in benin
    assert "last_checked" in benin
    assert benin["currency"] == "XOF"
    assert "source" in benin


def test_save_fuel_prices_deux_dates(tmp_path):
    """Vérifie que la date du site et la date de vérification sont distinctes."""
    from datetime import date

    donnees_brutes = [
        {"fuel": "Gasoline prices", "date": "26.10.2026", "price_xof": "750", "price_usd": "1.282"},
        {"fuel": "Diesel prices", "date": "26.10.2026", "price_xof": "765", "price_usd": "1.308"},
    ]
    chemin_sortie = tmp_path / "fuel_prices.json"

    save_fuel_prices(donnees_brutes, output_path=chemin_sortie)

    with open(chemin_sortie, encoding="utf-8") as f:
        benin = json.load(f)["benin"]

    # La date du site est convertie au format ISO
    assert benin["last_updated"] == "2026-10-26"
    # La date de vérification correspond au jour de l'exécution
    assert benin["last_checked"] == date.today().isoformat()


def test_save_fuel_prices_date_source_non_standard(tmp_path):
    """Vérifie qu'une date au format inattendu est conservée telle quelle."""
    donnees_brutes = [
        {"fuel": "Gasoline", "date": "Jun 2026", "price_xof": "725 XOF", "price_usd": "1.24"},
    ]
    chemin_sortie = tmp_path / "fuel_prices.json"

    save_fuel_prices(donnees_brutes, output_path=chemin_sortie)

    with open(chemin_sortie, encoding="utf-8") as f:
        benin = json.load(f)["benin"]

    assert benin["last_updated"] == "Jun 2026"


def test_save_fuel_prices_liste_vide(tmp_path):
    """Vérifie que save_fuel_prices retourne False quand la liste est vide."""
    chemin_sortie = tmp_path / "fuel_prices.json"

    # Appel avec une liste vide
    succes = save_fuel_prices([], output_path=chemin_sortie)

    # La fonction doit retourner False sans créer de fichier
    assert succes is False
    assert not chemin_sortie.exists()


def test_save_fuel_prices_carburant_non_reconnu(tmp_path):
    """Vérifie que les carburants non reconnus sont ignorés sans bloquer la sauvegarde."""
    donnees_brutes = [
        # Carburant avec un nom inconnu
        {"fuel": "Aviation Fuel", "date": "Jun 2026", "price_xof": "900 XOF", "price_usd": "1.55"},
        # Carburant reconnu
        {"fuel": "Gasoline", "date": "Jun 2026", "price_xof": "725 XOF", "price_usd": "1.24"},
    ]

    chemin_sortie = tmp_path / "fuel_prices.json"
    succes = save_fuel_prices(donnees_brutes, output_path=chemin_sortie)

    # La sauvegarde doit réussir grâce à l'essence reconnue
    assert succes is True

    with open(chemin_sortie, encoding="utf-8") as f:
        contenu = json.load(f)

    # L'essence doit être présente
    assert contenu["benin"]["essence"] == 725

    # "Aviation Fuel" ne doit pas apparaître dans le JSON
    assert "aviation_fuel" not in contenu["benin"]
