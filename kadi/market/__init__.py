"""
Point d'entrée du module kadi.market.

Contient la classe principale Market qui agrège toutes les fonctionnalités
(pricing, forecasting, logistics, advisor) et valide les paramètres
d'entrée avant d'initialiser les sous-modules.

La façade Market accepte maintenant un paramètre optionnel
weather (kadi.weather.Weather) pour activer l'ajustement
climatique dans la logistique et l'aide à la décision.
"""

import pandas as pd
import warnings
from .pricing import Pricing
from .forecasting import Forecasting
from .logistics import Logistics
from .decision_support import Advisor

# Nouveaux clients API réels (remplacement du stub data_ingestion)
from kadi._sources import WFPClient, ExchangeRateClient

from kadi.config import CONFIG

# Noms publics officiels (v1.2.0+)
__all__ = [
    "Pricing",
    "Forecasting",
    "Logistics",
    "Advisor",
]

# Bornes géographiques lues depuis la configuration centrale (CONFIG["weather"]["gps_validation_bbox"]).
# Les valeurs de repli correspondent aux bornes officielles définies dans config.py.
# Ne pas modifier ces lignes directement : mettre à jour config.py à la place.
_bbox = CONFIG.get("weather", {}).get("gps_validation_bbox", {})
_LAT_MIN = _bbox.get("min_lat", 2.5)
_LAT_MAX = _bbox.get("max_lat", 12.5)
_LON_MIN = _bbox.get("min_lon", -1.5)
_LON_MAX = _bbox.get("max_lon", 4.0)

# Table de rétrocompatibilité : ancien nom -> nouveau nom (méthodes publiques)
_DEPRECATED_METHODS = {
    "price_crop": "price",
    "predict_price": "predict",
    "assess_climate_risk": "climate_risk"
}

def _validate_coordinates(lat: float, lon: float, location: str):
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


