"""Vérifie les anciens exports publics du module marché."""

import pytest

from kadi.market import Advisor


def test_alias_decision_support():
    """L'ancien nom renvoie la classe officielle avec un avertissement."""
    with pytest.warns(DeprecationWarning, match="Advisor"):
        from kadi.market import DecisionSupport
    assert DecisionSupport is Advisor
