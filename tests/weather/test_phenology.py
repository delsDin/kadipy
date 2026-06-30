import pytest
import pandas as pd

from kadi.weather.phenology import Phenology
from kadi.weather.location import Location
from kadi.exceptions import InsufficientData

@pytest.fixture
def phenology_setup():
    location = Location(latitude=9.3041, longitude=2.0890) # Zone Nord
    dates = pd.date_range(start='2026-05-01', periods=40)
    precip_data = pd.Series([25] + [2]*39, index=dates)
    temp_df = pd.DataFrame({
        'temperature_min': [22]*40,
        'temperature_max': [32]*40,
        'temperature_mean': [27]*40
    }, index=dates)
    return location, precip_data, temp_df

def test_growing_degree_days(phenology_setup):
    location, precip_data, temp_df = phenology_setup
    pheno = Phenology(location, precip_data, temp_df)
    gdd = pheno.growing_degree_days('maize', '2026-05-01', '2026-05-10')
    
    assert gdd['gdd_accumulated'] == 170.0
    assert gdd['crop'] == 'maize'

def test_growing_degree_days_insufficient_data(phenology_setup):
    location, _, _ = phenology_setup
    empty_pheno = Phenology(location, pd.Series(dtype=float), pd.DataFrame())
    with pytest.raises(InsufficientData):
        empty_pheno.growing_degree_days('maize', '2026-05-01', '2026-05-10')

def test_onset_sivakumar(phenology_setup):
    location, precip_data, temp_df = phenology_setup
    pheno = Phenology(location, precip_data, temp_df)
    onset = pheno.onset()
    
    assert onset['onset_date'] is not None
