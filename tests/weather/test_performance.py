"""
Tests de performance du module kadi.weather.

Vérifie que les calculs respectent les contraintes de temps définies au
Cahier des Charges §8.2 : les opérations principales doivent s'exécuter
en moins de 1 seconde sur un historique de 10 ans (3 650 jours).
"""

import time
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from kadi.weather.hydrology import Hydrology
from kadi.weather.risk import RiskIndicators
from kadi.weather.location import Location

# Limite de temps autorisée (en secondes) pour chaque opération
LIMITE_SECONDES = 1.0

# Taille du jeu de données de performance : 10 ans de données quotidiennes
NB_JOURS = 3650


# ---------------------------------------------------------------------------
# Fixture de performance commune
# ---------------------------------------------------------------------------

@pytest.fixture
def donnees_10_ans():
    """Série de précipitations et températures sur 10 ans (3 650 jours)."""
    location = Location(latitude=9.3, longitude=2.0)
    dates = pd.date_range(start='2014-01-01', periods=NB_JOURS)

    # Précipitations aléatoires entre 0 et 10 mm/j
    np.random.seed(42)
    precip = pd.Series(np.random.uniform(0, 10, NB_JOURS), index=dates)

    temp_df = pd.DataFrame({
        'temperature_min': [22.0] * NB_JOURS,
        'temperature_max': [32.0] * NB_JOURS,
    }, index=dates)

    return location, precip, temp_df


# ---------------------------------------------------------------------------
# Tests de performance du bilan hydrique
# ---------------------------------------------------------------------------

@patch('kadi.weather.hydrology.Hydrology._resolve_soil_type_from_cache')
def test_performance_bilan_hydrique(mock_soil, donnees_10_ans):
    """compute_water_balance() sur 10 ans doit s'exécuter en moins de 1 seconde."""
    mock_soil.return_value = 'ferrugineux'
    location, precip, temp_df = donnees_10_ans

    hydro = Hydrology(location, precip, temp_df)

    debut = time.perf_counter()
    hydro.compute_water_balance()
    duree = time.perf_counter() - debut

    assert duree < LIMITE_SECONDES, (
        f"compute_water_balance() trop lent : {duree:.2f}s > {LIMITE_SECONDES}s"
    )


# ---------------------------------------------------------------------------
# Tests de performance des indicateurs de risque
# ---------------------------------------------------------------------------

def test_performance_hurst(donnees_10_ans):
    """hurst_exponent() sur 10 ans doit s'exécuter en moins de 1 seconde."""
    location, precip, _ = donnees_10_ans
    risk = RiskIndicators(location, precip, pd.DataFrame())

    debut = time.perf_counter()
    risk.hurst_exponent()
    duree = time.perf_counter() - debut

    assert duree < LIMITE_SECONDES, (
        f"hurst_exponent() trop lent : {duree:.2f}s > {LIMITE_SECONDES}s"
    )


def test_performance_markov(donnees_10_ans):
    """markov_transition() sur 10 ans doit s'exécuter en moins de 1 seconde."""
    location, precip, _ = donnees_10_ans
    risk = RiskIndicators(location, precip, pd.DataFrame())

    debut = time.perf_counter()
    risk.markov_transition()
    duree = time.perf_counter() - debut

    assert duree < LIMITE_SECONDES, (
        f"markov_transition() trop lent : {duree:.2f}s > {LIMITE_SECONDES}s"
    )


def test_performance_drought_index(donnees_10_ans):
    """drought_index() sur 10 ans doit s'exécuter en moins de 1 seconde."""
    location, precip, _ = donnees_10_ans
    risk = RiskIndicators(location, precip, pd.DataFrame())

    debut = time.perf_counter()
    risk.drought_index(window_months=3)
    duree = time.perf_counter() - debut

    assert duree < LIMITE_SECONDES, (
        f"drought_index() trop lent : {duree:.2f}s > {LIMITE_SECONDES}s"
    )
