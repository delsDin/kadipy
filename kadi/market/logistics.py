"""
Module gérant les coûts de logistique, de transport et les frictions
sur les corridors commerciaux au Bénin.
"""


class MarketLogistics:
    """
    Classe permettant de modéliser les frictions logistiques réelles :
    coûts de transport, attentes aux frontières, et dégradation de la qualité.
    """

    def __init__(self):
        """
        Initialise le module logistique avec les paramètres par défaut
        pour les corridors du Bénin.
        """
        # Distance en km des principaux corridors (valeurs approximatives)
        self.corridors_distance = {
            ('Cotonou', 'Parakou'): 263.0,
            ('Parakou', 'Niamey'): 360.0,
            ('Bohicon', 'Malanville'): 340.0,
            ('Abomey', 'Sèmè-Kraké'): 45.0
        }

    def get_distance(self, origine: str, destination: str) -> float:
        """
        Récupère la distance entre deux villes selon les corridors prédéfinis.

        Args:
            origine (str): Ville de départ.
            destination (str): Ville d'arrivée.

        Returns:
            float: La distance en kilomètres. Retourne 100.0 par défaut si inconnu.
        """
        # Recherche dans le sens origine -> destination
        if (origine, destination) in self.corridors_distance:
            return self.corridors_distance[(origine, destination)]
            
        # Recherche dans le sens inverse
        if (destination, origine) in self.corridors_distance:
            return self.corridors_distance[(destination, origine)]
            
        # Retour d'une distance par défaut si le trajet n'est pas répertorié
        return 100.0

    def calculate_transfer_cost(self, origine: str, destination: str, prix_carburant: float = 650.0) -> dict:
        """
        Calcule le coût total de transfert (C_transfer) d'un point A à un point B,
        incluant les coûts de recherche, transport, douane et perte de qualité.

        Formule: C_transfer = C_info + D_AB * (γ_route * P_carburant + μ_checkpoints) + C_qualite_loss

        Args:
            origine (str): Point de départ (ex: 'Savalou').
            destination (str): Point d'arrivée (ex: 'Malanville').
            prix_carburant (float, optional): Prix du carburant au litre en XOF. Défaut à 650.0.

        Returns:
            dict: Dictionnaire contenant le coût total et ses composantes par tonne.
        """
        # Récupération de la distance entre l'origine et la destination
        d_ab = self.get_distance(origine, destination)
        
        # Coûts fixes de recherche d'information et prospection (par tonne)
        c_info = 5000.0
        
        # Coefficient d'état de la route (plus élevé si piste, plus bas si asphalte)
        gamma_route = 1.2
        
        # Coût des tracasseries et checkpoints informels (au km par tonne)
        mu_checkpoints = 15.0
        
        # Dégradation de qualité estimée (valeur fixe pour l'exemple)
        c_qualite_loss = 2500.0
        
        # Calcul de la portion liée à la distance
        cout_distance = d_ab * ((gamma_route * prix_carburant / 100.0) + mu_checkpoints)
        
        # Calcul du coût total de transfert
        c_transfer = c_info + cout_distance + c_qualite_loss
        
        # Formatage du résultat de retour
        resultat = {
            'total_cost_cfa': c_transfer,
            'details': {
                'distance_km': d_ab,
                'search_costs': c_info,
                'transport_costs': cout_distance,
                'quality_loss': c_qualite_loss
            }
        }
        
        # Retourne les coûts calculés
        return resultat
