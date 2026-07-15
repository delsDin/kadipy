# -*- coding: utf-8 -*-
"""
Tests unitaires pour kadi.market.backtesting.MarketBacktester.

On utilise des prix mockés pour s'affranchir de l'API WFP et garantir
la reproductibilité des tests sur toutes les machines.

Cas couverts :
    - test_run_retourne_resultats            : run() retourne une liste non vide.
    - test_run_colonnes_presentes            : chaque résultat contient les clés attendues.
    - test_run_historique_trop_court         : historique insuffisant -> liste vide.
    - test_summary_report_metriques_valides  : summary_report() retourne des métriques cohérentes.
    - test_summary_sans_run_leve_erreur      : summary_report() sans run() lève RuntimeError.
    - test_metriques_mae_rmse_cohérence      : RMSE >= MAE mathématiquement.
    - test_mape_exclut_prix_nuls             : _calculer_mape() ignore les zéros.
    - test_precision_directionnelle          : calcul de la précision directionnelle.
"""

import numpy as np
import pandas as pd
import pytest

from kadi.market.backtesting import MarketBacktester
from kadi.market.forecasting import MarketForecasting


# ------------------------------------------------------------------
# Fixtures : données de prix synthétiques
# ------------------------------------------------------------------

def _historique_valide(nb_jours: int = 120) -> pd.DataFrame:
    """Génère un historique de prix synthétique.

    Produit une série de prix journaliers simulant une tendance haussière
    légère avec du bruit aléatoire, adaptée aux tests unitaires.

    Args:
        nb_jours (int): Nombre de jours à générer. Défaut : 120.

    Returns:
        pd.DataFrame: DataFrame avec colonnes 'date' et 'price'.
    """
    # Initialisation du générateur aléatoire pour la reproductibilité
    np.random.seed(42)

    # Dates quotidiennes sur nb_jours jours
    dates = pd.date_range(start="2025-01-01", periods=nb_jours, freq="D")

    # Prix simulés : tendance légèrement haussière + bruit gaussien
    prix = 250 + np.arange(nb_jours) * 0.5 + np.random.normal(0, 10, nb_jours)

    return pd.DataFrame({"date": dates, "price": prix})


@pytest.fixture
def backtester() -> MarketBacktester:
    """Retourne une instance de MarketBacktester avec un forecaster par défaut."""
    return MarketBacktester(forecaster=MarketForecasting())


@pytest.fixture
def historique_valide() -> pd.DataFrame:
    """Retourne un historique de 120 jours avec des prix synthétiques."""
    return _historique_valide(nb_jours=120)


@pytest.fixture
def historique_court() -> pd.DataFrame:
    """Retourne un historique trop court pour le backtesting (15 jours)."""
    return _historique_valide(nb_jours=15)


# ------------------------------------------------------------------
# Tests de la méthode run()
# ------------------------------------------------------------------

def test_run_retourne_resultats(backtester, historique_valide):
    """run() doit retourner une liste non vide avec un historique suffisant."""
    # Exécution du backtesting avec 3 fenêtres glissantes
    resultats = backtester.run(
        crop="maize",
        market="cotonou",
        historique=historique_valide,
        window_days=60,
        horizon_days=7,
        nb_fenetres=3,
    )

    # On s'attend à au moins une fenêtre évaluée
    assert isinstance(resultats, list), "Le résultat doit être une liste."
    assert len(resultats) > 0, "Au moins une fenêtre doit être évaluée."


def test_run_colonnes_presentes(backtester, historique_valide):
    """Chaque résultat de run() doit contenir toutes les clés attendues."""
    # Clés obligatoires dans chaque résultat de fenêtre
    cles_attendues = {
        "fenetre",
        "date_fin_train",
        "nb_train_pts",
        "prix_predit",
        "prix_reel_moyen",
        "mae",
        "rmse",
        "mape",
        "precision_dir",
        "is_simulated",
    }

    resultats = backtester.run(
        crop="rice",
        market="parakou",
        historique=historique_valide,
        window_days=60,
        horizon_days=7,
        nb_fenetres=3,
    )

    # Vérification des clés pour chaque fenêtre évaluée
    for fenetre in resultats:
        cles_manquantes = cles_attendues - set(fenetre.keys())
        assert not cles_manquantes, (
            f"Clés manquantes dans le résultat : {cles_manquantes}"
        )


def test_run_historique_trop_court(backtester, historique_court):
    """run() doit retourner une liste vide si l'historique est insuffisant."""
    resultats = backtester.run(
        crop="maize",
        market="cotonou",
        historique=historique_court,
        window_days=60,
        horizon_days=7,
        nb_fenetres=3,
    )

    # Un historique de 15 jours ne suffit pas pour window=60 + horizon=7
    assert resultats == [], (
        "Un historique trop court doit produire une liste vide."
    )


