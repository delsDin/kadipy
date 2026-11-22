"""Tests de compatibilité des prix utilisés par Advisor."""

import sys

import pytest

from kadi.market.decision_support import Advisor


@pytest.mark.parametrize("use_scipy", [True, False])
def test_optimize_accepte_les_formats_de_prix(monkeypatch, use_scipy):
    """Le solveur et le repli lisent les prix actuels et historiques."""
    if use_scipy:
        pytest.importorskip("scipy.optimize")
    else:
        monkeypatch.setitem(sys.modules, "scipy.optimize", None)
    current = {"maize": 285.0, "cowpea": 580.0}
    legacy = {crop: {"prix_moyen_xof": price} for crop, price in current.items()}
    advisor = Advisor()
    result = advisor.optimize(land_ha=10, market=current)
    assert result["methode"] == ("scipy_linprog" if use_scipy else "heuristique")
    assert result["revenu_attendu_cfa"] > 0
    assert advisor.optimize(land_ha=10, market=legacy) == result
    for invalid in (float("nan"), float("inf"), 0, -20):
        assert advisor.optimize(
            land_ha=10, market={**current, "soybean": invalid}
        ) == result
        assert advisor.optimize(
            land_ha=10, market={**legacy, "soybean": {"prix_moyen_xof": invalid}}
        ) == result
