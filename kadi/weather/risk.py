"""
Module risk.py

Indicateurs de risque : calcul des indices de sécheresse (SPI, Markov, Hurst)
et probabilité de précipitation à court terme.
"""

import warnings

import numpy as np
import pandas as pd
import scipy.stats as stats
from typing import Optional

from kadi.exceptions import DataError, ValidationError
from .location import Location


class Risk:
    """
    Évalue les risques climatiques (sécheresse, probabilité de pluie).

    Attributs:
        location (Location): Localisation associée.
        rainfall (pd.Series): Série historique de précipitations journalières.
        forecast (pd.DataFrame): Prévisions météorologiques.
    """

    def __init__(
        self,
        location: Location,
        rainfall_historical: pd.Series,
        forecast_data: pd.DataFrame,
    ):
        """
        Initialise les indicateurs de risque.

        Args:
            location (Location): Instance de la classe Location.
            rainfall_historical (pd.Series): Série historique de précipitations
                journalières.
            forecast_data (pd.DataFrame): DataFrame de prévisions météorologiques.
        """
        self.location = location
        # Nouveaux noms d'attributs
        self.rainfall = rainfall_historical
        self.forecast = forecast_data

    def drought(
        self,
        method: str = "spi",
        window: int = 3,
        window_months: Optional[int] = None,
    ) -> dict:
        """
        Calcule l'indice de sécheresse avec la méthode spécifiée.

        Args:
            method (str): Méthode de calcul parmi 'spi', 'markov', 'hurst' ou
                'combined' (toutes les méthodes combinées). Par défaut 'spi'.
            window (int): Fenêtre temporelle d'accumulation en mois pour le
                calcul du SPI. Par défaut 3.
            window_months (int, optionnel): Ancien nom du paramètre ``window``.

        Returns:
            dict: Dictionnaire avec les résultats de sécheresse. Les clés
                varient selon la méthode choisie (ex: 'spi_3month',
                'drought_severity', 'markov_p_dry', 'hurst_exponent').

        Raises:
            ValidationError: Si la méthode spécifiée n'est pas supportée.
        """
        if window_months is not None:
            warnings.warn(
                "Le paramètre 'window_months' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'window' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            window = window_months

        results = {}

        if method in ("spi", "combined"):
            spi_val = self.spi(window)
            results[f"spi_{window}month"] = spi_val
            results["drought_severity"] = self._severity(spi_val)

        if method in ("markov", "combined"):
            markov_res = self.markov()
            results["markov_p_dry"] = markov_res.get("p_dry_dry", 0.0)

        if method in ("hurst", "combined"):
            # L'exposant de Hurst nécessite une série assez longue
            hurst = self.hurst()
            results["hurst_exponent"] = round(hurst, 2)

        if method not in ("spi", "markov", "hurst", "combined"):
            raise ValidationError(
                f"Méthode {method} non supportée pour l'indice de sécheresse."
            )

        return results

    def spi(self, window: int = 3, window_months: Optional[int] = None) -> float:
        """
        Calcule le Standardized Precipitation Index (SPI) pour la période récente.

        La méthode suit la définition de McKee et al. (1993) :
        1. Calcul du cumul de précipitations sur la fenêtre temporelle.
        2. Ajustement d'une loi Gamma sur les cumuls strictement positifs.
        3. Correction de masse de probabilité pour les jours sans pluie.
        4. Conversion en score SPI via la loi normale inverse.

        Args:
            window (int): Fenêtre d'accumulation en mois.
            window_months (int, optionnel): Ancien nom du paramètre ``window``.

        Returns:
            float: Valeur du SPI arrondie à 2 décimales. Vaut 0.0 si tous les
                cumuls sont identiques (écart-type nul).

        Raises:
            DataError: Si la série est vide, si le nombre de fenêtres calculées
                est inférieur à 30, si les cumuls non nuls sont trop peu nombreux
                (moins de 10) pour ajuster une loi Gamma, ou si l'ajustement
                Gamma échoue numériquement.
        """
        if window_months is not None:
            warnings.warn(
                "Le paramètre 'window_months' est obsolète et sera supprimé dans "
                "KadiPy v2.0. Utilisez 'window' à la place.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            window = window_months

        if self.rainfall.empty:
            raise DataError("Aucune donnée historique pour le calcul du SPI.")


        # Calcul des cumuls glissants sur la fenêtre temporelle
        days = window * 30
        rolling_sum = self.rainfall.rolling(
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

        # Ajustement de la loi Gamma (floc=0 fixe le paramètre de localisation)
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

    def markov(self, thresh: float = 1.0) -> dict:
        """
        Calcule les probabilités de transition de Markov entre jours secs et humides.

        Args:
            thresh (float): Seuil de précipitation en millimètres pour considérer
                un jour comme humide. Par défaut 1.0 mm.

        Returns:
            dict: Dictionnaire avec les quatre probabilités de transition :
                - 'p_dry_dry'  : P(sec | sec précédent)
                - 'p_dry_wet'  : P(humide | sec précédent)
                - 'p_wet_dry'  : P(sec | humide précédent)
                - 'p_wet_wet'  : P(humide | humide précédent)

        Raises:
            DataError: Si la série historique est vide.
        """
        if self.rainfall.empty:
            raise DataError(
                "Aucune donnée historique pour le calcul des probabilités "
                "de transition de Markov."
            )

        # États : 0 = sec, 1 = humide
        states = (self.rainfall >= thresh).astype(int)

        # Construction de la matrice de transitions
        transitions = pd.DataFrame(
            {"current": states.iloc[:-1].values, "next": states.iloc[1:].values}
        )

        counts = transitions.groupby(["current", "next"]).size().unstack(fill_value=0)

        # S'assure d'avoir la matrice 2x2
        for i in [0, 1]:
            if i not in counts.index:
                counts.loc[i] = [0, 0]
            for j in [0, 1]:
                if j not in counts.columns:
                    counts[j] = 0

        # Calcul des probabilités normalisées par ligne
        p0 = counts.loc[0].sum()
        p1 = counts.loc[1].sum()

        p00 = counts.loc[0, 0] / p0 if p0 > 0 else 0
        p01 = counts.loc[0, 1] / p0 if p0 > 0 else 0
        p10 = counts.loc[1, 0] / p1 if p1 > 0 else 0
        p11 = counts.loc[1, 1] / p1 if p1 > 0 else 0

        return {
            "p_dry_dry": round(p00, 2),
            "p_dry_wet": round(p01, 2),
            "p_wet_dry": round(p10, 2),
            "p_wet_wet": round(p11, 2),
        }

    def hurst(self, window: int = 1095) -> float:
        """
        Calcule l'exposant de Hurst par la méthode de gamme rééchelonnée (R/S).

        L'algorithme segmente la série en sous-fenêtres de tailles croissantes,
        calcule le rapport R/S moyen pour chaque taille, puis estime H par
        régression log-log. Un exposant H supérieur à 0.5 indique une persistance
        climatique (mémoire longue).

        Args:
            window (int): Taille maximale de la fenêtre d'analyse en jours.
                Par défaut 1095 (environ 3 ans). La fenêtre effective est
                plafonnée à la moitié de la longueur de la série.

        Returns:
            float: Exposant de Hurst H, compris entre 0.01 et 0.99. Retourne
                0.5 si la série est trop courte pour une régression fiable.

        Raises:
            DataError: Si la série historique contient moins de 100 jours.
        """
        if len(self.rainfall) < 100:
            raise DataError(
                "Pas assez de données pour l'exposant de Hurst "
                "(minimum 100 jours requis)."
            )

        data = self.rainfall.values
        n_total = len(data)

        # Taille de la plus petite fenêtre (assez grande pour un R/S stable)
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

    def rain_prob(self, days: int = 1, min_mm: float = 1.0) -> dict:
        """
        Prévoit la probabilité de pluie pour les prochains jours.

        Combine deux sources d'information :
        1. Les prévisions API (Open-Meteo) pour le court terme.
        2. La probabilité de transition de Markov (calculée sur l'historique
           local) pour estimer la tendance climatique sous-jacente.
        La probabilité combinée pondère 70 % sur la prévision API et 30 %
        sur Markov.

        Args:
            days (int): Nombre de jours d'avance à calculer (1 à 7).
                Par défaut 1.
            min_mm (float): Seuil de précipitation en millimètres pour
                considérer un jour comme humide. Par défaut 1.0 mm.

        Returns:
            dict: Dictionnaire contenant :
                - 'tomorrow'   : probabilité de pluie demain (si days >= 1).
                - 'N_days'     : probabilité pour le jour N (N >= 2).
                - 'message'    : phrase de synthèse avec le risque maximal.
                - 'recommendation' : recommandation agronomique.

        Raises:
            DataError: Si les données de prévision sont absentes ou vides.
        """
        if self.forecast is None or self.forecast.empty:
            raise DataError(
                "Données de prévision indisponibles pour estimer la "
                "probabilité de pluie."
            )

        # Construction de la matrice de Markov depuis l'historique local
        try:
            markov = self.markov(min_mm)
            p_wet_if_wet = markov["p_wet_wet"]
            p_wet_if_dry = markov["p_dry_wet"]

            # État du dernier jour connu dans l'historique
            last_precip = (
                self.rainfall.iloc[-1]
                if not self.rainfall.empty
                else 0.0
            )
            current_p_wet = 1.0 if last_precip >= min_mm else 0.0
        except Exception:
            # Si Markov échoue, on ne l'utilise pas
            markov = None
            p_wet_if_wet = 0.5
            p_wet_if_dry = 0.5
            current_p_wet = 0.0

        df = self.forecast.head(days)
        probs = {}
        max_prob = 0.0

        for i, (date, row) in enumerate(df.iterrows()):
            forecast_precip = row.get("precipitation", 0.0)

            # 1. Probabilité issue de la prévision API (heuristique)
            prob_api = min(1.0, forecast_precip / (min_mm * 5))
            if forecast_precip < min_mm:
                prob_api *= 0.5

            # 2. Probabilité de Markov (probabilité conditionnelle d'un jour humide)
            prob_markov = (
                current_p_wet * p_wet_if_wet
                + (1.0 - current_p_wet) * p_wet_if_dry
            )

            # 3. Combinaison pondérée (API 70 %, Markov 30 %)
            prob_combined = 0.7 * prob_api + 0.3 * prob_markov

            # Mise à jour de l'état courant pour le jour suivant
            current_p_wet = prob_combined

            key = "tomorrow" if i == 0 else f"{i + 1}_days"
            probs[key] = round(prob_combined, 2)
            if prob_combined > max_prob:
                max_prob = prob_combined

        # Recommandations agronomiques selon le risque maximal
        msg = f"{int(max_prob * 100)} % de chance de pluie dans les {days} prochains jours."
        if max_prob > 0.7:
            rec = "Risque de lessivage élevé. Repousser les traitements phytosanitaires."
        elif max_prob < 0.2:
            rec = "Conditions sèches attendues. Bon moment pour les traitements phyto."
        else:
            rec = "Vigilance recommandée pour les opérations au champ."

        return {**probs, "message": msg, "recommendation": rec}

    def _severity(self, spi: float) -> str:
        """
        Interprète la valeur du SPI pour donner un niveau de sévérité.

        Args:
            spi (float): Valeur de l'indice SPI calculé par spi().

        Returns:
            str: Niveau de sévérité parmi :
                - 'no_drought' : SPI supérieur à 1.0 (période anormalement humide)
                - 'mild'       : -1.0 <= SPI <= 1.0 (conditions normales)
                - 'moderate'   : -1.5 <= SPI < -1.0
                - 'severe'     : SPI < -1.5
        """
        if spi > 1.0:
            return "no_drought"
        elif -1.0 <= spi <= 1.0:
            return "mild"
        elif -1.5 <= spi < -1.0:
            return "moderate"
        elif spi < -1.5:
            return "severe"
        return "unknown"

    # ----------------------------------------------------------------
    # Méthodes dépréciées (anciens noms publics)
    # ----------------------------------------------------------------

    def drought_index(self, method: str = "spi", window_months: int = 3) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.2.0.

        Utilisez ``drought(method, window)`` à la place.

        Args:
            method (str): Méthode de calcul.
            window_months (int): Ancien nom de ``window``.

        Returns:
            dict: Résultats de l'indice de sécheresse.
        """
        warnings.warn(
            "Risk.drought_index() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez drought() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.drought(method=method, window=window_months)

    def markov_transition(self, threshold_mm: float = 1.0) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.2.0.

        Utilisez ``markov(thresh)`` à la place.

        Args:
            threshold_mm (float): Ancien nom de ``thresh``.

        Returns:
            dict: Probabilités de transition de Markov.
        """
        warnings.warn(
            "Risk.markov_transition() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez markov() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.markov(thresh=threshold_mm)

    def hurst_exponent(self, window: int = 1095) -> float:
        """
        Ancienne méthode publique. Dépréciée depuis v1.2.0.

        Utilisez ``hurst(window)`` à la place.

        Args:
            window (int): Taille maximale de la fenêtre d'analyse.

        Returns:
            float: Exposant de Hurst H.
        """
        warnings.warn(
            "Risk.hurst_exponent() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez hurst() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.hurst(window=window)

    def rain_probability(self, days_ahead: int = 1, min_rainfall_mm: float = 1.0) -> dict:
        """
        Ancienne méthode publique. Dépréciée depuis v1.2.0.

        Utilisez ``rain_prob(days, min_mm)`` à la place.

        Args:
            days_ahead (int): Ancien nom de ``days``.
            min_rainfall_mm (float): Ancien nom de ``min_mm``.

        Returns:
            dict: Probabilité de pluie et recommandations.
        """
        warnings.warn(
            "Risk.rain_probability() est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez rain_prob() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.rain_prob(days=days_ahead, min_mm=min_rainfall_mm)

    # ----------------------------------------------------------------
    # Propriétés de rétrocompatibilité (anciens noms d'attributs)
    # ----------------------------------------------------------------

    @property
    def rainfall_historical(self) -> pd.Series:
        """Ancien nom de ``rainfall``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "Risk.rainfall_historical est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Risk.rainfall à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.rainfall

    @rainfall_historical.setter
    def rainfall_historical(self, value: pd.Series) -> None:
        """Ancien setter de ``rainfall``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "Risk.rainfall_historical est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Risk.rainfall à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.rainfall = value

    @property
    def forecast_data(self) -> pd.DataFrame:
        """Ancien nom de ``forecast``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "Risk.forecast_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Risk.forecast à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.forecast

    @forecast_data.setter
    def forecast_data(self, value: pd.DataFrame) -> None:
        """Ancien setter de ``forecast``. Déprécié depuis v1.2.0."""
        warnings.warn(
            "Risk.forecast_data est obsolète et sera supprimé dans "
            "KadiPy v2.0. Utilisez Risk.forecast à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        self.forecast = value


# ----------------------------------------------------------------
# Rétrocompatibilité au niveau du module : RiskIndicators -> Risk
# ----------------------------------------------------------------

_DEPRECATED = {
    "RiskIndicators": ("Risk", Risk),
}


def __getattr__(name: str):
    """
    Intercepte les anciens noms exportés depuis ce module.

    Args:
        name (str): Nom du symbole demandé.

    Returns:
        object: La cible correspondant au nouveau nom.

    Raises:
        AttributeError: Si le nom n'est ni courant ni un ancien nom connu.
    """
    if name in _DEPRECATED:
        new_name, target = _DEPRECATED[name]
        warnings.warn(
            f"kadi.weather.risk.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return target
    raise AttributeError(
        f"Le module 'kadi.weather.risk' n'a pas d'attribut '{name}'."
    )
