"""Tests de propagation du statut simulé vers la prévision."""

import pandas as pd
import pytest

from kadi.market import Market
from kadi.market.forecasting import Forecasting


def test_market_preserve_statut_simule():
    """La façade conserve les indicateurs et la confiance de simulation."""
    result = Market(9.3, 2.3, "Parakou", sim=True).predict("maize")
    assert result["is_simulated"] is True
    assert result["sim"] is True
    assert result["confidence_score"] == pytest.approx(0.1)


@pytest.mark.parametrize("marker, value", [("sim", True), ("source", "simulated")])
def test_forecasting_reconnait_statut_historique(marker, value):
    """Un seul marqueur historique suffit à signaler la simulation."""
    hist = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=90),
        "price": [200 + i for i in range(90)],
        marker: value,
    })
    result = Forecasting().predict(crop="maize", market="parakou", hist=hist)
    assert result["is_simulated"] is True
    assert result["confidence_score"] == pytest.approx(0.095)
