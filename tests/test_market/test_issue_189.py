"""Vérifie les mots-clés historiques des méthodes Pricing."""

import pandas as pd
import pytest

from kadi.market.pricing import Pricing


def test_anciens_parametres_pricing():
    """Les anciens mots-clés sont routés et avertissent les appelants."""
    pricing = Pricing()
    series = pd.DataFrame({"price": [10, None, 12]})
    with pytest.warns(DeprecationWarning, match="days"):
        assert not pricing.fetch("maize", "cotonou", days_back=3, simulated=True).empty
    with pytest.warns(DeprecationWarning, match="unit"):
        assert pricing.convert_unit(250_000, unit_orig="XOF/Tonne") == 250
    with pytest.warns(DeprecationWarning, match="series"):
        assert "is_anomaly" in pricing.anomalies(price_series=series, z_threshold=2)
    with pytest.warns(DeprecationWarning, match="series"):
        result = pricing.fill_gaps(price_series=series, max_gap_days=1)
        assert result["price"].tolist() == [10, 11, 12]
    with pytest.warns(DeprecationWarning, match="series"):
        assert pricing.source(price_series=None) == "wfp-vam"
    with pytest.raises(TypeError, match="series"):
        pricing.source()
    with pytest.raises(TypeError, match="unknown"):
        pricing.source(None, unknown=True)
