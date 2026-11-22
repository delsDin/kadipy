"""Vérifie la traçabilité des marchés normalisés."""

import pandas as pd

from kadi.kidas import Normalizer


def test_rapport_marche_geolocalise():
    """Le rapport contient la ville et les coordonnées du nom reconnu."""
    normalizer = Normalizer(pd.DataFrame({"marche": ["Parakou", "Inconnu"]}))
    result = normalizer.std_markets(col="marche")
    markets = normalizer.mappings()["marches"]
    assert set(markets) == {"Parakou"}
    assert markets["Parakou"]["ville"] == "Parakou"
    assert markets["Parakou"]["lat"] == result.loc[0, "market_lat"]
    assert markets["Parakou"]["lon"] == result.loc[0, "market_lon"]
