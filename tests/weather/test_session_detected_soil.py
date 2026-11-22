"""Teste le choix du sol pour le bilan hydrique de la façade Weather."""

import pandas as pd

from kadi.weather import Weather


def test_sol_explicite_ne_remplace_pas_la_detection(monkeypatch):
    """Une demande ponctuelle ne modifie pas le sol des appels suivants."""
    from kadi.weather.hydrology import Hydrology

    weather = Weather(lat=9.0, lon=2.0)
    dates = pd.date_range("2026-01-01", periods=5)
    weather.loader.historical = pd.DataFrame({
        "precipitation": 0.0, "temperature_min": 22.0, "temperature_max": 32.0,
    }, index=dates)
    monkeypatch.setattr(weather, "_load_data", lambda **kwargs: None)
    monkeypatch.setattr(Hydrology, "_resolve_soil", lambda self, location: "ferrallitique")

    detected = weather.water_balance()
    assert weather.hydrology.soil_type == "ferrallitique"
    assert not weather.water_balance(soil_type="sableux").equals(detected)
    assert weather.hydrology.soil_type == "ferrallitique"
    pd.testing.assert_frame_equal(weather.water_balance(), detected)
