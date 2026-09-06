# -*- coding: utf-8 -*-
"""
Package principal de KadiPy.

KadiPy est le "pandas" de l'agriculture africaine, facilitant le traitement
et l'analyse des données météorologiques, de marché et de récoltes locales
avec une approche "offline-first".

Ce module expose l'API publique de premier niveau. Les utilisateurs peuvent
importer directement depuis kadi sans connaître la structure interne :

    >>> import kadi
    >>> ws = kadi.Weather(lat=9.3, lon=2.1, name="Parakou")
    >>> mk = kadi.Market(lat=9.3, lon=2.1, location="Parakou")
    >>> df = kadi.read_csv("recoltes_2024.csv")

Accès aux sous-modules :

    >>> from kadi.weather import Weather, Location
    >>> from kadi.market import Pricing, Forecasting, Logistics
    >>> from kadi.kidas import Cleaner, Validator, Normalizer, Pipeline, Cache
    >>> from kadi.io import CSVSource, ExcelSource
"""

import logging
import warnings

# ------------------------------------------------------------------
# Version du package
# ------------------------------------------------------------------

__version__ = "1.2.0"

# ------------------------------------------------------------------
# Configuration du logger racine de KadiPy
#
# Tous les sous-modules utilisent logging.getLogger(__name__), ce qui
# crée des loggers de la forme "kadi.market.pricing", "kadi.weather.risk",
# etc. Ces loggers héritent automatiquement du niveau défini ici sur
# le logger racine "kadi". Il suffit donc de configurer ce seul logger
# pour contrôler l'ensemble de la bibliothèque.
# ------------------------------------------------------------------

# Logger racine du package (silence par défaut : WARNING)
_logger_kadi = logging.getLogger("kadi")
_logger_kadi.setLevel(logging.WARNING)

# Handler console minimal (affiché uniquement si aucun handler n'est
# configuré en amont dans l'application de l'utilisateur)
if not _logger_kadi.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    )
    _logger_kadi.addHandler(_handler)

# ------------------------------------------------------------------
# Imports publics de premier niveau
# ------------------------------------------------------------------

# Façade météo principale
from kadi.weather.session import Weather

# Façade marché principale
from kadi.market import Market

# Classes de traitement de données (KIDAS)
from kadi.kidas import (
    Cleaner,
    Validator,
    Normalizer,
    Cache,
    Pipeline,
)

# Classes sources d'ingestion et fonctions de lecture (module kadi.io)
from kadi.io import (
    Source,
    CSVSource,
    ExcelSource,
    JSONSource,
    APISource,
    read_csv,
    read_excel,
    read_json,
    read_netcdf,
    read_api,
)

# Import conditionnel : xarray requis pour NetCDF
try:
    from kadi.io import NetCDFSource
except ImportError:
    # Pas d'erreur : l'utilisateur sera informé à l'usage
    NetCDFSource = None  # type: ignore[assignment,misc]

# ------------------------------------------------------------------
# API publique officielle
# ------------------------------------------------------------------

__all__ = [
    # Version
    "__version__",
    # Utilitaires
    "set_verbosity",
    # Façades principales
    "Weather",
    "Market",
    # Traitement de données
    "Cleaner",
    "Validator",
    "Normalizer",
    "Cache",
    "Pipeline",
    # Sources d'ingestion
    "Source",
    "CSVSource",
    "ExcelSource",
    "JSONSource",
    "NetCDFSource",
    "APISource",
    # Fonctions de lecture rapide
    "read_csv",
    "read_excel",
    "read_json",
    "read_netcdf",
    "read_api",
]


# ------------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------------

