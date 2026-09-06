# -*- coding: utf-8 -*-
"""
Module kadi.io - Ingestion de données agricoles.

Ce module est le point d'entrée pour toutes les sources de données
supportées par KadiPy : fichiers locaux (CSV, Excel, JSON, NetCDF)
et APIs REST.

Ce module est entièrement nouveau (introduit en v1.2.0) : il n'expose
que les noms simplifiés et ne contient aucun alias de rétrocompatibilité.
Les anciens noms (CSVDataSource, ExcelDataSource, etc.) ne sont jamais
passés par ce module.

Exemples d'utilisation :

    >>> from kadi.io import CSVSource
    >>> df = CSVSource("recoltes_2024.csv").read()

    >>> from kadi.io import read_csv
    >>> df = read_csv("recoltes_2024.csv")
"""

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


def read_csv(filepath, **kwargs):
    """
    Lit un fichier CSV via CSVSource.

    Raccourci inspiré de pandas pour instancier et lire rapidement un CSV.

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

    Raccourci inspiré de pandas pour instancier et lire rapidement un fichier Excel.

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

    Raccourci inspiré de pandas pour instancier et lire rapidement un fichier JSON.

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

    Raccourci inspiré de pandas/xarray pour instancier et lire un fichier NetCDF.

    Args:
        filepath (str | Path): Chemin vers le fichier NetCDF.
        **kwargs: Paramètres additionnels transmis à NetCDFSource.

    Returns:
        xarray.Dataset | pandas.DataFrame: Contenu du fichier NetCDF.

    Raises:
        ImportError: Si xarray ou netCDF4 n'est pas disponible dans l'environnement.
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
]
