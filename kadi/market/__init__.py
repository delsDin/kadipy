"""
Point d'entrée du module kadi.market.

Contient la classe principale Market qui agrège toutes les fonctionnalités
(pricing, forecasting, logistics, decision_support) et valide les paramètres
d'entrée avant d'initialiser les sous-modules.
"""

from .pricing import MarketPricing
from .forecasting import MarketForecasting
from .logistics import MarketLogistics
from .decision_support import DecisionSupport
from .data_ingestion import WFPDataBridgesClient

# Borne géographique approximative du Bénin (± marge de 2 degrés pour les zones frontalières)
_LAT_MIN = 6.0
_LAT_MAX = 12.5
_LON_MIN = 0.5
_LON_MAX = 3.9


def _valider_coordonnees(lat: float, lon: float, location: str):
    """
    Valide que les coordonnées GPS sont cohérentes avec le territoire béninois.

    Args:
        lat (float): Latitude à valider.
        lon (float): Longitude à valider.
        location (str): Nom du lieu (pour le message d'erreur).

    Raises:
        TypeError: Si lat ou lon ne sont pas des nombres.
        ValueError: Si les coordonnées sont hors de la zone du Bénin.
    """
    # Vérification des types
    if not isinstance(lat, (int, float)):
        raise TypeError(
            f"La latitude doit être un nombre. Reçu : {type(lat).__name__} ('{lat}')."
        )
    if not isinstance(lon, (int, float)):
        raise TypeError(
            f"La longitude doit être un nombre. Reçu : {type(lon).__name__} ('{lon}')."
        )

    # Vérification de la plage valide pour le Bénin
    if not (_LAT_MIN <= lat <= _LAT_MAX):
        raise ValueError(
            f"Latitude '{lat}' hors de la zone Bénin (attendu entre {_LAT_MIN} et {_LAT_MAX})."
        )
    if not (_LON_MIN <= lon <= _LON_MAX):
        raise ValueError(
            f"Longitude '{lon}' hors de la zone Bénin (attendu entre {_LON_MIN} et {_LON_MAX})."
        )


def _valider_location(location: str):
    """
    Valide que le nom du lieu est une chaîne non vide.

    Args:
        location (str): Le nom du lieu à valider.

    Raises:
        TypeError: Si location n'est pas une chaîne de caractères.
        ValueError: Si location est vide ou ne contient que des espaces.
    """
    if not isinstance(location, str):
        raise TypeError(
            f"Le nom du lieu doit être une chaîne. Reçu : {type(location).__name__}."
        )
    if not location.strip():
        raise ValueError("Le nom du lieu ne peut pas être vide.")


class Market:
    """
    Façade principale pour le module d'économie agricole de KadiPy.

    Combine la tarification, la prévision, la logistique et l'aide à la
    décision stratégique dans une interface unique. Toutes les entrées sont
    validées à l'initialisation pour éviter des erreurs silencieuses
    dans les sous-modules.

    Note sur la zone géographique :
        Ce module est conçu pour le Bénin uniquement (V1.0.0).
        Le support d'autres pays sera ajouté dans une version future.
    """

    def __init__(self, lat: float, lon: float, location: str, env_file: str = ".env"):
        """
        Initialise le point central du marché avec les coordonnées d'une
        coopérative ou d'un nœud de marché au Bénin.

        Args:
            lat (float): La latitude du lieu (doit être dans la zone Bénin :
                entre 6.0 et 12.5 degrés nord).
            lon (float): La longitude du lieu (doit être dans la zone Bénin :
                entre 0.5 et 3.9 degrés est).
            location (str): Le nom du lieu (ex: 'Abomey', 'Parakou').
                Ne peut pas être vide.
            env_file (str, optional): Chemin vers le fichier .env contenant
                les variables d'environnement (ex: clé API WFP).
                Défaut à '.env'.

        Raises:
            TypeError: Si lat, lon ou location ne sont pas du bon type.
            ValueError: Si les coordonnées sont hors de la zone Bénin ou
                si le nom du lieu est vide.

        Exemples:
            >>> marche = Market(9.30, 2.08, "Parakou")
            >>> marche = Market(lat=6.36, lon=2.41, location="Cotonou")
        """
        # Validation des paramètres avant toute initialisation
        _valider_coordonnees(lat, lon, location)
        _valider_location(location)

        # Sauvegarde des coordonnées géographiques du lieu
        self.lat = lat
        self.lon = lon
        self.location = location.strip()

        # Initialisation du client d'ingestion de données WFP
        self.data_client = WFPDataBridgesClient(env_file=env_file)

        # Initialisation du module de tarification (normalisation + détection anomalies)
        self.pricing = MarketPricing(wfp_client=self.data_client)

        # Initialisation du module de prévision (séries temporelles)
        self.forecasting = MarketForecasting()

        # Initialisation du module logistique (distances, coûts de transport)
        self.logistics = MarketLogistics()

        # Initialisation de l'aide à la décision (couplée avec forecasting + logistics)
        self.decision_support = DecisionSupport(
            forecasting_module=self.forecasting,
            logistics_module=self.logistics,
        )
