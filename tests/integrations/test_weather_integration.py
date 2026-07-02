import pytest
import os
from kadi.weather.session import WeatherSession
from kadi.exceptions import InsufficientData

@pytest.fixture
def session():
    """Initialise une session pour Parakou (Nord Bénin) pour les tests d'intégration."""
    # Parakou : Latitude ~9.3, Longitude ~2.6
    return WeatherSession(latitude=9.3333, longitude=2.6333, name="Parakou")

@pytest.mark.integration
def test_forecast_integration(session):
    """Vérifie que la prévision récupère bien les données de l'API Open-Meteo."""
    res = session.forecast(days=3)
    
    assert 'data' in res
    assert 'location' in res
    assert res['location']['name'] == "Parakou"
    assert len(res['data']) == 3
    
    # Vérifie la présence des colonnes attendues
    first_day = res['data'][0]
    assert 'temperature_min' in first_day
    assert 'temperature_max' in first_day
    assert 'precipitation' in first_day

@pytest.mark.integration
def test_historical_integration(session):
    """Vérifie que l'historique récupère bien les données (Open-Meteo / CHIRPS)."""
    # 1 mois d'historique pour accélérer le test
    df = session.historical(months_back=1)
    
    assert not df.empty
    assert 'temperature_min' in df.columns
    assert 'precipitation' in df.columns
    assert len(df) >= 28  # Au moins 28 jours pour 1 mois

@pytest.mark.integration
def test_phenology_and_hydrology_integration(session):
    """Vérifie que le bilan hydrique et les GDD fonctionnent avec de vraies données."""
    
    # Calcul des GDD pour le maïs sur les 30 derniers jours
    import pandas as pd
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=30)
    
    try:
        gdd = session.growing_degree_days(
            crop='maize', 
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        assert gdd['crop'] == 'maize'
        assert gdd['gdd_accumulated'] >= 0
    except InsufficientData:
        # En cas d'absence de données locales complètes, on ignore gracieusement
        pytest.skip("Données historiques insuffisantes pour le calcul GDD.")

    try:
        wb = session.water_balance(crop='maize', soil_type='ferrugineux')
        assert not wb.empty
        assert 'deficit_eau' in wb.columns
        assert 'reserve_utile' in wb.columns
    except InsufficientData:
        pytest.skip("Données historiques insuffisantes pour le calcul du bilan hydrique.")

@pytest.mark.integration
def test_risk_indicators_integration(session):
    """Vérifie les indicateurs de risque en utilisant les prévisions réelles."""
    try:
        prob = session.rain_probability(days_ahead=3)
        assert 'message' in prob
        assert 'recommendation' in prob
        assert 'tomorrow' in prob
    except InsufficientData:
        pytest.skip("Données de prévision insuffisantes pour la probabilité de pluie.")