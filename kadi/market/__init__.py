"""
Point d'entrée du module kadi.market.
Contient la classe principale Market qui agrège toutes les fonctionnalités
(pricing, forecasting, logistics, decision_support).
"""

from .pricing import MarketPricing
from .forecasting import MarketForecasting
from .logistics import MarketLogistics
from .decision_support import DecisionSupport


from .data_ingestion import WFPDataBridgesClient


class Market:
    """
    Façade principale pour le module d'économie agricole, combinant la tarification,
    la prévision, la logistique et l'aide à la décision stratégique.
    """

    def __init__(self, lat: float, lon: float, location: str, env_file: str = '.env'):
        """
        Initialise le point central du marché avec les coordonnées d'une
        coopérative ou d'un nœud de marché.

        Args:
            lat (float): La latitude.
            lon (float): La longitude.
            location (str): Le nom du lieu (ex: 'Abomey').
            env_file (str, optional): Fichier contenant les variables d'env (ex: clé API).
        """
        # Sauvegarde des coordonnées géographiques du lieu
        self.lat = lat
        self.lon = lon
        self.location = location
        
        # Initialisation du client d'ingestion de données
        self.data_client = WFPDataBridgesClient(env_file=env_file)
        
        # Initialisation du module de tarification avec le client d'ingestion
        self.pricing = MarketPricing(wfp_client=self.data_client)
        
        # Initialisation du module de prévision (séries temporelles)
        self.forecasting = MarketForecasting()
        
        # Initialisation du module logistique (frictions, distances)
        self.logistics = MarketLogistics()
        
        # Initialisation de l'aide à la décision couplée avec forecasting et logistics
        self.decision_support = DecisionSupport(
            forecasting_module=self.forecasting,
            logistics_module=self.logistics
        )
