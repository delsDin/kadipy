"""
Connecteur pour SoilGrids.
Permet de récupérer les informations de sols (souvent via un cache local pour réduire la latence).
"""

import os
import json
import math
import logging

logger = logging.getLogger(__name__)

def fetch_soil_type(lat: float, lon: float, default_soil: str = "ferrugineux") -> str:
    """
    Détermine le type de sol depuis le cache local pré-téléchargé SoilGrids.
    
    Args:
        lat (float): Latitude.
        lon (float): Longitude.
        default_soil (str): Type de sol par défaut si introuvable.
        
    Returns:
        str: Le type de sol trouvé, ou la valeur par défaut.
    """
    cache_file = os.path.expanduser("~/.kadipy_cache/soilgrids_cache.json")
    
    if not os.path.exists(cache_file):
        logger.debug(f"Cache SoilGrids introuvable, utilisation du défaut: {default_soil}")
        return default_soil
        
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
            
        if not data:
            return default_soil
            
        closest_point = None
        min_dist = float('inf')
        
        for pt in data:
            dist = math.hypot(pt["lat"] - lat, pt["lon"] - lon)
            if dist < min_dist:
                min_dist = dist
                closest_point = pt
                
        if closest_point and "soil_type" in closest_point:
            return closest_point["soil_type"]
            
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du cache SoilGrids: {e}")
        
    return default_soil
