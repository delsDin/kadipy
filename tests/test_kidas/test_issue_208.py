"""Vérifie que les métadonnées Excel utilisent le bon en-tête."""

import pandas as pd
import pytest

from kadi.kidas import ExcelSource


@pytest.mark.parametrize("header", [2, "auto"])
def test_sheet_info_position_entete(tmp_path, header):
    """La feuille demandée est lue avec l'en-tête explicite ou détecté."""
    path = tmp_path / "prices.xlsx"
    frame = pd.DataFrame({"culture": ["maïs"], "prix": [350]})
    with pd.ExcelWriter(path) as book:
        frame.to_excel(book, sheet_name="Janvier", index=False)
        frame.to_excel(book, sheet_name="Février", startrow=2, index=False)
    source = ExcelSource(str(path), header=header)
    result = source.sheet_info("Février")
    assert result["rows"] == 1
    assert result["columns"] == ["culture", "prix"]
