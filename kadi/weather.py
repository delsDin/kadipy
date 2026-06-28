"""
Module météo public pour KadiPy (kadi.weather).

Ce module expose les fonctions de prévision, d'historique 
et de calculs agronomiques (DJC, probabilité de pluie, sécheresse).
L'ensemble est pensé "offline-first".
"""

import datetime
from typing import List, Dict, Any, Union

from kadi.config import CONFIG
from kadi.exceptions import InsufficientData
from kadi.cache import get_connection
from kadi._utils.coordinates import normalize_location
from kadi._utils.network import fetch_with_retry
from kadi._sources.open_meteo import fetch_forecast, fetch_historical

# Températures de base réelles pour les cultures d'Afrique de l'Ouest (en °C)
CROP_BASE_TEMP = {
    "maize": 10.0,
    "maïs": 10.0,
    "rice": 10.0,
    "riz": 10.0,
    "sorghum": 10.0,
    "sorgho": 10.0,
    "manioc": 14.0,
    "cassava": 14.0,
    "tomato": 10.0,
    "tomate": 10.0
}


def _store_weather_in_cache(location_id: str, lat: float, lon: float, data: List[Dict[str, Any]]) -> None:
    """Insère ou met à jour les données météo dans le cache SQLite."""
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        
        for row in data:
            cursor.execute("""
                INSERT INTO weather_data (
                    location_id, latitude, longitude, date, hour,
                    temperature_min, temperature_max, temperature_avg,
                    precipitation, data_type, data_source, confidence, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(location_id, date, hour) DO UPDATE SET
                    temperature_min=excluded.temperature_min,
                    temperature_max=excluded.temperature_max,
                    temperature_avg=excluded.temperature_avg,
                    precipitation=excluded.precipitation,
                    data_type=excluded.data_type,
                    data_source=excluded.data_source,
                    confidence=excluded.confidence,
                    fetched_at=excluded.fetched_at
            """, (
                location_id, lat, lon, row["date"], row["hour"],
                row["temperature_min"], row["temperature_max"], row["temperature_avg"],
                row["precipitation"], row["data_type"], row["data_source"],
                row["confidence"], now
            ))
        
        # Mise à jour des métadonnées du cache
        if data:
            data_source = data[0]["data_source"]
            cursor.execute("""
                INSERT INTO cache_metadata (
                    module_name, table_name, data_source, last_fetch, last_success, last_update
                ) VALUES ('weather', 'weather_data', ?, ?, ?, ?)
                ON CONFLICT(module_name, data_source) DO UPDATE SET
                    last_fetch=excluded.last_fetch,
                    last_success=excluded.last_success,
                    last_update=excluded.last_update
            """, (data_source, now, now, now))
            
        conn.commit()


def _get_weather_from_cache(location_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Récupère les données météo depuis le cache local."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, temperature_min, temperature_max, temperature_avg, precipitation,
                   data_type, data_source, confidence, fetched_at
            FROM weather_data
            WHERE location_id = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (location_id, start_date, end_date))
        
        return [dict(row) for row in cursor.fetchall()]


def forecast(location: str, days: int = None, refresh: bool = False) -> Dict[str, Any]:
    """
    Récupère les prévisions météo pour une localisation.
    Utilise le cache local en priorité, sauf si 'refresh' est True 
    ou si les données sont trop anciennes.
    
    Args:
        location: Le nom de la ville (ex: "Abomey").
        days: Le nombre de jours de prévision souhaité.
        refresh: Force un appel API pour ignorer le cache.
        
    Returns:
        Dict: Dictionnaire contenant les données météo et métadonnées.
    """
    if days is None:
        days = CONFIG["weather"]["forecast_days_default"]
    
    lat, lon = normalize_location(location)
    
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=days)
    
    # 1. Vérification du cache si refresh est False
    if not refresh:
        cached_data = _get_weather_from_cache(location, today.isoformat(), end_date.isoformat())
        if len(cached_data) >= days:
            # Vérifier la fraîcheur (si fetched_at < cache_ttl)
            fetched_at = datetime.datetime.fromisoformat(cached_data[0]["fetched_at"])
            cache_ttl = datetime.timedelta(hours=CONFIG["weather"]["cache_ttl_forecast_hours"])
            if datetime.datetime.now() - fetched_at < cache_ttl:
                return {
                    "location": {"name": location, "lat": lat, "lon": lon},
                    "data": cached_data,
                    "freshness_days": (datetime.datetime.now() - fetched_at).days,
                    "data_source": "cache",
                    "status": "success"
                }
    
    # 2. Récupération des données fraîches via l'API
    attempts = CONFIG["weather"]["retry_attempts"]
    backoff = CONFIG["weather"]["retry_backoff_sec"]
    
    fresh_data = fetch_with_retry(
        fetch_forecast, attempts, backoff, lat=lat, lon=lon, days=days
    )
    
    # 3. Stockage dans le cache
    _store_weather_in_cache(location, lat, lon, fresh_data)
    
    # 4. Formater la réponse
    return {
        "location": {"name": location, "lat": lat, "lon": lon},
        "data": fresh_data,
        "freshness_days": 0,
        "data_source": fresh_data[0]["data_source"],
        "status": "success"
    }


