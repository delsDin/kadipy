"""
Module location.py

Ce module contient la classe Location qui représente une position
géographique au Bénin et déduit automatiquement sa zone agro-climatique.
"""

import warnings

from kadi.exceptions import LocationError
from kadi.config import CONFIG


class Location:
    """
    Représente une localisation géographique avec détection automatique
    de la zone climatique béninoise.

    Attributs:
        lat (float): Latitude en degrés décimaux.
        lon (float): Longitude en degrés décimaux.
        name (str): Nom de la localité.
        zone (str): Zone climatique détectée ('Sud', 'Centre' ou 'Nord').
        regime (str): Régime climatique ('bimodal' ou 'unimodal').
    """

    def __init__(
        self,
        lat: float = None,
        lon: float = None,
        name: str = None,
        *,
        # Anciens paramètres conservés pour la rétrocompatibilité
        latitude: float = None,
        longitude: float = None,
    ):
        """
        Initialise une nouvelle localisation.

        Les paramètres ``lat`` et ``lon`` sont les noms recommandés.
        Les anciens noms ``latitude`` et ``longitude`` restent acceptés
        mais émettent un DeprecationWarning.

        Args:
            lat (float): Latitude en degrés décimaux.
            lon (float): Longitude en degrés décimaux.
            name (str): Nom de la localité (optionnel).
            latitude (float): Ancien nom de lat. Déprécié depuis v1.1.0.
            longitude (float): Ancien nom de lon. Déprécié depuis v1.1.0.
        """
        # Gestion des anciens paramètres avec avertissement de déprécation
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

        # Validation : les coordonnées doivent être fournies
        if lat is None or lon is None:
            raise TypeError("Location() requiert les arguments 'lat' et 'lon'.")

        # Stockage des coordonnées
        self.lat = lat
        self.lon = lon

        # Validation par rapport à la zone d'étude V1 (Bénin)
        bbox = CONFIG["weather"]["gps_validation_bbox"]
        if not (
            bbox["min_lat"] <= lat <= bbox["max_lat"]
            and bbox["min_lon"] <= lon <= bbox["max_lon"]
        ):
            raise LocationError(
                f"Les coordonnées GPS ({lat}, {lon}) sont en dehors "
                "de la zone d'étude (Bénin V1)."
            )

        self.name = name if name else f"Point({lat}, {lon})"

        # Détection automatique de la zone et du régime (stockés comme attributs)
        self.zone = self._detect_zone()
        self.regime = self._regime()

    def _detect_zone(self) -> str:
        """
        Calcule la zone climatique à partir de la latitude.

        Méthode interne appelée à l'initialisation. Pour lire la zone depuis
        l'extérieur, utiliser l'attribut ``self.zone``.

        Returns:
            str: 'Sud', 'Centre' ou 'Nord'.
        """
        if self.lat < 7.5:
            return "Sud"
        elif 7.5 <= self.lat < 9.0:
            return "Centre"
        else:
            return "Nord"

    def _regime(self) -> str:
        """
        Déduit le régime climatique selon la zone.

        Le Sud et le Centre ont un régime bimodal (deux saisons de pluies).
        Le Nord a un régime unimodal (une saison de pluies).

        Returns:
            str: 'bimodal' ou 'unimodal'.
        """
        # Le Centre suit également un cycle bimodal
        if self.zone in ("Sud", "Centre"):
            return "bimodal"
        return "unimodal"

    def climate(self) -> dict:
        """
        Retourne les paramètres climatiques par défaut pour la zone.

        Returns:
            dict: Dictionnaire des paramètres climatiques de la zone.
        """
        params = {
            "Sud":    {"Tbase": 10, "onset_method": "walter_anyadike"},
            "Centre": {"Tbase": 10, "onset_method": "hybrid"},
            "Nord":   {"Tbase": 10, "onset_method": "sivakumar"},
        }
        return params.get(self.zone, {})

    def to_dict(self) -> dict:
        """
        Sérialise la localisation pour le cache.

        Returns:
            dict: Représentation sérialisable de l'objet Location.
        """
        return {
            "name":   self.name,
            "lat":    self.lat,
            "lon":    self.lon,
            "zone":   self.zone,
            "regime": self.regime,
        }

    # ----------------------------------------------------------------
    # Méthodes dépréciées (anciens noms publics)
    # ----------------------------------------------------------------

    def detect_zone(self) -> str:
        """
        Ancienne méthode publique. Dépréciée depuis v1.1.0.

        Utilisez l'attribut ``self.zone`` à la place.

        Returns:
            str: Zone climatique ('Sud', 'Centre' ou 'Nord').
        """
        warnings.warn(
            "Location.detect_zone() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez l'attribut Location.zone à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.zone

    def get_climate_params(self) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.1.0.

        Utilisez ``Location.climate()`` à la place.

        Returns:
            dict: Paramètres climatiques de la zone.
        """
        warnings.warn(
            "Location.get_climate_params() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Location.climate() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.climate()

    # ----------------------------------------------------------------
    # Propriétés de rétrocompatibilité (anciens noms d'attributs)
    # ----------------------------------------------------------------

    @property
    def latitude(self) -> float:
        """Ancien nom de ``lat``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Location.latitude est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Location.lat à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.lat

    @latitude.setter
    def latitude(self, value: float) -> None:
        """Ancien setter de ``lat``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Location.latitude est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Location.lat à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.lat = value

    @property
    def longitude(self) -> float:
        """Ancien nom de ``lon``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Location.longitude est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Location.lon à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.lon

    @longitude.setter
    def longitude(self, value: float) -> None:
        """Ancien setter de ``lon``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Location.longitude est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Location.lon à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.lon = value

    @property
    def climate_regime(self) -> str:
        """Ancien nom de ``regime``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Location.climate_regime est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Location.regime à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.regime

    @climate_regime.setter
    def climate_regime(self, value: str) -> None:
        """Ancien setter de ``regime``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Location.climate_regime est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Location.regime à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.regime = value
