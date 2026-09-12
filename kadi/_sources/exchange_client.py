"""
Client de taux de change en temps réel pour KadiPy.

Ce module interroge l'API publique Frankfurter (api.frankfurter.dev)
pour obtenir les taux XOF/USD et XOF/EUR à la date du jour.

Un cache mémoire avec durée de vie configurable (TTL) évite les appels
réseau redondants. En cas d'indisponibilité du réseau, le client retourne
les taux de repli définis dans kadi.config.EXCHANGE_RATES.
"""

import logging
import time
from typing import Optional

import requests

# Import des URLs et taux de repli depuis la configuration centrale
from kadi.config import EXCHANGE_RATES, FRANKFURTER_API_URL

# Durée de vie du cache en mémoire : 24 heures par défaut
_TTL_SECONDES_DEFAULT = 24 * 3600

# Délai d'attente maximum pour une requête HTTP (en secondes)
_TIMEOUT_SECONDES = 10

logger = logging.getLogger(__name__)


class ExchangeRateClient:
    """
    Client de récupération des taux de change XOF/USD et XOF/EUR.

    Interroge l'API Frankfurter pour obtenir les taux du jour.
    Les résultats sont mis en cache en mémoire pour éviter des appels
    répétés pendant la durée de vie configurée (TTL).

    En mode hors ligne (réseau indisponible ou timeout), le client
    retourne automatiquement les taux de repli issus de config.EXCHANGE_RATES.

    Args:
        ttl_secondes (int): Durée de vie du cache en secondes.
            Défaut : 86400 (24 heures).
        api_url (str): URL de base de l'API Frankfurter.
            Défaut : valeur de config.FRANKFURTER_API_URL.

    Exemples:
        >>> client = ExchangeRateClient()
        >>> taux = client.get_rates()
        >>> print(taux["USD_TO_XOF"])  # ex: 571.4
    """

    def __init__(
        self,
        ttl_secondes: int = _TTL_SECONDES_DEFAULT,
        api_url: str = FRANKFURTER_API_URL,
    ) -> None:
        """
        Initialise le client avec les paramètres de cache et d'URL.

        Args:
            ttl_secondes (int): Durée de vie du cache en mémoire (en secondes).
            api_url (str): URL de base de l'API Frankfurter.
        """
        # URL de base de l'API Frankfurter
        self._api_url = api_url.rstrip("/")

        # Durée de vie du cache en secondes
        self._ttl_secondes = ttl_secondes

        # Horodatage du dernier appel réussi (None = jamais appelé)
        self._cache_timestamp: Optional[float] = None

        # Taux mis en cache lors du dernier appel réussi
        self._cache: Optional[dict] = None

    def get_rates(self) -> dict:
        """
        Retourne les taux de change XOF vers USD et EUR.

        Le résultat est un dictionnaire de la forme :
        ``{"USD_TO_XOF": float, "EUR_TO_XOF": float}``

        Les valeurs représentent le nombre d'unités XOF pour une unité
        de la devise cible (ex: USD_TO_XOF = 571 signifie 1 USD = 571 XOF).

        Si le cache est encore valide (âge < TTL), les taux en cache sont
        retournés sans appel réseau. Sinon, l'API Frankfurter est interrogée.

        En cas d'erreur réseau, les taux de repli de config.EXCHANGE_RATES
        sont retournés et un avertissement est journalisé.

        Returns:
            dict: Dictionnaire ``{"USD_TO_XOF": float, "EUR_TO_XOF": float}``.
        """
        # Vérification de la validité du cache
        if self._cache_valid():
            logger.debug("Taux de change servis depuis le cache mémoire.")
            return dict(self._cache)

        # Tentative de récupération depuis l'API
        taux = self._fetch_from_api()

        if taux is not None:
            # Mise à jour du cache avec les taux récupérés
            self._cache = taux
            self._cache_timestamp = time.monotonic()
            logger.info(
                "Taux de change mis à jour depuis Frankfurter : "
                f"USD_TO_XOF={taux['USD_TO_XOF']:.4f}, "
                f"EUR_TO_XOF={taux['EUR_TO_XOF']:.4f}"
            )
            return dict(taux)

        # Fallback : retour des taux de repli statiques
        logger.warning(
            "Impossible de récupérer les taux depuis l'API Frankfurter. "
            "Taux de repli statiques utilisés (config.EXCHANGE_RATES)."
        )
        return dict(EXCHANGE_RATES)

    def _cache_valid(self) -> bool:
        """
        Vérifie si le cache mémoire est encore dans sa période de validité.

        Returns:
            bool: True si le cache existe et n'a pas dépassé le TTL, False sinon.
        """
        # Le cache est invalide s'il n'a jamais été alimenté
        if self._cache is None or self._cache_timestamp is None:
            return False

        # Calcul de l'âge du cache en secondes
        age_secondes = time.monotonic() - self._cache_timestamp
        return age_secondes < self._ttl_secondes

    def _fetch_from_api(self) -> Optional[dict]:
        """
        Appelle l'API Frankfurter pour obtenir les taux XOF/USD et XOF/EUR.

        L'API retourne le taux d'une unité de XOF vers la devise cible.
        On inverse le résultat pour obtenir le nombre de XOF par unité de devise.

        Returns:
            dict: Dictionnaire ``{"USD_TO_XOF": float, "EUR_TO_XOF": float}``
                si la requête aboutit, None en cas d'erreur.
        """
        taux_recuperes = {}

        # Liste des devises à récupérer avec leur clé interne correspondante
        devises_cibles = [
            ("USD", "USD_TO_XOF"),
            ("EUR", "EUR_TO_XOF"),
        ]

        for devise, cle_interne in devises_cibles:
            # Construction de l'URL pour la paire XOF -> devise
            url = f"{self._api_url}/rate/XOF/{devise}"

            try:
                # Appel HTTP avec timeout strict
                reponse = requests.get(url, timeout=_TIMEOUT_SECONDES)
                reponse.raise_for_status()

                # Extraction du taux depuis la réponse JSON
                donnees = reponse.json()
                taux_xof_vers_devise = float(donnees["rate"])

                if taux_xof_vers_devise <= 0:
                    logger.warning(
                        f"Taux invalide reçu pour {devise} : {taux_xof_vers_devise}. "
                        "Ce taux est ignoré."
                    )
                    return None

                # Inversion du taux : XOF/devise -> devise/XOF -> XOF par 1 devise
                taux_recuperes[cle_interne] = round(1.0 / taux_xof_vers_devise, 4)

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Timeout lors de la récupération du taux {devise}. "
                    f"URL : {url}"
                )
                return None

            except requests.exceptions.ConnectionError:
                logger.warning(
                    f"Erreur de connexion lors de la récupération du taux {devise}. "
                    "Vérifiez la connectivité réseau."
                )
                return None

            except (requests.exceptions.RequestException, KeyError, ValueError) as err:
                logger.warning(
                    f"Erreur inattendue lors de la récupération du taux {devise} : {err}"
                )
                return None

        return taux_recuperes if len(taux_recuperes) == len(devises_cibles) else None
