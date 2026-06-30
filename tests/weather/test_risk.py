import pytest
import pandas as pd

from kadi.weather.risk import RiskIndicators
from kadi.weather.location import Location
from kadi.exceptions import InsufficientData

@pytest.fixture
def risk_setup():
    location = Location(latitude=9.3041, longitude=2.0890)
    dates = pd.date_range(start='2026-01-01', periods=120)
    precip_data = pd.Series([2.0]*120, index=dates)
    return location, precip_data

def test_drought_index(risk_setup):
    location, precip_data = risk_setup
    risk = RiskIndicators(location, precip_data, pd.DataFrame())
    drought = risk.drought_index(window_months=3)
    
    assert 'spi_3month' in drought
    assert 'drought_severity' in drought

def test_drought_index_insufficient_data(risk_setup):
    location, _ = risk_setup
    dates_short = pd.date_range(start='2026-01-01', periods=20)
    precip_short = pd.Series([2.0]*20, index=dates_short)
    risk = RiskIndicators(location, precip_short, pd.DataFrame())
    
    with pytest.raises(InsufficientData):
        risk.drought_index(window_months=3)

def test_rain_probability(risk_setup):
    location, _ = risk_setup
    dates = pd.date_range(start='2026-06-01', periods=5)
    precip_forecast = pd.DataFrame({'precipitation': [0, 2.0, 15.0, 0, 1.0]}, index=dates)
    
    risk = RiskIndicators(location, pd.Series(dtype=float), precip_forecast)
    prob = risk.rain_probability(days_ahead=5)
    
    assert 'message' in prob
    assert 'recommendation' in prob
    assert 'tomorrow' in prob
