"""Vérifie la sélection de l'API de prix WFP."""

import warnings
from unittest.mock import create_autospec

import pandas as pd

from kadi._sources.wfp_client import WFPClient
from kadi.market.pricing import Pricing


def test_pricing_appelle_api_wfp_actuelle():
    """Le client moderne est utilisé sans avertissement de dépréciation."""
    client = create_autospec(WFPClient, instance=True)
    client.prices.return_value = pd.DataFrame({"price": [200.]})
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = Pricing(wfp=client).fetch("maize", "cotonou")
    client.prices.assert_called_once()
    assert result["price"].tolist() == [200.]
