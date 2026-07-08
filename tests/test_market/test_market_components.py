"""
Tests unitaires pour les sous-modules de kadi.market.
Vérifie le bon fonctionnement des classes Pricing, Forecasting,
Logistics et DecisionSupport, ainsi que les nouvelles fonctionnalités
de la Phase 1 (validation, normalisation, retry, is_simulated).
"""

import pytest
import pandas as pd
import responses

from kadi.market import Market
from kadi.market.pricing import MarketPricing
from kadi.market.forecasting import MarketForecasting
from kadi.market.logistics import MarketLogistics
from kadi.market.decision_support import DecisionSupport
from kadi.market.data_ingestion import WFPDataBridgesClient, _get_with_retry
from kadi.market._normalization import (
    normalize_crop_name,
    normalize_market_name,
    get_container_weight_kg,
    CROP_NAME_MAPPING,
)


# ==========================================================================
# Tests existants (conservés et stabilisés)
# ==========================================================================

def test_pricing_normalize_units_tonne():
    """Teste la conversion XOF/Tonne vers XOF/kg."""
    pricing = MarketPricing()
    # 100 000 XOF/Tonne doit devenir 100 XOF/kg
    result = pricing.normalize_units(100000.0, "XOF/Tonne", "maize")
    assert result == 100.0


def test_pricing_normalize_units_kg_inchange():
    """Teste qu'un prix déjà en XOF/kg reste inchangé."""
    pricing = MarketPricing()
    result = pricing.normalize_units(300.0, "XOF/kg", "maize")
    assert result == 300.0


def test_pricing_detect_anomalies():
    """Teste la détection d'anomalies par Z-score."""
    pricing = MarketPricing()
    # Série avec beaucoup de valeurs normales et une valeur aberrante
    prices = [100, 105, 95, 102, 98] * 10 + [1000]
    df = pd.DataFrame({"price": prices})
    df_result = pricing.detect_anomalies(df)

    # La valeur aberrante (index 50) doit être marquée
    assert df_result.iloc[50]["is_anomaly"] == True
    # Une valeur normale ne doit pas être marquée
    assert df_result.iloc[0]["is_anomaly"] == False


def test_forecasting_predict_price():
    """Teste la structure de retour du module de prévision."""
    forecaster = MarketForecasting()
    res = forecaster.predict_price("maize", "cotonou", days_ahead=7)

    # Présence des clés essentielles
    assert "predicted_price" in res
    assert "low_90" in res
    assert "high_90" in res

    # Cohérence des intervalles
    assert res["low_90"] <= res["predicted_price"] <= res["high_90"]


@responses.activate
def test_logistics_transfer_cost_and_distance():
    """Teste le calcul de la distance via OSRM et le coût de transfert."""
    import os
    test_cache_file = ".test_osrm_cache.json"
    if os.path.exists(test_cache_file):
        os.remove(test_cache_file)

    logistics = MarketLogistics(cache_file=test_cache_file)

    # Mock Nominatim pour Cotonou
    responses.add(
        responses.GET,
        "https://nominatim.openstreetmap.org/search",
        json=[{"lon": "2.433", "lat": "6.366"}],
        status=200,
        match=[responses.matchers.query_param_matcher(
            {"q": "Cotonou, Benin", "format": "json", "limit": "1"}
        )],
    )
    # Mock Nominatim pour Parakou
    responses.add(
        responses.GET,
        "https://nominatim.openstreetmap.org/search",
        json=[{"lon": "2.633", "lat": "9.333"}],
        status=200,
        match=[responses.matchers.query_param_matcher(
            {"q": "Parakou, Benin", "format": "json", "limit": "1"}
        )],
    )
    # Mock OSRM
    responses.add(
        responses.GET,
        "http://router.project-osrm.org/route/v1/driving/2.433,6.366;2.633,9.333",
        json={"code": "Ok", "routes": [{"distance": 263000}]},
        status=200,
        match=[responses.matchers.query_param_matcher({"overview": "false"})],
    )

    res = logistics.calculate_transfer_cost("Cotonou", "Parakou")

    assert res["details"]["distance_km"] == 263.0
    assert res["total_cost_cfa"] > 0

    if os.path.exists(test_cache_file):
        os.remove(test_cache_file)


