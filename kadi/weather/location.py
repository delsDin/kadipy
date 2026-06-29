"""
Module location.py

Ce module contient la classe Location qui permet de représenter
une position géographique (latitude, longitude) au Bénin et
de déduire automatiquement sa zone agro-climatique.
"""

from kadi.exceptions import LocationNotFound
from kadi.config import CONFIG

class Location:
    """
    Représente une localisation géographique avec détection automatique
    de la zone climatique béninoise.
    """

    def __init__(self, latitude: float, longitude: float, name: str = None):
        """
        Initialise une nouvelle localisation.

        :param latitude: Latitude en degrés décimaux.
        :param longitude: Longitude en degrés décimaux.
        :param name: Nom de la localité (optionnel).
        """
        self.latitude = latitude
        self.longitude = longitude
        
        bbox = CONFIG["data"]["gps_validation_bbox"]
        if not (bbox["min_lat"] <= latitude <= bbox["max_lat"] and bbox["min_lon"] <= longitude <= bbox["max_lon"]):
            raise LocationNotFound(f"Les coordonnées GPS ({latitude}, {longitude}) sont en dehors de la zone d'étude.")
            
        self.name = name if name else f"Point({latitude}, {longitude})"
        
        # Détection automatique de la zone et du régime
        self.zone = self.detect_zone()
        self.climate_regime = self._detect_regime()

    def detect_zone(self) -> str:
        """
        Détecte la zone climatique (Nord, Centre, Sud) à partir de la latitude.
        Selon les spécifications, le découpage au Bénin est :
        - Sud : < 7°30' N (7.5)
        - Centre : entre 7°30' N et 9° N
        - Nord : > 9° N

        :return: 'Sud', 'Centre' ou 'Nord'
        """
        if self.latitude < 7.5:
            return 'Sud'
        elif 7.5 <= self.latitude < 9.0:
            return 'Centre'
        else:
            return 'Nord'

    def _detect_regime(self) -> str:
        """
        Déduit le régime climatique (bimodal ou unimodal) selon la zone.

        :return: 'bimodal' ou 'unimodal'
        """
        if self.zone == 'Sud':
            return 'bimodal'
        else:
            return 'unimodal'

    def get_climate_params(self) -> dict:
        """
        Retourne les paramètres climatiques par défaut pour la zone.

        :return: Dictionnaire des paramètres.
        """
        params = {
            'Sud': {'Tbase': 10, 'onset_method': 'walter_anyadike'},
            'Centre': {'Tbase': 10, 'onset_method': 'hybrid'},
            'Nord': {'Tbase': 10, 'onset_method': 'sivakumar'}
        }
        return params.get(self.zone, {})

    def to_dict(self) -> dict:
        """
        Sérialise la localisation pour le cache.

        :return: Dictionnaire représentant l'objet Location.
        """
        return {
            'name': self.name,
            'lat': self.latitude,
            'lon': self.longitude,
            'zone': self.zone,
            'regime': self.climate_regime
        }
