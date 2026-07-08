"""
Module responsable de l'agrégation multi-sources, de la normalisation
des données de marché, et de la détection d'anomalies de prix.
"""

import pandas as pd
import numpy as np
import datetime
import logging

from kadi.market._normalization import (
    EXCHANGE_RATES_DEFAULT,
    get_container_weight_kg,
)

logger = logging.getLogger(__name__)

# Taux de change par défaut (remplacés par config.EXCHANGE_RATES si disponibles)
_EXCHANGE_RATES = EXCHANGE_RATES_DEFAULT


class MarketPricing:
    """
    Classe gérant l'ingestion, la normalisation et la détection d'anomalies
    pour les données de prix de marché agricole au Bénin.
    """

    def __init__(self, wfp_client=None):
        """
        Initialise le module de tarification.

        Args:
            wfp_client: Instance de WFPDataBridgesClient pour récupérer les données.
                Si None, le module génère des données de simulation en fallback.
        """
        # Instance du client WFP DataBridges
        self.wfp_client = wfp_client

    def fetch_prices(self, crop: str, market: str, days_back: int = 365) -> pd.DataFrame:
        """
        Récupère les prix historiques pour une culture et un marché donnés.

        Le DataFrame retourné contient toujours une colonne ``is_simulated``
        indiquant si les données proviennent d'une source réelle (False)
        ou d'une simulation de secours (True).

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice').
            market (str): Nom normalisé du marché (ex: 'cotonou').
            days_back (int, optional): Nombre de jours d'historique. Défaut à 365.

        Returns:
            pd.DataFrame: DataFrame avec 'date', 'price', 'unit', 'is_simulated'.
        """
        # Calcul de la plage de dates pour la requête API
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days_back)
        time_range = (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

        if self.wfp_client is not None:
            # Appel au client WFP (qui gère lui-même le retry et le fallback)
            df_prices = self.wfp_client.get_market_prices(market, crop, time_range)
        else:
            # Pas de client configuré : on génère des données de simulation
            logger.warning(
                "Aucun client WFP configuré. Données simulées utilisées pour "
                f"{crop} / {market}."
            )
            dates = pd.date_range(end=end_date, periods=days_back, freq="D")
            prix_aleatoires = np.random.normal(loc=300, scale=20, size=days_back)
            df_prices = pd.DataFrame(
                {
                    "date": dates,
                    "price": prix_aleatoires,
                    "unit": "XOF/kg",
                    "is_simulated": True,
                }
            )

        return df_prices

    def normalize_units(self, value: float, unit_orig: str, crop: str = None) -> float:
        """
        Convertit une valeur de prix vers le standard XOF/kg.

        Gère les conversions suivantes :
        - XOF/Tonne  -> XOF/kg (division par 1000)
        - USD/kg     -> XOF/kg (multiplication par le taux de change)
        - EUR/kg     -> XOF/kg (multiplication par le taux de change)
        - XOF/sac    -> XOF/kg (division par le poids du sac en kg)
        - XOF/boisseau -> XOF/kg (division par le poids du boisseau)
        - XOF/tine   -> XOF/kg
        - XOF/caisse -> XOF/kg (pour les produits frais comme la tomate)
        - XOF/kg     -> sans changement (déjà à l'unité standard)

        Si l'unité est inconnue, la valeur est retournée sans modification
        et un avertissement est enregistré.

        Args:
            value (float): La valeur du prix à convertir.
            unit_orig (str): L'unité d'origine (ex: 'XOF/Tonne', 'USD/kg', 'XOF/sac').
            crop (str, optional): Code de la culture, utilisé pour les poids
                de contenants spécifiques (ex: poids d'un sac de maïs vs riz).

        Returns:
            float: Le prix normalisé en XOF/kg.
        """
        valeur = float(value)

        # Normalisation de l'unité pour la comparaison
        unite = unit_orig.strip().lower()

        # --- Conversion des tonnes ---
        if "tonne" in unite or "/t" == unite[-2:]:
            # 1 tonne = 1000 kg
            return valeur / 1000.0

        # --- Conversion des devises étrangères ---
        if unite.startswith("usd"):
            # USD vers XOF
            taux = _EXCHANGE_RATES.get("USD_TO_XOF", 620.0)
            return valeur * taux

        if unite.startswith("eur"):
            # EUR vers XOF (taux fixe UEMOA)
            taux = _EXCHANGE_RATES.get("EUR_TO_XOF", 655.957)
            return valeur * taux

        # --- Conversion des contenants locaux ---
        for conteneur in ("sac", "boisseau", "tine", "caisse", "boite", "panier"):
            if conteneur in unite:
                poids_kg = get_container_weight_kg(conteneur, crop)
                if poids_kg > 0:
                    return valeur / poids_kg
                # Poids inconnu : avertissement et valeur inchangée
                logger.warning(
                    f"Poids inconnu pour le conteneur '{conteneur}' / culture '{crop}'. "
                    "Le prix est retourné sans conversion."
                )
                return valeur

        # --- Unité déjà en XOF/kg ---
        if "xof/kg" in unite or unite == "kg":
            return valeur

        # --- Unité inconnue ---
        logger.warning(
            f"Unité inconnue : '{unit_orig}'. "
            "Le prix est retourné sans conversion."
        )
        return valeur

    def detect_anomalies(self, price_series: pd.DataFrame, z_threshold: float = 3.0) -> pd.DataFrame:
        """
        Détecte les anomalies dans une série de prix par la méthode du Z-score.

        Un prix est considéré comme anormal si son Z-score absolu dépasse
        le seuil configuré (par défaut : 3, soit environ 99.7% de la distribution).

        Args:
            price_series (pd.DataFrame): DataFrame contenant une colonne 'price'.
            z_threshold (float, optional): Seuil d'anomalie. Défaut à 3.0.

        Returns:
            pd.DataFrame: DataFrame original avec une colonne booléenne 'is_anomaly'.
        """
        # Copie pour ne pas modifier le DataFrame d'entrée
        df_result = price_series.copy()

        if "price" not in df_result.columns:
            logger.warning("Colonne 'price' absente du DataFrame. Aucune détection effectuée.")
            df_result["is_anomaly"] = False
            return df_result

        # Calcul des statistiques de la série
        moyenne = df_result["price"].mean()
        ecart_type = df_result["price"].std()

        if ecart_type > 0:
            # Calcul du Z-score pour chaque observation
            z_scores = (df_result["price"] - moyenne) / ecart_type
            # Marquage des anomalies au-delà du seuil
            df_result["is_anomaly"] = np.abs(z_scores) > z_threshold
        else:
            # Série constante : aucune variabilité, donc pas d'anomalie
            df_result["is_anomaly"] = False

        return df_result

    def interpolate_gaps(self, price_series: pd.DataFrame, max_gap_days: int = 7) -> pd.DataFrame:
        """
        Comble les valeurs manquantes dans une série de prix par interpolation linéaire.

        L'interpolation est limitée à un nombre configurable de jours consécutifs.
        Au-delà de cette limite, les valeurs restent manquantes (NaN) pour signaler
        un trou important dans les données.

        Args:
            price_series (pd.DataFrame): DataFrame contenant une colonne 'price'.
            max_gap_days (int, optional): Nombre maximum de jours à interpoler. Défaut à 7.

        Returns:
            pd.DataFrame: DataFrame avec les trous courts comblés par interpolation.
        """
        # Copie pour préserver le DataFrame d'entrée
        df_interpolated = price_series.copy()

        if "price" in df_interpolated.columns:
            # Interpolation linéaire avec limite sur la longueur des trous
            df_interpolated["price"] = df_interpolated["price"].interpolate(
                method="linear",
                limit=max_gap_days,
                limit_direction="both",
            )

        return df_interpolated

    def get_data_source(self, price_series: pd.DataFrame) -> str:
        """
        Identifie la source des données d'une série de prix.

        Si le DataFrame contient la colonne ``is_simulated``, la méthode
        retourne 'simulated' ou 'wfp-vam' selon le cas.

        Args:
            price_series (pd.DataFrame): DataFrame retourné par fetch_prices().

        Returns:
            str: La source identifiée ('wfp-vam', 'ratin', 'scrape-local', 'simulated').
        """
        # Vérification de la colonne is_simulated
        if "is_simulated" in price_series.columns:
            if price_series["is_simulated"].any():
                return "simulated"

        # Par défaut, on suppose WFP VAM (source primaire du V1)
        return "wfp-vam"