def test_decision_support_arbitrage():
    """Teste la structure de la recommandation d'arbitrage."""
    decision = DecisionSupport()
    res = decision.arbitrage_decision("maize", "Cotonou", "Parakou", qty_tons=10.0)

    assert "recommandation" in res
    assert "gain_net_percent" in res


def test_market_facade():
    """Teste l'initialisation de la façade principale Market."""
    market = Market(9.30, 2.08, "Abomey")

    assert market.location == "Abomey"
    assert market.pricing is not None
    assert market.forecasting is not None
    assert market.logistics is not None
    assert market.decision_support is not None


@responses.activate
def test_wfp_client_fetch_prices():
    """Teste la récupération de données via l'API WFP DataBridges."""
    client = WFPDataBridgesClient()
    client.token = "fake_token_for_test"

    # Pré-remplir le cache des IDs pour éviter des appels non mockés
    # vers Commodities/List et Markets/List pendant la résolution des IDs
    client.cache["commodities"] = {"maize": 51}
    client.cache["markets"] = {"savalou_market": 1234}

    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/MarketPrices/alldata",
        json={
            "items": [
                {"CommodityPriceDate": "2023-01-01T00:00:00", "ActualPrice": 250, "UnitName": "KG"},
                {"CommodityPriceDate": "2023-01-02T00:00:00", "ActualPrice": 260, "UnitName": "KG"},
            ]
        },
        status=200,
    )

    df = client.get_market_prices("savalou_market", "maize")

    assert not df.empty
    assert len(df) == 2
    assert "date" in df.columns
    assert "price" in df.columns
    assert df.iloc[0]["price"] == 250
    # Les données venant de l'API réelle ne sont pas simulées
    assert df.iloc[0]["is_simulated"] == False


@responses.activate
def test_wfp_client_fetch_ids_success():
    """Teste la récupération dynamique des IDs depuis l'API WFP."""
    import os
    test_cache = ".test_wfp_cache.json"
    if os.path.exists(test_cache):
        os.remove(test_cache)

    client = WFPDataBridgesClient(cache_file=test_cache)
    client.token = "fake_token"

    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Commodities/List",
        json={"items": [{"commodityID": 999, "commodityName": "Super Maize"}]},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Markets/List",
        json={"items": [{"marketID": 888, "marketName": "Super Market"}]},
        status=200,
        match=[responses.matchers.query_param_matcher({"CountryCode": "BEN"})],
    )

    c_id = client._get_commodity_id("super maize")
    m_id = client._get_market_id("super market")

    assert c_id == 999
    assert m_id == 888

    if os.path.exists(test_cache):
        os.remove(test_cache)


@responses.activate
def test_wfp_client_fetch_ids_fallback():
    """Teste le fallback sur les dictionnaires locaux quand l'API renvoie 401."""
    import os
    test_cache = ".test_wfp_cache.json"
    if os.path.exists(test_cache):
        os.remove(test_cache)

    client = WFPDataBridgesClient(cache_file=test_cache)
    client.token = "fake_token"

    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Commodities/List",
        status=401,
    )
    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/Markets/List",
        status=401,
    )

    # Le système doit utiliser le mapping de secours sans lever d'exception
    c_id = client._get_commodity_id("maize")
    m_id = client._get_market_id("savalou")

    assert c_id == 51
    assert m_id == 1234

    if os.path.exists(test_cache):
        os.remove(test_cache)


@responses.activate
def test_logistics_fuel_price_fetch_success(monkeypatch):
    """Teste la récupération du prix du carburant depuis GitHub (mockée)."""
    monkeypatch.delenv("BENIN_FUEL_PRICE", raising=False)

    logistics = MarketLogistics()

    responses.add(
        responses.GET,
        "https://raw.githubusercontent.com/delsDin/kadipy/main/config/fuel_prices.json",
        json={"benin": {"essence": 750.0}},
        status=200,
    )

    price = logistics._fetch_fuel_price()
    assert price == 750.0


