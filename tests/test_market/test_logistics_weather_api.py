"""Tests d'intégration de l'API météo dans la logistique."""

import warnings
from unittest.mock import MagicMock, create_autospec

from kadi.market.logistics import _rain_prob
from kadi.weather import Weather


def test_rain_prob_api_actuelle():
    """Préfère la méthode actuelle sans émettre d'avertissement."""
    weather = create_autospec(Weather, instance=True)
    weather.rain_prob.return_value = {"tomorrow": 0.9}
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert _rain_prob(weather) == 0.9
    weather.rain_prob.assert_called_once()
    weather.rain_probability.assert_not_called()


def test_rain_prob_api_historique():
    """Utilise la méthode historique lorsque la méthode actuelle manque."""
    weather = MagicMock(spec=["rain_probability"])
    weather.rain_probability.return_value = {"tomorrow": 0.7}
    assert _rain_prob(weather) == 0.7
    weather.rain_probability.assert_called_once()
