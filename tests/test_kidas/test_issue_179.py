"""Vérifie la géolocalisation des marchés sans nom."""

import pandas as pd

from kadi.kidas import Normalizer


def test_marches_vides_sans_coordonnees():
    """Les noms vides restent sans coordonnées."""
    df = Normalizer(pd.DataFrame({"marche": ["", "  ", "Parakou"]})).std_markets(
        col="marche"
    )
    coords = df[["market_lat", "market_lon"]]
    assert coords.iloc[:2].isna().all().all()
    assert coords.iloc[2].notna().all()
