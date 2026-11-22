"""Vérifie le traitement tabulaire des sources NetCDF dans Pipeline."""

import pandas as pd
import pytest

from kadi.kidas import Pipeline

xr = pytest.importorskip("xarray")


def test_pipeline_netcdf_stocke_un_dataframe(tmp_path):
    """Une grille NetCDF peut être normalisée et mise en cache."""
    path = tmp_path / "grid.nc"
    xr.Dataset({"Rain Test": (("lat", "lon"), [[1, 2], [3, 4]])},
               coords={"lat": [6, 9], "lon": [1, 3]}).to_netcdf(path)
    pipeline = Pipeline().load(str(path)).add_step("norm_cols")
    df, report = pipeline.run(cache=True)
    assert isinstance(df, pd.DataFrame)
    assert report["nb_rows_in"] == 4
    assert df["rain_test"].tolist() == [1, 2, 3, 4]
    cached, _ = pipeline.run(cache=True)
    pd.testing.assert_frame_equal(cached, df)
