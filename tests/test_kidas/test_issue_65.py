"""Vérifie le rapport renvoyé lors d'une lecture du cache."""

from kadi.kidas import Pipeline


def test_cache_restitue_rapport_et_distingue_etapes(tmp_path):
    """Le hit conserve le rapport et une nouvelle étape force le calcul."""
    path = tmp_path / "value.csv"
    path.write_text("Culture Locale,prix\nmaize,350\n", encoding="utf-8")
    pipeline = Pipeline().load(str(path)).add_step("drop_dupes").validate(
        {"prix": "int"}
    )
    _, first = pipeline.run(cache=True)
    _, hit = pipeline.run(cache=True)
    assert hit["cache_utilise"] is True
    for key in ("steps_summary", "quality_score", "details", "warnings"):
        assert hit[key] == first[key]
    pipeline.add_step("norm_cols")
    df, report = pipeline.run(cache=True)
    assert "culture_locale" in df
    assert report["steps_summary"][-1] == "norm_cols"
