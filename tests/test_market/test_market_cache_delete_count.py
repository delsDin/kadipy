"""Tests du compteur de suppression du cache des prix."""

import pandas as pd

from kadi.market._cache import sauvegarder_prix, vider_cache


def test_vider_cache_compte_les_prix(tmp_path):
    """Compte les observations supprimées dans chacun des trois modes."""
    path = tmp_path / "market.db"
    for market, crop, count in (
        ("cotonou", "maize", 15), ("cotonou", "yam", 3), ("parakou", "maize", 7),
    ):
        prices = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=count), "price": 200,
        })
        assert sauvegarder_prix(market, crop, prices, db_path=path) == count
    assert vider_cache("cotonou", "maize", db_path=path) == 15
    assert vider_cache("cotonou", db_path=path) == 3
    assert vider_cache(db_path=path) == 7
    assert vider_cache(db_path=path) == 0
