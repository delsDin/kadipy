"""
Tests d'intégration pour le module kadi.market.

Ces tests vérifient le flux complet depuis l'ingestion des données
jusqu'aux recommandations de décision, en mockant les couches réseau
et cache pour assurer la fiabilité et la rapidité des tests.

Contexte d'exécution :
    - Pas de clé API WFP disponible : les données réelles sont mockées
    - Le cache SQLite utilise une base temporaire (tmp_path de pytest)
    - Tous les appels HTTP sont interceptés par la bibliothèque responses
"""

import pytest
import responses
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

from kadi.market import Market
from kadi.market.data_ingestion import WFPDataBridgesClient
from kadi.market._cache import (
    initialiser_base,
    sauvegarder_prix,
    recuperer_prix,
    obtenir_info_fraicheur,
    calculer_score_confiance,
    vider_cache,
    MARKET_DB_PATH,
)


# ============================================================
# Fixtures partagées
# ============================================================

@pytest.fixture
def db_temporaire(tmp_path) -> Path:
    """
    Retourne un chemin vers une base SQLite temporaire pour les tests.

    Chaque test dispose de sa propre base vierge : pas d'interférence
    entre les tests, même en parallèle.
    """
    # Création d'une base temporaire isolée du cache de production
    return tmp_path / "test_market.db"


@pytest.fixture
def df_prix_reel() -> pd.DataFrame:
    """
    Retourne un DataFrame de prix réalistes pour le Bénin (maïs, Parakou).

    Simule 30 jours de données fraîches, marquées comme non simulées
    (is_simulated=False, source='wfp-vam').
    """
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=30, freq="D")
    maintenant = datetime.now(timezone.utc).isoformat()

    return pd.DataFrame({
        "date": dates,
        "price": [285 + i * 0.5 for i in range(30)],
        "unit": "XOF/kg",
        "is_simulated": False,
        "source": "wfp-vam",
        "fetched_at": maintenant,
    })


@pytest.fixture
def marche_parakou() -> Market:
    """
    Retourne une instance Market pour Parakou (centre du Bénin).

    Coordonnées réelles : lat=9.337, lon=2.627 - dans la zone Bénin valide.
    """
    return Market(lat=9.337, lon=2.627, location="Parakou")


# ============================================================
# Tests du module _cache.py
# ============================================================

