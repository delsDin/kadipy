import pytest
from unittest.mock import patch
import pandas as pd

from kadi.weather.data import WeatherData
from kadi.weather.location import Location

@pytest.fixture
def location():
    return Location(latitude=9.3041, longitude=2.0890, name="Abomey")

@patch('kadi.weather.data.WeatherData._save_to_cache')
@patch('kadi.weather.data.WeatherData._fetch_forecast_data')
@patch('kadi.weather.data.WeatherData._get_from_cache')
def test_forecast_returns_data(mock_get_cache, mock_fetch, mock_save, location):
    mock_get_cache.return_value = pd.DataFrame()
    
    df = pd.DataFrame({
        'date': pd.date_range(start='2026-06-29', periods=7),
        'temperature_min': [22]*7,
        'temperature_max': [32]*7,
        'temperature_mean': [27]*7,
        'precipitation': [0]*7,
        'humidity': [60]*7
    })
    df.set_index('date', inplace=True)
    mock_fetch.return_value = df
    
    weather_data = WeatherData(location)
    result = weather_data.fetch_forecast(days=7)
    
    assert not result.empty
    assert len(result) == 7
    mock_fetch.assert_called_once_with(days=7)

@patch('kadi.weather.data.WeatherData._save_to_cache')
@patch('kadi.weather.data.WeatherData._fetch_historical_data')
@patch('kadi.weather.data.WeatherData._get_from_cache')
def test_historical_returns_data(mock_get_cache, mock_fetch, mock_save, location):
    mock_get_cache.return_value = pd.DataFrame()
    
    df = pd.DataFrame({
        'date': pd.date_range(start='2026-06-01', periods=30),
        'temperature_min': [22]*30,
        'temperature_max': [32]*30,
        'temperature_mean': [27]*30,
        'precipitation': [5]*30,
        'humidity': [70]*30
    })
    df.set_index('date', inplace=True)
    mock_fetch.return_value = df
    
    weather_data = WeatherData(location)
    result = weather_data.fetch_historical(months_back=1)
    
    assert not result.empty
    assert len(result) == 30
    mock_fetch.assert_called_once_with(days=30)
