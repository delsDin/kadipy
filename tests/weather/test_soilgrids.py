"""
Tests unitaires pour kadi._sources.soilgrids.

Vérifie les comportements suivants :
- Traduction des classes WRB vers les types de sols KadiPy.
- Recherche dans le cache local (hit, miss, seuil de distance).
- Appel API SoilGrids et parsing de la réponse.
- Sauvegarde et chargement du cache JSON.
- Fallback en cas d'erreur réseau ou d'API indisponible.

Les appels réseau réels sont systématiquement mockés via pytest-mock (mocker.patch)
pour garantir la reproductibilité et l'isolation des tests.
"""

import json
import math
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import requests

# Import du module à tester
from kadi._sources import soilgrids as sg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cache_temporaire(tmp_path, monkeypatch):
    """Remplace le chemin du cache SoilGrids par un répertoire temporaire.

    Cette fixture s'applique à tous les tests automatiquement (autouse=True)
    pour éviter que les tests ne lisent ou n'écrivent dans le cache réel
    de l'utilisateur (~/.kadi/soilgrids_cache.json).
    """
    # Chemin vers un fichier de cache temporaire et isolé
    chemin_cache_temp = str(tmp_path / "soilgrids_cache.json")
    monkeypatch.setattr(sg, "_CACHE_FICHIER", chemin_cache_temp)
    return chemin_cache_temp


# ---------------------------------------------------------------------------
# Tests de la table de correspondance WRB -> KadiPy
# ---------------------------------------------------------------------------

class TestTraductionWRB:
    """Vérifie la table de correspondance WRB -> type de sol KadiPy."""

    def test_lixisol_donne_ferrugineux(self):
        """Lixisol est le sol ferrugineux tropical lessivé, dominant au Bénin."""
        assert sg._wrb_to_soil("Lixisol") == "ferrugineux"

    def test_ferralsol_donne_ferrallitique(self):
        """Ferralsol correspond aux sols fortement altérés du Sud-Bénin."""
        assert sg._wrb_to_soil("Ferralsol") == "ferrallitique"

    def test_arenosol_donne_sableux(self):
        """Arenosol correspond aux sables côtiers et dunaires."""
        assert sg._wrb_to_soil("Arenosol") == "sableux"

    def test_luvisol_donne_limoneux(self):
        """Luvisol correspond aux sols de texture fine des couloirs fluviaux."""
        assert sg._wrb_to_soil("Luvisol") == "limoneux"

    def test_classe_inconnue_retourne_ferrugineux(self):
        """Une classe WRB inconnue retourne le sol dominant béninois par défaut."""
        assert sg._wrb_to_soil("ClasseInexistante") == "ferrugineux"

    def test_chaine_vide_retourne_ferrugineux(self):
        """Une chaîne vide retourne le sol de repli."""
        assert sg._wrb_to_soil("") == "ferrugineux"

    def test_none_retourne_ferrugineux(self):
        """None retourne le sol de repli sans lever d'exception."""
        assert sg._wrb_to_soil(None) == "ferrugineux"

    def test_classe_avec_qualificatif_haplic(self):
        """'Haplic Lixisol' doit être reconnu par correspondance partielle."""
        # Les classes WRB contiennent souvent un qualificatif préfixe (ex: "Haplic")
        assert sg._wrb_to_soil("Haplic Lixisol") == "ferrugineux"

    def test_acrisol_donne_ferrugineux(self):
        """Acrisol est apparenté au Lixisol dans les sols béninois."""
        assert sg._wrb_to_soil("Acrisol") == "ferrugineux"

    def test_gleysol_donne_limoneux(self):
        """Gleysol correspond aux zones hydromorphes (alluvions de l'Ouémé)."""
        assert sg._wrb_to_soil("Gleysol") == "limoneux"

    def test_tous_les_types_kadipy_sont_couverts(self):
        """La table de correspondance doit couvrir les 4 types de sols KadiPy."""
        types_presents = set(sg._WRB_VERS_SOL_KADIPY.values())
        types_attendus = {"ferrugineux", "ferrallitique", "sableux", "limoneux"}
        assert types_attendus == types_presents


# ---------------------------------------------------------------------------
# Tests du cache local
# ---------------------------------------------------------------------------

