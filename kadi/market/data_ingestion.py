"""
Module de connexion aux APIs externes pour l'ingestion de données.
Inclut le client pour WFP DataBridges avec retry, cache et gestion
transparente des données simulées.
"""

import os
import json
import time
import logging
import requests
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Nombre de tentatives par défaut et délai initial du backoff exponentiel
RETRY_ATTEMPTS_DEFAULT = 3
RETRY_BACKOFF_SEC_DEFAULT = 2.0

# Mappings de secours (Fallback) en cas d'échec de l'API.
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

    La logique de retry s'applique aux erreurs réseau (timeout, connexion)
    et aux codes HTTP temporaires (429 rate-limit, 503 serveur indisponible).
    Les erreurs permanentes (401, 404) ne déclenchent pas de retry.

    Args:
        url (str): L'URL cible de la requête.
        headers (dict, optional): En-têtes HTTP à envoyer.
        params (dict, optional): Paramètres de requête (query string).
        timeout (int): Délai maximum d'attente en secondes.
        retry_attempts (int): Nombre maximum de tentatives.
        retry_backoff_sec (float): Délai initial entre deux tentatives (doublé à chaque essai).

    Returns:
        requests.Response: La réponse HTTP si la requête réussit.

    Raises:
        requests.exceptions.RequestException: Si toutes les tentatives ont échoué.
    """
    # Codes HTTP qui méritent un retry (erreurs temporaires)
    codes_a_reessayer = {429, 500, 502, 503, 504}

    derniere_exception = None

    for tentative in range(1, retry_attempts + 1):
        try:
            # Tentative de requête HTTP GET
            response = requests.get(url, headers=headers, params=params, timeout=timeout)

            # Si le code est une erreur permanente, on arrête immédiatement
            if response.status_code in (401, 403, 404):
                return response

            # Si le code est une erreur temporaire et qu'il reste des tentatives
            if response.status_code in codes_a_reessayer and tentative < retry_attempts:
                delai = retry_backoff_sec * (2 ** (tentative - 1))
                logger.warning(
                    f"Code {response.status_code} reçu (tentative {tentative}/{retry_attempts}). "
                    f"Nouvelle tentative dans {delai:.1f}s..."
                )
                time.sleep(delai)
                continue

            # Si la requête est un succès ou une erreur non-retryable, on retourne
            return response

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            derniere_exception = exc
            if tentative < retry_attempts:
                delai = retry_backoff_sec * (2 ** (tentative - 1))
                logger.warning(
                    f"Erreur réseau ({exc.__class__.__name__}, tentative {tentative}/{retry_attempts}). "
                    f"Nouvelle tentative dans {delai:.1f}s..."
                )
                time.sleep(delai)
            else:
                logger.error(f"Toutes les tentatives ont échoué pour {url}: {exc}")

    # Si toutes les tentatives ont échoué, on relance la dernière exception
    raise derniere_exception


class WFPDataBridgesClient:
    """
    Client HTTP pour interagir avec l'API WFP DataBridges (VAM).

    Ce client gère l'authentification, le cache local, le retry avec
    backoff exponentiel, et le repli (fallback) sur des données simulées.
    Lorsque des données simulées sont utilisées, le champ ``is_simulated``
    est toujours présent et vaut ``True`` dans le DataFrame retourné,
    afin que l'appelant puisse en informer l'utilisateur.
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
                directement des données simulées (utile pour les tests).
            env_file (str): Chemin vers le fichier .env contenant le token API.
            cache_file (str, optional): Chemin vers le fichier de cache JSON.
                Si None, utilise ``~/.kadi/wfp_cache.json``.
            retry_attempts (int): Nombre maximum de tentatives par requête HTTP.
            retry_backoff_sec (float): Délai initial en secondes pour le backoff.
        """
        # URL de base de l'API WFP DataBridges
        self.base_url = "https://api.wfp.org/vam-data-bridges/1.3.1"

        # Mode miroir local : sauter l'API et retourner des données simulées
        self.use_local_mirror = use_local_mirror

        # Paramètres de retry réseau
        self.retry_attempts = retry_attempts
        self.retry_backoff_sec = retry_backoff_sec

        # Chargement du token d'authentification
        self.token = self._load_token(env_file)

        # Initialisation du fichier de cache
        if cache_file is None:
            cache_dir = os.path.expanduser("~/.kadi")
            os.makedirs(cache_dir, exist_ok=True)
            self.cache_file = os.path.join(cache_dir, "wfp_cache.json")
        else:
            self.cache_file = cache_file

        # Structure du cache en mémoire
        self.cache = {"commodities": {}, "markets": {}}
        self._load_cache()

    def _load_cache(self):
        """Charge le cache persistant depuis le fichier JSON s'il existe."""
        if os.path.isfile(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cache["commodities"] = data.get("commodities", {})
                    self.cache["markets"] = data.get("markets", {})
            except Exception as e:
                logger.warning(f"Impossible de lire le cache WFP {self.cache_file}: {e}")

    def _save_cache(self):
        """Sauvegarde le cache en mémoire dans le fichier JSON persistant."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le cache WFP {self.cache_file}: {e}")

    def _load_token(self, env_file: str) -> str:
        """
        Charge le token d'authentification WFP depuis les variables
        d'environnement ou le fichier .env.

        Args:
            env_file (str): Chemin vers le fichier .env.

        Returns:
            str: Le token trouvé, ou une chaîne vide si absent.
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
                logger.warning(f"Erreur lors de la lecture du fichier {env_file}: {e}")

        return token

    def _fetch_commodities(self) -> dict:
        """
        Récupère la liste des cultures depuis l'API WFP.
        Utilise le cache en mémoire ou le fallback si l'API est indisponible.

        Returns:
            dict: Mapping {nom_normalise: commodity_id}.
        """
        # Si le cache est déjà rempli, on l'utilise directement
        if self.cache["commodities"]:
            return self.cache["commodities"]

        # Sans token, on utilise le fallback
        if not self.token:
            logger.info("Pas de token WFP : utilisation du mapping de secours pour les cultures.")
            return COMMODITY_MAPPING_FALLBACK

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        endpoint = f"{self.base_url}/Commodities/List"

        try:
            response = _get_with_retry(
                endpoint, headers=headers,
                retry_attempts=self.retry_attempts,
                retry_backoff_sec=self.retry_backoff_sec,
            )

            # Fallback sur /Commodities si /Commodities/List n'existe pas
            if response.status_code == 404:
                endpoint = f"{self.base_url}/Commodities"
                response = _get_with_retry(
                    endpoint, headers=headers,
                    retry_attempts=self.retry_attempts,
                    retry_backoff_sec=self.retry_backoff_sec,
                )

            response.raise_for_status()
            data = response.json()

            # Extraction des items (format WFP : {"items": [{...}]})
            items = data.get("items", [])
            mapping = {}
            for item in items:
                # Les noms de clés peuvent varier selon l'endpoint
                c_id = item.get("commodityID") or item.get("id")
                c_name = item.get("commodityName") or item.get("name")
                if c_id and c_name:
                    mapping[c_name.lower().replace(" ", "_")] = c_id

            if mapping:
                self.cache["commodities"] = mapping
                self._save_cache()
                return mapping

        except Exception as e:
            logger.warning(
                f"Impossible de récupérer les Commodities WFP: {e}. "
                "Utilisation du mapping de secours."
            )

        return COMMODITY_MAPPING_FALLBACK

    def _fetch_markets(self, country_code: str = "BEN") -> dict:
        """
        Récupère la liste des marchés depuis l'API WFP pour le Bénin.
        Utilise le cache ou le fallback si l'API est indisponible.

        Args:
            country_code (str): Code pays ISO3. Fixé à "BEN" pour le V1.

        Returns:
            dict: Mapping {nom_normalise: market_id}.
        """
        # Cache déjà rempli
        if self.cache["markets"]:
            return self.cache["markets"]

        # Sans token, fallback
        if not self.token:
            logger.info("Pas de token WFP : utilisation du mapping de secours pour les marchés.")
            return MARKET_MAPPING_FALLBACK

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        endpoint = f"{self.base_url}/Markets/List"
        # Le code pays est fixé au Bénin pour cette version
        params = {"CountryCode": country_code}

        try:
            response = _get_with_retry(
                endpoint, headers=headers, params=params,
                retry_attempts=self.retry_attempts,
                retry_backoff_sec=self.retry_backoff_sec,
            )

            # Fallback sur /Markets si /Markets/List n'existe pas
            if response.status_code == 404:
                endpoint = f"{self.base_url}/Markets"
                response = _get_with_retry(
                    endpoint, headers=headers, params=params,
                    retry_attempts=self.retry_attempts,
                    retry_backoff_sec=self.retry_backoff_sec,
                )

            response.raise_for_status()
            data = response.json()

            # Extraction des items
            items = data.get("items", [])
            mapping = {}
            for item in items:
                m_id = item.get("marketID") or item.get("id")
                m_name = item.get("marketName") or item.get("name")
                if m_id and m_name:
                    mapping[m_name.lower().replace(" ", "_")] = m_id

            if mapping:
                self.cache["markets"] = mapping
                self._save_cache()
                return mapping

        except Exception as e:
            logger.warning(
                f"Impossible de récupérer les Markets WFP: {e}. "
                "Utilisation du mapping de secours."
            )

        return MARKET_MAPPING_FALLBACK

    def _get_commodity_id(self, commodity_name: str) -> int:
        """
        Récupère l'identifiant WFP d'une culture par son nom.

        Args:
            commodity_name (str): Nom normalisé de la culture (ex: 'maize').

        Returns:
            int: L'identifiant WFP, ou 0 si introuvable.
        """
        key = commodity_name.lower().replace(" ", "_")
        mapping = self._fetch_commodities()
        return mapping.get(key, COMMODITY_MAPPING_FALLBACK.get(key, 0))

    def _get_market_id(self, market_name: str) -> int:
        """
        Récupère l'identifiant WFP d'un marché par son nom.

        Args:
            market_name (str): Nom normalisé du marché (ex: 'cotonou').

        Returns:
            int: L'identifiant WFP, ou 0 si introuvable.
        """
        key = market_name.lower().replace(" ", "_")
        mapping = self._fetch_markets()
        return mapping.get(key, MARKET_MAPPING_FALLBACK.get(key, 0))

    def _validate_api_response_items(self, items: list) -> list:
        """
        Valide et nettoie les items bruts retournés par l'API WFP.

        Vérifie que chaque item contient les colonnes essentielles et
        que les types sont cohérents (date parseable, prix numérique positif).
        Les items invalides sont ignorés avec un avertissement.

        Args:
            items (list): Liste de dictionnaires bruts de l'API.

        Returns:
            list: Liste des items valides uniquement.
        """
        items_valides = []

        for i, item in enumerate(items):
            # Vérification de la présence du prix
            prix_brut = item.get("ActualPrice") or item.get("price")
            if prix_brut is None:
                logger.debug(f"Item {i} ignoré : prix manquant.")
                continue

            # Vérification que le prix est un nombre positif
            try:
                prix = float(prix_brut)
                if prix < 0:
                    logger.debug(f"Item {i} ignoré : prix négatif ({prix}).")
                    continue
            except (ValueError, TypeError):
                logger.debug(f"Item {i} ignoré : prix non numérique ('{prix_brut}').")
                continue

            # Vérification de la présence d'une date
            date_brute = item.get("CommodityPriceDate") or item.get("date")
            if not date_brute:
                logger.debug(f"Item {i} ignoré : date manquante.")
                continue

            # L'item est valide
            items_valides.append(item)

        # Avertissement si une partie des données a été écartée
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
        Récupère les prix historiques pour un marché et une culture depuis WFP DataBridges.

        Le DataFrame retourné contient toujours une colonne ``is_simulated`` :
        - ``False`` si les données proviennent de l'API WFP,
        - ``True`` si les données sont simulées (fallback ou mode miroir).

        Utilisez toujours ce champ pour informer l'utilisateur final de
        la nature des données qu'il consulte.

        Args:
            market_name (str): Nom normalisé du marché (ex: 'cotonou').
            commodity (str): Code de la culture (ex: 'maize').
            time_range (tuple, optional): Tuple (date_debut, date_fin) au format 'YYYY-MM-DD'.

        Returns:
            pd.DataFrame: DataFrame avec colonnes 'date', 'price', 'unit', 'is_simulated'.
        """
        # Mode miroir : retourner directement des données simulées
        if self.use_local_mirror:
            logger.info("Mode miroir local actif : données simulées retournées.")
            return self._generate_simulated_data(time_range)

        market_id = self._get_market_id(market_name)
        commodity_id = self._get_commodity_id(commodity)

        # Infos insuffisantes pour interroger l'API : fallback simulé
        if market_id == 0 or commodity_id == 0 or not self.token:
            logger.warning(
                "Infos manquantes (Token/ID marché/ID culture). "
                "Données simulées utilisées en remplacement."
            )
            return self._generate_simulated_data(time_range)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        endpoint = f"{self.base_url}/MarketPrices/alldata"
        params = {
            "CountryCode": "BEN",
            "MarketID": market_id,
            "CommodityID": commodity_id,
        }

        # Ajout de la plage de dates si fournie
        if time_range and len(time_range) == 2:
            params["StartDate"] = time_range[0]
            params["EndDate"] = time_range[1]

        try:
            response = _get_with_retry(
                endpoint,
                headers=headers,
                params=params,
                retry_attempts=self.retry_attempts,
                retry_backoff_sec=self.retry_backoff_sec,
            )
            response.raise_for_status()

            data = response.json()
            items_bruts = data.get("items", [])

            # Validation des données brutes avant traitement
            items = self._validate_api_response_items(items_bruts)

            if not items:
                logger.warning(
                    f"Aucune donnée valide retournée par WFP pour "
                    f"{market_name}/{commodity}. Données simulées utilisées."
                )
                return self._generate_simulated_data(time_range)

            # Construction du DataFrame
            df = pd.DataFrame(items)

            # Renommage des colonnes vers le format interne standard
            col_mapping = {
                "CommodityPriceDate": "date",
                "ActualPrice": "price",
                "UnitName": "unit",
            }
            rename_dict = {k: v for k, v in col_mapping.items() if k in df.columns}
            df = df.rename(columns=rename_dict)

            # Conversion de la colonne date en datetime
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")

            # Marquage explicite : ces données viennent de l'API réelle
            df["is_simulated"] = False

            return df

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Erreur API WFP après {self.retry_attempts} tentatives : {e}. "
                "Données simulées utilisées."
            )
            return self._generate_simulated_data(time_range)

    def get_market_functionality_index(self, market_id: str) -> float:
        """
        Retourne l'indice de fonctionnalité d'un marché.

        Note : cette méthode est un stub dans le V1. Elle retourne une valeur
        fixe en attendant l'intégration de données réelles (FEWSNET ou WFP).

        Args:
            market_id (str): L'identifiant du marché.

        Returns:
            float: L'indice de fonctionnalité (stub : toujours 7.9 / 10).
        """
        # Stub V1 : valeur en dur, à remplacer par une vraie source de données
        return 7.9

    def _generate_simulated_data(self, time_range: tuple = None) -> pd.DataFrame:
        """
        Génère des données de prix simulées (bruit gaussien) pour le mode fallback.

        AVERTISSEMENT : ces données sont entièrement fictives. Elles ne doivent
        jamais être présentées à l'utilisateur final comme des prix réels.
        Le champ ``is_simulated=True`` dans le DataFrame signale cet état.

        Args:
            time_range (tuple, optional): Tuple (date_debut, date_fin).
                Si None, génère 365 jours se terminant aujourd'hui.

        Returns:
            pd.DataFrame: DataFrame simulé avec colonnes 'date', 'price',
                'unit', 'is_simulated'. ``is_simulated`` vaut toujours True.
        """
        # Génération de la plage de dates
        if time_range and len(time_range) == 2:
            dates = pd.date_range(start=time_range[0], end=time_range[1], freq="D")
        else:
            dates = pd.date_range(end=pd.Timestamp.today(), periods=365, freq="D")

        nb_jours = len(dates)

        # Génération de prix aléatoires centrés sur 300 XOF/kg
        prix_aleatoires = np.random.normal(loc=300, scale=20, size=nb_jours)

        # Construction du DataFrame avec le flag is_simulated = True
        df = pd.DataFrame(
            {
                "date": dates,
                "price": prix_aleatoires,
                "unit": "XOF/kg",
                # Ce flag est CRITIQUE : il indique que les données sont fictives
                "is_simulated": True,
            }
        )

        logger.warning(
            "Données simulées retournées (is_simulated=True). "
            "Ces valeurs sont des estimations fictives et ne doivent pas "
            "être utilisées pour des décisions commerciales réelles."
        )

        return df
