"""
Module de configuration globale pour KadiPy.

Ce module définit les chemins d'accès par défaut (cache, logs, modèles),
les paramètres de configuration pour les différents modules (météo, marché, data),
ainsi que les URL d'API et les taux de change.
"""

import os
from pathlib import Path

# Définition du répertoire de cache dans le dossier utilisateur
CACHE_DIR = Path.home() / ".kadi"

# Création du répertoire de cache s'il n'existe pas déjà
CACHE_DIR.mkdir(exist_ok=True)

# Chemins vers les bases de données SQLite de cache et de sauvegarde
CACHE_DB = CACHE_DIR / "cache.db"
CACHE_DB_BACKUP = CACHE_DIR / "cache_backup.db"

# Définition du répertoire pour les fichiers de journalisation (logs)
LOG_DIR = CACHE_DIR / "logs"

# Création du répertoire de logs s'il n'existe pas déjà
LOG_DIR.mkdir(exist_ok=True)

# Chemin vers le fichier de journalisation principal
LOG_FILE = LOG_DIR / "kadi.log"

# Chemin vers le répertoire contenant les modèles Machine Learning pré-entraînés
# Ce chemin est relatif à l'emplacement de ce fichier de configuration
MODELS_DIR = Path(__file__).parent / "_ml" / "models"

# Dictionnaire de configuration par défaut pour les différents modules
CONFIG = {
    # ---------------------------------------------------------
    # Paramètres liés au module météo (kadi.weather)
    # ---------------------------------------------------------
    "weather": {
        # Localisation par défaut si aucune n'est spécifiée par l'utilisateur
        "default_location": None,
        
        # Nombre de jours de prévision météorologique à récupérer par défaut
        "forecast_days_default": 7,
        
        # Limite maximale de jours pour les prévisions météorologiques (Open-Meteo permet souvent 14-16j)
        "max_forecast_days": 15,
        
        # Durée de vie en cache des prévisions météo (en heures), après quoi une nouvelle requête API sera faite
        "cache_ttl_forecast_hours": 24,
        
        # Durée de vie en cache des données historiques (en jours). 
        # Les données passées ne changent pas, la durée est donc très longue (1 an).
        "cache_ttl_historical_days": 365,
        
        # Nombre de tentatives de connexion en cas d'échec de la requête API (timeout/réseau)
        "retry_attempts": 3,
        
        # Temps d'attente (en secondes) avant de retenter une requête API après un échec
        "retry_backoff_sec": 5,
        
        # Zone géographique couverte par la V1 : le Bénin uniquement.
        # Tout point en dehors de cette boîte englobante est rejeté.
        # Limites : lat [2.5°N, 12.5°N], lon [-1.5°E, 4.0°E]
        "gps_validation_bbox": {
            "min_lat": 2.5,
            "max_lat": 12.5,
            "min_lon": -1.5,
            "max_lon": 4.0,
        },
    },

    # ---------------------------------------------------------
    # Paramètres liés au module de marché (kadi.market)
    # ---------------------------------------------------------
    "market": {
        # Ordre de priorité des sources pour récupérer les prix (fallback automatique)
        "sources_priority": ["wfp-vam", "ratin", "scrape-local"],

        # Minimum d'historique requis (en semaines) pour que le modèle ML
        # de prédiction des prix soit fiable
        "min_history_weeks": 52,

        # Durée de vie en cache des prix récupérés (en jours),
        # avant de vérifier s'il y a des prix plus récents
        "cache_ttl_prices_days": 7,

        # Durée de vie en cache des prédictions générées par le modèle local (en jours)
        "cache_ttl_predictions_days": 1,

        # Nombre de tentatives de connexion à la source de données de prix
        "retry_attempts": 3,

        # Temps d'attente initial (en secondes) avant de relancer une requête
        # Le backoff exponentiel multiplie ce délai à chaque tentative
        "retry_backoff_sec": 2,

        # Délai minimal entre deux requêtes vers Nominatim (OpenStreetMap)
        # Nominatim impose une limite stricte d'1 requête par seconde
        "nominatim_delay_sec": 1.1,
    },

    # ---------------------------------------------------------
    # Coefficients logistiques (kadi.market.logistics)
    # Ces paramètres modélisent les frictions de terrain au Bénin.
    # Ils sont centralisés ici pour être facilement ajustables.
    # ---------------------------------------------------------
    "logistics": {
        # Coût fixe de recherche d'informations (en XOF) :
        # temps passé à appeler les acheteurs, vérifier les prix, etc.
        "c_info_xof": 5000.0,

        # Coefficient d'état de la route (gamma_route) :
        # multiplicateur appliqué au prix du carburant par km.
        # 1.0 = route parfaite, 1.2 = route normale béninoise,
        # 1.5 = piste dégradée. À ajuster selon la saison.
        "gamma_route": 1.2,

        # Coût moyen des tracasseries policières par kilomètre (en XOF/km) :
        # représente les postes de contrôle, les frais informels, etc.
        "mu_checkpoints_xof_per_km": 15.0,

        # Perte de qualité fixe par trajet (en XOF) :
        # dégradation due aux manipulations, à la chaleur, aux chocs.
        # Valeur de base pour les céréales sèches. Les produits frais
        # (tomate, etc.) subiront un coefficient supplémentaire.
        "c_qualite_loss_xof": 2500.0,

        # Facteur de consommation du véhicule (litres pour 100 km) :
        # utilisé pour calculer le coût carburant en complément de gamma_route
        "consommation_l_per_100km": 12.0,

        # Seuil de rentabilité minimum (en %) pour recommander un transfert
        "seuil_rentabilite_pct": 10.0,

        # Prix de carburant de repli si toutes les sources échouent (en XOF/litre)
        "prix_carburant_fallback_xof": 680.0,
    },

    # ---------------------------------------------------------
    # Paramètres liés au module de traitement de données (kadi.kidas)
    # ---------------------------------------------------------
    "kidas": {
        # Taille maximale des fichiers (en mégaoctets) acceptée pour les imports locaux (Excel/CSV)
        "max_file_size_mb": 100,
        
        # Taille de l'échantillon (en octets) lue pour deviner automatiquement l'encodage du fichier
        "encoding_detection_sample_size": 100_000,
        
        # Coordonnées géographiques délimitant la zone d'étude (ici, l'Afrique de l'Ouest)
        # Permet de rejeter ou corriger les anomalies (ex: latitudes/longitudes inversées)
        "gps_validation_bbox": {
            "min_lat": -18.0,
            "max_lat": 16.0,
            "min_lon": -18.0,
            "max_lon": 4.0,
        },
    },
}

# URL des API externes, pouvant être surchargées par des variables d'environnement
OPENMETEO_API_URL = os.environ.get(
    "OPENMETEO_API_URL",
    "https://api.open-meteo.com/v1"
)

WFP_VAM_API_URL = os.environ.get(
    "WFP_VAM_API_URL",
    "https://hungermap.wfp.org"
)

RATIN_SCRAPE_URL = os.environ.get(
    "RATIN_SCRAPE_URL",
    "https://www.ratin.net"
)

# Taux de change par défaut pour les conversions de devises
EXCHANGE_RATES = {
    "XOF_USD": 0.0016,  # Mise à jour quotidienne prévue
    "XOF_EUR": 0.0015,
}
