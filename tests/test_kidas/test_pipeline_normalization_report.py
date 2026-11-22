"""Tests de régression du pipeline Kidas."""

import pandas as pd

from kadi.kidas import Pipeline


def test_rapport_normalisation_cumule_et_reinitialise(tmp_path):
    """Cumule deux mesures, puis repart du fichier mis à jour."""
    path = tmp_path / "cultures.csv"
    path.write_text("Culture Locale,prix\nmanioc,350\n", encoding="utf-8")
    pipeline = (
        Pipeline().load(str(path))
        .add_step("std_crops", col="Culture Locale")
        .add_step("norm_cols")
    )
    _, first = pipeline.run(cache=False)
    mappings = first["details"]["normalisation"]
    assert mappings["cultures"]["manioc"] == "cassava"
    assert mappings["colonnes"]["Culture Locale"] == "culture_locale"

    path.write_text("Culture Locale,prix\nsorgho,350\n", encoding="utf-8")
    _, second = pipeline.run(cache=False)
    mappings = second["details"]["normalisation"]
    assert mappings["cultures"]["sorgho"] == "sorghum"
    assert "manioc" not in mappings["cultures"]
    assert mappings["colonnes"]["Culture Locale"] == "culture_locale"
