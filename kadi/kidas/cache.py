# -*- coding: utf-8 -*-
"""
Module implémentant DataCache pour la gestion du cache SQLite dédié à kidas.

Ce module gère un cache persistant SQLite local distinct du cache global
KadiPy (kadi/cache.py). Il stocke les DataFrames sérialisés avec compression
zlib, supporte le versioning par hash SHA256 et l'invalidation par âge.

Répertoire du cache : ~/.kadi/kidas_cache/
"""

import hashlib
import logging
import os
import pickle
import sqlite3
import zlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Import des exceptions personnalisées
from kadi.exceptions import KidasCacheError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Répertoire par défaut du cache kidas
_DEFAULT_CACHE_DIR: str = os.path.join(os.path.expanduser("~"), ".kadi", "kidas_cache")

# Nom du fichier de base de données SQLite
_DB_FILENAME: str = "kidas_cache.db"


class DataCache:
    """Gestionnaire de cache SQLite persistant pour les données kidas.

    Stocke les DataFrames pandas sous forme sérialisée (pickle + zlib)
    dans une base de données SQLite locale. Supporte le versioning par
    hash SHA256, l'invalidation par âge, et la consultation de l'historique
    des versions antérieures.

    Le cache est distinct du cache global KadiPy (weather, market) et
    utilise son propre répertoire : ~/.kadi/kidas_cache/.

    Attributs:
        cache_dir (str): Répertoire du cache SQLite.
        max_age_days (int): Durée de validité maximale en jours.
        db_path (str): Chemin complet vers le fichier de base de données.

    Exemple:
        >>> cache = DataCache()
        >>> cache.save('recoltes_2024', df)
        >>> df_cached, meta = cache.load('recoltes_2024')
        >>> print(cache.get_cache_size())
        {'total_mb': 1.2, 'num_entries': 3, 'oldest_date': '2026-06-01'}
    """

    def __init__(
        self,
        cache_dir: str = _DEFAULT_CACHE_DIR,
        max_age_days: int = 365,
    ) -> None:
        """Initialise le répertoire du cache et la base de données SQLite.

        Args:
            cache_dir (str): Chemin vers le répertoire du cache. Par défaut
                ~/.kadi/kidas_cache/.
            max_age_days (int): Nombre de jours après lesquels une entrée
                est considérée comme expirée. Par défaut 365.

        Raises:
            KidasCacheError: Si le répertoire ne peut pas être créé.
        """
        # Chemin du répertoire de cache
        self.cache_dir: str = cache_dir

        # Durée de validité maximale des entrées
        self.max_age_days: int = max_age_days

        # Chemin complet vers la base de données SQLite
        self.db_path: str = os.path.join(cache_dir, _DB_FILENAME)

        # Création du répertoire si nécessaire
        self._creer_repertoire()

        # Initialisation des tables de la base de données
        self._initialiser_db()

    def _creer_repertoire(self) -> None:
        """Crée le répertoire du cache s'il n'existe pas encore.

        Raises:
            KidasCacheError: Si la création du répertoire échoue.
        """
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            logger.debug("Répertoire cache kidas : '%s'.", self.cache_dir)
        except OSError as erreur:
            raise KidasCacheError(
                f"Impossible de créer le répertoire cache '{self.cache_dir}' : {erreur}"
            ) from erreur

    def _obtenir_connexion(self) -> sqlite3.Connection:
        """Établit et retourne une connexion à la base de données SQLite.

        Returns:
            sqlite3.Connection: Objet de connexion à la base de données.

        Raises:
            KidasCacheError: En cas d'échec de connexion.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            # Accès aux colonnes par leur nom via Row factory
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Impossible de se connecter au cache '{self.db_path}' : {erreur}"
            ) from erreur

    def _initialiser_db(self) -> None:
        """Initialise les tables SQLite du cache kidas.

        Crée les tables 'kidas_cache' et 'kidas_cache_history' si elles
        n'existent pas déjà.

        Raises:
            KidasCacheError: Si la création des tables échoue.
        """
        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()

                # --- Table principale du cache ---
                # Stocke la version courante de chaque entrée
                curseur.execute("""
                    CREATE TABLE IF NOT EXISTS kidas_cache (
                        key TEXT PRIMARY KEY,
                        data BLOB NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP NOT NULL,
                        hash TEXT NOT NULL
                    );
                """)

                # Index sur la date de création pour les invalidations par âge
                curseur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kidas_cache_date
                    ON kidas_cache (created_at);
                """)

                # --- Table d'historique des versions ---
                # Conserve les versions antérieures pour le versioning
                curseur.execute("""
                    CREATE TABLE IF NOT EXISTS kidas_cache_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT NOT NULL,
                        data BLOB NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP NOT NULL,
                        hash TEXT NOT NULL
                    );
                """)

                # Index pour retrouver l'historique d'une clé spécifique
                curseur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_kidas_history_key
                    ON kidas_cache_history (key, created_at);
                """)

                conn.commit()
                logger.debug("Base de données cache kidas initialisée.")

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur d'initialisation du cache SQLite : {erreur}"
            ) from erreur

    @staticmethod
    def _serialiser(data: pd.DataFrame) -> Tuple[bytes, str]:
        """Sérialise un DataFrame en BLOB compressé et calcule son hash.

        Args:
            data (pd.DataFrame): Le DataFrame à sérialiser.

        Returns:
            tuple[bytes, str]: Tuple (blob_compressé, hash_sha256).
        """
        # Sérialisation pickle du DataFrame
        donnees_pickle = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)

        # Compression zlib pour réduire la taille du stockage
        blob_compresse = zlib.compress(donnees_pickle, level=6)

        # Calcul du hash SHA256 pour le versioning
        hash_sha256 = hashlib.sha256(donnees_pickle).hexdigest()

        return blob_compresse, hash_sha256

    @staticmethod
    def _deserialiser(blob: bytes) -> pd.DataFrame:
        """Désérialise un BLOB compressé en DataFrame pandas.

        Args:
            blob (bytes): Le BLOB compressé issu de la base de données.

        Returns:
            pd.DataFrame: Le DataFrame reconstruit.

        Raises:
            KidasCacheError: Si la désérialisation échoue.
        """
        try:
            # Décompression zlib
            donnees_pickle = zlib.decompress(blob)

            # Désérialisation pickle
            return pickle.loads(donnees_pickle)
        except Exception as erreur:
            raise KidasCacheError(
                f"Impossible de désérialiser les données du cache : {erreur}"
            ) from erreur

    def save(
        self,
        key: str,
        data: pd.DataFrame,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Sauvegarde un DataFrame dans le cache avec compression et horodatage.

        Si une entrée avec la même clé existe déjà, l'ancienne version est
        déplacée dans la table d'historique avant d'être remplacée.

        Args:
            key (str): Clé unique identifiant l'entrée de cache.
            data (pd.DataFrame): Le DataFrame à sauvegarder.
            metadata (dict | None): Métadonnées optionnelles à stocker
                avec les données (ex: source, nb_lignes, colonnes).
                Par défaut None.

        Returns:
            bool: True si la sauvegarde s'est déroulée avec succès.

        Raises:
            KidasCacheError: Si la sauvegarde échoue.
        """
        import json

        try:
            # Sérialisation et compression du DataFrame
            blob, hash_sha256 = self._serialiser(data)

            # Horodatage de la sauvegarde
            maintenant = datetime.now().isoformat()

            # Préparation des métadonnées JSON
            meta_json = json.dumps(metadata or {
                "nb_rows": len(data),
                "nb_cols": len(data.columns),
                "columns": list(data.columns),
            })

            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()

                # Archivage de l'ancienne version si elle existe
                ancienne = curseur.execute(
                    "SELECT key, data, metadata, created_at, hash "
                    "FROM kidas_cache WHERE key = ?",
                    (key,),
                ).fetchone()

                if ancienne:
                    curseur.execute(
                        "INSERT INTO kidas_cache_history "
                        "(key, data, metadata, created_at, hash) VALUES (?, ?, ?, ?, ?)",
                        (
                            ancienne["key"],
                            ancienne["data"],
                            ancienne["metadata"],
                            ancienne["created_at"],
                            ancienne["hash"],
                        ),
                    )

                # Insertion ou mise à jour de l'entrée principale
                curseur.execute(
                    "INSERT OR REPLACE INTO kidas_cache "
                    "(key, data, metadata, created_at, hash) VALUES (?, ?, ?, ?, ?)",
                    (key, blob, meta_json, maintenant, hash_sha256),
                )

                conn.commit()

            logger.info(
                "Cache kidas : clé '%s' sauvegardée (%d lignes, hash: %s...).",
                key,
                len(data),
                hash_sha256[:8],
            )
            return True

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors de la sauvegarde en cache (clé '{key}') : {erreur}"
            ) from erreur

    def load(
        self,
        key: str,
        check_validity: bool = True,
    ) -> Tuple[Optional[pd.DataFrame], Optional[Dict]]:
        """Charge un DataFrame depuis le cache.

        Args:
            key (str): Clé identifiant l'entrée à charger.
            check_validity (bool): Si True, retourne (None, None) si l'entrée
                est plus ancienne que max_age_days. Par défaut True.

        Returns:
            tuple[pd.DataFrame | None, dict | None]: Tuple contenant :
                - Le DataFrame chargé, ou None si absent/expiré.
                - Les métadonnées, ou None si absent/expiré.
        """
        import json

        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()
                ligne = curseur.execute(
                    "SELECT data, metadata, created_at FROM kidas_cache WHERE key = ?",
                    (key,),
                ).fetchone()

            if not ligne:
                logger.debug("Cache kidas : clé '%s' introuvable.", key)
                return None, None

            # Vérification de la fraîcheur si demandée
            if check_validity:
                date_creation = datetime.fromisoformat(ligne["created_at"])
                age = datetime.now() - date_creation

                if age > timedelta(days=self.max_age_days):
                    logger.info(
                        "Cache kidas : clé '%s' expirée (%d jours > %d jours max).",
                        key,
                        age.days,
                        self.max_age_days,
                    )
                    return None, None

            # Désérialisation du DataFrame
            df = self._deserialiser(ligne["data"])
            metadata = json.loads(ligne["metadata"]) if ligne["metadata"] else {}

            logger.info(
                "Cache kidas : clé '%s' chargée (%d lignes).", key, len(df)
            )
            return df, metadata

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors du chargement depuis le cache (clé '{key}') : {erreur}"
            ) from erreur

    def get_cached_keys(self) -> List[str]:
        """Retourne la liste de toutes les clés enregistrées dans le cache.

        Returns:
            list[str]: Liste ordonnée alphabétiquement des clés de cache.
        """
        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()
                resultats = curseur.execute(
                    "SELECT key FROM kidas_cache ORDER BY key"
                ).fetchall()

            return [r["key"] for r in resultats]

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors de la récupération des clés de cache : {erreur}"
            ) from erreur

    def invalidate(self, key: str) -> bool:
        """Supprime une entrée spécifique du cache (sans effacer l'historique).

        Args:
            key (str): Clé de l'entrée à invalider.

        Returns:
            bool: True si l'entrée a été supprimée, False si elle n'existait pas.
        """
        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()
                curseur.execute(
                    "DELETE FROM kidas_cache WHERE key = ?", (key,)
                )
                nb_supprimes = curseur.rowcount
                conn.commit()

            if nb_supprimes > 0:
                logger.info("Cache kidas : clé '%s' invalidée.", key)
            else:
                logger.debug("Cache kidas : clé '%s' introuvable pour invalidation.", key)

            return nb_supprimes > 0

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors de l'invalidation de la clé '{key}' : {erreur}"
            ) from erreur

    def invalidate_older_than(self, days: int) -> int:
        """Supprime toutes les entrées de cache plus anciennes que N jours.

        Args:
            days (int): Âge maximum en jours des entrées à conserver.

        Returns:
            int: Nombre d'entrées supprimées.
        """
        # Calcul de la date seuil
        date_seuil = (datetime.now() - timedelta(days=days)).isoformat()

        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()
                curseur.execute(
                    "DELETE FROM kidas_cache WHERE created_at < ?",
                    (date_seuil,),
                )
                nb_supprimes = curseur.rowcount
                conn.commit()

            logger.info(
                "Cache kidas : %d entrée(s) de plus de %d jours supprimée(s).",
                nb_supprimes,
                days,
            )
            return nb_supprimes

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors de l'invalidation par âge : {erreur}"
            ) from erreur

    def get_cache_size(self) -> dict:
        """Retourne des statistiques sur la taille du cache.

        Returns:
            dict: Dictionnaire contenant :
                - 'total_mb' (float) : taille totale du fichier SQLite en Mo.
                - 'num_entries' (int) : nombre d'entrées dans le cache.
                - 'oldest_date' (str | None) : date de la plus ancienne entrée.
        """
        # Taille du fichier SQLite
        taille_mo = 0.0
        if os.path.isfile(self.db_path):
            taille_mo = os.path.getsize(self.db_path) / (1024 * 1024)

        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()

                # Comptage des entrées
                nb_entrees = curseur.execute(
                    "SELECT COUNT(*) FROM kidas_cache"
                ).fetchone()[0]

                # Date de la plus ancienne entrée
                date_ancienne = curseur.execute(
                    "SELECT MIN(created_at) FROM kidas_cache"
                ).fetchone()[0]

            return {
                "total_mb": round(taille_mo, 3),
                "num_entries": nb_entrees,
                "oldest_date": date_ancienne[:10] if date_ancienne else None,
            }

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors du calcul de la taille du cache : {erreur}"
            ) from erreur

    def clear(self) -> bool:
        """Vide complètement le cache (tables principale et historique).

        Returns:
            bool: True si le vidage s'est déroulé avec succès.
        """
        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()
                curseur.execute("DELETE FROM kidas_cache")
                curseur.execute("DELETE FROM kidas_cache_history")
                conn.commit()

            logger.info("Cache kidas vidé complètement.")
            return True

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors du vidage du cache : {erreur}"
            ) from erreur

    def get_history(self, key: str) -> List[Dict]:
        """Retourne l'historique des versions antérieures d'une clé.

        Args:
            key (str): Clé dont on veut consulter l'historique.

        Returns:
            list[dict]: Liste ordonnée chronologiquement des versions,
                chacune avec les clés 'created_at', 'hash' et 'size_bytes'.
        """
        try:
            with self._obtenir_connexion() as conn:
                curseur = conn.cursor()
                resultats = curseur.execute(
                    "SELECT created_at, hash, LENGTH(data) as size_bytes "
                    "FROM kidas_cache_history "
                    "WHERE key = ? ORDER BY created_at DESC",
                    (key,),
                ).fetchall()

            historique = [
                {
                    "created_at": r["created_at"],
                    "hash": r["hash"][:16] + "...",
                    "size_bytes": r["size_bytes"],
                }
                for r in resultats
            ]

            logger.debug(
                "Historique cache pour clé '%s' : %d version(s).",
                key,
                len(historique),
            )
            return historique

        except sqlite3.Error as erreur:
            raise KidasCacheError(
                f"Erreur lors de la récupération de l'historique pour '{key}' : {erreur}"
            ) from erreur