@responses.activate
def test_logistics_fuel_price_fetch_fallback(monkeypatch):
    """Teste le repli sur la valeur de config si GitHub échoue."""
    monkeypatch.delenv("BENIN_FUEL_PRICE", raising=False)

    logistics = MarketLogistics()

    responses.add(
        responses.GET,
        "https://raw.githubusercontent.com/delsDin/kadipy/main/config/fuel_prices.json",
        status=404,
    )

    price = logistics._fetch_fuel_price()
    # La valeur de repli configurée est 680.0
    assert price == 680.0


def test_logistics_fuel_price_env(monkeypatch):
    """Teste que la variable d'environnement a la priorité sur les autres sources."""
    monkeypatch.setenv("BENIN_FUEL_PRICE", "720.5")

    logistics = MarketLogistics()
    price = logistics._fetch_fuel_price()
    assert price == 720.5


# ==========================================================================
# Nouveaux tests Phase 1
# ==========================================================================

# --- Tests de validation des entrées (Market.__init__) ---

def test_market_validation_lat_hors_zone():
    """Teste que des coordonnées hors Bénin lèvent une ValueError."""
    with pytest.raises(ValueError, match="Latitude"):
        # Paris, France : hors zone Bénin
        Market(48.85, 2.35, "Paris")


def test_market_validation_lon_hors_zone():
    """Teste qu'une longitude hors Bénin lève une ValueError."""
    with pytest.raises(ValueError, match="Longitude"):
        # Latitude valide (9.30, dans la zone Bénin) mais longitude
        # hors plage (5.00 > 3.9) : seule l'erreur de longitude doit être levée
        Market(9.30, 5.00, "HorsZone")


def test_market_validation_lat_type_invalide():
    """Teste qu'une latitude de type incorrect lève une TypeError."""
    with pytest.raises(TypeError, match="latitude"):
        Market("six virgule trente", 2.08, "Abomey")


def test_market_validation_location_vide():
    """Teste qu'un nom de lieu vide lève une ValueError."""
    with pytest.raises(ValueError, match="vide"):
        Market(9.30, 2.08, "   ")


def test_market_validation_location_type_invalide():
    """Teste qu'un nom de lieu de type incorrect lève une TypeError."""
    with pytest.raises(TypeError, match="chaîne"):
        Market(9.30, 2.08, 42)


def test_market_coordonnees_valides_extremes():
    """Teste que les coordonnées aux limites du Bénin sont acceptées."""
    # Coin nord-est du Bénin (zone de Malanville)
    marche = Market(11.80, 3.40, "Malanville")
    assert marche.location == "Malanville"

    # Coin sud-ouest (zone de Cotonou)
    marche_sud = Market(6.40, 2.40, "Cotonou")
    assert marche_sud.location == "Cotonou"


# --- Tests de normalisation des cultures (_normalization.py) ---

def test_normalize_crop_name_francais():
    """Teste la conversion de noms français vers les codes standards."""
    assert normalize_crop_name("Maïs") == "maize"
    assert normalize_crop_name("riz") == "rice"
    assert normalize_crop_name("manioc") == "cassava"
    assert normalize_crop_name("niébé") == "cowpea"
    assert normalize_crop_name("soja") == "soybean"


def test_normalize_crop_name_fautes_courantes():
    """Teste la tolérance aux fautes d'orthographe courantes."""
    assert normalize_crop_name("mais") == "maize"   # Sans accent
    assert normalize_crop_name("maiz") == "maize"   # Faute de frappe
    assert normalize_crop_name("niebe") == "cowpea" # Sans accent
    assert normalize_crop_name("Maize") == "maize"  # En anglais, majuscule


def test_normalize_crop_name_nom_local():
    """Teste les noms locaux (fon)."""
    assert normalize_crop_name("gbadji") == "maize"
    assert normalize_crop_name("kafle") == "sorghum"


