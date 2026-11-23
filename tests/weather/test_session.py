"""
Tests de la façade Weather : orchestration des composants du module kadi.weather.
"""

import pytest
from unittest.mock import patch
import pandas as pd

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


def test_rechargement_donnees_invalide_composants_paresseux(monkeypatch):
    """historical() et forecast() doivent forcer la reconstruction des composants."""
    session = Weather(lat=10.0, lon=2.0, name="Parakou")
    dates = pd.date_range("2025-05-01", periods=2)

    def make_df(temp: float, rain: float = 0.0) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "temperature_min": [temp, temp],
                "temperature_max": [temp, temp],
                "precipitation": [rain, rain],
            },
            index=dates,
        )

    monkeypatch.setattr(
        "kadi.weather.hydrology.Hydrology._resolve_soil",
        lambda self, loc: "ferrugineux",
    )
    session.loader.historical = make_df(20.0)
    session.loader.forecast = make_df(20.0, rain=0.0)
    assert session.gdd("maize", dates[0], dates[-1])["gdd_accumulated"] == 20.0
    _ = session.water_balance()
    _ = session.rain_prob(days=1)
    assert session.phenology is not None
    assert session.hydrology is not None
    assert session.risk is not None

    # Rechargement historique : Phenology, Hydrology et Risk doivent être recréés
    def reload_hist(**kwargs):
        session.loader.historical = make_df(30.0)
        return session.loader.historical

    monkeypatch.setattr(session.loader, "get_historical", reload_hist)
    session.historical(months=1)
    assert session.phenology is None
    assert session.hydrology is None
    assert session.risk is None
    assert session.gdd("maize", dates[0], dates[-1])["gdd_accumulated"] == 40.0

    # Initialisation de Risk puis rechargement des prévisions
    _ = session.rain_prob(days=1)
    assert session.risk is not None

    def reload_fore(**kwargs):
        session.loader.forecast = make_df(25.0, rain=10.0)
        return session.loader.forecast

    monkeypatch.setattr(session.loader, "get_forecast", reload_fore)
    session.forecast(days=2)
    assert session.risk is None
