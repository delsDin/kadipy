"""
Module session.py

Façade principale du module kadi.weather.
Orchestre les classes Location, WeatherLoader, Phenology, Hydrology et Risk
pour exposer une API simple, concise et unifiée des fonctions météorologiques.
"""

import warnings
from typing import Optional, Union

import pandas as pd

from kadi.config import CONFIG
from .location import Location
from .data import WeatherLoader
from .phenology import Phenology
from .hydrology import Hydrology
from .risk import Risk


class Weather:
    """
    Façade météorologique : point d'entrée principal pour l'utilisateur.

    Orchestre les composants Location, WeatherLoader, Phenology, Hydrology et
    Risk pour exposer une API simple et unifiée.

    Attributs:
        location (Location): Localisation associée à la façade météo.
        cache (str): Répertoire de cache (conservé pour la compatibilité).
        loader (WeatherLoader): Gestionnaire de données météorologiques.
        phenology (Phenology): Composant phénologique (chargé à la demande).
        hydrology (Hydrology): Composant hydrologique (chargé à la demande).
        risk (Risk): Composant des indicateurs de risque (chargé à la demande).
    """

    def __init__(
        self,
        lat: float = None,
        lon: float = None,
        name: str = None,
        cache: str = None,
        latitude: float = None,
        longitude: float = None,
        cache_dir: str = None,
    ):
        """
        Initialise une nouvelle façade météo pour une localisation.

        Args:
            lat (float): Latitude en degrés décimaux.
            lon (float): Longitude en degrés décimaux.
            name (str): Nom de la localité (optionnel).
            cache (str): Répertoire de cache (optionnel).
            latitude (float): Ancien nom du paramètre lat.
            longitude (float): Ancien nom du paramètre lon.
            cache_dir (str): Ancien nom du paramètre cache.
        """
        # Prise en charge des anciens noms de paramètres d'initialisation
        if latitude is not None:
            warnings.warn(
                "Le paramètre 'latitude' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'lat' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            lat = latitude

        if longitude is not None:
            warnings.warn(
                "Le paramètre 'longitude' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'lon' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            lon = longitude

        if cache_dir is not None:
            warnings.warn(
                "Le paramètre 'cache_dir' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'cache' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            cache = cache_dir

        if lat is None or lon is None:
            raise TypeError("Les coordonnées 'lat' et 'lon' sont obligatoires.")

        self.location = Location(lat, lon, name)
        # Conservé pour la compatibilité de signature
        self.cache = cache

        # Initialisation du gestionnaire de données
        self.loader = WeatherLoader(self.location, cache)

        # Composants métiers (initialisés à la demande)
        self.phenology: Optional[Phenology] = None
        self.hydrology: Optional[Hydrology] = None
        self.risk: Optional[Risk] = None

    def _load_data(
        self,
        forecast: bool = False,
        historical: bool = False,
    ) -> None:
        """
        S'assure que les données nécessaires sont chargées en mémoire.

        Args:
            forecast (bool): Si True, charge les prévisions si absentes.
            historical (bool): Si True, charge l'historique si absent.
        """
        if forecast and self.loader.forecast is None:
            self.loader.get_forecast()

        if historical and self.loader.historical is None:
            self.loader.get_historical()

    def _ensure_data(
        self,
        require_forecast: bool = False,
        require_historical: bool = False,
    ) -> None:
        """
        Ancien nom de ``_load_data``. Déprécié depuis v1.1.0.

        Args:
            require_forecast (bool): Ancien nom de forecast.
            require_historical (bool): Ancien nom de historical.
        """
        warnings.warn(
            "Weather._ensure_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather._load_data à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self._load_data(forecast=require_forecast, historical=require_historical)

    def _init_component(self, component: str) -> None:
        """
        S'assure que le composant demandé est initialisé.

        Args:
            component (str): Identifiant du composant parmi 'phenology',
                'hydrology' ou 'risk'.
        """
        if component == "phenology" and self.phenology is None:
            self._load_data(historical=True)
            hist = self.loader.historical
            self.phenology = Phenology(
                self.location,
                hist["precipitation"],
                hist[["temperature_min", "temperature_max"]],
            )

        elif component == "hydrology" and self.hydrology is None:
            self._load_data(historical=True)
            hist = self.loader.historical
            self.hydrology = Hydrology(
                self.location,
                hist["precipitation"],
                hist[["temperature_min", "temperature_max"]],
            )

        elif component == "risk" and self.risk is None:
            self._load_data(forecast=True, historical=True)
            self.risk = Risk(
                self.location,
                self.loader.historical["precipitation"],
                self.loader.forecast,
            )

    def _ensure_components(self, component: str) -> None:
        """
        Ancien nom de ``_init_component``. Déprécié depuis v1.1.0.

        Args:
            component (str): Identifiant du composant.
        """
        warnings.warn(
            "Weather._ensure_components est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather._init_component à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self._init_component(component)

    def forecast(self, days: int = None) -> dict:
        """
        Récupère la prévision météorologique court-terme.

        Args:
            days (int): Nombre de jours de prévision (défaut depuis CONFIG).

        Returns:
            dict: Dictionnaire des prévisions avec la localisation, les données
                brutes, la source et l'horodatage de mise à jour.
        """
        if days is None:
            days = CONFIG["weather"]["forecast_days_default"]

        # Plafonnement au maximum autorisé par la configuration
        if days > CONFIG["weather"]["max_forecast_days"]:
            days = CONFIG["weather"]["max_forecast_days"]

        df = self.loader.get_forecast(days=days)

        return {
            "location": {
                "name": self.location.name,
                "lat": self.location.lat,
                "lon": self.location.lon,
            },
            "data": df.reset_index().to_dict(orient="records"),
            "source": self.loader.source,
            "last_updated": pd.Timestamp.now().isoformat(),
        }

    def historical(
        self,
        metric: str = "all",
        months: int = 120,
        source: str = None,
        months_back: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Retourne les séries historiques météorologiques.

        Args:
            metric (str): Filtre de colonne : 'temperature', 'precipitation',
                'humidity' ou 'all' (défaut, toutes les colonnes).
            months (int): Nombre de mois d'historique à récupérer.
            source (str): Source des données de précipitation. Valeurs acceptées :
                'chirps', 'openmeteo', 'both'. Si None, utilise la valeur de CONFIG.
            months_back (int, optionnel): Ancien nom du paramètre ``months``.

        Returns:
            pd.DataFrame: DataFrame historique avec DatetimeIndex.
        """
        if months_back is not None:
            warnings.warn(
                "Le paramètre 'months_back' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'months' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            months = months_back

        df = self.loader.get_historical(months=months, source=source)

        # Filtre optionnel sur les colonnes
        if metric != "all":
            cols = [c for c in df.columns if metric in c]
            if cols:
                return df[cols]

        return df

    def gdd(
        self,
        crop: str,
        start: Union[str, pd.Timestamp],
        end: Union[str, pd.Timestamp] = None,
    ) -> dict:
        """
        Calcule l'accumulation des degrés-jours de croissance (GDD).

        Args:
            crop (str): Nom de la culture ('maize', 'rice', etc.).
            start (str ou pd.Timestamp): Date de semis (YYYY-MM-DD).
            end (str ou pd.Timestamp): Date de fin (optionnel).

        Returns:
            dict: Résultat du cumul GDD.
        """
        self._init_component("phenology")
        return self.phenology.gdd(crop, start, end)

    def growing_degree_days(
        self,
        crop: str,
        start_date: str,
        end_date: str = None,
    ) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.1.0.

        Utilisez ``gdd(crop, start, end)`` à la place.

        Args:
            crop (str): Nom de la culture.
            start_date (str): Ancien nom de start.
            end_date (str): Ancien nom de end.

        Returns:
            dict: Résultat du cumul GDD.
        """
        warnings.warn(
            "Weather.growing_degree_days() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez gdd() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.gdd(crop, start_date, end_date)

    def onset(self) -> dict:
        """
        Détecte la date de démarrage de la saison agricole.

        Returns:
            dict: Résultat de l'onset.
        """
        self._init_component("phenology")
        return self.phenology.onset()

    def cessation(self) -> dict:
        """
        Détermine la date de fin des pluies utiles.

        Returns:
            dict: Résultat de la cessation.
        """
        self._init_component("phenology")
        return self.phenology.cessation()

    def drought(
        self,
        method: str = "spi",
        window: int = 3,
        window_months: Optional[int] = None,
    ) -> dict:
        """
        Calcule l'indice de sécheresse.

        Args:
            method (str): 'spi', 'markov', 'hurst', 'combined'. Par défaut 'spi'.
            window (int): Fenêtre temporelle en mois. Par défaut 3.
            window_months (int, optionnel): Ancien nom du paramètre window.

        Returns:
            dict: Indicateurs de sécheresse.
        """
        self._init_component("risk")
        return self.risk.drought(method=method, window=window, window_months=window_months)

    def drought_index(self, method: str = "spi", window_months: int = 3) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.1.0.

        Utilisez ``drought(method, window)`` à la place.

        Args:
            method (str): Méthode de calcul.
            window_months (int): Ancien nom du paramètre window.

        Returns:
            dict: Indicateurs de sécheresse.
        """
        warnings.warn(
            "Weather.drought_index() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez drought() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.drought(method=method, window=window_months)

    def rain_prob(
        self,
        days: int = 1,
        min_mm: float = 1.0,
        days_ahead: Optional[int] = None,
        min_rainfall_mm: Optional[float] = None,
    ) -> dict:
        """
        Prévoit la probabilité de pluie.

        Args:
            days (int): Nombre de jours futurs.
            min_mm (float): Seuil minimum en mm.
            days_ahead (int, optionnel): Ancien nom du paramètre days.
            min_rainfall_mm (float, optionnel): Ancien nom du paramètre min_mm.

        Returns:
            dict: Probabilité et recommandations agronomiques.
        """
        if days_ahead is not None:
            warnings.warn(
                "Le paramètre 'days_ahead' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'days' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            days = days_ahead

        if min_rainfall_mm is not None:
            warnings.warn(
                "Le paramètre 'min_rainfall_mm' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'min_mm' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            min_mm = min_rainfall_mm

        self._init_component("risk")
        return self.risk.rain_prob(days=days, min_mm=min_mm)

    def rain_probability(self, days_ahead: int = 1, min_rainfall_mm: float = 1.0) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.1.0.

        Utilisez ``rain_prob(days, min_mm)`` à la place.

        Args:
            days_ahead (int): Ancien nom de days.
            min_rainfall_mm (float): Ancien nom de min_mm.

        Returns:
            dict: Probabilité et recommandations agronomiques.
        """
        warnings.warn(
            "Weather.rain_probability() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez rain_prob() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.rain_prob(days=days_ahead, min_mm=min_rainfall_mm)

    def water_balance(
        self,
        crop: str = "maize",
        soil_type: str = "ferrugineux",
    ) -> pd.DataFrame:
        """
        Simule le bilan hydrique quotidien (FAO-56).

        Args:
            crop (str): Type de culture.
            soil_type (str): Type de sol.

        Returns:
            pd.DataFrame: DataFrame avec le bilan hydrique.
        """
        self._init_component("hydrology")
        # Mise à jour des paramètres de culture et de sol avant le calcul
        self.hydrology.crop = crop
        self.hydrology.soil_type = soil_type
        self.hydrology.soil = self.hydrology.soil_params(soil_type)
        return self.hydrology.water_balance()

    def et0_hargreaves(
        self,
        tmin: float,
        tmax: float,
        day_of_year: int,
    ) -> float:
        """
        Calcule l'ETo par Hargreaves-Samani.

        Args:
            tmin (float): Température minimale (degC).
            tmax (float): Température maximale (degC).
            day_of_year (int): Jour de l'année (1 à 365).

        Returns:
            float: ETo en mm/jour.
        """
        self._init_component("hydrology")
        return self.hydrology.et0_hargreaves(tmin, tmax, day_of_year)

    def _setup(self) -> None:
        """
        Initialise toutes les classes composantes de la façade météo.
        """
        self._init_component("phenology")
        self._init_component("hydrology")
        self._init_component("risk")

    def _init_all_components(self) -> None:
        """
        Ancien nom de ``_setup``. Déprécié depuis v1.1.0.
        """
        warnings.warn(
            "Weather._init_all_components est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather._setup à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self._setup()

    # ----------------------------------------------------------------
    # Attributs et propriétés dépréciés (anciens noms)
    # ----------------------------------------------------------------

    @property
    def cache_dir(self) -> Optional[str]:
        """Ancien nom de ``cache``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Weather.cache_dir est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather.cache à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.cache

    @cache_dir.setter
    def cache_dir(self, value: Optional[str]) -> None:
        """Ancien setter de ``cache``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Weather.cache_dir est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather.cache à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.cache = value

    @property
    def weather_data(self) -> WeatherLoader:
        """Ancien nom de ``loader``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Weather.weather_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather.loader à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.loader

    @weather_data.setter
    def weather_data(self, value: WeatherLoader) -> None:
        """Ancien setter de ``loader``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Weather.weather_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather.loader à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.loader = value

    @property
    def risk_indicators(self) -> Optional[Risk]:
        """Ancien nom de ``risk``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Weather.risk_indicators est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather.risk à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.risk

    @risk_indicators.setter
    def risk_indicators(self, value: Optional[Risk]) -> None:
        """Ancien setter de ``risk``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Weather.risk_indicators est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Weather.risk à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.risk = value


# ----------------------------------------------------------------
# Rétrocompatibilité au niveau du module : WeatherSession -> Weather
# ----------------------------------------------------------------

_DEPRECATED = {
    "WeatherSession": ("Weather", Weather),
}


def __getattr__(name: str):
    """
    Intercepte les anciens noms exportés depuis ce module.

    Args:
        name (str): Nom du symbole demandé.

    Returns:
        object: La cible correspondant au nouveau nom.

    Raises:
        AttributeError: Si le nom n'est ni courant ni un ancien nom connu.
    """
    if name in _DEPRECATED:
        new_name, target = _DEPRECATED[name]
        warnings.warn(
            f"kadi.weather.session.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return target
    raise AttributeError(
        f"Le module 'kadi.weather.session' n'a pas d'attribut '{name}'."
    )
