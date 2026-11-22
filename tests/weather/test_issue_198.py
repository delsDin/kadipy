"""Couvre les matrices de Markov à états manquants."""

import pandas as pd
import pytest

from kadi.weather.location import Location
from kadi.weather.risk import Risk


@pytest.mark.parametrize("rain,expected", [
    ([5, 5], (0., 0., 0., 1.)),
    ([0, 0], (1., 0., 0., 0.)),
    ([5], (0., 0., 0., 0.)),
])
def test_markov_etats_manquants(rain, expected):
    """Les états absents donnent des probabilités nulles."""
    risk = Risk(Location(lat=9.3, lon=2.), pd.Series(rain), pd.DataFrame())
    values = tuple(risk.markov().values())
    assert values == expected
    assert all(type(value) is float for value in values)
