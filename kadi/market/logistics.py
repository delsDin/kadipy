"""
Module gérant les coûts de logistique, de transport et les frictions
sur les corridors commerciaux au Bénin.
"""
import os
import json
import logging
import requests
import math
from typing import Tuple

logger = logging.getLogger(__name__)

class MarketLogistics:
    """
    Classe permettant de modéliser les frictions logistiques réelles :
    coûts de transport, attentes aux frontières, et dégradation de la qualité.
    """

    def __init__(self, cache_file: str = None):
        """
        Initialise le module logistique avec les paramètres par défaut
        et le cache local pour les requêtes géographiques.
        """
        if cache_file is None:
            cache_dir = os.path.expanduser("~/.kadi")
            os.makedirs(cache_dir, exist_ok=True)
            self.cache_file = os.path.join(cache_dir, "osrm_cache.json")
        else:
            self.cache_file = cache_file
            
        self.cache = {
            "coords": {},
            "distances": {}
        }
        self._cached_fuel_price = None
        self._load_cache()

    def _load_cache(self):
        """Charge le cache persistant s'il existe."""
        if os.path.isfile(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache["coords"] = data.get("coords", {})
                    self.cache["distances"] = data.get("distances", {})
            except Exception as e:
                logger.warning(f"Impossible de lire le cache {self.cache_file}: {e}")

    def _save_cache(self):
        """Sauvegarde le cache en mémoire vers le fichier persistant."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le cache {self.cache_file}: {e}")

    def _haversine_distance(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Calcule la distance orthodromique (vol d'oiseau) entre deux points GPS
        en utilisant la formule de Haversine. Utilisé comme fallback.
        """
        R = 6371.0  # Rayon de la Terre en km
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        # On multiplie par 1.3 pour approximer la tortuosité des routes par rapport au vol d'oiseau
        return distance * 1.3

    def _geocode_city(self, city_name: str) -> Tuple[float, float]:
        """
        Interroge Nominatim (OpenStreetMap) pour obtenir les coordonnées d'une ville.
        Retourne (longitude, latitude).
        """
        city_key = city_name.strip().lower()
        if city_key in self.cache["coords"]:
            return tuple(self.cache["coords"][city_key])
            
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{city_name}, Benin",
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "KadiPy/0.1.0 (Agritech Research)"
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                lon = float(data[0]["lon"])
                lat = float(data[0]["lat"])
                self.cache["coords"][city_key] = [lon, lat]
                self._save_cache()
                return (lon, lat)
            else:
                logger.warning(f"Ville {city_name} introuvable via Nominatim.")
        except Exception as e:
            logger.warning(f"Erreur lors du géocodage de {city_name}: {e}")
            
        return None

    def _fetch_osrm_distance(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Interroge OSRM pour calculer la distance routière en km.
        """
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == "Ok" and len(data.get("routes", [])) > 0:
                distance_meters = data["routes"][0]["distance"]
                return distance_meters / 1000.0
        except Exception as e:
            logger.warning(f"Erreur lors de la requête OSRM: {e}")
            
        return None

    def get_distance(self, origine: str, destination: str) -> float:
        """
        Récupère la distance routière réelle entre deux villes.
        """
        orig_key = origine.strip().lower()
        dest_key = destination.strip().lower()
        route_key = f"{orig_key}_{dest_key}"
        rev_route_key = f"{dest_key}_{orig_key}"
        
        # 1. Vérification du cache des distances
        if route_key in self.cache["distances"]:
            return self.cache["distances"][route_key]
        if rev_route_key in self.cache["distances"]:
            return self.cache["distances"][rev_route_key]
            
        # 2. Géocodage
        coords_orig = self._geocode_city(origine)
        coords_dest = self._geocode_city(destination)
        
        if not coords_orig or not coords_dest:
            logger.warning(f"Impossible de géocoder l'itinéraire {origine} -> {destination}. Fallback à 100km.")
            return 100.0
            
        # 3. Requête OSRM
        dist = self._fetch_osrm_distance(coords_orig[0], coords_orig[1], coords_dest[0], coords_dest[1])
        
        # 4. Fallback mathématique (Haversine) si OSRM échoue
        if dist is None:
            logger.warning("Utilisation de Haversine comme Fallback pour la distance.")
            dist = self._haversine_distance(coords_orig[0], coords_orig[1], coords_dest[0], coords_dest[1])
            
        # Mise en cache
        self.cache["distances"][route_key] = dist
        self._save_cache()
        
        return dist

    def _fetch_fuel_price(self) -> float:
        """
        Récupère le prix du carburant depuis .env ou depuis le fichier distant GitHub.
        """
        # 1. Vérifier la variable d'environnement (priorité)
        env_price = os.getenv("BENIN_FUEL_PRICE")
        if env_price is not None:
            try:
                return float(env_price)
            except ValueError:
                logger.warning(f"Valeur BENIN_FUEL_PRICE invalide dans .env : {env_price}")

        # 2. Vérifier le cache en mémoire
        if self._cached_fuel_price is not None:
            return self._cached_fuel_price

        # 3. Requête HTTP vers la configuration en ligne
        url = "https://raw.githubusercontent.com/delsDin/kadipy/main/config/fuel_prices.json"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            price = float(data.get("benin", {}).get("essence", 680.0))
            self._cached_fuel_price = price
            return price
        except Exception as e:
            logger.warning(f"Impossible de récupérer le prix du carburant en ligne ({e}). Fallback à 680.0.")
            self._cached_fuel_price = 680.0
            return 680.0

    def calculate_transfer_cost(self, origine: str, destination: str, prix_carburant: float = None) -> dict:
        """
        Calcule le coût total de transfert (C_transfer) d'un point A à un point B.
        """
        if prix_carburant is None:
            prix_carburant = self._fetch_fuel_price()

        d_ab = self.get_distance(origine, destination)
        
        c_info = 5000.0
        gamma_route = 1.2
        mu_checkpoints = 15.0
        c_qualite_loss = 2500.0
        
        cout_distance = d_ab * ((gamma_route * prix_carburant / 100.0) + mu_checkpoints)
        c_transfer = c_info + cout_distance + c_qualite_loss
        
        resultat = {
            'total_cost_cfa': c_transfer,
            'details': {
                'distance_km': d_ab,
                'search_costs': c_info,
                'transport_costs': cout_distance,
                'quality_loss': c_qualite_loss
            }
        }
        
        return resultat