class TestCache:
    """Tests unitaires du cache SQLite (kadi.market._cache)."""

    def test_initialiser_base_cree_les_tables(self, db_temporaire):
        """Vérifie que les deux tables sont créées lors de l'initialisation."""
        import sqlite3

        initialiser_base(db_temporaire)

        with sqlite3.connect(str(db_temporaire)) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
            noms = [t[0] for t in tables]

        # Les deux tables doivent exister après initialisation
        assert "market_prices" in noms
        assert "cache_meta" in noms

    def test_initialiser_base_idempotente(self, db_temporaire):
        """Vérification que l'initialisation ne crée pas de doublons."""
        # Deux appels successifs ne doivent pas lever d'erreur
        initialiser_base(db_temporaire)
        initialiser_base(db_temporaire)

    def test_sauvegarder_et_recuperer_prix(self, db_temporaire, df_prix_reel):
        """Flux complet : sauvegarde puis récupération des prix depuis le cache."""
        # Sauvegarde dans la base temporaire
        nb = sauvegarder_prix("parakou", "maize", df_prix_reel, source="wfp-vam", db_path=db_temporaire)

        # Toutes les lignes doivent avoir été insérées
        assert nb == 30

        # Récupération dans les 7 jours : doit retourner les données
        df_retour = recuperer_prix("parakou", "maize", max_age_jours=7, db_path=db_temporaire)

        assert df_retour is not None
        assert len(df_retour) == 30
        assert "date" in df_retour.columns
        assert "price" in df_retour.columns
        assert "is_simulated" in df_retour.columns
        # Les données ont été sauvegardées comme non simulées
        assert df_retour["is_simulated"].all() == False

    def test_recuperer_prix_retourne_none_si_absent(self, db_temporaire):
        """Le cache retourne None pour un couple inexistant."""
        initialiser_base(db_temporaire)
        resultat = recuperer_prix("abomey", "yam", db_path=db_temporaire)
        assert resultat is None

    def test_sauvegarder_ignore_les_doublons(self, db_temporaire, df_prix_reel):
        """Deux sauvegardes consécutives ne doivent pas dupliquer les données."""
        # Première sauvegarde
        nb_1 = sauvegarder_prix("cotonou", "rice", df_prix_reel, db_path=db_temporaire)

        # Deuxième sauvegarde des mêmes données
        nb_2 = sauvegarder_prix("cotonou", "rice", df_prix_reel, db_path=db_temporaire)

        # La deuxième insertion ne doit rien ajouter
        assert nb_1 == 30
        assert nb_2 == 0

    def test_obtenir_info_fraicheur_absent(self, db_temporaire):
        """Les infos de fraîcheur pour un couple absent retournent en_cache=False."""
        initialiser_base(db_temporaire)
        info = obtenir_info_fraicheur("kandi", "millet", db_path=db_temporaire)

        assert info["en_cache"] == False
        assert info["age_jours"] is None
        assert info["nb_records"] == 0

    def test_obtenir_info_fraicheur_present(self, db_temporaire, df_prix_reel):
        """Les infos de fraîcheur retournent les bonnes métadonnées."""
        # On spécifie explicitement la source pour vérifier qu'elle est bien conservée
        sauvegarder_prix("bohicon", "cowpea", df_prix_reel, source="wfp-vam", db_path=db_temporaire)
        info = obtenir_info_fraicheur("bohicon", "cowpea", db_path=db_temporaire)

        assert info["en_cache"] == True
        # Les données viennent d'être sauvegardées : moins d'une minute
        assert info["age_jours"] is not None
        assert info["age_jours"] < 0.1
        assert info["source"] == "wfp-vam"

    def test_calculer_score_confiance_wfp_frais(self, db_temporaire, df_prix_reel):
        """Source WFP + données fraîches doit donner un score proche de 1.0."""
        sauvegarder_prix("natitingou", "sorghum", df_prix_reel, source="wfp-vam", db_path=db_temporaire)

        score = calculer_score_confiance("natitingou", "sorghum", db_path=db_temporaire)

        # Source WFP (1.0) * fraîcheur maximale (~1.0) = très proche de 1.0
        assert score > 0.9

    def test_calculer_score_confiance_simule(self, db_temporaire):
        """Données simulées doivent donner un score faible."""
        dates = pd.date_range(end=datetime.today(), periods=10, freq="D")
        df_simule = pd.DataFrame({
            "date": dates,
            "price": [300.0] * 10,
            "unit": "XOF/kg",
            "is_simulated": True,
        })
        sauvegarder_prix("parakou", "cassava", df_simule, source="simulated", db_path=db_temporaire)

        score = calculer_score_confiance("parakou", "cassava", db_path=db_temporaire)

        # Source simulée (0.1) * fraîcheur maximale (~1.0) = ~0.1
        assert score < 0.2

    def test_calculer_score_confiance_absent(self, db_temporaire):
        """Score de confiance nul si aucune donnée en cache."""
        initialiser_base(db_temporaire)
        score = calculer_score_confiance("porto_novo", "soybean", db_path=db_temporaire)
        assert score == 0.0

    def test_vider_cache_cible(self, db_temporaire, df_prix_reel):
        """Vider un couple spécifique ne touche pas les autres."""
        sauvegarder_prix("malanville", "maize", df_prix_reel, db_path=db_temporaire)
        sauvegarder_prix("malanville", "rice", df_prix_reel, db_path=db_temporaire)

        # Suppression ciblée : seulement maize à Malanville
        vider_cache("malanville", "maize", db_path=db_temporaire)

        # maize supprimé
        assert recuperer_prix("malanville", "maize", db_path=db_temporaire) is None
        # rice toujours présent
        assert recuperer_prix("malanville", "rice", db_path=db_temporaire) is not None

    def test_sauvegarder_leve_erreur_si_colonnes_manquantes(self, db_temporaire):
        """ValueError si le DataFrame ne contient pas 'date' et 'price'."""
        df_incomplet = pd.DataFrame({"valeur": [100, 200]})

        with pytest.raises(ValueError, match="Colonnes manquantes"):
            sauvegarder_prix("cotonou", "maize", df_incomplet, db_path=db_temporaire)


