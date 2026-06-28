"""
Connecteur pour l'API Open-Meteo.

Permet de récupérer les prévisions et l'historique météo.
Gère le formatage des paramètres et l'extraction de la réponse JSON.
"""

import requests
import datetime
from typing import Dict, Any, List

from kadi.config import OPENMETEO_API_URL
from kadi.exceptions import DataSourceError


def fetch_forecast(lat: float, lon: float, days: int = 7) -> List[Dict[str, Any]]:
    """
    Récupère les prévisions météo journalières via Open-Meteo.
    
    Args:
        lat (float): Latitude du lieu.
        lon (float): Longitude du lieu.
        days (int): Nombre de jours à récupérer.
        
    Returns:
        List[Dict]: Une liste de dictionnaires représentant les données par jour.
        
    Raises:
        DataSourceError: En cas d'erreur de requête HTTP.
    """
    url = f"{OPENMETEO_API_URL}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": days,
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return _parse_daily_data(data, "forecast", "open-meteo", confidence=0.95)
    except requests.RequestException as e:
        raise DataSourceError(f"Erreur de connexion Open-Meteo (forecast): {e}")


def fetch_historical(lat: float, lon: float, months_back: int = 12) -> List[Dict[str, Any]]:
    """
    Récupère l'historique météo (Archive) via Open-Meteo.
    
    Args:
        lat (float): Latitude du lieu.
        lon (float): Longitude du lieu.
        months_back (int): Nombre de mois en arrière à récupérer.
        
    Returns:
        List[Dict]: Une liste de dictionnaires représentant les données passées par jour.
        
    Raises:
        DataSourceError: En cas d'erreur de requête HTTP.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    # Calcul des dates de début et fin
    end_date = datetime.date.today() - datetime.timedelta(days=2) # L'archive a environ 2 jours de délai
    start_date = end_date - datetime.timedelta(days=30 * months_back)
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        return _parse_daily_data(data, "historical", "open-meteo-archive", confidence=1.0)
    except requests.RequestException as e:
        raise DataSourceError(f"Erreur de connexion Open-Meteo (historical): {e}")


def _parse_daily_data(
    data: Dict[str, Any], 
    data_type: str, 
    source: str, 
    confidence: float
) -> List[Dict[str, Any]]:
    """
    Parse la structure JSON retournée par Open-Meteo (daily).
    
    Args:
        data: Le dictionnaire JSON renvoyé par l'API.
        data_type: Le type ('forecast' ou 'historical').
        source: Le nom de la source.
        confidence: L'indice de confiance.
        
    Returns:
        Une liste de lignes prêtes à être insérées dans le cache ou traitées.
    """
    daily = data.get("daily", {})
    if not daily:
        return []
        
    dates = daily.get("time", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    
    results = []
    
    for i, date_str in enumerate(dates):
        # On calcule la température moyenne si min et max sont disponibles
        max_val = t_max[i] if i < len(t_max) else None
        min_val = t_min[i] if i < len(t_min) else None
        
        avg_val = None
        if max_val is not None and min_val is not None:
            avg_val = round((max_val + min_val) / 2.0, 2)
            
        row = {
            "date": date_str,
            "hour": None,
            "temperature_min": min_val,
            "temperature_max": max_val,
            "temperature_avg": avg_val,
            "precipitation": precip[i] if i < len(precip) else None,
            "data_type": data_type,
            "data_source": source,
            "confidence": confidence
        }
        results.append(row)
        
    return results
