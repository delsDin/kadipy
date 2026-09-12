# -*- coding: utf-8 -*-
"""
Module kadi.io - Ingestion et exportation de données agricoles.

Ce module est le point d'entrée pour toutes les sources de données
supportées par KadiPy : fichiers locaux (CSV, Excel, JSON, NetCDF)
et APIs REST.

Il expose :
- Les classes de sources concrètes (`CSVSource`, `ExcelSource`, etc.)
- Les fonctions de lecture raccourcies (`read_csv`, `read_excel`, etc.)
- Les fonctions d'écriture raccourcies (`write_csv`, `write_excel`, etc.)
- Les fonctions génériques avec détection automatique du format (`write`, `info`, `ping`)

Exemples d'utilisation :

    >>> from kadi.io import read_csv, write_csv
    >>> df = read_csv("recoltes_2024.csv")
    >>> write_csv(df, "recoltes_copie.csv")

    >>> import kadi.io as io
    >>> io.write(df, "donnees.json")
    >>> meta = io.info("recoltes_2024.csv")
    >>> ok = io.ping("recoltes_2024.csv")
"""

import os

# Import de la classe de base abstraite
from kadi.kidas.sources.base import Source

# Import des classes concrètes par format
from kadi.kidas.sources.csv_source import CSVSource
from kadi.kidas.sources.excel_source import ExcelSource
from kadi.kidas.sources.json_source import JSONSource
from kadi.kidas.sources.api_source import APISource

# Import conditionnel : xarray est requis pour la lecture NetCDF
try:
    from kadi.kidas.sources.netcdf_source import NetCDFSource
except ImportError:
    # xarray ou netCDF4 non installé : NetCDFSource reste None
    NetCDFSource = None  # type: ignore[assignment,misc]


# ------------------------------------------------------------------
# Fonctions de lecture raccourcies (read_*)
# ------------------------------------------------------------------

def read_csv(filepath, **kwargs):
    """
    Lit un fichier CSV via CSVSource.

    Args:
        filepath (str | Path): Chemin vers le fichier CSV.
        **kwargs: Paramètres additionnels transmis à CSVSource.

    Returns:
        pandas.DataFrame: Contenu du fichier CSV sous forme de DataFrame.
    """
    # Instanciation de la source CSV et lecture des données
    return CSVSource(filepath, **kwargs).read()


def read_excel(filepath, **kwargs):
    """
    Lit un fichier Excel via ExcelSource.

    Args:
        filepath (str | Path): Chemin vers le fichier Excel.
        **kwargs: Paramètres additionnels transmis à ExcelSource.

    Returns:
        pandas.DataFrame: Contenu du fichier Excel sous forme de DataFrame.
    """
    # Instanciation de la source Excel et lecture des données
    return ExcelSource(filepath, **kwargs).read()


def read_json(filepath, **kwargs):
    """
    Lit un fichier JSON via JSONSource.

    Args:
        filepath (str | Path): Chemin vers le fichier JSON.
        **kwargs: Paramètres additionnels transmis à JSONSource.

    Returns:
        pandas.DataFrame: Contenu du fichier JSON sous forme de DataFrame.
    """
    # Instanciation de la source JSON et lecture des données
    return JSONSource(filepath, **kwargs).read()


def read_netcdf(filepath, **kwargs):
    """
    Lit un fichier NetCDF via NetCDFSource.

    Args:
        filepath (str | Path): Chemin vers le fichier NetCDF.
        **kwargs: Paramètres additionnels transmis à NetCDFSource.

    Returns:
        xarray.Dataset | pandas.DataFrame: Contenu du fichier NetCDF.

    Raises:
        ImportError: Si xarray ou netCDF4 n'est pas disponible.
    """
    # Vérification de la présence du module NetCDFSource
    if NetCDFSource is None:
        raise ImportError(
            "Le support NetCDF nécessite l'installation des dépendances xarray et netCDF4."
        )
    # Instanciation de la source NetCDF et lecture des données
    return NetCDFSource(filepath, **kwargs).read()


def read_api(url: str, params: dict = None, **kwargs):
    """
    Lit des données depuis une API REST via APISource.

    Raccourci de haut niveau pour exécuter une requête GET vers une API.

    Args:
        url (str): URL de l'API.
        params (dict, optional): Paramètres de requête HTTP.
        **kwargs: Paramètres additionnels transmis à APISource.

    Returns:
        pandas.DataFrame: Données renvoyées par l'API sous forme de DataFrame.
    """
    # Instanciation de la source API et lecture des données
    source = APISource(url, **kwargs)
    return source.read(params or {})


# ------------------------------------------------------------------
# Fonctions d'écriture raccourcies (write_*)
# ------------------------------------------------------------------

def write_csv(data, filepath: str, **kwargs) -> bool:
    """
    Écrit un DataFrame dans un fichier CSV via CSVSource.

    Args:
        data (pandas.DataFrame): Les données à exporter.
        filepath (str): Chemin du fichier CSV de destination.
        **kwargs: Paramètres additionnels transmis à CSVSource.write().

    Returns:
        bool: True si l'écriture est réussie.
    """
    # Instanciation de la source CSV et écriture des données
    return CSVSource(filepath, **kwargs).write(data)


def write_excel(data, filepath: str, **kwargs) -> bool:
    """
    Écrit un DataFrame dans un fichier Excel via ExcelSource.

    Args:
        data (pandas.DataFrame): Les données à exporter.
        filepath (str): Chemin du fichier Excel de destination.
        **kwargs: Paramètres additionnels transmis à ExcelSource.write().

    Returns:
        bool: True si l'écriture est réussie.
    """
    # Instanciation de la source Excel et écriture des données
    return ExcelSource(filepath, **kwargs).write(data)


