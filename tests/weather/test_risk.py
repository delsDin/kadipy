"""
Tests des indicateurs de risque climatique : sécheresse, Hurst, Markov, probabilité de pluie.
"""

import pytest
import numpy as np
import pandas as pd

from kadi.weather.risk import RiskIndicators
from kadi.weather.location import Location
from kadi.exceptions import InsufficientData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def risk_setup():
    """Jeu de données de base pour les tests de risque (120 jours, pluie uniforme)."""
    location = Location(latitude=9.3041, longitude=2.0890)
    dates = pd.date_range(start='2026-01-01', periods=120)
    precip_data = pd.Series([2.0] * 120, index=dates)
    return location, precip_data


@pytest.fixture
def risk_long_setup():
    """Série pluviométrique plus longue (365 jours) pour Hurst et Markov."""
    location = Location(latitude=6.5, longitude=2.0)
    # Alterne jours secs et jours humides avec un cycle de 7 jours
    dates = pd.date_range(start='2025-01-01', periods=365)
    precip = np.where(np.arange(365) % 7 < 3, 8.0, 0.0)
    precip_data = pd.Series(precip, index=dates)
    return location, precip_data


# ---------------------------------------------------------------------------
# Tests de l'indice de sécheresse (SPI)
# ---------------------------------------------------------------------------

def test_drought_index(risk_setup):
    """L'indice de sécheresse doit retourner un SPI et un niveau de sévérité."""
    location, precip_data = risk_setup
    risk = RiskIndicators(location, precip_data, pd.DataFrame())
    drought = risk.drought_index(window_months=3)

    assert 'spi_3month' in drought
    assert 'drought_severity' in drought


def test_drought_index_insufficient_data(risk_setup):
    """Un indice sur une série trop courte doit lever InsufficientData."""
    location, _ = risk_setup
    dates_court = pd.date_range(start='2026-01-01', periods=20)
    precip_court = pd.Series([2.0] * 20, index=dates_court)
    risk = RiskIndicators(location, precip_court, pd.DataFrame())

    with pytest.raises(InsufficientData):
        risk.drought_index(window_months=3)


# ---------------------------------------------------------------------------
# Tests de l'exposant de Hurst (R/S multi-échelle)
# ---------------------------------------------------------------------------

def test_hurst_retourne_valeur_entre_0_et_1(risk_long_setup):
    """L'exposant de Hurst doit être compris entre 0 et 1."""
    location, precip_data = risk_long_setup
    risk = RiskIndicators(location, precip_data, pd.DataFrame())
    h = risk.hurst_exponent()

    assert 0.0 < h < 1.0


def test_hurst_insufficient_data(risk_setup):
    """Hurst sur moins de 100 jours doit lever InsufficientData."""
    location, _ = risk_setup
    dates_court = pd.date_range(start='2026-01-01', periods=50)
    precip_court = pd.Series([3.0] * 50, index=dates_court)
    risk = RiskIndicators(location, precip_court, pd.DataFrame())

    with pytest.raises(InsufficientData):
        risk.hurst_exponent()


# ---------------------------------------------------------------------------
# Tests de la matrice de Markov
# ---------------------------------------------------------------------------

def test_markov_transition_probabilites_valides(risk_long_setup):
    """Les probabilités de Markov doivent être comprises entre 0 et 1."""
    location, precip_data = risk_long_setup
    risk = RiskIndicators(location, precip_data, pd.DataFrame())
    markov = risk.markov_transition(threshold_mm=1.0)

    assert 0.0 <= markov['p_wet_wet'] <= 1.0
    assert 0.0 <= markov['p_dry_wet'] <= 1.0
    assert 0.0 <= markov['p_wet_dry'] <= 1.0
    assert 0.0 <= markov['p_dry_dry'] <= 1.0


def test_markov_somme_transitions(risk_long_setup):
    """Les probabilités de transition d'un état doivent sommer à 1."""
    location, precip_data = risk_long_setup
    risk = RiskIndicators(location, precip_data, pd.DataFrame())
    markov = risk.markov_transition(threshold_mm=1.0)

    # Depuis un état humide : P(wet|wet) + P(dry|wet) = 1
    assert abs(markov['p_wet_wet'] + markov['p_wet_dry'] - 1.0) < 1e-6
    # Depuis un état sec : P(wet|dry) + P(dry|dry) = 1
    assert abs(markov['p_dry_wet'] + markov['p_dry_dry'] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Tests de la probabilité de pluie (Markov + prévisions API)
# ---------------------------------------------------------------------------

def test_rain_probability_structure(risk_long_setup):
    """rain_probability() doit retourner un message, une recommandation et 'tomorrow'."""
    location, precip_hist = risk_long_setup
    dates = pd.date_range(start='2026-06-01', periods=5)
    precip_forecast = pd.DataFrame({'precipitation': [0, 2.0, 15.0, 0, 1.0]}, index=dates)

    risk = RiskIndicators(location, precip_hist, precip_forecast)
    prob = risk.rain_probability(days_ahead=5)

    assert 'message' in prob
    assert 'recommendation' in prob
    assert 'tomorrow' in prob


def test_rain_probability_valeurs_entre_0_et_1(risk_long_setup):
    """Les probabilités par jour doivent être entre 0 et 1."""
    location, precip_hist = risk_long_setup
    dates = pd.date_range(start='2026-06-01', periods=3)
    precip_forecast = pd.DataFrame({'precipitation': [0.0, 10.0, 0.0]}, index=dates)

    risk = RiskIndicators(location, precip_hist, precip_forecast)
    prob = risk.rain_probability(days_ahead=3)

    # Vérification sur les clés numériques uniquement
    for key in ('tomorrow', '2_days', '3_days'):
        if key in prob:
            assert 0.0 <= prob[key] <= 1.0


def test_rain_probability_sans_historique(risk_setup):
    """Sans historique, Markov doit se rabattre sur les prévisions API sans planter."""
    location, _ = risk_setup
    dates = pd.date_range(start='2026-06-01', periods=3)
    precip_forecast = pd.DataFrame({'precipitation': [5.0, 10.0, 0.0]}, index=dates)

    # Historique vide — Markov doit échouer silencieusement
    risk = RiskIndicators(location, pd.Series(dtype=float), precip_forecast)
    prob = risk.rain_probability(days_ahead=3)

    assert 'tomorrow' in prob
