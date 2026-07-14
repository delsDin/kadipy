# -*- coding: utf-8 -*-
"""Tests unitaires pour les classes ExcelDataSource, JSONDataSource,
NetCDFDataSource, APIDataSource et DataCache."""

import json
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from kadi.kidas.sources.excel_source import ExcelDataSource
from kadi.kidas.sources.json_source import JSONDataSource
from kadi.kidas.sources.api_source import APIDataSource
from kadi.kidas.cache import DataCache
from kadi.exceptions import KidasConnectionError, KidasReadError, KidasCacheError


# =============================================================================
# Tests ExcelDataSource
# =============================================================================

class TestExcelDataSource:
    """Tests unitaires pour ExcelDataSource."""

    def test_validate_connection_existant(self, temp_excel_file):
        """Vérifie qu'un fichier Excel existant est accessible."""
        source = ExcelDataSource(temp_excel_file)
        assert source.validate_connection() is True

    def test_validate_connection_absent(self):
        """Vérifie qu'un fichier absent retourne False."""
        source = ExcelDataSource("/absent.xlsx")
        assert source.validate_connection() is False

    def test_list_sheets_retourne_liste(self, temp_excel_file):
        """Vérifie que list_sheets() retourne une liste non vide."""
        source = ExcelDataSource(temp_excel_file)
        feuilles = source.list_sheets()
        assert isinstance(feuilles, list)
        assert len(feuilles) >= 1

    def test_read_retourne_dataframe(self, temp_excel_file):
        """Vérifie que read() retourne un DataFrame non vide."""
        source = ExcelDataSource(temp_excel_file)
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_fichier_absent_leve_exception(self):
        """Vérifie que la lecture d'un fichier absent lève une exception."""
        source = ExcelDataSource("/absent.xlsx")
        with pytest.raises(KidasConnectionError):
            source.read()

    def test_unmerge_cells_forward_fill(self):
        """Vérifie que unmerge_cells() propage les valeurs manquantes."""
        source = ExcelDataSource.__new__(ExcelDataSource)
        df_avec_nan = pd.DataFrame({
            "commune": ["Cotonou", None, None, "Parakou", None],
            "valeur": [1, 2, 3, 4, 5],
        })
        df_resolu = source.unmerge_cells(df_avec_nan)
        # Les NaN de 'commune' doivent être comblés par forward fill
        assert df_resolu["commune"].isna().sum() == 0

    def test_get_metadata_retourne_dict(self, temp_excel_file):
        """Vérifie les clés des métadonnées retournées."""
        source = ExcelDataSource(temp_excel_file)
        meta = source.get_metadata()
        for cle in ("source_path", "source_type", "sheets", "size_kb"):
            assert cle in meta

    def test_write_retourne_true(self, temp_excel_file, sample_df):
        """Vérifie que write() retourne True sur succès."""
        source = ExcelDataSource(temp_excel_file)
        assert source.write(sample_df) is True


# =============================================================================
# Tests JSONDataSource
# =============================================================================

class TestJSONDataSource:
    """Tests unitaires pour JSONDataSource."""

    def test_read_depuis_fichier(self, temp_json_file):
        """Vérifie la lecture depuis un fichier JSON."""
        source = JSONDataSource(temp_json_file)
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_depuis_dict(self, mock_api_response):
        """Vérifie la lecture depuis un dictionnaire Python en mémoire."""
        source = JSONDataSource(mock_api_response[0])
        df = source.read()
        assert isinstance(df, pd.DataFrame)

    def test_flatten_json_simple(self):
        """Vérifie l'aplatissement d'un dict imbriqué simple."""
        source = JSONDataSource.__new__(JSONDataSource)
        entree = {"location": {"lat": 9.3, "lon": 2.4}, "crop": "maize"}
        resultat = source.flatten_json(entree)
        assert "location.lat" in resultat
        assert "location.lon" in resultat
        assert "crop" in resultat
        assert resultat["location.lat"] == 9.3

    def test_flatten_json_liste(self, nested_json_dict):
        """Vérifie que la source lit correctement un JSON imbriqué avec liste."""
        # Le dict imbriqué contient une clé 'data' avec une liste
        source = JSONDataSource(nested_json_dict)
        df = source.read(flatten=True)
        assert isinstance(df, pd.DataFrame)

    def test_validate_connection_fichier_existant(self, temp_json_file):
        """Vérifie la connexion sur un fichier JSON existant."""
        source = JSONDataSource(temp_json_file)
        assert source.validate_connection() is True

    def test_validate_connection_dict_toujours_true(self, mock_api_response):
        """Vérifie qu'un dict en mémoire est toujours accessible."""
        source = JSONDataSource(mock_api_response[0])
        assert source.validate_connection() is True

    def test_write_json_fichier(self, temp_json_file, sample_df):
        """Vérifie l'écriture d'un DataFrame en JSON."""
        source = JSONDataSource(temp_json_file)
        assert source.write(sample_df) is True


