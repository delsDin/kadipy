# -*- coding: utf-8 -*-
"""
Tests pour le point d'entrée racine kadi et le module kadi.io.

Ce fichier vérifie l'export des classes principales, les fonctions d'aide read_*,
ainsi que l'émission des avertissements de déprécation lors de l'accès aux anciens noms.
"""

import warnings
import pytest
import kadi
import kadi.io


def test_root_exports_new_names():
    """
    Vérifie l'exportation des nouveaux noms de classes depuis la racine kadi.
    """
    # Vérification des classes principales
    assert kadi.Weather is not None
    assert kadi.Market is not None
    assert kadi.Cleaner is not None
    assert kadi.Validator is not None
    assert kadi.Normalizer is not None
    assert kadi.Pipeline is not None
    assert kadi.Cache is not None

    # Vérification des classes de sources
    assert kadi.CSVSource is not None
    assert kadi.ExcelSource is not None
    assert kadi.JSONSource is not None
    assert kadi.NetCDFSource is not None
    assert kadi.APISource is not None


def test_io_module_exports():
    """
    Vérifie l'exportation des classes et fonctions du module kadi.io.
    """
    # Vérification des classes du module io
    assert kadi.io.CSVSource is kadi.CSVSource
    assert kadi.io.ExcelSource is kadi.ExcelSource
    assert kadi.io.JSONSource is kadi.JSONSource
    assert kadi.io.NetCDFSource is kadi.NetCDFSource
    assert kadi.io.APISource is kadi.APISource

    # Vérification des fonctions utilitaires du module io
    assert callable(kadi.io.read_csv)
    assert callable(kadi.io.read_excel)
    assert callable(kadi.io.read_json)
    assert callable(kadi.io.read_netcdf)


def test_root_read_functions():
    """
    Vérifie que les fonctions read_* sont disponibles à la racine de kadi.
    """
    # Contrôle de la présence des fonctions read_* à la racine
    assert kadi.read_csv is kadi.io.read_csv
    assert kadi.read_excel is kadi.io.read_excel
    assert kadi.read_json is kadi.io.read_json
    assert kadi.read_netcdf is kadi.io.read_netcdf


def test_deprecated_aliases_warning():
    """
    Vérifie que l'accès aux anciens noms émet un avertissement DeprecationWarning.
    """
    # Liste des couples d'anciens noms et de leurs nouvelles classes attendues
    deprecated_mapping = [
        ("CSVDataSource", kadi.CSVSource),
        ("ExcelDataSource", kadi.ExcelSource),
        ("JSONDataSource", kadi.JSONSource),
        ("NetCDFDataSource", kadi.NetCDFSource),
        ("APIDataSource", kadi.APISource),
        ("DataCleaner", kadi.Cleaner),
        ("DataValidator", kadi.Validator),
        ("DataNormalizer", kadi.Normalizer),
        ("WeatherSession", kadi.Weather),
        ("MarketSession", kadi.Market),
    ]

    # Test de chaque nom obsolète pour valider l'avertissement et la classe retournée
    for old_name, expected_cls in deprecated_mapping:
        with pytest.deprecated_call():
            cls = getattr(kadi, old_name)
            assert cls is expected_cls


def test_invalid_attribute_error():
    """
    Vérifie qu'un attribut inexistant lève bien une exception AttributeError.
    """
    # Tentative d'accès à un attribut inconnu
    with pytest.raises(AttributeError):
        _ = kadi.AttributInexistant
