"""
Module définissant la hiérarchie des exceptions personnalisées de KadiPy.

Chaque exception décrit une catégorie d'erreur précise : source de données,
cache, validation, accès hors ligne, nettoyage, pipeline.

Les anciens noms sont gérés via __getattr__ : ils continuent de fonctionner
mais émettent un DeprecationWarning pour encourager la migration vers les
nouveaux noms. Ils seront supprimés dans KadiPy v2.0.
"""

import warnings


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


# Table des anciens noms -> (nouveau nom, classe cible)
# Utilisée par __getattr__ pour intercepter les imports d'anciens noms.
_DEPRECATED = {
    "KadiException":      ("KadiError",       KadiError),
    "DataSourceError":    ("SourceError",      SourceError),
    "LocationNotFound":   ("LocationError",    LocationError),
    "CropNotFound":       ("CropError",        CropError),
    "InsufficientData":   ("DataError",        DataError),
    "KidasReadError":     ("ReadError",        ReadError),
    "KidasWriteError":    ("WriteError",       WriteError),
    "KidasConnectionError": ("ConnectError",   ConnectError),
    "KidasCleaningError": ("CleanError",       CleanError),
    "KidasValidationError": ("ValidationError", ValidationError),
    "KidasCacheError":    ("CacheError",       CacheError),
    "KidasPipelineError": ("PipelineError",    PipelineError),
}


def __getattr__(name: str):
    """Intercepte l'accès aux anciens noms d'exceptions pour émettre un avertissement.

    Paramètres
    ----------
    name : str
        Nom de l'attribut demandé dans ce module.

    Retourne
    --------
    type
        La classe exception correspondant à l'ancien nom.

    Lève
    ----
    AttributeError
        Si le nom demandé n'est ni un symbole courant ni un ancien nom connu.
    """
    if name in _DEPRECATED:
        # Récupère le nouveau nom et la classe cible
        new_name, cls = _DEPRECATED[name]
        warnings.warn(
            f"kadi.exceptions.{name} est obsolète et sera supprimé dans KadiPy v2.0. "
            f"Utilisez kadi.exceptions.{new_name} à la place.",
            category=DeprecationWarning,
            # stacklevel=2 pointe vers la ligne de code de l'utilisateur,
            # pas vers cette fonction interne
            stacklevel=2,
        )
        return cls
    raise AttributeError(
        f"Le module 'kadi.exceptions' n'a pas d'attribut '{name}'."
    )