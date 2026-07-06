"""
Tests unitaires pour les sous-modules de kadi.market.
Vérifie le bon fonctionnement des classes Pricing, Forecasting,
Logistics et DecisionSupport.
"""

import pytest
import pandas as pd
import responses

from kadi.market import Market
from kadi.market.pricing import MarketPricing
from kadi.market.forecasting import MarketForecasting
from kadi.market.logistics import MarketLogistics
from kadi.market.decision_support import DecisionSupport
from kadi.market.data_ingestion import WFPDataBridgesClient


def test_pricing_normalize_units():
    """Teste la normalisation des unités de prix."""
    pricing = MarketPricing()
    # 100 000 XOF/Tonne doit devenir 100 XOF/kg
    result = pricing.normalize_units(100000.0, "XOF/Tonne", "maize")
    assert result == 100.0
    
    # Sans mention de Tonne, ça ne doit pas changer
    result_kg = pricing.normalize_units(300.0, "XOF/kg", "maize")
    assert result_kg == 300.0


def test_pricing_detect_anomalies():
    """Teste la détection d'anomalies par Z-score."""
    pricing = MarketPricing()
    # Création d'une série avec une anomalie évidente (1000)
    df = pd.DataFrame({'price': [100, 105, 95, 102, 98, 1000]})
    df_result = pricing.detect_anomalies(df)
    
    # Vérification que l'anomalie est bien détectée (index 5)
    assert df_result.iloc[5]['is_anomaly'] == True
    # Vérification qu'une valeur normale n'est pas détectée (index 0)
    assert df_result.iloc[0]['is_anomaly'] == False


def test_forecasting_predict_price():
    """Teste la structure de retour du module de prévision."""
    forecaster = MarketForecasting()
    res = forecaster.predict_price("maize", "cotonou", days_ahead=7)
    
    # Vérifie la présence des clés essentielles
    assert 'predicted_price' in res
    assert 'low_90' in res
    assert 'high_90' in res
    
    # Vérifie la cohérence des intervalles
    assert res['low_90'] <= res['predicted_price'] <= res['high_90']


@responses.activate
def test_logistics_transfer_cost_and_distance():
    """Teste la récupération dynamique de la distance via OSRM et les coûts."""
    import os
    test_cache_file = ".test_osrm_cache.json"
    if os.path.exists(test_cache_file):
        os.remove(test_cache_file)
        
    logistics = MarketLogistics(cache_file=test_cache_file)
    
    # Mock Nominatim
    responses.add(
        responses.GET,
        "https://nominatim.openstreetmap.org/search",
        json=[{"lon": "2.433", "lat": "6.366"}],
        status=200,
        match=[responses.matchers.query_param_matcher({"q": "Cotonou, Benin", "format": "json", "limit": "1"})]
    )
    responses.add(
        responses.GET,
        "https://nominatim.openstreetmap.org/search",
        json=[{"lon": "2.633", "lat": "9.333"}],
        status=200,
        match=[responses.matchers.query_param_matcher({"q": "Parakou, Benin", "format": "json", "limit": "1"})]
    )
    
    # Mock OSRM
    responses.add(
        responses.GET,
        "http://router.project-osrm.org/route/v1/driving/2.433,6.366;2.633,9.333",
        json={
            "code": "Ok",
            "routes": [{"distance": 263000}]
        },
        status=200,
        match=[responses.matchers.query_param_matcher({"overview": "false"})]
    )
    
    # Test
    res = logistics.calculate_transfer_cost("Cotonou", "Parakou")
    
    # Vérifie la distance
    assert res['details']['distance_km'] == 263.0
    # Vérifie que le coût total est calculé
    assert res['total_cost_cfa'] > 0
    
    # Nettoyage
    if os.path.exists(test_cache_file):
        os.remove(test_cache_file)


def test_decision_support_arbitrage():
    """Teste la recommandation d'arbitrage."""
    decision = DecisionSupport()
    # Test avec la logistique désactivée (valeur par défaut utilisée)
    res = decision.arbitrage_decision("maize", "Cotonou", "Parakou", qty_tons=10.0)
    
    # Vérifie la structure de la réponse
    assert 'recommandation' in res
    assert 'gain_net_percent' in res
    # Le gain dépend des constantes internes (actuellement prix dest: 350, origine: 250)


def test_market_facade():
    """Teste l'initialisation de la façade principale Market."""
    market = Market(9.30, 2.08, "Abomey")
    
    # Vérifie que les coordonnées sont bien enregistrées
    assert market.location == "Abomey"
    
    # Vérifie que tous les sous-modules sont bien initialisés
    assert market.pricing is not None
    assert market.forecasting is not None
    assert market.logistics is not None
    assert market.decision_support is not None


@responses.activate
def test_wfp_client_fetch_prices():
    """Teste la récupération de données via l'API WFP DataBridges."""
    client = WFPDataBridgesClient()
    # On force un token factice pour bypasser la vérification locale
    client.token = "fake_token_for_test"
    
    # Mock de la réponse de l'API
    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/MarketPrices/alldata",
        json={
            "items": [
                {"CommodityPriceDate": "2023-01-01T00:00:00", "ActualPrice": 250, "UnitName": "KG"},
                {"CommodityPriceDate": "2023-01-02T00:00:00", "ActualPrice": 260, "UnitName": "KG"}
            ]
        },
        status=200
    )
    
    # Appel de la méthode
    df = client.get_market_prices("savalou_market", "maize")
    
    # Vérifications
    assert not df.empty
    assert len(df) == 2
    assert "date" in df.columns
    assert "price" in df.columns
    assert df.iloc[0]["price"] == 250


@responses.activate
def test_wfp_client_fetch_ids_success():
    """Teste la récupération dynamique des IDs avec succès."""
    import os
    test_cache = ".test_wfp_cache.json"
    if os.path.exists(test_cache):
        os.remove(test_cache)
        
    client = WFPDataBridgesClient(cache_file=test_cache)
    client.token = "fake_token"
    
    # Mock Commodities
    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Commodities/List",
        json={"items": [{"commodityID": 999, "commodityName": "Super Maize"}]},
        status=200
    )
    
    # Mock Markets
    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Markets/List",
        json={"items": [{"marketID": 888, "marketName": "Super Market"}]},
        status=200,
        match=[responses.matchers.query_param_matcher({"CountryCode": "BEN"})]
    )
    
    c_id = client._get_commodity_id("super maize")
    m_id = client._get_market_id("super market")
    
    assert c_id == 999
    assert m_id == 888
    
    if os.path.exists(test_cache):
        os.remove(test_cache)

@responses.activate
def test_wfp_client_fetch_ids_fallback():
    """Teste le fallback sur les dictionnaires en dur quand l'API échoue (401)."""
    import os
    test_cache = ".test_wfp_cache.json"
    if os.path.exists(test_cache):
        os.remove(test_cache)
        
    client = WFPDataBridgesClient(cache_file=test_cache)
    client.token = "fake_token"
    
    # Mock erreur 401
    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Commodities/List",
        status=401
    )
    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Markets/List",
        status=401
    )
    
    # Le système doit utiliser le mapping de secours
    c_id = client._get_commodity_id("maize")
    m_id = client._get_market_id("savalou")
    
    assert c_id == 51
    assert m_id == 1234
    
    if os.path.exists(test_cache):
        os.remove(test_cache)
