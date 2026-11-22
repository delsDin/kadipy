"""Vérifie la conservation des données manquantes pendant le filtrage."""

import pandas as pd
import pytest

from kadi.kidas import Cleaner


@pytest.mark.parametrize("method", ["iqr", "zscore", "mad"])
def test_outliers_conservent_les_valeurs_manquantes(method):
    """Les valeurs manquantes seules ne rendent pas une ligne aberrante."""
    df = pd.DataFrame({"prix": [10., 12., 11., 10.5, None]})
    clean, outliers = Cleaner(df).drop_outliers(method=method, thresh=3.0)
    pd.testing.assert_frame_equal(clean, df)
    assert outliers.empty
