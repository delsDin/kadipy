# -*- coding: utf-8 -*-
"""Tests unitaires pour la classe CSVDataSource."""

import os

import pandas as pd
import pytest

from kadi.kidas.sources.csv_source import CSVDataSource
from kadi.exceptions import KidasConnectionError, KidasReadError


class TestCSVDataSourceValidation:
    """Tests de validation de la connexion et des métadonnées."""

    def test_validate_connection_fichier_existant(self, temp_csv_file):
        """Vérifie qu'un fichier existant est correctement détecté comme accessible."""
        source = CSVDataSource(temp_csv_file)
        assert source.validate_connection() is True

    def test_validate_connection_fichier_absent(self):
        """Vérifie qu'un fichier inexistant retourne False."""
        source = CSVDataSource("/chemin/inexistant/fichier.csv")
        assert source.validate_connection() is False

    def test_get_metadata_retourne_dict_complet(self, temp_csv_file):
        """Vérifie que get_metadata() retourne toutes les clés attendues."""
        source = CSVDataSource(temp_csv_file)
        meta = source.get_metadata()
        # Vérification des clés obligatoires
        for cle in ("source_path", "source_type", "encoding", "delimiter",
                    "rows", "cols", "size_kb"):
            assert cle in meta, f"Clé manquante dans les métadonnées : '{cle}'"

    def test_get_metadata_source_type_csv(self, temp_csv_file):
        """Vérifie que le type de source est bien 'csv'."""
        source = CSVDataSource(temp_csv_file)
        assert source.get_metadata()["source_type"] == "csv"


class TestCSVDataSourceDetection:
    """Tests de détection automatique (encodage, délimiteur)."""

    def test_detect_encoding_utf8(self, temp_csv_file):
        """Vérifie que chardet détecte un fichier UTF-8."""
        source = CSVDataSource(temp_csv_file, encoding="auto")
        encodage = source.detect_encoding()
        assert encodage is not None
        assert isinstance(encodage, str)

    def test_detect_delimiter_virgule(self, temp_csv_file):
        """Vérifie que le délimiteur virgule est correctement détecté."""
        source = CSVDataSource(temp_csv_file, delimiter="auto")
        delimiteur = source.detect_delimiter()
        assert delimiteur == ","

    def test_detect_delimiter_point_virgule(self, temp_csv_semicolon_file):
        """Vérifie que le délimiteur point-virgule est correctement détecté."""
        source = CSVDataSource(temp_csv_semicolon_file, delimiter="auto")
        delimiteur = source.detect_delimiter()
        assert delimiteur == ";"


class TestCSVDataSourceLecture:
    """Tests de lecture du fichier CSV."""

    def test_read_retourne_dataframe(self, temp_csv_file):
        """Vérifie que read() retourne un pandas DataFrame non vide."""
        source = CSVDataSource(temp_csv_file)
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_nrows_limite(self, temp_csv_file):
        """Vérifie que le paramètre nrows limite correctement le nombre de lignes."""
        source = CSVDataSource(temp_csv_file)
        df = source.read(nrows=2)
        assert len(df) == 2

    def test_read_fichier_latin1(self, temp_csv_latin1_file):
        """Vérifie la lecture robuste d'un fichier encodé en Latin-1."""
        source = CSVDataSource(temp_csv_latin1_file, encoding="auto")
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_fichier_inexistant_leve_exception(self):
        """Vérifie que la lecture d'un fichier absent lève KidasConnectionError."""
        source = CSVDataSource("/fichier/absent.csv")
        with pytest.raises(KidasConnectionError):
            source.read()

    def test_read_met_a_jour_last_read(self, temp_csv_file):
        """Vérifie que last_read est mis à jour après une lecture réussie."""
        source = CSVDataSource(temp_csv_file)
        assert source.last_read is None
        source.read()
        assert source.last_read is not None


class TestCSVDataSourceEcriture:
    """Tests d'écriture vers un fichier CSV."""

    def test_write_retourne_true(self, temp_csv_file, sample_df):
        """Vérifie que write() retourne True sur succès."""
        source = CSVDataSource(temp_csv_file)
        resultat = source.write(sample_df)
        assert resultat is True

    def test_write_puis_read_coherent(self, temp_csv_file, sample_df):
        """Vérifie qu'un DataFrame écrit puis relu est cohérent."""
        source = CSVDataSource(temp_csv_file)
        source.write(sample_df)
        df_relu = source.read()
        assert len(df_relu) == len(sample_df)
        assert list(df_relu.columns) == list(sample_df.columns)
