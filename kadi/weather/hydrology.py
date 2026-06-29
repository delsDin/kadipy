"""
Module hydrology.py

Hydrologie et bilan hydrique : calcul de l'évapotranspiration de référence (ET0),
ruissellement et réserve utile du sol selon FAO-56.
"""

import numpy as np
import pandas as pd
from typing import Optional

from kadi.exceptions import InsufficientData, CropNotFound, ValidationError
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

    def et0_hargreaves(self, tmin: float, tmax: float, day_of_year: int) -> float:
        """
        Calcule l'évapotranspiration de référence (ETo) par Hargreaves-Samani.

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
        
        gsc = 0.0820 # Constante solaire
        ra = (24 * 60 / np.pi) * gsc * dr * (
            omega_s * np.sin(lat_rad) * np.sin(delta) +
            np.cos(lat_rad) * np.cos(delta) * np.sin(omega_s)
        )
        
        # 2. Formule Hargreaves-Samani
        tmean = (tmax + tmin) / 2.0
        tdiff = max(0.0, tmax - tmin)
        k_rs = 0.0023
        
        eto = 0.408 * k_rs * ra * (tmean + 17.8) * (tdiff ** 0.5)
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
            raise InsufficientData("Données météorologiques historiques manquantes pour le calcul du bilan hydrique.")
            
        taw = self.soil_params['taw'] # Total Available Water
        dr = 0.0 # Depletion (épuisement initial, sol plein = 0)
        
        dates = self.rainfall_data.index
        results = []
        
        for i, date in enumerate(dates):
            precip = self.rainfall_data.iloc[i]
            tmin = self.temperature_data['temperature_min'].iloc[i]
            tmax = self.temperature_data['temperature_max'].iloc[i]
            
            # Pluie sur 5j précédents pour le CN
            if i >= 5:
                prior_5d = self.rainfall_data.iloc[i-5:i].sum()
            else:
                prior_5d = self.rainfall_data.iloc[:i].sum()
                
            # Ruissellement
            runoff = self.runoff_cn(precip, prior_5d)
            pluie_eff = max(0.0, precip - runoff)
            
            # Evapotranspiration
            et0 = self.et0_hargreaves(tmin, tmax, date.dayofyear)
            kc = self.get_crop_coefficients(self.crop, 'mid') # Simplifié pour le MVP
            etc = et0 * kc
            
            # Bilan
            temp_dr = dr - pluie_eff
            
            if temp_dr < 0:
                dr = 0.0 # Drainage profond
            else:
                dr = min(taw, temp_dr + etc)
                
            reserve = taw - dr
            stress_index = dr / taw if taw > 0 else 0
            
            results.append({
                'date': date,
                'precip': precip,
                'et0': round(et0, 2),
                'pluie_eff': round(pluie_eff, 2),
                'evapotransp': round(etc, 2),
                'deficit_eau': round(dr, 2),
                'reserve_utile': round(reserve, 2),
                'stress_hydrique_index': round(stress_index, 2)
            })
            
        df = pd.DataFrame(results).set_index('date')
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
            raise CropNotFound(f"Culture non reconnue pour le coefficient FAO-56: {crop}")
        params = kcs[crop]
        return params.get(stage, 1.0)
