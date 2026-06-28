import pytest
import responses
from kadi._sources.open_meteo import fetch_forecast, fetch_historical
from kadi.exceptions import DataSourceError

@responses.activate
def test_fetch_forecast_success():
    """Test la récupération des prévisions avec une réponse mockée."""
    responses.add(
        responses.GET,
        "https://api.open-meteo.com/v1/forecast",
        json={
            "daily": {
                "time": ["2026-06-27", "2026-06-28"],
                "temperature_2m_max": [30.0, 31.0],
                "temperature_2m_min": [24.0, 25.0],
                "precipitation_sum": [5.0, 0.0]
            }
        },
        status=200
    )
    
    data = fetch_forecast(lat=6.36, lon=2.41, days=2)
    assert len(data) == 2
    assert data[0]["date"] == "2026-06-27"
    assert data[0]["temperature_max"] == 30.0
    assert data[0]["temperature_avg"] == 27.0  # (30+24)/2
    assert data[0]["precipitation"] == 5.0
    assert data[0]["data_source"] == "open-meteo"

@responses.activate
def test_fetch_forecast_failure():
    """Test la levée d'exception en cas d'erreur API."""
    responses.add(
        responses.GET,
        "https://api.open-meteo.com/v1/forecast",
        status=500
    )
    
    with pytest.raises(DataSourceError):
        fetch_forecast(lat=6.36, lon=2.41, days=2)
