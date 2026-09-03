"""
Point d'entrée du module kadi.market.

Contient la classe principale Market qui agrège toutes les fonctionnalités
(pricing, forecasting, logistics, decision_support) et valide les paramètres
d'entrée avant d'initialiser les sous-modules.

Phase 4 : La façade Market accepte maintenant un paramètre optionnel
weather_session (kadi.weather.WeatherSession) pour activer l'ajustement
climatique dans la logistique et l'aide à la décision.
"""

import pandas as pd

from .pricing import MarketPricing
from .forecasting import MarketForecasting
from .logistics import MarketLogistics
from .decision_support import DecisionSupport

# Nouveaux clients API réels (remplacement du stub data_ingestion)
from kadi._sources import WFPClient, ExchangeRateClient

from kadi.config import CONFIG

# Bornes géographiques lues depuis la configuration centrale (CONFIG["weather"]["gps_validation_bbox"]).
# Les valeurs de repli correspondent aux bornes officielles définies dans config.py.
# Ne pas modifier ces lignes directement : mettre à jour config.py à la place.
_bbox = CONFIG.get("weather", {}).get("gps_validation_bbox", {})
_LAT_MIN = _bbox.get("min_lat", 2.5)
_LAT_MAX = _bbox.get("max_lat", 12.5)
_LON_MIN = _bbox.get("min_lon", -1.5)
_LON_MAX = _bbox.get("max_lon", 4.0)



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

    def __init__(
        self,
        lat: float,
        lon: float,
        location: str,
        weather_session=None,
        simulated: bool = False,
    ):
        """
        Initialise le point central du marché pour un lieu au Bénin.

        Phase 4 : accepte un weather_session optionnel pour activer
        l'ajustement climatique dans la logistique (gamma_route dynamique,
        perte de qualité variable) et l'aide à la décision.

        Les clients API (WFP HAPI, Frankfurter) sont instanciés automatiquement.
        Configurez les variables d'environnement HAPI_APP_IDENTIFIER, HAPI_API_URL
        et FRANKFURTER_API_URL pour contrôler leur comportement.

        Le paramètre ``simulated`` permet de forcer le mode simulation pour
        tous les appels de prix (études, tests, démonstrations sans réseau).
        Quand simulated=True, aucun appel HTTP n'est effectué : les prix
        retournés sont générés mathématiquement et clairement marqués
        ``is_simulated=True, confidence_score=0.1``.

        Args:
            lat (float): Latitude du lieu (entre 2.5 et 12.5 degrés nord).
            lon (float): Longitude du lieu (entre -1.5 et 4.0 degrés est).
            location (str): Nom du lieu (ex: 'Abomey', 'Parakou'). Non vide.
            weather_session (WeatherSession, optional): Session météo
                (kadi.weather.WeatherSession) pour l'ajustement climatique.
                Si None, pas d'ajustement météo (comportement V1).
            simulated (bool, optional): Si True, force le mode simulation pour
                tous les appels de prix. Aucune requête réseau ne sera effectuée.
                Utile pour les études, les démonstrations ou les tests hors ligne.
                Défaut : False (données réelles de l'API HAPI HumData).

        Raises:
            TypeError: Si lat, lon ou location ne sont pas du bon type.
            ValueError: Si les coordonnées sont hors de la zone Bénin ou
                si le nom du lieu est vide.

        Exemples:
            >>> # Mode données réelles (nécessite HAPI_APP_IDENTIFIER dans l'environnement)
            >>> marche = Market(9.30, 2.08, "Parakou")

            >>> # Mode simulation explicite (aucun réseau requis)
            >>> marche = Market(9.30, 2.08, "Parakou", simulated=True)

            >>> # Avec intégration météo :
            >>> from kadi.weather import WeatherSession
            >>> ws = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
            >>> marche = Market(9.30, 2.08, "Parakou", weather_session=ws)
        """
        # Validation des paramètres avant toute initialisation
        _valider_coordonnees(lat, lon, location)
        _valider_location(location)

        # Coordonnées et nom du lieu de référence
        self.lat = lat
        self.lon = lon
        self.location = location.strip()

        # Choix explicite du mode simulation
        # Quand True, aucun appel HTTP ne sera effectué pour les prix
        self.simulated = simulated

        if simulated:
            import logging as _logging
            _logging.getLogger(__name__).info(
                f"Market('{location}') : mode simulation activé. "
                "Tous les appels de prix retourneront des données fictives "
                "(is_simulated=True, confidence_score=0.1). "
                "Passez simulated=False pour utiliser les données réelles "
                "de l'API HAPI HumData (PAM)."
            )

        # Session météo optionnelle (Phase 4)
        self.weather_session = weather_session

        # Client de taux de change dynamiques (API Frankfurter)
        # Partagé avec MarketPricing pour les conversions USD/EUR -> XOF
        exchange_client = ExchangeRateClient()

        # Client d'ingestion des données de marché (API HAPI HumData / PAM)
        wfp_client = WFPClient()

        # Module de tarification : normalisation, anomalies, agrégation
        # Les deux clients et le mode simulation sont injectés
        self.pricing = MarketPricing(
            wfp_client=wfp_client,
            exchange_client=exchange_client,
            simulated=simulated,
        )

        # Module de prévision des prix (séries temporelles)
        self.forecasting = MarketForecasting()

        # Module logistique : distances, coûts de transport
        # La session météo est injectée pour ajuster gamma_route et la qualité
        self.logistics = MarketLogistics(weather_session=weather_session)

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
        simulated: bool = None,
    ) -> dict:
        """
        API de haut niveau : récupère, normalise et résume les prix d'une culture.

        Effectue le pipeline complet en une seule méthode :
        1. Récupération des prix (API HAPI HumData ou simulation)
        2. Normalisation vers XOF/kg
        3. Détection des anomalies
        4. Calcul des statistiques descriptives

        Le paramètre ``simulated`` de cette méthode surcharge le réglage
        global de l'instance (défini à l'initialisation de Market).
        Cela permet d'alterner les modes au sein de la même instance.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days_back (int, optional): Nombre de jours d'historique à récupérer.
                Défaut : 90 jours.
            normalize_to_xof_kg (bool, optional): Si True, normalise les prix
                vers XOF/kg. Défaut : True.
            simulated (bool, optional): Surcharge le mode simulation de l'instance.
                Si None, hérite de self.simulated. Défaut : None.

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
        # Résolution du mode simulation : paramètre local ou héritage de l'instance
        mode_simule = self.simulated if simulated is None else simulated

        # Récupération des données via le module pricing
        df = self.pricing.fetch_prices(
            crop, self.location, days_back=days_back, simulated=mode_simule
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
        simulated: bool = None,
    ) -> dict:
        """
        API de haut niveau : prédit le prix futur d'une culture sur ce marché.

        Cette méthode orchestre le pipeline complet en un seul appel :
        1. Récupération de l'historique de prix (API HAPI HumData ou simulation)
        2. Normalisation vers XOF/kg
        3. Prévision par régression linéaire avec features saisonnières
        4. Sauvegarde de la prévision dans la table SQLite price_predictions

        Le paramètre ``simulated`` surcharge le réglage global de l'instance.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days_ahead (int, optional): Horizon de prévision en jours.
                Défaut : 7 jours. La précision décroît avec l'horizon.
            confidence_interval (float, optional): Niveau de confiance pour
                l'intervalle de prévision (0.9 ou 0.95). Défaut : 0.9.
            days_back (int, optional): Nombre de jours d'historique à utiliser
                pour entraîner le modèle. Défaut : 365 jours.
            simulated (bool, optional): Surcharge le mode simulation de l'instance.
                Si None, hérite de self.simulated. Défaut : None.

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
        # Résolution du mode simulation : paramètre local ou héritage de l'instance
        mode_simule = self.simulated if simulated is None else simulated

        # --- Étape 1 : récupération de l'historique de prix ---
        df_historique = self.pricing.fetch_prices(
            crop, self.location, days_back=days_back, simulated=mode_simule
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
        simulated: bool = None,
    ) -> dict:
        """
        Calcule l'indice saisonnier mensuel des prix d'une culture sur ce marché.

        Cette méthode de haut niveau orchestre deux étapes :
        1. Récupération de l'historique de prix sur la période demandée
        2. Calcul des 12 indices saisonniers par la méthode des ratios

        Le paramètre ``simulated`` surcharge le réglage global de l'instance.

        Un historique d'au moins 12 mois est recommandé pour des résultats
        fiables. La valeur par défaut de ``days_back`` (730 jours, soit 2 ans)
        vise à maximiser la fiabilité des indices calculés.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice', 'cowpea').
            days_back (int, optional): Nombre de jours d'historique à
                récupérer pour le calcul. Défaut : 730 (2 ans).
                Utiliser 365 si seule la dernière année est pertinente.
            simulated (bool, optional): Surcharge le mode simulation de l'instance.
                Si None, hérite de self.simulated. Défaut : None.

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
        # Résolution du mode simulation : paramètre local ou héritage de l'instance
        mode_simule = self.simulated if simulated is None else simulated

        # --- Étape 1 : récupération de l'historique de prix ---
        df_historique = self.pricing.fetch_prices(
            crop, self.location, days_back=days_back, simulated=mode_simule
        )

        # --- Étape 2 : délégation du calcul au module pricing ---
        return self.pricing.seasonality(historique=df_historique)

    def assess_climate_risk(self, days_ahead: int = 7) -> dict:
        """
        Évalue le risque climatique courant pour la localisation du marché.

        Méthode de haut niveau qui agrège les indicateurs météo disponibles
        (pluie prévue et indice de sécheresse) depuis la session weather_session.

        Si aucun weather_session n'a été fourni à l'initialisation, retourne
        un dictionnaire indiquant l'absence de données météo.

        Args:
            days_ahead (int, optional): Horizon de prévision de pluie en jours.
                Défaut : 7 jours.

        Returns:
            dict: Dictionnaire contenant :
                - 'weather_available'  : bool : True si weather_session est actif
                - 'prob_pluie'         : dict : probabilités de pluie par jour
                - 'drought_index'      : dict : indice de sécheresse (SPI et sévérité)
                - 'recommendation'     : str : message de synthèse
                - 'prob_pluie_j1'      : float : probabilité de pluie demain (0 à 1)
                - 'drought_severity'   : str : sévérité de la sécheresse
        """
        if self.weather_session is None:
            # Aucun module météo injecté : retour neutre
            return {
                "weather_available": False,
                "prob_pluie": {},
                "drought_index": {},
                "recommendation": (
                    "Aucun module météo configuré. Fournissez un weather_session "
                    "à Market() pour activer l'analyse climatique."
                ),
                "prob_pluie_j1": 0.0,
                "drought_severity": "unknown",
            }

        # Récupération de la probabilité de pluie sur l'horizon demandé
        try:
            prob_pluie = self.weather_session.rain_probability(
                days_ahead=days_ahead, min_rainfall_mm=1.0
            )
            prob_j1 = float(prob_pluie.get("tomorrow", 0.0))
        except Exception:
            prob_pluie = {"message": "Données de prévision indisponibles."}
            prob_j1 = 0.0

        # Récupération de l'indice de sécheresse SPI
        try:
            drought = self.weather_session.drought_index(method="spi", window_months=3)
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

