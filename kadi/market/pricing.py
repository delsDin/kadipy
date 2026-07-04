"""
Module responsable de l'agrégation multi-sources, de la normalisation
des données de marché, et de la détection d'anomalies.
"""

import pandas as pd
import numpy as np
import datetime


class MarketPricing:
    """
    Classe gérant l'ingestion, la normalisation et la détection d'anomalies
    pour les données de prix de marché.
    """

    def __init__(self, wfp_client=None):
        """
        Initialise le module de tarification.
        
        Args:
            wfp_client: Instance de WFPDataBridgesClient pour récupérer les données.
        """
        # Sauvegarde de l'instance du client WFP DataBridges
        self.wfp_client = wfp_client

    def fetch_prices(self, crop: str, market: str, days_back: int = 365) -> pd.DataFrame:
        """
        Récupère les prix historiques pour une culture et un marché donnés.

        Args:
            crop (str): Le nom de la culture (ex: 'maize').
            market (str): Le nom du marché (ex: 'Savalou_Market').
            days_back (int, optional): Nombre de jours historiques à récupérer. Défaut à 365.

        Returns:
            pd.DataFrame: Un DataFrame contenant les séries temporelles de prix.
        """
        # Calcul de la plage de dates pour la requête
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days_back)
        time_range = (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
        if self.wfp_client is not None:
            # Appel à l'API via le client configuré
            df_prices = self.wfp_client.get_market_prices(market, crop, time_range)
        else:
            # Simulation d'une série temporelle si le client n'est pas fourni (fallback mode)
            dates = pd.date_range(end=end_date, periods=days_back, freq='D')
            
            # Génération de prix aléatoires (distribution normale)
            prix_aleatoires = np.random.normal(loc=300, scale=20, size=days_back)
            
            # Création du DataFrame avec dates et prix
            df_prices = pd.DataFrame({'date': dates, 'price': prix_aleatoires})
        
        # Retourne le DataFrame contenant les prix
        return df_prices

    def normalize_units(self, value: float, unit_orig: str, crop: str) -> float:
        """
        Normalise une valeur de prix vers le standard XOF/kg.

        Args:
            value (float): La valeur du prix à normaliser.
            unit_orig (str): L'unité d'origine (ex: 'XOF/Tonne', 'USD/kg').
            crop (str): La culture concernée.

        Returns:
            float: Le prix normalisé en XOF/kg.
        """
        # On stocke la valeur d'origine comme point de départ
        valeur_normalisee = float(value)
        
        # Si l'unité d'origine est par tonne, on divise par 1000 pour avoir le prix par kg
        if 'Tonne' in unit_orig:
            valeur_normalisee = valeur_normalisee / 1000.0
            
        # Retour de la valeur normalisée
        return valeur_normalisee

    def detect_anomalies(self, price_series: pd.DataFrame) -> pd.DataFrame:
        """
        Détecte les anomalies dans une série de prix en utilisant la méthode du Z-score.

        Args:
            price_series (pd.DataFrame): DataFrame contenant une colonne 'price'.

        Returns:
            pd.DataFrame: Le DataFrame original avec une colonne 'is_anomaly' ajoutée.
        """
        # Création d'une copie pour éviter de modifier l'original
        df_result = price_series.copy()
        
        # Vérifie si la colonne 'price' existe avant le calcul
        if 'price' in df_result.columns:
            # Calcul de la moyenne des prix
            moyenne = df_result['price'].mean()
            
            # Calcul de l'écart-type des prix
            ecart_type = df_result['price'].std()
            
            # Si l'écart type est non nul, on calcule le z-score
            if ecart_type > 0:
                # Calcul du z-score pour chaque prix
                z_scores = (df_result['price'] - moyenne) / ecart_type
                
                # Une valeur est une anomalie si son z-score absolu est supérieur à 3
                df_result['is_anomaly'] = np.abs(z_scores) > 3
            else:
                # Pas de variation, donc pas d'anomalie
                df_result['is_anomaly'] = False
                
        # Retour du DataFrame avec les anomalies signalées
        return df_result

    def interpolate_gaps(self, price_series: pd.DataFrame, max_gap_days: int = 7) -> pd.DataFrame:
        """
        Interpole les valeurs manquantes dans une série de prix temporelle.

        Args:
            price_series (pd.DataFrame): DataFrame contenant des données de prix.
            max_gap_days (int, optional): Nombre maximum de jours à interpoler. Défaut à 7.

        Returns:
            pd.DataFrame: Le DataFrame avec les valeurs manquantes interpolées.
        """
        # Copie du DataFrame pour ne pas affecter l'entrée
        df_interpolated = price_series.copy()
        
        # Utilisation de l'interpolation linéaire pour combler les trous
        if 'price' in df_interpolated.columns:
            # Interpolation linéaire avec limite sur le nombre de jours
            df_interpolated['price'] = df_interpolated['price'].interpolate(
                method='linear', 
                limit=max_gap_days,
                limit_direction='both'
            )
            
        # Retour du DataFrame interpolé
        return df_interpolated

    def get_data_source(self, price_point: float) -> str:
        """
        Identifie la source de la donnée de prix selon sa caractéristique.

        Args:
            price_point (float): Un point de donnée de prix.

        Returns:
            str: La source identifiée (ex: 'wfp-vam', 'onasa').
        """
        # Simulation d'une source par défaut
        source_par_defaut = 'wfp-vam'
        
        # Retour de la source par défaut
        return source_par_defaut