def _validate_location(location: str):
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
        Les données retournées seront simulées (is_sim=True,
        confidence_score=0.1). Cette configuration est normale pendant
        la phase de développement.

    Zone géographique :
        Ce module est conçu pour le Bénin uniquement.
    """

    def __init__(
        self,
        lat: float,
        lon: float,
        location: str,
        weather=None,
        sim: bool = False,
        **kwargs,
    ):
        """
        Initialise le point central du marché pour un lieu au Bénin.

        La session météo optionnelle (weather) permet d'activer
        l'ajustement climatique dans la logistique (gamma_route dynamique,
        perte de qualité variable) et l'aide à la décision.

        Les clients API (WFP HAPI, Frankfurter) sont instanciés automatiquement.
        Configurez les variables d'environnement HAPI_APP_IDENTIFIER, HAPI_API_URL
        et FRANKFURTER_API_URL pour contrôler leur comportement.

        Le paramètre ``sim`` permet de forcer le mode simulation pour
        tous les appels de prix (études, tests, démonstrations sans réseau).
        Quand sim=True, aucun appel HTTP n'est effectué : les prix
        retournés sont générés mathématiquement et clairement marqués
        ``is_sim=True, confidence_score=0.1``.

        Args:
            lat (float): Latitude du lieu (entre 2.5 et 12.5 degrés nord).
            lon (float): Longitude du lieu (entre -1.5 et 4.0 degrés est).
            location (str): Nom du lieu (ex: 'Abomey', 'Parakou'). Non vide.
            weather (Weather, optional): Session météo
                (kadi.weather.Weather) pour l'ajustement climatique.
                Si None, pas d'ajustement météo (comportement V1).
            sim (bool, optional): Si True, force le mode simulation pour
                tous les appels de prix. Aucune requête réseau ne sera effectuée.
                Utile pour les études, les démonstrations ou les tests hors ligne.
                Défaut : False (données réelles de l'API HAPI HumData).
            **kwargs: Anciens arguments (weather_session, simulated) pour rétrocompatibilité.

        Raises:
            TypeError: Si lat, lon ou location ne sont pas du bon type.
            ValueError: Si les coordonnées sont hors de la zone Bénin ou
                si le nom du lieu est vide.

        Exemples:
            >>> # Mode données réelles (nécessite HAPI_APP_IDENTIFIER dans l'environnement)
            >>> marche = Market(9.30, 2.08, "Parakou")

            >>> # Mode simulation explicite (aucun réseau requis)
            >>> marche = Market(9.30, 2.08, "Parakou", sim=True)

            >>> # Avec intégration météo :
            >>> from kadi.weather import Weather
            >>> ws = Weather(latitude=9.30, longitude=2.08, name="Parakou")
            >>> marche = Market(9.30, 2.08, "Parakou", weather=ws)
        """

        if "weather_session" in kwargs:
            weather = kwargs.pop("weather_session")
        if "simulated" in kwargs:
            sim = kwargs.pop("simulated")
        if "is_simulated" in kwargs:
            sim = kwargs.pop("is_simulated")
        
        # Validation des paramètres avant toute initialisation
        _validate_coordinates(lat, lon, location)
        _validate_location(location)

        # Coordonnées et nom du lieu de référence
        self.lat = lat
        self.lon = lon
        self.location = location.strip()

        # Choix explicite du mode simulation
        # Quand True, aucun appel HTTP ne sera effectué pour les prix
        self.sim = sim

        if sim:
            import logging as _logging
            _logging.getLogger(__name__).info(
                f"Market('{location}') : mode simulation activé. "
                "Tous les appels de prix retourneront des données fictives "
                "(is_sim=True, confidence_score=0.1). "
                "Passez sim=False pour utiliser les données réelles "
                "de l'API HAPI HumData (PAM)."
            )

        # Session météo optionnelle (Phase 4)
        self.weather = weather

        # Client de taux de change dynamiques (API Frankfurter)
        # Partagé avec MarketPricing pour les conversions USD/EUR -> XOF
        exchange_client = ExchangeRateClient()

        # Client d'ingestion des données de marché (API HAPI HumData / PAM)
        wfp_client = WFPClient()

        # Module de tarification : normalisation, anomalies, agrégation
        # Les deux clients et le mode simulation sont injectés
        self.pricing = Pricing(
            wfp=wfp_client,
            exchange=exchange_client,
            sim=sim,
        )

        # Module de prévision des prix (séries temporelles)
        self.forecast = Forecasting()

        # Module logistique : distances, coûts de transport
        # La session météo est injectée pour ajuster gamma_route et la qualité
        self.logistics = Logistics(weather = weather)

        # Module d'aide à la décision, connecté au pricing réel
        self.advisor = Advisor(
            forecast=self.forecast,
            logistics=self.logistics,
            pricing=self.pricing,  # Injection des vrais prix
        )

    @property
    def decision_support(self):
        """Propriété de rétrocompatibilité pour accéder au module d'aide à la décision."""
        return self.advisor


    # ------------------------------------------------------------------
    # Rétrocompatibilité : méthodes publiques renommées
    # ------------------------------------------------------------------

    def __getattr__(self, name: str):
        """Intercepte les accès aux anciens noms de méthodes publiques.

        Délègue vers le nouveau nom et émet un DeprecationWarning.

        Args:
            name (str): Nom de l'attribut ou méthode demandé.

        Returns:
            callable: La méthode correspondante sous son nouveau nom.

        Raises:
            AttributeError: Si le nom n'est ni nouveau ni ancien.
        """
        # Vérification dans la table de rétrocompatibilité
        if name in _DEPRECATED_METHODS:
            new_name = _DEPRECATED_METHODS[name]
            warnings.warn(
                f"Market.{name}() est obsolète et sera supprimé dans "
                f"KadiPy v2.0. Utilisez Market.{new_name}() à la place.",
                DeprecationWarning,
                stacklevel=2,
            )
            return getattr(self, new_name)
        raise AttributeError(f"'Market' n'a pas d'attribut '{name}'.")


    def price(
        self,
        crop: str,
        days: int = 90,
        normalize: bool = True,
        sim: bool = None,
        **kwargs,
    ) -> dict:
        """
        API de haut niveau : récupère, normalise et résume les prix d'une culture.

        Effectue le pipeline complet en une seule méthode :
        1. Récupération des prix (API HAPI HumData ou simulation)
        2. Normalisation vers XOF/kg
        3. Détection des anomalies
        4. Calcul des statistiques descriptives

        Le paramètre ``sim`` de cette méthode surcharge le réglage
        global de l'instance (défini à l'initialisation de Market).
        Cela permet d'alterner les modes au sein de la même instance.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days (int, optional): Nombre de jours d'historique à récupérer.
                Défaut : 90 jours.
            normalize (bool, optional): Si True, normalise les prix
                vers XOF/kg. Défaut : True.
            sim (bool, optional): Surcharge le mode simulation de l'instance.
                Si None, hérite de self.sim. Défaut : None.

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
                - 'is_sim'    : True si les données sont fictives
                - 'confidence_score': score de confiance 0.0 à 1.0
                - 'source'          : source des données
                - 'donnees'         : DataFrame complet avec toutes les colonnes
        """
        # Gestion de l'ancien nom de paramètre pour la rétrocompatibilité
        if "days_back" in kwargs:
            days = kwargs.pop("days_back")

        # Résolution du mode simulation : paramètre local ou héritage de l'instance
        mode_simule = self.sim if sim is None else sim

        # Récupération des données via le module pricing
        df = self.pricing.fetch(
            crop, self.location, days=days, sim=mode_simule
        )

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
                "is_sim": True,
                "is_simulated": True,
                "confidence_score": 0.0,
                "source": "none",
                "donnees": df,
            }

        # Normalisation vers XOF/kg si demandée
        if normalize and "unit" in df.columns:
            df["price"] = df.apply(
                lambda row: self.pricing.convert_unit(
                    row["price"],
                    row.get("unit", "XOF/kg"),
                    crop=crop,
                ),
                axis=1,
            )

        # Détection des anomalies de prix
        df = self.pricing.anomalies(df)

        # Comblage des valeurs manquantes par interpolation linéaire
        df = self.pricing.fill_gaps(df)

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
        est_simule = bool(df["is_sim"].any()) if "is_sim" in df.columns else True

        return {
            "crop": crop,
            "market": self.location,
            "prix_median": round(float(prix.median()), 2),
            "prix_min": round(float(prix.min()), 2),
            "prix_max": round(float(prix.max()), 2),
            "prix_moyen": round(float(prix.mean()), 2),
            "nb_observations": len(prix),
            "nb_anomalies": nb_anomalies,
            "is_sim": est_simule,
            "is_simulated": est_simule,
            "confidence_score": round(confidence, 3),
            "source": source,
            "donnees": df,
        }

    def predict(
        self,
        crop: str,
        ahead: int = 7,
        confidence_interval: float = 0.9,
        days: int = 365,
        sim: bool = None,
        **kwargs,
    ) -> dict:
        """
        API de haut niveau : prédit le prix futur d'une culture sur ce marché.

        Cette méthode orchestre le pipeline complet en un seul appel :
        1. Récupération de l'historique de prix (API HAPI HumData ou simulation)
        2. Normalisation vers XOF/kg
        3. Prévision par régression linéaire avec features saisonnières
        4. Sauvegarde de la prévision dans la table SQLite price_predictions

        Le paramètre ``sim`` surcharge le réglage global de l'instance.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            ahead (int, optional): Horizon de prévision en jours.
                Défaut : 7 jours. La précision décroît avec l'horizon.
            confidence_interval (float, optional): Niveau de confiance pour
                l'intervalle de prévision (0.9 ou 0.95). Défaut : 0.9.
            days (int, optional): Nombre de jours d'historique à utiliser
                pour entraîner le modèle. Défaut : 365 jours.
            sim (bool, optional): Surcharge le mode simulation de l'instance.
                Si None, hérite de self.sim. Défaut : None.
            **kwargs: Anciens arguments (days_ahead) gérés pour rétrocompatibilité.

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
                - 'is_sim'     : True si les données source sont simulées
                - 'confidence_score' : score de fiabilité 0.0 à 1.0
                - 'nb_history_pts'   : nombre de points d'historique utilisés
                - 'ahead'       : horizon de prévision utilisé
        """
        if "days_ahead" in kwargs:
            ahead = kwargs.pop("days_ahead")
        if "days_back" in kwargs:
            days = kwargs.pop("days_back")
            
        # Résolution du mode simulation : paramètre local ou héritage de l'instance
        mode_simule = self.sim if sim is None else sim

        # --- Étape 1 : récupération de l'historique de prix ---
        df_historique = self.pricing.fetch(
            crop, self.location, days=days, sim=mode_simule
        )

        # Normalisation vers XOF/kg si les données sont disponibles
        if not df_historique.empty and "unit" in df_historique.columns:
            df_historique["price"] = df_historique.apply(
                lambda row: self.pricing.convert_unit(
                    row["price"],
                    row.get("unit", "XOF/kg"),
                    crop=crop,
                ),
                axis=1,
            )

        # --- Étape 2 : prévision par le module forecasting ---
        prediction = self.forecast.predict(
            crop=crop,
            market=self.location,
            ahead = ahead,
            ci = confidence_interval,
            hist = df_historique if not df_historique.empty else None,
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

        # Rétrocompatibilité : synchronisation sim et is_simulated
        if "is_simulated" in prediction and "sim" not in prediction:
            prediction["sim"] = prediction["is_simulated"]
        elif "sim" in prediction and "is_simulated" not in prediction:
            prediction["is_simulated"] = prediction["sim"]

        return prediction

    def seasonality(
        self,
        crop: str,
        days: int = 730,
        sim: bool = None,
        **kwargs,
    ) -> dict:
        """
        Calcule l'indice saisonnier mensuel des prix d'une culture sur ce marché.

        Cette méthode de haut niveau orchestre deux étapes :
        1. Récupération de l'historique de prix sur la période demandée
        2. Calcul des 12 indices saisonniers par la méthode des ratios

        Le paramètre ``sim`` surcharge le réglage global de l'instance.

        Un historique d'au moins 12 mois est recommandé pour des résultats
        fiables. La valeur par défaut de ``days`` (730 jours, soit 2 ans en arrière)
        vise à maximiser la fiabilité des indices calculés.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days (int, optional): Nombre de jours d'historique à
                récupérer pour le calcul. Défaut : 730 (2 ans).
                Utiliser 365 si seule la dernière année est pertinente.
            sim (bool, optional): Surcharge le mode simulation de l'instance.
                Si None, hérite de self.sim. Défaut : None.
            **kwargs: Anciens arguments (days_back) gérés pour rétrocompatibilité.

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
                - ``is_sim`` (bool) : True si les données sont simulées.
                - ``message`` (str | None) : avertissement si données insuffisantes.
        """
        if "days_back" in kwargs:
            days = kwargs.pop("days_back")
            
        # Résolution du mode simulation : paramètre local ou héritage de l'instance
        mode_simule = self.sim if sim is None else sim

        # --- Étape 1 : récupération de l'historique de prix ---
        df_historique = self.pricing.fetch(
            crop, self.location, days=days, sim=mode_simule
        )

        # --- Étape 2 : délégation du calcul au module pricing ---
        return self.pricing.seasonality(historique=df_historique)

    def climate_risk(self, ahead: int = 7, **kwargs) -> dict:
        """
        Évalue le risque climatique courant pour la localisation du marché.

        Méthode de haut niveau qui agrège les indicateurs météo disponibles
        (pluie prévue et indice de sécheresse) depuis la session weather.

        Si aucun weather n'a été fourni à l'initialisation, retourne
        un dictionnaire indiquant l'absence de données météo.

        Args:
            ahead (int, optional): Horizon de prévision de pluie en jours.
                Défaut : 7 jours.
            **kwargs: Anciens arguments (days_ahead) pour rétrocompatibilité.

        Returns:
            dict: Dictionnaire contenant :
                - 'weather_available'  : bool : True si weather est actif
                - 'prob_pluie'         : dict : probabilités de pluie par jour
                - 'drought_index'      : dict : indice de sécheresse (SPI et sévérité)
                - 'recommendation'     : str : message de synthèse
                - 'prob_pluie_j1'      : float : probabilité de pluie demain (0 à 1)
                - 'drought_severity'   : str : sévérité de la sécheresse
        """
        if "days_ahead" in kwargs:
            ahead = kwargs.pop("days_ahead")
        
        if self.weather is None:
            # Aucun module météo injecté : retour neutre
            return {
                "weather_available": False,
                "prob_pluie": {},
                "drought_index": {},
                "recommendation": (
                    "Aucun module météo configuré. Fournissez un weather "
                    "à Market() pour activer l'analyse climatique."
                ),
                "prob_pluie_j1": 0.0,
                "drought_severity": "unknown",
            }

        # Récupération de la probabilité de pluie sur l'horizon demandé
        try:
            prob_pluie = self.weather.rain_probability(
                ahead = ahead, min_rainfall_mm=1.0
            )
            prob_j1 = float(prob_pluie.get("tomorrow", 0.0))
        except Exception:
            prob_pluie = {"message": "Données de prévision indisponibles."}
            prob_j1 = 0.0

        # Récupération de l'indice de sécheresse SPI
        try:
            drought = self.weather.drought_index(method="spi", window_months=3)
            severity = drought.get("drought_severity", "unknown")
        except Exception:
            drought = {}
            severity = "unknown"

        # Construction d'un message de synthèse contextuel
        pct = int(prob_j1 * 100)
        if prob_j1 > 0.7:
            recommandation = (
                f"Risque de pluie élevé demain ({pct}%). "
                "Les coûts logistiques seront majorés (routes dégradées)."
            )
        elif prob_j1 > 0.3:
            recommandation = (
                f"Pluie modérée possible demain ({pct}%). "
                "Surveiller les conditions de transport."
            )
        else:
            recommandation = (
                f"Peu de pluie prévue demain ({pct}%). "
                "Conditions logistiques favorables."
            )

        if severity in ("moderate", "severe"):
            recommandation += (
                f" Sécheresse {severity} détectée (SPI). "
                "Anticiper une hausse des prix des cultures sensibles."
            )

        return {
            "weather_available": True,
            "prob_pluie": prob_pluie,
            "drought_index": drought,
            "recommendation": recommandation,
            "prob_pluie_j1": round(prob_j1, 3),
            "drought_severity": severity,
        }




_DEPRECATED = {
    "MarketPricing":          ("Pricing",       Pricing),
    "MarketForecasting":      ("Forecasting",   Forecasting),
    "MarketLogistics":        ("Logistics",     Logistics),
    "MarketPricing":          ("Pricing",       Pricing)
}


def __getattr__(name: str):
    """
    Intercepte les anciens noms exportés depuis kadi.weather.

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
            f"kadi.market.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return target
    raise AttributeError(
        f"Le module 'kadi.market' n'a pas d'attribut '{name}'."
    )

