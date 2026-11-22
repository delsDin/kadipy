"""Vérifie la compatibilité des résolutions datetime de pandas."""

import pandas as pd

from kadi.kidas import Validator


def test_check_types_accepte_resolutions_datetime():
    """Une colonne datetime64[us] satisfait un schéma datetime64[ns]."""
    dates = pd.Series(pd.to_datetime(["2024-01-01"])).astype("datetime64[us]")
    valid, _ = Validator(pd.DataFrame({"d": dates})).check_types(
        {"d": "datetime64[ns]"}
    )
    assert valid