def write_json(data, filepath: str, **kwargs) -> bool:
    """
    Écrit un DataFrame dans un fichier JSON via JSONSource.

    Args:
        data (pandas.DataFrame): Les données à exporter.
        filepath (str): Chemin du fichier JSON de destination.
        **kwargs: Paramètres additionnels transmis à JSONSource.write().

    Returns:
        bool: True si l'écriture est réussie.
    """
    # Instanciation de la source JSON et écriture des données
    return JSONSource(filepath, **kwargs).write(data)


def write_netcdf(data, filepath: str, **kwargs) -> bool:
    """
    Écrit des données dans un fichier NetCDF via NetCDFSource.

    Args:
        data (pandas.DataFrame | xarray.Dataset): Les données à exporter.
        filepath (str): Chemin du fichier NetCDF de destination.
        **kwargs: Paramètres additionnels transmis à NetCDFSource.write().

    Returns:
        bool: True si l'écriture est réussie.

    Raises:
        ImportError: Si xarray ou netCDF4 n'est pas disponible.
    """
    # Vérification du module NetCDFSource
    if NetCDFSource is None:
        raise ImportError(
            "Le support NetCDF nécessite l'installation des dépendances xarray et netCDF4."
        )
    # Instanciation de la source NetCDF et écriture des données
    return NetCDFSource(filepath, **kwargs).write(data)


def write_api(data, url: str, **kwargs) -> bool:
    """
    Écrit des données vers une API REST via APISource.

    Args:
        data (pandas.DataFrame): Les données à envoyer.
        url (str): URL de l'endpoint API.
        **kwargs: Paramètres additionnels transmis à APISource.write().

    Returns:
        bool: True si l'envoi s'est déroulé avec succès.
    """
    # Instanciation de la source API et envoi des données
    return APISource(url, **kwargs).write(data)


# ------------------------------------------------------------------
# Fonctions génériques avec détection automatique du format
# ------------------------------------------------------------------

def _detect_source(filepath_or_url: str, **kwargs) -> Source:
    """
    Détermine la classe Source appropriée selon l'extension du fichier ou l'URL.

    Args:
        filepath_or_url (str): Chemin du fichier local ou URL de l'API REST.
        **kwargs: Arguments optionnels transmis à la classe Source.

    Returns:
        Source: Instance de la sous-classe de Source correspondante.

    Raises:
        ValueError: Si le format ne peut pas être déduit automatiquement.
    """
    # Détection des requêtes vers une API HTTP/HTTPS
    if isinstance(filepath_or_url, str) and filepath_or_url.startswith(("http://", "https://")):
        return APISource(filepath_or_url, **kwargs)

    # Extraction de l'extension de fichier en minuscules
    path_str = str(filepath_or_url)
    _, ext = os.path.splitext(path_str.lower())

    # Association de l'extension à la classe Source correspondante
    if ext == ".csv":
        return CSVSource(path_str, **kwargs)
    elif ext in (".xlsx", ".xls"):
        return ExcelSource(path_str, **kwargs)
    elif ext == ".json":
        return JSONSource(path_str, **kwargs)
    elif ext in (".nc", ".netcdf"):
        if NetCDFSource is None:
            raise ImportError(
                "Le support NetCDF nécessite l'installation des dépendances xarray et netCDF4."
            )
        return NetCDFSource(path_str, **kwargs)

    # Exception levée si le format est inconnu
    raise ValueError(
        f"Impossible de déterminer automatiquement la source pour '{filepath_or_url}'. "
        "Utilisez une classe Source spécifique (CSVSource, ExcelSource, etc.)."
    )


def write(data, filepath_or_url: str, **kwargs) -> bool:
    """
    Écrit des données dans une source en détectant automatiquement son format.

    Args:
        data (pandas.DataFrame): Les données à exporter.
        filepath_or_url (str): Chemin du fichier ou URL de l'API REST.
        **kwargs: Paramètres additionnels transmis à la source.

    Returns:
        bool: True si l'écriture est réussie.
    """
    # Détection automatique de la source et exécution de l'écriture
    source = _detect_source(filepath_or_url, **kwargs)
    return source.write(data)


def info(filepath_or_url: str, **kwargs) -> dict:
    """
    Obtient les métadonnées d'une source en détectant automatiquement son format.

    Args:
        filepath_or_url (str): Chemin du fichier ou URL de l'API REST.
        **kwargs: Paramètres additionnels transmis à la source.

    Returns:
        dict: Dictionnaire de métadonnées décrivant la source.
    """
    # Détection automatique de la source et récupération des métadonnées
    source = _detect_source(filepath_or_url, **kwargs)
    return source.info()


def ping(filepath_or_url: str, **kwargs) -> bool:
    """
    Vérifie l'accessibilité d'une source de données en détectant son format.

    Args:
        filepath_or_url (str): Chemin du fichier local ou URL de l'API REST.
        **kwargs: Paramètres additionnels transmis à la source.

    Returns:
        bool: True si la source est accessible et fonctionnelle.
    """
    # Détection automatique de la source et contrôle d'accès
    source = _detect_source(filepath_or_url, **kwargs)
    return source.ping()


# Liste officielle des symboles publics du module kadi.io
__all__ = [
    "Source",
    "CSVSource",
    "ExcelSource",
    "JSONSource",
    "NetCDFSource",
    "APISource",
    "read_csv",
    "read_excel",
    "read_json",
    "read_netcdf",
    "read_api",
    "write_csv",
    "write_excel",
    "write_json",
    "write_netcdf",
    "write_api",
    "write",
    "info",
    "ping",
]
