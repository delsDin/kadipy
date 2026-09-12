"""
Tests du module hydrologique : bilan hydrique, ETo Hargreaves, ETo Penman-Monteith FAO-56.
"""

import pytest
from unittest.mock import patch
import pandas as pd

from kadi.weather.hydrology import Hydrology
from kadi.weather.location import Location
from kadi.exceptions import DataError


# ---------------------------------------------------------------------------
# Fixture commune
# ---------------------------------------------------------------------------

@pytest.fixture
def hydrology_setup():
    """Jeu de données minimal pour les tests hydrologiques (10 jours, zone Centre)."""
    location = Location(latitude=9.3041, longitude=2.0890)
    dates = pd.date_range(start='2026-06-01', periods=10)
    precip_data = pd.Series([10, 0, 5, 20, 0, 0, 0, 30, 10, 0], index=dates)
    temp_data = pd.DataFrame({
        'temperature_min': [22] * 10,
        'temperature_max': [32] * 10
    }, index=dates)
    return location, precip_data, temp_data


# ---------------------------------------------------------------------------
# Tests du bilan hydrique
# ---------------------------------------------------------------------------

@patch('kadi.weather.hydrology.Hydrology._resolve_soil')
def test_compute_water_balance(mock_resolve_soil, hydrology_setup):
    """Le bilan hydrique doit retourner un DataFrame avec toutes les colonnes attendues."""
    mock_resolve_soil.return_value = 'ferrugineux'
    location, precip_data, temp_data = hydrology_setup

    hydro = Hydrology(location, precip_data, temp_data)
    balance_df = hydro.water_balance()

    assert not balance_df.empty
    assert len(balance_df) == 10
    assert 'deficit_eau' in balance_df.columns
    assert 'et0' in balance_df.columns
    assert 'reserve_utile' in balance_df.columns
    assert 'stress_hydrique_index' in balance_df.columns


@patch('kadi.weather.hydrology.Hydrology._resolve_soil')
def test_insufficient_data(mock_resolve_soil, hydrology_setup):
    """Un bilan sur des données vides doit lever DataError."""
    mock_resolve_soil.return_value = 'ferrugineux'
    location, _, _ = hydrology_setup

    hydro = Hydrology(location, pd.Series(dtype=float), pd.DataFrame())
    with pytest.raises(DataError):
        hydro.water_balance()


# ---------------------------------------------------------------------------
# Tests de l'évapotranspiration Hargreaves
# ---------------------------------------------------------------------------

@patch('kadi.weather.hydrology.Hydrology._resolve_soil')
def test_et0_hargreaves_valeur_positive(mock_resolve_soil, hydrology_setup):
    """L'ETo Hargreaves doit toujours être positive ou nulle."""
    mock_resolve_soil.return_value = 'ferrugineux'
    location, precip_data, temp_data = hydrology_setup

    hydro = Hydrology(location, precip_data, temp_data)
    eto = hydro.et0_hargreaves(tmin=22.0, tmax=32.0, day_of_year=180)

    assert eto >= 0.0


# ---------------------------------------------------------------------------
# Tests de l'évapotranspiration Penman-Monteith FAO-56
# ---------------------------------------------------------------------------

@patch('kadi.weather.hydrology.Hydrology._resolve_soil')
def test_et0_penman_valeur_positive(mock_resolve_soil, hydrology_setup):
    """L'ETo Penman-Monteith doit toujours être positive ou nulle."""
    mock_resolve_soil.return_value = 'ferrugineux'
    location, precip_data, temp_data = hydrology_setup

    hydro = Hydrology(location, precip_data, temp_data)
    eto = hydro.et0_fao56_penman(
        tmin=22.0,
        tmax=32.0,
        humidity=70.0,
        wind_speed=2.0,
        solar_rad=20.0,
    )

    assert eto >= 0.0


@patch('kadi.weather.hydrology.Hydrology._resolve_soil')
def test_et0_penman_superieur_avec_vent(mock_resolve_soil, hydrology_setup):
    """Un vent plus fort doit augmenter l'évapotranspiration Penman-Monteith."""
    mock_resolve_soil.return_value = 'ferrugineux'
    location, precip_data, temp_data = hydrology_setup

    hydro = Hydrology(location, precip_data, temp_data)
    eto_vent_faible = hydro.et0_fao56_penman(tmin=22.0, tmax=32.0, humidity=70.0, wind_speed=1.0, solar_rad=20.0)
    eto_vent_fort = hydro.et0_fao56_penman(tmin=22.0, tmax=32.0, humidity=70.0, wind_speed=5.0, solar_rad=20.0)

    assert eto_vent_fort > eto_vent_faible


@patch('kadi.weather.hydrology.Hydrology._resolve_soil')
def test_et0_penman_plage_realiste_benin(mock_resolve_soil, hydrology_setup):
    """L'ETo Penman-Monteith sous le climat béninois doit se situer entre 2 et 10 mm/jour."""
    mock_resolve_soil.return_value = 'ferrugineux'
    location, precip_data, temp_data = hydrology_setup

    hydro = Hydrology(location, precip_data, temp_data)
    eto = hydro.et0_fao56_penman(tmin=24.0, tmax=34.0, humidity=65.0, wind_speed=2.5, solar_rad=22.0)

    assert 2.0 <= eto <= 10.0
