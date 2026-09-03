"""
Client pour l'API HAPI HumData du Programme Alimentaire Mondial (PAM).

Ce module interroge l'endpoint public food-prices-market-monitor de l'API
HAPI HumData pour récupérer les prix de marché agricoles.

L'identifiant applicatif (HAPI_APP_IDENTIFIER) doit être fourni via la
variable d'environnement du même nom. En son absence, ou en cas d'erreur
réseau, le client retourne un DataFrame de données simulées avec le flag
is_simulated=True.

L'endpoint HAPI retourne des données au format CSV, paginées par tranches
de 10 000 lignes maximum. Ce client gère la pagination automatiquement.
"""

import datetime
import logging
import time
import warnings
from io import StringIO
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests

# Import des constantes de configuration
from kadi.config import HAPI_API_URL, HAPI_APP_IDENTIFIER

# Endpoint HAPI ciblé pour les prix de marché alimentaire
_HAPI_ENDPOINT = "food-security-nutrition-poverty/food-prices-market-monitor"

# Nombre maximum de résultats par page HAPI
_HAPI_PAGE_SIZE = 10_000

# Délai d'attente maximum pour une requête HTTP (en secondes)
_TIMEOUT_SECONDES = 30

# Nombre de tentatives avant de tomber en mode fallback
_MAX_TENTATIVES = 3

# Délai de base pour le backoff exponentiel (en secondes)
_BACKOFF_BASE_SEC = 2

# Code ISO-3 du Bénin, localisation par défaut
_LOCATION_CODE_DEFAUT = "BEN"

logger = logging.getLogger(__name__)


