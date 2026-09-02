"""
Module définissant la hiérarchie des exceptions personnalisées de KadiPy.

Chaque exception décrit une catégorie d'erreur précise : source de données,
cache, validation, accès hors ligne, nettoyage, pipeline. Les anciens noms
sont conservés comme alias pour ne pas casser les scripts existants.
"""


# Exception racine

class KadiError(Exception):
    """Exception de base pour toutes les erreurs spécifiques à KadiPy."""
    pass



# Exceptions générales

class SourceError(KadiError):
    """Erreur de récupération d'une API ou source de données externe."""
    pass


class CacheError(KadiError):
    """Erreur liée au cache SQLite local."""
    pass


class ValidationError(KadiError):
    """Erreur de validation des données ou d'un schéma."""
    pass


class OfflineError(KadiError):
    """Aucune donnée disponible en mode hors ligne."""
    pass


class LocationError(ValidationError):
    """Localisation (coordonnées ou nom de lieu) introuvable."""
    pass


class CropError(ValidationError):
    """Code ou nom de culture inconnu."""
    pass


class DataError(ValidationError):
    """Historique insuffisant pour l'opération demandée."""
    pass



# Exceptions du module kidas

class ReadError(KadiError):
    """Echec de lecture d'une source de données kidas.

    Peut être levée par CSVSource, ExcelSource, JSONSource,
    NetCDFSource ou APISource lors d'un appel à read().
    """
    pass


class WriteError(KadiError):
    """Echec d'écriture vers une source kidas.

    Peut être levée par les méthodes write() des classes Source.
    """
    pass


class ConnectError(KadiError):
    """Source de données kidas inaccessible.

    Couvre les fichiers introuvables, les endpoints API injoignables
    et les fichiers NetCDF corrompus.
    """
    pass


class CleanError(KadiError):
    """Erreur durant le nettoyage ou la normalisation des données.

    Peut être levée par Cleaner ou Normalizer lorsqu'une stratégie
    est incompatible avec les données fournies.
    """
    pass


class PipelineError(KadiError):
    """Erreur d'orchestration dans Pipeline.

    Peut être levée par run() si une étape est mal configurée
    ou si les données intermédiaires sont invalides.
    """
    pass



# Alias de compatibilite (anciens noms conserves)
# Ces alias permettent aux scripts existants de continuer a fonctionner
# sans modification immediate. Ils seront supprimes dans une version future.

# -- Exception racine
KadiException = KadiError

# -- Exceptions generales
DataSourceError = SourceError
LocationNotFound = LocationError
CropNotFound = CropError
InsufficientData = DataError

# -- Exceptions kidas
KidasReadError = ReadError
KidasWriteError = WriteError
KidasConnectionError = ConnectError
KidasCleaningError = CleanError
KidasValidationError = ValidationError
KidasCacheError = CacheError
KidasPipelineError = PipelineError