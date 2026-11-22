"""Tests de régression du pipeline Kidas."""

import pandas as pd
import pytest

from kadi.kidas import Pipeline


@pytest.fixture
def source(tmp_path):
    """Crée des données qui échouent aux contrôles demandés."""
    path = tmp_path / "prix.csv"
    pd.DataFrame({
        "prix": [350, 12], "lat": [90, 9], "lon": [2, 2],
        "marche": ["a", "a"],
    }).to_csv(path, index=False)
    return str(path)


@pytest.mark.parametrize(
    "method, args, kwargs",
    [
        ("check_types", ({"prix": "datetime64[ns]"},), {}),
        ("check_ranges", ({"prix": (0, 100)},), {}),
        ("check_coords", (), {"lat": "lat", "lon": "lon"}),
        ("check_unique", (["marche"],), {}),
        ("check_fk", (), {"fk_col": "marche", "ref": {"b"}}),
    ],
)
def test_pipeline_executes_validation(source, method, args, kwargs):
    """Vérifie que chaque contrôle traite les données et ses paramètres."""
    _, report = Pipeline().load(source).add_step(
        method, *args, **kwargs
    ).run(cache=False)
    checks = report["details"]["validation"]["validations"]
    assert len(checks) == 1
    assert checks[0]["type"] != "schema"
    assert not checks[0]["valide"]


def test_pipeline_legacy_fk(source):
    """L'ancien nom de la validation référentielle reste opérationnel."""
    pipeline = Pipeline().load(source).add_step(
        "validate_referential_integrity", fk_col="marche", ref={"b"}
    )
    with pytest.warns(DeprecationWarning, match="check_fk") as caught:
        _, report = pipeline.run(cache=False)
    assert len(caught) == 1
    assert not report["details"]["validation"]["validations"][0]["valide"]


def test_pipeline_quality_score(source):
    """Le calcul direct et son alias produisent le même rapport."""
    pipeline = Pipeline().load(source)
    _, modern = pipeline.add_step("quality_score").run(cache=False)
    with pytest.warns(DeprecationWarning, match="quality_score") as caught:
        _, legacy = Pipeline().load(source).add_step(
            "compute_quality_score"
        ).run(cache=False)
    assert len(caught) == 1
    assert modern["quality_score"] == legacy["quality_score"]
    assert 0 <= modern["quality_score"]["overall"] <= 1


@pytest.mark.parametrize("method", ["check_coords", "check_fk"])
def test_pipeline_requires_named_validation_parameters(method):
    """Les contrôles à plusieurs paramètres exigent des arguments nommés."""
    with pytest.raises(TypeError, match="argument positionnel"):
        Pipeline().add_step(method, "colonne")
