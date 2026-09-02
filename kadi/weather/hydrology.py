"""
Module hydrology.py

Hydrologie et bilan hydrique : calcul de l'évapotranspiration de référence (ET0),
ruissellement et réserve utile du sol selon FAO-56.
"""

import numpy as np
import pandas as pd
from typing import Optional

from kadi.exceptions import DataError, CropError, ValidationError
from .location import Location

class Hydrology:
    """
    Gère la modélisation hydrologique (bilan hydrique du sol) pour une parcelle.
    """

    def __init__(self, location: Location, rainfall_data: pd.Series, temperature_data: pd.DataFrame, soil_type: Optional[str] = None, crop: str = 'maize'):
        """
        Initialise l'analyseur hydrologique.

        :param location: Instance de Location.
        :param rainfall_data: Série pandas de précipitations quotidiennes.
        :param temperature_data: DataFrame avec les colonnes 'temperature_min' et 'temperature_max'.
        :param soil_type: Type de sol ('ferrugineux', 'ferrallitique', 'sableux', 'limoneux').
        :param crop: Type de culture.
        """
        self.location = location
        self.rainfall_data = rainfall_data
        self.temperature_data = temperature_data
        self.crop = crop
        self.soil_type = soil_type or self._resolve_soil_type_from_cache(location)
        self.balance_result: Optional[pd.DataFrame] = None
        
        self.soil_params = self.get_soil_params(self.soil_type)

    def _resolve_soil_type_from_cache(self, location: Location) -> str:
        """Détermine le type de sol depuis le cache local pré-téléchargé."""
        from kadi._sources.soilgrids import fetch_soil_type
        return fetch_soil_type(location.latitude, location.longitude)

    def et0_hargreaves(self, tmin, tmax, day_of_year) -> float:
        """
        Calcule l'évapotranspiration de référence (ETo) par Hargreaves-Samani.

        Méthode alternative à Penman-Monteith, utilisée en l'absence de données
        d'humidité, de vent et de rayonnement solaire.

        :param tmin: Température minimale (°C).
        :param tmax: Température maximale (°C).
        :param day_of_year: Jour de l'année (1-365).
        :return: ETo en mm/jour.
        """
        # 1. Calcul du rayonnement extraterrestre Ra
        lat_rad = np.radians(self.location.latitude)
        dr = 1 + 0.033 * np.cos(2 * np.pi * day_of_year / 365.0)
        delta = 0.409 * np.sin(2 * np.pi * day_of_year / 365.0 - 1.39)

        cos_omega_s = -np.tan(lat_rad) * np.tan(delta)
        cos_omega_s = np.clip(cos_omega_s, -1.0, 1.0)
        omega_s = np.arccos(cos_omega_s)

        # Constante solaire (MJ/m2/min)
        gsc = 0.0820
        ra = (24 * 60 / np.pi) * gsc * dr * (
            omega_s * np.sin(lat_rad) * np.sin(delta)
            + np.cos(lat_rad) * np.cos(delta) * np.sin(omega_s)
        )

        # 2. Formule Hargreaves-Samani
        tmean = (tmax + tmin) / 2.0
        tdiff = np.maximum(0.0, tmax - tmin) if isinstance(tmax, np.ndarray) else max(0.0, tmax - tmin)
        k_rs = 0.0023

        eto = 0.408 * k_rs * ra * (tmean + 17.8) * (tdiff ** 0.5)
        if isinstance(eto, np.ndarray):
            return np.maximum(0.0, eto)
        return float(max(0.0, eto))

    def et0_fao56_penman(
        self,
        tmin: float,
        tmax: float,
        humidity: float,
        wind_speed: float,
        solar_rad: float,
    ) -> float:
        """
        Calcule l'évapotranspiration de référence (ETo) par FAO-56 Penman-Monteith.

        Méthode de référence internationale (Allen et al., 1998, FAO-56).
        Plus précise que Hargreaves car elle intègre l'humidité relative,
        la vitesse du vent et le rayonnement solaire mesuré.

        :param tmin: Température minimale (°C).
        :param tmax: Température maximale (°C).
        :param humidity: Humidité relative moyenne (%, entre 0 et 100).
        :param wind_speed: Vitesse du vent mesurée à 2 m de hauteur (m/s).
        :param solar_rad: Rayonnement solaire incident (MJ/m²/jour).
        :return: ETo en mm/jour.
        """
        # Altitude moyenne estimée au Bénin (m) — utilisée pour la pression atmosphérique
        z = 200.0
        tmean = (tmax + tmin) / 2.0

        # Pression atmosphérique (kPa) selon l'équation standard (FAO-56 Eq. 7)
        p_atm = 101.3 * ((293.0 - 0.0065 * z) / 293.0) ** 5.26

        # Constante psychrométrique gamma (kPa/°C) (FAO-56 Eq. 8)
        gamma = 0.000665 * p_atm

        # Pente de la courbe de pression de vapeur saturante (kPa/°C) (FAO-56 Eq. 13)
        delta = 4098.0 * (0.6108 * np.exp(17.27 * tmean / (tmean + 237.3))) / (tmean + 237.3) ** 2

        # Pression de vapeur saturante (kPa) : moyenne sur Tmin et Tmax (FAO-56 Eq. 11-12)
        es_tmax = 0.6108 * np.exp(17.27 * tmax / (tmax + 237.3))
        es_tmin = 0.6108 * np.exp(17.27 * tmin / (tmin + 237.3))
        es = (es_tmax + es_tmin) / 2.0

        # Pression de vapeur réelle ea (kPa) depuis l'humidité relative (FAO-56 Eq. 17)
        ea = (humidity / 100.0) * es

        # Déficit de pression de vapeur (kPa)
        vpd = es - ea

        # Rayonnement net (MJ/m²/jour) : simplification Rns - Rnl
        # Rayonnement net court (albédo = 0.23 pour une culture de référence)
        rns = (1.0 - 0.23) * solar_rad
        # Rayonnement net long-onde (approximation simplifiée)
        rnl = 0.2 * solar_rad
        rn = rns - rnl

        # Flux de chaleur du sol G ≈ 0 à l'échelle journalière (FAO-56 hypothèse)
        g = 0.0

        # Équation FAO-56 Penman-Monteith (FAO-56 Eq. 6)
        num = 0.408 * delta * (rn - g) + gamma * (900.0 / (tmean + 273.0)) * wind_speed * vpd
        den = delta + gamma * (1.0 + 0.34 * wind_speed)

        eto = num / den
        return float(max(0.0, eto))


    def runoff_cn(self, precipitation: float, prior_5d_rain: float = 0.0) -> float:
        """
        Calcule le ruissellement quotidien par la méthode révisée SCS-CN.

        :param precipitation: Précipitation du jour (mm).
        :param prior_5d_rain: Pluie des 5 jours précédents (pour ajustement AMC).
        :return: Ruissellement (mm).
        """
        if precipitation <= 0.0:
            return 0.0
            
        base_cn = self.soil_params['cn_amc2']
        
        # Ajustement AMC (Antecedent Moisture Condition)
        if prior_5d_rain < 12.5:
            cn = base_cn / (2.281 - 0.0128 * base_cn) # AMC I (sec)
        elif prior_5d_rain > 35.5:
            cn = base_cn / (0.427 + 0.00573 * base_cn) # AMC III (humide)
        else:
            cn = base_cn # AMC II (moyen)
            
        s = (25400.0 / cn) - 254.0
        ia = 0.2 * s # Abstraction initiale
        
        if precipitation > ia:
            runoff = ((precipitation - ia) ** 2) / (precipitation + 0.8 * s)
            return float(runoff)
        return 0.0

    def compute_water_balance(self) -> pd.DataFrame:
        """
        Simule le bilan hydrique quotidien du sol selon FAO-56.

        :return: DataFrame contenant l'évolution du bilan.
        """
        if self.rainfall_data.empty or self.temperature_data.empty:
            raise DataError("Données météorologiques historiques manquantes pour le calcul du bilan hydrique.")
            
        taw = self.soil_params['taw'] # Total Available Water
        base_cn = self.soil_params['cn_amc2']
        kc = self.get_crop_coefficients(self.crop, 'mid')

        precip_arr = self.rainfall_data.to_numpy()
        tmin_arr = self.temperature_data['temperature_min'].to_numpy()
        tmax_arr = self.temperature_data['temperature_max'].to_numpy()
        dates = self.rainfall_data.index
        dayofyear_arr = dates.dayofyear.to_numpy()

        # Calcul des pluies accumulées sur les 5 jours précédents
        prior_5d_arr = self.rainfall_data.shift(1).rolling(window=5, min_periods=0).sum().fillna(0.0).to_numpy()

        # Vectorisation ETo Hargreaves-Samani
        eto_arr = self.et0_hargreaves(tmin_arr, tmax_arr, dayofyear_arr)
        etc_arr = eto_arr * kc

        # Vectorisation du ruissellement SCS-CN
        cn_1 = base_cn / (2.281 - 0.0128 * base_cn)
        cn_3 = base_cn / (0.427 + 0.00573 * base_cn)
        cn_arr = np.where(prior_5d_arr < 12.5, cn_1, np.where(prior_5d_arr > 35.5, cn_3, base_cn))
        s_arr = (25400.0 / cn_arr) - 254.0
        ia_arr = 0.2 * s_arr

        runoff_arr = np.where(
            (precip_arr > 0) & (precip_arr > ia_arr),
            ((precip_arr - ia_arr) ** 2) / (precip_arr + 0.8 * s_arr),
            0.0
        )
        pluie_eff_arr = np.maximum(0.0, precip_arr - runoff_arr)

        # Calcul séquentiel rapide du stock d'eau du sol
        n = len(dates)
        dr_arr = np.zeros(n)
        reserve_arr = np.zeros(n)
        stress_arr = np.zeros(n)
        dr = 0.0

        for i in range(n):
            temp_dr = dr - pluie_eff_arr[i]
            if temp_dr < 0:
                dr = 0.0
            else:
                dr = min(taw, temp_dr + etc_arr[i])
            dr_arr[i] = dr
            reserve_arr[i] = taw - dr
            stress_arr[i] = dr / taw if taw > 0 else 0.0

        df = pd.DataFrame({
            'precip': precip_arr,
            'et0': np.round(eto_arr, 2),
            'pluie_eff': np.round(pluie_eff_arr, 2),
            'evapotransp': np.round(etc_arr, 2),
            'deficit_eau': np.round(dr_arr, 2),
            'reserve_utile': np.round(reserve_arr, 2),
            'stress_hydrique_index': np.round(stress_arr, 2)
        }, index=dates)

        self.balance_result = df
        return df

    def get_soil_params(self, soil_type: str) -> dict:
        """
        Retourne les paramètres physiques du sol béninois.
        AWC: Available Water Capacity, CN: Curve Number, Ksat: conductivité.
        """
        soils = {
            'ferrugineux': {'taw': 100.0, 'cn_amc2': 82.0, 'ksat': 15.0},
            'ferrallitique': {'taw': 130.0, 'cn_amc2': 75.0, 'ksat': 35.0},
            'sableux': {'taw': 60.0, 'cn_amc2': 65.0, 'ksat': 100.0},
            'limoneux': {'taw': 150.0, 'cn_amc2': 78.0, 'ksat': 10.0}
        }
        if soil_type not in soils:
            raise ValidationError(f"Type de sol non pris en charge: {soil_type}")
        return soils[soil_type]

    def get_crop_coefficients(self, crop: str, stage: str) -> float:
        """
        Retourne le coefficient de culture (Kc) selon le stade.
        (Simplifié pour l'implémentation de base).
        """
        kcs = {
            'maize': {'ini': 0.3, 'mid': 1.2, 'end': 0.35},
            'rice': {'ini': 1.05, 'mid': 1.2, 'end': 0.9},
            'manioc': {'ini': 0.3, 'mid': 0.8, 'end': 0.3},
            'sorghum': {'ini': 0.3, 'mid': 1.0, 'end': 0.55},
            'tomato': {'ini': 0.6, 'mid': 1.15, 'end': 0.7}
        }
        if crop not in kcs:
            raise CropError(f"Culture non reconnue pour le coefficient FAO-56: {crop}")
        params = kcs[crop]
        return params.get(stage, 1.0)