class WFPClient:
    """
    Client de récupération des prix de marché via l'API HAPI HumData (PAM).

    Interroge l'endpoint food-prices-market-monitor pour obtenir les prix
    agricoles filtrés par pays, marché et marchandise.

    L'accès à l'API nécessite un identifiant applicatif encodé en base64,
    fourni par la variable d'environnement HAPI_APP_IDENTIFIER. Si cet
    identifiant est absent, le client retourne des données simulées.

    En cas d'erreur réseau ou de timeout, le client effectue jusqu'à
    _MAX_TENTATIVES requêtes avec un backoff exponentiel, puis retombe
    en mode simulation.

    Args:
        api_url (str): URL de base de l'API HAPI. Défaut : config.HAPI_API_URL.
        app_identifier (str, optional): Identifiant applicatif HAPI.
            Défaut : config.HAPI_APP_IDENTIFIER.

    Exemples:
        >>> client = WFPClient()
        >>> df = client.prices("cotonou", "maize", ("2024-01-01", "2024-12-31"))
        >>> print(df.columns.tolist())
        ['date', 'price', 'unit', 'is_simulated', 'source', 'fetched_at', 'confidence_score']
    """

    # Table des anciens noms de méthodes -> nouveau nom
    # Utilisée par __getattr__ pour intercepter les appels aux méthodes dépréciées.
    _METHODES_DEPRECATED = {
        "get_market_prices": "prices",
    }

    def __init__(
        self,
        api_url: str = HAPI_API_URL,
        app_identifier: Optional[str] = HAPI_APP_IDENTIFIER,
    ) -> None:
        """
        Initialise le client avec l'URL de l'API et l'identifiant applicatif.

        Args:
            api_url (str): URL de base de l'API HAPI HumData.
            app_identifier (str, optional): Identifiant base64 requis par HAPI.
                Si None, le client fonctionnera en mode simulation.
        """
        # URL de base de l'API (sans slash final)
        self._api_url = api_url.rstrip("/")

        # Identifiant applicatif HAPI (peut être None si non configuré)
        self._app_identifier = app_identifier

        if not self._app_identifier:
            logger.warning(
                "HAPI_APP_IDENTIFIER non défini. Le client WFP fonctionnera "
                "en mode simulation. Définissez la variable d'environnement "
                "HAPI_APP_IDENTIFIER pour accéder aux données réelles."
            )

    def __getattr__(self, name: str):
        """
        Intercepte les appels aux anciennes méthodes pour émettre un avertissement.

        Args:
            name (str): Nom de la méthode demandée.

        Returns:
            callable: La méthode correspondant à l'ancien nom.

        Raises:
            AttributeError: Si le nom n'est ni courant ni un ancien nom connu.
        """
        if name in WFPClient._METHODES_DEPRECATED:
            # Récupération du nouveau nom de méthode
            nouveau_nom = WFPClient._METHODES_DEPRECATED[name]
            warnings.warn(
                f"WFPClient.{name} est obsolète et sera supprimé "
                f"dans KadiPy v2.0. Utilisez WFPClient.{nouveau_nom} à la place.",
                category=DeprecationWarning,
                # stacklevel=2 pointe vers la ligne de code de l'utilisateur,
                # pas vers cette fonction interne
                stacklevel=2,
            )
            return getattr(self, nouveau_nom)
        raise AttributeError(
            f"'{type(self).__name__}' n'a pas d'attribut '{name}'."
        )

    def prices(
        self,
        market: str,
        commodity: str,
        range_: Tuple[str, str],
        location: str = _LOCATION_CODE_DEFAUT,
        location_code: str = None,
    ) -> pd.DataFrame:
        """
        Récupère les prix de marché pour une marchandise et un marché donnés.

        Appelle l'API HAPI HumData et retourne un DataFrame normalisé
        avec les colonnes internes de KadiPy. La pagination est gérée
        automatiquement.

        En cas d'identifiant manquant ou d'erreur réseau, un DataFrame de
        données simulées est retourné avec is_simulated=True.

        Args:
            market (str): Nom du marché (ex: 'cotonou', 'Dantokpa').
            commodity (str): Nom de la marchandise en anglais (ex: 'maize', 'rice').
            range_ (Tuple[str, str]): Tuple (start_date, end_date) au format
                'YYYY-MM-DD'.
            location (str): Code ISO-3 du pays. Défaut : 'BEN' (Bénin).
            location_code (str, optional): Alias de ``location`` conservé pour
                la rétrocompatibilité. Prioritaire sur ``location`` si fourni.

        Returns:
            pd.DataFrame: DataFrame avec les colonnes :
                - ``date`` (datetime) : date de l'observation.
                - ``price`` (float) : prix en unité locale.
                - ``unit`` (str) : unité du prix (ex: 'XOF/KG').
                - ``is_simulated`` (bool) : True si données simulées.
                - ``source`` (str) : organisation source (ex: 'WFP').
                - ``fetched_at`` (str) : horodatage ISO de la récupération.
                - ``confidence_score`` (float) : score de confiance (0.0-1.0).
        """
        # Rétrocompatibilité : location_code (ancienne API) prioritaire sur location
        if location_code is not None:
            location = location_code

        # Si l'identifiant est absent, on tombe directement en simulation
        if not self._app_identifier:
            logger.warning(
                f"Données simulées pour {commodity}/{market} "
                "(HAPI_APP_IDENTIFIER non configuré)."
            )
            return self._simulate(commodity, range_)

        # Tentative de récupération depuis l'API avec retry
        df = self._fetch_with_retry(market, commodity, range_, location)

        if df is not None:
            return df

        # Fallback : données simulées si toutes les tentatives ont échoué
        logger.warning(
            f"Toutes les tentatives HAPI ont échoué pour {commodity}/{market}. "
            "Données simulées retournées."
        )
        return self._simulate(commodity, range_)

    def _fetch_with_retry(
        self,
        market: str,
        commodity: str,
        range_: Tuple[str, str],
        location: str,
    ) -> Optional[pd.DataFrame]:
        """
        Effectue les appels à l'API avec retry et backoff exponentiel.

        En cas d'erreur réseau, chaque tentative attend un délai croissant
        (2s, 4s, 8s) avant de réessayer.

        Args:
            market (str): Nom du marché ciblé.
            commodity (str): Nom de la marchandise.
            range_ (Tuple[str, str]): Plage de dates (start, end).
            location (str): Code pays ISO-3.

        Returns:
            pd.DataFrame si l'appel réussit, None si toutes les tentatives échouent.
        """
        for tentative in range(1, _MAX_TENTATIVES + 1):
            try:
                df = self._paginate(market, commodity, range_, location)
                return df

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Tentative {tentative}/{_MAX_TENTATIVES} : timeout HAPI "
                    f"pour {commodity}/{market}."
                )

            except requests.exceptions.ConnectionError:
                logger.warning(
                    f"Tentative {tentative}/{_MAX_TENTATIVES} : erreur de connexion "
                    f"HAPI pour {commodity}/{market}."
                )

            except (requests.exceptions.RequestException, Exception) as err:
                logger.warning(
                    f"Tentative {tentative}/{_MAX_TENTATIVES} : erreur inattendue "
                    f"pour {commodity}/{market} : {err}"
                )

            # Attente avec backoff exponentiel avant la prochaine tentative
            if tentative < _MAX_TENTATIVES:
                delai = _BACKOFF_BASE_SEC ** tentative
                logger.debug(f"Attente de {delai}s avant la prochaine tentative.")
                time.sleep(delai)

        return None

    def _paginate(
        self,
        market: str,
        commodity: str,
        range_: Tuple[str, str],
        location: str,
    ) -> pd.DataFrame:
        """
        Interroge l'API HAPI en paginant automatiquement les résultats.

        L'API limite chaque réponse à 10 000 lignes. Cette méthode continue
        d'appeler l'API avec un offset croissant jusqu'à récupérer toutes
        les lignes disponibles.

        Args:
            market (str): Nom du marché.
            commodity (str): Nom de la marchandise.
            range_ (Tuple[str, str]): Tuple (start_date, end_date).
            location (str): Code pays ISO-3.

        Returns:
            pd.DataFrame: Toutes les lignes récupérées, normalisées.

        Raises:
            requests.exceptions.RequestException: En cas d'erreur HTTP.
        """
        # Construction de l'URL complète de l'endpoint
        url = f"{self._api_url}/{_HAPI_ENDPOINT}"

        # Horodatage de la récupération
        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Paramètres de base communs à toutes les pages
        params_base = {
            "app_identifier": self._app_identifier,
            "market_name": market,
            "commodity_name": commodity,
            "location_code": location,
            "start_date": range_[0],
            "end_date": range_[1],
            "output_format": "csv",
            "limit": _HAPI_PAGE_SIZE,
        }

        # Liste des DataFrames de chaque page pour la concaténation finale
        pages = []
        offset = 0

        while True:
            # Ajout de l'offset de pagination aux paramètres
            params = {**params_base, "offset": offset}

            reponse = requests.get(url, params=params, timeout=_TIMEOUT_SECONDES)
            reponse.raise_for_status()

            # Conversion du CSV en DataFrame
            df_page = pd.read_csv(StringIO(reponse.text))

            if df_page.empty:
                # Plus de données : fin de la pagination
                break

            pages.append(df_page)
            logger.debug(
                f"Page récupérée : {len(df_page)} lignes (offset={offset})."
            )

            # Si la page est incomplète, c'est la dernière
            if len(df_page) < _HAPI_PAGE_SIZE:
                break

            # Passage à la page suivante
            offset += _HAPI_PAGE_SIZE

        if not pages:
            logger.info(
                f"Aucune donnée retournée par HAPI pour {commodity}/{market} "
                f"sur la période {range_[0]} -> {range_[1]}."
            )
            return self._simulate(commodity, range_)

        # Concaténation de toutes les pages
        df_brut = pd.concat(pages, ignore_index=True)

        # Normalisation des colonnes vers le format interne KadiPy
        return self._normalize(df_brut, fetched_at)

    def _normalize(
        self,
        df: pd.DataFrame,
        fetched_at: str,
    ) -> pd.DataFrame:
        """
        Traduit les colonnes de la réponse HAPI vers le format interne KadiPy.

        Mapping appliqué :
        - reference_period_start -> date
        - price                  -> price
        - price_unit             -> unit
        - source_org_acronym     -> source

        Ajoute les colonnes calculées : is_simulated, fetched_at, confidence_score.

        Args:
            df (pd.DataFrame): DataFrame brut issu de l'API HAPI.
            fetched_at (str): Horodatage ISO de la récupération.

        Returns:
            pd.DataFrame: DataFrame normalisé avec les colonnes internes.
        """
        # Dictionnaire de renommage des colonnes HAPI vers le format interne
        mapping_colonnes = {
            "reference_period_start": "date",
            "price": "price",
            "price_unit": "unit",
            "source_org_acronym": "source",
        }

        # Sélection et renommage des colonnes disponibles dans la réponse
        colonnes_disponibles = {
            col_hapi: col_interne
            for col_hapi, col_interne in mapping_colonnes.items()
            if col_hapi in df.columns
        }
        df = df.rename(columns=colonnes_disponibles)

        # Conversion de la colonne date en datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Conversion de la colonne price en float
        if "price" in df.columns:
            df["price"] = pd.to_numeric(df["price"], errors="coerce")

        # Ajout des colonnes complémentaires
        df["is_simulated"] = False
        df["fetched_at"] = fetched_at

        # Score de confiance : 1.0 pour les données réelles WFP
        df["confidence_score"] = 1.0

        # Sélection des colonnes finales dans l'ordre standard
        colonnes_finales = [
            "date", "price", "unit", "is_simulated", "source",
            "fetched_at", "confidence_score",
        ]
        # Inclusion uniquement des colonnes présentes dans le DataFrame
        colonnes_presentes = [c for c in colonnes_finales if c in df.columns]
        return df[colonnes_presentes].dropna(subset=["date", "price"])

    def _simulate(
        self,
        commodity: str,
        range_: Tuple[str, str],
    ) -> pd.DataFrame:
        """
        Génère un DataFrame de données de prix simulées en mode fallback.

        Les prix sont générés par une distribution normale centrée sur 300 XOF/kg
        avec un écart-type de 20, ce qui est représentatif des marchés béninois
        pour les céréales sèches. is_simulated=True est positionné sur toutes
        les lignes pour signaler l'origine simulée.

        Args:
            commodity (str): Code de la marchandise (utilisé pour les logs).
            range_ (Tuple[str, str]): Plage de dates (start, end).

        Returns:
            pd.DataFrame: DataFrame simulé avec is_simulated=True.
        """
        # Construction de la plage de dates quotidienne
        try:
            start = datetime.date.fromisoformat(range_[0])
            end = datetime.date.fromisoformat(range_[1])
        except ValueError:
            # En cas de format de date invalide, simulation sur 365 jours
            end = datetime.date.today()
            start = end - datetime.timedelta(days=365)

        dates = pd.date_range(start=start, end=end, freq="D")
        nb_jours = len(dates)

        # Génération des prix simulés (distribution normale)
        prix_simules = np.random.normal(loc=300.0, scale=20.0, size=nb_jours)
        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        logger.info(
            f"Données simulées générées pour '{commodity}' "
            f"({nb_jours} observations)."
        )

        return pd.DataFrame({
            "date": dates,
            "price": prix_simules,
            "unit": "XOF/KG",
            "is_simulated": True,
            "source": "simulated",
            "fetched_at": fetched_at,
            "confidence_score": 0.1,
        })


# Table des anciens noms -> (nouveau nom, classe cible)
# Utilisée par __getattr__ pour intercepter les imports de l'ancien nom.
_DEPRECATED = {
    "WFPDataBridgesClient": ("WFPClient", WFPClient),
}


def __getattr__(name: str):
    """
    Intercepte l'accès aux anciens noms de classes pour émettre un avertissement.

    Args:
        name (str): Nom de l'attribut demandé dans ce module.

    Returns:
        type: La classe correspondant à l'ancien nom.

    Raises:
        AttributeError: Si le nom demandé n'est ni un symbole courant
            ni un ancien nom connu.
    """
    if name in _DEPRECATED:
        # Récupère le nouveau nom et la classe cible
        new_name, cls = _DEPRECATED[name]
        warnings.warn(
            f"kadi._sources.wfp_client.{name} est obsolète et sera supprimé "
            f"dans KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            # stacklevel=2 pointe vers la ligne de code de l'utilisateur,
            # pas vers cette fonction interne
            stacklevel=2,
        )
        return cls
    raise AttributeError(
        f"Le module '{__name__}' n'a pas d'attribut '{name}'."
    )
