"""
Module data.py

Ce module gère l'acquisition, le cache local (SQLite KadiPy) et la
normalisation des données météorologiques pour kadi.weather.
"""

import warnings

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import os

from kadi.cache import get_connection, init_db
from kadi.config import CONFIG
from kadi.exceptions import OfflineError
from .location import Location


class WeatherLoader:
    """
    Gère l'acquisition, le cache SQLite et la normalisation
    des données météorologiques pour une localisation donnée.

    Attributs:
        location (Location): Localisation associée.
        forecast (pd.DataFrame): Prévisions en mémoire (None si non chargées).
        historical (pd.DataFrame): Historique en mémoire (None si non chargé).
        source (str): Source des dernières données chargées.
    """

    @staticmethod
    def _unify_temp(df: pd.DataFrame) -> pd.DataFrame:
        """
        Garantit la présence de la colonne ``temperature_mean`` dans le DataFrame.

        Centralise la logique d'alias entre ``temperature_avg`` (nom SQLite du
        cache) et ``temperature_mean`` (nom utilisé par les algorithmes du module
        weather).

        Ordre de priorité :
        1. Calcul direct (temperature_min + temperature_max) / 2 si les deux
           colonnes de base sont disponibles.
        2. Alias depuis ``temperature_avg`` si le calcul est impossible (cas
           cache sans temperature_min/temperature_max).

        Args:
            df (pd.DataFrame): DataFrame météo brut ou issu du cache.

        Returns:
            pd.DataFrame: DataFrame avec ``temperature_mean`` garanti si les
                données sources sont présentes.
        """
        # Calcul direct prioritaire : (min + max) / 2
        if "temperature_min" in df.columns and "temperature_max" in df.columns:
            tmean_calc = (df["temperature_min"] + df["temperature_max"]) / 2.0
            if "temperature_mean" not in df.columns:
                # Création de la colonne depuis les bornes thermiques
                df["temperature_mean"] = tmean_calc
            else:
                # Comblement des NaN uniquement, sans écraser les valeurs existantes
                df["temperature_mean"] = df["temperature_mean"].fillna(tmean_calc)
        elif "temperature_avg" in df.columns and "temperature_mean" not in df.columns:
            # Alias de secours : temperature_avg provient du cache SQLite
            df["temperature_mean"] = df["temperature_avg"]
        return df

    def __init__(self, location: Location, cache_dir: str = None):
        """
        Initialise le gestionnaire de données pour une localisation donnée.

        Args:
            location (Location): Instance de la classe Location.
            cache_dir (str): Ignoré car on utilise kadi.cache (SQLite global).
        """
        self.location = location
        # Données en mémoire (chargées à la demande)
        self.forecast: Optional[pd.DataFrame] = None
        self.historical: Optional[pd.DataFrame] = None
        self.source: str = "none"

        # S'assure que la base de données et les tables existent
        init_db()

    def get_forecast(self, days: int = 7, refresh: bool = False) -> pd.DataFrame:
        """
        Récupère les prévisions météorologiques en vérifiant d'abord le cache.

        Args:
            days (int): Nombre de jours de prévision à récupérer.
            refresh (bool): Si True, ignore le cache et force le rechargement.

        Returns:
            pd.DataFrame: DataFrame indexé par date avec les prévisions.

        Raises:
            OfflineError: Si l'API est inaccessible et qu'aucun cache n'existe.
        """
        today = datetime.now().date()
        end_date = today + timedelta(days=days - 1)

        if not refresh:
            # Vérification du cache avant tout appel API
            cached_data = self._from_cache(today.isoformat(), end_date.isoformat())
            if not cached_data.empty and len(cached_data) >= days:
                fetched_at = pd.to_datetime(cached_data["fetched_at"]).max()
                cache_ttl = timedelta(
                    hours=CONFIG["weather"]["cache_ttl_forecast_hours"]
                )
                if datetime.now() - fetched_at < cache_ttl:
                    cached_data = cached_data.head(days)
                    self.forecast = cached_data
                    self.source = "cached"
                    return cached_data

        # Appel API
        try:
            df = self._fetch_forecast(days=days)
            self._to_cache(df, "forecast")
        except Exception as e:
            # Repli sur le cache si disponible
            if "cached_data" in locals() and not cached_data.empty:
                cached_data = cached_data.head(days)
                self.forecast = cached_data
                self.source = "cached_offline"
                return cached_data
            raise OfflineError(
                "Impossible de récupérer les prévisions et aucun cache "
                f"n'est disponible : {e}"
            )

        df = df.head(days)
        self.forecast = df
        self.source = "open-meteo"
        return df

    def get_historical(
        self,
        months: int = 120,
        refresh: bool = False,
        source: str = None,
    ) -> pd.DataFrame:
        """
        Récupère les données historiques en vérifiant d'abord le cache SQLite.

        Args:
            months (int): Nombre de mois d'historique à récupérer.
            refresh (bool): Si True, ignore le cache et force le rechargement.
            source (str): Source de précipitation. Valeurs acceptées :
                'chirps' (CHIRPS uniquement, repli Open-Meteo si indisponible),
                'openmeteo' (Open-Meteo uniquement, comportement V1.0),
                'both' (CHIRPS pour l'historique long, Open-Meteo pour le
                récent). Si None, utilise CONFIG.

        Returns:
            pd.DataFrame: DataFrame indexé par date avec l'historique météo.

        Raises:
            OfflineError: Si l'API est inaccessible et qu'aucun cache n'existe.
        """
        # Résolution de la source par défaut depuis la configuration
        if source is None:
            source = CONFIG["weather"]["chirps"]["source_default"]

        days = months * 30
        today = datetime.now().date()
        start_date = today - timedelta(days=days)

        if not refresh:
            # Vérification du cache (tolérance de 5 jours)
            cached_data = self._from_cache(start_date.isoformat(), today.isoformat())
            if not cached_data.empty and len(cached_data) >= (days - 5):
                fetched_at = pd.to_datetime(cached_data["fetched_at"]).max()
                cache_ttl = timedelta(
                    days=CONFIG["weather"]["cache_ttl_historical_days"]
                )
                if datetime.now() - fetched_at < cache_ttl:
                    self.historical = cached_data
                    self.source = "cached"
                    return cached_data

        # Appel API
        try:
            df = self._fetch_historical(days=days, source=source)
            self._to_cache(df, "historical")
        except Exception as e:
            if "cached_data" in locals() and not cached_data.empty:
                self.historical = cached_data
                self.source = "cached_offline"
                return cached_data
            raise OfflineError(
                "Impossible de récupérer l'historique météo et aucun cache "
                f"n'est disponible : {e}"
            )

        self.historical = df
        self.source = source
        return df

    def _from_cache(self, start: str, end: str) -> pd.DataFrame:
        """
        Récupère les données météo depuis le cache SQLite KadiPy.

        Args:
            start (str): Date de début au format ISO (YYYY-MM-DD).
            end (str): Date de fin au format ISO (YYYY-MM-DD).

        Returns:
            pd.DataFrame: DataFrame des données en cache, ou DataFrame vide.
        """
        with get_connection() as conn:
            query = """
                SELECT date, temperature_min, temperature_max, temperature_avg,
                       precipitation, humidity, data_type, data_source,
                       confidence, fetched_at
                FROM weather_data
                WHERE location_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, fetched_at DESC
            """
            df = pd.read_sql_query(
                query, conn,
                params=(self.location.name, start, end),
            )

            if df.empty:
                return df

            # Déduplication : garder le fetch le plus récent par date
            df = df.drop_duplicates(subset=["date"], keep="first")

            # Normalisation de l'index
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

            # Garantit la présence de temperature_mean (logique centralisée)
            df = WeatherLoader._unify_temp(df)

            return df

    def _to_cache(self, data: pd.DataFrame, kind: str) -> None:
        """
        Insère ou met à jour les données météo dans le cache SQLite KadiPy.

        Args:
            data (pd.DataFrame): DataFrame contenant les données météo normalisées.
            kind (str): Type de données ('forecast' ou 'historical').

        Returns:
            None
        """
        # Vérification si le DataFrame est vide
        if data.empty:
            # Fin prématurée si aucune donnée à sauvegarder
            return

        # Ouverture de la connexion à la base de données SQLite KadiPy
        with get_connection() as conn:
            # Création du curseur d'exécution SQL
            cursor = conn.cursor()

            # Horodatage courant au format ISO
            now = datetime.now().isoformat()

            # Parcours de chaque ligne du DataFrame de données météo
            for date_idx, row in data.iterrows():
                # Formattage de la date en chaîne YYYY-MM-DD
                date_str = date_idx.strftime("%Y-%m-%d")

                # Extraction ou calcul de la température moyenne
                t_avg = row.get("temperature_mean", row.get("temperature_avg", None))
                if t_avg is None:
                    # Calcul par la moyenne min et max
                    t_avg = (row["temperature_min"] + row["temperature_max"]) / 2.0

                # Extraction de la source réelle de données pour la ligne courante
                valeur_source = row.get("data_source", None)
                if not valeur_source or pd.isna(valeur_source):
                    valeur_source = "open-meteo"

                # Insertion avec gestion du conflit d'unicité (ON CONFLICT UPDATE)
                cursor.execute(
                    """
                    INSERT INTO weather_data (
                        location_id, latitude, longitude, date, hour,
                        temperature_min, temperature_max, temperature_avg,
                        precipitation, humidity, data_type, data_source,
                        confidence, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(location_id, date, hour) DO UPDATE SET
                        temperature_min=excluded.temperature_min,
                        temperature_max=excluded.temperature_max,
                        temperature_avg=excluded.temperature_avg,
                        precipitation=excluded.precipitation,
                        humidity=excluded.humidity,
                        data_type=excluded.data_type,
                        data_source=excluded.data_source,
                        confidence=excluded.confidence,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        self.location.name,
                        self.location.lat,
                        self.location.lon,
                        date_str,
                        -1,
                        row["temperature_min"],
                        row["temperature_max"],
                        t_avg,
                        row["precipitation"],
                        row.get("humidity", 0.0),
                        kind,
                        str(valeur_source),
                        1.0,
                        now,
                    ),
                )

            # Détermination de la source principale pour la table de métadonnées
            source_principale = "open-meteo"
            if "data_source" in data.columns:
                sources_uniques = [
                    str(s)
                    for s in data["data_source"].dropna().unique()
                    if s
                ]
                if sources_uniques:
                    if len(sources_uniques) > 1:
                        source_principale = "+".join(sorted(sources_uniques))
                    else:
                        source_principale = sources_uniques[0]

            # Mise à jour de la table des métadonnées du cache
            cursor.execute(
                """
                INSERT INTO cache_metadata (
                    module_name, table_name, data_source,
                    last_fetch, last_success, last_update
                ) VALUES ('weather', 'weather_data', ?, ?, ?, ?)
                ON CONFLICT(module_name, data_source) DO UPDATE SET
                    last_fetch=excluded.last_fetch,
                    last_success=excluded.last_success,
                    last_update=excluded.last_update
                """,
                (source_principale, now, now, now),
            )

            # Validation définitive des transactions en base
            conn.commit()

    def _fetch_forecast(self, days: int = 7) -> pd.DataFrame:
        """
        Récupère les prévisions via l'API Open-Meteo.

        Args:
            days (int): Nombre de jours de prévision.

        Returns:
            pd.DataFrame: DataFrame normalisé des prévisions.
        """
        from kadi._sources import fetch_forecast
        from kadi._utils.network import fetch_with_retry

        attempts = CONFIG["weather"]["retry_attempts"]
        backoff = CONFIG["weather"]["retry_backoff_sec"]

        data_list = fetch_with_retry(
            fetch_forecast, attempts, backoff,
            lat=self.location.lat, lon=self.location.lon, days=days,
        )

        df = pd.DataFrame(data_list)
        return self._normalize(df)

    def _fetch_historical(self, days: int = 7, source: str = "both") -> pd.DataFrame:
        """
        Récupère l'historique météo en combinant CHIRPS et/ou Open-Meteo.

        La logique de fusion est la suivante :
        - 'openmeteo' : comportement V1 inchangé, Open-Meteo fournit tout.
        - 'chirps' : CHIRPS fournit les précipitations, Open-Meteo les
          températures. Repli automatique sur Open-Meteo si CHIRPS échoue.
        - 'both' : CHIRPS couvre la période historique, Open-Meteo complète
          les dates récentes non encore disponibles dans CHIRPS.

        Args:
            days (int): Nombre de jours d'historique à récupérer.
            source (str): Source de précipitation à utiliser.

        Returns:
            pd.DataFrame: DataFrame normalisé avec les données historiques.
        """
        from datetime import date as date_type

        # Calcul des bornes de la plage demandée
        aujourd_hui = datetime.now().date()
        date_debut = aujourd_hui - timedelta(days=days)
        months = max(1, (days + 29) // 30)

        # Récupération des températures via Open-Meteo (toujours nécessaire)
        from kadi._sources.open_meteo import fetch_historical
        from kadi._utils.network import fetch_with_retry

        attempts = CONFIG["weather"]["retry_attempts"]
        backoff = CONFIG["weather"]["retry_backoff_sec"]

        om_list = fetch_with_retry(
            fetch_historical, attempts, backoff,
            lat=self.location.lat, lon=self.location.lon,
            months_back=months,
        )
        df_om = pd.DataFrame(om_list)
        df_om = self._normalize(df_om)
        # Marquage explicite de la source Open-Meteo pour la précipitation
        df_om["data_source"] = "open-meteo"

        # Mode Open-Meteo uniquement : comportement V1 inchangé
        if source == "openmeteo":
            return df_om

        # Récupération des précipitations CHIRPS
        from kadi._sources.chirps import fetch_historical_precipitation

        df_chirps = None
        try:
            df_chirps = fetch_historical_precipitation(
                lat=self.location.lat,
                lon=self.location.lon,
                start_date=date_debut.isoformat(),
                end_date=aujourd_hui.isoformat(),
            )
        except Exception as exc:
            # Repli global sur Open-Meteo avec message explicite
            import logging
            logging.getLogger(__name__).warning(
                "CHIRPS inaccessible pour toute la plage demandée. "
                "Les précipitations proviennent exclusivement d'Open-Meteo. "
                "Détail : %s",
                exc,
            )

        # Si CHIRPS n'a rien retourné : comportement identique à 'openmeteo'
        if df_chirps is None or df_chirps.empty:
            import logging
            logging.getLogger(__name__).warning(
                "Aucune donnée CHIRPS disponible (source='%s'). "
                "Repli automatique sur Open-Meteo.",
                source,
            )
            return df_om

        # Fusion CHIRPS (précipitations) + Open-Meteo (températures)
        df_chirps = df_chirps.set_index("date")
        df_chirps.index = pd.to_datetime(df_chirps.index)

        if source == "chirps":
            # CHIRPS fournit les précipitations, Open-Meteo les températures
            df_fusion = df_om.copy()
            dates_chirps = df_chirps.index
            masque = df_fusion.index.isin(dates_chirps)
            df_fusion.loc[masque, "precipitation"] = df_chirps.loc[
                df_chirps.index.isin(df_fusion.index), "precipitation"
            ].values
            df_fusion["data_source"] = "open-meteo"
            df_fusion.loc[masque, "data_source"] = "chirps"
            return df_fusion

        # Mode 'both' : CHIRPS pour la période couverte, Open-Meteo pour le reste
        df_fusion = df_om.copy()
        dates_chirps = df_chirps.index
        masque_chirps = df_fusion.index.isin(dates_chirps)
        df_fusion.loc[masque_chirps, "precipitation"] = df_chirps.loc[
            df_chirps.index.isin(df_fusion.index), "precipitation"
        ].values
        df_fusion.loc[masque_chirps, "data_source"] = "chirps"

        return df_fusion

    def _normalize(self, raw: pd.DataFrame) -> pd.DataFrame:
        """
        Normalise les données brutes retournées par une source météo.

        Applique dans l'ordre :
        1. Conversion de la colonne 'date' en index DatetimeIndex.
        2. Filtrage des valeurs aberrantes (températures hors [-5, 55] degC,
           pluie négative).
        3. Calcul de la colonne 'data_quality' (ratio de colonnes critiques
           renseignées).
        4. Interpolation linéaire sur les lacunes courtes (max 3 jours).
        5. Remplissage résiduel (précipitation à 0, temperature_mean).

        Args:
            raw (pd.DataFrame): DataFrame brut retourné par la source de données.

        Returns:
            pd.DataFrame: DataFrame normalisé avec l'index en date.
        """
        if raw.empty:
            return raw

        df = raw.copy()

        # 1. Conversion et indexation par date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

        # Tri chronologique avant interpolation
        df = df.sort_index()

        # 2. Filtrage des valeurs aberrantes de température
        for col in ("temperature_min", "temperature_max"):
            if col in df.columns:
                masque_aberrant = (df[col] < -5.0) | (df[col] > 55.0)
                df.loc[masque_aberrant, col] = np.nan

        # Précipitation négative remise à zéro (impossible physiquement)
        if "precipitation" in df.columns:
            df.loc[df["precipitation"] < 0.0, "precipitation"] = 0.0

        # 3. Colonne data_quality : proportion de colonnes critiques renseignées
        cols_critiques = [
            c for c in ("temperature_min", "temperature_max", "precipitation")
            if c in df.columns
        ]
        if cols_critiques:
            ratio_manquant = df[cols_critiques].isna().mean(axis=1)
            df["data_quality"] = (1.0 - ratio_manquant).round(2)
        else:
            df["data_quality"] = 1.0

        # 4. Interpolation linéaire pour les lacunes courtes (max 3 jours)
        for col in cols_critiques:
            if df[col].isna().any():
                df[col] = df[col].interpolate(
                    method="linear", limit=3, limit_direction="both"
                )

        # 5. Remplissages résiduels après interpolation
        if "precipitation" in df.columns:
            # Toute lacune restante en pluie est supposée nulle (0 mm)
            df["precipitation"] = df["precipitation"].fillna(0.0)

        # Garantit la présence de temperature_mean (logique centralisée)
        df = WeatherLoader._unify_temp(df)

        return df

    # ----------------------------------------------------------------
    # Méthodes et attributs dépréciés (anciens noms)
    # ----------------------------------------------------------------

    def fetch_forecast(self, days: int = 7, force_refresh: bool = False) -> pd.DataFrame:
        """
        Ancienne méthode publique. Dépréciée depuis v1.2.0.

        Utilisez ``get_forecast(days, refresh)`` à la place.

        Args:
            days (int): Nombre de jours de prévision.
            force_refresh (bool): Ancien nom de ``refresh``.

        Returns:
            pd.DataFrame: DataFrame des prévisions.
        """
        warnings.warn(
            "WeatherLoader.fetch_forecast() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez get_forecast() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.get_forecast(days=days, refresh=force_refresh)

    def fetch_historical(
        self,
        months_back: int = 120,
        force_refresh: bool = False,
        source: str = None,
    ) -> pd.DataFrame:
        """
        Ancienne méthode publique. Dépréciée depuis v1.2.0.

        Utilisez ``get_historical(months, refresh, source)`` à la place.

        Args:
            months_back (int): Ancien nom de ``months``.
            force_refresh (bool): Ancien nom de ``refresh``.
            source (str): Source de données.

        Returns:
            pd.DataFrame: DataFrame historique.
        """
        warnings.warn(
            "WeatherLoader.fetch_historical() est obsolète et sera supprimé "
            "dans KadiPy v2.0. Utilisez get_historical() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.get_historical(months=months_back, refresh=force_refresh, source=source)

    @property
    def forecast_data(self) -> Optional[pd.DataFrame]:
        """Ancien nom de ``forecast``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "WeatherLoader.forecast_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader.forecast à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.forecast

    @forecast_data.setter
    def forecast_data(self, value: Optional[pd.DataFrame]) -> None:
        """Ancien setter de ``forecast``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "WeatherLoader.forecast_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader.forecast à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.forecast = value

    @property
    def historical_data(self) -> Optional[pd.DataFrame]:
        """Ancien nom de ``historical``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "WeatherLoader.historical_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader.historical à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.historical

    @historical_data.setter
    def historical_data(self, value: Optional[pd.DataFrame]) -> None:
        """Ancien setter de ``historical``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "WeatherLoader.historical_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader.historical à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.historical = value

    @property
    def data_source(self) -> str:
        """Ancien nom de ``source``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "WeatherLoader.data_source est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader.source à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.source

    @data_source.setter
    def data_source(self, value: str) -> None:
        """Ancien setter de ``source``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "WeatherLoader.data_source est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader.source à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.source = value

    # ----------------------------------------------------------------
    # Méthodes privées dépréciées (anciens noms internes)
    # ----------------------------------------------------------------

    def _normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ancien nom de ``_normalize``. Déprécié depuis v1.2.0.

        Args:
            df (pd.DataFrame): DataFrame à normaliser.

        Returns:
            pd.DataFrame: DataFrame normalisé.
        """
        warnings.warn(
            "WeatherLoader._normalize_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader._normalize à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self._normalize(df)

    def _get_from_cache(self, start: str, end: str) -> pd.DataFrame:
        """
        Ancien nom de ``_from_cache``. Déprécié depuis v1.2.0.

        Args:
            start (str): Date de début ISO.
            end (str): Date de fin ISO.

        Returns:
            pd.DataFrame: Données en cache.
        """
        warnings.warn(
            "WeatherLoader._get_from_cache est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader._from_cache à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self._from_cache(start, end)

    def _save_to_cache(self, data: pd.DataFrame, kind: str) -> None:
        """
        Ancien nom de ``_to_cache``. Déprécié depuis v1.2.0.

        Args:
            data (pd.DataFrame): Données à sauvegarder.
            kind (str): Type de données.
        """
        warnings.warn(
            "WeatherLoader._save_to_cache est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader._to_cache à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self._to_cache(data, kind)

    def _fetch_forecast_data(self, days: int = 7) -> pd.DataFrame:
        """
        Ancien nom de ``_fetch_forecast``. Déprécié depuis v1.2.0.

        Args:
            days (int): Jours de prévision.

        Returns:
            pd.DataFrame: Données prévues.
        """
        warnings.warn(
            "WeatherLoader._fetch_forecast_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader._fetch_forecast à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self._fetch_forecast(days=days)

    def _fetch_historical_data(self, days: int = 7, source: str = "both") -> pd.DataFrame:
        """
        Ancien nom de ``_fetch_historical``. Déprécié depuis v1.2.0.

        Args:
            days (int): Jours d'historique.
            source (str): Source de données.

        Returns:
            pd.DataFrame: Données historiques.
        """
        warnings.warn(
            "WeatherLoader._fetch_historical_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez WeatherLoader._fetch_historical à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self._fetch_historical(days=days, source=source)



# ----------------------------------------------------------------
# Rétrocompatibilité au niveau du module : WeatherData -> WeatherLoader
# ----------------------------------------------------------------

# Alias de la classe pour les imports directs (ex: from kadi.weather.data import WeatherData)
_DEPRECATED = {
    "WeatherData": ("WeatherLoader", WeatherLoader),
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
            f"kadi.weather.data.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return target
    raise AttributeError(
        f"Le module 'kadi.weather.data' n'a pas d'attribut '{name}'."
    )
