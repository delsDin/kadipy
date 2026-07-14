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

        Pour le Nord (unimodal), utilise l'algorithme de Sivakumar.
        Pour le Sud et le Centre (bimodal), utilise l'hybride Walter-Anyadike
        sur deux fenêtres saisonnières distinctes (S1 : Jan-Août, S2 : Août-Déc).

        La clé 'onset_date' est maintenue comme alias de 'onset_1' pour
        la rétrocompatibilité.

        :param threshold_days_after: Fenêtre de calcul (non utilisé directement, conservé pour la signature).
        :return: Dictionnaire contenant les informations de l'onset.
        """
        if self.rainfall_data.empty:
            raise InsufficientData("Impossible de calculer l'onset : aucune donnée de précipitation disponible.")

        # Utilise l'année du dernier enregistrement disponible
        current_year = self.rainfall_data.index[-1].year

        if self.location.zone == 'Nord':
            # Zone Nord : régime unimodal, algorithme de Sivakumar (recherche à partir de mai)
            search_start = f"{current_year}-05-01"
            date_s1 = self._sivakumar(search_start)
            algorithm = 'Sivakumar'

            onset_1_str = date_s1.strftime('%Y-%m-%d') if date_s1 else None
            if date_s1:
                self.onset_date = date_s1

            return {
                'onset_date': onset_1_str,   # Alias de rétrocompatibilité
                'onset_1': onset_1_str,
                'onset_2': None,             # Pas de S2 en zone Nord
                'algorithm': algorithm,
                'zone': self.location.zone,
                'confidence': 0.85,
            }
        else:
            # Zones Sud et Centre : régime bimodal
            # S1 : première saison (janvier à fin juillet)
            # S2 : deuxième saison (août à décembre)
            annual_precip = self.rainfall_data.loc[str(current_year)].sum()

            date_s1 = self._walter_anyadike_bimodal(
                current_year, season='S1'
            )
            date_s2 = self._walter_anyadike_bimodal(
                current_year, season='S2'
            )
            algorithm = 'Walter-Anyadike bimodal'

            onset_1_str = date_s1.strftime('%Y-%m-%d') if date_s1 else None
            onset_2_str = date_s2.strftime('%Y-%m-%d') if date_s2 else None

            # La date principale est celle de la S1 (première saison)
            if date_s1:
                self.onset_date = date_s1

            return {
                'onset_date': onset_1_str,   # Alias de rétrocompatibilité
                'onset_1': onset_1_str,
                'onset_2': onset_2_str,
                'algorithm': algorithm,
                'zone': self.location.zone,
                'confidence': 0.80,
            }

    def cessation(self) -> dict:
        """
        Détermine la date de fin des pluies utiles.

        Pour le Nord (unimodal), calcule une unique date de cessation après août.
        Pour le Sud et le Centre (bimodal), calcule deux dates de cessation :
        - cessation_1 : fin de la première saison (autour de juillet)
        - cessation_2 : fin de la deuxième saison (autour de novembre)

        :return: Dictionnaire avec la ou les dates de cessation.
        """
        if self.rainfall_data.empty:
            raise InsufficientData("Impossible de calculer la cessation : aucune donnée de précipitation disponible.")

        years = sorted(list(set(self.rainfall_data.index.year)), reverse=True)

        if self.location.zone == 'Nord':
            # Zone Nord : cessation unique après août
            for year in years:
                year_data = self.rainfall_data.loc[str(year)]
                try:
                    late_year = year_data.loc[f"{year}-09-01":]
                except KeyError:
                    continue
                if late_year.empty:
                    continue

                reversed_cum = late_year[::-1].cumsum()
                valid_dates = reversed_cum[reversed_cum >= 20.0].index
                if len(valid_dates) > 0:
                    cessation_date = valid_dates.max()
                    year_onset = self._sivakumar(f"{year}-05-01")
                    duration = (cessation_date - year_onset).days if year_onset else 0
                    return {
                        'cessation_date': cessation_date.strftime('%Y-%m-%d'),
                        'cessation_1': cessation_date.strftime('%Y-%m-%d'),
                        'cessation_2': None,
                        'duration_days': duration,
                        'total_rainfall': float(year_data.sum()),
                        'zone': self.location.zone
                    }
        else:
            # Zones Sud et Centre : deux cessations (S1 et S2)
            for year in years:
                year_data = self.rainfall_data.loc[str(year)]

                # Cessation S1 : fin de la première saison (mars-juillet)
                cess_1 = self._cessation_in_window(year_data, f"{year}-05-01", f"{year}-07-31")
                # Cessation S2 : fin de la deuxième saison (sept-décembre)
                cess_2 = self._cessation_in_window(year_data, f"{year}-10-01", f"{year}-12-15")

                if cess_1 or cess_2:
                    cess_1_str = cess_1.strftime('%Y-%m-%d') if cess_1 else None
                    cess_2_str = cess_2.strftime('%Y-%m-%d') if cess_2 else None
                    return {
                        'cessation_date': cess_1_str,    # Alias rétrocompatibilité
                        'cessation_1': cess_1_str,
                        'cessation_2': cess_2_str,
                        'duration_days': 0,              # Calculé séparément si besoin
                        'total_rainfall': float(year_data.sum()),
                        'zone': self.location.zone
                    }

        # Aucune cessation trouvée
        return {
            'cessation_date': None,
            'cessation_1': None,
            'cessation_2': None,
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

    def _walter_anyadike_bimodal(self, year: int, season: str) -> Optional[pd.Timestamp]:
        """
        Applique la méthode hybride Walter-Anyadike sur une fenêtre saisonnière restreinte.

        Pour la phénologie bimodale (Sud et Centre), on découpe l'année en deux
        sous-périodes avant d'appliquer l'algorithme :
        - S1 : 1er janvier au 31 juillet (première saison des pluies)
        - S2 : 1er août au 31 décembre (deuxième saison des pluies)

        :param year: Année cible pour le calcul.
        :param season: 'S1' (première saison) ou 'S2' (deuxième saison).
        :return: Timestamp de la date d'onset estimée, ou None si non détectée.
        """
        # Définition des fenêtres temporelles pour chaque saison
        if season == 'S1':
            start_date = f"{year}-01-01"
            end_date = f"{year}-07-31"
        elif season == 'S2':
            start_date = f"{year}-08-01"
            end_date = f"{year}-12-31"
        else:
            return None

        try:
            # Extraction de la sous-période
            season_data = self.rainfall_data.loc[start_date:end_date]
            if season_data.empty:
                return None

            # Ré-échantillonnage mensuel de la sous-période
            monthly = season_data.resample("ME").sum()
        except Exception:
            return None

        # Total de précipitation sur la sous-période
        season_total = float(season_data.sum())
        if season_total <= 0:
            return None

        # Critère Walter : premier mois où le cumul mensuel dépasse 50.8 mm
        walter_date = None
        accum_prior = 0.0
        for month_end, month_precip in monthly.items():
            if month_precip >= 50.8:
                days_in_m = month_end.days_in_month
                offset = days_in_m * ((50.8 - accum_prior) / month_precip) if month_precip > 0 else days_in_m
                offset = int(np.clip(offset, 1, days_in_m))
                walter_date = pd.Timestamp(year=year, month=month_end.month, day=offset)
                break
            accum_prior += month_precip

        # Critère Anyadike : premier mois où le cumul dépasse 8.3 % du total saisonnier
        anyadike_date = None
        target = season_total * 0.083
        accum_anya = 0.0
        for month_end, month_precip in monthly.items():
            if month_precip >= target:
                days_in_m = month_end.days_in_month
                offset = days_in_m * ((target - accum_anya) / month_precip) if month_precip > 0 else days_in_m
                offset = int(np.clip(offset, 1, days_in_m))
                anyadike_date = pd.Timestamp(year=year, month=month_end.month, day=offset)
                break
            accum_anya += month_precip

        # Moyenne des deux critères (hybride)
        if walter_date and anyadike_date:
            doy_w = walter_date.dayofyear
            doy_a = anyadike_date.dayofyear
            mean_doy = int((doy_w + doy_a) / 2)
            return pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=mean_doy - 1)

        return walter_date or anyadike_date

    def _cessation_in_window(
        self,
        year_data: pd.Series,
        start_date: str,
        end_date: str,
        threshold_mm: float = 20.0
    ) -> Optional[pd.Timestamp]:
        """
        Détecte la date de cessation des pluies utiles dans une fenêtre temporelle donnée.

        La cessation est définie comme le dernier jour à partir duquel le cumul
        restant de pluie (calculé en sens inverse) passe sous le seuil de 20 mm.

        :param year_data: Série de précipitations pour l'année entière.
        :param start_date: Début de la fenêtre de recherche (format 'YYYY-MM-DD').
        :param end_date: Fin de la fenêtre de recherche (format 'YYYY-MM-DD').
        :param threshold_mm: Seuil de cumul en mm pour définir la cessation.
        :return: Timestamp de la date de cessation, ou None si non détectée.
        """
        try:
            # Extraction de la fenêtre temporelle
            window_data = year_data.loc[start_date:end_date]
        except KeyError:
            return None

        if window_data.empty:
            return None

        # Cumul cumulatif en sens inverse (du dernier au premier jour)
        reversed_cum = window_data[::-1].cumsum()

        # Le dernier jour où le cumul restant est encore >= threshold_mm
        valid_dates = reversed_cum[reversed_cum >= threshold_mm].index
        if len(valid_dates) > 0:
            return valid_dates.max()

        return None
