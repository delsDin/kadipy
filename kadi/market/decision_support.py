"""
Module d'aide à la décision stratégique pour l'arbitrage spatial,
le stockage temporel et l'optimisation de portefeuille de cultures.

Phase 4 :
    - Horizon de stockage configurable dans storage_vs_sell_now().
    - Score de confiance global sur chaque recommandation.
    - portfolio_optimization() utilise scipy.optimize.linprog.
    - Les données météo (via weather_session injecté dans Market) alimentent
      directement la décision de stockage et de portefeuille.
"""

import logging

from kadi.config import CONFIG

logger = logging.getLogger(__name__)

# Seuil de rentabilité minimum pour recommander un transfert (configurable)
_SEUIL_RENTABILITE = CONFIG.get("logistics", {}).get("seuil_rentabilite_pct", 10.0)

# Horizon de stockage par défaut en mois (configurable dans config.py)
_HORIZON_MOIS_DEFAULT = CONFIG.get("market", {}).get("horizon_stockage_mois_default", 3)

# Rendements typiques au Bénin (tonnes par hectare), utilisés par portfolio_optimization
# Valeurs issues des rapports FAO/INSAE pour le centre-nord du Bénin.
_RENDEMENTS_BENIN = {
    "maize": 1.8,
    "sorghum": 1.2,
    "millet": 1.0,
    "rice": 2.5,
    "cowpea": 0.7,
    "soybean": 1.2,
    "yam": 8.0,
    "cassava": 12.0,
}


