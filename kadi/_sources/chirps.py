"""
Connecteur pour CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data).
Permet de récupérer les données historiques de précipitation (souvent depuis un cache local).
"""

import os
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def fetch_historical_precipitation(lat: float, lon: float) -> Optional[pd.DataFrame]:
    """
    Récupère l'historique des précipitations pour un point donné depuis le cache CHIRPS.
    
    Args:
        lat (float): Latitude du lieu.
        lon (float): Longitude du lieu.
        
    Returns:
        Optional[pd.DataFrame]: DataFrame avec la date en index et une colonne 'precipitation', 
                                ou None si le fichier est introuvable ou malformé.
    """
    # TODO: Ajouter le filtrage spatial (lat, lon) lorsque les vraies données NetCDF seront utilisées.
    # Pour l'instant on lit le CSV global.
    
    chirps_file = os.path.expanduser("~/.kadipy_cache/historical_rainfall_1981_2024.csv")
    
    if not os.path.exists(chirps_file):
        logger.warning(f"Fichier de cache CHIRPS introuvable: {chirps_file}")
        return None
        
    try:
        df = pd.read_csv(chirps_file)
        if df.empty or 'precipitation' not in df.columns or 'date' not in df.columns:
            logger.warning("Fichier CHIRPS invalide ou vide.")
            return None
            
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Retourne uniquement la colonne précipitation
        return df[['precipitation']]
        
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du cache CHIRPS: {e}")
        return None
