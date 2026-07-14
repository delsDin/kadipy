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

def test_bbox_reject_north():
    """Un point au nord du Bénin (latitude > 12.5) doit être rejeté."""
    with pytest.raises(LocationNotFound):
        Location(latitude=13.0, longitude=2.0, name="HorsBenin")

def test_bbox_reject_south():
    """Un point au sud de la BBox (latitude < 2.5) doit être rejeté."""
    with pytest.raises(LocationNotFound):
        Location(latitude=1.0, longitude=2.0, name="HorsBenin")

def test_bbox_reject_east():
    """Un point à l'est du Bénin (longitude > 4.0) doit être rejeté."""
    with pytest.raises(LocationNotFound):
        Location(latitude=8.0, longitude=5.0, name="HorsBenin")

def test_bbox_reject_west():
    """Un point à l'ouest de la BBox (longitude < -1.5) doit être rejeté."""
    with pytest.raises(LocationNotFound):
        Location(latitude=8.0, longitude=-2.0, name="HorsBenin")

def test_bbox_frontiere_valide():
    """Un point à la frontière de la BBox doit être accepté."""
    # Latitude limite nord (12.5)
    loc = Location(latitude=12.5, longitude=2.0, name="NordBenin")
    assert loc is not None

