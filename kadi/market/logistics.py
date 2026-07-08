"""
Module gérant les coûts de logistique, de transport et les frictions
sur les corridors commerciaux au Bénin (V1).

Note sur les intégrations futures :
    La plan de développement prévoit de connecter ce module
    à kadi.weather pour ajuster automatiquement le coefficient d'état
    des routes (gamma_route) selon la saison des pluies, et pour
    augmenter la perte de qualité des produits frais en période humide.
    Dans le V1, ces ajustements sont laissés à la configuration manuelle.
"""

import os
import json
import time
import logging
import math
import requests
from typing import Tuple, Optional

# Import de la configuration centralisée pour les coefficients logistiques
from kadi.config import CONFIG

logger = logging.getLogger(__name__)

# Récupération des coefficients logistiques depuis la configuration
_LOGISTICS_CONFIG = CONFIG.get("logistics", {})
_MARKET_CONFIG = CONFIG.get("market", {})

# Délai entre deux requêtes Nominatim (OpenStreetMap exige max 1 req/seconde)
_NOMINATIM_DELAY_SEC = _MARKET_CONFIG.get("nominatim_delay_sec", 1.1)

# Timestamp de la dernière requête Nominatim (pour respecter le rate-limit)
_derniere_requete_nominatim: float = 0.0


def _respecter_rate_limit_nominatim():
    """
    Attend le temps nécessaire pour respecter la limite de taux de Nominatim.

    Nominatim (OpenStreetMap) impose une limite d'1 requête par seconde.
    Cette fonction calcule le temps d'attente restant et met le thread en pause
    si la dernière requête est trop récente.
    """
    global _derniere_requete_nominatim

    temps_ecoule = time.time() - _derniere_requete_nominatim
    temps_restant = _NOMINATIM_DELAY_SEC - temps_ecoule

    if temps_restant > 0:
        logger.debug(f"Rate-limit Nominatim : attente de {temps_restant:.2f}s.")
        time.sleep(temps_restant)

    # On met à jour le timestamp après le délai
    _derniere_requete_nominatim = time.time()