def test_normalize_crop_name_inconnu():
    """Teste qu'un nom de culture inconnu lève une ValueError avec un message clair."""
    with pytest.raises(ValueError, match="Culture inconnue"):
        normalize_crop_name("quinoa")


def test_normalize_market_name():
    """Teste la normalisation des noms de marchés."""
    assert normalize_market_name("Dantokpa") == "cotonou"
    assert normalize_market_name("Porto-Novo") == "porto_novo"
    assert normalize_market_name("Savalou Market") == "savalou"


# --- Tests de normalisation des unités (pricing.py) ---

def test_normalize_units_usd():
    """Teste la conversion USD/kg vers XOF/kg."""
    pricing = MarketPricing()
    # 1 USD/kg avec taux 620 XOF = 620 XOF/kg
    result = pricing.normalize_units(1.0, "USD/kg")
    assert result == pytest.approx(620.0, abs=1.0)


def test_normalize_units_eur():
    """Teste la conversion EUR/kg vers XOF/kg (taux fixe UEMOA)."""
    pricing = MarketPricing()
    # 1 EUR/kg = 655.957 XOF/kg (taux fixe)
    result = pricing.normalize_units(1.0, "EUR/kg")
    assert result == pytest.approx(655.957, abs=0.01)


def test_normalize_units_sac_maize():
    """Teste la conversion XOF/sac (maïs) vers XOF/kg."""
    pricing = MarketPricing()
    # 10 000 XOF pour un sac de maïs (100 kg) = 100 XOF/kg
    result = pricing.normalize_units(10000.0, "XOF/sac", crop="maize")
    assert result == 100.0


def test_normalize_units_boisseau_maize():
    """Teste la conversion XOF/boisseau (maïs) vers XOF/kg."""
    pricing = MarketPricing()
    # 5 000 XOF pour un boisseau de maïs (25 kg) = 200 XOF/kg
    result = pricing.normalize_units(5000.0, "XOF/boisseau", crop="maize")
    assert result == 200.0


# --- Tests du flag is_simulated ---

def test_is_simulated_true_sans_client():
    """Teste que les données sans client WFP ont is_simulated=True."""
    pricing = MarketPricing(wfp_client=None)
    df = pricing.fetch_prices("maize", "cotonou")
    assert "is_simulated" in df.columns
    assert bool(df["is_simulated"].all()) is True


def test_is_simulated_true_mode_miroir():
    """Teste que le mode miroir local retourne is_simulated=True."""
    client = WFPDataBridgesClient(use_local_mirror=True)
    df = client.get_market_prices("cotonou", "maize")
    assert "is_simulated" in df.columns
    assert bool(df["is_simulated"].all()) is True


@responses.activate
def test_is_simulated_false_donnees_reelles():
    """Teste que des données réelles de l'API ont is_simulated=False."""
    client = WFPDataBridgesClient()
    client.token = "fake_token"

    # Pré-remplir le cache des IDs pour éviter des appels non mockés
    # vers Commodities/List et Markets/List pendant la résolution des IDs
    client.cache["commodities"] = {"maize": 51}
    client.cache["markets"] = {"cotonou": 1001}

    responses.add(
        responses.GET,
        "https://api.wfp.org/vam-data-bridges/1.3.1/MarketPrices/alldata",
        json={
            "items": [
                {"CommodityPriceDate": "2024-01-01T00:00:00", "ActualPrice": 310, "UnitName": "KG"},
            ]
        },
        status=200,
    )

    df = client.get_market_prices("cotonou", "maize")
    assert "is_simulated" in df.columns
    # numpy.bool_ n'est pas identique à bool Python : on utilise == et non 'is'
    assert df.iloc[0]["is_simulated"] == False


# --- Tests de la validation des données API ---

