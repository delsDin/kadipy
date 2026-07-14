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

    def fetch_historical(self, months_back: int = 120, force_refresh: bool = False) -> pd.DataFrame:
        """
        Récupère les données historiques en vérifiant d'abord le cache SQLite.
        """
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
            df = self._fetch_historical_data(days=days)
            self._save_to_cache(df, "historical")
        except Exception as e:
            if 'cached_data' in locals() and not cached_data.empty:
                self.historical_data = cached_data
                self.data_source = 'cached_offline'
                return cached_data
            raise OfflineError(f"Impossible de récupérer l'historique météo et aucun cache n'est disponible : {e}")
        
        self.historical_data = df
        self.data_source = 'open-meteo'
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
            
            # Assurer la compatibilité avec les algorithmes (temperature_mean)
            if 'temperature_avg' in df.columns and 'temperature_mean' not in df.columns:
                df['temperature_mean'] = df['temperature_avg']
                
            return df

    def _save_to_cache(self, data: pd.DataFrame, data_type: str) -> None:
        """
        Insère ou met à jour les données météo dans le cache SQLite KadiPy.
        """
        if data.empty:
            return
            
        with get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            for date_idx, row in data.iterrows():
                date_str = date_idx.strftime('%Y-%m-%d')
                
                t_avg = row.get('temperature_mean', row.get('temperature_avg', None))
                if t_avg is None:
                    t_avg = (row['temperature_min'] + row['temperature_max']) / 2.0
                    
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
                    row['precipitation'], row.get('humidity', 0.0), data_type, "mock_api",
                    1.0, now
                ))
            
            # Mise à jour des métadonnées du cache
            cursor.execute("""
                INSERT INTO cache_metadata (
                    module_name, table_name, data_source, last_fetch, last_success, last_update
                ) VALUES ('weather', 'weather_data', ?, ?, ?, ?)
                ON CONFLICT(module_name, data_source) DO UPDATE SET
                    last_fetch=excluded.last_fetch,
                    last_success=excluded.last_success,
                    last_update=excluded.last_update
            """, ("mock_api", now, now, now))
            
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

    def _fetch_historical_data(self, days: int = 7) -> pd.DataFrame:
        """
        Récupère l'historique météo depuis Open-Meteo.

        En V1, CHIRPS est désactivé (données manquantes). Toutes les données
        de précipitation proviennent donc d'Open-Meteo.

        :param days: Nombre de jours d'historique à récupérer.
        :return: DataFrame normalisé avec les données historiques.
        """
        from kadi._sources.open_meteo import fetch_historical
        from kadi._utils.network import fetch_with_retry

        attempts = CONFIG["weather"]["retry_attempts"]
        backoff = CONFIG["weather"]["retry_backoff_sec"]
        months = max(1, (days + 29) // 30)

        # Récupération des données via Open-Meteo (températures et précipitations)
        om_list = fetch_with_retry(
            fetch_historical, attempts, backoff,
            lat=self.location.latitude, lon=self.location.longitude, months_back=months
        )
        df = pd.DataFrame(om_list)
        df = self._normalize_data(df)

        # CHIRPS désactivé pour V1 — les précipitations viennent d'Open-Meteo
        # Réactivation prévue en V2 avec les fichiers NetCDF et le filtrage spatial
        df['data_source'] = 'open-meteo'

        return df

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

        # Calcul de temperature_mean si absente ou incomplète
        if 'temperature_min' in df.columns and 'temperature_max' in df.columns:
            tmean_calc = (df['temperature_min'] + df['temperature_max']) / 2.0
            if 'temperature_mean' not in df.columns:
                df['temperature_mean'] = tmean_calc
            else:
                df['temperature_mean'] = df['temperature_mean'].fillna(tmean_calc)

        # Alias pour la compatibilité cache (temperature_avg = temperature_mean)
        if 'temperature_avg' in df.columns and 'temperature_mean' not in df.columns:
            df['temperature_mean'] = df['temperature_avg']

        return df

