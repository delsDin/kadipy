"""Vérifie le routage des options des lecteurs publics."""

from unittest.mock import Mock

import kadi.io as io
import pytest


@pytest.mark.parametrize("name,cls,init,options", [
    ("csv", "CSVSource", {"sep": ";"}, {"n": 2, "skip": 1}),
    ("json", "JSONSource", {}, {"flatten": False}),
    ("netcdf", "NetCDFSource", {"use_dask": False},
     {"lat_bounds": (5, 8), "lon_bounds": (1, 2), "time_bounds": ("a", "b")}),
])
def test_options_de_lecture(monkeypatch, name, cls, init, options):
    """Les options ne sont passées qu'à la méthode concernée."""
    factory = Mock()
    monkeypatch.setattr(io, cls, factory)
    assert getattr(io, f"read_{name}")("fichier", **init, **options) is (
        factory.return_value.read.return_value
    )
    factory.assert_called_once_with("fichier", **init)
    factory.return_value.read.assert_called_once_with(**options)
