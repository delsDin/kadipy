"""
Connecteur pour CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data).

Ce module télécharge les rasters GeoTIFF journaliers depuis les serveurs du
Climate Hazards Center (CHC) de l'UC Santa Barbara, les découpe sur la zone
d'étude (Bénin), extrait la valeur de précipitation au point GPS demandé, et
met le raster découpé en cache local pour éviter les téléchargements redondants.

Source utilisée : africa_daily à la résolution de 0.05° (environ 5 km).
URL de base : https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_daily/tifs/p05

Délai de disponibilité : les données finales d'un mois M sont disponibles
vers le 15 du mois M+1 (exemple : juillet disponible le 15 août).
"""

import gzip
import io
import logging
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from kadi.config import CHIRPS_BASE_URL, CONFIG
from kadi.exceptions import SourceError

# Journaliseur dédié à ce module
logger = logging.getLogger(__name__)


def _is_available(day: date) -> bool:
    """
    Détermine si les données CHIRPS finales sont disponibles pour un jour donné.

    Les données CHIRPS finales d'un mois M sont publiées aux alentours du 15
    du mois M+1. Cette fonction calcule la date de disponibilité attendue pour
    le mois du jour demandé et la compare à la date d'aujourd'hui.

    :param day: Date pour laquelle on vérifie la disponibilité.
    :return: True si les données finales sont probablement publiées, False sinon.
    """
    # Récupération du délai configuré (en jours après la fin du mois)
    lag = CONFIG["weather"]["chirps"]["availability_lag_days_after_month_end"]

    # Calcul du premier jour du mois suivant celui du jour demandé
    if day.month == 12:
        # Cas du mois de décembre : le mois suivant est janvier de l'année suivante
        premier_mois_suivant = date(day.year + 1, 1, 1)
    else:
        premier_mois_suivant = date(day.year, day.month + 1, 1)

    # La date de disponibilité est le premier du mois suivant + le délai configuré
    date_disponible = premier_mois_suivant + timedelta(days=lag)

    return date.today() >= date_disponible


def _cache_path(day: date) -> Path:
    """
    Construit le chemin local du fichier GeoTIFF découpé pour un jour donné.

    Les rasters sont stockés dans le dossier de cache configuré, organisés par
    année : <raster_cache_dir>/<YYYY>/chirps-v2.0.YYYY.MM.DD.tif.

    :param day: Date du raster à localiser.
    :return: Chemin absolu vers le fichier GeoTIFF découpé.
    """
    cache_dir = Path(CONFIG["weather"]["chirps"]["raster_cache_dir"])
    # Sous-dossier par année pour limiter le nombre de fichiers par répertoire
    dossier_annee = cache_dir / str(day.year)
    nom_fichier = f"chirps-v2.0.{day.strftime('%Y.%m.%d')}.tif"
    return dossier_annee / nom_fichier


def _build_url(day: date) -> str:
    """
    Construit l'URL du fichier GeoTIFF compressé (.tif.gz) pour un jour donné.

    Convention de nommage CHIRPS africa_daily :
    <base_url>/<YYYY>/chirps-v2.0.YYYY.MM.DD.tif.gz

    :param day: Date du raster à télécharger.
    :return: URL complète vers le fichier .tif.gz sur les serveurs CHC.
    """
    nom_fichier = f"chirps-v2.0.{day.strftime('%Y.%m.%d')}.tif.gz"
    return f"{CHIRPS_BASE_URL}/{day.year}/{nom_fichier}"


