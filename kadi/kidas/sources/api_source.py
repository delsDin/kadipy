# -*- coding: utf-8 -*-
"""
Module implémentant APIDataSource pour l'interfaçage avec des APIs REST.

Ce module gère les appels aux APIs agricoles et climatiques utilisées en
AgriTech : Open-Meteo (météo), WFP VAM (prix marchés), FAO (production
agricole), SoilGrids (propriétés des sols). Il intègre une gestion du
rate limiting et un mécanisme de réessai avec backoff exponentiel.
"""

import logging
import time
from typing import Any, Dict, Optional

import pandas as pd
import requests

# Import de la classe de base et des exceptions personnalisées
from kadi.kidas.sources.base import DataSource
from kadi.exceptions import KidasReadError, KidasWriteError, KidasConnectionError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Codes HTTP indiquant une erreur temporaire (réessayables)
_HTTP_RETRY_CODES = {429, 500, 502, 503, 504}

# Délai maximum entre deux réessais (secondes)
_MAX_BACKOFF_SEC = 60


class APIDataSource(DataSource):
    """Source de données pour les APIs REST agricoles et climatiques.

    Gère les appels HTTP GET/POST avec gestion du rate limiting,
    réessais automatiques avec backoff exponentiel, et parse de la
    réponse en DataFrame pandas.

    Attributs:
        api_url (str): URL de base de l'endpoint API.
        auth_token (str | None): Jeton d'authentification Bearer.
            None pour les APIs publiques.
        rate_limit_per_sec (float): Nombre maximum de requêtes par seconde.
        _last_request_time (float): Timestamp de la dernière requête HTTP.
        _schema_cache (dict | None): Schéma API mis en cache.

    Exemple:
        >>> source = APIDataSource(
        ...     'https://api.open-meteo.com/v1/forecast',
        ...     rate_limit_per_sec=10,
        ... )
        >>> df = source.read({
        ...     'latitude': 6.36,
        ...     'longitude': 2.42,
        ...     'daily': 'temperature_2m_max',
        ... })
    """

    def __init__(
        self,
        api_url: str,
        auth_token: Optional[str] = None,
        rate_limit_per_sec: float = 5.0,
    ) -> None:
        """Initialise la source API avec gestion du rate limiting.

        Args:
            api_url (str): URL de base de l'endpoint API (sans paramètres).
            auth_token (str | None): Jeton Bearer pour les APIs authentifiées.
                None pour les APIs publiques (Open-Meteo, etc.).
            rate_limit_per_sec (float): Nombre maximal de requêtes autorisées
                par seconde. Par défaut 5.0.
        """
        # Initialisation de la classe parente avec le type 'api'
        super().__init__(
            source_path=api_url,
            source_type="api",
            encoding="utf-8",
        )

        # URL de base de l'endpoint API
        self.api_url: str = api_url

        # Jeton d'authentification (None pour APIs publiques)
        self.auth_token: Optional[str] = auth_token

        # Limite de débit en requêtes/seconde
        self.rate_limit_per_sec: float = rate_limit_per_sec

        # Timestamp de la dernière requête (pour le rate limiting)
        self._last_request_time: float = 0.0

        # Cache du schéma API
        self._schema_cache: Optional[dict] = None

    def _construire_entetes(self) -> Dict[str, str]:
        """Construit les en-têtes HTTP pour la requête API.

        Returns:
            dict: Dictionnaire des en-têtes HTTP avec authentification
                si un jeton est configuré.
        """
        # En-têtes de base communs à toutes les requêtes
        entetes: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "KadiPy/1.0 (AgriTech Benin)",
        }

        # Ajout du jeton d'authentification si disponible
        if self.auth_token:
            entetes["Authorization"] = f"Bearer {self.auth_token}"

        return entetes

    def _respecter_rate_limit(self) -> None:
        """Applique le délai nécessaire pour respecter le rate limit.

        Calcule le temps écoulé depuis la dernière requête et attend
        si nécessaire pour ne pas dépasser la limite de débit configurée.
        """
        # Délai minimum entre deux requêtes (en secondes)
        delai_minimum = 1.0 / self.rate_limit_per_sec

        # Temps écoulé depuis la dernière requête
        temps_ecoule = time.monotonic() - self._last_request_time

        if temps_ecoule < delai_minimum:
            # Attente du temps restant pour respecter la limite
            temps_attente = delai_minimum - temps_ecoule
            logger.debug(
                "Rate limiting : attente de %.3f secondes.", temps_attente
            )
            time.sleep(temps_attente)

    def fetch_with_retry(
        self,
        params: Dict[str, Any],
        max_retries: int = 3,
        backoff_sec: float = 5.0,
    ) -> dict:
        """Effectue une requête GET avec réessais et backoff exponentiel.

        En cas d'erreur temporaire (codes 429, 500, 502, 503, 504),
        réessaie automatiquement avec un délai croissant.

        Args:
            params (dict): Paramètres de la requête GET (query string).
            max_retries (int): Nombre maximum de tentatives en cas d'échec.
                Par défaut 3.
            backoff_sec (float): Délai de base (en secondes) entre les
                réessais. Le délai est doublé à chaque tentative.
                Par défaut 5.0.

        Returns:
            dict: La réponse JSON parsée de l'API.

        Raises:
            KidasConnectionError: Si l'API est inaccessible après toutes
                les tentatives.
            KidasReadError: Si la réponse n'est pas un JSON valide.
        """
        derniere_erreur: Optional[Exception] = None

        for tentative in range(max_retries + 1):
            try:
                # Respect du rate limit avant chaque requête
                self._respecter_rate_limit()

                # Enregistrement du timestamp de la requête
                self._last_request_time = time.monotonic()

                # Exécution de la requête HTTP GET
                reponse = requests.get(
                    self.api_url,
                    params=params,
                    headers=self._construire_entetes(),
                    timeout=30,
                )

                # Journalisation de la requête
                logger.debug(
                    "Requête API [tentative %d/%d] : %s (status: %d).",
                    tentative + 1,
                    max_retries + 1,
                    reponse.url,
                    reponse.status_code,
                )

                # Vérification si le code est réessayable
                if reponse.status_code in _HTTP_RETRY_CODES and tentative < max_retries:
                    # Calcul du backoff exponentiel
                    delai_attente = min(backoff_sec * (2 ** tentative), _MAX_BACKOFF_SEC)
                    logger.warning(
                        "Erreur HTTP %d. Réessai dans %.1f secondes (tentative %d/%d).",
                        reponse.status_code,
                        delai_attente,
                        tentative + 1,
                        max_retries,
                    )
                    time.sleep(delai_attente)
                    continue

                # Levée d'exception pour les codes d'erreur non-réessayables
                reponse.raise_for_status()

                # Parse et retour de la réponse JSON
                return reponse.json()

            except requests.exceptions.ConnectionError as erreur:
                derniere_erreur = erreur
                if tentative < max_retries:
                    delai_attente = min(backoff_sec * (2 ** tentative), _MAX_BACKOFF_SEC)
                    logger.warning(
                        "Erreur de connexion. Réessai dans %.1f sec.", delai_attente
                    )
                    time.sleep(delai_attente)

            except requests.exceptions.HTTPError as erreur:
                # Erreur HTTP non-réessayable
                raise KidasConnectionError(
                    f"Erreur HTTP lors de l'appel à '{self.api_url}' : {erreur}"
                ) from erreur

            except ValueError as erreur:
                # Réponse non-JSON
                raise KidasReadError(
                    f"La réponse de '{self.api_url}' n'est pas du JSON valide : {erreur}"
                ) from erreur

        # Toutes les tentatives ont échoué
        raise KidasConnectionError(
            f"API '{self.api_url}' inaccessible après {max_retries + 1} tentatives. "
            f"Dernière erreur : {derniere_erreur}"
        )

    def read(self, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Effectue une requête GET et retourne la réponse sous forme de DataFrame.

        Gère automatiquement les réponses JSON de type dict (avec clé 'data'
        ou 'results') et les réponses de type liste.

        Args:
            params (dict | None): Paramètres de la requête GET.
                Par défaut None (requête sans paramètres).

        Returns:
            pd.DataFrame: Les données de la réponse API sous forme tabulaire.

        Raises:
            KidasConnectionError: Si l'API est inaccessible.
            KidasReadError: Si la conversion en DataFrame échoue.
        """
        # Paramètres de requête par défaut
        parametres = params or {}

        # Exécution de la requête avec réessais
        donnees_brutes = self.fetch_with_retry(parametres)

        try:
            # Normalisation de la structure de réponse en liste d'enregistrements
            if isinstance(donnees_brutes, list):
                # Réponse déjà sous forme de liste
                enregistrements = donnees_brutes
            elif isinstance(donnees_brutes, dict):
                # Recherche d'une clé standard contenant les données
                for cle_donnees in ("data", "results", "items", "records", "features"):
                    if cle_donnees in donnees_brutes:
                        enregistrements = donnees_brutes[cle_donnees]
                        break
                else:
                    # Pas de clé standard : utilise le dict entier
                    enregistrements = [donnees_brutes]
            else:
                raise KidasReadError(
                    f"Format de réponse non supporté : {type(donnees_brutes).__name__}"
                )

            # Conversion en DataFrame pandas
            df = pd.json_normalize(enregistrements)

            logger.info(
                "Données API '%s' reçues : %d lignes, %d colonnes.",
                self.api_url,
                len(df),
                len(df.columns),
            )

            # Mise à jour de l'horodatage de lecture
            self._update_last_read()
            return df

        except KidasReadError:
            raise
        except Exception as erreur:
            raise KidasReadError(
                f"Impossible de convertir la réponse de '{self.api_url}' "
                f"en DataFrame : {erreur}"
            ) from erreur

    def write(self, data: pd.DataFrame) -> bool:
        """Envoie des données vers l'API via une requête POST.

        Args:
            data (pd.DataFrame): Les données à envoyer à l'API en JSON.

        Returns:
            bool: True si l'envoi a réussi (code 200 ou 201).

        Raises:
            KidasWriteError: Si la requête POST échoue.
        """
        try:
            # Conversion du DataFrame en liste de dictionnaires JSON
            payload = data.to_dict(orient="records")

            # Respect du rate limit avant la requête
            self._respecter_rate_limit()
            self._last_request_time = time.monotonic()

            # Envoi de la requête POST
            reponse = requests.post(
                self.api_url,
                json=payload,
                headers=self._construire_entetes(),
                timeout=30,
            )
            reponse.raise_for_status()

            logger.info(
                "Données envoyées avec succès à '%s' (%d enregistrements, "
                "status: %d).",
                self.api_url,
                len(data),
                reponse.status_code,
            )
            return True

        except requests.exceptions.HTTPError as erreur:
            raise KidasWriteError(
                f"Erreur HTTP lors du POST vers '{self.api_url}' : {erreur}"
            ) from erreur
        except Exception as erreur:
            raise KidasWriteError(
                f"Impossible d'envoyer les données vers '{self.api_url}' : {erreur}"
            ) from erreur

    def get_schema(self) -> dict:
        """Retourne la spécification connue de l'API.

        Retourne les métadonnées de configuration de la source API :
        URL, authentification, rate limit, et un aperçu de la réponse
        si disponible.

        Returns:
            dict: Schéma de la source API avec les paramètres de configuration.
        """
        return {
            "api_url": self.api_url,
            "requires_auth": self.auth_token is not None,
            "rate_limit_per_sec": self.rate_limit_per_sec,
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def get_metadata(self) -> dict:
        """Retourne les métadonnées de la connexion API.

        Returns:
            dict: Dictionnaire contenant les clés suivantes :
                - 'source_path' (str) : URL de l'API.
                - 'source_type' (str) : 'api'.
                - 'requires_auth' (bool) : True si un jeton est requis.
                - 'rate_limit_per_sec' (float) : limite de débit.
                - 'last_read' (str | None) : horodatage de la dernière lecture.
        """
        return {
            "source_path": self.api_url,
            "source_type": "api",
            "requires_auth": self.auth_token is not None,
            "rate_limit_per_sec": self.rate_limit_per_sec,
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def validate_connection(self) -> bool:
        """Vérifie que l'endpoint API est accessible via une requête HEAD.

        Returns:
            bool: True si l'endpoint répond (même avec une erreur 4xx),
                False si la connexion échoue complètement.
        """
        try:
            # Requête HEAD légère pour tester la connectivité
            reponse = requests.head(
                self.api_url,
                headers=self._construire_entetes(),
                timeout=10,
            )
            # Tout code de réponse indique que l'API est accessible
            est_accessible = reponse.status_code < 500
            logger.debug(
                "Validation connexion API '%s' : status %d → %s.",
                self.api_url,
                reponse.status_code,
                "OK" if est_accessible else "KO",
            )
            return est_accessible

        except requests.exceptions.RequestException as erreur:
            logger.warning(
                "API '%s' inaccessible : %s", self.api_url, erreur
            )
            return False
