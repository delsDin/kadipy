import pytest
import datetime
from unittest.mock import patch
from kadi.weather import (
    forecast,
    historical,
    growing_degree_days,
    rain_probability,
    drought_index
)
from kadi.exceptions import InsufficientData

@patch('kadi.weather._get_weather_from_cache')
@patch('kadi.weather.fetch_with_retry')
@patch('kadi.weather._store_weather_in_cache')
def test_forecast_uses_api_when_cache_empty(mock_store, mock_fetch, mock_cache):
    """Test que l'API est appelée lorsque le cache est vide."""
    mock_cache.return_value = []
    mock_fetch.return_value = [
        {"date": "2026-06-27", "data_source": "open-meteo", "confidence": 0.95}
    ]
    
    result = forecast("Cotonou", days=1, refresh=False)
    
    assert result["status"] == "success"
    assert result["data_source"] == "open-meteo"
    assert mock_fetch.called
    assert mock_store.called

@patch('kadi.weather._get_weather_from_cache')
@patch('kadi.weather.fetch_with_retry')
def test_forecast_uses_cache(mock_fetch, mock_cache):
    """Test que le cache est utilisé directement s'il est frais."""
    now = datetime.datetime.now()
    mock_cache.return_value = [
        {"date": "2026-06-27", "data_source": "open-meteo", "fetched_at": now.isoformat()}
    ]
    
    result = forecast("Cotonou", days=1, refresh=False)
    
    assert result["data_source"] == "cache"
    assert not mock_fetch.called

@patch('kadi.weather._get_weather_from_cache')
def test_growing_degree_days(mock_cache):
    """Test le calcul des degrés-jours de croissance."""
    mock_cache.return_value = [
        {"date": "2026-06-01", "temperature_avg": 25.0},
        {"date": "2026-06-02", "temperature_avg": 20.0},
    ]
    
    # Pour le maïs, la base est de 10°C
    # Jour 1: 25 - 10 = 15
    # Jour 2: 20 - 10 = 10
    # Total = 25 GDD
    result = growing_degree_days("Cotonou", "maïs", "2026-06-01", "2026-06-02")
    
    assert result["gdd"] == 25.0
    assert result["valid_days"] == 2

@patch('kadi.weather.forecast')
def test_rain_probability(mock_forecast):
    """Test la logique de risque de pluie."""
    mock_forecast.return_value = {
        "data": [
            {"precipitation": 12.0},  # Forte pluie
            {"precipitation": 0.0},   # Sec
            {"precipitation": 2.0}    # Pluie significative
        ]
    }
    
    result = rain_probability("Abomey", days_ahead=3)
    
    # Avec 1 forte pluie sur 3 jours, le risque est classé 'Fort'
    assert result["risk_level"] == "Fort"
    assert result["total_expected_rain_mm"] == 14.0
    assert "Risque de pluie fort" in result["message"]
