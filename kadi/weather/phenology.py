"""
Module phenology.py

Analyse phénologique : détection du début (onset) et de la fin (cessation)
de la saison agricole, calcul des degrés-jours de croissance (GDD).
"""

from typing import Optional, Union
import numpy as np
import pandas as pd
from datetime import datetime

from kadi.exceptions import InsufficientData, CropNotFound
from .location import Location

class Phenology:
    """
    Gère l'analyse phénologique (onset, cessation, GDD) pour une localisation donnée.
    """

    def __init__(self, location: Location, rainfall_data: pd.Series, temperature_data: pd.DataFrame):
        """
        Initialise l'analyseur phénologique.

        :param location: Instance de Location.
        :param rainfall_data: Série pandas de précipitations quotidiennes.
        :param temperature_data: DataFrame avec les colonnes 'temperature_min' et 'temperature_max'.
        """
        self.location = location
        self.rainfall_data = rainfall_data
        self.temperature_data = temperature_data
        self.onset_date: Optional[pd.Timestamp] = None
        
        # Paramètres culturaux par défaut
        self.crop_params = {
            'maize': {'base_temp': 10, 'gdd_total': 1300},
            'rice': {'base_temp': 10, 'gdd_total': 1500},
            'manioc': {'base_temp': 14, 'gdd_total': 3000},
            'sorghum': {'base_temp': 10, 'gdd_total': 1400},
            'tomato': {'base_temp': 10, 'gdd_total': 1000}
        }

    def onset(self, threshold_days_after: int = 120) -> dict:
        """
        Détecte la date de démarrage de la saison agricole.
        Utilise l'algorithme approprié selon la zone (Sivakumar pour le Nord,
        Walter-Anyadike hybride pour le Sud/Centre).

        :param threshold_days_after: Fenêtre de calcul.
        :return: Dictionnaire contenant les informations de l'onset.
        """
        current_year = pd.Timestamp.now().year
        if self.rainfall_data.empty:
            raise InsufficientData("Impossible de calculer l'onset : aucune donnée de précipitation disponible.")
            
        current_year = self.rainfall_data.index[-1].year

        if self.location.zone == 'Nord':
            # Nord : Unimodal, on utilise Sivakumar
            # Recherche généralement à partir de Mai
            search_start = f"{current_year}-05-01"
            date = self._sivakumar(search_start)
            algorithm = 'Sivakumar'
        else:
            # Sud et Centre : bimodal/transition, Walter-Anyadike
            annual_precipitation = self.rainfall_data.loc[str(current_year)].sum()
            date = self._walter_anyadike(current_year, annual_precipitation)
            algorithm = 'Walter-Anyadike hybride'

        if date:
            self.onset_date = date
            return {
                'onset_date': date.strftime('%Y-%m-%d'),
                'confidence': 0.85, # Valeur fixe simplifiée pour le MVP
                'algorithm': algorithm,
                'zone': self.location.zone,
                'earliest_possible': f"{current_year}-04-01",
                'latest_possible': f"{current_year}-07-31"
            }
        else:
            return {
                'onset_date': None,
                'confidence': 0.0,
                'algorithm': algorithm,
                'zone': self.location.zone
            }

    def cessation(self) -> dict:
        """
        Détermine la date de fin des pluies utiles.
        Critère simplifié : Dernier jour après septembre où le cumul restant < 20 mm.

        :return: Dictionnaire contenant la date de cessation.
        """
        if self.rainfall_data.empty:
            raise InsufficientData("Impossible de calculer la cessation : aucune donnée de précipitation disponible.")
            
        # Logique simplifiée pour la cessation
        # On parcourt les années disponibles de la plus récente à la plus ancienne
        years = sorted(list(set(self.rainfall_data.index.year)), reverse=True)
        
        for year in years:
            year_data = self.rainfall_data.loc[str(year)]
            
            # Filtre de la période potentielle de cessation (après août)
            try:
                late_year = year_data.loc[f"{year}-09-01":]
            except KeyError:
                continue
                
            if late_year.empty:
                continue
            
            # Cumul à l'envers
            reversed_cum = late_year[::-1].cumsum()
            
            # Trouve le jour où le cumul restant devient >= 20 mm, le jour précédent est la cessation
            valid_dates = reversed_cum[reversed_cum >= 20.0].index
            
            if len(valid_dates) > 0:
                cessation_date = valid_dates.max()
                cessation_str = cessation_date.strftime('%Y-%m-%d')
                
                duration = 0
                if self.onset_date and self.onset_date.year == year:
                    duration = (cessation_date - self.onset_date).days
                    
                return {
                    'cessation_date': cessation_str,
                    'duration_days': duration,
                    'total_rainfall': float(year_data.sum()),
                    'zone': self.location.zone
                }
                
        # Si on n'a trouvé aucune cessation valide
        return {
            'cessation_date': None,
            'duration_days': 0,
            'total_rainfall': float(self.rainfall_data.sum()) if not self.rainfall_data.empty else 0.0,
            'zone': self.location.zone
        }

    def growing_degree_days(self, crop: str, start_date: Union[str, pd.Timestamp], end_date: Union[str, pd.Timestamp] = None) -> dict:
        """
        Calcule l'accumulation des degrés-jours pour une culture.

        :param crop: Nom de la culture ('maize', 'rice', etc.).
        :param start_date: Date de début (semis).
        :param end_date: Date de fin (défaut: aujourd'hui).
        :return: Dictionnaire avec le cumul et le stade.
        """
        if end_date is None:
            end_date = pd.Timestamp.now()
            
        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date)
        
        if crop.lower() not in self.crop_params:
            raise CropNotFound(f"Culture non reconnue pour le calcul des GDD : {crop}")
            
        params = self.crop_params.get(crop.lower())
        tbase = params['base_temp']
        gdd_req = params['gdd_total']
        
        # Extrait la période
        period = self.temperature_data.loc[start_ts:end_ts]
        if period.empty:
            raise InsufficientData("Pas assez de données de température pour la période de calcul des degrés-jours.")
            
        # Calcul GDD journalier
        tmean = (period['temperature_max'] + period['temperature_min']) / 2.0
        daily_gdd = tmean - tbase
        # GDD ne peut pas être négatif
        daily_gdd[daily_gdd < 0] = 0
        
        gdd_accumulated = float(daily_gdd.sum())
        pct_cycle = min(100, int((gdd_accumulated / gdd_req) * 100))
        
        # Détermination empirique du stade (exemple maïs)
        stage = 'vegetative'
        if pct_cycle > 90:
            stage = 'maturity'
        elif pct_cycle > 60:
            stage = 'tasseling/flowering'
            
        return {
            'gdd_accumulated': round(gdd_accumulated, 1),
            'crop': crop,
            'gdd_total_cycle': gdd_req,
            'pct_cycle': pct_cycle,
            'phenology_stage': stage
        }

    def _sivakumar(self, search_start_date: str, trigger_days: int = 3, trigger_amount: float = 20.0, dry_spell_window: int = 30, max_dry_spell: int = 7) -> Optional[pd.Timestamp]:
        """
        Détermine la date d'onset d'après le critère de Sivakumar (Nord Bénin).
        """
        try:
            series = self.rainfall_data.loc[search_start_date:]
        except KeyError:
            return None

        if len(series) < dry_spell_window + trigger_days:
            return None

        for i in range(len(series) - dry_spell_window - trigger_days):
            trigger_sub = series.iloc[i : i + trigger_days]
            if trigger_sub.sum() >= trigger_amount:
                potential_onset = trigger_sub.index[0]
                post_window = series.iloc[i + trigger_days : i + trigger_days + dry_spell_window]
                
                is_dry = (post_window < 1.0).astype(int)
                dry_runs = is_dry.rolling(window=max_dry_spell + 1).sum()
                
                if dry_runs.max() <= max_dry_spell:
                    return potential_onset
        return None

    def _walter_anyadike(self, year: int, annual_precipitation: float) -> Optional[pd.Timestamp]:
        """
        Calcule l'onset hybride pour le Sud/Centre Bénin.
        """
        try:
            year_data = self.rainfall_data.loc[str(year)]
            # Correction pour pandas récent (utilisation de 'ME' ou 'M')
            monthly = year_data.resample("ME").sum()
        except Exception:
            return None

        # Walter
        walter_date = None
        accum_prior = 0.0
        for month_date, month_precip in monthly.items():
            if month_precip >= 50.8:
                days_in_m = month_date.days_in_month
                offset = days_in_m * ((50.8 - accum_prior) / month_precip) if month_precip > 0 else days_in_m
                offset = np.clip(offset, 1, days_in_m)
                walter_date = pd.Timestamp(year=year, month=month_date.month, day=int(offset))
                break
            accum_prior += month_precip

        # Anyadike
        anyadike_date = None
        target = annual_precipitation * 0.083
        accum_anya = 0.0
        for month_date, month_precip in monthly.items():
            if month_precip >= target:
                days_in_m = month_date.days_in_month
                offset = days_in_m * ((target - accum_anya) / month_precip) if month_precip > 0 else days_in_m
                offset = np.clip(offset, 1, days_in_m)
                anyadike_date = pd.Timestamp(year=year, month=month_date.month, day=int(offset))
                break
            accum_anya += month_precip

        # Hybride (Moyenne)
        if walter_date and anyadike_date:
            doy_w = walter_date.dayofyear
            doy_a = anyadike_date.dayofyear
            mean_doy = int((doy_w + doy_a) / 2)
            return pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=mean_doy - 1)

        return walter_date or anyadike_date