# ============================================================
# Tests d'intégration du client WFP avec cache
# ============================================================

@responses.activate
class TestWFPClientAvecCache:
    """Tests du client WFP DataBridges avec cache SQLite intégré."""

    def test_cache_hit_evite_appel_api(self, db_temporaire, df_prix_reel, monkeypatch):
        """Quand le cache est frais, l'API ne doit pas être appelée."""
        # Pré-remplissage du cache avec des données fraîches
        sauvegarder_prix("cotonou", "maize", df_prix_reel, source="wfp-vam", db_path=db_temporaire)

        # Monkey-patch pour utiliser la base temporaire
        monkeypatch.setattr(
            "kadi.market._cache.MARKET_DB_PATH", db_temporaire
        )
        monkeypatch.setattr(
            "kadi.market.data_ingestion.recuperer_prix",
            lambda m, c, max_age_jours: recuperer_prix(m, c, max_age_jours, db_temporaire),
        )

        client = WFPDataBridgesClient()
        client.token = "fake_token"
        client.cache["commodities"] = {"maize": 51}
        client.cache["markets"] = {"cotonou": 1001}

        # Aucun endpoint HTTP ne doit être appelé
        df = client.get_market_prices("cotonou", "maize")

        # Les données du cache doivent être retournées
        assert not df.empty
        assert len(responses.calls) == 0, "L'API ne doit pas être appelée si le cache est frais"

    @responses.activate
    def test_donnees_reelles_api_sauvegardees_en_cache(self, db_temporaire, monkeypatch):
        """Après un appel API réussi, les données sont sauvegardées dans le cache."""
        # Mock de l'API WFP
        responses.add(
            responses.GET,
            "https://api.wfp.org/vam-data-bridges/1.3.1/MarketPrices/alldata",
            json={
                "items": [
                    {"CommodityPriceDate": "2024-01-01T00:00:00", "ActualPrice": 310, "UnitName": "KG"},
                    {"CommodityPriceDate": "2024-01-02T00:00:00", "ActualPrice": 320, "UnitName": "KG"},
                ]
            },
            status=200,
        )

        # Monkey-patch pour utiliser la base temporaire
        monkeypatch.setattr(
            "kadi.market.data_ingestion.recuperer_prix",
            lambda m, c, max_age_jours: None,  # Cache vide : forcer l'appel API
        )
        monkeypatch.setattr(
            "kadi.market.data_ingestion.sauvegarder_prix",
            lambda m, c, df, source, **kw: sauvegarder_prix(m, c, df, source, db_temporaire),
        )

        client = WFPDataBridgesClient()
        client.token = "fake_token"
        client.cache["commodities"] = {"maize": 51}
        client.cache["markets"] = {"savalou": 1234}

        df = client.get_market_prices("savalou", "maize")

        # Les données API doivent être retournées avec les bonnes colonnes
        assert not df.empty
        assert "is_simulated" in df.columns
        assert "source" in df.columns
        assert "fetched_at" in df.columns
        assert "confidence_score" in df.columns
        assert df["is_simulated"].all() == False
        assert df["source"].iloc[0] == "wfp-vam"

    @responses.activate
    def test_fallback_simule_sans_token(self):
        """Sans token WFP, le client retourne des données simulées."""
        client = WFPDataBridgesClient()
        # Pas de token : client.token == ""
        assert client.token == ""

        df = client.get_market_prices("cotonou", "maize")

        # Les données doivent être simulées
        assert not df.empty
        assert "is_simulated" in df.columns
        assert df["is_simulated"].all() == True
        assert df["source"].iloc[0] == "simulated"
        assert df["confidence_score"].iloc[0] == 0.1
        # Aucun appel HTTP ne doit avoir eu lieu
        assert len(responses.calls) == 0


