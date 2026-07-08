"""
Module définissant la hiérarchie des exceptions personnalisées de KadiPy.

Ces exceptions permettent de distinguer les erreurs liées aux API externes,
au cache local, à la validation des données, et à l'accès hors ligne.
Elles couvrent également les erreurs propres au module kidas (acquisition,
nettoyage, validation, normalisation, cache et pipeline).
"""

class KadiException(Exception):
    """Exception de base pour toutes les erreurs spécifiques à KadiPy."""
    pass


class DataSourceError(KadiException):
    """Exception levée lors de l'échec de récupération d'une API ou source."""
    pass


class CacheError(KadiException):
    """Exception levée en cas d'erreur liée à SQLite ou au cache local."""
    pass


class ValidationError(KadiException):
    """Exception levée lorsque la validation des données échoue."""
    pass


class OfflineError(KadiException):
    """Exception levée lorsqu'aucune donnée n'est disponible hors ligne."""
    pass


class LocationNotFound(ValidationError):
    """Exception levée lorsqu'une localisation (coordonnées ou lieu) est introuvable."""
    pass


class CropNotFound(ValidationError):
    """Exception levée lorsque le code de la culture est inconnu."""
    pass


class InsufficientData(ValidationError):
    """Exception levée lorsqu'il n'y a pas assez d'historique pour une opération."""
    pass


# =============================================================================
# Exceptions du module kidas
# =============================================================================

class KidasReadError(KadiException):
    """Exception levée lors de l'échec de lecture d'une source de données kidas.

    Peut être levée par CSVDataSource, ExcelDataSource, JSONDataSource,
    NetCDFDataSource ou APIDataSource lors d'un appel à read().
    """
    pass


class KidasWriteError(KadiException):
    """Exception levée lors de l'échec d'écriture vers une source kidas.

    Peut être levée par les méthodes write() des classes DataSource.
    """
    pass


class KidasConnectionError(KadiException):
    """Exception levée lorsqu'une source de données kidas est inaccessible.

    Couvre les fichiers introuvables, les endpoints API injoignables
    ou les fichiers NetCDF corrompus.
    """
    pass


class KidasCleaningError(KadiException):
    """Exception levée lors d'une erreur durant le nettoyage des données.

    Peut être levée par DataCleaner lorsqu'une stratégie de nettoyage
    est incompatible avec les données fournies.
    """
    pass


class KidasValidationError(KadiException):
    """Exception levée lorsque la validation d'un schéma ou d'une valeur échoue.

    Peut être levée par DataValidator lors de validate_schema(),
    validate_ranges() ou validate_coordinates().
    """
    pass


class KidasCacheError(KadiException):
    """Exception levée en cas d'erreur sur le cache SQLite dédié à kidas.

    Le cache kidas est stocké dans ~/.kadi/kidas_cache/ et est distinct
    du cache global KadiPy (kadi/cache.py).
    """
    pass


class KidasPipelineError(KadiException):
    """Exception levée lors d'une erreur d'orchestration dans DataPipeline.

    Peut être levée par execute() si une étape du pipeline est mal
    configurée ou si les données intermédiaires sont invalides.
    """
    pass