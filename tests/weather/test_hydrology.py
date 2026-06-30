import pytest
from unittest.mock import patch
import pandas as pd

from kadi.weather.hydrology import Hydrology
from kadi.weather.location import Location
from kadi.exceptions import InsufficientData

@pytest.fixture
def hydrology_setup():
    location = Location(latitude=9.3041, longitude=2.0890)
    dates = pd.date_range(start='2026-06-01', periods=10)
    precip_data = pd.Series([10, 0, 5, 20, 0, 0, 0, 30, 10, 0], index=dates)
    temp_data = pd.DataFrame({
        'temperature_min': [22]*10,
        'temperature_max': [32]*10
    }, index=dates)
    return location, precip_data, temp_data

@patch('kadi.weather.hydrology.Hydrology._resolve_soil_type_from_cache')
def test_compute_water_balance(mock_resolve_soil, hydrology_setup):
    mock_resolve_soil.return_value = 'ferrugineux'
    location, precip_data, temp_data = hydrology_setup
    
    hydro = Hydrology(location, precip_data, temp_data)
    balance_df = hydro.compute_water_balance()
    
    assert not balance_df.empty
    assert len(balance_df) == 10
    assert 'deficit_eau' in balance_df.columns
    assert 'et0' in balance_df.columns
    assert 'reserve_utile' in balance_df.columns

@patch('kadi.weather.hydrology.Hydrology._resolve_soil_type_from_cache')
def test_insufficient_data(mock_resolve_soil, hydrology_setup):
    mock_resolve_soil.return_value = 'ferrugineux'
    location, _, _ = hydrology_setup
    
    hydro = Hydrology(location, pd.Series(dtype=float), pd.DataFrame())
    with pytest.raises(InsufficientData):
        hydro.compute_water_balance()
