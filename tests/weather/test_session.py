"""
Tests de la façade Weather : orchestration des composants du module kadi.weather.
"""

import pytest
from unittest.mock import patch
import pandas as pd

from kadi.exceptions import ValidationError
from kadi.weather.session import Weather, WeatherSession


@pytest.fixture
def weather():
    """Fixture retournant une instance de Weather initialisée pour Abomey."""
    return Weather(lat=9.3041, lon=2.0890, name="Abomey")


@patch('kadi.weather.data.WeatherLoader.get_forecast')
def test_forecast(mock_forecast, weather):
    """forecast() doit utiliser loader.get_forecast() et retourner la structure attendue."""
    mock_forecast.return_value = pd.DataFrame({'precipitation': [0] * 7})
    res = weather.forecast(days=7)
    assert 'data' in res
    assert 'location' in res
    mock_forecast.assert_called_once_with(days=7)


@patch('kadi.weather.data.WeatherLoader.get_historical')
def test_historical(mock_historical, weather):
    """historical() doit utiliser loader.get_historical() avec le nombre de mois spécifié."""
    mock_historical.return_value = pd.DataFrame({'precipitation': [0] * 30})
    res = weather.historical(months=1)
    assert not res.empty
    mock_historical.assert_called_once_with(months=1, source=None)


@patch('kadi.weather.phenology.Phenology.onset')
@patch('kadi.weather.data.WeatherLoader.get_historical')
def test_onset(mock_historical, mock_onset, weather):
    """onset() doit orchestrer phenology.onset() et retourner la date détectée."""
    df = pd.DataFrame({
        'precipitation': [0] * 100,
        'temperature_min': [22] * 100,
        'temperature_max': [32] * 100
    }, index=pd.date_range('2026-01-01', periods=100))
    mock_historical.return_value = df
    weather.loader.historical = df
    mock_onset.return_value = {'onset_date': '2026-05-15'}

    res = weather.onset()
    assert res['onset_date'] == '2026-05-15'


@patch('kadi.weather.phenology.Phenology.gdd')
@patch('kadi.weather.data.WeatherLoader.get_historical')
def test_gdd(mock_historical, mock_gdd, weather):
    """gdd() doit orchestrer phenology.gdd()."""
    df = pd.DataFrame({
        'precipitation': [0] * 30,
        'temperature_min': [22] * 30,
        'temperature_max': [32] * 30,
        'temperature_mean': [25] * 30
    }, index=pd.date_range('2026-05-01', periods=30))
    mock_historical.return_value = df
    weather.loader.historical = df
    mock_gdd.return_value = {'gdd_accumulated': 300}

    res = weather.gdd(crop='maize', start='2026-05-01', end='2026-05-30')
    assert res['gdd_accumulated'] == 300


@patch('kadi.weather.risk.Risk.drought')
@patch('kadi.weather.data.WeatherLoader.get_forecast')
@patch('kadi.weather.data.WeatherLoader.get_historical')
def test_drought(mock_historical, mock_forecast, mock_drought, weather):
    """drought() doit orchestrer risk.drought()."""
    df_hist = pd.DataFrame({'precipitation': [0] * 100}, index=pd.date_range('2026-01-01', periods=100))
    df_fore = pd.DataFrame({'precipitation': [0] * 7}, index=pd.date_range('2026-06-01', periods=7))
    mock_historical.return_value = df_hist
    mock_forecast.return_value = df_fore
    weather.loader.historical = df_hist
    weather.loader.forecast = df_fore
    mock_drought.return_value = {'spi_3month': -1.5}

    res = weather.drought(window=3)
    assert res['spi_3month'] == -1.5


def test_alias_retrocompatibilite_weather_session(weather):
    """L'ancien nom WeatherSession doit être disponible et pointer vers Weather."""
    assert WeatherSession is Weather
    session_old = WeatherSession(lat=9.3, lon=2.0)
    assert isinstance(session_old, Weather)


def test_historical_filtre_metric_inconnue_ou_absente(weather, caplog):
    """historical() lève ValidationError si metric est inconnue et avertit si humidity manque."""
    df_hist = pd.DataFrame(
        {
            "temperature_min": [20.0],
            "temperature_max": [33.0],
            "temperature_mean": [26.5],
            "precipitation": [1.0],
            "data_quality": [1.0],
        },
        index=pd.date_range("2026-01-01", periods=1),
    )

    with patch.object(weather.loader, "get_historical", return_value=df_hist):
        # Filtre valide par catégorie et par nom exact de colonne
        df_temp = weather.historical(metric="temperature", months=1)
        assert list(df_temp.columns) == [
            "temperature_min",
            "temperature_max",
            "temperature_mean",
        ]
        assert list(weather.historical(metric="temperature_max", months=1).columns) == [
            "temperature_max"
        ]

        # Métrique connue absente (humidity sur Open-Meteo) : avertissement + 0 colonne
        with caplog.at_level("WARNING"):
            df_hum = weather.historical(metric="humidity", months=1)
        assert list(df_hum.columns) == []
        assert df_hum.index.equals(df_hist.index)
        assert "humidity" in caplog.text

        # Métriques inconnues ou invalides -> ValidationError
        for invalid in ("wind", "precip", "", "   ", None):
            with pytest.raises(ValidationError):
                weather.historical(metric=invalid, months=1)
