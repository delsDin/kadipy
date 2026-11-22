"""Tests de régression du pipeline Kidas."""

import pandas as pd

from kadi.kidas import Pipeline


def test_diagnostics_conservent_dataframe(tmp_path):
    """Le rapport et le diagnostic décimal ne remplacent pas les données."""
    path = tmp_path / "decimales.csv"
    pd.DataFrame({"valeur": ["1.2", "1.2", "1,2"]}).to_csv(path, index=False)
    df, report = (
        Pipeline().load(str(path), sep=",")
        .add_step("check_decimals")
        .add_step("report")
        .add_step("drop_dupes")
        .run(cache=False)
    )
    assert isinstance(df, pd.DataFrame)
    assert df["valeur"].tolist() == ["1.2", "1,2"]
    diagnostics = report["details"]["nettoyage"]["diagnostics_decimales"]
    assert diagnostics[0]["valeur"]["mixed"]
