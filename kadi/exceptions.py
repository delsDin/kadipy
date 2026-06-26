"""
Module définissant la hiérarchie des exceptions personnalisées de KadiPy.

Ces exceptions permettent de distinguer les erreurs liées aux API externes,
au cache local, à la validation des données, et à l'accès hors ligne.
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
