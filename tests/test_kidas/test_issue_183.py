"""Vérifie la sélection NetCDF sur des axes décroissants."""

import pytest

from kadi.kidas import NetCDFSource

xr = pytest.importorskip("xarray")


def test_netcdf_axes_decroissants(tmp_path):
    """La sélection conserve les axes et exclut les points hors emprise."""
    path = tmp_path / "grid.nc"
    ds = xr.Dataset({"rain": (("lat", "lon"), [[0] * 3] * 3)},
                    coords={"lat": [14, 9, 6], "lon": [3, 1, -3]})
    ds.to_netcdf(path)
    data = NetCDFSource(str(path)).read()
    assert data.lat.values.tolist() == [9, 6]
    assert data.lon.values.tolist() == [3, 1]
