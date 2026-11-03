"""
Module de web scraping pour récupérer les prix des carburants au Bénin.

Ce script extrait les tarifs récents (Essence, Gazole / Diesel, Pétrole lampant)
depuis le site web GlobalPetrolPrices pour le Bénin, puis sauvegarde les données
dans le fichier de configuration config/fuel_prices.json.
"""

import json
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
    if headers is None:
        headers = DEFAULT_HEADERS

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
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
    soup = BeautifulSoup(html_content, "html.parser")

    # Recherche du tableau principal contenant les prix des carburants
    table = soup.find("table")
    if not table:
        return []

    results = []
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")

    for row in rows:
        name_cell = row.find("th")
        val_cells = row.find_all("td", class_="value")
        if not val_cells:
            val_cells = row.find_all("td")

        # Cas où le libellé du carburant est dans une balise td
        if not name_cell and val_cells and len(val_cells) >= 4:
            name_cell = val_cells[0]
            val_cells = val_cells[1:]

        # Vérification qu'il s'agit d'une ligne de données complète
        if name_cell and len(val_cells) >= 3:
            fuel_name = name_cell.text.strip()
            date_val = val_cells[0].text.strip()
            price_xof = val_cells[1].text.strip()
            price_usd = val_cells[2].text.strip()

            fuel_data = {
                "fuel": fuel_name,
                "date": date_val,
                "price_xof": price_xof,
                "price_usd": price_usd,
            }
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
    nettoyee = chaine.replace(",", "").replace(" ", "").strip()
    for unite in ["XOF", "USD", "FCFA", "CFA"]:
        nettoyee = nettoyee.replace(unite, "")

    try:
        return float(nettoyee)
    except ValueError:
        return None


def _extraire_date(chaine_date: str) -> str:
    """
    Normalise la date du relevé extraite du site au format ISO (YYYY-MM-DD).

    Prend en charge les formats fréquents de GlobalPetrolPrices :
    - '26.10.2026' (DD.MM.YYYY)
    - '26/10/2026' (DD/MM/YYYY)
    - '26-10-2026' (DD-MM-YYYY)
    - '2026-10-26' (YYYY-MM-DD)
    - 'Jun 2026' / 'October 2026'

    Args:
        chaine_date (str): Chaîne brute représentant la date.

    Returns:
        str: Date au format YYYY-MM-DD, ou chaîne brute nettoyée si non reconnue.
    """
    if not chaine_date or not chaine_date.strip():
        return date.today().isoformat()

    nettoyee = chaine_date.strip()
    formats = [
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%b %Y",
        "%B %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(nettoyee, fmt).date().isoformat()
        except ValueError:
            continue

    return nettoyee


def save_fuel_prices(
    prices: List[Dict[str, str]],
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> bool:
    """
    Transforme les données brutes du scraping et les sauvegarde dans fuel_prices.json.

    La structure JSON produite est normalisée pour être compatible avec les autres
    modules de KadiPy. Les clés de carburants sont standardisées grâce au dictionnaire
    FUEL_KEY_MAP.
    La clé `last_updated` est renseignée avec la date réelle du relevé issue du site
    (au format YYYY-MM-DD), évitant ainsi de mettre à jour artificiellement la date
    avec la date du jour si les prix n'ont pas changé.

    Args:
        prices (List[Dict[str, str]]): La liste brute issue de parse_fuel_prices().
        output_path (Path): Chemin vers le fichier JSON de destination.

    Returns:
        bool: True si la sauvegarde a réussi, False si aucun prix n'a été trouvé.
    """
    if not prices:
        print("Aucun prix à sauvegarder.")
        return False

    # Recherche de la date réelle du relevé parmi les carburants extraits
    date_releve = None
    for item in prices:
        raw_date = item.get("date")
        if raw_date:
            date_releve = _extraire_date(raw_date)
            break

    # Si aucune date n'a pu être extraite, on utilise la date du jour en repli
    date_maj = date_releve if date_releve else date.today().isoformat()

    # Chargement préalable du fichier existant si présent pour conserver
    # d'éventuelles métadonnées ou carburants non présents dans ce relevé
    donnees_existantes = {}
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as fichier:
                donnees_existantes = json.load(fichier).get("benin", {})
        except Exception:
            donnees_existantes = {}

    benin_data: Dict[str, object] = {
        "last_updated": date_maj,
        "source": URL_BENIN_FUEL,
        "currency": "XOF",
    }

    # Conservation des clés existantes par défaut
    for cle_existante, val_existante in donnees_existantes.items():
        if cle_existante not in benin_data:
            benin_data[cle_existante] = val_existante

    carburants_trouves = 0

    # Parcours de chaque carburant extrait pour le normaliser
    for item in prices:
        fuel_name_lower = item.get("fuel", "").lower()

        cle_json = None
        for nom_source, cle in FUEL_KEY_MAP.items():
            if nom_source in fuel_name_lower:
                cle_json = cle
                break

        if cle_json is None:
            continue

        valeur = _extraire_valeur_numerique(item.get("price_xof", ""))

        if valeur is not None:
            benin_data[cle_json] = int(round(valeur))
            carburants_trouves += 1

    if carburants_trouves == 0:
        print("Aucun prix valide n'a pu être extrait des données fournies.")
        return False

    donnees_finales = {"benin": benin_data}

    with open(output_path, "w", encoding="utf-8") as fichier:
        json.dump(donnees_finales, fichier, indent=4, ensure_ascii=False)

    print(f"Fichier mis à jour : {output_path} (date du relevé : {date_maj})")
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
    html = fetch_html_content(url)
    prices = parse_fuel_prices(html)
    return prices


def main():
    """
    Point d'entrée principal pour l'exécution directe du script.

    Scrape les prix des carburants depuis GlobalPetrolPrices, puis sauvegarde
    le résultat dans config/fuel_prices.json.
    """
    print("Récupération des prix des carburants au Bénin en cours...")

    try:
        data = get_benin_fuel_prices()

        print("\nRésultats bruts obtenus :")
        print(json.dumps(data, indent=4, ensure_ascii=False))

        succes = save_fuel_prices(data)

        if not succes:
            raise RuntimeError(
                "Aucun prix valide n'a pu être extrait ou enregistré."
            )

    except Exception as err:
        print(f"Une erreur s'est produite lors du scraping : {err}")
        raise


if __name__ == "__main__":
    main()