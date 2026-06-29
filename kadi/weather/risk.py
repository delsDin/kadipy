"""
Module risk.py

Indicateurs de risque : calcul des indices de sécheresse (SPI, Markov, Hurst)
et probabilité de précipitation à court terme.
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
from typing import Optional

from kadi.exceptions import InsufficientData, ValidationError
from .location import Location

class RiskIndicators:
    """
    Évalue les risques climatiques (sécheresse, probabilité de pluie).
    """

    def __init__(self, location: Location, rainfall_historical: pd.Series, forecast_data: pd.DataFrame):
        """
        Initialise les indicateurs de risque.

        :param location: Instance de Location.
        :param rainfall_historical: Série historique de pluie.
        :param forecast_data: DataFrame de prévisions météorologiques.
        """
        self.location = location
        self.rainfall_historical = rainfall_historical
        self.forecast_data = forecast_data

    def drought_index(self, method: str = 'spi', window_months: int = 3) -> dict:
        """
        Calcule l'indice de sécheresse avec la méthode spécifiée.

        :param method: Méthode ('spi', 'markov', 'hurst', 'combined').
        :param window_months: Fenêtre temporelle pour le calcul du SPI.
        :return: Dictionnaire avec les résultats de sécheresse.
        """
        results = {}
        
        if method in ['spi', 'combined']:
            spi_val = self.spi(window_months)
            results[f'spi_{window_months}month'] = spi_val
            results['drought_severity'] = self._get_severity_level(spi_val)
            
        if method in ['markov', 'combined']:
            markov_res = self.markov_transition()
            results['markov_p_dry'] = markov_res.get('p_dry_dry', 0.0)
            
        if method in ['hurst', 'combined']:
            # L'exposant de Hurst nécessite une série assez longue (au moins qq années)
            hurst = self.hurst_exponent()
            results['hurst_exponent'] = round(hurst, 2)
            
        if method not in ['spi', 'markov', 'hurst', 'combined']:
            raise ValidationError(f"Méthode {method} non supportée pour l'indice de sécheresse.")
            
        return results

    def spi(self, window_months: int) -> float:
        """
        Calcule le Standardized Precipitation Index (SPI) pour la période récente.
        Implémentation simplifiée pour le MVP.
        
        :param window_months: Fenêtre d'accumulation en mois.
        :return: Valeur du SPI.
        """
        if self.rainfall_historical.empty:
            raise InsufficientData("Aucune donnée historique pour le calcul du SPI.")
            
        # Cumul de précipitation sur la fenêtre temporelle
        days = window_months * 30
        rolling_sum = self.rainfall_historical.rolling(window=days, min_periods=days//2).sum()
        rolling_sum = rolling_sum.dropna()
        
        if len(rolling_sum) < 30: # Pas assez de données pour faire une loi Gamma
            raise InsufficientData("Pas assez de jours de données pour ajuster le modèle SPI (minimum 30 requis).")
            
        # Ajustement d'une distribution Gamma simplifié
        # On évite les zéros pour la distribution Gamma
        valid_data = rolling_sum[rolling_sum > 0]
        if len(valid_data) == 0:
            return -3.0 # Extrême sécheresse
            
        # Dans un environnement de production, on utiliserait scipy.stats.gamma.fit
        # et une correction de probabilité mixte pour p(x=0). 
        # Ici on fait une approximation simple par score Z (loi normale) pour le mock
        current_val = rolling_sum.iloc[-1]
        mean_val = rolling_sum.mean()
        std_val = rolling_sum.std()
        
        if std_val == 0:
            return 0.0
            
        spi_val = (current_val - mean_val) / std_val
        return round(float(spi_val), 2)

    def markov_transition(self, threshold_mm: float = 1.0) -> dict:
        """
        Calcule les probabilités de transition de Markov (jour sec -> jour sec).

        :param threshold_mm: Seuil pour considérer un jour comme humide.
        :return: Dictionnaire avec les probabilités p00, p01, p10, p11.
        """
        if self.rainfall_historical.empty:
            raise InsufficientData("Aucune donnée historique pour le calcul des probabilités de transition de Markov.")
            
        # États : 0 = sec, 1 = humide
        states = (self.rainfall_historical >= threshold_mm).astype(int)
        
        # Transitions
        transitions = pd.DataFrame({'current': states.iloc[:-1].values, 'next': states.iloc[1:].values})
        
        counts = transitions.groupby(['current', 'next']).size().unstack(fill_value=0)
        
        # On s'assure d'avoir la matrice 2x2
        for i in [0, 1]:
            if i not in counts.index:
                counts.loc[i] = [0, 0]
            for j in [0, 1]:
                if j not in counts.columns:
                    counts[j] = 0
                    
        # Probabilités
        p0 = counts.loc[0].sum()
        p1 = counts.loc[1].sum()
        
        p00 = counts.loc[0, 0] / p0 if p0 > 0 else 0
        p01 = counts.loc[0, 1] / p0 if p0 > 0 else 0
        p10 = counts.loc[1, 0] / p1 if p1 > 0 else 0
        p11 = counts.loc[1, 1] / p1 if p1 > 0 else 0
        
        return {
            'p_dry_dry': round(p00, 2),
            'p_dry_wet': round(p01, 2),
            'p_wet_dry': round(p10, 2),
            'p_wet_wet': round(p11, 2)
        }

    def hurst_exponent(self, window: int = 1095) -> float:
        """
        Calcule l'exposant de Hurst par la méthode de gamme rééchelonnée (R/S).
        
        :param window: Taille de la fenêtre maximale (jours) pour l'analyse.
        :return: Exposant de Hurst (H). Si H > 0.5, persistance climatique.
        """
        if len(self.rainfall_historical) < 100:
            raise InsufficientData("Pas assez de données pour l'exposant de Hurst (minimum 100 requis).")
            
        data = self.rainfall_historical.values
        # Simulation d'un calcul R/S simplifié (un calcul complet est coûteux)
        # H est typiquement autour de 0.65 pour les régimes pluviométriques
        
        mean = np.mean(data)
        centered_y = data - mean
        cumulative_y = np.cumsum(centered_y)
        
        r = np.max(cumulative_y) - np.min(cumulative_y)
        s = np.std(data)
        
        if s == 0:
            return 0.5
            
        # Approximation grossière : R/S = (N/2)^H
        rs = r / s
        n = len(data)
        
        try:
            h = np.log(rs) / np.log(n/2)
            # Contraint entre 0 et 1
            return float(np.clip(h, 0.01, 0.99))
        except:
            return 0.5

    def rain_probability(self, days_ahead: int = 1, min_rainfall_mm: float = 1.0) -> dict:
        """
        Prévoit la probabilité de pluie pour les jours suivants.

        :param days_ahead: Jours d'avance (1 à 7).
        :param min_rainfall_mm: Seuil de précipitation minimale.
        :return: Dictionnaire avec probabilités et recommandations.
        """
        if self.forecast_data is None or self.forecast_data.empty:
            raise InsufficientData("Données de prévision indisponibles pour estimer la probabilité de pluie.")
            
        # Restreint aux jours demandés
        df = self.forecast_data.head(days_ahead)
        
        # Pour le mock, on utilise la précipitation brute simulée
        # et on la transforme en probabilité
        probs = {}
        max_prob = 0.0
        
        for i, (date, row) in enumerate(df.iterrows()):
            precip = row.get('precipitation', 0)
            
            # Simple heuristique pour la probabilité
            prob = min(1.0, precip / (min_rainfall_mm * 5))
            if precip < min_rainfall_mm:
                prob = prob * 0.5
                
            key = 'tomorrow' if i == 0 else f"{i+1}_days"
            probs[key] = round(prob, 2)
            if prob > max_prob:
                max_prob = prob
                
        # Recommandations
        msg = f"{int(max_prob * 100)}% de chance de pluie dans les {days_ahead} jours."
        if max_prob > 0.7:
            rec = "Risque de lessivage. Repousser les traitements phytosanitaires."
        elif max_prob < 0.2:
            rec = "Conditions sèches. Bon moment pour traitements phyto."
        else:
            rec = "Vigilance recommandée pour les opérations au champ."
            
        return {
            **probs,
            'message': msg,
            'recommendation': rec
        }

    def _get_severity_level(self, spi_value: float) -> str:
        """
        Interprète la valeur du SPI pour donner un niveau de sévérité.

        :param spi_value: Valeur de l'indice SPI.
        :return: Catégorie de sécheresse.
        """
        if spi_value > 1.0:
            return 'no_drought' # En réalité anormalement humide
        elif -1.0 <= spi_value <= 1.0:
            return 'mild'
        elif -1.5 <= spi_value < -1.0:
            return 'moderate'
        elif spi_value < -1.5:
            return 'severe'
        return 'unknown'
