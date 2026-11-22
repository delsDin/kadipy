"""Vérifie la provenance du résultat de Pipeline.run."""

from kadi.kidas import Pipeline


def test_mise_en_cache_is_distincte_de_la_lecture(tmp_path):
    """Seule une lecture effective du cache active l'indicateur."""
    path = tmp_path / "values.csv"
    path.write_text("prix\n10\n", encoding="utf-8")
    pipeline = Pipeline().load(str(path))
    _, miss = pipeline.run(cache=True)
    _, hit = pipeline.run(cache=True)
    assert miss["cache_utilise"] is False
    assert hit["cache_utilise"] is True
