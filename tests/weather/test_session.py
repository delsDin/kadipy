import pytest
from unittest.mock import patch
import pandas as pd

from kadi.weather.session import WeatherSession

@pytest.fixture
def session():
    return WeatherSession(latitude=9.3041, longitude=2.0890, name="Abomey")

@patch('kadi.weather.data.WeatherData.fetch_forecast')
def test_forecast(mock_forecast, session):
    mock_forecast.return_value = pd.DataFrame({'precipitation': [0]*7})
    res = session.forecast(days=7)
    assert 'data' in res
    assert 'location' in res
    mock_forecast.assert_called_once_with(days=7)

@patch('kadi.weather.data.WeatherData.fetch_historical')
def test_historical(mock_historical, session):
    mock_historical.return_value = pd.DataFrame({'precipitation': [0]*30})
    res = session.historical(months_back=1)
    assert not res.empty
    mock_historical.assert_called_once_with(months_back=1)

@patch('kadi.weather.phenology.Phenology.onset')
@patch('kadi.weather.data.WeatherData.fetch_historical')
def test_onset(mock_historical, mock_onset, session):
    df = pd.DataFrame({
        'precipitation': [0]*100,
        'temperature_min': [22]*100,
        'temperature_max': [32]*100
    })
    mock_historical.return_value = df
    session.weather_data.historical_data = df
    mock_onset.return_value = {'onset_date': '2026-05-15'}
    
    res = session.onset()
    assert res['onset_date'] == '2026-05-15'

@patch('kadi.weather.phenology.Phenology.growing_degree_days')
@patch('kadi.weather.data.WeatherData.fetch_historical')
def test_growing_degree_days(mock_historical, mock_gdd, session):
    df = pd.DataFrame({
        'precipitation': [0]*30,
        'temperature_min': [22]*30,
        'temperature_max': [32]*30,
        'temperature_mean': [25]*30
    })
    mock_historical.return_value = df
    session.weather_data.historical_data = df
    mock_gdd.return_value = {'gdd_accumulated': 300}
    
    res = session.growing_degree_days(crop='maize', start_date='2026-05-01', end_date='2026-05-30')
    assert res['gdd_accumulated'] == 300

@patch('kadi.weather.risk.RiskIndicators.drought_index')
@patch('kadi.weather.data.WeatherData.fetch_forecast')
@patch('kadi.weather.data.WeatherData.fetch_historical')
def test_drought_index(mock_historical, mock_forecast, mock_drought, session):
    df_hist = pd.DataFrame({'precipitation': [0]*100})
    df_fore = pd.DataFrame({'precipitation': [0]*7})
    mock_historical.return_value = df_hist
    mock_forecast.return_value = df_fore
    session.weather_data.historical_data = df_hist
    session.weather_data.forecast_data = df_fore
    mock_drought.return_value = {'spi_3month': -1.5}
    
    res = session.drought_index(window_months=3)
    assert res['spi_3month'] == -1.5