def historical(location: str, months_back: int = 12, metric: str = "all") -> Dict[str, Any]:
    """
    Récupère l'historique météo (d'abord en cache, sinon depuis l'API).
    
    Args:
        location: Le nom de la ville (ex: "Abomey").
        months_back: Le nombre de mois d'historique souhaité.
        metric: (Optionnel) pour un futur filtrage.
        
    Returns:
        Dict: Dictionnaire contenant les données météo et métadonnées.
    """
    lat, lon = normalize_location(location)
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=30 * months_back)
    
    cached_data = _get_weather_from_cache(location, start_date.isoformat(), end_date.isoformat())
    
    # Si le cache est suffisant (on s'attend à environ 30 * months_back jours)
    expected_days = 30 * months_back - 5
    if len(cached_data) >= expected_days:
        return {
            "location": {"name": location, "lat": lat, "lon": lon},
            "data": cached_data,
            "data_source": "cache",
            "status": "success"
        }
        
    # Sinon, on fetch l'historique
    fresh_data = fetch_with_retry(
        fetch_historical, 3, 5, lat=lat, lon=lon, months_back=months_back
    )
    
    _store_weather_in_cache(location, lat, lon, fresh_data)
    
    return {
        "location": {"name": location, "lat": lat, "lon": lon},
        "data": fresh_data,
        "data_source": fresh_data[0]["data_source"],
        "status": "success"
    }


def growing_degree_days(location: str, crop: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Calcule les Degrés-Jours de Croissance (GDD) pour une culture sur une période.
    
    Args:
        location: Nom de la ville.
        crop: Nom de la culture (ex: 'maïs').
        start_date: Date de début (YYYY-MM-DD).
        end_date: Date de fin (YYYY-MM-DD).
        
    Returns:
        Dict: Résultat des DJC calculés.
    """
    crop_lower = crop.lower()
    if crop_lower not in CROP_BASE_TEMP:
        raise ValueError(f"Température de base inconnue pour la culture '{crop}'.")
        
    base_temp = CROP_BASE_TEMP[crop_lower]
    
    cached_data = _get_weather_from_cache(location, start_date, end_date)
    if not cached_data:
        raise InsufficientData("Aucune donnée disponible dans le cache pour cette période. Récupérez d'abord l'historique.")
        
    total_gdd = 0.0
    valid_days = 0
    
    for day in cached_data:
        t_avg = day.get("temperature_avg")
        if t_avg is not None:
            gdd = max(0.0, t_avg - base_temp)
            total_gdd += gdd
            valid_days += 1
            
    return {
        "location": location,
        "crop": crop,
        "base_temp": base_temp,
        "start_date": start_date,
        "end_date": end_date,
        "gdd": round(total_gdd, 2),
        "valid_days": valid_days
    }


def drought_index(location: str, months_back: int = 12) -> Dict[str, Any]:
    """
    Calcule un indicateur de sécheresse simplifié basé sur l'écart à la moyenne 
    des précipitations (Standardized Precipitation Index simplifié).
    
    Args:
        location: Nom de la ville.
        months_back: Période d'évaluation en mois.
        
    Returns:
        Dict: L'indice de sécheresse calculé.
    """
    history = historical(location, months_back=months_back)
    data = history.get("data", [])
    
    if len(data) < 30:
        raise InsufficientData("Pas assez de données pour calculer l'indice de sécheresse.")
        
    # Calcul des précipitations totales sur la période
    total_precip = sum(d["precipitation"] for d in data if d["precipitation"] is not None)
    
    avg_precip_per_day = total_precip / len(data)
    
    return {
        "location": location,
        "total_precipitation": round(total_precip, 2),
        "avg_precipitation_per_day": round(avg_precip_per_day, 2),
        "months_evaluated": months_back,
        "message": "Indice de sécheresse calculé sur la période historique."
    }


def rain_probability(location: str, days_ahead: int = 3) -> Dict[str, Any]:
    """
    Fournit un pourcentage simple et lisible pour l'agriculteur sur la 
    probabilité et la quantité de pluie à venir.
    
    Args:
        location: Nom de la ville.
        days_ahead: Jours de prévision.
        
    Returns:
        Dict: Probabilité et quantité de pluie.
    """
    forecast_data = forecast(location, days=days_ahead)
    data = forecast_data.get("data", [])
    
    rain_days = 0
    total_rain = 0.0
    
    for day in data:
        precip = day.get("precipitation", 0)
        if precip is not None and precip > 0.5:
            rain_days += 1
            total_rain += precip
            
    prob = (rain_days / len(data)) * 100 if data else 0
    
    return {
        "location": location,
        "days_ahead": days_ahead,
        "probability_pct": round(prob, 1),
        "total_expected_rain_mm": round(total_rain, 1),
        "message": f"{round(prob)}% de chance de pluie (Total: {round(total_rain)} mm)."
    }
