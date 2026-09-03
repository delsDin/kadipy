# -*- coding: utf-8 -*-
"""
Package kidas - KadiPy Data Acquisition & Standardization.

Ce package est le coeur du traitement de données agricoles dans KadiPy.
Il expose des classes pour lire, nettoyer, valider, normaliser et mettre
en cache des données issues de fichiers CSV, Excel, JSON, NetCDF ou d'APIs.

Exemple d'utilisation rapide :
    >>> import kadi.kidas as kidas
    >>> df, report = kidas.load_and_clean('recolte_2024.csv')

Exemple avec pipeline personnalisé :
    >>> pipeline = kidas.Pipeline()
    >>> df, report = (
    ...     pipeline
    ...     .add_source('recolte_2024.xlsx')
    ...     .add_step('drop_dupes')
    ...     .add_step('fill_missing', strategy='mean')
    ...     .add_step('check_schema', {'culture': 'str', 'rendement_kg': 'float'})
    ...     .run(cache=True)
    ... )
"""

import warnings

# --- Sources de données (nouveaux noms Phase 2) ---
from kadi.kidas.sources import (CSVSource,
    ExcelSource,
    JSONSource,
    APISource,
    Source)

# Import conditionnel : xarray est requis pour NetCDF
try:
    from kadi.kidas.sources import NetCDFSource
except ImportError:
    NetCDFSource = None  # type: ignore[assignment]

# --- Classes de traitement (Phase 3 : nouveaux noms) ---
from kadi.kidas.cleaner import Cleaner
from kadi.kidas.validator import Validator
from kadi.kidas.normalizer import Normalizer

# --- Infrastructure (Phase 3 : nouveaux noms) ---
from kadi.kidas.cache import Cache
from kadi.kidas.pipeline import Pipeline

# Version du module kidas
__version__ = "1.1.0"

# API publique exposée par le package
__all__ = [
    "Source",
    "CSVSource",
    "ExcelSource",
    "JSONSource",
    "NetCDFSource",
    "APISource",
    "Cleaner",
    "Validator",
    "Normalizer",
    "Cache",
    "Pipeline",
    "load_clean",
    "load_and_clean"
]


def load_clean(source: str, cache: bool = True):
    """Charge et nettoie automatiquement des données depuis une source.

    Fonction de haut niveau créant un Pipeline pré-configuré avec
    des étapes de nettoyage standard : suppression des doublons et
    imputation des valeurs manquantes par la moyenne.

    Args:
        source (str): Chemin vers le fichier de données ou URL d'une API.
            Formats supportés : CSV, Excel, JSON, NetCDF, API REST.
        cache (bool): Si True, utilise le cache SQLite kidas pour éviter
            de recharger une source déjà traitée. Par défaut True.

    Returns:
        tuple[pd.DataFrame, dict]: Tuple contenant :
            - Le DataFrame chargé et nettoyé.
            - Le rapport complet du pipeline.

    Exemple:
        >>> import kadi.kidas as kidas
        >>> df, report = kidas.load_and_clean('recoltes_2024.csv')
        >>> print(f"{len(df)} lignes chargées, score qualité : "
        ...       f"{report.get('quality_score', {}).get('overall', 'N/A')}")
    """
    # Création et exécution d'un pipeline standard
    pipeline = Pipeline()
    return (
        pipeline
        .add_source(source)
        .add_step("drop_dupes")
        .add_step("fill_missing", strategy="mean")
        .run(cache=cache)
    )


# Table des anciens noms -> (nouveau nom, référence)
# Intercepte les imports du style :
#   from kadi.kidas import CSVDataSource
#   from kadi.kidas import DataCleaner
_DEPRECATED_KIDAS = {
    # Sources (Phase 2)
    "DataSource":      ("Source",      lambda: Source),
    "CSVDataSource":   ("CSVSource",   lambda: CSVSource),
    "ExcelDataSource": ("ExcelSource", lambda: ExcelSource),
    "JSONDataSource":  ("JSONSource",  lambda: JSONSource),
    "NetCDFDataSource":("NetCDFSource",lambda: NetCDFSource),
    "APIDataSource":   ("APISource",   lambda: APISource),
    # Classes de traitement (Phase 3)
    "DataCleaner":     ("Cleaner",     lambda: Cleaner),
    "DataValidator":   ("Validator",   lambda: Validator),
    "DataNormalizer":  ("Normalizer",  lambda: Normalizer),
    "DataCache":       ("Cache",       lambda: Cache),
    "DataPipeline":    ("Pipeline",    lambda: Pipeline),
    "load_and_clean":  ("load_clean",  lambda: load_clean)
}


def __getattr__(name: str):
    """Intercepte les anciens noms importés depuis kadi.kidas.

    Permet la rétrocompatibilité complète pour les imports du style :
    ``from kadi.kidas import CSVDataSource``.

    Args:
        name (str): Nom du symbole demandé dans ce package.

    Returns:
        type: La classe source correspondante.

    Raises:
        AttributeError: Si le nom demandé n'est ni un export courant
            ni un ancien nom connu.
    """
    if name in _DEPRECATED_KIDAS:
        # Récupère le nouveau nom et la factory
        new_name, factory = _DEPRECATED_KIDAS[name]
        warnings.warn(
            f"kadi.kidas.{name} est obsolète et sera supprimé dans KadiPy v2.0. "
            f"Utilisez kadi.kidas.{new_name} à la place.",
            category=DeprecationWarning,
            # stacklevel=2 pointe vers la ligne de code de l'utilisateur
            stacklevel=2,
        )
        return factory()
    raise AttributeError(
        f"Le module 'kadi.kidas' n'a pas d'attribut '{name}'."
    )
