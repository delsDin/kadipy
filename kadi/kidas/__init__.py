# -*- coding: utf-8 -*-
"""
Package kidas — KadiPy Data Acquisition & Standardization.

Ce package est le coeur du traitement de données agricoles dans KadiPy.
Il expose des classes pour lire, nettoyer, valider, normaliser et mettre
en cache des données issues de fichiers CSV, Excel, JSON, NetCDF ou d'APIs.

Exemple d'utilisation rapide :
    >>> import kadi.kidas as kidas
    >>> df, report = kidas.load_and_clean('recolte_2024.csv')

Exemple avec pipeline personnalisé :
    >>> pipeline = kidas.DataPipeline()
    >>> df, report = (
    ...     pipeline
    ...     .load_data('recolte_2024.xlsx')
    ...     .add_cleaning_step('remove_duplicates')
    ...     .add_cleaning_step('handle_missing_values', strategy='mean')
    ...     .add_validation_step({'culture': 'str', 'rendement_kg': 'float'})
    ...     .add_normalization_step({'crops': 'culture'})
    ...     .execute(cache=True)
    ... )
"""

# --- Sources de données ---
from kadi.kidas.sources.csv_source import CSVDataSource
from kadi.kidas.sources.excel_source import ExcelDataSource
from kadi.kidas.sources.json_source import JSONDataSource
from kadi.kidas.sources.api_source import APIDataSource

# Import conditionnel : xarray est requis pour NetCDF
try:
    from kadi.kidas.sources.netcdf_source import NetCDFDataSource
except ImportError:
    NetCDFDataSource = None  # type: ignore[assignment]

# --- Classes de traitement ---
from kadi.kidas.cleaner import DataCleaner
from kadi.kidas.validator import DataValidator
from kadi.kidas.normalizer import DataNormalizer

# --- Infrastructure ---
from kadi.kidas.cache import DataCache
from kadi.kidas.pipeline import DataPipeline

# Version du module kidas
__version__ = "1.0.0"

# API publique exposée par le package
__all__ = [
    "CSVDataSource",
    "ExcelDataSource",
    "JSONDataSource",
    "NetCDFDataSource",
    "APIDataSource",
    "DataCleaner",
    "DataValidator",
    "DataNormalizer",
    "DataCache",
    "DataPipeline",
    "load_and_clean",
]


def load_and_clean(source: str, cache: bool = True):
    """Charge et nettoie automatiquement des données depuis une source.

    Fonction de haut niveau créant un DataPipeline pré-configuré avec
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
    pipeline = DataPipeline()
    return (
        pipeline
        .load_data(source)
        .add_cleaning_step("remove_duplicates")
        .add_cleaning_step("handle_missing_values", strategy="mean")
        .execute(cache=cache)
    )
