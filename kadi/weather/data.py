"""
Module data.py

Ce module gère l'acquisition, le cache local (via SQLite KadiPy) et la normalisation
des données météorologiques pour le module kadi.weather.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import os

from kadi.cache import get_connection, init_db
from kadi.config import CONFIG
from kadi.exceptions import OfflineError
from .location import Location

class WeatherData:
    """
    Gère l'acquisition, le cache SQLite et la normalisation des données météorologiques.
    """

    @staticmethod
    def _unifier_colonne_temperature(df: pd.DataFrame) -> pd.DataFrame:
        """Garantit la présence de la colonne temperature_mean dans le DataFrame.

        Centralise la logique d'alias entre temperature_avg (nom SQLite du cache)
        et temperature_mean (nom utilisé par les algorithmes du module weather).
        Cette méthode est le point unique de normalisation de cette colonne.

        Ordre de priorité :
        1. Calcul direct (temperature_min + temperature_max) / 2 si les deux
           colonnes de base sont disponibles.
        2. Alias depuis temperature_avg si le calcul est impossible (cas cache
           sans temperature_min/temperature_max).

        Args:
            df (pd.DataFrame): DataFrame météo brut ou issu du cache.

        Returns:
            pd.DataFrame: DataFrame avec temperature_mean garanti si les
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

        :param location: Instance de la classe Location.
        :param cache_dir: Ignoré car on utilise kadi.cache (SQLite global).
        """
        self.location = location
        self.forecast_data: Optional[pd.DataFrame] = None
        self.historical_data: Optional[pd.DataFrame] = None
        self.data_source: str = 'none'
        
        # S'assure que la base de données et les tables existent
        init_db()

    def fetch_forecast(self, days: int = 7, force_refresh: bool = False) -> pd.DataFrame:
        """
        Récupère les prévisions météorologiques en vérifiant d'abord le cache SQLite.
        """
        today = datetime.now().date()
        end_date = today + timedelta(days=days - 1)
        
        if not force_refresh:
            cached_data = self._get_from_cache(today.isoformat(), end_date.isoformat())
            if not cached_data.empty and len(cached_data) >= days:
                fetched_at = pd.to_datetime(cached_data['fetched_at']).max()
                cache_ttl = timedelta(hours=CONFIG["weather"]["cache_ttl_forecast_hours"])
                if datetime.now() - fetched_at < cache_ttl:
                    cached_data = cached_data.head(days)
                    self.forecast_data = cached_data
                    self.data_source = 'cached'
                    return cached_data
                
        # Appel API
        try:
            df = self._fetch_forecast_data(days=days)
            self._save_to_cache(df, "forecast")
        except Exception as e:
            if 'cached_data' in locals() and not cached_data.empty:
                cached_data = cached_data.head(days)
                self.forecast_data = cached_data
                self.data_source = 'cached_offline'
                return cached_data
            raise OfflineError(f"Impossible de récupérer les prévisions et aucun cache n'est disponible : {e}")
        
        df = df.head(days)
        self.forecast_data = df
        self.data_source = 'open-meteo'
        return df

    def fetch_historical(self, months_back: int = 120, force_refresh: bool = False, source: str = None) -> pd.DataFrame:
        """
        Récupère les données historiques en vérifiant d'abord le cache SQLite.

        :param months_back: Nombre de mois d'historique à récupérer.
        :param force_refresh: Si True, ignore le cache et force le rechargement.
        :param source: Source de précipitation à utiliser. Valeurs acceptées :
            'chirps' (données CHIRPS uniquement, repli Open-Meteo si indisponible),
            'openmeteo' (Open-Meteo uniquement, comportement V1.0),
            'both' (CHIRPS pour l'historique long, Open-Meteo pour le récent).
            Si None, utilise CONFIG["weather"]["chirps"]["source_default"].
        """
        # Résolution de la source par défaut depuis la configuration
        if source is None:
            source = CONFIG["weather"]["chirps"]["source_default"]

        days = months_back * 30
        today = datetime.now().date()
        start_date = today - timedelta(days=days)
        
        if not force_refresh:
            cached_data = self._get_from_cache(start_date.isoformat(), today.isoformat())
            # On accepte le cache s'il est suffisamment rempli (tolérance 5 jours)
            if not cached_data.empty and len(cached_data) >= (days - 5):
                fetched_at = pd.to_datetime(cached_data['fetched_at']).max()
                cache_ttl = timedelta(days=CONFIG["weather"]["cache_ttl_historical_days"])
                if datetime.now() - fetched_at < cache_ttl:
                    self.historical_data = cached_data
                    self.data_source = 'cached'
                    return cached_data
                
        # Appel API
        try:
            df = self._fetch_historical_data(days=days, source=source)
            self._save_to_cache(df, "historical")
        except Exception as e:
            if 'cached_data' in locals() and not cached_data.empty:
                self.historical_data = cached_data
                self.data_source = 'cached_offline'
                return cached_data
            raise OfflineError(f"Impossible de récupérer l'historique météo et aucun cache n'est disponible : {e}")
        
        self.historical_data = df
        self.data_source = source
        return df

    def _get_from_cache(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Récupère les données météo depuis le cache SQLite KadiPy.
        """
        with get_connection() as conn:
            query = """
                SELECT date, temperature_min, temperature_max, temperature_avg, precipitation,
                       humidity, data_type, data_source, confidence, fetched_at
                FROM weather_data
                WHERE location_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, fetched_at DESC
            """
            df = pd.read_sql_query(query, conn, params=(self.location.name, start_date, end_date))
            
            if df.empty:
                return df
                
            # Déduplication au cas où (garder le fetch le plus récent)
            df = df.drop_duplicates(subset=['date'], keep='first')
            
            # Normalisation
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # Garantit la présence de temperature_mean (logique centralisée)
            df = WeatherData._unifier_colonne_temperature(df)

            return df

    def _save_to_cache(self, data: pd.DataFrame, data_type: str) -> None:
        """Insère ou met à jour les données météo dans le cache SQLite KadiPy.

        Cette méthode parcourt les lignes du DataFrame et les sauvegarde dans la
        table SQLite weather_data. La vraie source des données (open-meteo, chirps,
        etc.) est préservée pour chaque ligne au lieu d'être remplacée par une
        valeur statique.

        Args:
            data (pd.DataFrame): DataFrame contenant les données météo normalisées.
            data_type (str): Type de données ("forecast" ou "historical").

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
                date_str = date_idx.strftime('%Y-%m-%d')

                # Extraction ou calcul de la température moyenne
                t_avg = row.get('temperature_mean', row.get('temperature_avg', None))
                # Fallback si t_avg n'est pas directement disponible
                if t_avg is None:
                    # Calcul par la moyenne min et max
                    t_avg = (row['temperature_min'] + row['temperature_max']) / 2.0

                # Extraction de la source réelle de données pour la ligne courante
                valeur_source = row.get('data_source', None)
                # Fallback sur une valeur par défaut cohérente si non spécifiée
                if not valeur_source or pd.isna(valeur_source):
                    # Par défaut la source est open-meteo
                    valeur_source = "open-meteo"

                # Exécution de la requête d'insertion avec gestion du conflit d'unicité
                cursor.execute("""
                    INSERT INTO weather_data (
                        location_id, latitude, longitude, date, hour,
                        temperature_min, temperature_max, temperature_avg,
                        precipitation, humidity, data_type, data_source, confidence, fetched_at
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
                """, (
                    self.location.name, self.location.latitude, self.location.longitude, date_str, -1,
                    row['temperature_min'], row['temperature_max'], t_avg,
                    row['precipitation'], row.get('humidity', 0.0), data_type, str(valeur_source),
                    1.0, now
                ))

            # Détermination de la source principale pour la table de métadonnées
            source_principale = "open-meteo"
            # Inspection des sources uniques présentes dans la colonne data_source
            if "data_source" in data.columns:
                # Extraction des valeurs uniques non nuls
                sources_uniques = [str(s) for s in data["data_source"].dropna().unique() if s]
                # Si au moins une source est présente
                if sources_uniques:
                    # Si plusieurs sources sont mélangées (ex: chirps et open-meteo)
                    if len(sources_uniques) > 1:
                        # Concaténation explicite des sources
                        source_principale = "+".join(sorted(sources_uniques))
                    else:
                        # Utilisation de la source unique
                        source_principale = sources_uniques[0]

            # Mise à jour de la table des métadonnées du cache
            cursor.execute("""
                INSERT INTO cache_metadata (
                    module_name, table_name, data_source, last_fetch, last_success, last_update
                ) VALUES ('weather', 'weather_data', ?, ?, ?, ?)
                ON CONFLICT(module_name, data_source) DO UPDATE SET
                    last_fetch=excluded.last_fetch,
                    last_success=excluded.last_success,
                    last_update=excluded.last_update
            """, (source_principale, now, now, now))

            # Validation définitive des transactions en base
            conn.commit()

    def _fetch_forecast_data(self, days: int = 7) -> pd.DataFrame:
        """
        Récupère les prévisions via l'API Open-Meteo réelle.
        """
        from kadi._sources.open_meteo import fetch_forecast
        from kadi._utils.network import fetch_with_retry
        
        attempts = CONFIG["weather"]["retry_attempts"]
        backoff = CONFIG["weather"]["retry_backoff_sec"]
        
        data_list = fetch_with_retry(
            fetch_forecast, attempts, backoff, 
            lat=self.location.latitude, lon=self.location.longitude, days=days
        )
        
        df = pd.DataFrame(data_list)
        return self._normalize_data(df)

    def _fetch_historical_data(self, days: int = 7, source: str = "both") -> pd.DataFrame:
        """
        Récupère l'historique météo en combinant CHIRPS et/ou Open-Meteo selon le
        paramètre `source`.

        La logique de fusion est la suivante :
        - 'openmeteo' : comportement V1 inchangé, Open-Meteo fournit tout.
        - 'chirps' : CHIRPS fournit les précipitations, Open-Meteo fournit les
          températures. Les deux DataFrames sont fusionnés sur l'index date.
          Un repli automatique sur Open-Meteo est appliqué si CHIRPS échoue,
          avec un message d'avertissement explicite.
        - 'both' : CHIRPS couvre la période historique (1981 à J-lag), Open-Meteo
          complète les dates récentes non encore disponibles dans CHIRPS.
          La colonne data_source reflète la source réelle de chaque ligne.

        :param days: Nombre de jours d'historique à récupérer.
        :param source: Source de précipitation à utiliser.
        :return: DataFrame normalisé avec les données historiques.
        """
        from kadi.exceptions import DataError
        from datetime import date as date_type

        # Calcul des bornes de la plage demandée
        aujourd_hui = datetime.now().date()
        date_debut = aujourd_hui - timedelta(days=days)

        months = max(1, (days + 29) // 30)

        # --- Récupération des températures via Open-Meteo (toujours nécessaire) ---
        from kadi._sources.open_meteo import fetch_historical
        from kadi._utils.network import fetch_with_retry

        attempts = CONFIG["weather"]["retry_attempts"]
        backoff = CONFIG["weather"]["retry_backoff_sec"]

        om_list = fetch_with_retry(
            fetch_historical, attempts, backoff,
            lat=self.location.latitude, lon=self.location.longitude,
            months_back=months
        )
        df_om = pd.DataFrame(om_list)
        df_om = self._normalize_data(df_om)
        # Marquage explicite de la source Open-Meteo pour la précipitation
        df_om["data_source"] = "open-meteo"

        # Mode Open-Meteo uniquement : comportement V1 inchangé
        if source == "openmeteo":
            return df_om

        # --- Récupération des précipitations CHIRPS ---
        from kadi._sources.chirps import fetch_historical_precipitation

        df_chirps = None
        try:
            df_chirps = fetch_historical_precipitation(
                lat=self.location.latitude,
                lon=self.location.longitude,
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
                "Les précipitations proviennent exclusivement d'Open-Meteo "
                "(repli automatique).",
                source,
            )
            return df_om

        # --- Fusion CHIRPS (précipitations) + Open-Meteo (températures) ---
        # Indexation de CHIRPS par date pour la jointure
        df_chirps = df_chirps.set_index("date")
        df_chirps.index = pd.to_datetime(df_chirps.index)

        # Mode 'chirps' : CHIRPS fournit les précipitations, Open-Meteo les températures
        if source == "chirps":
            # Mise à jour de la colonne précipitation dans le DataFrame Open-Meteo
            df_fusion = df_om.copy()
            dates_chirps = df_chirps.index
            masque = df_fusion.index.isin(dates_chirps)
            df_fusion.loc[masque, "precipitation"] = df_chirps.loc[
                df_chirps.index.isin(df_fusion.index), "precipitation"
            ].values
            # Marquage de la source réelle par ligne
            df_fusion["data_source"] = "open-meteo"
            df_fusion.loc[masque, "data_source"] = "chirps"
            return df_fusion

        # Mode 'both' : CHIRPS pour la période couverte, Open-Meteo pour le reste
        # La colonne data_source reflète la source réelle de chaque ligne.
        df_fusion = df_om.copy()
        dates_chirps = df_chirps.index
        masque_chirps = df_fusion.index.isin(dates_chirps)
        df_fusion.loc[masque_chirps, "precipitation"] = df_chirps.loc[
            df_chirps.index.isin(df_fusion.index), "precipitation"
        ].values
        df_fusion.loc[masque_chirps, "data_source"] = "chirps"

        return df_fusion

    def _normalize_data(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """
        Normalise les données brutes retournées par une source météo.

        Applique dans l'ordre :
        1. Conversion de la colonne 'date' en index DatetimeIndex.
        2. Filtrage des valeurs aberrantes (températures hors [-5, 55]°C, pluie négative).
        3. Calcul de la colonne 'data_quality' (ratio de colonnes critiques renseignées).
        4. Interpolation linéaire sur les lacunes courtes (maximum 3 jours consécutifs).
        5. Remplissage résiduel pour la précipitation (0 par défaut) et temperature_mean.

        :param raw_data: DataFrame brut retourné par la source de données.
        :return: DataFrame normalisé avec l'index en date.
        """
        if raw_data.empty:
            return raw_data

        df = raw_data.copy()

        # 1. Conversion et indexation par date
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

        # Tri chronologique avant interpolation
        df = df.sort_index()

        # 2. Filtrage des valeurs aberrantes de température
        for col in ('temperature_min', 'temperature_max'):
            if col in df.columns:
                masque_aberrant = (df[col] < -5.0) | (df[col] > 55.0)
                df.loc[masque_aberrant, col] = np.nan

        # Précipitation négative remise à zéro (impossible physiquement)
        if 'precipitation' in df.columns:
            df.loc[df['precipitation'] < 0.0, 'precipitation'] = 0.0

        # 3. Colonne data_quality : proportion de colonnes critiques renseignées (0 à 1)
        cols_critiques = [c for c in ('temperature_min', 'temperature_max', 'precipitation') if c in df.columns]
        if cols_critiques:
            ratio_manquant = df[cols_critiques].isna().mean(axis=1)
            df['data_quality'] = (1.0 - ratio_manquant).round(2)
        else:
            df['data_quality'] = 1.0

        # 4. Interpolation linéaire pour les lacunes courtes (max 3 jours)
        for col in cols_critiques:
            if df[col].isna().any():
                df[col] = df[col].interpolate(method='linear', limit=3, limit_direction='both')

        # 5. Remplissages résiduels après interpolation
        if 'precipitation' in df.columns:
            # Toute lacune restante en pluie est supposée nulle (pas de pluie = 0 mm)
            df['precipitation'] = df['precipitation'].fillna(0.0)

        # Garantit la présence de temperature_mean (logique centralisée
        # dans _unifier_colonne_temperature pour éviter la duplication).
        df = WeatherData._unifier_colonne_temperature(df)

        return df

