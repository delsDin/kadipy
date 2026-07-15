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
        Calcule l'exposant de Hurst par la méthode de gamme rééchelonnée (R/S) multi-échelle.

        L'algorithme segmente la série en sous-fenêtres de tailles croissantes,
        calcule le rapport R/S moyen pour chaque taille, puis estime H par régression
        log-log. Un exposant H > 0.5 indique une persistance climatique (mémoire longue).

        :param window: Taille maximale de la fenêtre d'analyse (jours).
        :return: Exposant de Hurst H (compris entre 0.01 et 0.99).
        """
        if len(self.rainfall_historical) < 100:
            raise InsufficientData("Pas assez de données pour l'exposant de Hurst (minimum 100 jours requis).")

        data = self.rainfall_historical.values
        n_total = len(data)

        # Taille de la plus petite fenêtre (doit être assez grande pour un R/S stable)
        min_w = 10
        # Taille de la plus grande fenêtre (plafonnée à la moitié de la série)
        max_w = min(window, n_total // 2)

        window_sizes = []
        rs_means = []

        # Progression géométrique des tailles de fenêtre (facteur 1.5)
        w = min_w
        while w <= max_w:
            # Calcul du R/S moyen sur toutes les sous-séquences non chevauchantes
            num_segments = n_total // w
            rs_values_w = []

            for k in range(num_segments):
                segment = data[k * w: (k + 1) * w]
                seg_mean = np.mean(segment)
                centered = segment - seg_mean
                cum_dev = np.cumsum(centered)

                # Gamme (R) et écart-type (S) du segment
                r = np.max(cum_dev) - np.min(cum_dev)
                s = np.std(segment)

                if s > 0:
                    rs_values_w.append(r / s)

            if rs_values_w:
                window_sizes.append(w)
                rs_means.append(np.mean(rs_values_w))

            w = max(w + 1, int(w * 1.5))

        # Minimum de 3 points pour une régression fiable
        if len(window_sizes) < 3:
            return 0.5

        # Régression linéaire dans l'espace log-log : log(R/S) = H * log(N) + c
        log_n = np.log(np.array(window_sizes, dtype=float))
        log_rs = np.log(np.array(rs_means, dtype=float))
        coeffs = np.polyfit(log_n, log_rs, 1)

        # H est la pente de la droite de régression
        h = float(coeffs[0])
        return float(np.clip(h, 0.01, 0.99))

    def rain_probability(self, days_ahead: int = 1, min_rainfall_mm: float = 1.0) -> dict:
        """
        Prévoit la probabilité de pluie pour les prochains jours.

        Combine deux sources d'information pour plus de robustesse :
        1. Les prévisions API (Open-Meteo) pour le court terme.
        2. La probabilité de transition de Markov (calculée sur l'historique local)
           pour estimer la tendance climatique sous-jacente.
        La probabilité combinée pondère 70 % sur la prévision API et 30 % sur Markov.

        :param days_ahead: Nombre de jours d'avance (1 à 7).
        :param min_rainfall_mm: Seuil de précipitation pour considérer un jour comme humide.
        :return: Dictionnaire avec probabilités par jour et recommandations.
        """
        if self.forecast_data is None or self.forecast_data.empty:
            raise InsufficientData("Données de prévision indisponibles pour estimer la probabilité de pluie.")

        # Construction de la matrice de Markov depuis l'historique local
        try:
            markov = self.markov_transition(min_rainfall_mm)
            p_wet_if_wet = markov['p_wet_wet']
            p_wet_if_dry = markov['p_dry_wet']

            # État du dernier jour connu dans l'historique
            last_precip = self.rainfall_historical.iloc[-1] if not self.rainfall_historical.empty else 0.0
            current_p_wet = 1.0 if last_precip >= min_rainfall_mm else 0.0
        except Exception:
            # Si Markov échoue, on ne l'utilise pas
            markov = None
            p_wet_if_wet = 0.5
            p_wet_if_dry = 0.5
            current_p_wet = 0.0

        df = self.forecast_data.head(days_ahead)
        probs = {}
        max_prob = 0.0

        for i, (date, row) in enumerate(df.iterrows()):
            forecast_precip = row.get('precipitation', 0.0)

            # 1. Probabilité issue de la prévision API (heuristique sur la pluie prévue)
            prob_api = min(1.0, forecast_precip / (min_rainfall_mm * 5))
            if forecast_precip < min_rainfall_mm:
                prob_api *= 0.5

            # 2. Probabilité de Markov (probabilité conditionnelle d'un jour humide)
            prob_markov = current_p_wet * p_wet_if_wet + (1.0 - current_p_wet) * p_wet_if_dry

            # 3. Combinaison pondérée (API court terme = 70 %, Markov tendance = 30 %)
            prob_combined = 0.7 * prob_api + 0.3 * prob_markov

            # Mise à jour de l'état courant pour le jour suivant
            current_p_wet = prob_combined

            key = 'tomorrow' if i == 0 else f"{i + 1}_days"
            probs[key] = round(prob_combined, 2)
            if prob_combined > max_prob:
                max_prob = prob_combined

        # Recommandations agronomiques selon le risque maximal
        msg = f"{int(max_prob * 100)} % de chance de pluie dans les {days_ahead} prochains jours."
        if max_prob > 0.7:
            rec = "Risque de lessivage élevé. Repousser les traitements phytosanitaires."
        elif max_prob < 0.2:
            rec = "Conditions sèches attendues. Bon moment pour les traitements phyto."
        else:
            rec = "Vigilance recommandée pour les opérations au champ."

        return {
            **probs,
            'message': msg,
            'recommendation': rec,
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
