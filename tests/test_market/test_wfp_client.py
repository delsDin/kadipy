"""
Tests unitaires pour le module kadi._sources.wfp_client.

Vérifie le comportement de WFPClient :
- la structure et le schéma du DataFrame retourné,
- la normalisation des colonnes HAPI vers le format interne,
- le fallback en mode simulation (réseau indisponible ou identifiant absent),
- la transmission des filtres à l'API,
- la pagination automatique.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from kadi._sources import WFPClient


# CSV minimaliste simulant une réponse de l'API HAPI
_CSV_HAPI_VALIDE = (
    "reference_period_start,price,price_unit,source_org_acronym\n"
    "2026-01-01,280.5,XOF/KG,WFP\n"
    "2026-02-01,295.0,XOF/KG,WFP\n"
    "2026-03-01,310.0,XOF/KG,WFP\n"
)

# CSV avec une page complète (simulant la pagination)
_CSV_PAGE_PLEINE = "\n".join(
    ["reference_period_start,price,price_unit,source_org_acronym"]
    + [f"2026-01-{str(i).zfill(2)},280.0,XOF/KG,WFP" for i in range(1, 28)]
)

# Plage de dates utilisée dans les tests
_TIME_RANGE = ("2026-01-01", "2026-03-31")


def _creer_reponse_csv_mock(contenu_csv: str, status_code: int = 200) -> MagicMock:
    """
    Crée un mock de réponse HTTP contenant un CSV.

    Args:
        contenu_csv (str): Contenu CSV de la réponse simulée.
        status_code (int): Code HTTP simulé.

    Returns:
        MagicMock: Mock compatible avec requests.Response.
    """
    mock_reponse = MagicMock()
    mock_reponse.status_code = status_code
    mock_reponse.text = contenu_csv
    mock_reponse.raise_for_status.return_value = None
    return mock_reponse


class TestGetMarketPricesStructure:
    """Vérifie la structure et le schéma du DataFrame retourné."""

    def test_get_market_prices_retourne_un_dataframe(self):
        """get_market_prices() doit toujours retourner un pd.DataFrame."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch("kadi._sources.wfp_client.requests.get", return_value=reponse_mock):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert isinstance(df, pd.DataFrame)

    def test_colonnes_internes_presentes(self):
        """Le DataFrame doit contenir les colonnes standard de KadiPy."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch("kadi._sources.wfp_client.requests.get", return_value=reponse_mock):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        colonnes_attendues = {"date", "price", "unit", "is_simulated", "source", "fetched_at"}
        assert colonnes_attendues.issubset(set(df.columns))

    def test_prix_sont_des_numeriques(self):
        """La colonne 'price' doit contenir des valeurs numériques."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch("kadi._sources.wfp_client.requests.get", return_value=reponse_mock):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert pd.api.types.is_numeric_dtype(df["price"])

    def test_dates_sont_des_datetime(self):
        """La colonne 'date' doit contenir des objets datetime."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch("kadi._sources.wfp_client.requests.get", return_value=reponse_mock):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert pd.api.types.is_datetime64_any_dtype(df["date"])


class TestNormalisationColonnes:
    """Vérifie le mapping des colonnes HAPI vers le format interne KadiPy."""

    def test_colonnes_hapi_normalisees_vers_format_interne(self):
        """Les noms de colonnes HAPI doivent être traduits vers les noms internes."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch("kadi._sources.wfp_client.requests.get", return_value=reponse_mock):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        # Vérification que les noms HAPI ont été remplacés par les noms internes
        assert "reference_period_start" not in df.columns
        assert "price_unit" not in df.columns
        assert "source_org_acronym" not in df.columns
        assert "date" in df.columns
        assert "unit" in df.columns
        assert "source" in df.columns

    def test_donnees_reelles_ont_is_simulated_false(self):
        """Les données issues de l'API HAPI doivent avoir is_simulated=False."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch("kadi._sources.wfp_client.requests.get", return_value=reponse_mock):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert not df["is_simulated"].any()

    def test_confidence_score_vaut_1_pour_donnees_reelles(self):
        """Les données WFP réelles doivent avoir un confidence_score de 1.0."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch("kadi._sources.wfp_client.requests.get", return_value=reponse_mock):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert (df["confidence_score"] == 1.0).all()


