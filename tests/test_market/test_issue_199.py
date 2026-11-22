"""Vérifie les prix par contenant avec ou sans accent."""

import pytest

from kadi.market.pricing import Pricing


@pytest.mark.parametrize("unit", ["XOF/boîte", "XOF/boite"])
def test_conversion_boite_tomate(unit):
    """Les deux variantes utilisent le poids spécifique à la tomate."""
    pricing = Pricing()
    assert pricing.convert_unit(10_000, unit, "Tomato") == 1_000
    assert pricing.convert_unit(10_000, "XOF/sac", "Maize") == 100
