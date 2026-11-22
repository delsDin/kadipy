"""Vérifie les nouvelles tentatives après un délai réseau."""

import pytest
import requests

from kadi.exceptions import ConnectError
from kadi.kidas import APISource


def test_timeout_declenche_des_reessais(mocker):
    """Le délai réseau est réessayé puis converti en erreur de connexion."""
    get = mocker.patch("requests.get", side_effect=requests.exceptions.Timeout)
    mocker.patch("time.sleep")
    with pytest.raises(ConnectError):
        APISource("https://example.test").fetch({}, retries=2, backoff=0)
    assert get.call_count == 3