def _download_and_clip(day: date, cache_path: Path) -> None:
    """
    Télécharge le raster CHIRPS compressé, le décompresse, le découpe sur la
    zone d'étude (bbox depuis config.py) et le sauvegarde en local.

    La bbox est lue depuis CONFIG["weather"]["gps_validation_bbox"] afin de
    rester synchronisée avec la validation GPS du reste du package.

    Le fichier partiellement téléchargé est supprimé en cas d'erreur pour
    éviter toute corruption du cache local.

    :param day: Date du raster à télécharger.
    :param cache_path: Chemin de destination du GeoTIFF découpé.
    :raises SourceError: Si le serveur est inaccessible ou si le fichier
        n'existe pas pour cette date sur le serveur CHC.
    """
    # Import conditionnel : rioxarray n'est requis que pour ce connecteur
    try:
        import rioxarray  # noqa: F401 (import utilisé via xarray accessor)
    except ImportError as exc:
        raise SourceError(
            "Le connecteur CHIRPS nécessite rioxarray et rasterio. "
            "Installez-les avec : pip install rioxarray rasterio"
        ) from exc

    # Lecture de la bbox depuis la configuration centrale (synchronisée avec GPS)
    bbox_cfg = CONFIG["weather"]["gps_validation_bbox"]
    min_lon = bbox_cfg["min_lon"]
    min_lat = bbox_cfg["min_lat"]
    max_lon = bbox_cfg["max_lon"]
    max_lat = bbox_cfg["max_lat"]

    url = _build_url(day)
    timeout = CONFIG["weather"]["chirps"]["http_timeout_sec"]

    logger.debug("Téléchargement CHIRPS : %s", url)

    # Création du dossier de cache si nécessaire
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Téléchargement du fichier .tif.gz en mémoire
        with urllib.request.urlopen(url, timeout=timeout) as reponse:
            contenu_gzippe = reponse.read()

    except urllib.error.HTTPError as exc:
        # Erreur 404 : la date demandée n'existe pas (jour hors plage CHIRPS)
        raise SourceError(
            f"Données CHIRPS introuvables pour le {day.isoformat()} "
            f"(HTTP {exc.code}). URL : {url}"
        ) from exc
    except OSError as exc:
        # Erreur réseau générique (timeout, DNS, etc.)
        raise SourceError(
            f"Impossible de joindre le serveur CHIRPS pour le {day.isoformat()}. "
            f"Vérifiez la connexion Internet. Détail : {exc}"
        ) from exc

    try:
        # Décompression du flux gzip en mémoire
        donnees_tif = gzip.decompress(contenu_gzippe)

        # Chargement du raster depuis le flux binaire
        import xarray as xr
        rds = xr.open_dataset(
            io.BytesIO(donnees_tif),
            engine="rasterio"
        )

        # Découpage sur la zone d'étude (bbox issue de config.py)
        # L'ordre des arguments pour clip_box est (min_x, min_y, max_x, max_y)
        rds_decoupe = rds.rio.clip_box(
            minx=min_lon,
            miny=min_lat,
            maxx=max_lon,
            maxy=max_lat
        )

        # Sauvegarde du GeoTIFF découpé en local
        rds_decoupe.rio.to_raster(str(cache_path))
        logger.debug("Raster CHIRPS sauvegardé : %s", cache_path)

    except Exception as exc:
        # Nettoyage du fichier partiel pour éviter la corruption du cache
        if cache_path.exists():
            cache_path.unlink()
            logger.warning("Fichier CHIRPS partiel supprimé : %s", cache_path)
        raise SourceError(
            f"Erreur lors du traitement du raster CHIRPS pour le {day.isoformat()} : {exc}"
        ) from exc


def _extract_point(raster_path: Path, lat: float, lon: float) -> float:
    """
    Extrait la valeur de précipitation au pixel le plus proche du point GPS demandé.

    :param raster_path: Chemin vers le fichier GeoTIFF local.
    :param lat: Latitude du point d'extraction.
    :param lon: Longitude du point d'extraction.
    :return: Valeur de précipitation en millimètres (float).
    :raises SourceError: Si la lecture du raster échoue.
    """
    try:
        import xarray as xr

        # Ouverture du raster avec chunking minimal pour l'extraction ponctuelle
        rds = xr.open_dataset(str(raster_path), engine="rasterio")

        # Sélection du pixel le plus proche du point GPS demandé
        # Les dimensions x et y correspondent à la longitude et à la latitude
        valeur = rds.isel(band=0).sel(x=lon, y=lat, method="nearest")

        # Extraction de la valeur numérique (variable unique dans le raster CHIRPS)
        nom_var = list(valeur.data_vars)[0]
        precip = float(valeur[nom_var].values)

        # CHIRPS utilise -9999.0 comme valeur manquante
        if precip < 0.0:
            precip = 0.0

        return precip

    except Exception as exc:
        raise SourceError(
            f"Impossible d'extraire la valeur ponctuelle depuis {raster_path} : {exc}"
        ) from exc