# ============================================================
# Tests d'intégration de la classe Market
# ============================================================

class TestMarketFacade:
    """Tests d'intégration de la façade Market (flux complet)."""

    def test_price_crop_retourne_un_dict_complet(self, marche_parakou):
        """price_crop() doit retourner toutes les clés attendues."""
        resultat = marche_parakou.price_crop("maize", days_back=30)

        cles_attendues = {
            "crop", "market", "prix_median", "prix_min", "prix_max",
            "prix_moyen", "nb_observations", "nb_anomalies",
            "is_simulated", "confidence_score", "source", "donnees",
        }
        assert cles_attendues <= set(resultat.keys())

    def test_price_crop_maize(self, marche_parakou):
        """En mode sans clé, price_crop retourne des données simulées cohérentes."""
        resultat = marche_parakou.price_crop("maize", days_back=30)

        # Sans API, les données sont simulées
        assert resultat["is_simulated"] == True
        assert resultat["confidence_score"] == 0.1
        assert resultat["nb_observations"] > 0
        assert resultat["prix_median"] is not None
        assert resultat["prix_min"] <= resultat["prix_median"] <= resultat["prix_max"]

    def test_price_crop_donnees_est_dataframe(self, marche_parakou):
        """La clé 'donnees' doit être un DataFrame pandas."""
        resultat = marche_parakou.price_crop("sorghum")
        assert isinstance(resultat["donnees"], pd.DataFrame)

    def test_market_coordonnees_invalides_latitude(self):
        """Latitude hors Bénin lève ValueError."""
        with pytest.raises(ValueError, match="Latitude"):
            Market(lat=14.0, lon=2.3, location="HorsZone")

    def test_market_coordonnees_invalides_longitude(self):
        """Longitude hors Bénin lève ValueError."""
        with pytest.raises(ValueError, match="Longitude"):
            Market(lat=9.5, lon=5.0, location="HorsZone")

    def test_market_coordonnees_type_invalide(self):
        """Type non numérique pour lat lève TypeError."""
        with pytest.raises(TypeError, match="latitude"):
            Market(lat="neuf", lon=2.3, location="Parakou")

    def test_market_location_vide_leve_erreur(self):
        """Nom de lieu vide lève ValueError."""
        with pytest.raises(ValueError, match="vide"):
            Market(lat=9.3, lon=2.3, location="   ")


# ============================================================
# Tests d'intégration du module DecisionSupport
# ============================================================

class TestDecisionSupportIntegration:
    """Tests de l'aide à la décision avec les vrais prix (simulés en mode sans-API)."""

    def test_arbitrage_decision_retourne_les_cles_attendues(self, marche_parakou):
        """arbitrage_decision() doit retourner toutes les clés obligatoires."""
        resultat = marche_parakou.decision_support.arbitrage_decision(
            crop="maize",
            market_from="Parakou",
            market_to="Cotonou",
            qty_tons=5.0,
        )

        cles_attendues = {
            "recommandation", "gain_net_total_cfa", "gain_net_percent",
            "frais_logistiques_total", "prix_origine_xof_kg",
            "prix_destination_xof_kg", "is_simulated",
        }
        assert cles_attendues <= set(resultat.keys())

    def test_arbitrage_decision_recommandation_est_string(self, marche_parakou):
        """La recommandation doit être l'une des deux valeurs attendues."""
        resultat = marche_parakou.decision_support.arbitrage_decision(
            crop="rice",
            market_from="Savalou",
            market_to="Cotonou",
            qty_tons=2.0,
        )
        assert resultat["recommandation"] in ("TRANSPORTER", "NE PAS TRANSPORTER")

    def test_storage_vs_sell_now_retourne_les_cles_attendues(self, marche_parakou):
        """storage_vs_sell_now() doit retourner toutes les clés obligatoires."""
        resultat = marche_parakou.decision_support.storage_vs_sell_now(
            crop="maize",
            market="Parakou",
            current_price=285_000.0,
            qty_tons=3.0,
        )

        cles_attendues = {
            "recommandation_binaire", "marge_nette_cfa",
            "marge_nette_par_tonne", "prix_futur_estime", "is_simulated",
        }
        assert cles_attendues <= set(resultat.keys())

    def test_storage_vs_sell_now_recommandation_valide(self, marche_parakou):
        """La recommandation de stockage doit être l'une des deux valeurs attendues."""
        resultat = marche_parakou.decision_support.storage_vs_sell_now(
            crop="yam",
            market="Abomey",
            current_price=250_000.0,
            qty_tons=1.5,
        )
        assert resultat["recommandation_binaire"] in ("STOCKER", "VENDRE IMMÉDIATEMENT")

    def test_arbitrage_is_simulated_true_sans_api(self, marche_parakou):
        """Sans clé API, les recommandations doivent signaler is_simulated=True."""
        resultat = marche_parakou.decision_support.arbitrage_decision(
            crop="maize",
            market_from="Natitingou",
            market_to="Parakou",
            qty_tons=10.0,
        )
        # Sans API, les prix sont forcément simulés
        assert resultat["is_simulated"] == True


