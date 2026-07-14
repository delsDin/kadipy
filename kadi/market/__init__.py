"""
Point d'entrée du module kadi.market.

Contient la classe principale Market qui agrège toutes les fonctionnalités
(pricing, forecasting, logistics, decision_support) et valide les paramètres
d'entrée avant d'initialiser les sous-modules.
"""

import pandas as pd

from .pricing import MarketPricing
from .forecasting import MarketForecasting
from .logistics import MarketLogistics
from .decision_support import DecisionSupport
from .data_ingestion import WFPDataBridgesClient

# Bornes géographiques du Bénin (avec marge de ~2° pour les zones frontalières)
_LAT_MIN = 6.0
_LAT_MAX = 12.5
_LON_MIN = 0.5
_LON_MAX = 3.9


def _valider_coordonnees(lat: float, lon: float, location: str):
    """
    Valide que les coordonnées GPS sont cohérentes avec le territoire béninois.

    Args:
        lat (float): Latitude à valider.
        lon (float): Longitude à valider.
        location (str): Nom du lieu (pour le message d'erreur).

    Raises:
        TypeError: Si lat ou lon ne sont pas des nombres.
        ValueError: Si les coordonnées sont hors de la zone du Bénin.
    """
    # Vérification du type de la latitude
    if not isinstance(lat, (int, float)):
        raise TypeError(
            f"La latitude doit être un nombre. "
            f"Reçu : {type(lat).__name__} ('{lat}')."
        )

    # Vérification du type de la longitude
    if not isinstance(lon, (int, float)):
        raise TypeError(
            f"La longitude doit être un nombre. "
            f"Reçu : {type(lon).__name__} ('{lon}')."
        )

    # Vérification des bornes de la latitude
    if not (_LAT_MIN <= lat <= _LAT_MAX):
        raise ValueError(
            f"Latitude '{lat}' hors de la zone Bénin "
            f"(attendu entre {_LAT_MIN} et {_LAT_MAX})."
        )

    # Vérification des bornes de la longitude
    if not (_LON_MIN <= lon <= _LON_MAX):
        raise ValueError(
            f"Longitude '{lon}' hors de la zone Bénin "
            f"(attendu entre {_LON_MIN} et {_LON_MAX})."
        )


def _valider_location(location: str):
    """
    Valide que le nom du lieu est une chaîne non vide.

    Args:
        location (str): Le nom du lieu à valider.

    Raises:
        TypeError: Si location n'est pas une chaîne de caractères.
        ValueError: Si location est vide ou ne contient que des espaces.
    """
    if not isinstance(location, str):
        raise TypeError(
            f"Le nom du lieu doit être une chaîne. "
            f"Reçu : {type(location).__name__}."
        )
    if not location.strip():
        raise ValueError("Le nom du lieu ne peut pas être vide.")


