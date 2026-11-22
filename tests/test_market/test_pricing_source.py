"""Tests de la provenance des séries de prix."""

import pandas as pd
import pytest

from kadi.market.pricing import Pricing


@pytest.mark.parametrize("flag", ["sim", "is_sim", "is_simulated"])
def test_indicateur_simulation_prioritaire(flag):
    """Un indicateur vrai prévaut sur la provenance déclarée."""
    series = pd.DataFrame({flag: [None, True], "source": ["ratin", "ratin"]})
    assert Pricing().source(series) == "simulated"


@pytest.mark.parametrize("source", ["ratin", "simulated"])
def test_derniere_source_non_nulle(source):
    """Les valeurs manquantes ne masquent pas la dernière source."""
    series = pd.DataFrame({"is_simulated": [None, None], "source": [source, None]})
    assert Pricing().source(series) == source


@pytest.mark.parametrize("series", [None, pd.DataFrame(), pd.DataFrame({"sim": [None]})])
def test_repli_source_vide(series):
    """Les séries sans provenance retournent la source par défaut."""
    assert Pricing().source(series) == "wfp-vam"
