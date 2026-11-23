"""
Tests de WeatherLoader : récupération depuis l'API, le cache SQLite, et normalisation des données.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch

from kadi.weather.data import WeatherLoader, WeatherData
from kadi.weather.location import Location


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def location():
    """Localisation de test : Abomey (zone Centre, régime bimodal)."""
    return Location(latitude=9.3041, longitude=2.0890, name="Abomey")


@pytest.fixture
def df_forecast_7j():
    """DataFrame de prévisions météo sur 7 jours."""
    dates = pd.date_range(start='2026-06-29', periods=7)
    return pd.DataFrame({
        'date': dates,
        'temperature_min': [22.0] * 7,
        'temperature_max': [32.0] * 7,
        'temperature_mean': [27.0] * 7,
        'precipitation': [0.0] * 7,
        'humidity': [60.0] * 7,
    })


@pytest.fixture
def df_historique_30j():
    """DataFrame historique sur 30 jours."""
    dates = pd.date_range(start='2026-06-01', periods=30)
    return pd.DataFrame({
        'date': dates,
        'temperature_min': [22.0] * 30,
        'temperature_max': [32.0] * 30,
        'temperature_mean': [27.0] * 30,
        'precipitation': [5.0] * 30,
        'humidity': [70.0] * 30,
    })


# ---------------------------------------------------------------------------
# Tests de récupération des prévisions
# ---------------------------------------------------------------------------

@patch('kadi.weather.data.WeatherLoader._to_cache')
@patch('kadi.weather.data.WeatherLoader._fetch_forecast')
@patch('kadi.weather.data.WeatherLoader._from_cache')
def test_forecast_retourne_donnees(mock_cache, mock_fetch, mock_save, location, df_forecast_7j):
    """get_forecast() doit retourner un DataFrame non vide de 7 jours."""
    # Cache vide : force l'appel API
    mock_cache.return_value = pd.DataFrame()
    df = df_forecast_7j.set_index('date')
    mock_fetch.return_value = df

    weather = WeatherLoader(location)
    result = weather.get_forecast(days=7)

    assert not result.empty
    assert len(result) == 7
    mock_fetch.assert_called_once_with(days=7)


# ---------------------------------------------------------------------------
# Tests de récupération de l'historique
# ---------------------------------------------------------------------------

@patch('kadi.weather.data.WeatherLoader._to_cache')
@patch('kadi.weather.data.WeatherLoader._fetch_historical')
@patch('kadi.weather.data.WeatherLoader._from_cache')
def test_historical_retourne_donnees(mock_cache, mock_fetch, mock_save, location, df_historique_30j):
    """get_historical() doit retourner un DataFrame non vide de 30 jours."""
    mock_cache.return_value = pd.DataFrame()
    df = df_historique_30j.set_index('date')
    mock_fetch.return_value = df

    weather = WeatherLoader(location)
    result = weather.get_historical(months=1)

    assert not result.empty
    assert len(result) == 30
    # Le paramètre source='both' est la valeur par défaut depuis l'intégration CHIRPS
    mock_fetch.assert_called_once_with(days=30, source='both')


# ---------------------------------------------------------------------------
# Tests de la normalisation des données
# ---------------------------------------------------------------------------

def test_normalize_corrige_temperature_aberrante(location):
    """Les températures hors [-5, 55]°C doivent être interpolées."""
    weather = WeatherLoader(location)
    dates = pd.date_range(start='2026-06-01', periods=5)
    df = pd.DataFrame({
        'date': dates,
        # Jour 3 (index 2) : température aberrante à 99°C
        'temperature_min': [22.0, 22.0, 99.0, 22.0, 22.0],
        'temperature_max': [32.0, 32.0, 32.0, 32.0, 32.0],
        'precipitation': [0.0, 5.0, 3.0, 3.0, 0.0],
    })

    result = weather._normalize(df)

    # Après interpolation, la valeur aberrante doit être < 55
    assert result['temperature_min'].iloc[2] < 55.0


def test_normalize_corrige_precipitation_negative(location):
    """Les précipitations négatives doivent être remises à 0."""
    weather = WeatherLoader(location)
    dates = pd.date_range(start='2026-06-01', periods=3)
    df = pd.DataFrame({
        'date': dates,
        'temperature_min': [22.0, 22.0, 22.0],
        'temperature_max': [32.0, 32.0, 32.0],
        'precipitation': [5.0, -3.0, 0.0],   # -3 est physiquement impossible
    })

    result = weather._normalize(df)

    # Aucune précipitation ne doit être négative
    assert (result['precipitation'] >= 0.0).all()


def test_normalize_ajoute_data_quality(location):
    """La normalisation doit générer une colonne 'data_quality'."""
    weather = WeatherLoader(location)
    dates = pd.date_range(start='2026-06-01', periods=5)
    df = pd.DataFrame({
        'date': dates,
        'temperature_min': [22.0] * 5,
        'temperature_max': [32.0] * 5,
        'precipitation': [0.0] * 5,
    })

    result = weather._normalize(df)

    assert 'data_quality' in result.columns
    # Données complètes : qualité = 1.0
    assert (result['data_quality'] == 1.0).all()


def test_normalize_dataframe_vide_retourne_vide(location):
    """Un DataFrame vide en entrée doit être retourné vide sans exception."""
    weather = WeatherLoader(location)
    result = weather._normalize(pd.DataFrame())
    assert result.empty


def test_normalize_calcule_temperature_mean(location):
    """temperature_mean doit être calculée comme moyenne de min et max si absente."""
    weather = WeatherLoader(location)
    dates = pd.date_range(start='2026-06-01', periods=3)
    df = pd.DataFrame({
        'date': dates,
        'temperature_min': [20.0, 22.0, 24.0],
        'temperature_max': [30.0, 32.0, 34.0],
        'precipitation': [0.0, 0.0, 0.0],
    })

    result = weather._normalize(df)

    assert 'temperature_mean' in result.columns
    # Vérification du calcul : (20+30)/2 = 25
    assert result['temperature_mean'].iloc[0] == pytest.approx(25.0)


def test_alias_retrocompatibilite_weather_data(location):
    """L'ancien alias WeatherData doit pointer vers WeatherLoader."""
    assert WeatherData is WeatherLoader
    weather = WeatherData(location)
    assert isinstance(weather, WeatherLoader)


