"""
Module phenology.py

Analyse phénologique : détection du début (onset) et de la fin (cessation)
de la saison agricole, calcul des degrés-jours de croissance (GDD).
"""

import warnings

from typing import Optional, Union
import numpy as np
import pandas as pd
from datetime import datetime

from kadi.exceptions import DataError, CropError
from .location import Location

class Phenology:
    """
    Gère l'analyse phénologique (onset, cessation, GDD) pour une localisation.

    Attributs:
        location (Location): Localisation de l'analyse.
        rainfall (pd.Series): Série de précipitations quotidiennes.
        temperature (pd.DataFrame): DataFrame avec temperature_min et
            temperature_max.
        onset (pd.Timestamp): Date d'onset calculée (None avant le premier appel).
        crop (dict): Paramètres culturaux par défaut.
    """

    def __init__(
        self,
        location: Location,
        rainfall_data: pd.Series,
        temperature_data: pd.DataFrame,
    ):
        """
        Initialise l'analyseur phénologique.

        Args:
            location (Location): Instance de Location.
            rainfall_data (pd.Series): Série de précipitations quotidiennes.
            temperature_data (pd.DataFrame): DataFrame avec les colonnes
                'temperature_min' et 'temperature_max'.
        """
        self.location = location
        # Nouveaux noms d'attributs
        self.rainfall = rainfall_data
        self.temperature = temperature_data
        # Date d'onset calculée (None avant le premier appel à onset())
        # Nom onset_ts pour éviter le conflit avec la méthode onset()
        self.onset_ts: Optional[pd.Timestamp] = None

        # Paramètres culturaux par défaut (Kc, base thermique, total GDD)
        self.crop = {
            "maize":   {"base_temp": 10, "gdd_total": 1300},
            "rice":    {"base_temp": 10, "gdd_total": 1500},
            "manioc":  {"base_temp": 14, "gdd_total": 3000},
            "sorghum": {"base_temp": 10, "gdd_total": 1400},
            "tomato":  {"base_temp": 10, "gdd_total": 1000},
        }

    def onset(self, threshold: int = 120) -> dict:
        """
        Détecte la date de démarrage de la saison agricole.

        Pour le Nord (unimodal), utilise l'algorithme de Sivakumar.
        Pour le Sud et le Centre (bimodal), utilise l'hybride Walter-Anyadike
        sur deux fenêtres saisonnières (S1 : Jan-Juil, S2 : Aoùt-Déc).

        La clé 'onset_date' est maintenue comme alias de 'onset_1' pour
        la rétrocompatibilité.

        Args:
            threshold (int): Fenêtre de calcul (conservé pour la signature).

        Returns:
            dict: Dictionnaire contenant les informations de l'onset.

        Raises:
            DataError: Si aucune donnée de précipitation n'est disponible.
        """
        if self.rainfall.empty:
            raise DataError(
                "Impossible de calculer l'onset : aucune donnée de précipitation "
                "disponible."
            )

        # Utilise l'année du dernier enregistrement disponible
        current_year = self.rainfall.index[-1].year

        if self.location.zone == "Nord":
            # Zone Nord : régime unimodal, Sivakumar (recherche à partir de mai)
            search_start = f"{current_year}-05-01"
            date_s1 = self._sivakumar(search_start)
            algorithm = "Sivakumar"

            onset_1_str = date_s1.strftime("%Y-%m-%d") if date_s1 else None
            if date_s1:
                self.onset_ts = date_s1

            return {
                "onset_date": onset_1_str,   # Alias de rétrocompatibilité
                "onset_1": onset_1_str,
                "onset_2": None,             # Pas de S2 en zone Nord
                "algorithm": algorithm,
                "zone": self.location.zone,
                "confidence": 0.85,
            }
        else:
            # Zones Sud et Centre : régime bimodal
            annual_precip = self.rainfall.loc[str(current_year)].sum()

            date_s1 = self._walter_anyadike_bimodal(current_year, season="S1")
            date_s2 = self._walter_anyadike_bimodal(current_year, season="S2")
            algorithm = "Walter-Anyadike bimodal"

            onset_1_str = date_s1.strftime("%Y-%m-%d") if date_s1 else None
            onset_2_str = date_s2.strftime("%Y-%m-%d") if date_s2 else None

            # La date principale est celle de la S1 (première saison)
            if date_s1:
                self.onset_ts = date_s1

            return {
                "onset_date": onset_1_str,   # Alias de rétrocompatibilité
                "onset_1": onset_1_str,
                "onset_2": onset_2_str,
                "algorithm": algorithm,
                "zone": self.location.zone,
                "confidence": 0.80,
            }

    def cessation(self) -> dict:
        """
        Détermine la date de fin des pluies utiles.

        Pour le Nord (unimodal), calcule une unique date de cessation après août.
        Pour le Sud et le Centre (bimodal), calcule deux dates de cessation :
        - cessation_1 : fin de la première saison (autour de juillet)
        - cessation_2 : fin de la deuxième saison (autour de novembre)

        Returns:
            dict: Dictionnaire avec la ou les dates de cessation.

        Raises:
            DataError: Si aucune donnée de précipitation n'est disponible.
        """
        if self.rainfall.empty:
            raise DataError(
                "Impossible de calculer la cessation : aucune donnée de "
                "précipitation disponible."
            )

        years = sorted(list(set(self.rainfall.index.year)), reverse=True)

        if self.location.zone == "Nord":
            # Zone Nord : cessation unique après août
            for year in years:
                year_data = self.rainfall.loc[str(year)]
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
                        "cessation_date": cessation_date.strftime("%Y-%m-%d"),
                        "cessation_1":    cessation_date.strftime("%Y-%m-%d"),
                        "cessation_2":    None,
                        "duration_days":  duration,
                        "total_rainfall": float(year_data.sum()),
                        "zone":           self.location.zone,
                    }
        else:
            # Zones Sud et Centre : deux cessations (S1 et S2)
            for year in years:
                year_data = self.rainfall.loc[str(year)]

                # Cessation S1 : fin de la première saison (mars-juillet)
                cess_1 = self._cessation_in_window(
                    year_data, f"{year}-05-01", f"{year}-07-31"
                )
                # Cessation S2 : fin de la deuxième saison (sept-décembre)
                cess_2 = self._cessation_in_window(
                    year_data, f"{year}-10-01", f"{year}-12-15"
                )

                if cess_1 or cess_2:
                    cess_1_str = cess_1.strftime("%Y-%m-%d") if cess_1 else None
                    cess_2_str = cess_2.strftime("%Y-%m-%d") if cess_2 else None
                    return {
                        "cessation_date": cess_1_str,  # Alias rétrocompatibilité
                        "cessation_1":    cess_1_str,
                        "cessation_2":    cess_2_str,
                        "duration_days":  0,
                        "total_rainfall": float(year_data.sum()),
                        "zone":           self.location.zone,
                    }

        # Aucune cessation trouvée
        return {
            "cessation_date": None,
            "cessation_1":    None,
            "cessation_2":    None,
            "duration_days":  0,
            "total_rainfall": (
                float(self.rainfall.sum())
                if not self.rainfall.empty
                else 0.0
            ),
            "zone": self.location.zone,
        }

    def gdd(
        self,
        crop: str,
        start: Union[str, pd.Timestamp],
        end: Union[str, pd.Timestamp] = None,
    ) -> dict:
        """
        Calcule l'accumulation des degrés-jours de croissance (GDD) pour une
        culture donnée.

        Args:
            crop (str): Nom de la culture ('maize', 'rice', etc.).
            start (str or pd.Timestamp): Date de début (semis).
            end (str or pd.Timestamp): Date de fin (défaut : aujourd'hui).

        Returns:
            dict: Dictionnaire avec le cumul GDD, le stade phenologique et le
                pourcentage du cycle accompli.

        Raises:
            CropError: Si la culture n'est pas reconnue.
            DataError: Si les données de température sont insuffisantes.
        """
        if end is None:
            end = pd.Timestamp.now()

        start_ts = pd.to_datetime(start)
        end_ts = pd.to_datetime(end)

        if crop.lower() not in self.crop:
            raise CropError(f"Culture non reconnue pour le calcul des GDD : {crop}")

        params = self.crop.get(crop.lower())
        tbase = params["base_temp"]
        gdd_req = params["gdd_total"]

        # Extraction de la période demandée
        period = self.temperature.loc[start_ts:end_ts]
        if period.empty:
            raise DataError(
                "Pas assez de données de température pour la période de "
                "calcul des degrés-jours."
            )

        # Calcul GDD journalier : (Tmax + Tmin) / 2 - Tbase
        tmean = (period["temperature_max"] + period["temperature_min"]) / 2.0
        daily_gdd = tmean - tbase
        # GDD ne peut pas être négatif
        daily_gdd[daily_gdd < 0] = 0

        gdd_accumulated = float(daily_gdd.sum())
        pct_cycle = min(100, int((gdd_accumulated / gdd_req) * 100))

        # Détermination empirique du stade phenologique
        stage = "vegetative"
        if pct_cycle > 90:
            stage = "maturity"
        elif pct_cycle > 60:
            stage = "tasseling/flowering"

        return {
            "gdd_accumulated":  round(gdd_accumulated, 1),
            "crop":             crop,
            "gdd_total_cycle":  gdd_req,
            "pct_cycle":        pct_cycle,
            "phenology_stage":  stage,
        }

    def growing_degree_days(
        self,
        crop: str,
        start_date: Union[str, pd.Timestamp],
        end_date: Union[str, pd.Timestamp] = None,
    ) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.1.0.

        Utilisez ``gdd(crop, start, end)`` à la place.

        Args:
            crop (str): Nom de la culture.
            start_date (str or pd.Timestamp): Ancien nom de ``start``.
            end_date (str or pd.Timestamp): Ancien nom de ``end``.

        Returns:
            dict: Résultat du calcul des degrés-jours de croissance.
        """
        warnings.warn(
            "Phenology.growing_degree_days() est obsolète et sera supprimé "
            "dans KadiPy v2.0. Utilisez gdd() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.gdd(crop=crop, start=start_date, end=end_date)

    def _sivakumar(
        self,
        search_start_date: str,
        trigger_days: int = 3,
        trigger_amount: float = 20.0,
        dry_spell_window: int = 30,
        max_dry_spell: int = 7,
    ) -> Optional[pd.Timestamp]:
        """
        Détermine la date d'onset selon le critère de Sivakumar (Nord Bénin).

        Args:
            search_start_date (str): Date de début de recherche (YYYY-MM-DD).
            trigger_days (int): Nombre de jours consécutifs pour le déclencheur.
            trigger_amount (float): Cumul de pluie déclencheur en mm.
            dry_spell_window (int): Fenêtre de vérification des périodes sèches.
            max_dry_spell (int): Nombre maximum de jours secs consécutifs autorisé.

        Returns:
            pd.Timestamp: Date d'onset estimée, ou None si non détectée.
        """
        try:
            series = self.rainfall.loc[search_start_date:]
        except KeyError:
            return None

        if len(series) < dry_spell_window + trigger_days:
            return None

        for i in range(len(series) - dry_spell_window - trigger_days):
            trigger_sub = series.iloc[i: i + trigger_days]
            if trigger_sub.sum() >= trigger_amount:
                potential_onset = trigger_sub.index[0]
                post_window = series.iloc[
                    i + trigger_days: i + trigger_days + dry_spell_window
                ]

                is_dry = (post_window < 1.0).astype(int)
                dry_runs = is_dry.rolling(window=max_dry_spell + 1).sum()

                if dry_runs.max() <= max_dry_spell:
                    return potential_onset
        return None

    def _walter_anyadike(self, year: int, annual_precipitation: float) -> Optional[pd.Timestamp]:
        """
        Calcule l'onset hybride Walter-Anyadike pour le Sud/Centre Bénin.

        Args:
            year (int): Année cible.
            annual_precipitation (float): Cumul annuel de précipitations en mm.

        Returns:
            pd.Timestamp: Date d'onset estimée, ou None si non détectée.
        """
        try:
            year_data = self.rainfall.loc[str(year)]
            # Correction pour pandas récent (utilisation de 'ME' au lieu de 'M')
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
            season_data = self.rainfall.loc[start_date:end_date]
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

    # ----------------------------------------------------------------
    # Propriétés de rétrocompatibilité (anciens noms d'attributs)
    # ----------------------------------------------------------------

    @property
    def rainfall_data(self) -> pd.Series:
        """Ancien nom de ``rainfall``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.rainfall_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.rainfall à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.rainfall

    @rainfall_data.setter
    def rainfall_data(self, value: pd.Series) -> None:
        """Ancien setter de ``rainfall``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.rainfall_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.rainfall à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.rainfall = value

    @property
    def temperature_data(self) -> pd.DataFrame:
        """Ancien nom de ``temperature``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.temperature_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.temperature à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.temperature

    @temperature_data.setter
    def temperature_data(self, value: pd.DataFrame) -> None:
        """Ancien setter de ``temperature``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.temperature_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.temperature à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.temperature = value

    @property
    def onset_date(self) -> Optional[pd.Timestamp]:
        """Ancien nom de ``onset_ts``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.onset_date est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.onset_ts à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.onset_ts

    @onset_date.setter
    def onset_date(self, value: Optional[pd.Timestamp]) -> None:
        """Ancien setter de ``onset_ts``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.onset_date est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.onset_ts à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.onset_ts = value

    @property
    def crop_params(self) -> dict:
        """Ancien nom de ``crop``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.crop_params est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.crop à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.crop

    @crop_params.setter
    def crop_params(self, value: dict) -> None:
        """Ancien setter de ``crop``. Déprécié depuis v1.1.0."""
        warnings.warn(
            "Phenology.crop_params est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Phenology.crop à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.crop = value
