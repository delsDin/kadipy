# -*- coding: utf-8 -*-
"""Tests unitaires pour les classes ExcelSource, JSONSource,
APISource et DataCache."""

import json
import os
import tempfile
import warnings

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from kadi.kidas import ExcelSource, JSONSource, APISource, Cache
from kadi.exceptions import ConnectError, ReadError, CacheError


# =============================================================================
# Tests ExcelSource
# =============================================================================

class TestExcelSource:
    """Tests unitaires pour ExcelSource."""

    def test_ping_existant(self, temp_excel_file):
        """Vérifie qu'un fichier Excel existant est accessible."""
        source = ExcelSource(temp_excel_file)
        assert source.ping() is True

    def test_ping_absent(self):
        """Vérifie qu'un fichier absent retourne False."""
        source = ExcelSource("/absent.xlsx")
        assert source.ping() is False

    def test_sheets_retourne_liste(self, temp_excel_file):
        """Vérifie que sheets() retourne une liste non vide."""
        source = ExcelSource(temp_excel_file)
        feuilles = source.sheets()
        assert isinstance(feuilles, list)
        assert len(feuilles) >= 1

    def test_read_retourne_dataframe(self, temp_excel_file):
        """Vérifie que read() retourne un DataFrame non vide."""
        source = ExcelSource(temp_excel_file)
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_fichier_absent_leve_exception(self):
        """Vérifie que la lecture d'un fichier absent lève une exception."""
        source = ExcelSource("/absent.xlsx")
        with pytest.raises(ConnectError):
            source.read()

    def test_unmerge_forward_fill(self):
        """Vérifie que _unmerge() propage les valeurs manquantes."""
        source = ExcelSource.__new__(ExcelSource)
        df_avec_nan = pd.DataFrame({
            "commune": ["Cotonou", None, None, "Parakou", None],
            "valeur": [1, 2, 3, 4, 5],
        })
        df_resolu = source._unmerge(df_avec_nan)
        # Les NaN de 'commune' doivent être comblés par forward fill
        assert df_resolu["commune"].isna().sum() == 0

    def test_info_retourne_dict(self, temp_excel_file):
        """Vérifie les clés des métadonnées retournées."""
        source = ExcelSource(temp_excel_file)
        meta = source.info()
        for cle in ("path", "kind", "sheets", "size_kb"):
            assert cle in meta

    def test_write_retourne_true(self, temp_excel_file, sample_df):
        """Vérifie que write() retourne True sur succès."""
        source = ExcelSource(temp_excel_file)
        assert source.write(sample_df) is True


# =============================================================================
# Tests JSONSource
# =============================================================================

class TestJSONSource:
    """Tests unitaires pour JSONSource."""

    def test_read_depuis_fichier(self, temp_json_file):
        """Vérifie la lecture depuis un fichier JSON."""
        source = JSONSource(temp_json_file)
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_depuis_dict(self, mock_api_response):
        """Vérifie la lecture depuis un dictionnaire Python en mémoire."""
        source = JSONSource(mock_api_response[0])
        df = source.read()
        assert isinstance(df, pd.DataFrame)

    def test_flatten_simple(self):
        """Vérifie l'aplatissement d'un dict imbriqué simple."""
        source = JSONSource.__new__(JSONSource)
        entree = {"location": {"lat": 9.3, "lon": 2.4}, "crop": "maize"}
        resultat = source.flatten(entree)
        assert "location.lat" in resultat
        assert "location.lon" in resultat
        assert "crop" in resultat
        assert resultat["location.lat"] == 9.3

    def test_flatten_liste(self, nested_json_dict):
        """Vérifie que la source lit correctement un JSON imbriqué avec liste."""
        # Le dict imbriqué contient une clé 'data' avec une liste
        source = JSONSource(nested_json_dict)
        df = source.read(flatten=True)
        assert isinstance(df, pd.DataFrame)

    def test_ping_fichier_existant(self, temp_json_file):
        """Vérifie la connexion sur un fichier JSON existant."""
        source = JSONSource(temp_json_file)
        assert source.ping() is True

    def test_ping_dict_toujours_true(self, mock_api_response):
        """Vérifie qu'un dict en mémoire est toujours accessible."""
        source = JSONSource(mock_api_response[0])
        assert source.ping() is True

    def test_write_json_fichier(self, temp_json_file, sample_df):
        """Vérifie l'écriture d'un DataFrame en JSON."""
        source = JSONSource(temp_json_file)
        assert source.write(sample_df) is True


# =============================================================================
# Tests APISource
# =============================================================================

