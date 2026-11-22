"""Vérifie l'indépendance des rapports sur plusieurs exécutions."""

from copy import deepcopy

from kadi.kidas import Pipeline


def test_rapports_pipeline_independants(tmp_path):
    """Les compteurs et le score repartent de la source à chaque calcul."""
    path = tmp_path / "values.csv"
    path.write_text("culture,prix\nmaize,5\nmaize,5\n", encoding="utf-8")
    pipeline = Pipeline().load(str(path)).add_step("drop_dupes").validate(
        {"culture": "str"}
    )
    _, first = pipeline.run(cache=True)
    snapshot = deepcopy(first)
    _, second = pipeline.run(cache=False)
    assert first == snapshot
    assert first["details"] == second["details"]
    assert first["quality_score"] == second["quality_score"]
    assert second["cache_utilise"] is False
