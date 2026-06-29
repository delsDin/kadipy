"""
Module kadi.weather

Ce module expose les fonctionnalités de climatologie agronomique
pour le package KadiPy, adaptées au contexte béninois.
"""

from .session import WeatherSession
from .location import Location
from .data import WeatherData
from .phenology import Phenology
from .hydrology import Hydrology
from .risk import RiskIndicators

__all__ = [
    'WeatherSession',
    'Location',
    'WeatherData',
    'Phenology',
    'Hydrology',
    'RiskIndicators'
]