class TestCache:
    """Vérifie le comportement du cache JSON local."""

    def test_cache_vide_retourne_liste_vide(self):
        """Un cache inexistant doit retourner une liste vide sans erreur."""
        assert sg._load_cache() == []

    def test_sauvegarde_puis_chargement(self):
        """Les données sauvegardées doivent être relisibles correctement."""
        points = [{"lat": 9.33, "lon": 2.35, "wrb_class": "Lixisol", "soil_type": "ferrugineux"}]
        sg._save_cache(points)
        recharge = sg._load_cache()
        assert len(recharge) == 1
        assert recharge[0]["soil_type"] == "ferrugineux"

    def test_cache_corrompu_retourne_liste_vide(self, monkeypatch):
        """Un fichier de cache corrompu (JSON invalide) ne doit pas lever d'exception."""
        # Écriture d'un fichier JSON invalide à l'emplacement du cache
        with open(sg._CACHE_FICHIER, "w") as f:
            f.write("ceci n'est pas du JSON valide {{{")
        assert sg._load_cache() == []

    def test_chercher_cache_hit_proche(self):
        """Un point à distance inférieure au seuil doit être trouvé dans le cache."""
        # Point sauvegardé à (9.33, 2.35)
        points = [{"lat": 9.33, "lon": 2.35, "wrb_class": "Lixisol", "soil_type": "ferrugineux"}]
        sg._save_cache(points)

        # Point recherché à seulement 0.01° du point enregistré (bien en dessous du seuil)
        resultat = sg._lookup_cache(lat=9.34, lon=2.35)
        assert resultat == "ferrugineux"

    def test_chercher_cache_miss_trop_loin(self):
        """Un point trop éloigné (> seuil) ne doit pas retourner de résultat du cache."""
        # Point sauvegardé à (9.33, 2.35)
        points = [{"lat": 9.33, "lon": 2.35, "wrb_class": "Lixisol", "soil_type": "ferrugineux"}]
        sg._save_cache(points)

        # Point recherché à 1.0° de distance (bien au-dessus du seuil de 0.25°)
        resultat = sg._lookup_cache(lat=10.33, lon=2.35)
        assert resultat is None

    def test_chercher_cache_vide_retourne_none(self):
        """Une recherche dans un cache vide doit retourner None."""
        assert sg._lookup_cache(lat=9.33, lon=2.35) is None

    def test_seuil_exactement_atteint(self):
        """Un point exactement au seuil doit être considéré comme proche (<=)."""
        points = [{"lat": 9.33, "lon": 2.35, "wrb_class": "Lixisol", "soil_type": "ferrugineux"}]
        sg._save_cache(points)

        # Distance = exactement _CACHE_DISTANCE_SEUIL (0.25°) sur la latitude seule
        lat_recherche = 9.33 + sg._CACHE_DISTANCE_SEUIL
        resultat = sg._lookup_cache(lat=lat_recherche, lon=2.35)
        assert resultat == "ferrugineux"


# ---------------------------------------------------------------------------
# Tests de l'appel API SoilGrids
# ---------------------------------------------------------------------------

