"""Vérifie les paramètres historiques du constructeur Advisor."""

import pytest

from kadi.market import Advisor


def test_constructeur_advisor_anciens_noms():
    """Les composants explicites restent prioritaires sur les anciens noms."""
    forecast, logistics, pricing = object(), object(), object()
    with pytest.warns(DeprecationWarning) as caught:
        advisor = Advisor(forecast=forecast, forecasting_module=object(),
                          logistics_module=logistics, pricing_module=pricing)
    assert len(caught) == 3
    assert (advisor.forecast, advisor.logistics, advisor.pricing) == (
        forecast, logistics, pricing,
    )
    with pytest.raises(TypeError, match="invalid"):
        Advisor(invalid=True)