def test_validation_api_items_prix_negatif():
    """Teste que les items avec prix négatif sont rejetés."""
    client = WFPDataBridgesClient()
    items_bruts = [
        {"CommodityPriceDate": "2024-01-01", "ActualPrice": -50},
        {"CommodityPriceDate": "2024-01-02", "ActualPrice": 300},
    ]
    items_valides = client._validate_api_response_items(items_bruts)
    assert len(items_valides) == 1
    assert items_valides[0]["ActualPrice"] == 300


def test_validation_api_items_prix_manquant():
    """Teste que les items sans prix sont rejetés."""
    client = WFPDataBridgesClient()
    items_bruts = [
        {"CommodityPriceDate": "2024-01-01"},           # Pas de prix
        {"CommodityPriceDate": "2024-01-02", "ActualPrice": 280},
    ]
    items_valides = client._validate_api_response_items(items_bruts)
    assert len(items_valides) == 1


def test_validation_api_items_date_manquante():
    """Teste que les items sans date sont rejetés."""
    client = WFPDataBridgesClient()
    items_bruts = [
        {"ActualPrice": 250},                            # Pas de date
        {"CommodityPriceDate": "2024-01-01", "ActualPrice": 270},
    ]
    items_valides = client._validate_api_response_items(items_bruts)
    assert len(items_valides) == 1


# --- Tests du retry avec backoff ---

@responses.activate
def test_retry_sur_erreur_503():
    """Teste que le retry est déclenché sur une erreur 503 (serveur indisponible)."""
    # Première réponse : 503
    responses.add(
        responses.GET,
        "https://api.wfp.org/test-retry",
        status=503,
    )
    # Deuxième réponse : succès
    responses.add(
        responses.GET,
        "https://api.wfp.org/test-retry",
        json={"success": True},
        status=200,
    )

    response = _get_with_retry(
        "https://api.wfp.org/test-retry",
        retry_attempts=3,
        retry_backoff_sec=0.01,  # Délai très court pour les tests
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    # Vérification que deux appels ont bien été effectués
    assert len(responses.calls) == 2


@responses.activate
def test_erreur_401_pas_de_retry():
    """Teste que les erreurs 401 (non-autorisé) ne déclenchent pas de retry."""
    responses.add(
        responses.GET,
        "https://api.wfp.org/test-no-retry",
        status=401,
    )

    response = _get_with_retry(
        "https://api.wfp.org/test-no-retry",
        retry_attempts=3,
        retry_backoff_sec=0.01,
    )

    assert response.status_code == 401
    # Un seul appel : pas de retry sur 401
    assert len(responses.calls) == 1


# --- Tests des coefficients logistiques configurables ---

def test_coefficients_depuis_config():
    """Teste que le module logistique utilise bien les coefficients de config.py."""
    from kadi.config import CONFIG

    logistique_cfg = CONFIG.get("logistics", {})
    # Vérification que les clés essentielles sont présentes dans la config
    assert "c_info_xof" in logistique_cfg
    assert "gamma_route" in logistique_cfg
    assert "mu_checkpoints_xof_per_km" in logistique_cfg
    assert "c_qualite_loss_xof" in logistique_cfg
    assert "prix_carburant_fallback_xof" in logistique_cfg

    # Vérification de la cohérence des valeurs
    assert logistique_cfg["gamma_route"] >= 1.0
    assert logistique_cfg["c_info_xof"] > 0
    assert logistique_cfg["seuil_rentabilite_pct"] > 0


# --- Tests du poids des contenants ---

def test_poids_contenants_maize():
    """Teste les poids de référence des contenants pour le maïs."""
    assert get_container_weight_kg("sac", "maize") == 100.0
    assert get_container_weight_kg("boisseau", "maize") == 25.0


def test_poids_contenant_generique():
    """Teste le fallback sur le poids générique si la culture est inconnue."""
    poids = get_container_weight_kg("sac", "produit_inconnu")
    # Doit retourner le poids générique d'un sac
    assert poids == 80.0


def test_poids_contenant_totalement_inconnu():
    """Teste le fallback à 80 kg si le contenant est complètement inconnu."""
    poids = get_container_weight_kg("contenant_bizarre")
    assert poids == 80.0
