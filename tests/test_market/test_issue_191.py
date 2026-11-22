"""Vérifie les prix historiques transmis aux prévisions de stockage."""

from unittest.mock import Mock

import pandas as pd

from kadi.market import Advisor


def test_stockage_utilise_historique_en_xof_kg():
    """Le conseiller récupère l'historique et convertit une copie des prix."""
    price_data = pd.DataFrame({"price": [350_000], "unit": ["XOF/tonne"]})
    pricing = Mock(sim=False)
    pricing.fetch.return_value = price_data
    pricing.convert_unit.return_value = 350
    forecasting = Mock()
    forecasting.predict.return_value = {"predicted_price": 350, "is_simulated": False}

    result = Advisor(forecast=forecasting, pricing=pricing).store_sell(
        crop="maize", market="parakou", price=300_000, qty=1, months=3
    )
    pricing.fetch.assert_called_once_with("maize", "parakou", days=365)
    assert forecasting.predict.call_args.kwargs["hist"]["price"].tolist() == [350]
    assert price_data["price"].tolist() == [350_000]
    assert result["is_simulated"] is False
