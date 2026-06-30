import pytest
from kadi.weather.location import Location
from kadi.exceptions import LocationNotFound

def test_init_valid_location():
    loc = Location(latitude=6.5, longitude=2.0, name="Cotonou")
    assert loc.latitude == 6.5
    assert loc.longitude == 2.0
    assert loc.name == "Cotonou"
    assert loc.zone == "Sud"
    assert loc.climate_regime == "bimodal"

def test_init_invalid_location():
    with pytest.raises(LocationNotFound):
        Location(latitude=20.0, longitude=2.0, name="Paris")

def test_detect_zone():
    loc_sud = Location(latitude=6.5, longitude=2.0)
    assert loc_sud.zone == "Sud"

    loc_centre = Location(latitude=8.0, longitude=2.0)
    assert loc_centre.zone == "Centre"

    loc_nord = Location(latitude=10.0, longitude=2.0)
    assert loc_nord.zone == "Nord"

def test_to_dict():
    loc = Location(latitude=6.5, longitude=2.0, name="TestLoc")
    d = loc.to_dict()
    assert d["name"] == "TestLoc"
    assert d["lat"] == 6.5
    assert d["zone"] == "Sud"
