# -*- coding: utf-8 -*-
"""
Point d'entrée du sous-package kadi._sources.

Expose les clients et fonctions utilitaires utilisés par les modules
kadi.weather et kadi.market pour accéder aux sources de données externes.
"""

import warnings

from .chirps import fetch_historical_precipitation
from .exchange_client import ExchangeRateClient
from .open_meteo import fetch_forecast, fetch_historical
from .soilgrids import fetch_soil_type
from .wfp_client import WFPClient

__all__ = [
    'fetch_historical_precipitation',
    'ExchangeRateClient',
    'fetch_forecast',
    'fetch_historical',
    'fetch_soil_type',
    'WFPClient',
]

# Table des anciens noms -> (nouveau nom, cible)
# Utilisée par __getattr__ pour intercepter les imports des anciens noms.
_DEPRECATED = {
    "WFPDataBridgesClient": ("WFPClient", WFPClient),
}


def __getattr__(name: str):
    """
    Intercepte l'accès aux anciens noms pour émettre un avertissement.

    Args:
        name (str): Nom de l'attribut demandé dans ce module.

    Returns:
        type: La classe correspondant à l'ancien nom.

    Raises:
        AttributeError: Si le nom n'est ni courant ni un ancien nom connu.
    """
    if name in _DEPRECATED:
        # Récupère le nouveau nom et la cible
        new_name, target = _DEPRECATED[name]
        warnings.warn(
            f"kadi._sources.{name} est obsolète et sera supprimé "
            f"dans KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            # stacklevel=2 pointe vers la ligne de code de l'utilisateur,
            # pas vers cette fonction interne
            stacklevel=2,
        )
        return target
    raise AttributeError(
        f"Le module '{__name__}' n'a pas d'attribut '{name}'."
    )