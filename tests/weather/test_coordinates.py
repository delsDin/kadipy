import pytest
from kadi._utils.coordinates import normalize_location
from kadi.exceptions import LocationNotFound

def test_normalize_location_success():
    """Vérifie la résolution d'une ville existante."""
    lat, lon = normalize_location("Cotonou")
    assert lat == 6.36536
    assert lon == 2.41833
    
def test_normalize_location_case_insensitivity():
    """Vérifie que la résolution gère les espaces et la casse."""
    lat, lon = normalize_location("  cOtoNOU  ")
    assert lat == 6.36536
    assert lon == 2.41833

def test_normalize_location_not_found():
    """Vérifie le comportement avec une ville inconnue."""
    with pytest.raises(LocationNotFound):
        normalize_location("Paris")
