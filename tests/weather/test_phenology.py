"""
Tests de phénologie : onset, cessation, GDD.
Couvre les régimes unimodal (Nord) et bimodal (Sud, Centre).
"""

import pytest
import numpy as np
import pandas as pd

from kadi.weather.phenology import Phenology
from kadi.weather.location import Location
from kadi.exceptions import DataError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nord_setup():
    """Données pour la zone Nord (régime unimodal, Sivakumar)."""
    location = Location(latitude=9.3041, longitude=2.0890)
    dates = pd.date_range(start='2026-05-01', periods=60)

    # Simule une période déclenchante : 25 mm sur les 3 premiers jours,
    # puis des jours modérés sans séquence sèche prolongée.
    precip = [25.0, 10.0, 8.0] + [3.0] * 57
    precip_data = pd.Series(precip, index=dates)

    temp_df = pd.DataFrame({
        'temperature_min': [22.0] * 60,
        'temperature_max': [32.0] * 60,
        'temperature_mean': [27.0] * 60,
    }, index=dates)

    return location, precip_data, temp_df


@pytest.fixture
def sud_bimodal_setup():
    """Données pour la zone Sud (régime bimodal, Walter-Anyadike)."""
    location = Location(latitude=6.5, longitude=2.0)
    dates = pd.date_range(start='2026-01-01', periods=365)

    # Deux saisons de pluies : mars-mai (S1) et sept-oct (S2)
    precip = np.zeros(365)
    precip[60:120] = 60.0    # S1 : environ mars-avril
    precip[240:290] = 60.0   # S2 : environ sept-oct
    precip_data = pd.Series(precip, index=dates)

    temp_df = pd.DataFrame({
        'temperature_min': [22.0] * 365,
        'temperature_max': [32.0] * 365,
        'temperature_mean': [27.0] * 365,
    }, index=dates)

    return location, precip_data, temp_df


# ---------------------------------------------------------------------------
# Tests des degrés-jours de croissance (GDD)
# ---------------------------------------------------------------------------

def test_growing_degree_days(nord_setup):
    """Le GDD accumulé sur 10 jours avec Tbase=10, Tmoy=27 doit être 170."""
    location, precip_data, temp_df = nord_setup
    pheno = Phenology(location, precip_data, temp_df)
    gdd = pheno.growing_degree_days('maize', '2026-05-01', '2026-05-10')

    assert gdd['gdd_accumulated'] == 170.0
    assert gdd['crop'] == 'maize'


@pytest.mark.parametrize("crop", ["cassava", "manioc"])
def test_gdd_manioc(nord_setup, crop):
    """Le code canonique et son alias utilisent les paramètres du manioc."""
    pheno = Phenology(*nord_setup)

    gdd = pheno.gdd(crop=crop, start="2026-05-01", end="2026-05-10")

    assert gdd["crop"] == crop
    assert gdd["gdd_accumulated"] == 130.0
    assert gdd["gdd_total_cycle"] == 3000


def test_growing_degree_days_insufficient_data(nord_setup):
    """Un GDD sur des données vides doit lever DataError."""
    location, _, _ = nord_setup
    pheno = Phenology(location, pd.Series(dtype=float), pd.DataFrame())
    with pytest.raises(DataError):
        pheno.growing_degree_days('maize', '2026-05-01', '2026-05-10')


def test_gdd_temperatures_manquantes_leve_data_error():
    """Une période sans aucune température moyenne valide doit lever DataError."""
    location = Location(lat=10.0, lon=2.0, name="Natitingou")
    dates = pd.date_range("2025-05-01", periods=2)
    precip = pd.Series([0.0, 0.0], index=dates)

    # Tmin et Tmax entièrement manquants
    temp_nan = pd.DataFrame(
        {"temperature_min": [np.nan, np.nan], "temperature_max": [np.nan, np.nan]},
        index=dates,
    )
    with pytest.raises(DataError):
        Phenology(location, precip, temp_nan).gdd("maize", dates[0], dates[-1])

    # Une seule colonne manquante suffit à rendre tmean inexploitable
    temp_partiel = pd.DataFrame(
        {"temperature_min": [np.nan, np.nan], "temperature_max": [30.0, 32.0]},
        index=dates,
    )
    with pytest.raises(DataError):
        Phenology(location, precip, temp_partiel).gdd("maize", dates[0], dates[-1])

    # Températures valides mais sous Tbase : 0.0 reste attendu
    temp_froid = pd.DataFrame(
        {"temperature_min": [5.0, 6.0], "temperature_max": [8.0, 9.0]},
        index=dates,
    )
    res_froid = Phenology(location, precip, temp_froid).gdd(
        "maize", dates[0], dates[-1]
    )
    assert res_froid["gdd_accumulated"] == 0.0


# ---------------------------------------------------------------------------
# Tests de l'onset
# ---------------------------------------------------------------------------

def test_onset_nord_retourne_onset_date(nord_setup):
    """L'onset en zone Nord doit retourner une clé onset_date non nulle."""
    location, precip_data, temp_df = nord_setup
    pheno = Phenology(location, precip_data, temp_df)
    onset = pheno.onset()

    assert 'onset_date' in onset
    assert onset['onset_date'] is not None
    assert onset['algorithm'] == 'Sivakumar'


def test_onset_nord_pas_de_s2(nord_setup):
    """En zone Nord (unimodal), onset_2 doit être None."""
    location, precip_data, temp_df = nord_setup
    pheno = Phenology(location, precip_data, temp_df)
    onset = pheno.onset()

    assert 'onset_2' in onset
    assert onset['onset_2'] is None


def test_onset_bimodal_retourne_deux_saisons(sud_bimodal_setup):
    """En zone Sud (bimodal), onset() doit retourner onset_1 et onset_2."""
    location, precip_data, temp_df = sud_bimodal_setup
    pheno = Phenology(location, precip_data, temp_df)
    onset = pheno.onset()

    assert 'onset_1' in onset
    assert 'onset_2' in onset
    assert onset['algorithm'] == 'Walter-Anyadike bimodal'


def test_onset_bimodal_retrocompatibilite(sud_bimodal_setup):
    """La clé 'onset_date' doit être l'alias de 'onset_1' (rétrocompatibilité)."""
    location, precip_data, temp_df = sud_bimodal_setup
    pheno = Phenology(location, precip_data, temp_df)
    onset = pheno.onset()

    assert onset['onset_date'] == onset['onset_1']


def test_onset_donnees_vides(nord_setup):
    """Un onset sur des données vides doit lever DataError."""
    location, _, temp_df = nord_setup
    pheno = Phenology(location, pd.Series(dtype=float), temp_df)
    with pytest.raises(DataError):
        pheno.onset()
