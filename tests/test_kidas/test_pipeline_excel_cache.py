# -*- coding: utf-8 -*-
"""Tests du cache Pipeline pour la distinction des feuilles Excel."""

import pandas as pd

from kadi.kidas import Pipeline
from kadi.kidas.cache import Cache


def test_pipeline_cache_distingue_feuilles_excel(tmp_path, monkeypatch):
    """Deux feuilles d'un même classeur Excel ne partagent pas la même entrée en cache."""
    # Isolation du cache de Pipeline dans un répertoire temporaire dédié au test
    cache = Cache(cache_dir=str(tmp_path / "cache"))
    monkeypatch.setattr("kadi.kidas.pipeline.Cache", lambda: cache)

    # Création d'un classeur contenant deux feuilles distinctes
    excel_path = tmp_path / "prices.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        pd.DataFrame({"price": [100]}).to_excel(
            writer, sheet_name="first", index=False
        )
        pd.DataFrame({"price": [200]}).to_excel(
            writer, sheet_name="second", index=False
        )

    # Premier appel : met en cache la feuille 'first'
    Pipeline().add_source(excel_path, sheet="first", header=0).run()

    # Second appel : la feuille 'second' doit être lue sans collision avec 'first'
    result, report = (
        Pipeline().add_source(excel_path, sheet="second", header=0).run()
    )
    assert result["price"].tolist() == [200]
    assert report["cache_utilise"] is False
