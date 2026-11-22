"""Tests de régression du pipeline Kidas."""

import pandas as pd
import pytest

from kadi.kidas import Pipeline


@pytest.fixture
def pipeline(tmp_path):
    """Charge un exemple de culture avant normalisation."""
    path = tmp_path / "cultures.csv"
    path.write_text("culture,prix\nmanioc,350\n", encoding="utf-8")
    return Pipeline().load(str(path))


@pytest.mark.parametrize("step", [None, "norm_cols", "mappings"])
def test_pipeline_crop_mappings(pipeline, step):
    """Les trois formes historiques exécutent la normalisation demandée."""
    mappings = {"crops": "culture"}
    if step is None:
        pipeline.normalize(mappings)
    else:
        pipeline.add_step(step, mappings)
    df, _ = pipeline.run(cache=False)
    assert df["culture"].tolist() == ["cassava"]


def test_pipeline_legacy_normalization(pipeline):
    """L'ancien nom transforme les données avec un avertissement unique."""
    pipeline.add_step("normalize_crop_names", col="culture")
    with pytest.warns(DeprecationWarning, match="std_crops") as caught:
        df, _ = pipeline.run(cache=False)
    assert len(caught) == 1
    assert df["culture"].tolist() == ["cassava"]
