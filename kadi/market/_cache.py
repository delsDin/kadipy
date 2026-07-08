"""
Module de cache persistant pour les données de prix de marché.

Les données sont stockées dans une base SQLite localisée dans ~/kadi/
(via CACHE_DIR défini dans kadi.config). Ce module évite de re-télécharger
des données déjà fraîches depuis l'API WFP, et permet de travailler hors
ligne quand la clé API n'est pas encore disponible.

Tables utilisées :
    - market_prices : une ligne par observation de prix (marché, culture, date)
    - cache_meta    : métadonnées sur la dernière mise à jour par (marché, culture)
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

# Import du chemin de cache depuis la configuration centrale
from kadi.config import CACHE_DIR

logger = logging.getLogger(__name__)

# Base SQLite dédiée aux prix de marché, séparée du cache global
MARKET_DB_PATH = CACHE_DIR / "market_prices.db"


def _connexion(db_path: Path = MARKET_DB_PATH) -> sqlite3.Connection:
    """
    Ouvre et retourne une connexion SQLite avec WAL activé.

    Utilise le mode WAL (Write-Ahead Logging) pour de meilleures performances
    en lecture concurrente et active les clés étrangères.

    Args:
        db_path (Path): Chemin vers le fichier SQLite à utiliser.

    Returns:
        sqlite3.Connection: Une connexion SQLite configurée.
    """
    # S'assurer que le répertoire parent existe
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))

    # Mode WAL : améliore les performances en lecture concurrente
    conn.execute("PRAGMA journal_mode=WAL;")

    # Activation des contraintes de clés étrangères
    conn.execute("PRAGMA foreign_keys=ON;")

    return conn


def initialiser_base(db_path: Path = MARKET_DB_PATH) -> None:
    """
    Crée les tables du cache si elles n'existent pas encore.

    Idempotente : peut être appelée plusieurs fois sans erreur.
    Appelée automatiquement par les autres fonctions du module.

    Args:
        db_path (Path): Chemin vers le fichier SQLite. Utilise MARKET_DB_PATH par défaut.
    """
    with _connexion(db_path) as conn:
        # Table principale : une ligne par observation de prix
        # La contrainte UNIQUE sur (market, crop, date) permet le dédoublonnage
        # via INSERT OR IGNORE dans sauvegarder_prix().
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_prices (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                market       TEXT    NOT NULL,
                crop         TEXT    NOT NULL,
                date         TEXT    NOT NULL,
                price        REAL    NOT NULL,
                unit         TEXT    NOT NULL DEFAULT 'XOF/kg',
                source       TEXT    NOT NULL DEFAULT 'simulated',
                is_simulated INTEGER NOT NULL DEFAULT 1,
                fetched_at   TEXT    NOT NULL,
                UNIQUE (market, crop, date)
            );
        """)

        # Index composite pour accélérer les recherches par (marché, culture)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_crop
            ON market_prices (market, crop);
        """)

        # Index secondaire sur la date pour les tris chronologiques
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_date
            ON market_prices (date);
        """)

        # Table de métadonnées : état de la dernière mise à jour par (marché, culture)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_meta (
                market     TEXT NOT NULL,
                crop       TEXT NOT NULL,
                last_fetch TEXT NOT NULL,
                source     TEXT NOT NULL DEFAULT 'simulated',
                nb_records INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (market, crop)
            );
        """)

        conn.commit()


def sauvegarder_prix(
    market: str,
    crop: str,
    df: pd.DataFrame,
    source: str = "simulated",
    db_path: Path = MARKET_DB_PATH,
) -> int:
    """
    Sauvegarde un DataFrame de prix dans le cache SQLite.

    Les lignes déjà présentes pour la même (marché, culture, date) ne sont
    pas dupliquées grâce à INSERT OR IGNORE.

    Args:
        market (str): Nom normalisé du marché (ex: 'cotonou').
        crop (str): Code de la culture (ex: 'maize').
        df (pd.DataFrame): DataFrame avec au minimum les colonnes 'date' et 'price'.
        source (str): Identifiant de la source des données.
            Valeurs attendues : 'wfp-vam', 'ratin', 'scrape-local', 'simulated'.
        db_path (Path): Chemin vers le fichier SQLite.

    Returns:
        int: Nombre de nouvelles lignes effectivement insérées (les doublons
            ignorés ne sont pas comptés).

    Raises:
        ValueError: Si les colonnes 'date' ou 'price' sont absentes du DataFrame.
    """
    # S'assurer que la base est initialisée
    initialiser_base(db_path)

    # Vérification des colonnes requises
    colonnes_requises = {"date", "price"}
    colonnes_manquantes = colonnes_requises - set(df.columns)
    if colonnes_manquantes:
        raise ValueError(
            f"Colonnes manquantes dans le DataFrame pour la sauvegarde : {colonnes_manquantes}"
        )

    # Horodatage du moment de la sauvegarde (UTC avec info de fuseau)
    maintenant = datetime.now(timezone.utc).isoformat()
    lignes_inserees = 0

    with _connexion(db_path) as conn:
        for _, ligne in df.iterrows():
            # Conversion de la date en string ISO si nécessaire
            date_val = ligne["date"]
            date_str = (
                date_val.isoformat()
                if hasattr(date_val, "isoformat")
                else str(date_val)
            )

            # Lecture des colonnes optionnelles avec valeurs par défaut
            unite = ligne.get("unit", "XOF/kg") if "unit" in df.columns else "XOF/kg"
            est_simule = (
                int(bool(ligne["is_simulated"])) if "is_simulated" in df.columns else 1
            )

            # Insertion en ignorant les doublons (même marché, culture, date)
            curseur = conn.execute(
                """
                INSERT OR IGNORE INTO market_prices
                    (market, crop, date, price, unit, source, is_simulated, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market, crop, date_str,
                    float(ligne["price"]),
                    str(unite), source,
                    est_simule, maintenant,
                ),
            )
            lignes_inserees += curseur.rowcount

        # Mise à jour (ou création) de la métadonnée (marché, culture)
        conn.execute(
            """
            INSERT INTO cache_meta (market, crop, last_fetch, source, nb_records)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(market, crop) DO UPDATE SET
                last_fetch  = excluded.last_fetch,
                source      = excluded.source,
                nb_records  = (
                    SELECT COUNT(*) FROM market_prices
                    WHERE market = excluded.market AND crop = excluded.crop
                )
            """,
            (market, crop, maintenant, source, lignes_inserees),
        )
        conn.commit()

    logger.debug(
        f"Cache : {lignes_inserees} nouvelles lignes pour {market}/{crop} "
        f"(source: {source})."
    )
    return lignes_inserees