class TestAPISource:
    """Tests unitaires pour APISource avec mock HTTP."""

    def test_info_retourne_dict(self):
        """Vérifie les clés des métadonnées de la source API."""
        source = APISource("https://api.example.com/data")
        meta = source.info()
        for cle in ("url", "kind", "requires_auth", "rate_limit"):
            assert cle in meta

    def test_requires_auth_avec_token(self):
        """Vérifie que requires_auth est True si un token est fourni."""
        source = APISource("https://api.example.com", token="secret123")
        assert source.info()["requires_auth"] is True

    def test_requires_auth_sans_token(self):
        """Vérifie que requires_auth est False sans token."""
        source = APISource("https://api.example.com")
        assert source.info()["requires_auth"] is False

    @patch("kadi.kidas.sources.api_source.requests.get")
    def test_read_retourne_dataframe(self, mock_get, mock_api_response):
        """Vérifie que read() retourne un DataFrame depuis une réponse JSON simulée."""
        # Configuration du mock HTTP
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        source = APISource("https://api.example.com/data")
        df = source.read({})
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(mock_api_response)

    @patch("kadi.kidas.sources.api_source.requests.get")
    def test_fetch_succes_deuxieme_tentative(self, mock_get):
        """Vérifie le mécanisme de réessai lors d'une erreur 503."""
        import requests

        # Première tentative : 503, deuxième : 200
        mock_erreur = MagicMock()
        mock_erreur.status_code = 503

        mock_succes = MagicMock()
        mock_succes.status_code = 200
        mock_succes.json.return_value = [{"key": "value"}]
        mock_succes.raise_for_status.return_value = None

        mock_get.side_effect = [mock_erreur, mock_succes]

        source = APISource("https://api.example.com", rate_limit=100)
        # Modification du backoff pour accélérer le test
        resultat = source.fetch({}, retries=2, backoff=0.01)
        assert resultat == [{"key": "value"}]

    def test_retrocompatibilite_apidatasource_emet_warning(self):
        """Vérifie que l'accès via l'ancien nom APIDataSource émet un DeprecationWarning."""
        import kadi.kidas.sources.api_source as mod
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Accès via l'ancien nom (intercepté par __getattr__)
            ancien_cls = mod.APIDataSource
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "APIDataSource" in str(w[0].message)
        # La classe retournée est bien APISource
        assert ancien_cls is APISource


# =============================================================================
# Tests Cache
# =============================================================================

class TestCache:
    """Tests unitaires pour la classe Cache (SQLite kidas)."""

    @pytest.fixture
    def cache_temp(self, tmp_path):
        """Crée une instance Cache dans un répertoire temporaire."""
        return Cache(cache_dir=str(tmp_path), max_age_days=365)

    def test_set_et_get_dataframe(self, cache_temp, sample_df):
        """Vérifie la sauvegarde et le rechargement d'un DataFrame."""
        cache_temp.set("test_key", sample_df)
        df_charge, meta = cache_temp.get("test_key")
        assert df_charge is not None
        assert len(df_charge) == len(sample_df)

    def test_get_cle_absente_retourne_none(self, cache_temp):
        """Vérifie que le chargement d'une clé inexistante retourne None."""
        df, meta = cache_temp.get("cle_inexistante")
        assert df is None
        assert meta is None

    def test_keys(self, cache_temp, sample_df):
        """Vérifie que les clés sauvegardées apparaissent dans keys()."""
        cache_temp.set("cle_a", sample_df)
        cache_temp.set("cle_b", sample_df)
        cles = cache_temp.keys()
        assert "cle_a" in cles
        assert "cle_b" in cles

    def test_delete_supprime_entree(self, cache_temp, sample_df):
        """Vérifie que delete() supprime l'entrée du cache."""
        cache_temp.set("a_supprimer", sample_df)
        assert cache_temp.delete("a_supprimer") is True
        df, _ = cache_temp.get("a_supprimer")
        assert df is None

    def test_clear_vide_le_cache(self, cache_temp, sample_df):
        """Vérifie que clear() supprime toutes les entrées."""
        cache_temp.set("entree_1", sample_df)
        cache_temp.set("entree_2", sample_df)
        cache_temp.clear()
        assert len(cache_temp.keys()) == 0

    def test_size_retourne_dict(self, cache_temp, sample_df):
        """Vérifie que size() retourne les clés attendues."""
        cache_temp.set("test", sample_df)
        taille = cache_temp.size()
        for cle in ("total_mb", "num_entries", "oldest_date"):
            assert cle in taille

    def test_history_apres_deux_sets(self, cache_temp, sample_df):
        """Vérifie que l'historique est enregistré lors d'un remplacement."""
        cache_temp.set("ma_cle", sample_df)
        cache_temp.set("ma_cle", sample_df)
        historique = cache_temp.history("ma_cle")
        assert len(historique) >= 1

    def test_purge(self, cache_temp, sample_df):
        """Vérifie la suppression des entrées trop anciennes."""
        cache_temp.set("entree_recente", sample_df)
        nb = cache_temp.purge(days=0)
        assert isinstance(nb, int)