def test_run_historique_colonnes_manquantes(backtester):
    """run() doit retourner une liste vide si les colonnes obligatoires manquent."""
    # DataFrame sans la colonne 'price'
    df_incomplet = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=60)})

    resultats = backtester.run(
        crop="maize",
        market="cotonou",
        historique=df_incomplet,
        window_days=30,
        horizon_days=7,
        nb_fenetres=2,
    )

    assert resultats == [], (
        "Un historique sans colonne 'price' doit produire une liste vide."
    )


# ------------------------------------------------------------------
# Tests de la méthode summary_report()
# ------------------------------------------------------------------

def test_summary_report_metriques_valides(backtester, historique_valide):
    """summary_report() doit retourner des métriques numériques cohérentes."""
    # Exécution du backtesting préalable
    backtester.run(
        crop="maize",
        market="cotonou",
        historique=historique_valide,
        window_days=60,
        horizon_days=7,
        nb_fenetres=4,
    )

    rapport = backtester.summary_report()

    # Vérification de la structure du rapport
    assert "nb_fenetres_evaluees" in rapport
    assert "mae_moyen" in rapport
    assert "rmse_moyen" in rapport
    assert "mape_moyen" in rapport
    assert "precision_dir_moy" in rapport
    assert "pct_simule" in rapport
    assert "details" in rapport

    # Les métriques doivent être numériques et non-négatifs
    assert rapport["nb_fenetres_evaluees"] >= 1
    assert rapport["mae_moyen"] >= 0 or np.isnan(rapport["mae_moyen"])
    assert rapport["rmse_moyen"] >= 0 or np.isnan(rapport["rmse_moyen"])
    assert 0 <= rapport["pct_simule"] <= 100


def test_summary_sans_run_leve_erreur(backtester):
    """summary_report() doit lever RuntimeError si run() n'a pas été appelé."""
    with pytest.raises(RuntimeError, match="Appelez run()"):
        backtester.summary_report()


# ------------------------------------------------------------------
# Tests des méthodes de métriques (méthodes statiques)
# ------------------------------------------------------------------

def test_metriques_rmse_superieur_ou_egal_mae():
    """RMSE doit toujours être supérieur ou égal à MAE (propriété mathématique)."""
    # Données de test avec erreurs asymétriques
    y_reel = np.array([100.0, 110.0, 105.0, 120.0, 95.0])
    y_pred = np.array([102.0, 115.0, 100.0, 130.0, 90.0])

    mae = MarketBacktester._calculer_mae(y_reel, y_pred)
    rmse = MarketBacktester._calculer_rmse(y_reel, y_pred)

    # Le RMSE pénalise plus les grosses erreurs, donc RMSE >= MAE
    assert rmse >= mae, f"RMSE ({rmse:.2f}) doit être >= MAE ({mae:.2f})."


def test_mape_exclut_prix_nuls():
    """_calculer_mape() doit ignorer les observations avec un prix réel nul."""
    # Prix réel avec un zéro (division par zéro à éviter)
    y_reel = np.array([100.0, 0.0, 120.0])
    y_pred = np.array([110.0, 50.0, 130.0])

    mape = MarketBacktester._calculer_mape(y_reel, y_pred)

    # MAPE = moyenne(|100-110|/100, |120-130|/120) * 100
    # = moyenne(0.10, 0.0833) * 100 = 9.167%
    # L'observation avec prix réel = 0 est ignorée
    assert not np.isnan(mape), "MAPE ne doit pas être NaN si des prix valides existent."
    assert mape > 0, "MAPE doit être positif avec des prévisions imparfaites."


def test_precision_directionnelle_parfaite():
    """_calculer_precision_directionnelle() doit retourner 100 si toutes les directions sont correctes."""
    # Prévisions qui suivent exactement la tendance réelle
    y_reel = np.array([100.0, 110.0, 120.0, 115.0])
    y_pred = np.array([100.0, 108.0, 118.0, 114.0])  # même direction à chaque fois

    precision = MarketBacktester._calculer_precision_directionnelle(y_reel, y_pred)

    assert precision == 100.0, (
        f"Précision directionnelle parfaite attendue, obtenue {precision}."
    )


def test_mae_tableau_vide():
    """_calculer_mae() doit retourner NaN pour un tableau vide."""
    mae = MarketBacktester._calculer_mae(np.array([]), np.array([]))
    assert np.isnan(mae), "MAE doit être NaN pour un tableau vide."
