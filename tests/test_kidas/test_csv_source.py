# -*- coding: utf-8 -*-
"""Tests unitaires pour la classe CSVSource."""

import os
import warnings

import pandas as pd
import pytest

from kadi.kidas import CSVSource
from kadi.exceptions import ConnectError, ReadError


class TestCSVSourceValidation:
    """Tests de validation de la connexion et des métadonnées."""

    def test_ping_fichier_existant(self, temp_csv_file):
        """Vérifie qu'un fichier existant est correctement détecté comme accessible."""
        source = CSVSource(temp_csv_file)
        assert source.ping() is True

    def test_ping_fichier_absent(self):
        """Vérifie qu'un fichier inexistant retourne False."""
        source = CSVSource("/chemin/inexistant/fichier.csv")
        assert source.ping() is False

    def test_info_retourne_dict_complet(self, temp_csv_file):
        """Vérifie que info() retourne toutes les clés attendues."""
        source = CSVSource(temp_csv_file)
        meta = source.info()
        # Vérification des clés obligatoires
        for cle in ("path", "kind", "encoding", "sep", "rows", "cols", "size_kb"):
            assert cle in meta, f"Clé manquante dans les métadonnées : '{cle}'"

    def test_info_kind_csv(self, temp_csv_file):
        """Vérifie que le type de source est bien 'csv'."""
        source = CSVSource(temp_csv_file)
        assert source.info()["kind"] == "csv"

    def test_retrocompatibilite_csvdatasource_emet_warning(self, temp_csv_file):
        """Vérifie que l'accès via l'ancien nom CSVDataSource émet un DeprecationWarning."""
        import kadi.kidas.sources.csv_source as mod
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Accès via l'ancien nom (intercepté par __getattr__)
            ancien_cls = mod.CSVDataSource
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "CSVDataSource" in str(w[0].message)
        # La classe retournée est bien CSVSource
        assert ancien_cls is CSVSource


class TestCSVSourceDetection:
    """Tests de détection automatique (encodage, délimiteur)."""

    def test_sniff_encoding_utf8(self, temp_csv_file):
        """Vérifie que chardet détecte un fichier UTF-8."""
        source = CSVSource(temp_csv_file, encoding="auto")
        encodage = source._sniff_encoding()
        assert encodage is not None
        assert isinstance(encodage, str)

    def test_sniff_sep_virgule(self, temp_csv_file):
        """Vérifie que le délimiteur virgule est correctement détecté."""
        source = CSVSource(temp_csv_file, sep="auto")
        delimiteur = source._sniff_sep()
        assert delimiteur == ","

    def test_sniff_sep_point_virgule(self, temp_csv_semicolon_file):
        """Vérifie que le délimiteur point-virgule est correctement détecté."""
        source = CSVSource(temp_csv_semicolon_file, sep="auto")
        delimiteur = source._sniff_sep()
        assert delimiteur == ";"


class TestCSVSourceLecture:
    """Tests de lecture du fichier CSV."""

    def test_read_retourne_dataframe(self, temp_csv_file):
        """Vérifie que read() retourne un pandas DataFrame non vide."""
        source = CSVSource(temp_csv_file)
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_n_limite_lignes(self, temp_csv_file):
        """Vérifie que le paramètre n limite correctement le nombre de lignes."""
        source = CSVSource(temp_csv_file)
        df = source.read(n=2)
        assert len(df) == 2

    def test_read_fichier_latin1(self, temp_csv_latin1_file):
        """Vérifie la lecture robuste d'un fichier encodé en Latin-1."""
        source = CSVSource(temp_csv_latin1_file, encoding="auto")
        df = source.read()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_read_fichier_inexistant_leve_exception(self):
        """Vérifie que la lecture d'un fichier absent lève ConnectError."""
        source = CSVSource("/fichier/absent.csv")
        with pytest.raises(ConnectError):
            source.read()

    def test_read_met_a_jour_last_read(self, temp_csv_file):
        """Vérifie que last_read est mis à jour après une lecture réussie."""
        source = CSVSource(temp_csv_file)
        assert source.last_read is None
        source.read()
        assert source.last_read is not None


class TestCSVSourceEcriture:
    """Tests d'écriture vers un fichier CSV."""

    def test_write_retourne_true(self, temp_csv_file, sample_df):
        """Vérifie que write() retourne True sur succès."""
        source = CSVSource(temp_csv_file)
        resultat = source.write(sample_df)
        assert resultat is True

    def test_write_puis_read_coherent(self, temp_csv_file, sample_df):
        """Vérifie qu'un DataFrame écrit puis relu est cohérent."""
        source = CSVSource(temp_csv_file)
        source.write(sample_df)
        df_relu = source.read()
        assert len(df_relu) == len(sample_df)
        assert list(df_relu.columns) == list(sample_df.columns)
