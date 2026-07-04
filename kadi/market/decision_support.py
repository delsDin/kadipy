"""
Module d'aide à la décision stratégique pour l'arbitrage spatial,
le stockage temporel et l'optimisation de portefeuille de cultures.
"""


class DecisionSupport:
    """
    Classe convertissant les prévisions de prix et de climat en recommandations
    opérationnelles : stockage, arbitrage spatial, choix de cultures.
    """

    def __init__(self, forecasting_module=None, logistics_module=None):
        """
        Initialise le module d'aide à la décision.

        Args:
            forecasting_module: Instance de MarketForecasting pour obtenir les prix futurs.
            logistics_module: Instance de MarketLogistics pour calculer les frais.
        """
        # Références vers les autres sous-modules pour enrichir la décision
        self.forecasting = forecasting_module
        self.logistics = logistics_module

    def arbitrage_decision(self, crop: str, market_from: str, market_to: str, qty_tons: float) -> dict:
        """
        Évalue la rentabilité d'un transfert physique de marchandises entre deux marchés.

        Args:
            crop (str): La culture concernée.
            market_from (str): Le marché d'origine.
            market_to (str): Le marché de destination.
            qty_tons (float): La quantité à transporter en tonnes.

        Returns:
            dict: Les détails de la décision d'arbitrage (gain net, recommandation).
        """
        # Prix de vente simulé au marché de destination
        prix_destination_kg = 350.0 
        
        # Prix d'achat simulé au marché d'origine
        prix_origine_kg = 250.0
        
        # Marge brute par tonne
        marge_brute_tonne = (prix_destination_kg - prix_origine_kg) * 1000
        
        # Récupération des coûts logistiques si le module est présent
        frais_logistiques_tonne = 0
        if self.logistics:
            # Appel au calcul du coût de transfert
            res_logistics = self.logistics.calculate_transfer_cost(market_from, market_to)
            frais_logistiques_tonne = res_logistics['total_cost_cfa']
        else:
            # Valeur par défaut si non fourni
            frais_logistiques_tonne = 30000.0
            
        # Gain net par tonne après déduction des frais logistiques
        gain_net_tonne = marge_brute_tonne - frais_logistiques_tonne
        
        # Gain net total sur la quantité transportée
        gain_net_total = gain_net_tonne * qty_tons
        
        # Calcul du gain net en pourcentage par rapport au coût total (achat + transport)
        cout_total_investissement = (prix_origine_kg * 1000 + frais_logistiques_tonne) * qty_tons
        gain_net_percent = (gain_net_total / cout_total_investissement) * 100 if cout_total_investissement > 0 else 0
        
        # La recommandation est de transporter si le gain dépasse 10%
        recommandation = 'TRANSPORTER' if gain_net_percent >= 10.0 else 'NE PAS TRANSPORTER'
        
        # Construction du dictionnaire de résultats
        resultat = {
            'recommandation': recommandation,
            'gain_net_total_cfa': round(gain_net_total, 2),
            'gain_net_percent': round(gain_net_percent, 2),
            'frais_logistiques_total': round(frais_logistiques_tonne * qty_tons, 2)
        }
        
        # Retour des résultats de l'arbitrage
        return resultat

    def storage_vs_sell_now(self, crop: str, market: str, current_price: float, qty_tons: float) -> dict:
        """
        Évalue s'il est plus rentable de stocker la production ou de la vendre immédiatement.
        Formule : E = E[P_t+n | F_t] - P_t - C_storage(n) - C_opportunity(n) - θ*Var(P)

        Args:
            crop (str): La culture concernée.
            market (str): Le marché de référence.
            current_price (float): Le prix actuel à la récolte par tonne.
            qty_tons (float): La quantité récoltée en tonnes.

        Returns:
            dict: Recommandation binaire et détails financiers.
        """
        # Horizon de stockage par défaut (3 mois)
        mois_stockage = 3
        jours_stockage = mois_stockage * 30
        
        # Obtention du prix futur estimé
        future_price_estim = current_price * 1.15  # Par défaut, hausse de 15%
        variance = current_price * 0.05
        
        # Utilisation du module forecasting si disponible
        if self.forecasting:
            # Appel pour la prédiction
            prevision = self.forecasting.predict_price(crop, market, days_ahead=jours_stockage)
            future_price_estim = prevision['predicted_price'] * 1000  # conversion en tonne
            variance = prevision['rmse'] * 1000
            
        # Coûts de stockage (C_storage) mensuel par tonne (frais de gardiennage, pertes)
        cout_stockage_mensuel_tonne = 3200.0
        c_storage = cout_stockage_mensuel_tonne * mois_stockage
        
        # Coût d'opportunité d'immobilisation de la trésorerie (ex: 1.5% / mois)
        taux_opportunite_mensuel = 0.015
        c_opportunity = current_price * (taux_opportunite_mensuel * mois_stockage)
        
        # Aversion au risque du producteur (théta)
        theta_risque = 0.04
        penalite_risque = theta_risque * variance
        
        # Espérance de gain net par tonne (E)
        esperance_gain_net = future_price_estim - current_price - c_storage - c_opportunity - penalite_risque
        
        # Gain total attendu
        marge_nette_totale = esperance_gain_net * qty_tons
        
        # Décision : si l'espérance est positive, on stocke, sinon on vend
        recommandation = 'STOCKER' if esperance_gain_net > 0 else 'VENDRE IMMÉDIATEMENT'
        
        # Formatage des résultats
        resultat = {
            'recommandation_binaire': recommandation,
            'marge_nette_cfa': round(marge_nette_totale, 2),
            'marge_nette_par_tonne': round(esperance_gain_net, 2)
        }
        
        # Retourne les recommandations de stockage
        return resultat

    def portfolio_optimization(self, available_land_ha: float, climate_forecast: dict, market_forecast: dict) -> dict:
        """
        Optimise la répartition des cultures sur la surface disponible en fonction
        des prévisions climatiques (kadi.weather) et de prix (kadi.market).

        Args:
            available_land_ha (float): Surface arable disponible en hectares.
            climate_forecast (dict): Prévisions météorologiques et stress hydrique.
            market_forecast (dict): Prévisions de prix pour différentes cultures.

        Returns:
            dict: La répartition optimale en pourcentages et surfaces.
        """
        # Répartition simulée en fonction du stress hydrique
        repartition = {
            'maïs': 0.5 * available_land_ha,
            'soja': 0.3 * available_land_ha,
            'niébé': 0.2 * available_land_ha
        }
        
        # Ajustement simplifié : si sécheresse anticipée, on favorise le niébé (plus résistant)
        if climate_forecast.get('secheresse_anticipee', False):
            repartition['maïs'] = 0.3 * available_land_ha
            repartition['soja'] = 0.3 * available_land_ha
            repartition['niébé'] = 0.4 * available_land_ha
            
        # Construction de la réponse
        resultat = {
            'repartition_hectares': repartition,
            'revenu_attendu_cfa': 1500000.0,  # Valeur fictive
            'recommandation': 'Privilégier les cultures résistantes à la sécheresse.' 
                              if climate_forecast.get('secheresse_anticipee', False) else 'Répartition équilibrée.'
        }
        
        # Retourne l'optimisation
        return resultat
