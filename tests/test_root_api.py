# -*- coding: utf-8 -*-
"""
Tests pour le point d'entrée racine kadi et le module kadi.io.

Ce fichier vérifie l'export des classes principales, les fonctions d'aide read_*, write_*,
les fonctions I/O génériques (write, info, ping), ainsi que l'émission des avertissements
de déprécation lors de l'accès aux anciens noms.
"""

import warnings
import pytest
import pandas as pd
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

    # Vérification des fonctions de lecture du module io
    assert callable(kadi.io.read_csv)
    assert callable(kadi.io.read_excel)
    assert callable(kadi.io.read_json)
    assert callable(kadi.io.read_netcdf)
    assert callable(kadi.io.read_api)

    # Vérification des fonctions d'écriture du module io
    assert callable(kadi.io.write_csv)
    assert callable(kadi.io.write_excel)
    assert callable(kadi.io.write_json)
    assert callable(kadi.io.write_netcdf)
    assert callable(kadi.io.write_api)

    # Vérification des fonctions génériques du module io
    assert callable(kadi.io.write)
    assert callable(kadi.io.info)
    assert callable(kadi.io.ping)


def test_root_io_functions():
    """
    Vérifie que les fonctions E/S sont disponibles à la racine de kadi.
    """
    # Contrôle des fonctions de lecture à la racine
    assert kadi.read_csv is kadi.io.read_csv
    assert kadi.read_excel is kadi.io.read_excel
    assert kadi.read_json is kadi.io.read_json
    assert kadi.read_netcdf is kadi.io.read_netcdf
    assert kadi.read_api is kadi.io.read_api

    # Contrôle des fonctions d'écriture et génériques à la racine
    assert kadi.write_csv is kadi.io.write_csv
    assert kadi.write_excel is kadi.io.write_excel
    assert kadi.write_json is kadi.io.write_json
    assert kadi.write is kadi.io.write
    assert kadi.info is kadi.io.info
    assert kadi.ping is kadi.io.ping


def test_generic_io_operations(tmp_path):
    """
    Vérifie le fonctionnement des fonctions génériques write, info et ping avec détection de format.

    Args:
        tmp_path (pathlib.Path): Dossier temporaire fourni par pytest.
    """
    # Création d'un DataFrame de données de test
    data = pd.DataFrame({"culture": ["Mais", "Riz"], "rendement": [2.5, 3.8]})
    csv_file = str(tmp_path / "test_data.csv")

    # Écriture générique avec détection de l'extension .csv
    success = kadi.io.write(data, csv_file)
    assert success is True

    # Récupération des métadonnées avec la fonction générique info
    meta = kadi.io.info(csv_file)
    assert isinstance(meta, dict)
    assert meta["kind"] == "csv"

    # Vérification d'accessibilité avec la fonction générique ping
    assert kadi.io.ping(csv_file) is True

    # Relecture des données écrites pour valider le contenu
    df_read = kadi.io.read_csv(csv_file)
    assert len(df_read) == 2


def test_detect_source_unsupported_extension():
    """
    Vérifie qu'une extension inconnue lève une exception ValueError.
    """
    # Tentative d'utilisation d'une extension non supportée
    with pytest.raises(ValueError, match="Impossible de déterminer automatiquement"):
        kadi.io.ping("fichier.extension_inconnue")


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
