"""Vérifie les options d'écriture des raccourcis et du répartiteur public."""

import json

import pandas as pd
import pytest

from kadi import io


@pytest.mark.parametrize("generic", [False, True])
def test_options_ecriture(tmp_path, generic):
    """L'index CSV, la feuille Excel et l'orientation JSON sont respectés."""
    data = pd.DataFrame({"prix": [350]}, index=["a"])
    csv, excel, js = [str(tmp_path / f"export.{ext}") for ext in ("csv", "xlsx", "json")]
    (io.write if generic else io.write_csv)(data, csv, index=True, sep=";")
    (io.write if generic else io.write_excel)(data, excel, sheet="Export")
    (io.write if generic else io.write_json)(data, js, orient="index")
    assert pd.read_csv(csv, index_col=0, sep=";").index.tolist() == ["a"]
    with pd.ExcelFile(excel) as book:
        assert book.sheet_names == ["Export"]
    with open(js, encoding="utf-8") as file:
        assert json.load(file) == {"a": {"prix": 350}}