class DecisionSupport:
    """
    Classe convertissant les prévisions de prix et les données de marché
    en recommandations opérationnelles : arbitrage spatial, stockage,
    et optimisation de portefeuille de cultures.

    Phase 4 :
        Chaque recommandation inclut un 'confidence_score' (0.0 à 1.0)
        calculé à partir de la qualité des données de prix, du flag
        is_simulated et de la magnitude du gain estimé.

        portfolio_optimization() utilise scipy.optimize.linprog si disponible,
        avec un fallback heuristique si scipy est absent.
    """

    def __init__(
        self,
        forecasting_module=None,
        logistics_module=None,
        pricing_module=None,
    ):
        """
        Initialise le module d'aide à la décision.

        Args:
            forecasting_module: Instance de MarketForecasting pour les prévisions.
            logistics_module: Instance de MarketLogistics pour les coûts de transport.
            pricing_module: Instance de MarketPricing pour les prix réels du marché.
                Si None, les méthodes utiliseront des prix estimés par défaut.
        """
        # Références vers les sous-modules
        self.forecasting = forecasting_module
        self.logistics = logistics_module
        self.pricing = pricing_module

    # ------------------------------------------------------------------
    # Méthodes privées : données de prix et score de confiance
    # ------------------------------------------------------------------

    def _obtenir_prix_marche(self, crop: str, market: str) -> tuple:
        """
        Récupère le prix médian actuel pour une culture sur un marché donné.

        Interroge le module pricing pour obtenir les données réelles ou simulées.
        Retourne aussi le flag is_simulated et le confidence_score des données.

        Args:
            crop (str): Code de la culture (ex: 'maize').
            market (str): Nom normalisé du marché (ex: 'cotonou').

        Returns:
            tuple: (prix_median_xof_kg: float, is_simulated: bool, confidence: float)
        """
        if self.pricing is None:
            # Pas de module pricing : retour du prix de repli avec confiance nulle
            logger.warning(
                f"Pas de pricing_module disponible pour {crop}/{market}. "
                "Prix de repli utilisé (300 XOF/kg)."
            )
            return 300.0, True, 0.0

        try:
            # Récupération des 30 derniers jours de données
            df = self.pricing.fetch_prices(crop, market, days_back=30)

            if df.empty or "price" not in df.columns:
                return 300.0, True, 0.0

            # Calcul du prix médian (robuste aux outliers)
            prix_median = float(df["price"].median())

            # Flag de simulation : True si au moins une ligne est simulée
            est_simule = (
                bool(df["is_simulated"].any())
                if "is_simulated" in df.columns
                else True
            )

            # Score de confiance : median des scores individuels dans le DataFrame
            if "confidence_score" in df.columns:
                confiance = float(df["confidence_score"].median())
            else:
                confiance = 0.0 if est_simule else 0.8

            return prix_median, est_simule, confiance

        except Exception as e:
            logger.warning(
                f"Erreur lors de la récupération du prix {crop}/{market}: {e}. "
                "Prix de repli utilisé."
            )
            return 300.0, True, 0.0

    def _calculer_confidence_score(
        self,
        price_confidence: float,
        is_simulated: bool,
        gain_net_pct: float,
    ) -> float:
        """
        Calcule un score de confiance global sur une recommandation financière.

        Formule pondérée :
            score = 0.5 * price_confidence
                  + 0.3 * (0 si simulé, 1 si réel)
                  + 0.2 * min(1, |gain_net_pct| / 30)

        Le troisième terme représente l'idée qu'une recommandation avec un
        gain de +30% ou plus est plus convaincante qu'un gain de +1%.

        Args:
            price_confidence (float): Score de confiance des données de prix (0 à 1).
            is_simulated (bool): True si les données sont fictives.
            gain_net_pct (float): Gain net en % du capital investi (peut être négatif).

        Returns:
            float: Score de confiance global entre 0.0 et 1.0.
        """
        # Composante 1 : confiance des données de prix
        score_prix = 0.5 * max(0.0, min(1.0, price_confidence))

        # Composante 2 : données réelles vs simulées
        score_source = 0.3 * (0.0 if is_simulated else 1.0)

        # Composante 3 : magnitude relative du gain (30% = confiance max)
        score_magnitude = 0.2 * min(1.0, abs(gain_net_pct) / 30.0)

        score = score_prix + score_source + score_magnitude
        return round(max(0.0, min(1.0, score)), 3)

    # ------------------------------------------------------------------
    # API publique : recommandations de marché
    # ------------------------------------------------------------------

    def arbitrage_decision(
        self,
        crop: str,
        market_from: str,
        market_to: str,
        qty_tons: float,
    ) -> dict:
        """
        Évalue la rentabilité d'un transfert physique de marchandises entre deux marchés.

        Utilise les prix réels du marché (via pricing_module) pour calculer
        la marge brute. Les coûts logistiques (avec ajustement météo si disponible)
        sont calculés par le module logistics.

        Formule :
            Gain net = (prix_destination - prix_origine) * 1000 * qty - cout_transport

        Args:
            crop (str): La culture concernée (ex: 'maize').
            market_from (str): Le marché d'achat (ex: 'Parakou').
            market_to (str): Le marché de vente (ex: 'Cotonou').
            qty_tons (float): La quantité à transporter en tonnes métriques.

        Returns:
            dict: Dictionnaire contenant :
                - 'recommandation'       : 'TRANSPORTER' ou 'NE PAS TRANSPORTER'
                - 'gain_net_total_cfa'   : gain net total en XOF
                - 'gain_net_percent'     : gain net en % du capital investi
                - 'frais_logistiques_total' : coûts de transport totaux en XOF
                - 'prix_origine_xof_kg'  : prix au marché d'achat
                - 'prix_destination_xof_kg' : prix au marché de vente
                - 'is_simulated'         : True si les prix utilisés sont fictifs
                - 'confidence_score'     : score de confiance de la recommandation (0-1)
                - 'prob_pluie'           : probabilité de pluie utilisée (0 si sans météo)
        """
        # Récupération des prix réels (ou simulés) pour les deux marchés
        prix_origine_kg, simule_origine, conf_origine = self._obtenir_prix_marche(
            crop, market_from
        )
        prix_destination_kg, simule_destination, conf_destination = self._obtenir_prix_marche(
            crop, market_to
        )

        # Les données sont simulées si l'une des deux sources l'est
        est_simule = simule_origine or simule_destination

        # Confiance combinée sur les prix : moyenne des deux marchés
        price_confidence = (conf_origine + conf_destination) / 2.0

        # Marge brute par tonne (conversion kg -> tonne : *1000)
        marge_brute_tonne = (prix_destination_kg - prix_origine_kg) * 1000

        # Calcul des frais logistiques via le module dédié
        prob_pluie = 0.0
        if self.logistics:
            # On passe le crop pour activer la perte de qualité par culture
            res_logistics = self.logistics.calculate_transfer_cost(
                market_from, market_to, crop=crop
            )
            frais_logistiques_tonne = res_logistics["total_cost_cfa"]
            prob_pluie = res_logistics.get("prob_pluie", 0.0)
        else:
            frais_logistiques_tonne = 30000.0
            logger.warning(
                "Pas de logistics_module. Frais de transport de repli : 30 000 XOF/tonne."
            )

        # Gain net par tonne et total sur la quantité transportée
        gain_net_tonne = marge_brute_tonne - frais_logistiques_tonne
        gain_net_total = gain_net_tonne * qty_tons

        # Gain net en % du capital investi (achat + transport)
        cout_total = (prix_origine_kg * 1000 + frais_logistiques_tonne) * qty_tons
        gain_net_pct = (gain_net_total / cout_total * 100) if cout_total > 0 else 0.0

        # Recommandation basée sur le seuil de rentabilité configuré
        recommandation = (
            "TRANSPORTER" if gain_net_pct >= _SEUIL_RENTABILITE else "NE PAS TRANSPORTER"
        )

        # Score de confiance global sur la recommandation
        confidence_score = self._calculer_confidence_score(
            price_confidence, est_simule, gain_net_pct
        )

        return {
            "recommandation": recommandation,
            "gain_net_total_cfa": round(gain_net_total, 2),
            "gain_net_percent": round(gain_net_pct, 2),
            "frais_logistiques_total": round(frais_logistiques_tonne * qty_tons, 2),
            "prix_origine_xof_kg": round(prix_origine_kg, 2),
            "prix_destination_xof_kg": round(prix_destination_kg, 2),
            "is_simulated": est_simule,
            "confidence_score": confidence_score,
            "prob_pluie": round(prob_pluie, 3),
        }

    def storage_vs_sell_now(
        self,
        crop: str,
        market: str,
        current_price: float,
        qty_tons: float,
        mois_stockage: int = None,
    ) -> dict:
        """
        Évalue s'il est plus rentable de stocker ou de vendre immédiatement.

        Phase 4 : l'horizon de stockage est maintenant configurable via le
        paramètre mois_stockage. La valeur par défaut est lue depuis config.py
        (clé market.horizon_stockage_mois_default, défaut : 3 mois).

        Formule :
            E = E[P_{t+n}] - P_t - C_stockage(n) - C_opportunite(n) - theta * Var(P)

        Args:
            crop (str): La culture concernée.
            market (str): Le marché de référence.
            current_price (float): Prix actuel en XOF par tonne.
            qty_tons (float): Quantité récoltée en tonnes.
            mois_stockage (int, optional): Horizon de stockage en mois.
                Si None, utilise CONFIG["market"]["horizon_stockage_mois_default"].

        Returns:
            dict: Dictionnaire contenant :
                - 'recommandation_binaire' : 'STOCKER' ou 'VENDRE IMMÉDIATEMENT'
                - 'marge_nette_cfa'        : espérance de gain total en XOF
                - 'marge_nette_par_tonne'  : espérance de gain par tonne
                - 'prix_futur_estime'      : prix prévu à l'horizon (XOF/tonne)
                - 'horizon_mois'           : horizon de stockage utilisé
                - 'is_simulated'           : True si les prévisions sont simulées
                - 'confidence_score'       : score de confiance (0-1)
        """
        # Lecture de l'horizon de stockage (paramètre > config > défaut)
        if mois_stockage is None:
            mois_stockage = _HORIZON_MOIS_DEFAULT
        jours_stockage = mois_stockage * 30

        est_simule = True

        # Récupération du prix futur estimé via le module de prévision
        if self.forecasting:
            try:
                prevision = self.forecasting.predict_price(
                    crop, market, days_ahead=jours_stockage
                )
                # La prévision est en XOF/kg ; on convertit en XOF/tonne
                prix_futur_tonne = prevision["predicted_price"] * 1000
                variance = (
                    prevision.get("rmse", prevision["predicted_price"] * 0.05) * 1000
                )
                est_simule = True  # Le module forecasting V1 reste un stub
            except Exception as e:
                logger.warning(
                    f"Erreur lors de la prévision {crop}/{market}: {e}. "
                    "Hypothèse de hausse de 15%."
                )
                prix_futur_tonne = current_price * 1.15
                variance = current_price * 0.05
        else:
            # Sans module de prévision : hypothèse conservative de hausse de 15%
            prix_futur_tonne = current_price * 1.15
            variance = current_price * 0.05

        # Coûts de stockage : gardiennage, pertes, sacs (par mois par tonne)
        cout_stockage_mensuel_tonne = 3200.0
        c_stockage = cout_stockage_mensuel_tonne * mois_stockage

        # Coût d'opportunité : immobilisation de la trésorerie à 1.5%/mois
        taux_opportunite_mensuel = 0.015
        c_opportunite = current_price * (taux_opportunite_mensuel * mois_stockage)

        # Pénalité de risque (aversion au risque theta)
        theta_risque = 0.04
        penalite_risque = theta_risque * variance

        # Espérance de gain net par tonne
        esperance_gain = (
            prix_futur_tonne
            - current_price
            - c_stockage
            - c_opportunite
            - penalite_risque
        )

        recommandation = "STOCKER" if esperance_gain > 0 else "VENDRE IMMÉDIATEMENT"

        # Gain net en % du capital actuel (pour le score de confiance)
        gain_pct = (esperance_gain / current_price * 100) if current_price > 0 else 0.0

        # Score de confiance (prix simulés = confiance faible)
        confidence_score = self._calculer_confidence_score(
            price_confidence=0.0 if est_simule else 0.7,
            is_simulated=est_simule,
            gain_net_pct=gain_pct,
        )

        return {
            "recommandation_binaire": recommandation,
            "marge_nette_cfa": round(esperance_gain * qty_tons, 2),
            "marge_nette_par_tonne": round(esperance_gain, 2),
            "prix_futur_estime": round(prix_futur_tonne, 2),
            "horizon_mois": mois_stockage,
            "is_simulated": est_simule,
            "confidence_score": confidence_score,
        }

    def portfolio_optimization(
        self,
        available_land_ha: float,
        climate_forecast: dict,
        market_forecast: dict,
        rendements_t_ha: dict = None,
    ) -> dict:
        """
        Optimise la répartition des cultures sur la surface disponible.

        Phase 4 : utilise scipy.optimize.linprog pour maximiser le revenu
        attendu sous contraintes agronomiques et de surface. Si scipy n'est
        pas disponible, utilise un fallback heuristique.

        Modèle d'optimisation (programmation linéaire) :
            - Variables : x_i = hectares alloués à la culture i
            - Objectif  : maximiser sum(prix_i * rendement_i * x_i)
            - Contraintes :
                * sum(x_i) <= available_land_ha  (surface totale)
                * x_i >= 0
                * x_i <= 0.7 * available_land_ha  (diversification minimale)

        Ajustements climatiques (SPI de sécheresse) :
            - Sécheresse sévère (drought_severity='severe') :
                rendement_niébé * 1.3 (résistant), rendement_maïs * 0.7
            - Sécheresse modérée ('moderate') :
                rendement_maïs * 0.85

        Args:
            available_land_ha (float): Surface arable disponible en hectares.
            climate_forecast (dict): Prévisions climatiques. Clés attendues :
                - 'secheresse_anticipee' (bool) : compatibilité V1
                - 'drought_severity' (str)      : 'no_drought', 'mild', 'moderate', 'severe'
                - 'prob_pluie_7j' (float)       : probabilité de pluie sur 7 jours
            market_forecast (dict): Prix médians actuels par culture (XOF/kg).
                Exemple : {'maize': 285, 'cowpea': 580, 'sorghum': 210}
            rendements_t_ha (dict, optional): Rendements attendus en tonnes/hectare.
                Si None, utilise les rendements de référence béninois.

        Returns:
            dict: Dictionnaire contenant :
                - 'repartition_hectares' : répartition optimale par culture (hectares)
                - 'revenu_attendu_cfa'   : revenu total attendu en XOF
                - 'recommandation'       : texte explicatif
                - 'methode'              : 'scipy_linprog' ou 'heuristique'
                - 'confidence_score'     : score de confiance de l'optimisation
        """
        # Rendements de référence (paramètre > défauts Bénin)
        rends = dict(_RENDEMENTS_BENIN)
        if rendements_t_ha:
            rends.update(rendements_t_ha)

        # Cultures à optimiser : celles pour lesquelles on a un prix de marché
        # On filtre pour ne garder que les cultures connues dans les rendements
        cultures = [
            c for c in market_forecast
            if c in rends and market_forecast[c] > 0
        ]

        if not cultures:
            # Aucune culture avec données : fallback heuristique complet
            return self._portfolio_heuristique(
                available_land_ha, climate_forecast, market_forecast
            )

        # Ajustement des rendements selon la sévérité de la sécheresse
        severity = climate_forecast.get("drought_severity", "mild")
        if climate_forecast.get("secheresse_anticipee", False):
            # Rétrocompatibilité V1 : bool -> sécheresse sévère
            severity = "severe"

        rends_ajustes = {}
        for c in cultures:
            r = rends[c]
            if severity == "severe":
                # Sécheresse sévère : niébé résiste, maïs souffre
                if c == "cowpea":
                    r *= 1.3
                elif c in ("maize", "rice"):
                    r *= 0.7
            elif severity == "moderate":
                if c == "maize":
                    r *= 0.85
            rends_ajustes[c] = r

        # Revenus attendus par hectare pour chaque culture (XOF/ha)
        # prix en XOF/kg * rendement en t/ha * 1000 kg/t = XOF/ha
        revenu_par_ha = {
            c: market_forecast[c] * rends_ajustes[c] * 1000
            for c in cultures
        }

        # --- Tentative d'optimisation linéaire avec scipy -----------------
        try:
            from scipy.optimize import linprog

            n = len(cultures)
            # linprog minimise -> on inverse les coefficients (maximisation)
            c_obj = [-revenu_par_ha[culture] for culture in cultures]

            # Contraintes d'inégalité : sum(x_i) <= available_land_ha
            A_ub = [[1.0] * n]
            b_ub = [available_land_ha]

            # Bornes : 0 <= x_i <= 70% de la surface (diversification minimale)
            max_mono = 0.7 * available_land_ha
            bounds = [(0.0, max_mono)] * n

            resultat_scipy = linprog(
                c_obj,
                A_ub=A_ub,
                b_ub=b_ub,
                bounds=bounds,
                method="highs",
            )

            if resultat_scipy.success:
                # Extraction de la répartition optimale
                repartition = {
                    c: round(x, 4)
                    for c, x in zip(cultures, resultat_scipy.x)
                }
                # Revenu attendu total = - valeur objectif minimisée
                revenu_total = round(-resultat_scipy.fun, 2)

                # Construction du texte de recommandation
                culture_dominante = max(repartition, key=repartition.get)
                recommandation_texte = (
                    f"Optimisation linéaire ({severity}). "
                    f"Culture dominante recommandée : {culture_dominante} "
                    f"({repartition[culture_dominante]:.1f} ha)."
                )

                return {
                    "repartition_hectares": repartition,
                    "revenu_attendu_cfa": revenu_total,
                    "recommandation": recommandation_texte,
                    "methode": "scipy_linprog",
                    "confidence_score": 0.75 if severity in ("mild", "no_drought") else 0.55,
                }

        except ImportError:
            logger.warning(
                "scipy non disponible. Utilisation du fallback heuristique pour "
                "portfolio_optimization()."
            )
        except Exception as e:
            logger.warning(
                f"Erreur scipy.optimize.linprog : {e}. Fallback heuristique."
            )

        # --- Fallback heuristique si scipy est absent ou échoue ----------
        return self._portfolio_heuristique(available_land_ha, climate_forecast, market_forecast)

    def _portfolio_heuristique(
        self,
        available_land_ha: float,
        climate_forecast: dict,
        market_forecast: dict,
    ) -> dict:
        """
        Répartition heuristique de secours pour portfolio_optimization().

        Applique des règles agronomiques simples au lieu de l'optimiseur linéaire.
        Utilisé quand scipy n'est pas disponible ou quand aucune culture n'a de prix.

        Args:
            available_land_ha (float): Surface disponible en hectares.
            climate_forecast (dict): Prévisions climatiques.
            market_forecast (dict): Prix par culture (peut être vide).

        Returns:
            dict: Répartition heuristique et revenu estimé.
        """
        # Répartition par défaut : maïs 50%, soja 30%, niébé 20%
        repartition = {
            "maïs": 0.5 * available_land_ha,
            "soja": 0.3 * available_land_ha,
            "niébé": 0.2 * available_land_ha,
        }

        severity = climate_forecast.get("drought_severity", "mild")
        secheresse = (
            climate_forecast.get("secheresse_anticipee", False)
            or severity == "severe"
        )

        if secheresse:
            # En sécheresse sévère : favoriser le niébé (plus résistant)
            repartition["maïs"] = 0.3 * available_land_ha
            repartition["soja"] = 0.3 * available_land_ha
            repartition["niébé"] = 0.4 * available_land_ha

        recommandation_texte = (
            "Sécheresse anticipée : privilégier le niébé, culture résistante."
            if secheresse
            else "Conditions normales : répartition équilibrée recommandée."
        )

        return {
            "repartition_hectares": repartition,
            "revenu_attendu_cfa": 1_500_000.0,
            "recommandation": recommandation_texte,
            "methode": "heuristique",
            "confidence_score": 0.3,
        }