def recuperer_prix(
    market: str,
    crop: str,
    max_age_jours: int = 7,
    db_path: Path = MARKET_DB_PATH,
) -> Optional[pd.DataFrame]:
    """
    Récupère les prix depuis le cache SQLite si les données sont fraîches.

    Retourne None si aucune donnée n'existe ou si les données dépassent
    l'âge maximum autorisé. Dans ce cas, l'appelant doit aller chercher
    des données fraîches auprès de l'API.

    Args:
        market (str): Nom normalisé du marché.
        crop (str): Code de la culture.
        max_age_jours (int): Âge maximum acceptable en jours. Défaut : 7.
        db_path (Path): Chemin vers le fichier SQLite.

    Returns:
        pd.DataFrame: DataFrame avec colonnes 'date', 'price', 'unit',
            'is_simulated', 'source', 'fetched_at' si les données sont fraîches.
        None: Si le cache est vide ou périmé.
    """
    initialiser_base(db_path)

    with _connexion(db_path) as conn:
        # Vérification de la fraîcheur via la table de métadonnées
        curseur = conn.execute(
            "SELECT last_fetch FROM cache_meta WHERE market = ? AND crop = ?",
            (market, crop),
        )
        meta = curseur.fetchone()

    if meta is None:
        # Aucune entrée dans le cache pour ce couple (marché, culture)
        return None

    # Calcul de l'âge des données
    try:
        last_fetch_dt = datetime.fromisoformat(meta[0])
        # On travaille toujours en UTC. Si le timestamp est naive, on le traite
        # comme UTC pour la compatibilité avec les anciennes entrées.
        if last_fetch_dt.tzinfo is None:
            last_fetch_dt = last_fetch_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    age = datetime.now(timezone.utc) - last_fetch_dt
    if age > timedelta(days=max_age_jours):
        logger.info(
            f"Cache périmé pour {market}/{crop} "
            f"({age.days} j > {max_age_jours} j maximum)."
        )
        return None

    # Récupération des données encore fraîches
    with _connexion(db_path) as conn:
        df = pd.read_sql_query(
            """
            SELECT date, price, unit, is_simulated, source, fetched_at
            FROM market_prices
            WHERE market = ? AND crop = ?
            ORDER BY date ASC
            """,
            conn,
            params=(market, crop),
        )

    if df.empty:
        return None

    # Conversion du type de la colonne date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Conversion du flag is_simulated en booléen Python natif
    df["is_simulated"] = df["is_simulated"].astype(bool)

    return df


