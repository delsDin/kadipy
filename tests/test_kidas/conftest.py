# -*- coding: utf-8 -*-
"""Fixtures partagées pour les tests du module kidas."""

import io
import json
import os
import tempfile

import numpy as np
import pandas as pd
import pytest


# =============================================================================
# Fixtures : DataFrames de test
# =============================================================================

@pytest.fixture
def sample_df():
    """Retourne un DataFrame agricole minimal pour les tests de base."""
    return pd.DataFrame({
        "culture": ["maïs", "Niébé", "igname", "maïs", None],
        "rendement_kg": [1500.0, 800.0, 2000.0, 1500.0, np.nan],
        "marche": ["Dantokpa cotonou", "Parakou", "Bohicon", "Dantokpa", "Kandi"],
        "date_recolte": ["2024-01-15", "2024-02-20", "2024/03/10", "15-01-2024", None],
        "lat": [6.366, 9.337, 7.181, 6.366, 11.133],
        "lon": [2.437, 2.629, 2.067, 2.437, 2.940],
    })


@pytest.fixture
def sample_df_with_duplicates(sample_df):
    """Retourne un DataFrame contenant des lignes dupliquées."""
    return pd.concat([sample_df, sample_df.iloc[[0]]], ignore_index=True)


@pytest.fixture
def sample_df_with_outliers():
    """Retourne un DataFrame contenant des outliers évidents."""
    return pd.DataFrame({
        "culture": ["maïs"] * 10,
        "rendement_kg": [1500, 1600, 1450, 1550, 1480, 1520, 15000, 1530, 1510, 1490],
    })


# =============================================================================
# Fixtures : fichiers temporaires
# =============================================================================

@pytest.fixture
def temp_csv_file(sample_df):
    """Crée un fichier CSV temporaire UTF-8 avec délimiteur virgule."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        sample_df.to_csv(f, index=False)
        chemin = f.name
    yield chemin
    # Nettoyage après le test
    os.unlink(chemin)


@pytest.fixture
def temp_csv_semicolon_file(sample_df):
    """Crée un fichier CSV temporaire avec délimiteur point-virgule (style français)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        sample_df.to_csv(f, index=False, sep=";")
        chemin = f.name
    yield chemin
    os.unlink(chemin)


@pytest.fixture
def temp_csv_latin1_file(sample_df):
    """Crée un fichier CSV temporaire encodé Latin-1."""
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False
    ) as f:
        chemin = f.name
    sample_df.to_csv(chemin, index=False, encoding="latin-1")
    yield chemin
    os.unlink(chemin)


@pytest.fixture
def temp_excel_file(sample_df):
    """Crée un fichier Excel temporaire (.xlsx) avec une feuille de données."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        chemin = f.name
    sample_df.to_excel(chemin, index=False, sheet_name="Recoltes")
    yield chemin
    os.unlink(chemin)


@pytest.fixture
def temp_json_file(sample_df):
    """Crée un fichier JSON temporaire (orientation 'records')."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        sample_df.to_json(f, orient="records", force_ascii=False, indent=2)
        chemin = f.name
    yield chemin
    os.unlink(chemin)


@pytest.fixture
def nested_json_dict():
    """Retourne un dictionnaire JSON imbriqué représentant une réponse API."""
    return {
        "metadata": {"source": "WFP VAM", "date": "2024-01-01"},
        "data": [
            {
                "location": {"country": "Benin", "city": "Cotonou"},
                "crop": "maize",
                "price_xof": 350,
            },
            {
                "location": {"country": "Benin", "city": "Parakou"},
                "crop": "cowpea",
                "price_xof": 500,
            },
        ],
    }


@pytest.fixture
def mock_api_response():
    """Retourne une réponse API simulée sous forme de liste de dictionnaires."""
    return [
        {"culture": "maize", "prix_xof": 350, "marche": "Dantokpa"},
        {"culture": "cowpea", "prix_xof": 500, "marche": "Parakou"},
    ]
