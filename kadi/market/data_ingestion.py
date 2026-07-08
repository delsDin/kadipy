"""
Module de connexion aux APIs externes pour l'ingestion de données de marché.

Inclut le client WFP DataBridges avec :
- Retry avec backoff exponentiel
- Cache SQLite (~/kadi/market_prices.db) pour limiter les appels réseau
- Flag is_simulated transparent dans tous les retours
- Colonnes enrichies : source, fetched_at, confidence_score

Note : sans clé API WFP (WFP_API_Token), le système fonctionne entièrement
en mode fallback simulé. Toutes les méthodes restent appelables.
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

import pandas as pd
import numpy as np

# Import du module de cache SQLite dédié aux prix de marché
from kadi.market._cache import (
    recuperer_prix,
    sauvegarder_prix,
    calculer_score_confiance,
)

logger = logging.getLogger(__name__)

# Nombre de tentatives par défaut et délai initial du backoff exponentiel
RETRY_ATTEMPTS_DEFAULT = 3
RETRY_BACKOFF_SEC_DEFAULT = 2.0

# Mappings de secours utilisés quand l'API WFP est inaccessible ou sans token.
# Ces identifiants correspondent aux marchés et cultures officiels WFP pour le Bénin.
COMMODITY_MAPPING_FALLBACK = {
    "maize": 51,
    "maize_white": 51,
    "rice": 73,
    "sorghum": 58,
    "yam": 97,
    "cassava": 83,
    "cowpea": 67,
    "soybean": 60,
    "millet": 56,
}

MARKET_MAPPING_FALLBACK = {
    "cotonou": 1001,
    "dantokpa": 1001,
    "parakou": 1002,
    "malanville": 1003,
    "savalou": 1234,
    "savalou_market": 1234,
    "abomey": 1005,
    "natitingou": 1006,
    "porto_novo": 1007,
    "bohicon": 1008,
    "kandi": 1009,
}


def _get_with_retry(
    url: str,
    headers: dict = None,
    params: dict = None,
    timeout: int = 10,
    retry_attempts: int = RETRY_ATTEMPTS_DEFAULT,
    retry_backoff_sec: float = RETRY_BACKOFF_SEC_DEFAULT,
) -> requests.Response:
    """
    Effectue une requête GET HTTP avec retry et backoff exponentiel.

    Le retry s'applique aux erreurs réseau (timeout, connexion) et aux codes
    HTTP temporaires (429, 500, 502, 503, 504). Les erreurs permanentes
    (401, 403, 404) ne déclenchent pas de retry.

    Args:
        url (str): L'URL cible.
        headers (dict, optional): En-têtes HTTP à envoyer.
        params (dict, optional): Paramètres de la requête (query string).
        timeout (int): Délai maximum d'attente en secondes. Défaut : 10.
        retry_attempts (int): Nombre maximum de tentatives. Défaut : 3.
        retry_backoff_sec (float): Délai initial entre tentatives (doublé à chaque essai).

    Returns:
        requests.Response: La réponse HTTP si la requête réussit.

    Raises:
        requests.exceptions.RequestException: Si toutes les tentatives ont échoué.
    """
    # Codes HTTP temporaires qui méritent un retry
    codes_temporaires = {429, 500, 502, 503, 504}
    derniere_exception = None

    for tentative in range(1, retry_attempts + 1):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)

            # Erreurs permanentes : on retourne immédiatement sans retry
            if response.status_code in (401, 403, 404):
                return response

            # Erreurs temporaires : on attend et on réessaie
            if response.status_code in codes_temporaires and tentative < retry_attempts:
                delai = retry_backoff_sec * (2 ** (tentative - 1))
                logger.warning(
                    f"Code {response.status_code} reçu "
                    f"(tentative {tentative}/{retry_attempts}). "
                    f"Nouvelle tentative dans {delai:.1f}s..."
                )
                time.sleep(delai)
                continue

            return response

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            derniere_exception = exc
            if tentative < retry_attempts:
                delai = retry_backoff_sec * (2 ** (tentative - 1))
                logger.warning(
                    f"Erreur réseau ({exc.__class__.__name__}, "
                    f"tentative {tentative}/{retry_attempts}). "
                    f"Nouvelle tentative dans {delai:.1f}s..."
                )
                time.sleep(delai)
            else:
                logger.error(
                    f"Toutes les tentatives ont échoué pour {url}: {exc}"
                )

    raise derniere_exception


class WFPDataBridgesClient:
    """
    Client HTTP pour l'API WFP DataBridges (VAM).

    Gère l'authentification, le cache SQLite local, le retry avec backoff
    exponentiel, et le repli transparent sur des données simulées.

    Fonctionnement sans clé API :
        Si aucun token WFP n'est configuré, le client retourne des données
        simulées (is_simulated=True, confidence_score=0.1) sans erreur.
        Cela permet de développer et tester sans accès réseau.

    Colonnes toujours présentes dans les DataFrames retournés :
        - is_simulated    : True si les données sont fictives
        - source          : 'wfp-vam', 'ratin', 'scrape-local', ou 'simulated'
        - fetched_at      : horodatage ISO de la récupération
        - confidence_score: score 0.0 à 1.0 (source + fraîcheur)
    """

    def __init__(
        self,
        use_local_mirror: bool = False,
        env_file: str = ".env",
        cache_file: str = None,
        retry_attempts: int = RETRY_ATTEMPTS_DEFAULT,
        retry_backoff_sec: float = RETRY_BACKOFF_SEC_DEFAULT,
    ):
        """
        Initialise le client WFP DataBridges.

        Args:
            use_local_mirror (bool): Si True, ignore l'API et retourne
                directement des données simulées. Utile pour les tests.
            env_file (str): Chemin vers le fichier .env contenant le token API.
            cache_file (str, optional): Chemin vers le fichier JSON de cache
                des IDs (commodités et marchés). Par défaut : ~/.kadi/wfp_cache.json.
            retry_attempts (int): Nombre maximum de tentatives par requête HTTP.
            retry_backoff_sec (float): Délai initial en secondes pour le backoff.
        """
        # URL de base de l'API WFP DataBridges
        self.base_url = "https://api.wfp.org/vam-data-bridges/1.3.1"

        # Mode miroir local (bypass de l'API pour les tests)
        self.use_local_mirror = use_local_mirror

        # Paramètres de retry réseau
        self.retry_attempts = retry_attempts
        self.retry_backoff_sec = retry_backoff_sec

        # Chargement du token d'authentification WFP
        self.token = self._charger_token(env_file)

        # Fichier JSON de cache pour les IDs de commodités et marchés
        if cache_file is None:
            from kadi.config import CACHE_DIR
            self.cache_file = str(CACHE_DIR / "wfp_cache.json")
        else:
            self.cache_file = cache_file

        # Cache en mémoire pour les IDs WFP (commodités et marchés)
        self.cache = {"commodities": {}, "markets": {}}
        self._charger_cache_ids()

    def _charger_cache_ids(self):
        """Charge le cache JSON des IDs (commodités et marchés) depuis le disque."""
        if os.path.isfile(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cache["commodities"] = data.get("commodities", {})
                    self.cache["markets"] = data.get("markets", {})
            except Exception as e:
                logger.warning(f"Impossible de lire le cache IDs WFP : {e}")

    def _sauvegarder_cache_ids(self):
        """Sauvegarde le cache JSON des IDs sur le disque."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le cache IDs WFP : {e}")

    def _charger_token(self, env_file: str) -> str:
        """
        Charge le token WFP depuis les variables d'environnement ou le fichier .env.

        Args:
            env_file (str): Chemin vers le fichier .env.

        Returns:
            str: Le token WFP si trouvé, sinon une chaîne vide.
        """
        # Priorité 1 : variable d'environnement
        token = os.environ.get("WFP_API_Token", os.environ.get("WFP_API_KEY", ""))

        # Priorité 2 : fichier .env
        if not token and os.path.isfile(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split("=", 1)
                            if len(parts) == 2 and parts[0].strip() in (
                                "WFP_API_Token",
                                "WFP_API_KEY",
                            ):
                                token = parts[1].strip().strip("'\"")
                                break
            except Exception as e:
                logger.warning(f"Erreur lecture du fichier {env_file}: {e}")

        if not token:
            logger.info(
                "Aucun token WFP trouvé. Le client fonctionnera en mode "
                "fallback simulé jusqu'à la configuration de WFP_API_Token."
            )

        return token

    def _recuperer_commodites(self) -> dict:
        """
        Récupère la liste des cultures depuis l'API WFP et la met en cache.

        Returns:
            dict: Mapping {nom_normalise: commodity_id}.
        """
        # Cache en mémoire disponible
        if self.cache["commodities"]:
            return self.cache["commodities"]

        # Sans token, on retourne le fallback directement
        if not self.token:
            return COMMODITY_MAPPING_FALLBACK

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        for endpoint in (
            f"{self.base_url}/Commodities/List",
            f"{self.base_url}/Commodities",
        ):
            try:
                response = _get_with_retry(
                    endpoint, headers=headers,
                    retry_attempts=self.retry_attempts,
                    retry_backoff_sec=self.retry_backoff_sec,
                )
                if response.status_code == 404:
                    continue
                response.raise_for_status()

                items = response.json().get("items", [])
                mapping = {}
                for item in items:
                    c_id = item.get("commodityID") or item.get("id")
                    c_name = item.get("commodityName") or item.get("name")
                    if c_id and c_name:
                        mapping[c_name.lower().replace(" ", "_")] = c_id

                if mapping:
                    self.cache["commodities"] = mapping
                    self._sauvegarder_cache_ids()
                    return mapping
                break

            except Exception as e:
                logger.warning(
                    f"Impossible de récupérer les Commodities WFP depuis {endpoint}: {e}. "
                    "Utilisation du mapping de secours."
                )
                break

        return COMMODITY_MAPPING_FALLBACK

    def _recuperer_marches(self, country_code: str = "BEN") -> dict:
        """
        Récupère la liste des marchés WFP pour le Bénin.

        Args:
            country_code (str): Code pays ISO3. Fixé à 'BEN' pour le V1.

        Returns:
            dict: Mapping {nom_normalise: market_id}.
        """
        if self.cache["markets"]:
            return self.cache["markets"]

        if not self.token:
            return MARKET_MAPPING_FALLBACK

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        for endpoint in (
            f"{self.base_url}/Markets/List",
            f"{self.base_url}/Markets",
        ):
            try:
                response = _get_with_retry(
                    endpoint, headers=headers,
                    params={"CountryCode": country_code},
                    retry_attempts=self.retry_attempts,
                    retry_backoff_sec=self.retry_backoff_sec,
                )
                if response.status_code == 404:
                    continue
                response.raise_for_status()

                items = response.json().get("items", [])
                mapping = {}
                for item in items:
                    m_id = item.get("marketID") or item.get("id")
                    m_name = item.get("marketName") or item.get("name")
                    if m_id and m_name:
                        mapping[m_name.lower().replace(" ", "_")] = m_id

                if mapping:
                    self.cache["markets"] = mapping
                    self._sauvegarder_cache_ids()
                    return mapping
                break

            except Exception as e:
                logger.warning(
                    f"Impossible de récupérer les Markets WFP depuis {endpoint}: {e}. "
                    "Utilisation du mapping de secours."
                )
                break

        return MARKET_MAPPING_FALLBACK

    def _get_commodity_id(self, commodity_name: str) -> int:
        """
        Retourne l'identifiant WFP d'une culture par son nom normalisé.

        Args:
            commodity_name (str): Nom normalisé de la culture (ex: 'maize').

        Returns:
            int: L'identifiant WFP, ou 0 si introuvable.
        """
        key = commodity_name.lower().replace(" ", "_")
        mapping = self._recuperer_commodites()
        return mapping.get(key, COMMODITY_MAPPING_FALLBACK.get(key, 0))

    def _get_market_id(self, market_name: str) -> int:
        """
        Retourne l'identifiant WFP d'un marché par son nom normalisé.

        Args:
            market_name (str): Nom normalisé du marché (ex: 'cotonou').

        Returns:
            int: L'identifiant WFP, ou 0 si introuvable.
        """
        key = market_name.lower().replace(" ", "_")
        mapping = self._recuperer_marches()
        return mapping.get(key, MARKET_MAPPING_FALLBACK.get(key, 0))

    def _validate_api_response_items(self, items: list) -> list:
        """
        Valide et nettoie les items bruts retournés par l'API WFP.

        Chaque item doit avoir un prix numérique positif et une date valide.
        Les items invalides sont ignorés avec un avertissement dans les logs.

        Args:
            items (list): Liste de dictionnaires bruts provenant de l'API.

        Returns:
            list: Liste des items valides uniquement.
        """
        items_valides = []

        for i, item in enumerate(items):
            # Vérification du prix
            prix_brut = item.get("ActualPrice") or item.get("price")
            if prix_brut is None:
                logger.debug(f"Item {i} ignoré : prix manquant.")
                continue

            try:
                prix = float(prix_brut)
                if prix < 0:
                    logger.debug(f"Item {i} ignoré : prix négatif ({prix}).")
                    continue
            except (ValueError, TypeError):
                logger.debug(f"Item {i} ignoré : prix non numérique ('{prix_brut}').")
                continue

            # Vérification de la date
            date_brute = item.get("CommodityPriceDate") or item.get("date")
            if not date_brute:
                logger.debug(f"Item {i} ignoré : date manquante.")
                continue

            items_valides.append(item)

        nb_ignores = len(items) - len(items_valides)
        if nb_ignores > 0:
            logger.warning(
                f"{nb_ignores}/{len(items)} items API ignorés "
                "car invalides (prix manquant, négatif, ou date absente)."
            )

        return items_valides

    def get_market_prices(
        self,
        market_name: str,
        commodity: str,
        time_range: tuple = None,
    ) -> pd.DataFrame:
        """
        Récupère les prix historiques pour un marché et une culture.

        Stratégie en cascade (la première source disponible est utilisée) :
        1. Cache SQLite local (~/kadi/market_prices.db) si les données sont fraîches
        2. API WFP DataBridges (si le token WFP_API_Token est configuré)
        3. Données simulées en dernier recours (is_simulated=True)

        Le DataFrame retourné contient toujours ces colonnes standards :
        - ``date``             : datetime de l'observation
        - ``price``            : prix en XOF/kg
        - ``unit``             : unité d'origine ('KG', 'XOF/kg', etc.)
        - ``is_simulated``     : True si les données sont fictives
        - ``source``           : 'wfp-vam', 'cache', 'simulated'
        - ``fetched_at``       : horodatage ISO de la récupération
        - ``confidence_score`` : score 0.0 à 1.0 (source + fraîcheur)

        Args:
            market_name (str): Nom normalisé du marché (ex: 'cotonou').
            commodity (str): Code de la culture (ex: 'maize').
            time_range (tuple, optional): (date_debut, date_fin) en 'YYYY-MM-DD'.

        Returns:
            pd.DataFrame: DataFrame enrichi avec toutes les colonnes standards.
        """
        from kadi.config import CONFIG

        # Durée de vie du cache (en jours) lue depuis la configuration
        max_age_jours = CONFIG.get("market", {}).get("cache_ttl_prices_days", 7)

        # ----------------------------------------------------------------
        # Étape 1 : mode miroir local (pour les tests automatiques)
        # Le mode miroir court-circuite toutes les autres couches.
        # ----------------------------------------------------------------
        if self.use_local_mirror:
            logger.info("Mode miroir local actif : données simulées retournées.")
            return self._generer_donnees_simulees(time_range)

        # ----------------------------------------------------------------
        # Étape 2 : lecture du cache SQLite si les données sont fraîches
        # ----------------------------------------------------------------
        df_cache = recuperer_prix(market_name, commodity, max_age_jours=max_age_jours)
        if df_cache is not None and not df_cache.empty:
            logger.info(
                f"Cache hit pour {market_name}/{commodity} "
                f"({len(df_cache)} lignes)."
            )
            # Calcul et ajout du score de confiance basé sur le cache
            df_cache["confidence_score"] = calculer_score_confiance(
                market_name, commodity, max_age_jours=max_age_jours
            )
            return df_cache

        # ----------------------------------------------------------------
        # Étape 3 : appel à l'API WFP DataBridges
        # ----------------------------------------------------------------
        market_id = self._get_market_id(market_name)
        commodity_id = self._get_commodity_id(commodity)

        # Sans token ou sans IDs valides : fallback simulé
        if market_id == 0 or commodity_id == 0 or not self.token:
            logger.warning(
                "Pas de token WFP ou IDs introuvables. "
                "Données simulées utilisées en remplacement."
            )
            return self._generer_donnees_simulees(time_range)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        params = {
            "CountryCode": "BEN",
            "MarketID": market_id,
            "CommodityID": commodity_id,
        }
        if time_range and len(time_range) == 2:
            params["StartDate"] = time_range[0]
            params["EndDate"] = time_range[1]

        try:
            response = _get_with_retry(
                f"{self.base_url}/MarketPrices/alldata",
                headers=headers,
                params=params,
                retry_attempts=self.retry_attempts,
                retry_backoff_sec=self.retry_backoff_sec,
            )
            response.raise_for_status()

            items_bruts = response.json().get("items", [])
            items = self._validate_api_response_items(items_bruts)

            if not items:
                logger.warning(
                    f"Aucune donnée valide de l'API WFP pour {market_name}/{commodity}. "
                    "Données simulées utilisées."
                )
                return self._generer_donnees_simulees(time_range)

            # Construction du DataFrame à partir des items validés
            df = pd.DataFrame(items)

            # Renommage vers le format interne standard
            col_mapping = {
                "CommodityPriceDate": "date",
                "ActualPrice": "price",
                "UnitName": "unit",
            }
            df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")

            # Ajout des colonnes standards
            maintenant = datetime.now(timezone.utc).isoformat()
            df["is_simulated"] = False
            df["source"] = "wfp-vam"
            df["fetched_at"] = maintenant

            # ----------------------------------------------------------------
            # Sauvegarde dans le cache SQLite pour les prochains appels
            # ----------------------------------------------------------------
            try:
                nb = sauvegarder_prix(market_name, commodity, df, source="wfp-vam")
                logger.debug(f"Cache : {nb} nouvelles lignes sauvegardées pour {market_name}/{commodity}.")
            except Exception as e:
                # L'échec du cache ne bloque pas le retour des données
                logger.warning(f"Échec de la sauvegarde dans le cache SQLite : {e}")

            # Ajout du score de confiance
            df["confidence_score"] = calculer_score_confiance(
                market_name, commodity, max_age_jours=max_age_jours
            )

            return df

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Erreur API WFP après {self.retry_attempts} tentatives : {e}. "
                "Données simulées utilisées."
            )
            return self._generer_donnees_simulees(time_range)

    def get_market_functionality_index(self, market_id: str) -> float:
        """
        Retourne l'indice de fonctionnalité d'un marché.

        Note : stub V1. Retourne une valeur fixe en attendant l'intégration
        de données réelles (FEWSNET ou WFP Market Monitor).

        Args:
            market_id (str): L'identifiant du marché.

        Returns:
            float: Indice de fonctionnalité (stub : 7.9 / 10).
        """
        # Stub V1 : valeur en dur, à remplacer par une vraie source
        return 7.9

    def _generer_donnees_simulees(self, time_range: tuple = None) -> pd.DataFrame:
        """
        Génère des données de prix simulées (bruit gaussien) pour le fallback.

        AVERTISSEMENT : ces données sont entièrement fictives. Le champ
        is_simulated=True et confidence_score=0.1 signalent cet état.
        Ne jamais présenter ces données à un utilisateur comme des prix réels.

        Args:
            time_range (tuple, optional): (date_debut, date_fin) en 'YYYY-MM-DD'.
                Si None, génère 365 jours se terminant aujourd'hui.

        Returns:
            pd.DataFrame: DataFrame simulé avec toutes les colonnes standards.
        """
        # Génération de la plage de dates
        if time_range and len(time_range) == 2:
            dates = pd.date_range(start=time_range[0], end=time_range[1], freq="D")
        else:
            dates = pd.date_range(end=pd.Timestamp.today(), periods=365, freq="D")

        nb_jours = len(dates)

        # Prix aléatoires centrés sur 300 XOF/kg (valeur de référence béninoise)
        prix_aleatoires = np.random.normal(loc=300, scale=20, size=nb_jours)

        maintenant = datetime.now(timezone.utc).isoformat()

        df = pd.DataFrame({
            "date": dates,
            "price": prix_aleatoires,
            "unit": "XOF/kg",
            "is_simulated": True,
            "source": "simulated",
            "fetched_at": maintenant,
            "confidence_score": 0.1,
        })

        logger.warning(
            "Données simulées retournées (is_simulated=True, confidence_score=0.1). "
            "Ne pas utiliser pour des décisions commerciales réelles."
        )

        return df
