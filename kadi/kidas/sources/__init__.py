# -*- coding: utf-8 -*-
"""
Sous-package regroupant toutes les sources de données du module kidas.

Ce package expose les classes concrètes héritant de Source pour la lecture
et l'écriture de données dans différents formats agricoles (CSV, Excel,
JSON, NetCDF, API REST).

Les anciens noms (DataSource, CSVDataSource, etc.) sont interceptés par
__getattr__ : ils continuent de fonctionner mais émettent un
DeprecationWarning pour guider la migration vers les nouveaux noms.
"""

import warnings

# Export des nouvelles classes publiques
from .base import Source
from .csv_source import CSVSource
from .excel_source import ExcelSource
from .json_source import JSONSource
from .netcdf_source import NetCDFSource
from .api_source import APISource

# Liste officielle des symboles publics du sous-package
__all__ = [
    "Source",
    "CSVSource",
    "ExcelSource",
    "JSONSource",
    "NetCDFSource",
    "APISource",
]

# Table des anciens noms -> (nouveau nom, classe cible)
# Interceptés ici pour les imports du style :
#   from kadi.kidas.sources import CSVDataSource
_DEPRECATED_SOURCES = {
    "DataSource": ("Source", Source),
    "CSVDataSource": ("CSVSource", CSVSource),
    "ExcelDataSource": ("ExcelSource", ExcelSource),
    "JSONDataSource": ("JSONSource", JSONSource),
    "NetCDFDataSource": ("NetCDFSource", NetCDFSource),
    "APIDataSource": ("APISource", APISource),
}


def __getattr__(name: str):
    """Intercepte les anciens noms importés depuis kadi.kidas.sources.

    Permet à tout code utilisant les anciens noms de continuer de fonctionner
    tout en recevant un avertissement clair indiquant la migration à effectuer.

    Args:
        name (str): Nom du symbole demandé dans ce sous-package.

    Returns:
        type: La classe source correspondante.

    Raises:
        AttributeError: Si le nom demandé n'est ni un export courant
            ni un ancien nom connu.
    """
    if name in _DEPRECATED_SOURCES:
        # Récupère le nouveau nom et la classe cible
        new_name, cls = _DEPRECATED_SOURCES[name]
        warnings.warn(
            f"kadi.kidas.sources.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez kadi.kidas.sources.{new_name} à la place.",
            category=DeprecationWarning,
            # stacklevel=2 pointe vers la ligne de code de l'utilisateur,
            # pas vers cette fonction interne
            stacklevel=2,
        )
        return cls
    raise AttributeError(
        f"Le module 'kadi.kidas.sources' n'a pas d'attribut '{name}'."
    )
