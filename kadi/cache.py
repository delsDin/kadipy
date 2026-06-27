"""
Module de gestion du cache local (SQLite) pour KadiPy.

Ce module gère la connexion à la base de données SQLite locale, 
l'initialisation des schémas de base de données (météo, prix, métadonnées),
ainsi que les opérations d'insertion et de récupération de base.
L'objectif est d'assurer un fonctionnement "offline-first".
"""

import sqlite3
import logging

# Import du chemin de la base de données défini dans la configuration globale
from kadi.config import CACHE_DB
# Import de l'exception spécifique pour gérer les erreurs de cache
from kadi.exceptions import CacheError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """
    Établit et retourne une connexion à la base de données locale SQLite.
    
    Returns:
        sqlite3.Connection: Objet de connexion à la base de données locale.
    
    Raises:
        CacheError: En cas de problème lors de la connexion (ex: permissions).
    """
    try:
        # Connexion à la base de données SQLite via le chemin défini
        conn = sqlite3.connect(CACHE_DB)
        
        # On active l'accès aux colonnes par leur nom (dictionnaire-like) via Row
        conn.row_factory = sqlite3.Row
        
        # Retourne l'objet de connexion prêt à l'emploi
        return conn
    
    except sqlite3.Error as e:
        # Journalisation de l'erreur en cas d'échec
        logger.error(f"Erreur de connexion SQLite: {e}")
        
        # Levée d'une exception personnalisée KadiPy
        raise CacheError(f"Impossible de se connecter au cache : {e}")


def init_db() -> None:
    """
    Initialise la base de données SQLite en créant les tables nécessaires
    si elles n'existent pas déjà.
    
    Les tables créées sont :
    - weather_data : historique et prévisions météo
    - market_prices : prix des marchés locaux
    - data_imports : métadonnées des imports locaux (fichiers Excel/CSV)
    - cache_metadata : état du cache et synchronisation
    - price_predictions : prédictions générées par le module de machine learning
    
    Raises:
        CacheError: Si l'exécution des requêtes SQL échoue.
    """
    try:
        # Ouverture de la connexion à la base de données
        with get_connection() as conn:
            # Création d'un curseur pour exécuter les requêtes SQL
            cursor = conn.cursor()
            
            # --- 1. Création de la table weather_data ---
            # Stocke les données météorologiques (températures, précipitations, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    date TEXT NOT NULL,
                    hour INTEGER,
                    temperature_min REAL,
                    temperature_max REAL,
                    temperature_avg REAL,
                    humidity REAL,
                    precipitation REAL,
                    wind_speed REAL,
                    wind_direction INTEGER,
                    solar_radiation REAL,
                    data_type TEXT,
                    data_source TEXT,
                    confidence REAL,
                    fetched_at TIMESTAMP,
                    UNIQUE(location_id, date, hour)
                );
            """)
            
            # Index pour accélérer les requêtes météo par lieu et par date
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_location_date "
                "ON weather_data (location_id, date);"
            )
            
            # --- 2. Création de la table market_prices ---
            # Stocke les relevés de prix des marchés (ex: WFP VAM, sources locales)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crop_code TEXT NOT NULL,
                    crop_name_local TEXT,
                    market_code TEXT NOT NULL,
                    market_name TEXT,
                    latitude REAL,
                    longitude REAL,
                    date TEXT NOT NULL,
                    week_start DATE,
                    price_xof REAL NOT NULL,
                    price_original REAL,
                    price_unit_original TEXT,
                    price_usd REAL,
                    data_source TEXT,
                    confidence REAL,
                    freshness_days INTEGER,
                    fetched_at TIMESTAMP,
                    UNIQUE(crop_code, market_code, date, data_source)
                );
            """)
            
            # Index pour accélérer la recherche par produit, marché et date
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_crop_market_date "
                "ON market_prices (crop_code, market_code, date);"
            )
            
            # Index pour trier/filtrer par fraîcheur et source
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_freshness "
                "ON market_prices (data_source, fetched_at);"
            )

            # --- 3. Création de la table data_imports ---
            # Permet la traçabilité des fichiers Excel/CSV importés par l'utilisateur
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    filepath TEXT,
                    file_size INTEGER,
                    file_hash TEXT,
                    detected_encoding TEXT,
                    detected_delimiter TEXT,
                    columns_raw TEXT,
                    columns_normalized TEXT,
                    data_quality_score REAL,
                    row_count INTEGER,
                    first_row_sample TEXT,
                    warnings TEXT,
                    import_timestamp TIMESTAMP
                );
            """)
            
            # Index sur la date d'import pour retrouver rapidement les derniers imports
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_import_timestamp "
                "ON data_imports (import_timestamp);"
            )

            # --- 4. Création de la table cache_metadata ---
            # Garde une trace des dernières synchronisations, des sources et de l'état du cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    data_source TEXT,
                    last_fetch TIMESTAMP,
                    last_success TIMESTAMP,
                    last_update TIMESTAMP,
                    record_count INTEGER,
                    cache_size_mb REAL,
                    sync_needed BOOLEAN DEFAULT 0,
                    sync_last_attempt TIMESTAMP,
                    config_json TEXT,
                    UNIQUE(module_name, data_source)
                );
            """)
            
            # Index sur la date de dernier fetch
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_last_fetch "
                "ON cache_metadata (last_fetch);"
            )

            # --- 5. Création de la table price_predictions ---
            # Enregistre les prédictions générées pour éviter de recalculer inutilement
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crop_code TEXT NOT NULL,
                    market_code TEXT NOT NULL,
                    prediction_date DATE NOT NULL,
                    target_date DATE NOT NULL,
                    days_ahead INTEGER,
                    predicted_price_xof REAL,
                    predicted_price_low REAL,
                    predicted_price_high REAL,
                    confidence REAL,
                    model_version TEXT,
                    model_type TEXT,
                    training_points INTEGER,
                    UNIQUE(crop_code, market_code, prediction_date, target_date)
                );
            """)
            
            # Index pour retrouver une prédiction spécifique pour un produit, marché et date cible
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_crop_market_target "
                "ON price_predictions (crop_code, market_code, target_date);"
            )
            
            # Validation (commit) de toutes les créations de tables
            conn.commit()
            
            # Journalisation du succès de l'opération
            logger.info("Base de données locale initialisée avec succès.")
            
    except sqlite3.Error as e:
        # Journalisation de l'erreur
        logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
        
        # Levée de l'exception spécifique KadiPy
        raise CacheError(f"Échec de création des tables de cache : {e}")
