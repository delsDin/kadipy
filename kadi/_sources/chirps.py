"""
Connecteur pour CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data).
Permet de récupérer les données historiques de précipitation depuis un cache local.

Statut V1 : désactivé.
Le fichier CSV fourni (historical_rainfall_1981_2024.csv) est vide ou manquant.
Un filtrage spatial approprié des données CHIRPS nécessitera la transition vers
des fichiers NetCDF (.nc) dans la V2 du projet. En attendant, le système bascule
exclusivement sur l'historique d'Open-Meteo.
"""

import pandas as pd
from typing import Optional
import logging

# Journaliseur pour ce module
logger = logging.getLogger(__name__)


def fetch_historical_precipitation(lat: float, lon: float) -> Optional[pd.DataFrame]:
    """
    Récupère l'historique des précipitations pour un point donné depuis le cache CHIRPS.

    Cette fonction est désactivée pour la V1. Le fichier CSV global fourni est vide.
    Le filtrage spatial par coordonnées GPS nécessitera des fichiers NetCDF en V2.

    :param lat: Latitude du lieu (non utilisée en V1).
    :param lon: Longitude du lieu (non utilisée en V1).
    :return: Toujours None en V1. Retournera un DataFrame en V2.
    """
    # Désactivé pour V1 : fichier CSV global vide, transition vers NetCDF prévue en V2.
    logger.warning(
        "Connecteur CHIRPS désactivé (V1) : fichier de données vide. "
        "Le filtrage spatial des données NetCDF est prévu pour la V2. "
        "Les données de précipitation proviennent exclusivement d'Open-Meteo."
    )
    return None
