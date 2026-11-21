"""Tests fonctionnels de lecture et d'écriture des sources NetCDF."""

import importlib

import numpy as np
import pandas as pd
import pytest

from kadi.exceptions import ConnectError, ReadError, WriteError

xr = pytest.importorskip("xarray")
pytest.importorskip("netCDF4")
netcdf_source = importlib.import_module("kadi.kidas.sources.netcdf_source")
NetCDFSource = netcdf_source.NetCDFSource


@pytest.fixture
def netcdf_file(tmp_path):
    """Crée un fichier avec des coordonnées intérieures et extérieures au Bénin."""
    path = tmp_path / "precip.nc"
    dataset = xr.Dataset(
        {"precip": (("time", "lat", "lon"), np.arange(18).reshape(2, 3, 3))},
        coords={
            "time": pd.date_range("2026-01-01", periods=2),
            "lat": [0.0, 6.0, 10.0],
            "lon": [-2.0, 1.0, 3.0],
        },
    )
    dataset.to_netcdf(path)
    return path


def test_info_et_dimensions(netcdf_file):
    """Expose les dimensions et les variables du fichier lisible."""
    source = NetCDFSource(str(netcdf_file))
    assert source.ping()
    assert source.dims() == {"time": 2, "lat": 3, "lon": 3}
    info = source.info()
    assert info["kind"] == "netcdf"
    assert info["dimensions"] == source.dims()
    assert info["variables"] == ["precip"]


def test_lecture_benin_et_filtres(netcdf_file):
    """Applique l'emprise par défaut, puis les trois filtres explicites."""
    source = NetCDFSource(str(netcdf_file))
    data = source.read()
    assert data.sizes == {"time": 2, "lat": 2, "lon": 2}
    assert data.lat.values.tolist() == [6.0, 10.0]
    assert data.lon.values.tolist() == [1.0, 3.0]

    data = source.read(
        lat_bounds=(9, 11), lon_bounds=(2, 4),
        time_bounds=("2026-01-02", "2026-01-02"),
    )
    assert data.item() == 17
    assert source.to_df()["precip"].tolist() == [17]


def test_ecriture(tmp_path):
    """Écrit un DataFrame et vérifie les valeurs dans le fichier produit."""
    path = tmp_path / "sortie.nc"
    source = NetCDFSource(str(path))
    assert source.write(pd.DataFrame({"precip": [2.0, 5.0]}))
    with xr.open_dataset(path) as dataset:
        assert dataset["precip"].values.tolist() == [2.0, 5.0]


def test_erreurs_de_source(tmp_path):
    """Distingue fichier absent, contenu illisible et destination invalide."""
    absent = NetCDFSource(str(tmp_path / "absent.nc"))
    assert not absent.ping()
    with pytest.raises(ConnectError):
        absent.read()

    invalid = tmp_path / "invalid.nc"
    invalid.write_text("fichier illisible")
    with pytest.raises(ReadError):
        NetCDFSource(str(invalid)).read()

    target = NetCDFSource(str(tmp_path / "absent" / "sortie.nc"))
    with pytest.raises(WriteError):
        target.write(pd.DataFrame({"precip": [1.0]}))


def test_alias_deprecie():
    """L'ancien nom reste accessible et signale sa dépréciation."""
    with pytest.warns(DeprecationWarning, match="NetCDFDataSource"):
        assert netcdf_source.NetCDFDataSource is NetCDFSource