class TestFallbackSimulation:
    """Vérifie le comportement en mode simulation (absence de réseau ou d'identifiant)."""

    def test_fallback_si_identifiant_absent(self):
        """Sans identifiant HAPI, les données doivent être simulées (is_simulated=True)."""
        # Client instancié sans identifiant
        client = WFPClient(app_identifier=None)
        df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert isinstance(df, pd.DataFrame)
        assert df["is_simulated"].all()

    def test_fallback_si_timeout(self):
        """En cas de Timeout réseau, les données doivent être simulées."""
        import requests

        with patch(
            "kadi._sources.wfp_client.requests.get",
            side_effect=requests.exceptions.Timeout("Timeout"),
        ):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert df["is_simulated"].all()

    def test_fallback_si_connection_error(self):
        """En cas de ConnectionError, les données doivent être simulées."""
        import requests

        with patch(
            "kadi._sources.wfp_client.requests.get",
            side_effect=requests.exceptions.ConnectionError("Pas de réseau"),
        ):
            client = WFPClient(app_identifier="identifiant_test")
            df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert df["is_simulated"].all()

    def test_fallback_contient_colonnes_standards(self):
        """Le DataFrame de simulation doit respecter le schéma standard."""
        client = WFPClient(app_identifier=None)
        df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        colonnes_attendues = {"date", "price", "unit", "is_simulated", "source", "fetched_at"}
        assert colonnes_attendues.issubset(set(df.columns))

    def test_fallback_source_est_simulated(self):
        """La colonne 'source' doit valoir 'simulated' en mode fallback."""
        client = WFPClient(app_identifier=None)
        df = client.get_market_prices("cotonou", "maize", _TIME_RANGE)

        assert (df["source"] == "simulated").all()


class TestFiltresAPI:
    """Vérifie la transmission des filtres aux paramètres de l'API."""

    def test_filtres_location_code_transmis(self):
        """Le paramètre location_code doit être inclus dans les paramètres HTTP."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch(
            "kadi._sources.wfp_client.requests.get", return_value=reponse_mock
        ) as mock_get:
            client = WFPClient(app_identifier="identifiant_test")
            client.get_market_prices(
                "cotonou", "maize", _TIME_RANGE, location_code="BEN"
            )

            # Récupération des paramètres effectivement transmis à requests.get
            params_appel = mock_get.call_args[1]["params"]
            assert params_appel.get("location_code") == "BEN"

    def test_filtre_market_name_transmis(self):
        """Le nom du marché doit être transmis dans les paramètres."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch(
            "kadi._sources.wfp_client.requests.get", return_value=reponse_mock
        ) as mock_get:
            client = WFPClient(app_identifier="identifiant_test")
            client.get_market_prices("parakou", "maize", _TIME_RANGE)

            params_appel = mock_get.call_args[1]["params"]
            assert params_appel.get("market_name") == "parakou"

    def test_filtre_commodity_name_transmis(self):
        """Le nom de la marchandise doit être transmis dans les paramètres."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch(
            "kadi._sources.wfp_client.requests.get", return_value=reponse_mock
        ) as mock_get:
            client = WFPClient(app_identifier="identifiant_test")
            client.get_market_prices("cotonou", "rice", _TIME_RANGE)

            params_appel = mock_get.call_args[1]["params"]
            assert params_appel.get("commodity_name") == "rice"

    def test_location_code_defaut_est_ben(self):
        """La localisation par défaut doit être BEN (Bénin)."""
        reponse_mock = _creer_reponse_csv_mock(_CSV_HAPI_VALIDE)

        with patch(
            "kadi._sources.wfp_client.requests.get", return_value=reponse_mock
        ) as mock_get:
            client = WFPClient(app_identifier="identifiant_test")
            client.get_market_prices("cotonou", "maize", _TIME_RANGE)

            params_appel = mock_get.call_args[1]["params"]
            assert params_appel.get("location_code") == "BEN"
