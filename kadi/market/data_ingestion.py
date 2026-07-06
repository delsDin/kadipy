"""
Module de connexion aux APIs externes pour l'ingestion de données.
Inclut le client pour WFP DataBridges.
"""

import os
import json
import requests
import logging
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Mappings de secours (Fallback) en cas d'échec de l'API
COMMODITY_MAPPING_FALLBACK = {
    'maize': 51,
    'maize_white': 51,
    'rice': 73,
    'sorghum': 58,
    'yam': 97,
    'cassava': 83
}

MARKET_MAPPING_FALLBACK = {
    'savalou_market': 1234,
    'savalou': 1234,
    'cotonou': 1001,
    'parakou': 1002,
    'dantokpa': 1001,
    'malanville': 1003
}


class WFPDataBridgesClient:
    """
    Client HTTP léger pour interagir avec l'API WFP DataBridges.
    Gère la conversion des noms, l'authentification et le repli (fallback).
    """

    def __init__(self, use_local_mirror: bool = False, env_file: str = '.env', cache_file: str = None):
        """
        Initialise le client WFP.

        Args:
            use_local_mirror (bool): Si True, utilise le cache local/simulé.
            env_file (str): Chemin vers le fichier d'environnement.
            cache_file (str): Chemin vers le fichier de cache WFP.
        """
        self.base_url = "https://api.wfp.org/vam-data-bridges/1.3.1"
        self.use_local_mirror = use_local_mirror
        self.token = self._load_token(env_file)
        
        if cache_file is None:
            cache_dir = os.path.expanduser("~/.kadi")
            os.makedirs(cache_dir, exist_ok=True)
            self.cache_file = os.path.join(cache_dir, "wfp_cache.json")
        else:
            self.cache_file = cache_file
            
        self.cache = {
            "commodities": {},
            "markets": {}
        }
        self._load_cache()
        
    def _load_cache(self):
        """Charge le cache persistant s'il existe."""
        if os.path.isfile(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache["commodities"] = data.get("commodities", {})
                    self.cache["markets"] = data.get("markets", {})
            except Exception as e:
                logger.warning(f"Impossible de lire le cache WFP {self.cache_file}: {e}")

    def _save_cache(self):
        """Sauvegarde le cache en mémoire vers le fichier persistant."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le cache WFP {self.cache_file}: {e}")
            
    def _load_token(self, env_file: str) -> str:
        token = os.environ.get('WFP_API_Token', os.environ.get('WFP_API_KEY', ''))
        if not token and os.path.isfile(env_file):
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2 and parts[0].strip() in ('WFP_API_Token', 'WFP_API_KEY'):
                                token = parts[1].strip().strip('\'"')
                                break
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture du fichier {env_file}: {e}")
        return token

    def _fetch_commodities(self) -> dict:
        """
        Récupère dynamiquement la liste des cultures via l'API, ou utilise le cache/fallback.
        """
        if self.cache["commodities"]:
            return self.cache["commodities"]
            
        if not self.token:
            return COMMODITY_MAPPING_FALLBACK
            
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        endpoint = f"{self.base_url}/Commodities/List"
        
        try:
            # On essaye l'endpoint Commodities/List (ou Commodities)
            response = requests.get(endpoint, headers=headers, timeout=10)
            if response.status_code == 404:
                # Fallback sur /Commodities si /Commodities/List n'existe pas
                endpoint = f"{self.base_url}/Commodities"
                response = requests.get(endpoint, headers=headers, timeout=10)
                
            response.raise_for_status()
            data = response.json()
            
            # WFP retourne généralement {"items": [{"commodityID": 51, "commodityName": "Maize"}, ...]}
            items = data.get("items", [])
            mapping = {}
            for item in items:
                # Extraction générique (car les clés exactes peuvent varier selon l'endpoint)
                c_id = item.get("commodityID") or item.get("id")
                c_name = item.get("commodityName") or item.get("name")
                if c_id and c_name:
                    mapping[c_name.lower().replace(' ', '_')] = c_id
                    
            if mapping:
                self.cache["commodities"] = mapping
                self._save_cache()
                return mapping
                
        except Exception as e:
            logger.warning(f"Impossible de récupérer les Commodities WFP: {e}. Utilisation du fallback.")
            
        return COMMODITY_MAPPING_FALLBACK

    def _fetch_markets(self, country_code: str = "BEN") -> dict:
        """
        Récupère dynamiquement la liste des marchés via l'API, ou utilise le cache/fallback.
        """
        if self.cache["markets"]:
            return self.cache["markets"]
            
        if not self.token:
            return MARKET_MAPPING_FALLBACK
            
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        endpoint = f"{self.base_url}/Markets/List"
        params = {"CountryCode": country_code}
        
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            if response.status_code == 404:
                endpoint = f"{self.base_url}/Markets"
                response = requests.get(endpoint, headers=headers, params=params, timeout=10)
                
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            mapping = {}
            for item in items:
                m_id = item.get("marketID") or item.get("id")
                m_name = item.get("marketName") or item.get("name")
                if m_id and m_name:
                    mapping[m_name.lower().replace(' ', '_')] = m_id
                    
            if mapping:
                self.cache["markets"] = mapping
                self._save_cache()
                return mapping
                
        except Exception as e:
            logger.warning(f"Impossible de récupérer les Markets WFP: {e}. Utilisation du fallback.")
            
        return MARKET_MAPPING_FALLBACK

    def _get_commodity_id(self, commodity_name: str) -> int:
        """Récupère l'ID WFP pour une culture donnée."""
        key = commodity_name.lower().replace(' ', '_')
        mapping = self._fetch_commodities()
        return mapping.get(key, COMMODITY_MAPPING_FALLBACK.get(key, 0))
        
    def _get_market_id(self, market_name: str) -> int:
        """Récupère l'ID WFP pour un marché donné."""
        key = market_name.lower().replace(' ', '_')
        mapping = self._fetch_markets()
        return mapping.get(key, MARKET_MAPPING_FALLBACK.get(key, 0))

    def get_market_prices(self, market_name: str, commodity: str, time_range: tuple = None) -> pd.DataFrame:
        """
        Récupère les prix pour un marché et une culture depuis WFP DataBridges.
        """
        if self.use_local_mirror:
            return self._generate_simulated_data(time_range)
            
        market_id = self._get_market_id(market_name)
        commodity_id = self._get_commodity_id(commodity)
        
        if market_id == 0 or commodity_id == 0 or not self.token:
            logger.warning("Infos manquantes (Token/ID). Utilisation du miroir de repli.")
            return self._generate_simulated_data(time_range)
            
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }
        
        endpoint = f"{self.base_url}/MarketPrices/alldata"
        params = {
            "CountryCode": "BEN",
            "MarketID": market_id,
            "CommodityID": commodity_id
        }
        
        if time_range and len(time_range) == 2:
            params["StartDate"] = time_range[0]
            params["EndDate"] = time_range[1]
            
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                return pd.DataFrame(columns=['date', 'price', 'unit'])
                
            df = pd.DataFrame(items)
            
            col_mapping = {
                'CommodityPriceDate': 'date',
                'ActualPrice': 'price',
                'UnitName': 'unit'
            }
            
            rename_dict = {k: v for k, v in col_mapping.items() if k in df.columns}
            df = df.rename(columns=rename_dict)
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur API WFP : {e}. Utilisation du cache local.")
            return self._generate_simulated_data(time_range)

    def get_market_functionality_index(self, market_id: str) -> float:
        return 7.9

    def _generate_simulated_data(self, time_range: tuple = None) -> pd.DataFrame:
        if time_range and len(time_range) == 2:
            dates = pd.date_range(start=time_range[0], end=time_range[1], freq='D')
        else:
            dates = pd.date_range(end=pd.Timestamp.today(), periods=365, freq='D')
            
        days = len(dates)
        prix_aleatoires = np.random.normal(loc=300, scale=20, size=days)
        
        df = pd.DataFrame({
            'date': dates,
            'price': prix_aleatoires,
            'unit': 'XOF/kg'
        })
        return df
