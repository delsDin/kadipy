"""Vérifie le comptage des lignes dupliquées supprimées."""

import pandas as pd

from kadi.kidas import Cleaner


def test_drop_dupes_compte_toutes_les_occurrences():
    """Le compteur correspond aux lignes réellement retirées."""
    cleaner = Cleaner(pd.DataFrame({"a": [1, 1, 2]}))
    assert cleaner.drop_dupes(keep=False)["a"].tolist() == [2]
    assert cleaner.report()["doublons_supprimes"] == 2
