"""Vérifie les paramètres positionnels des étapes de normalisation."""

import pytest

from kadi.kidas import Pipeline


@pytest.mark.parametrize("step,arg,column,expected", [
    ("convert_units", {"prix": "tonne"}, "prix", 1000),
    ("std_crops", "culture", "culture", "cassava"),
    ("std_markets", "marche", "market_lat", 9.337),
    ("convert_currency", "prix", "prix", 1),
])
def test_normalisation_positionnelle(tmp_path, step, arg, column, expected):
    """Achemine le paramètre vers l'option de la méthode demandée."""
    path = tmp_path / "data.csv"
    path.write_text("prix,culture,marche\n1,manioc,Parakou\n", encoding="utf-8")
    df, _ = Pipeline().load(str(path)).add_step(step, arg).run(cache=False)
    assert df.loc[0, column] == expected
