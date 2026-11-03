"""
Module de web scraping pour récupérer les prix des carburants au Bénin.

Ce script extrait les tarifs récents (Essence, Gazole / Diesel, Pétrole lampant)
depuis le site web GlobalPetrolPrices pour le Bénin, puis sauvegarde les données
dans le fichier de configuration config/fuel_prices.json.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# URL de référence pour les prix des carburants au Bénin
URL_BENIN_FUEL = "https://www.globalpetrolprices.com/Benin/"

# Chemin par défaut vers le fichier de sortie JSON
# (résolu depuis la racine du projet, quel que soit le répertoire courant)
DEFAULT_OUTPUT_PATH = Path(__file__).parent / "fuel_prices.json"

# En-têtes HTTP pour simuler un navigateur web standard
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

# Correspondance entre les noms extraits du site et les clés JSON du projet
# Les noms sur le site peuvent varier légèrement selon la langue de la page
FUEL_KEY_MAP = {
    "gasoline": "essence",
    "essence": "essence",
    "diesel": "gasoil",
    "gazole": "gasoil",
    "gasoil": "gasoil",
    "kerosene": "petrole_lampant",
    "pétrole lampant": "petrole_lampant",
    "kerosene / lpk": "petrole_lampant",
}


def fetch_html_content(
    url: str = URL_BENIN_FUEL,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 10,
) -> str:
    """
    Télécharge le contenu HTML de la page web cible.

    Args:
        url (str): L'adresse web à télécharger. Par défaut, l'URL du Bénin.
        headers (Optional[Dict[str, str]]): En-têtes HTTP personnalisés.
        timeout (int): Délai d'attente maximal en secondes pour la requête.

    Returns:
        str: Le code source HTML de la page web.

    Raises:
        requests.RequestException: En cas d'erreur de connexion ou d'erreur HTTP.
    """
    # Utilisation des en-têtes par défaut si aucun en-tête n'est fourni
    if headers is None:
        headers = DEFAULT_HEADERS

    # Envoi de la requête HTTP GET pour récupérer le contenu de la page
    response = requests.get(url, headers=headers, timeout=timeout)

    # Vérification du statut HTTP de la réponse (exception si != 200)
    response.raise_for_status()

    # Retourne le contenu HTML sous forme de chaîne de caractères
    return response.text


def parse_fuel_prices(html_content: str) -> List[Dict[str, str]]:
    """
    Extrait les prix des carburants à partir du contenu HTML de la page.

    Args:
        html_content (str): Le contenu HTML téléchargé de la page web.

    Returns:
        List[Dict[str, str]]: Une liste de dictionnaires contenant pour chaque
        carburant son nom, la date du relevé, le prix en XOF et le prix en USD.
    """
    # Analyse du code HTML avec la bibliothèque BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Recherche du tableau principal contenant les prix des carburants
    table = soup.find("table")
    if not table:
        # Si aucun tableau n'est trouvé, retourner une liste vide
        return []

    # Liste pour stocker les données extraites
    results = []

    # Parcours des lignes du corps du tableau
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")

    for row in rows:
        # Extraction des cellules de la ligne
        name_cell = row.find("th")
        val_cells = row.find_all("td", class_="value")

        # Vérification qu'il s'agit d'une ligne de données complète
        if name_cell and len(val_cells) >= 3:
            # Nettoyage du nom du carburant
            fuel_name = name_cell.text.strip()

            # Extraction des trois valeurs (Date, Prix XOF, Prix USD)
            date_val = val_cells[0].text.strip()
            price_xof = val_cells[1].text.strip()
            price_usd = val_cells[2].text.strip()

            # Structuration des informations dans un dictionnaire
            fuel_data = {
                "fuel": fuel_name,
                "date": date_val,
                "price_xof": price_xof,
                "price_usd": price_usd,
            }

            # Ajout au tableau de résultats
            results.append(fuel_data)

    return results


def _extraire_valeur_numerique(chaine: str) -> Optional[float]:
    """
    Convertit une chaîne de prix en valeur numérique flottante.

    Supprime les espaces, les virgules et les unités textuelles (ex: "XOF", "USD")
    pour isoler le nombre.

    Args:
        chaine (str): La chaîne à convertir (exemple : "725 XOF" ou "1.25").

    Returns:
        Optional[float]: La valeur numérique extraite, ou None si la conversion échoue.
    """
    # Suppression des espaces et des caractères non numériques courants
    nettoyee = chaine.replace(",", "").replace(" ", "").strip()

    # Suppression des unités monétaires textuelles si présentes
    for unite in ["XOF", "USD", "FCFA", "CFA"]:
        nettoyee = nettoyee.replace(unite, "")

    try:
        # Conversion en nombre flottant
        return float(nettoyee)
    except ValueError:
        # Retourner None si la conversion est impossible
        return None


def _convertir_date_source(chaine: str) -> str:
    """
    Convertit la date du relevé affichée par le site au format ISO.

    Le site affiche les dates au format "JJ.MM.AAAA" (exemple : "26.10.2026").

    Args:
        chaine (str): La date telle qu'elle apparaît sur le site.

    Returns:
        str: La date au format ISO "AAAA-MM-JJ", ou la chaîne d'origine
        si elle ne correspond pas au format attendu.
    """
    try:
        return datetime.strptime(chaine.strip(), "%d.%m.%Y").date().isoformat()
    except ValueError:
        # On conserve la valeur brute plutôt que de perdre l'information
        return chaine.strip()


def save_fuel_prices(
    prices: List[Dict[str, str]],
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> bool:
    """
    Transforme les données brutes du scraping et les sauvegarde dans fuel_prices.json.

    La structure JSON produite est normalisée pour être compatible avec les autres
    modules de KadiPy. Les clés de carburants sont standardisées grâce au dictionnaire
    FUEL_KEY_MAP. Deux dates sont enregistrées :

    - `last_updated` : date du relevé publiée par le site, qui indique
      l'âge réel des prix ;
    - `last_checked` : date du jour, qui indique la dernière vérification.

    Args:
        prices (List[Dict[str, str]]): La liste brute issue de parse_fuel_prices().
        output_path (Path): Chemin vers le fichier JSON de destination.

    Returns:
        bool: True si la sauvegarde a réussi, False si aucun prix n'a été trouvé.
    """
    # Vérification que la liste de prix n'est pas vide
    if not prices:
        print("Aucun prix à sauvegarder.")
        return False

    # Construction de la structure JSON normalisée pour le Bénin
    # La date du site est la même pour tous les carburants d'un relevé,
    # on prend donc celle de la première ligne
    benin_data: Dict[str, object] = {
        "last_updated": _convertir_date_source(prices[0].get("date", "")),
        "last_checked": date.today().isoformat(),
        "source": URL_BENIN_FUEL,
        "currency": "XOF",
    }

    # Parcours de chaque carburant extrait pour le normaliser
    for item in prices:
        # Normalisation du nom du carburant en minuscules pour la correspondance
        fuel_name_lower = item.get("fuel", "").lower()

        # Recherche de la clé JSON correspondante dans le dictionnaire de correspondance
        cle_json = None
        for nom_source, cle in FUEL_KEY_MAP.items():
            if nom_source in fuel_name_lower:
                cle_json = cle
                break

        # Si le carburant n'est pas reconnu, on l'ignore
        if cle_json is None:
            continue

        # Extraction et conversion du prix en XOF en valeur numérique entière
        valeur = _extraire_valeur_numerique(item.get("price_xof", ""))

        if valeur is not None:
            # Stockage du prix arrondi à l'entier (les prix XOF sont toujours entiers)
            benin_data[cle_json] = int(round(valeur))

    # Assemblage de la structure finale avec le pays comme clé racine
    donnees_finales = {"benin": benin_data}

    # Écriture du fichier JSON avec indentation lisible
    with open(output_path, "w", encoding="utf-8") as fichier:
        json.dump(donnees_finales, fichier, indent=4, ensure_ascii=False)

    print(f"Fichier mis à jour : {output_path}")
    return True


def get_benin_fuel_prices(url: str = URL_BENIN_FUEL) -> List[Dict[str, str]]:
    """
    Fonction principale de scraping des prix des carburants au Bénin.

    Télécharge la page web puis extrait les données des carburants.

    Args:
        url (str): URL de la page web à parcourir.

    Returns:
        List[Dict[str, str]]: La liste des carburants avec leurs prix.
    """
    # Étape 1 : Téléchargement du contenu de la page HTML
    html = fetch_html_content(url)

    # Étape 2 : Extraction et structuration des prix des carburants
    prices = parse_fuel_prices(html)

    return prices


def main():
    """
    Point d'entrée principal pour l'exécution directe du script.

    Scrape les prix des carburants depuis GlobalPetrolPrices, puis sauvegarde
    le résultat dans config/fuel_prices.json.
    """
    # Information sur l'avancement de l'opération
    print("Récupération des prix des carburants au Bénin en cours...")

    try:
        # Lancement de la procédure de scraping
        data = get_benin_fuel_prices()

        # Affichage structuré du résultat dans la console (utile pour le débogage CI)
        print("\nRésultats bruts obtenus :")
        print(json.dumps(data, indent=4, ensure_ascii=False))

        # Sauvegarde des données dans le fichier de configuration JSON
        succes = save_fuel_prices(data)

        # Code de sortie non-zero si l'enregistrement a échoué (utile pour la CI)
        if not succes:
            raise RuntimeError(
                "Aucun prix valide n'a pu être extrait ou enregistré."
            )

    except Exception as err:
        # Gestion claire des erreurs potentielles lors de l'exécution
        print(f"Une erreur s'est produite lors du scraping : {err}")
        raise


if __name__ == "__main__":
    main()
