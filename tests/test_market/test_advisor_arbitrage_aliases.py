"""Tests des arguments historiques d'arbitrage."""

from unittest.mock import call

import pytest

from kadi.market.decision_support import Advisor


def test_alias_arbitrage_utilisent_les_marches(mocker):
    """Les alias avertissent et sont transmis aux lectures des prix."""
    advisor = Advisor()
    lookup = mocker.patch.object(advisor, "_get_price", return_value=(200, False, 0.8))
    with pytest.warns(DeprecationWarning) as caught:
        advisor.arbitrage("maize", origine="Kandi", destination="Malanville")
    assert len(caught) == 2
    assert "m_from" in str(caught[0].message)
    assert "to" in str(caught[1].message)
    assert lookup.call_args_list == [call("maize", "Kandi"), call("maize", "Malanville")]


def test_arbitrage_rejette_argument_inconnu():
    """Une faute de paramètre est signalée avant tout appel externe."""
    with pytest.raises(TypeError, match="destnation"):
        Advisor().arbitrage("maize", destnation="Malanville")