def set_verbosity(level: str = "WARNING") -> None:
    """
    Configure le niveau de log pour tous les sous-modules de KadiPy.

    Cette fonction est le point d'entrée unique pour contrôler la
    verbosité de la bibliothèque. Elle s'applique au logger racine
    "kadi", dont héritent automatiquement tous les sous-loggers
    (kadi.market, kadi.weather, kadi.kidas, etc.).

    Args:
        level (str): Niveau de log souhaité. Valeurs acceptées :
            - "DEBUG"   : logs détaillés (requêtes API, calculs internes).
            - "INFO"    : messages d'état du pipeline.
            - "WARNING" : uniquement les avertissements (defaut).
            - "ERROR"   : uniquement les erreurs critiques.

    Raises:
        ValueError: Si le niveau fourni n'est pas reconnu par le module
            standard logging.

    Exemple:
        >>> import kadi
        >>> kadi.set_verbosity("DEBUG")   # Active les logs détaillés
        >>> kadi.set_verbosity("WARNING") # Remet en mode silencieux (défaut)
    """
    # Conversion du niveau texte en constante numérique logging
    niveau_numerique = getattr(logging, level.upper(), None)

    # Vérification que le niveau est valide
    if not isinstance(niveau_numerique, int):
        niveaux_valides = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        raise ValueError(
            f"Niveau de log invalide : '{level}'. "
            f"Valeurs acceptées : {niveaux_valides}"
        )

    # Application du niveau sur le logger racine du package
    _logger_kadi.setLevel(niveau_numerique)

    # Journalisation du changement (visible uniquement si le niveau
    # sélectionné est DEBUG ou INFO)
    _logger_kadi.info(
        "kadi : niveau de verbosité défini à '%s'.", level.upper()
    )


# ------------------------------------------------------------------
# Rétrocompatibilité : anciens noms accessibles depuis kadi
# (uniquement ici, pas dans kadi.io ni kadi.kidas.sources)
# ------------------------------------------------------------------

# Table des anciens symboles -> (nouveau nom, objet cible)
_DEPRECATED = {
    # Module market (Phase 6)
    "MarketSession":  ("Market",    lambda: Market),
    # Module weather (Phase 5)
    "WeatherSession": ("Weather",   lambda: Weather),
    # Module kidas - classes de traitement (Phase 3)
    "DataCleaner":    ("Cleaner",   lambda: Cleaner),
    "DataValidator":  ("Validator", lambda: Validator),
    "DataNormalizer": ("Normalizer", lambda: Normalizer),
    "DataCache":      ("Cache",     lambda: Cache),
    "DataPipeline":   ("Pipeline",  lambda: Pipeline),
    # Module kidas - sources de données (Phase 2)
    "DataSource":       ("Source",       lambda: Source),
    "CSVDataSource":    ("CSVSource",    lambda: CSVSource),
    "ExcelDataSource":  ("ExcelSource",  lambda: ExcelSource),
    "JSONDataSource":   ("JSONSource",   lambda: JSONSource),
    "NetCDFDataSource": ("NetCDFSource", lambda: NetCDFSource),
    "APIDataSource":    ("APISource",    lambda: APISource),
}


def __getattr__(name: str):
    """
    Intercepte les anciens noms importés depuis le package kadi.

    Permet la rétrocompatibilité complète pour les anciens noms de classes.
    Les anciens noms émettent un DeprecationWarning lors de l'accès.

    Args:
        name (str): Nom du symbole demandé dans ce package.

    Returns:
        object: La classe ou l'objet correspondant au nouveau nom.

    Raises:
        AttributeError: Si le nom n'existe ni dans l'API officielle ni dans _DEPRECATED.
    """
    # Contrôle de la présence du symbole dans la table des déprécations
    if name in _DEPRECATED:
        # Récupération du nouveau nom et du constructeur associé
        new_name, factory = _DEPRECATED[name]
        warnings.warn(
            f"kadi.{name} est obsolète et sera supprimé dans KadiPy v2.0. "
            f"Utilisez kadi.{new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return factory()

    # Erreur standard si le symbole est inexistant
    raise AttributeError(
        f"Le module 'kadi' n'a pas d'attribut '{name}'."
    )