class Market:
    """
    Façade principale pour le module d'économie agricole de KadiPy.

    Agrège la tarification, la prévision, la logistique et l'aide à la
    décision dans une interface unique. Toutes les entrées sont validées
    à l'initialisation pour éviter des erreurs silencieuses dans les
    sous-modules.

    Fonctionnement sans clé API WFP :
        Toutes les méthodes sont utilisables même sans token WFP configuré.
        Les données retournées seront simulées (is_simulated=True,
        confidence_score=0.1). Cette configuration est normale pendant
        la phase de développement.

    Zone géographique :
        Ce module est conçu pour le Bénin uniquement (V1.0.0).
    """

    def __init__(self, lat: float, lon: float, location: str, env_file: str = ".env"):
        """
        Initialise le point central du marché pour un lieu au Bénin.

        Args:
            lat (float): Latitude du lieu (entre 6.0 et 12.5 degrés nord).
            lon (float): Longitude du lieu (entre 0.5 et 3.9 degrés est).
            location (str): Nom du lieu (ex: 'Abomey', 'Parakou'). Non vide.
            env_file (str, optional): Chemin vers le fichier .env contenant
                les variables d'environnement (ex: WFP_API_Token). Défaut : '.env'.

        Raises:
            TypeError: Si lat, lon ou location ne sont pas du bon type.
            ValueError: Si les coordonnées sont hors de la zone Bénin ou
                si le nom du lieu est vide.

        Exemples:
            >>> marche = Market(9.30, 2.08, "Parakou")
            >>> marche = Market(lat=6.36, lon=2.41, location="Cotonou")
        """
        # Validation des paramètres avant toute initialisation
        _valider_coordonnees(lat, lon, location)
        _valider_location(location)

        # Coordonnées et nom du lieu de référence
        self.lat = lat
        self.lon = lon
        self.location = location.strip()

        # Client d'ingestion des données de marché (WFP DataBridges + cache SQLite)
        self.data_client = WFPDataBridgesClient(env_file=env_file)

        # Module de tarification : normalisation, anomalies, agrégation
        self.pricing = MarketPricing(wfp_client=self.data_client)

        # Module de prévision des prix (séries temporelles)
        self.forecasting = MarketForecasting()

        # Module logistique : distances, coûts de transport
        self.logistics = MarketLogistics()

        # Module d'aide à la décision, connecté au pricing réel
        self.decision_support = DecisionSupport(
            forecasting_module=self.forecasting,
            logistics_module=self.logistics,
            pricing_module=self.pricing,  # Injection des vrais prix
        )

    def price_crop(
        self,
        crop: str,
        days_back: int = 90,
        normalize_to_xof_kg: bool = True,
    ) -> dict:
        """
        API de haut niveau : récupère, normalise et résume les prix d'une culture.

        Effectue le pipeline complet en une seule méthode :
        1. Récupération des prix (cache SQLite ou API WFP)
        2. Normalisation vers XOF/kg
        3. Détection des anomalies
        4. Calcul des statistiques descriptives

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days_back (int, optional): Nombre de jours d'historique à récupérer.
                Défaut : 90 jours.
            normalize_to_xof_kg (bool, optional): Si True, normalise les prix
                vers XOF/kg. Défaut : True.

        Returns:
            dict: Dictionnaire contenant :
                - 'crop'            : code de la culture
                - 'market'          : nom du lieu de référence
                - 'prix_median'     : prix médian en XOF/kg
                - 'prix_min'        : prix minimum observé
                - 'prix_max'        : prix maximum observé
                - 'prix_moyen'      : prix moyen
                - 'nb_observations' : nombre de points de données
                - 'nb_anomalies'    : nombre d'anomalies détectées
                - 'is_simulated'    : True si les données sont fictives
                - 'confidence_score': score de confiance 0.0 à 1.0
                - 'source'          : source des données
                - 'donnees'         : DataFrame complet avec toutes les colonnes
        """
        # Récupération des données via le module pricing (qui gère cache + API)
        df = self.pricing.fetch_prices(crop, self.location, days_back=days_back)

        if df.empty:
            return {
                "crop": crop,
                "market": self.location,
                "prix_median": None,
                "prix_min": None,
                "prix_max": None,
                "prix_moyen": None,
                "nb_observations": 0,
                "nb_anomalies": 0,
                "is_simulated": True,
                "confidence_score": 0.0,
                "source": "none",
                "donnees": df,
            }

        # Normalisation vers XOF/kg si demandée
        if normalize_to_xof_kg and "unit" in df.columns:
            df["price"] = df.apply(
                lambda row: self.pricing.normalize_units(
                    row["price"],
                    row.get("unit", "XOF/kg"),
                    crop=crop,
                ),
                axis=1,
            )

        # Détection des anomalies de prix
        df = self.pricing.detect_anomalies(df)

        # Comblage des valeurs manquantes par interpolation linéaire
        df = self.pricing.interpolate_gaps(df)

        # Extraction des statistiques descriptives
        prix = df["price"].dropna()
        nb_anomalies = int(df["is_anomaly"].sum()) if "is_anomaly" in df.columns else 0

        # Source et score de confiance
        source = df["source"].iloc[-1] if "source" in df.columns else "unknown"
        confidence = (
            float(df["confidence_score"].iloc[-1])
            if "confidence_score" in df.columns
            else 0.0
        )
        est_simule = bool(df["is_simulated"].any()) if "is_simulated" in df.columns else True

        return {
            "crop": crop,
            "market": self.location,
            "prix_median": round(float(prix.median()), 2),
            "prix_min": round(float(prix.min()), 2),
            "prix_max": round(float(prix.max()), 2),
            "prix_moyen": round(float(prix.mean()), 2),
            "nb_observations": len(prix),
            "nb_anomalies": nb_anomalies,
            "is_simulated": est_simule,
            "confidence_score": round(confidence, 3),
            "source": source,
            "donnees": df,
        }

    def predict_price(
        self,
        crop: str,
        days_ahead: int = 7,
        confidence_interval: float = 0.9,
        days_back: int = 365,
    ) -> dict:
        """
        API de haut niveau : prédit le prix futur d'une culture sur ce marché.

        Cette méthode orchestre le pipeline complet en un seul appel :
        1. Récupération de l'historique de prix (cache SQLite ou API WFP)
        2. Normalisation vers XOF/kg
        3. Prévision par régression linéaire avec features saisonnières
        4. Sauvegarde de la prévision dans la table SQLite price_predictions

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days_ahead (int, optional): Horizon de prévision en jours.
                Défaut : 7 jours. La précision décroît avec l'horizon.
            confidence_interval (float, optional): Niveau de confiance pour
                l'intervalle de prévision (0.9 ou 0.95). Défaut : 0.9.
            days_back (int, optional): Nombre de jours d'historique à utiliser
                pour entraîner le modèle. Défaut : 365 jours.

        Returns:
            dict: Dictionnaire contenant :
                - 'crop'             : code de la culture
                - 'market'           : nom du marché de référence
                - 'predicted_price'  : prix prédit en XOF/kg
                - 'low_90'           : borne inférieure de l'intervalle
                - 'high_90'          : borne supérieure de l'intervalle
                - 'confidence'       : niveau de confiance (0.9 ou 0.95)
                - 'model_used'       : identifiant du modèle
                - 'rmse'             : RMSE réel en XOF/kg (None si simulé)
                - 'is_simulated'     : True si les données source sont simulées
                - 'confidence_score' : score de fiabilité 0.0 à 1.0
                - 'nb_history_pts'   : nombre de points d'historique utilisés
                - 'days_ahead'       : horizon de prévision utilisé
        """
        # --- Étape 1 : récupération de l'historique de prix ---
        df_historique = self.pricing.fetch_prices(
            crop, self.location, days_back=days_back
        )

        # Normalisation vers XOF/kg si les données sont disponibles
        if not df_historique.empty and "unit" in df_historique.columns:
            df_historique["price"] = df_historique.apply(
                lambda row: self.pricing.normalize_units(
                    row["price"],
                    row.get("unit", "XOF/kg"),
                    crop=crop,
                ),
                axis=1,
            )

        # --- Étape 2 : prévision par le module forecasting ---
        prediction = self.forecasting.predict_price(
            crop=crop,
            market=self.location,
            days_ahead=days_ahead,
            confidence_interval=confidence_interval,
            historique=df_historique if not df_historique.empty else None,
        )

        # --- Étape 3 : sauvegarde dans la table SQLite price_predictions ---
        try:
            from kadi.market._cache import sauvegarder_prediction
            sauvegarder_prediction(
                market=self.location.lower(),
                crop=crop,
                prediction=prediction,
            )
        except Exception as exc:
            # L'échec de la sauvegarde ne bloque pas le retour de la prévision
            import logging
            logging.getLogger(__name__).warning(
                f"Impossible de sauvegarder la prévision en cache SQLite : {exc}"
            )

        # --- Étape 4 : enrichissement du résultat avec le contexte ---
        prediction["crop"] = crop
        prediction["market"] = self.location

        return prediction

    def seasonality(
        self,
        crop: str,
        days_back: int = 730,
    ) -> dict:
        """
        Calcule l'indice saisonnier mensuel des prix d'une culture sur ce marché.

        Cette méthode de haut niveau orchestre deux étapes :
        1. Récupération de l'historique de prix sur la période demandée
        2. Calcul des 12 indices saisonniers par la méthode des ratios

        Un historique d'au moins 12 mois est recommandé pour des résultats
        fiables. La valeur par défaut de ``days_back`` (730 jours, soit 2 ans)
        vise à maximiser la fiabilité des indices calculés.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days_back (int, optional): Nombre de jours d'historique à
                récupérer pour le calcul. Défaut : 730 (2 ans).
                Utiliser 365 si seule la dernière année est pertinente.

        Returns:
            dict: Résultat de ``MarketPricing.seasonality()``, contenant :

                - ``indices`` (dict[int, float | None]) : les 12 indices
                  saisonniers, indexés par mois (1=jan, 12=déc). None si
                  données insuffisantes pour un mois.
                - ``mois_pic`` (list[int]) : mois dont l'indice dépasse 1.05.
                - ``mois_creux`` (list[int]) : mois dont l'indice est sous 0.95.
                - ``prix_moyen_global`` (float) : prix moyen de référence en XOF/kg.
                - ``prix_moyen_par_mois`` (dict[int, float | None]) : prix brut
                  moyen par mois.
                - ``nb_observations`` (int) : nombre d'observations utilisées.
                - ``nb_mois_couverts`` (int) : mois avec données suffisantes.
                - ``confiance`` (float) : score de fiabilité de 0.0 à 1.0.
                - ``is_simulated`` (bool) : True si les données sont simulées.
                - ``message`` (str | None) : avertissement si données insuffisantes.
        """
        # --- Étape 1 : récupération de l'historique de prix ---
        df_historique = self.pricing.fetch_prices(
            crop, self.location, days_back=days_back
        )

        # --- Étape 2 : délégation du calcul au module pricing ---
        return self.pricing.seasonality(historique=df_historique)
