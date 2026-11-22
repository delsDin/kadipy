"""Vérifie la normalisation des cultures dans les coefficients FAO."""

import pytest

from kadi.exceptions import CropError
from kadi.weather.hydrology import Hydrology


def test_coefficient_culture_normalisee():
    """Les variations de casse et d'espacement préservent le coefficient."""
    hydro = Hydrology.__new__(Hydrology)
    assert hydro.crop_kc(" Maize ", "mid") == hydro.crop_kc("maize", "mid")
    assert hydro.crop_kc("MANIOC", "mid") == hydro.crop_kc("cassava", "mid")
    with pytest.raises(CropError):
        hydro.crop_kc(None, "mid")