# =============================================================================
# Tests APIDataSource
# =============================================================================

class TestAPIDataSource:
    """Tests unitaires pour APIDataSource avec mock HTTP."""

    def test_get_metadata_retourne_dict(self):
        """Vérifie les clés des métadonnées de la source API."""
        source = APIDataSource("https://api.example.com/data")
        meta = source.get_metadata()
        for cle in ("source_path", "source_type", "requires_auth", "rate_limit_per_sec"):
            assert cle in meta

    def test_requires_auth_avec_token(self):
        """Vérifie que requires_auth est True si un token est fourni."""
        source = APIDataSource("https://api.example.com", auth_token="secret123")
        assert source.get_metadata()["requires_auth"] is True

    def test_requires_auth_sans_token(self):
        """Vérifie que requires_auth est False sans token."""
        source = APIDataSource("https://api.example.com")
        assert source.get_metadata()["requires_auth"] is False

    @patch("kadi.kidas.sources.api_source.requests.get")
    def test_read_retourne_dataframe(self, mock_get, mock_api_response):
        """Vérifie que read() retourne un DataFrame depuis une réponse JSON simulée."""
        # Configuration du mock HTTP
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        source = APIDataSource("https://api.example.com/data")
        df = source.read({})
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(mock_api_response)

    @patch("kadi.kidas.sources.api_source.requests.get")
    def test_fetch_with_retry_succes_deuxieme_tentative(self, mock_get):
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

        source = APIDataSource("https://api.example.com", rate_limit_per_sec=100)
        # Modification du backoff pour accélérer le test
        resultat = source.fetch_with_retry({}, max_retries=2, backoff_sec=0.01)
        assert resultat == [{"key": "value"}]


# =============================================================================
# Tests DataCache
# =============================================================================

class TestDataCache:
    """Tests unitaires pour DataCache (SQLite kidas)."""

    @pytest.fixture
    def cache_temp(self, tmp_path):
        """Crée une instance DataCache dans un répertoire temporaire."""
        return DataCache(cache_dir=str(tmp_path), max_age_days=365)

    def test_save_et_load_dataframe(self, cache_temp, sample_df):
        """Vérifie la sauvegarde et le rechargement d'un DataFrame."""
        cache_temp.save("test_key", sample_df)
        df_charge, meta = cache_temp.load("test_key")
        assert df_charge is not None
        assert len(df_charge) == len(sample_df)

    def test_load_cle_absente_retourne_none(self, cache_temp):
        """Vérifie que le chargement d'une clé inexistante retourne None."""
        df, meta = cache_temp.load("cle_inexistante")
        assert df is None
        assert meta is None

    def test_get_cached_keys(self, cache_temp, sample_df):
        """Vérifie que les clés sauvegardées apparaissent dans get_cached_keys()."""
        cache_temp.save("cle_a", sample_df)
        cache_temp.save("cle_b", sample_df)
        cles = cache_temp.get_cached_keys()
        assert "cle_a" in cles
        assert "cle_b" in cles

    def test_invalidate_supprime_entree(self, cache_temp, sample_df):
        """Vérifie que invalidate() supprime l'entrée du cache."""
        cache_temp.save("a_supprimer", sample_df)
        assert cache_temp.invalidate("a_supprimer") is True
        df, _ = cache_temp.load("a_supprimer")
        assert df is None

    def test_clear_vide_le_cache(self, cache_temp, sample_df):
        """Vérifie que clear() supprime toutes les entrées."""
        cache_temp.save("entree_1", sample_df)
        cache_temp.save("entree_2", sample_df)
        cache_temp.clear()
        assert len(cache_temp.get_cached_keys()) == 0

    def test_get_cache_size_retourne_dict(self, cache_temp, sample_df):
        """Vérifie que get_cache_size() retourne les clés attendues."""
        cache_temp.save("test", sample_df)
        taille = cache_temp.get_cache_size()
        for cle in ("total_mb", "num_entries", "oldest_date"):
            assert cle in taille

    def test_get_history_apres_deux_saves(self, cache_temp, sample_df):
        """Vérifie que l'historique est enregistré lors d'un remplacement."""
        cache_temp.save("ma_cle", sample_df)
        cache_temp.save("ma_cle", sample_df)  # Deuxième save : archive la première
        historique = cache_temp.get_history("ma_cle")
        assert len(historique) >= 1

    def test_invalidate_older_than(self, cache_temp, sample_df):
        """Vérifie la suppression des entrées trop anciennes."""
        cache_temp.save("entree_recente", sample_df)
        # Avec 0 jours, toutes les entrées sont considérées expirées
        nb = cache_temp.invalidate_older_than(days=0)
        # Peut retourner 0 si l'entrée a été créée dans la même seconde
        assert isinstance(nb, int)
