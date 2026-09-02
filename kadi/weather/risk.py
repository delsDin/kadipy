"""
Module risk.py

Indicateurs de risque : calcul des indices de sécheresse (SPI, Markov, Hurst)
et probabilité de précipitation à court terme.
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
from typing import Optional

from kadi.exceptions import DataError, ValidationError
from .location import Location

class RiskIndicators:
    """
    Évalue les risques climatiques (sécheresse, probabilité de pluie).
    """

    def __init__(self, location: Location, rainfall_historical: pd.Series, forecast_data: pd.DataFrame):
        """
        Initialise les indicateurs de risque.

        Args:
            location (Location): Instance de la classe Location.
            rainfall_historical (pd.Series): Série historique de précipitations journalières.
            forecast_data (pd.DataFrame): DataFrame de prévisions météorologiques.
        """
        self.location = location
        self.rainfall_historical = rainfall_historical
        self.forecast_data = forecast_data

    def drought_index(self, method: str = 'spi', window_months: int = 3) -> dict:
        """
        Calcule l'indice de sécheresse avec la méthode spécifiée.

        Args:
            method (str): Méthode de calcul parmi 'spi', 'markov', 'hurst' ou
                'combined' (toutes les méthodes combinées). Par défaut 'spi'.
            window_months (int): Fenêtre temporelle d'accumulation en mois
                pour le calcul du SPI. Par défaut 3.

        Returns:
            dict: Dictionnaire avec les résultats de sécheresse. Les clés
                varient selon la méthode choisie (ex: 'spi_3month',
                'drought_severity', 'markov_p_dry', 'hurst_exponent').

        Raises:
            ValidationError: Si la méthode spécifiée n'est pas supportée.
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

        La méthode suit la définition originale de McKee et al. (1993) :

        1. Calcul du cumul de précipitations sur la fenêtre temporelle demandée.
        2. Ajustement d'une loi Gamma sur les cumuls strictement positifs via
           scipy.stats.gamma.fit (localisation fixée à 0 avec floc=0).
        3. Application d'une correction de masse de probabilité pour les jours sans
           pluie (cumul nul) : la probabilité en 0 est répartie proportionnellement
           à la fréquence observée de jours secs.
        4. Conversion de la probabilité cumulative en score SPI via la fonction
           quantile de la loi normale inverse (scipy.stats.norm.ppf).

        Args:
            window_months (int): Fenêtre d'accumulation en mois.

        Returns:
            float: Valeur du SPI arrondie à 2 décimales. Vaut 0.0 si tous les
                cumuls sont identiques (écart-type nul).

        Raises:
            DataError: Si la série est vide, si le nombre de fenêtres
                calculées est inférieur à 30, si les cumuls non nuls sont
                trop peu nombreux (< 10) pour ajuster une loi Gamma, ou si
                l'ajustement Gamma échoue numériquement.
        """
        if self.rainfall_historical.empty:
            raise DataError("Aucune donnée historique pour le calcul du SPI.")

        # Calcul des cumuls glissants sur la fenêtre temporelle
        days = window_months * 30
        rolling_sum = self.rainfall_historical.rolling(
            window=days, min_periods=days // 2
        ).sum()
        rolling_sum = rolling_sum.dropna()

        # Vérification du nombre minimal de fenêtres
        if len(rolling_sum) < 30:
            raise DataError(
                "Pas assez de jours de données pour ajuster le modèle SPI "
                "(minimum 30 fenêtres requises)."
            )

        # Cas dégénéré : tous les cumuls sont identiques, le SPI est nul
        if rolling_sum.std() == 0:
            return 0.0

        # Valeur du cumul courant (point le plus récent de la série)
        current_val = float(rolling_sum.iloc[-1])

        # Calcul de la proportion de jours sans pluie (correction de masse)
        n_total = len(rolling_sum)
        n_zero = int((rolling_sum == 0).sum())
        q_zero = n_zero / n_total

        # Isolation des cumuls strictement positifs pour l'ajustement Gamma
        valid_data = rolling_sum[rolling_sum > 0].values

        if len(valid_data) < 10:
            raise DataError(
                "Pas assez de cumuls non nuls pour ajuster une loi Gamma "
                f"(trouvé {len(valid_data)}, minimum 10 requis). "
                "La période analysée est peut-être trop sèche."
            )

        # Ajustement de la loi Gamma (floc=0 fixe le paramètre de localisation à 0)
        try:
            shape, loc, scale = stats.gamma.fit(valid_data, floc=0)
        except Exception as exc:
            raise DataError(
                f"L'ajustement de la loi Gamma a échoué : {exc}. "
                "Vérifiez la qualité de la série pluviométrique."
            ) from exc

        # Calcul de la probabilité cumulative avec correction de masse en 0
        if current_val == 0:
            # Les jours sans pluie tombent dans la masse ponctuelle en 0
            prob_cumul = q_zero / 2.0
        else:
            # Probabilité mixte : masse en 0 + CDF Gamma sur les valeurs positives
            prob_gamma = float(stats.gamma.cdf(current_val, shape, loc=loc, scale=scale))
            prob_cumul = q_zero + (1.0 - q_zero) * prob_gamma

        # Clip de sécurité pour éviter +/-inf lors de l'appel à norm.ppf
        prob_cumul = float(np.clip(prob_cumul, 1e-6, 1.0 - 1e-6))

        # Conversion en score SPI via la loi normale inverse
        spi_val = float(stats.norm.ppf(prob_cumul))
        return round(spi_val, 2)

    def markov_transition(self, threshold_mm: float = 1.0) -> dict:
        """
        Calcule les probabilités de transition de Markov entre jours secs et humides.

        Args:
            threshold_mm (float): Seuil de précipitation en millimètres pour
                considérer un jour comme humide. Par défaut 1.0 mm.

        Returns:
            dict: Dictionnaire avec les quatre probabilités de transition :
                - 'p_dry_dry'  : P(sec | sec précédent)
                - 'p_dry_wet'  : P(humide | sec précédent)
                - 'p_wet_dry'  : P(sec | humide précédent)
                - 'p_wet_wet'  : P(humide | humide précédent)

        Raises:
            DataError: Si la série historique est vide.
        """
        if self.rainfall_historical.empty:
            raise DataError("Aucune donnée historique pour le calcul des probabilités de transition de Markov.")
            
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

        Args:
            window (int): Taille maximale de la fenêtre d'analyse en jours.
                Par défaut 1095 (environ 3 ans). La fenêtre effective est
                plafonnée à la moitié de la longueur de la série.

        Returns:
            float: Exposant de Hurst H, compris entre 0.01 et 0.99.
                Retourne 0.5 si la série est trop courte pour une régression fiable.

        Raises:
            DataError: Si la série historique contient moins de 100 jours.
        """
        if len(self.rainfall_historical) < 100:
            raise DataError("Pas assez de données pour l'exposant de Hurst (minimum 100 jours requis).")

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

        Args:
            days_ahead (int): Nombre de jours d'avance à calculer (1 à 7).
                Par défaut 1 (probabilité pour demain).
            min_rainfall_mm (float): Seuil de précipitation en millimètres
                pour considérer un jour comme humide. Par défaut 1.0 mm.

        Returns:
            dict: Dictionnaire contenant :
                - 'tomorrow'   : probabilité de pluie demain (si days_ahead >= 1).
                - 'N_days'     : probabilité pour le jour N (N >= 2).
                - 'message'    : phrase de synthèse avec le risque maximal.
                - 'recommendation' : recommandation agronomique.

        Raises:
            DataError: Si les données de prévision sont absentes ou vides.
        """
        if self.forecast_data is None or self.forecast_data.empty:
            raise DataError("Données de prévision indisponibles pour estimer la probabilité de pluie.")

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

        Args:
            spi_value (float): Valeur de l'indice SPI calculé par spi().

        Returns:
            str: Niveau de sévérité parmi :
                - 'no_drought' : SPI > 1.0 (période anormalement humide)
                - 'mild'       : -1.0 <= SPI <= 1.0 (conditions normales)
                - 'moderate'   : -1.5 <= SPI < -1.0
                - 'severe'     : SPI < -1.5
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