def obtenir_info_fraicheur(
    market: str,
    crop: str,
    db_path: Path = MARKET_DB_PATH,
) -> dict:
    """
    Retourne les informations de fraîcheur des données en cache.

    Utile pour informer l'utilisateur de l'ancienneté des données
    et pour calculer le score de confiance.

    Args:
        market (str): Nom normalisé du marché.
        crop (str): Code de la culture.
        db_path (Path): Chemin vers le fichier SQLite.

    Returns:
        dict: Dictionnaire avec les clés :
            - 'en_cache' (bool)    : True si des données existent.
            - 'age_jours' (float)  : Âge en jours, ou None si absent.
            - 'source' (str)       : Source de la dernière mise à jour.
            - 'nb_records' (int)   : Nombre de points de données stockés.
            - 'last_fetch' (str)   : Horodatage ISO de la dernière mise à jour.
    """
    initialiser_base(db_path)

    with _connexion(db_path) as conn:
        curseur = conn.execute(
            "SELECT last_fetch, source, nb_records FROM cache_meta WHERE market = ? AND crop = ?",
            (market, crop),
        )
        meta = curseur.fetchone()

    if meta is None:
        return {
            "en_cache": False,
            "age_jours": None,
            "source": None,
            "nb_records": 0,
            "last_fetch": None,
        }

    # Calcul de l'âge à partir du timestamp stocké
    try:
        last_fetch_dt = datetime.fromisoformat(meta[0])
        if last_fetch_dt.tzinfo is None:
            last_fetch_dt = last_fetch_dt.replace(tzinfo=timezone.utc)
        age_jours = (datetime.now(timezone.utc) - last_fetch_dt).total_seconds() / 86400.0
    except ValueError:
        age_jours = None

    return {
        "en_cache": True,
        "age_jours": round(age_jours, 2) if age_jours is not None else None,
        "source": meta[1],
        "nb_records": meta[2],
        "last_fetch": meta[0],
    }


def calculer_score_confiance(
    market: str,
    crop: str,
    max_age_jours: int = 7,
    db_path: Path = MARKET_DB_PATH,
) -> float:
    """
    Calcule un score de confiance entre 0.0 et 1.0 pour les données en cache.

    Le score combine deux facteurs indépendants :
    - La source (WFP officiel = 1.0, données simulées = 0.1)
    - La fraîcheur (score décroissant linéairement sur max_age_jours)

    Formule : score = score_source * score_fraicheur

    Ce score est conçu pour être affiché à l'utilisateur et pour
    avertir clairement quand les données ne sont pas fiables (< 0.3).

    Args:
        market (str): Nom normalisé du marché.
        crop (str): Code de la culture.
        max_age_jours (int): Âge de référence pour le calcul de la fraîcheur.
        db_path (Path): Chemin vers le fichier SQLite.

    Returns:
        float: Score de confiance arrondi à 3 décimales.
    """
    info = obtenir_info_fraicheur(market, crop, db_path)

    if not info["en_cache"]:
        # Aucune donnée en cache : confiance nulle
        return 0.0

    # Score basé sur la source
    scores_sources = {
        "wfp-vam": 1.0,       # Source officielle ONU : confiance maximale
        "ratin": 0.85,         # Réseau régional de collecte terrain
        "scrape-local": 0.65,  # Agrégation de sources locales non officielles
        "simulated": 0.1,      # Données entièrement fictives
    }
    source = info.get("source") or "simulated"
    score_source = scores_sources.get(source, 0.5)

    # Score basé sur la fraîcheur (décroissance linéaire)
    age = info.get("age_jours")
    if age is None or age < 0:
        score_fraicheur = 0.0
    elif age <= max_age_jours:
        # De 1.0 (données fraîches) à 0.1 (données au bord de l'expiration)
        score_fraicheur = max(0.1, 1.0 - (age / max_age_jours) * 0.9)
    else:
        # Données périmées
        score_fraicheur = 0.05

    return round(score_source * score_fraicheur, 3)


def vider_cache(
    market: str = None,
    crop: str = None,
    db_path: Path = MARKET_DB_PATH,
) -> int:
    """
    Supprime les données du cache pour un marché/culture ou pour tout le cache.

    Args:
        market (str, optional): Si fourni, supprime uniquement ce marché.
        crop (str, optional): Si fourni (avec market), supprime uniquement cette culture.
        db_path (Path): Chemin vers le fichier SQLite.

    Returns:
        int: Nombre de lignes supprimées dans market_prices.
    """
    initialiser_base(db_path)

    with _connexion(db_path) as conn:
        if market and crop:
            conn.execute(
                "DELETE FROM market_prices WHERE market = ? AND crop = ?",
                (market, crop),
            )
            conn.execute(
                "DELETE FROM cache_meta WHERE market = ? AND crop = ?",
                (market, crop),
            )
        elif market:
            conn.execute("DELETE FROM market_prices WHERE market = ?", (market,))
            conn.execute("DELETE FROM cache_meta WHERE market = ?", (market,))
        else:
            conn.execute("DELETE FROM market_prices;")
            conn.execute("DELETE FROM cache_meta;")

        nb = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()

    return nb