# ============================================================
# Tests d'intégration Phase 4 : météo-marché
# ============================================================

class TestWeatherMarketIntegration:
    """
    Tests d'intégration Phase 4 : connexion kadi.weather <-> kadi.market.

    Tous les appels au module météo sont mockés via unittest.mock pour garantir
    la rapidité et l'absence d'appels réseau réels pendant les tests.
    """

    @pytest.fixture
    def mock_weather_session_pluie_elevee(self):
        """
        Retourne un mock de WeatherSession simulant une forte probabilité de pluie.

        rain_probability retourne 0.9 pour demain (pluie quasi certaine).
        """
        from unittest.mock import MagicMock

        ws = MagicMock()
        # Probabilité de pluie élevée demain (saison des pluies)
        ws.rain_probability.return_value = {
            "tomorrow": 0.9,
            "message": "90% de chance de pluie demain.",
            "recommendation": "Repousser les opérations au champ.",
        }
        ws.drought_index.return_value = {
            "spi_3month": -0.3,
            "drought_severity": "mild",
        }
        return ws

    @pytest.fixture
    def mock_weather_session_saison_seche(self):
        """
        Retourne un mock de WeatherSession simulant une saison sèche (SPI sévère).

        rain_probability retourne 0.05 pour demain.
        drought_index retourne sévérité 'severe'.
        """
        from unittest.mock import MagicMock

        ws = MagicMock()
        # Probabilité de pluie très faible (saison sèche)
        ws.rain_probability.return_value = {
            "tomorrow": 0.05,
            "message": "5% de chance de pluie demain.",
            "recommendation": "Bon moment pour les traitements phyto.",
        }
        ws.drought_index.return_value = {
            "spi_3month": -1.8,
            "drought_severity": "severe",
        }
        return ws

    def test_logistics_gamma_eleve_saison_pluies(
        self, mock_weather_session_pluie_elevee
    ):
        """
        gamma_effectif doit être strictement supérieur à gamma_base quand
        la probabilité de pluie est élevée (0.9).
        """
        from kadi.market.logistics import MarketLogistics, _calculer_gamma_effectif
        from kadi.config import CONFIG

        # Instanciation du module logistique avec la session météo mockée
        logistics = MarketLogistics(
            cache_file="/tmp/test_osrm_cache.json",
            weather_session=mock_weather_session_pluie_elevee,
        )

        # Récupération du gamma de base depuis la configuration
        gamma_base = CONFIG.get("logistics", {}).get("gamma_route", 1.2)
        prob_pluie = 0.9

        # Calcul du gamma effectif
        gamma_effectif = _calculer_gamma_effectif(gamma_base, prob_pluie)

        # Vérification : avec forte pluie, gamma_effectif > gamma_base
        assert gamma_effectif > gamma_base, (
            f"gamma_effectif ({gamma_effectif}) doit être > gamma_base ({gamma_base}) "
            f"quand prob_pluie={prob_pluie}"
        )
        # Majoration maximale : alpha=0.25, prob=1.0 -> max 25% au-dessus de gamma_base
        alpha = CONFIG.get("logistics", {}).get("alpha_pluie", 0.25)
        assert gamma_effectif <= gamma_base * (1.0 + alpha)

    def test_logistics_gamma_inchange_sans_weather_session(self):
        """
        Sans weather_session, gamma_effectif doit être identique à gamma_base.
        La logistique V1 reste inchangée.
        """
        from kadi.market.logistics import _calculer_gamma_effectif
        from kadi.config import CONFIG

        gamma_base = CONFIG.get("logistics", {}).get("gamma_route", 1.2)

        # Pas de pluie (prob = 0.0) = comportement sans météo
        gamma_effectif = _calculer_gamma_effectif(gamma_base, 0.0)

        assert gamma_effectif == gamma_base, (
            "Sans pluie (prob=0.0), gamma_effectif doit être identique à gamma_base."
        )

    def test_qualite_loss_variable_par_culture(self):
        """
        La perte de qualité d'une tomate doit être nettement supérieure
        à celle du maïs pour le même trajet (cultures plus périssables).
        """
        from kadi.market.logistics import _calculer_perte_qualite

        distance_km = 100.0
        prob_pluie = 0.0  # Pas de pluie pour isoler l'effet culture

        perte_tomate = _calculer_perte_qualite("tomato", distance_km, prob_pluie)
        perte_mais = _calculer_perte_qualite("maize", distance_km, prob_pluie)

        assert perte_tomate > perte_mais, (
            f"Tomate ({perte_tomate} XOF) doit avoir une perte > maïs ({perte_mais} XOF) "
            "sur {distance_km} km sans pluie."
        )

    def test_qualite_loss_augmente_avec_pluie(self):
        """
        La perte de qualité doit être plus élevée avec pluie (0.8) qu'à sec (0.0)
        pour une culture périssable (tomate) sur une même distance.
        """
        from kadi.market.logistics import _calculer_perte_qualite

        distance_km = 80.0

        # Perte sans pluie
        perte_sec = _calculer_perte_qualite("tomato", distance_km, prob_pluie=0.0)
        # Perte avec forte pluie
        perte_pluie = _calculer_perte_qualite("tomato", distance_km, prob_pluie=0.8)

        assert perte_pluie > perte_sec, (
            f"Perte sous la pluie ({perte_pluie}) doit être > perte à sec ({perte_sec})."
        )

    def test_storage_horizon_configurable_1_vs_6_mois(self):
        """
        Un horizon de 1 mois doit donner un résultat différent d'un horizon
        de 6 mois (coûts de stockage et prix futur différents).
        """
        from kadi.market.decision_support import DecisionSupport

        ds = DecisionSupport()  # Pas de modules : utilise les valeurs par défaut

        res_1_mois = ds.storage_vs_sell_now(
            crop="maize",
            market="Parakou",
            current_price=300_000.0,
            qty_tons=2.0,
            mois_stockage=1,
        )
        res_6_mois = ds.storage_vs_sell_now(
            crop="maize",
            market="Parakou",
            current_price=300_000.0,
            qty_tons=2.0,
            mois_stockage=6,
        )

        # Les horizons doivent être bien enregistrés
        assert res_1_mois["horizon_mois"] == 1
        assert res_6_mois["horizon_mois"] == 6

        # Les marges nettes doivent différer (coûts de stockage différents)
        assert res_1_mois["marge_nette_par_tonne"] != res_6_mois["marge_nette_par_tonne"], (
            "Un horizon de 1 mois doit produire une marge différente d'un horizon de 6 mois."
        )

    def test_confidence_score_present_dans_arbitrage(self):
        """
        arbitrage_decision() doit inclure la clé 'confidence_score' dans son résultat.
        """
        from kadi.market.decision_support import DecisionSupport

        ds = DecisionSupport()
        resultat = ds.arbitrage_decision(
            crop="rice",
            market_from="Savalou",
            market_to="Cotonou",
            qty_tons=3.0,
        )

        assert "confidence_score" in resultat, (
            "La clé 'confidence_score' doit être présente dans le résultat d'arbitrage."
        )
        assert 0.0 <= resultat["confidence_score"] <= 1.0, (
            "confidence_score doit être compris entre 0 et 1."
        )

    def test_confidence_score_faible_si_simule(self):
        """
        En mode sans API (is_simulated=True), le confidence_score doit être
        inférieur à 0.5 (données peu fiables).
        """
        from kadi.market.decision_support import DecisionSupport

        ds = DecisionSupport()  # Pas de pricing_module : données simulées
        resultat = ds.arbitrage_decision(
            crop="maize",
            market_from="Parakou",
            market_to="Abomey",
            qty_tons=1.0,
        )

        # Sans API, is_simulated=True -> confidence_score doit être faible
        assert resultat["is_simulated"] == True
        assert resultat["confidence_score"] < 0.5, (
            f"confidence_score ({resultat['confidence_score']}) doit être < 0.5 "
            "quand les données sont simulées."
        )

    def test_portfolio_optimization_scipy_retourne_repartition_valide(self):
        """
        portfolio_optimization() avec scipy doit retourner une répartition
        valide : toutes les cultures >= 0 et la somme <= available_land_ha.
        """
        from kadi.market.decision_support import DecisionSupport

        ds = DecisionSupport()

        # Prévisions de prix simulées (XOF/kg)
        market_forecast = {"maize": 285.0, "cowpea": 580.0, "sorghum": 210.0}

        # Conditions climatiques normales
        climate_forecast = {"drought_severity": "mild", "secheresse_anticipee": False}

        available_land = 10.0  # 10 hectares disponibles

        resultat = ds.portfolio_optimization(
            available_land_ha=available_land,
            climate_forecast=climate_forecast,
            market_forecast=market_forecast,
        )

        # Le résultat doit contenir les clés obligatoires
        assert "repartition_hectares" in resultat
        assert "revenu_attendu_cfa" in resultat
        assert "methode" in resultat
        assert "confidence_score" in resultat

        repartition = resultat["repartition_hectares"]

        # Chaque culture doit avoir une surface >= 0
        for culture, surface in repartition.items():
            assert surface >= 0.0, (
                f"La surface allouée à {culture} ({surface} ha) ne peut pas être négative."
            )

        # La surface totale ne peut pas dépasser la surface disponible
        total = sum(repartition.values())
        assert total <= available_land + 1e-6, (
            f"Surface totale allouée ({total:.2f} ha) > surface disponible ({available_land} ha)."
        )

    def test_assess_climate_risk_sans_weather_session(self):
        """
        assess_climate_risk() sans weather_session doit retourner
        weather_available=False et un message explicatif.
        """
        marche = Market(lat=9.337, lon=2.627, location="Parakou")

        resultat = marche.assess_climate_risk(days_ahead=3)

        assert resultat["weather_available"] == False
        assert resultat["prob_pluie_j1"] == 0.0
        assert "weather_session" in resultat["recommendation"] or "météo" in resultat["recommendation"]

    def test_assess_climate_risk_avec_weather_session(
        self, mock_weather_session_pluie_elevee
    ):
        """
        assess_climate_risk() avec weather_session doit retourner
        weather_available=True et une probabilité de pluie > 0.
        """
        marche = Market(
            lat=9.337, lon=2.627, location="Parakou",
            weather_session=mock_weather_session_pluie_elevee,
        )

        resultat = marche.assess_climate_risk(days_ahead=1)

        assert resultat["weather_available"] == True
        assert resultat["prob_pluie_j1"] > 0.0
        assert isinstance(resultat["recommendation"], str)
        assert len(resultat["recommendation"]) > 0