def fetch_historical_precipitation(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> Optional[pd.DataFrame]:
    """
    Récupère la série historique de précipitations CHIRPS pour un point GPS.

    Pour chaque date dans la plage [start_date, end_date], la fonction :
    1. Vérifie si les données finales CHIRPS sont disponibles (délai ~15 jours
       après la fin du mois).
    2. Cherche le raster GeoTIFF découpé dans le cache local.
    3. Si absent, télécharge le raster depuis les serveurs CHC, le découpe sur
       la zone d'étude et le sauvegarde localement.
    4. Extrait la valeur de précipitation au pixel le plus proche du point GPS.

    Si CHIRPS est indisponible pour une date (délai non écoulé ou erreur réseau),
    la date est ignorée avec un avertissement et un message de repli explicite.
    L'appelant (WeatherData) est chargé de compléter les données manquantes via
    Open-Meteo.

    :param lat: Latitude du lieu (en degrés décimaux).
    :param lon: Longitude du lieu (en degrés décimaux).
    :param start_date: Date de début de la plage (format ISO 'YYYY-MM-DD').
    :param end_date: Date de fin de la plage (format ISO 'YYYY-MM-DD').
    :return: DataFrame avec les colonnes 'date' (datetime64), 'precipitation'
        (float, mm), 'data_source' (str), 'confidence' (float). Retourne None
        si aucune date n'a pu être extraite.
    :raises ValueError: Si le format des dates est invalide.
    """
    # Conversion des chaînes en objets date Python
    try:
        debut = date.fromisoformat(start_date)
        fin = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError(
            f"Format de date invalide. Attendu 'YYYY-MM-DD'. Reçu : {start_date}, {end_date}"
        ) from exc

    if debut > fin:
        raise ValueError(
            f"La date de début ({start_date}) est postérieure à la date de fin ({end_date})."
        )

    resultats = []
    nb_ignorees_delai = 0
    nb_erreurs_reseau = 0

    # Itération sur chaque jour de la plage demandée
    jour_courant = debut
    while jour_courant <= fin:

        # Vérification du délai de disponibilité des données finales CHIRPS
        if not _is_available(jour_courant):
            nb_ignorees_delai += 1
            jour_courant += timedelta(days=1)
            continue

        chemin_cache = _cache_path(jour_courant)

        # Téléchargement uniquement si le raster n'est pas déjà en cache local
        if not chemin_cache.exists():
            try:
                _download_and_clip(jour_courant, chemin_cache)
            except SourceError as exc:
                # On enregistre l'erreur mais on continue sur les autres dates
                logger.warning(
                    "CHIRPS indisponible pour le %s (repli sur Open-Meteo prévu). "
                    "Détail : %s",
                    jour_courant.isoformat(),
                    exc,
                )
                nb_erreurs_reseau += 1
                jour_courant += timedelta(days=1)
                continue

        # Extraction de la valeur ponctuelle depuis le raster en cache
        try:
            precip = _extract_point(chemin_cache, lat, lon)
        except SourceError as exc:
            logger.warning(
                "Extraction CHIRPS impossible pour le %s : %s",
                jour_courant.isoformat(),
                exc,
            )
            jour_courant += timedelta(days=1)
            continue

        # Ajout de la ligne au résultat
        resultats.append({
            "date": pd.Timestamp(jour_courant),
            "precipitation": precip,
            "data_source": "chirps",
            "confidence": 1.0,
        })

        jour_courant += timedelta(days=1)

    # Message de repli global si une partie des dates a été ignorée
    if nb_ignorees_delai > 0:
        logger.info(
            "%d jour(s) ignorés car les données CHIRPS finales ne sont pas encore "
            "publiées (délai ~15 jours après la fin du mois). "
            "Ces dates seront complétées par Open-Meteo.",
            nb_ignorees_delai,
        )

    if nb_erreurs_reseau > 0:
        logger.warning(
            "%d jour(s) non récupérés en raison d'erreurs réseau ou serveur. "
            "Ces dates seront complétées par Open-Meteo si la source 'both' est utilisée.",
            nb_erreurs_reseau,
        )

    # Retour None si aucune date exploitable n'a été trouvée
    if not resultats:
        logger.warning(
            "Aucune donnée CHIRPS extraite pour la plage %s - %s "
            "(toutes les dates ignorées pour délai ou erreur réseau).",
            start_date,
            end_date,
        )
        return None

    # Construction et retour du DataFrame trié chronologiquement
    df = pd.DataFrame(resultats)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df


# Table des anciens noms -> (nouveau nom, classe cible)
_DEPRECATED = {
    "_chirps_disponible_pour": ("is_available", _is_available),
    "_chemin_raster_cache": ("_cache_path", _cache_path),
    "_construire_url": ("_build_url", _build_url),
    "_telecharger_et_decouper_raster": ("_download_and_clip", _download_and_clip),
    "_extraire_valeur_ponctuelle": ("_extract_point", _extract_point),
}


def __getattr__(name: str):
    """Intercepte les anciens noms importés depuis ce module.

    Args:
        name (str): Nom du symbole demandé dans ce module.

    Returns:
        type: La classe correspondante.

    Raises:
        AttributeError: Si le nom n'est pas un alias connu.
    """
    import warnings as _warnings
    if name in _DEPRECATED:
        new_name, cls = _DEPRECATED[name]
        _warnings.warn(
            f"kadi.kidas.cache.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return cls
    raise AttributeError(
        f"Le module 'kadi.kidas.cache' n'a pas d'attribut '{name}'."
    )
