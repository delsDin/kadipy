"""
Module session.py

Façade principale du module kadi.weather.
Orchestre les classes Location, WeatherData, Phenology, Hydrology et RiskIndicators
pour exposer une API simple et unifiée des 9 fonctions principales.
"""

from typing import Optional
import pandas as pd

from kadi.config import CONFIG
from .location import Location
from .data import WeatherData
from .phenology import Phenology
from .hydrology import Hydrology
from .risk import RiskIndicators

class WeatherSession:
    """
    Session météorologique : point d'entrée principal pour l'utilisateur.
    Gère le setup, le cache et expose l'API fonctionnelle complète.
    """

    def __init__(self, latitude: float, longitude: float, name: str = None, cache_dir: str = None):
        """
        Initialise une nouvelle session pour une localisation.

        :param latitude: Latitude (en degrés décimaux).
        :param longitude: Longitude (en degrés décimaux).
        :param name: Nom de la localité (optionnel).
        :param cache_dir: Dossier pour le cache (optionnel).
        """
        self.location = Location(latitude, longitude, name)
        self.cache_dir = cache_dir
        
        # Initialisation de la gestion des données
        self.weather_data = WeatherData(self.location, cache_dir)
        
        # Composants métiers (initialisés paresseusement ou lors de _init_all_components)
        self.phenology: Optional[Phenology] = None
        self.hydrology: Optional[Hydrology] = None
        self.risk_indicators: Optional[RiskIndicators] = None

    def _ensure_data(self, require_forecast=False, require_historical=False):
        """
        S'assure que les données nécessaires sont chargées.
        """
        if require_forecast and self.weather_data.forecast_data is None:
            self.weather_data.fetch_forecast()
            
        if require_historical and self.weather_data.historical_data is None:
            self.weather_data.fetch_historical()

    def _ensure_components(self, component: str):
        """
        S'assure que le composant demandé est initialisé.
        """
        if component == 'phenology' and self.phenology is None:
            self._ensure_data(require_historical=True)
            hist = self.weather_data.historical_data
            self.phenology = Phenology(self.location, hist['precipitation'], hist[['temperature_min', 'temperature_max']])
            
        elif component == 'hydrology' and self.hydrology is None:
            self._ensure_data(require_historical=True)
            hist = self.weather_data.historical_data
            self.hydrology = Hydrology(self.location, hist['precipitation'], hist[['temperature_min', 'temperature_max']])
            
        elif component == 'risk' and self.risk_indicators is None:
            self._ensure_data(require_forecast=True, require_historical=True)
            self.risk_indicators = RiskIndicators(self.location, self.weather_data.historical_data['precipitation'], self.weather_data.forecast_data)

    def forecast(self, days: int = None) -> dict:
        """
        Récupère la prévision météorologique court-terme.

        :param days: Nombre de jours de prévision (défaut depuis CONFIG).
        :return: Dictionnaire des prévisions.
        """
        if days is None:
            days = CONFIG["weather"]["forecast_days_default"]
            
        if days > CONFIG["weather"]["max_forecast_days"]:
            days = CONFIG["weather"]["max_forecast_days"]
            
        df = self.weather_data.fetch_forecast(days=days)
        
        # Format de retour selon cahier des charges
        return {
            'location': {'name': self.location.name, 'lat': self.location.latitude, 'lon': self.location.longitude},
            'data': df.reset_index().to_dict(orient='records'),
            'data_source': self.weather_data.data_source,
            'last_updated': pd.Timestamp.now().isoformat()
        }

    def historical(self, metric: str = 'all', months_back: int = 120) -> pd.DataFrame:
        """
        Retourne les séries historiques.

        :param metric: Filtre de colonne ('temperature', 'precipitation', 'humidity', 'all').
        :param months_back: Nombre de mois d'historique.
        :return: DataFrame historique.
        """
        df = self.weather_data.fetch_historical(months_back=months_back)
        
        if metric != 'all':
            cols = [c for c in df.columns if metric in c]
            if cols:
                return df[cols]
                
        return df

    def growing_degree_days(self, crop: str, start_date: str, end_date: str = None) -> dict:
        """
        Calcule l'accumulation des degrés-jours.

        :param crop: Nom de la culture.
        :param start_date: Date de semis (YYYY-MM-DD).
        :param end_date: Date de fin (optionnel).
        :return: Résultat du cumul GDD.
        """
        self._ensure_components('phenology')
        return self.phenology.growing_degree_days(crop, start_date, end_date)

    def onset(self) -> dict:
        """
        Détecte la date de démarrage de la saison agricole.

        :return: Résultat de l'onset.
        """
        self._ensure_components('phenology')
        return self.phenology.onset()

    def cessation(self) -> dict:
        """
        Détermine la date de fin des pluies utiles.

        :return: Résultat de cessation.
        """
        self._ensure_components('phenology')
        return self.phenology.cessation()

    def drought_index(self, method: str = 'spi', window_months: int = 3) -> dict:
        """
        Calcule l'indice de sécheresse.

        :param method: 'spi', 'markov', 'hurst', 'combined'.
        :param window_months: Fenêtre temporelle en mois.
        :return: Indicateurs de sécheresse.
        """
        self._ensure_components('risk')
        return self.risk_indicators.drought_index(method, window_months)

    def rain_probability(self, days_ahead: int = 1, min_rainfall_mm: float = 1.0) -> dict:
        """
        Prévoit la probabilité de pluie.

        :param days_ahead: Nombre de jours futurs.
        :param min_rainfall_mm: Seuil minimum.
        :return: Probabilité et recommandations.
        """
        self._ensure_components('risk')
        return self.risk_indicators.rain_probability(days_ahead, min_rainfall_mm)

    def water_balance(self, crop: str = 'maize', soil_type: str = 'ferrugineux') -> pd.DataFrame:
        """
        Simule le bilan hydrique quotidien (FAO-56).

        :param crop: Type de culture.
        :param soil_type: Type de sol.
        :return: DataFrame avec le bilan hydrique.
        """
        self._ensure_components('hydrology')
        self.hydrology.crop = crop
        self.hydrology.soil_type = soil_type
        self.hydrology.soil_params = self.hydrology.get_soil_params(soil_type)
        return self.hydrology.compute_water_balance()

    def et0_hargreaves(self, tmin: float, tmax: float, day_of_year: int) -> float:
        """
        Calcule l'ETo par Hargreaves-Samani.

        :param tmin: Temp. min.
        :param tmax: Temp. max.
        :param day_of_year: Jour de l'année.
        :return: ETo en mm/jour.
        """
        self._ensure_components('hydrology')
        return self.hydrology.et0_hargreaves(tmin, tmax, day_of_year)

    def _init_all_components(self) -> None:
        """
        Initialise toutes les classes composantes.
        """
        self._ensure_components('phenology')
        self._ensure_components('hydrology')
        self._ensure_components('risk')
