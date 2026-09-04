"""
Module kadi.weather

Ce module expose les fonctionnalités de climatologie agronomique
pour le package KadiPy, adaptées au contexte béninois.

Les anciens noms (WeatherData, RiskIndicators, WeatherSession) restent accessibles
via rétrocompatibilité mais sont dépréciés depuis la version 1.1.0.
"""

import warnings

from .session import Weather
from .location import Location
from .data import WeatherLoader
from .phenology import Phenology
from .hydrology import Hydrology
from .risk import Risk

# Noms publics officiels (v1.1.0+)
__all__ = [
    "Weather",
    "Location",
    "WeatherLoader",
    "Phenology",
    "Hydrology",
    "Risk",
]

# ----------------------------------------------------------------
# Rétrocompatibilité : anciens noms au niveau du package
# ----------------------------------------------------------------

_DEPRECATED = {
    "WeatherSession": ("Weather", Weather),
    "WeatherData":    ("WeatherLoader", WeatherLoader),
    "RiskIndicators": ("Risk", Risk),
}


def __getattr__(name: str):
    """
    Intercepte les anciens noms exportés depuis kadi.weather.

    Args:
        name (str): Nom du symbole demandé.

    Returns:
        object: La cible correspondant au nouveau nom.

    Raises:
        AttributeError: Si le nom n'est ni courant ni un ancien nom connu.
    """
    if name in _DEPRECATED:
        new_name, target = _DEPRECATED[name]
        warnings.warn(
            f"kadi.weather.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return target
    raise AttributeError(
        f"Le module 'kadi.weather' n'a pas d'attribut '{name}'."
    )
