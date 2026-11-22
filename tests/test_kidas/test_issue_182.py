"""Vérifie la détection d'en-tête des classeurs multifeuilles."""

import pandas as pd

from kadi.kidas import ExcelSource


def test_entetes_distincts_par_feuille(tmp_path):
    """Un en-tête détecté n'est réutilisé que pour sa feuille."""
    path = tmp_path / "prices.xlsx"
    frame = pd.DataFrame({"culture": ["maïs"], "prix": [350]})
    with pd.ExcelWriter(path) as book:
        frame.to_excel(book, sheet_name="Janvier", index=False)
        frame.to_excel(book, sheet_name="Février", startrow=3, index=False)
    source = ExcelSource(str(path), sheet="Février")
    for sheet, header in ((0, 0), ("Février", 3), (0, 0)):
        pd.testing.assert_frame_equal(source.read(sheet), frame)
        assert source.info()["detected_header"] == header
