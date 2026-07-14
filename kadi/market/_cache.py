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

    Tables créées :
        - market_prices    : une ligne par observation de prix
        - cache_meta       : métadonnées de la dernière mise à jour
        - price_predictions: prévisions générées par le module forecasting

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

        # Table des prévisions : une ligne par prévision générée.
        # Permet le backtesting futur (Phase 5) en comparant predicted_price
        # aux observations réelles de la table market_prices.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_predictions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                market          TEXT    NOT NULL,
                crop            TEXT    NOT NULL,
                generated_at    TEXT    NOT NULL,
                target_date     TEXT    NOT NULL,
                days_ahead      INTEGER NOT NULL,
                predicted_price REAL    NOT NULL,
                low_bound       REAL    NOT NULL,
                high_bound      REAL    NOT NULL,
                confidence      REAL    NOT NULL,
                rmse            REAL,
                model_used      TEXT    NOT NULL DEFAULT 'linear_regression',
                is_simulated    INTEGER NOT NULL DEFAULT 0,
                nb_history_pts  INTEGER NOT NULL DEFAULT 0
            );
        """)

        # Index pour retrouver rapidement les prévisions par (marché, culture)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pred_market_crop
            ON price_predictions (market, crop);
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


def sauvegarder_prediction(
    market: str,
    crop: str,
    prediction: dict,
    db_path: Path = MARKET_DB_PATH,
) -> int:
    """
    Sauvegarde une prévision de prix dans la table price_predictions.

    Cette table permet de comparer ultérieurement (Phase 5) les prévisions
    passées aux prix réels observés (backtesting).

    Args:
        market (str): Nom normalisé du marché (ex: 'cotonou').
        crop (str): Code de la culture (ex: 'maize').
        prediction (dict): Dictionnaire retourné par MarketForecasting.predict_price().
            Doit contenir au minimum : 'predicted_price', 'low_90', 'high_90',
            'confidence', 'rmse', 'model_used', 'is_simulated', 'days_ahead'.
        db_path (Path): Chemin vers le fichier SQLite.

    Returns:
        int: L'identifiant (rowid) de la prévision insérée, ou -1 en cas d'échec.
    """
    # Initialisation de la base si nécessaire
    initialiser_base(db_path)

    # Horodatage de la génération de la prévision (UTC)
    maintenant = datetime.now(timezone.utc).isoformat()

    # Calcul de la date cible à partir du nombre de jours
    # timedelta est déjà importé en tête du module depuis datetime
    days_ahead = int(prediction.get("days_ahead", 7))
    date_cible = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).date().isoformat()

    with _connexion(db_path) as conn:
        curseur = conn.execute(
            """
            INSERT INTO price_predictions
                (market, crop, generated_at, target_date, days_ahead,
                 predicted_price, low_bound, high_bound, confidence,
                 rmse, model_used, is_simulated, nb_history_pts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                market,
                crop,
                maintenant,
                date_cible,
                days_ahead,
                float(prediction.get("predicted_price", 0.0)),
                float(prediction.get("low_90", 0.0)),
                float(prediction.get("high_90", 0.0)),
                float(prediction.get("confidence", 0.0)),
                float(prediction["rmse"]) if prediction.get("rmse") is not None else None,
                str(prediction.get("model_used", "linear_regression")),
                int(bool(prediction.get("is_simulated", False))),
                int(prediction.get("nb_history_pts", 0)),
            ),
        )
        rowid = curseur.lastrowid
        conn.commit()

    logger.debug(
        f"Prévision sauvegardée pour {market}/{crop} "
        f"(target: {date_cible}, prix: {prediction.get('predicted_price')})."
    )
    return rowid


def recuperer_predictions(
    market: str,
    crop: str,
    max_age_jours: int = 1,
    db_path: Path = MARKET_DB_PATH,
) -> Optional[pd.DataFrame]:
    """
    Récupère les prévisions récentes depuis la table price_predictions.

    Utilisé pour éviter de recalculer une prévision déjà fraîche, et
    pour alimenter le backtesting (Phase 5).

    Args:
        market (str): Nom normalisé du marché.
        crop (str): Code de la culture.
        max_age_jours (int): Âge maximum en jours des prévisions à retourner.
            Défaut : 1 (prévisions du jour uniquement).
        db_path (Path): Chemin vers le fichier SQLite.

    Returns:
        pd.DataFrame: Prévisions récentes triées par date de génération décroissante.
        None: Si aucune prévision récente n'existe.
    """
    initialiser_base(db_path)

    # Calcul de la date minimale acceptable (UTC)
    date_limite = (
        datetime.now(timezone.utc) - timedelta(days=max_age_jours)
    ).isoformat()

    with _connexion(db_path) as conn:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM price_predictions
            WHERE market = ? AND crop = ?
              AND generated_at >= ?
            ORDER BY generated_at DESC
            """,
            conn,
            params=(market, crop, date_limite),
        )

    if df.empty:
        return None

    # Conversion du flag is_simulated en booléen Python
    df["is_simulated"] = df["is_simulated"].astype(bool)

    return df
