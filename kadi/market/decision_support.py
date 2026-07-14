"""
Module d'aide à la décision stratégique pour l'arbitrage spatial,
le stockage temporel et l'optimisation de portefeuille de cultures.

Ce module utilise les données de prix réelles fournies par pricing_module
pour calculer des recommandations financièrement fondées. En l'absence
de données API (pas de clé WFP), il fonctionne avec les prix simulés.
"""

import logging

from kadi.config import CONFIG

logger = logging.getLogger(__name__)

# Lecture du seuil de rentabilité depuis la configuration logistique
_SEUIL_RENTABILITE = CONFIG.get("logistics", {}).get("seuil_rentabilite_pct", 10.0)


class DecisionSupport:
    """
    Classe convertissant les prévisions de prix et les données de marché
    en recommandations opérationnelles : arbitrage spatial, stockage,
    et optimisation de portefeuille de cultures.

    Tous les calculs utilisent les données réelles fournies par le module
    pricing (via pricing_module). En mode sans-API, les données simulées
    sont utilisées de façon transparente.
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

    def _obtenir_prix_marche(self, crop: str, market: str) -> tuple:
        """
        Récupère le prix actuel médian pour une culture sur un marché donné.

        Utilise le module pricing pour obtenir les données réelles (ou simulées).
        Retourne également un flag indiquant si les données sont simulées.

        Args:
            crop (str): Code de la culture (ex: 'maize').
            market (str): Nom normalisé du marché (ex: 'cotonou').

        Returns:
            tuple: (prix_median_xof_kg: float, is_simulated: bool)
                Le prix médian en XOF/kg et le flag de simulation.
        """
        if self.pricing is None:
            # Pas de module pricing : on retourne un prix de repli
            logger.warning(
                f"Pas de pricing_module disponible pour {crop}/{market}. "
                "Prix de repli utilisé (300 XOF/kg)."
            )
            return 300.0, True

        try:
            # Récupération des 30 derniers jours de données
            df = self.pricing.fetch_prices(crop, market, days_back=30)

            if df.empty or "price" not in df.columns:
                return 300.0, True

            # Calcul du prix médian pour éviter les outliers
            prix_median = float(df["price"].median())
            est_simule = bool(df["is_simulated"].any()) if "is_simulated" in df.columns else True

            return prix_median, est_simule

        except Exception as e:
            logger.warning(
                f"Erreur lors de la récupération du prix {crop}/{market}: {e}. "
                "Prix de repli utilisé."
            )
            return 300.0, True

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
        la marge brute. Les coûts logistiques sont calculés par le module logistics.

        Formule :
            Gain net = (prix_destination - prix_origine) * 1000 * qty - cout_transport

        Args:
            crop (str): La culture concernée (ex: 'maize').
            market_from (str): Le marché d'achat (ex: 'Parakou').
            market_to (str): Le marché de vente (ex: 'Cotonou').
            qty_tons (float): La quantité à transporter en tonnes métriques.

        Returns:
            dict: Dictionnaire contenant :
                - 'recommandation' : 'TRANSPORTER' ou 'NE PAS TRANSPORTER'
                - 'gain_net_total_cfa' : gain net en XOF sur toute la quantité
                - 'gain_net_percent' : gain net en % du capital investi
                - 'frais_logistiques_total' : coûts de transport totaux en XOF
                - 'prix_origine_xof_kg' : prix au marché d'achat
                - 'prix_destination_xof_kg' : prix au marché de vente
                - 'is_simulated' : True si les prix utilisés sont fictifs
        """
        # Récupération des prix réels (ou simulés) pour les deux marchés
        prix_origine_kg, simule_origine = self._obtenir_prix_marche(crop, market_from)
        prix_destination_kg, simule_destination = self._obtenir_prix_marche(crop, market_to)

        # Les données sont simulées si l'une des deux sources l'est
        est_simule = simule_origine or simule_destination

        # Marge brute par tonne (conversion kg -> tonne : *1000)
        marge_brute_tonne = (prix_destination_kg - prix_origine_kg) * 1000

        # Calcul des frais logistiques via le module dédié
        if self.logistics:
            res_logistics = self.logistics.calculate_transfer_cost(market_from, market_to)
            frais_logistiques_tonne = res_logistics["total_cost_cfa"]
        else:
            # Valeur de repli si le module logistics n'est pas disponible
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

        return {
            "recommandation": recommandation,
            "gain_net_total_cfa": round(gain_net_total, 2),
            "gain_net_percent": round(gain_net_pct, 2),
            "frais_logistiques_total": round(frais_logistiques_tonne * qty_tons, 2),
            "prix_origine_xof_kg": round(prix_origine_kg, 2),
            "prix_destination_xof_kg": round(prix_destination_kg, 2),
            "is_simulated": est_simule,
        }

    def storage_vs_sell_now(
        self,
        crop: str,
        market: str,
        current_price: float,
        qty_tons: float,
    ) -> dict:
        """
        Évalue s'il est plus rentable de stocker ou de vendre immédiatement.

        Formule :
            E = E[P_{t+n}] - P_t - C_stockage(n) - C_opportunite(n) - theta * Var(P)

        Args:
            crop (str): La culture concernée.
            market (str): Le marché de référence.
            current_price (float): Prix actuel en XOF par tonne.
            qty_tons (float): Quantité récoltée en tonnes.

        Returns:
            dict: Dictionnaire contenant :
                - 'recommandation_binaire' : 'STOCKER' ou 'VENDRE IMMÉDIATEMENT'
                - 'marge_nette_cfa' : espérance de gain en XOF sur la quantité totale
                - 'marge_nette_par_tonne' : espérance de gain par tonne
                - 'prix_futur_estime' : prix prévu dans 3 mois (en XOF/tonne)
                - 'is_simulated' : True si les prévisions sont simulées
        """
        # Horizon de stockage standard (3 mois)
        mois_stockage = 3
        jours_stockage = mois_stockage * 30

        est_simule = True

        # Récupération du prix futur estimé via le module de prévision
        if self.forecasting:
            try:
                prevision = self.forecasting.predict_price(
                    crop, market, days_ahead=jours_stockage
                )
                # La prévision est en XOF/kg, on convertit en XOF/tonne
                prix_futur_tonne = prevision["predicted_price"] * 1000
                variance = prevision.get("rmse", prevision["predicted_price"] * 0.05) * 1000
                est_simule = True  # Le module forecasting V1 est encore un stub
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
            prix_futur_tonne - current_price - c_stockage - c_opportunite - penalite_risque
        )

        recommandation = "STOCKER" if esperance_gain > 0 else "VENDRE IMMÉDIATEMENT"

        return {
            "recommandation_binaire": recommandation,
            "marge_nette_cfa": round(esperance_gain * qty_tons, 2),
            "marge_nette_par_tonne": round(esperance_gain, 2),
            "prix_futur_estime": round(prix_futur_tonne, 2),
            "is_simulated": est_simule,
        }

    def portfolio_optimization(
        self,
        available_land_ha: float,
        climate_forecast: dict,
        market_forecast: dict,
    ) -> dict:
        """
        Optimise la répartition des cultures sur la surface disponible.

        Basée sur les prévisions climatiques (kadi.weather, Phase 4) et de
        prix (kadi.market). En V1, utilise des règles heuristiques simples.

        Args:
            available_land_ha (float): Surface arable disponible en hectares.
            climate_forecast (dict): Prévisions météo (clé: 'secheresse_anticipee').
            market_forecast (dict): Prévisions de prix par culture.

        Returns:
            dict: La répartition optimale en hectares par culture et le revenu attendu.
        """
        # Répartition par défaut : maïs 50%, soja 30%, niébé 20%
        repartition = {
            "maïs": 0.5 * available_land_ha,
            "soja": 0.3 * available_land_ha,
            "niébé": 0.2 * available_land_ha,
        }

        # Ajustement si sécheresse anticipée : favoriser le niébé (plus résistant)
        if climate_forecast.get("secheresse_anticipee", False):
            repartition["maïs"] = 0.3 * available_land_ha
            repartition["soja"] = 0.3 * available_land_ha
            repartition["niébé"] = 0.4 * available_land_ha

        recommandation_texte = (
            "Sécheresse anticipée : privilégier le niébé, culture résistante."
            if climate_forecast.get("secheresse_anticipee", False)
            else "Conditions normales : répartition équilibrée recommandée."
        )

        return {
            "repartition_hectares": repartition,
            "revenu_attendu_cfa": 1_500_000.0,  # Stub V1 : valeur à calculer en Phase 3
            "recommandation": recommandation_texte,
        }