class TestAppelAPI:
    """Vérifie l'appel HTTP à l'API SoilGrids avec des réponses mockées."""

    def _reponse_mock(self, wrb_class: str = "Lixisol", status_code: int = 200) -> MagicMock:
        """Crée un objet réponse HTTP simulé."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = {
            "type": "Point",
            "geometry": {"type": "Point", "coordinates": [2.35, 9.33]},
            "properties": {
                "most_probable_wrb_class": wrb_class,
                "probabilities": [
                    {"wrb_class": wrb_class, "percentage": 65},
                    {"wrb_class": "Acrisol", "percentage": 20},
                ],
            },
        }
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_appel_api_retourne_classe_wrb(self):
        """Un appel API réussi doit retourner la classe WRB la plus probable."""
        with patch("requests.get", return_value=self._reponse_mock("Lixisol")):
            resultat = sg._call_api(lat=9.33, lon=2.35)
        assert resultat == "Lixisol"

    def test_appel_api_timeout_retourne_none(self):
        """Un timeout sur tous les essais doit retourner None (sans exception levée)."""
        with patch("requests.get", side_effect=requests.exceptions.Timeout), \
             patch("time.sleep"):  # accélère le test en supprimant les attentes
            resultat = sg._call_api(lat=9.33, lon=2.35)
        assert resultat is None

    def test_appel_api_erreur_connexion_retourne_none(self):
        """Une erreur de connexion sur tous les essais doit retourner None."""
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError), \
             patch("time.sleep"):
            resultat = sg._call_api(lat=9.33, lon=2.35)
        assert resultat is None

    def test_appel_api_reponse_sans_classe_wrb(self):
        """Une réponse valide mais sans classe WRB doit retourner None."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"properties": {}}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            resultat = sg._call_api(lat=9.33, lon=2.35)
        assert resultat is None

    def test_appel_api_fallback_via_probabilities(self):
        """Si 'most_probable_wrb_class' est absent, utiliser la première probabilité."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "properties": {
                "probabilities": [
                    {"wrb_class": "Ferralsol", "percentage": 80},
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            resultat = sg._call_api(lat=6.36, lon=2.42)
        assert resultat == "Ferralsol"

    def test_nombre_de_tentatives_respecte(self):
        """Le module ne doit pas dépasser _MAX_TENTATIVES appels HTTP."""
        compteur = {"n": 0}

        def side_effect(*args, **kwargs):
            compteur["n"] += 1
            raise requests.exceptions.ConnectionError

        with patch("requests.get", side_effect=side_effect), \
             patch("time.sleep"):
            sg._call_api(lat=9.33, lon=2.35)

        assert compteur["n"] == sg._MAX_TENTATIVES


# ---------------------------------------------------------------------------
# Tests de fetch_soil_type (interface publique)
# ---------------------------------------------------------------------------

class TestFetchSoilType:
    """Vérifie le comportement de la fonction publique fetch_soil_type."""

    def test_retourne_depuis_cache_si_disponible(self):
        """Si le cache contient un point proche, aucun appel API ne doit être effectué."""
        points = [{"lat": 9.33, "lon": 2.35, "wrb_class": "Lixisol", "soil_type": "ferrugineux"}]
        sg._save_cache(points)

        with patch("requests.get") as mock_get:
            resultat = sg.fetch_soil_type(lat=9.33, lon=2.35)
            # L'API ne doit pas avoir été appelée
            mock_get.assert_not_called()

        assert resultat == "ferrugineux"

    def test_appelle_api_si_cache_manquant(self):
        """Si le cache est vide, l'API doit être appelée."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "properties": {
                "most_probable_wrb_class": "Ferralsol",
                "probabilities": [{"wrb_class": "Ferralsol", "percentage": 70}],
            }
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            resultat = sg.fetch_soil_type(lat=6.36, lon=2.42)

        assert resultat == "ferrallitique"

    def test_cache_mis_a_jour_apres_appel_api(self):
        """Après un appel API réussi, le point doit être sauvegardé dans le cache."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "properties": {
                "most_probable_wrb_class": "Arenosol",
                "probabilities": [],
            }
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            sg.fetch_soil_type(lat=6.35, lon=2.43)

        # Le cache doit maintenant contenir le point
        points = sg._load_cache()
        assert len(points) == 1
        assert points[0]["wrb_class"] == "Arenosol"
        assert points[0]["soil_type"] == "sableux"

    def test_retourne_fallback_si_api_indisponible(self):
        """Si l'API échoue et le cache est vide, retourner le sol par défaut."""
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError), \
             patch("time.sleep"):
            resultat = sg.fetch_soil_type(lat=9.33, lon=2.35, default_soil="limoneux")

        assert resultat == "limoneux"

    def test_fallback_defaut_est_ferrugineux(self):
        """Sans argument default_soil, le fallback est 'ferrugineux'."""
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError), \
             patch("time.sleep"):
            resultat = sg.fetch_soil_type(lat=9.33, lon=2.35)

        assert resultat == "ferrugineux"

    def test_default_soil_invalide_remplace_par_ferrugineux(self):
        """Un default_soil invalide est silencieusement remplacé par 'ferrugineux'."""
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError), \
             patch("time.sleep"):
            resultat = sg.fetch_soil_type(lat=9.33, lon=2.35, default_soil="granite")

        assert resultat == "ferrugineux"