class MarketLogistics:
    """
    Classe modélisant les frictions logistiques réelles au Bénin :
    coûts de transport, tracasseries aux postes de contrôle,
    et dégradation de la qualité des marchandises.

    Les coefficients utilisés dans les formules de coût sont lus
    depuis la configuration centrale (config.py) pour être ajustables
    sans modifier le code source.
    """

    def __init__(self, cache_file: str = None):
        """
        Initialise le module logistique.

        Charge le cache persistant des coordonnées GPS et des distances
        routières pour éviter des appels réseau redondants.

        Args:
            cache_file (str, optional): Chemin vers le fichier de cache JSON.
                Si None, utilise ``~/.kadi/osrm_cache.json``.
        """
        # Initialisation du chemin du fichier de cache
        if cache_file is None:
            cache_dir = os.path.expanduser("~/.kadi")
            os.makedirs(cache_dir, exist_ok=True)
            self.cache_file = os.path.join(cache_dir, "osrm_cache.json")
        else:
            self.cache_file = cache_file

        # Structure du cache en mémoire (coordonnées et distances routières)
        self.cache = {"coords": {}, "distances": {}}

        # Cache en mémoire pour le prix du carburant (évite les appels répétés)
        self._cached_fuel_price: Optional[float] = None

        # Chargement du cache depuis le disque
        self._load_cache()

    def _load_cache(self):
        """Charge le cache persistant depuis le fichier JSON s'il existe."""
        if os.path.isfile(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cache["coords"] = data.get("coords", {})
                    self.cache["distances"] = data.get("distances", {})
            except Exception as e:
                logger.warning(f"Impossible de lire le cache {self.cache_file}: {e}")

    def _save_cache(self):
        """Sauvegarde le cache en mémoire dans le fichier JSON persistant."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le cache {self.cache_file}: {e}")

    def _haversine_distance(
        self, lon1: float, lat1: float, lon2: float, lat2: float
    ) -> float:
        """
        Calcule la distance orthodromique entre deux points GPS
        en utilisant la formule de Haversine.

        Utilisée comme fallback si OSRM est indisponible. La distance
        vol d'oiseau est multipliée par un facteur de tortuosité (1.3)
        pour approximer la distance réelle sur les routes béninoises.

        Args:
            lon1 (float): Longitude du point de départ.
            lat1 (float): Latitude du point de départ.
            lon2 (float): Longitude du point d'arrivée.
            lat2 (float): Latitude du point d'arrivée.

        Returns:
            float: Distance routière approximée en kilomètres.
        """
        # Rayon de la Terre en kilomètres
        R = 6371.0

        # Conversion des coordonnées en radians
        lat1_r = math.radians(lat1)
        lon1_r = math.radians(lon1)
        lat2_r = math.radians(lat2)
        lon2_r = math.radians(lon2)

        dlon = lon2_r - lon1_r
        dlat = lat2_r - lat1_r

        # Formule de Haversine
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance_vol_oiseau = R * c

        # Facteur de tortuosité : les routes béninoises font environ 30%
        # de plus que la distance à vol d'oiseau en moyenne
        return distance_vol_oiseau * 1.3

    def _geocode_city(self, city_name: str) -> Optional[Tuple[float, float]]:
        """
        Interroge Nominatim (OpenStreetMap) pour obtenir les coordonnées GPS
        d'une ville. Respecte la limite de taux de 1 requête/seconde.

        Le résultat est mis en cache pour éviter des appels répétés.

        Args:
            city_name (str): Nom de la ville à géocoder (ex: 'Cotonou').

        Returns:
            tuple: (longitude, latitude) ou None si la ville est introuvable.
        """
        city_key = city_name.strip().lower()

        # Retour depuis le cache si déjà résolu
        if city_key in self.cache["coords"]:
            return tuple(self.cache["coords"][city_key])

        # Respect du rate-limit Nominatim avant toute requête
        _respecter_rate_limit_nominatim()

        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{city_name}, Benin",
            "format": "json",
            "limit": 1,
        }
        # Identification de l'application (requis par les conditions d'utilisation Nominatim)
        headers = {"User-Agent": "KadiPy/0.1.0 (Agritech Research, Benin)"}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                lon = float(data[0]["lon"])
                lat = float(data[0]["lat"])
                # Mise en cache du résultat
                self.cache["coords"][city_key] = [lon, lat]
                self._save_cache()
                return (lon, lat)
            else:
                logger.warning(f"Ville '{city_name}' introuvable via Nominatim.")

        except Exception as e:
            logger.warning(f"Erreur lors du géocodage de '{city_name}': {e}")

        return None

    def _fetch_osrm_distance(
        self, lon1: float, lat1: float, lon2: float, lat2: float
    ) -> Optional[float]:
        """
        Interroge le serveur public OSRM pour calculer la distance routière
        réelle entre deux points GPS.

        Args:
            lon1 (float): Longitude du point de départ.
            lat1 (float): Latitude du point de départ.
            lon2 (float): Longitude du point d'arrivée.
            lat2 (float): Latitude du point d'arrivée.

        Returns:
            float: Distance en kilomètres, ou None si la requête a échoué.
        """
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=false"
        )
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Ok" and data.get("routes"):
                distance_metres = data["routes"][0]["distance"]
                return distance_metres / 1000.0

        except Exception as e:
            logger.warning(f"Erreur lors de la requête OSRM : {e}")

        return None

    def get_distance(self, origine: str, destination: str) -> float:
        """
        Récupère la distance routière réelle entre deux villes béninoises.

        Stratégie en cascade :
        1. Cache local (résultat d'un appel précédent)
        2. Géocodage Nominatim + routage OSRM
        3. Fallback Haversine (vol d'oiseau * 1.3) si OSRM échoue
        4. Valeur par défaut 100 km si le géocodage échoue

        Args:
            origine (str): Nom de la ville de départ (ex: 'Parakou').
            destination (str): Nom de la ville d'arrivée (ex: 'Cotonou').

        Returns:
            float: Distance estimée en kilomètres.
        """
        orig_key = origine.strip().lower()
        dest_key = destination.strip().lower()
        route_key = f"{orig_key}_{dest_key}"
        rev_route_key = f"{dest_key}_{orig_key}"

        # 1. Vérification du cache (aller et retour)
        if route_key in self.cache["distances"]:
            return self.cache["distances"][route_key]
        if rev_route_key in self.cache["distances"]:
            return self.cache["distances"][rev_route_key]

        # 2. Géocodage des deux villes
        coords_orig = self._geocode_city(origine)
        coords_dest = self._geocode_city(destination)

        if not coords_orig or not coords_dest:
            logger.warning(
                f"Géocodage impossible pour '{origine}' -> '{destination}'. "
                "Valeur de repli : 100 km."
            )
            return 100.0

        # 3. Requête OSRM pour la vraie distance routière
        dist = self._fetch_osrm_distance(
            coords_orig[0], coords_orig[1],
            coords_dest[0], coords_dest[1],
        )

        # 4. Fallback Haversine si OSRM est indisponible
        if dist is None:
            logger.warning(
                f"OSRM indisponible pour '{origine}' -> '{destination}'. "
                "Utilisation de la formule Haversine (distance approximée)."
            )
            dist = self._haversine_distance(
                coords_orig[0], coords_orig[1],
                coords_dest[0], coords_dest[1],
            )

        # Mise en cache du résultat
        self.cache["distances"][route_key] = dist
        self._save_cache()

        return dist

    def _fetch_fuel_price(self) -> float:
        """
        Récupère le prix actuel du carburant (essence) au Bénin.

        Stratégie en cascade :
        1. Variable d'environnement BENIN_FUEL_PRICE (priorité absolue)
        2. Cache en mémoire (évite les appels répétés)
        3. Fichier de configuration sur GitHub (config/fuel_prices.json)
        4. Valeur de repli depuis la configuration (680 XOF/litre par défaut)

        Returns:
            float: Prix de l'essence en XOF par litre.
        """
        # Priorité 1 : variable d'environnement
        env_price = os.getenv("BENIN_FUEL_PRICE")
        if env_price is not None:
            try:
                return float(env_price)
            except ValueError:
                logger.warning(
                    f"Valeur BENIN_FUEL_PRICE invalide dans .env : '{env_price}'. "
                    "Passage à la source suivante."
                )

        # Priorité 2 : cache en mémoire
        if self._cached_fuel_price is not None:
            return self._cached_fuel_price

        # Priorité 3 : configuration en ligne (GitHub)
        url = "https://raw.githubusercontent.com/delsDin/kadipy/main/config/fuel_prices.json"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            price = float(data.get("benin", {}).get("essence", None))
            self._cached_fuel_price = price
            return price
        except Exception as e:
            logger.warning(
                f"Impossible de récupérer le prix du carburant en ligne ({e}). "
                "Utilisation de la valeur de repli."
            )

        # Priorité 4 : valeur de repli depuis la configuration
        prix_repli = _LOGISTICS_CONFIG.get("prix_carburant_fallback_xof", 680.0)
        self._cached_fuel_price = prix_repli
        return prix_repli

    def calculate_transfer_cost(
        self,
        origine: str,
        destination: str,
        prix_carburant: float = None,
    ) -> dict:
        """
        Calcule le coût total de transfert d'un point A vers un point B.

        Formule appliquée :
            C_transfer = C_info + (Distance * (gamma_route * P_carburant / 100 + mu_checkpoints)) + C_qualite

        Où :
        - C_info = coût fixe de recherche d'informations (appels, déplacements préalables)
        - gamma_route = coefficient d'état des routes (configurable)
        - P_carburant = prix du litre d'essence en XOF
        - mu_checkpoints = coût moyen des tracasseries par km
        - C_qualite = perte de valeur marchande due au transport

        Args:
            origine (str): Ville de départ (ex: 'Parakou').
            destination (str): Ville de destination (ex: 'Cotonou').
            prix_carburant (float, optional): Prix du litre d'essence en XOF.
                Si None, récupéré automatiquement depuis les sources configurées.

        Returns:
            dict: Dictionnaire contenant le coût total et le détail par poste.
        """
        # Récupération du prix du carburant si non fourni
        if prix_carburant is None:
            prix_carburant = self._fetch_fuel_price()

        # Récupération des coefficients depuis la configuration centrale
        c_info = _LOGISTICS_CONFIG.get("c_info_xof", 5000.0)
        gamma_route = _LOGISTICS_CONFIG.get("gamma_route", 1.2)
        mu_checkpoints = _LOGISTICS_CONFIG.get("mu_checkpoints_xof_per_km", 15.0)
        c_qualite_loss = _LOGISTICS_CONFIG.get("c_qualite_loss_xof", 2500.0)

        # Calcul de la distance routière entre les deux villes
        d_ab = self.get_distance(origine, destination)

        # Calcul du coût lié à la distance (carburant + tracasseries)
        cout_distance = d_ab * ((gamma_route * prix_carburant / 100.0) + mu_checkpoints)

        # Coût de transfert total
        c_transfer = c_info + cout_distance + c_qualite_loss

        # Construction du résultat détaillé
        resultat = {
            "total_cost_cfa": round(c_transfer, 2),
            "details": {
                "distance_km": round(d_ab, 2),
                "search_costs": c_info,
                "transport_costs": round(cout_distance, 2),
                "quality_loss": c_qualite_loss,
                "fuel_price_used": prix_carburant,
                "gamma_route": gamma_route,
            },
        }

        return resultat