def test_cache_historique_isole_source_et_type(tmp_path, monkeypatch):
    """Le cache sépare les politiques de source historique ainsi que les prévisions."""
    import kadi.cache as cache_module
    import kadi.config as config_module

    db_path = tmp_path / "weather.db"
    monkeypatch.setattr(cache_module, "CACHE_DB", db_path)
    monkeypatch.setattr(config_module, "CACHE_DB", db_path)

    loc = Location(lat=10.0, lon=2.0, name="audit")
    loader = WeatherLoader(loc)

    hist_dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=30)
    df_chirps = pd.DataFrame(
        {
            "temperature_min": [20.0] * 30,
            "temperature_max": [30.0] * 30,
            "precipitation": [99.0] * 30,
            "data_source": ["chirps"] * 30,
        },
        index=hist_dates,
    )
    df_openmeteo = pd.DataFrame(
        {
            "temperature_min": [20.0] * 30,
            "temperature_max": [30.0] * 30,
            "precipitation": [2.0] * 30,
            "data_source": ["open-meteo-archive"] * 30,
        },
        index=hist_dates,
    )

    # Stockage en cache pour la source 'chirps'
    monkeypatch.setattr(loader, "_fetch_historical", lambda **kw: df_chirps)
    res_chirps = loader.get_historical(months=1, source="chirps")
    assert (res_chirps["precipitation"] == 99.0).all()

    # Une requête explicite avec source='openmeteo' ne doit pas relire le cache 'chirps'
    monkeypatch.setattr(loader, "_fetch_historical", lambda **kw: df_openmeteo)
    res_openmeteo = loader.get_historical(months=1, source="openmeteo")
    assert (res_openmeteo["precipitation"] == 2.0).all()

    # Le cache prévisionnel est également isolé du cache historique
    fore_dates = pd.date_range(start=pd.Timestamp.today().normalize(), periods=3)
    df_fore = pd.DataFrame(
        {
            "temperature_min": [22.0] * 3,
            "temperature_max": [32.0] * 3,
            "precipitation": [7.0] * 3,
        },
        index=fore_dates,
    )
    monkeypatch.setattr(loader, "_fetch_forecast", lambda **kw: df_fore)
    res_fore = loader.get_forecast(days=3)
    assert (res_fore["precipitation"] == 7.0).all()

    # Une relecture depuis le cache 'chirps' reste intacte sans réseau
    monkeypatch.setattr(
        loader,
        "_fetch_historical",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("Reseau non attendu")),
    )
    res_chirps_cache = loader.get_historical(months=1, source="chirps")
    assert (res_chirps_cache["precipitation"] == 99.0).all()
