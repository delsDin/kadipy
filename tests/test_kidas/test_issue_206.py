"""Vérifie le contrôle d'unicité sans colonnes explicites."""

import pandas as pd
import pytest

from kadi.kidas import Validator


@pytest.mark.parametrize("cols", [None, []])
def test_check_unique_sans_cols(cols):
    """L'unicité porte sur toutes les colonnes si la sélection est vide."""
    validator = Validator(pd.DataFrame({"a": [1, 1, 1], "b": [2, 2, 3]}))
    valid, duplicates = validator.check_unique(cols)
    assert not valid
    assert duplicates.index.tolist() == [0, 1]
    assert validator.report()["validations"][0]["cols"] == ["a", "b"]
