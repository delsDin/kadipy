"""
Module soilgrids.py

Client pour l'API SoilGrids v2.0 de l'ISRIC (International Soil Reference and
Information Centre). Récupère la classification WRB (World Reference Base for
Soil Resources) d'un point GPS et la traduit vers les types de sols utilisés
par le module kadi.weather.hydrology.

Documentation de l'API : https://rest.isric.org/soilgrids/v2.0/docs
Endpoint utilisé : GET /classification/query

La correspondance WRB -> type KadiPy est basée sur les sols dominants du Bénin,
décrits dans la nomenclature FAO/ISRIC pour l'Afrique de l'Ouest.

Stratégie en cascade :
    1. Cache JSON local (~/.kadi/soilgrids_cache.json) — évite les appels répétés.
    2. Appel API SoilGrids v2.0 avec retry et backoff exponentiel.
    3. Fallback statique sur "ferrugineux" si tout échoue (sol dominant du Bénin).
"""

import json
import logging
import math
import os
import time
from typing import Optional

import requests

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# URL de base de l'API SoilGrids v2.0 (ISRIC)
_SOILGRIDS_BASE_URL = "https://rest.isric.org/soilgrids/v2.0"

# Délai d'attente maximum pour une requête HTTP (secondes)
_TIMEOUT_SECONDES = 20

# Nombre de tentatives avant de tomber en mode fallback
_MAX_TENTATIVES = 3

# Délai de base pour le backoff exponentiel (secondes)
_BACKOFF_BASE_SEC = 2

# Distance maximale (en degrés) pour réutiliser un point du cache local.
# À 9° de latitude, 0.25° correspond à environ 25 km, ce qui est raisonnable
# pour la variabilité des sols au Bénin.
_CACHE_DISTANCE_SEUIL = 0.25

# Chemin du fichier de cache JSON local
_CACHE_FICHIER = os.path.expanduser("~/.kadi/soilgrids_cache.json")

# Sol par défaut en cas d'échec complet (sol ferrugineux tropical dominant au Bénin)
_SOL_DEFAUT = "ferrugineux"

# Table de correspondance des classes WRB (World Reference Base) vers
# les types de sols KadiPy utilisés dans kadi.weather.hydrology.
#
# Sources :
# - ISRIC SoilGrids (https://www.isric.org/explore/soilgrids)
# - FAO World Reference Base for Soil Resources, 2014
# - Données ORSTOM / IRD sur les sols du Bénin
#
# Logique de classification appliquée au Bénin :
# - Ferralsol / Oxisol -> 'ferrallitique' (sols très altérés, zone subéquatoriale)
# - Lixisol / Acrisol / Alisol -> 'ferrugineux' (sol ferrugineux tropical lessivé)
# - Arenosol / Regosol -> 'sableux' (dunes et sédiments côtiers ou sahéliens)
# - Luvisol / Cambisol / Vertisol -> 'limoneux' (sols de texture fine, couloirs fluviaux)
# - Gleysol / Fluvisol -> 'limoneux' (zones alluviales inondées)
# - Calcisol / Durisol / Gypsisol -> 'ferrugineux' (sols peu développés, Nord)
# - Autres -> 'ferrugineux' (valeur de repli, sol le plus fréquent au Bénin)
_WRB_VERS_SOL_KADIPY = {
    # Ferralsols : sols rouges très altérés du Sud-Bénin (zone cotonnière, Sud-Bénin)
    "Ferralsol": "ferrallitique",
    "Plinthosol": "ferrallitique",
    "Nitisol": "ferrallitique",

    # Lixisols et Acrisols : sols ferrugineux tropicaux lessivés (Centre et Nord-Bénin)
    "Lixisol": "ferrugineux",
    "Acrisol": "ferrugineux",
    "Alisol": "ferrugineux",

    # Luvisols et Cambisols : sols de texture limoneuse (couloirs fluviaux, plateaux)
    "Luvisol": "limoneux",
    "Cambisol": "limoneux",
    "Vertisol": "limoneux",

    # Gleysols et Fluvisols : alluvions et zones humides (plaine de l'Ouémé)
    "Gleysol": "limoneux",
    "Fluvisol": "limoneux",
    "Stagnosol": "limoneux",

    # Arenosols : sables côtiers et dunaires (littoral et zone soudano-sahélienne)
    "Arenosol": "sableux",
    "Regosol": "sableux",
    "Psammosol": "sableux",

    # Calcisols et Durisols : sols peu évolués du Nord (zone soudanienne)
    "Calcisol": "ferrugineux",
    "Durisol": "ferrugineux",
    "Gypsisol": "ferrugineux",

    # Autres classes peu représentées au Bénin
    "Kastanozem": "ferrugineux",
    "Phaeozem": "limoneux",
    "Chernozem": "limoneux",
    "Umbrisol": "ferrallitique",
    "Andosol": "ferrallitique",
    "Technosol": "ferrugineux",
    "Histosol": "limoneux",
    "Cryosol": "ferrugineux",
    "Solonetz": "limoneux",
    "Solonchak": "limoneux",
    "Leptosol": "ferrugineux",
    "Planosol": "limoneux",
    "Albeluvisol": "limoneux",
}


def _load_cache() -> list:
    """Charge le cache local SoilGrids depuis le fichier JSON.

    Returns:
        list: Liste de points {lat, lon, wrb_class, soil_type}, vide si introuvable.
    """
    # Retourne une liste vide si le fichier de cache n'existe pas
    if not os.path.exists(_CACHE_FICHIER):
        return []

    try:
        with open(_CACHE_FICHIER, "r", encoding="utf-8") as f:
            donnees = json.load(f)
        # Validation minimale : le cache doit être une liste
        return donnees if isinstance(donnees, list) else []
    except Exception as exc:
        logger.warning("Lecture du cache SoilGrids échouée : %s", exc)
        return []


def _save_cache(points: list) -> None:
    """Persiste la liste de points dans le fichier de cache JSON.

    Args:
        points (list): Liste de points à sauvegarder.
    """
    try:
        # Création du répertoire parent si nécessaire
        os.makedirs(os.path.dirname(_CACHE_FICHIER), exist_ok=True)
        with open(_CACHE_FICHIER, "w", encoding="utf-8") as f:
            json.dump(points, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Sauvegarde du cache SoilGrids échouée : %s", exc)


def _lookup_cache(lat: float, lon: float) -> Optional[str]:
    """Recherche le type de sol le plus proche dans le cache local.

    Utilise la distance euclidienne en degrés. Un point est considéré
    suffisamment proche si la distance est inférieure à _CACHE_DISTANCE_SEUIL.

    Args:
        lat (float): Latitude du point recherché.
        lon (float): Longitude du point recherché.

    Returns:
        str ou None: Type de sol KadiPy si un point proche est trouvé, sinon None.
    """
    points = _load_cache()

    if not points:
        return None

    # Recherche du point le plus proche
    point_proche = None
    dist_min = float("inf")

    for pt in points:
        # Calcul de la distance euclidienne en degrés (suffisant à cette échelle)
        dist = math.hypot(pt.get("lat", 0) - lat, pt.get("lon", 0) - lon)
        if dist < dist_min:
            dist_min = dist
            point_proche = pt

    # Vérification que le point trouvé est assez proche
    if point_proche and dist_min <= _CACHE_DISTANCE_SEUIL:
        soil_type = point_proche.get("soil_type", _SOL_DEFAUT)
        logger.debug(
            "Cache SoilGrids : type '%s' trouvé à %.4f° du point (%.4f, %.4f).",
            soil_type, dist_min, lat, lon,
        )
        return soil_type

    return None


def _wrb_to_soil(wrb_class: str) -> str:
    """Traduit une classe WRB en type de sol KadiPy.

    Tente d'abord une correspondance exacte, puis une correspondance par
    préfixe (les classes WRB contiennent parfois des qualificatifs,
    ex: "Haplic Lixisol" -> "Lixisol").

    Args:
        wrb_class (str): Classe WRB retournée par l'API SoilGrids.

    Returns:
        str: Type de sol KadiPy correspondant, ou 'ferrugineux' par défaut.
    """
    if not wrb_class:
        return _SOL_DEFAUT

    # Correspondance exacte
    if wrb_class in _WRB_VERS_SOL_KADIPY:
        return _WRB_VERS_SOL_KADIPY[wrb_class]

    # Correspondance par suffixe : "Haplic Lixisol" -> "Lixisol"
    for cle, sol_type in _WRB_VERS_SOL_KADIPY.items():
        if wrb_class.endswith(cle) or cle in wrb_class:
            return sol_type

    # Aucune correspondance : fallback sur le sol dominant béninois
    logger.info(
        "Classe WRB '%s' non reconnue dans la table de correspondance. "
        "Type de repli '%s' utilisé.",
        wrb_class, _SOL_DEFAUT,
    )
    return _SOL_DEFAUT


def _call_api(lat: float, lon: float) -> Optional[str]:
    """Appelle l'API SoilGrids v2.0 pour obtenir la classe WRB d'un point GPS.

    Effectue jusqu'à _MAX_TENTATIVES appels avec backoff exponentiel en cas
    d'erreur réseau ou de timeout.

    Args:
        lat (float): Latitude du point (entre -90 et 90).
        lon (float): Longitude du point (entre -180 et 180).

    Returns:
        str ou None: Classe WRB la plus probable, ou None si tous les appels échouent.
    """
    url = f"{_SOILGRIDS_BASE_URL}/classification/query"
    params = {"lon": lon, "lat": lat, "number_classes": 3}
    headers = {"User-Agent": "KadiPy/1.1.0 (Agritech Research, Benin; ISRIC SoilGrids)"}

    for tentative in range(1, _MAX_TENTATIVES + 1):
        try:
            reponse = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=_TIMEOUT_SECONDES,
            )
            reponse.raise_for_status()
            donnees = reponse.json()

            # Extraction de la classe WRB la plus probable depuis la réponse
            # Format attendu : {"properties": {"most_probable_wrb_class": "Lixisol", ...}}
            proprietes = donnees.get("properties", {})
            wrb_class = proprietes.get("most_probable_wrb_class", "")

            if wrb_class:
                logger.info(
                    "SoilGrids : classe WRB '%s' obtenue pour (lat=%.4f, lon=%.4f).",
                    wrb_class, lat, lon,
                )
                return wrb_class

            # Si la clé est absente, tenter dans la liste des probabilités
            probabilites = proprietes.get("probabilities", [])
            if probabilites:
                # La première entrée est la plus probable (liste triée par pourcentage)
                premiere = probabilites[0]
                wrb_class = premiere.get("wrb_class", "")
                if wrb_class:
                    logger.info(
                        "SoilGrids (fallback probabilités) : classe '%s' pour (%.4f, %.4f).",
                        wrb_class, lat, lon,
                    )
                    return wrb_class

            logger.warning(
                "SoilGrids : réponse valide mais classe WRB absente "
                "pour (lat=%.4f, lon=%.4f). Contenu : %s",
                lat, lon, str(donnees)[:200],
            )
            return None

        except requests.exceptions.Timeout:
            logger.warning(
                "SoilGrids tentative %d/%d : timeout (%.0fs) pour (%.4f, %.4f).",
                tentative, _MAX_TENTATIVES, _TIMEOUT_SECONDES, lat, lon,
            )
        except requests.exceptions.ConnectionError:
            logger.warning(
                "SoilGrids tentative %d/%d : erreur de connexion pour (%.4f, %.4f).",
                tentative, _MAX_TENTATIVES, lat, lon,
            )
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "SoilGrids tentative %d/%d : erreur HTTP %s pour (%.4f, %.4f).",
                tentative, _MAX_TENTATIVES, exc.response.status_code, lat, lon,
            )
        except Exception as exc:
            logger.warning(
                "SoilGrids tentative %d/%d : erreur inattendue pour (%.4f, %.4f) : %s.",
                tentative, _MAX_TENTATIVES, lat, lon, exc,
            )

        # Attente avec backoff exponentiel avant la prochaine tentative
        if tentative < _MAX_TENTATIVES:
            delai = _BACKOFF_BASE_SEC ** tentative
            logger.debug("SoilGrids : attente de %.0fs avant la prochaine tentative.", delai)
            time.sleep(delai)

    return None


def fetch_soil_type(
    lat: float,
    lon: float,
    default_soil: str = _SOL_DEFAUT,
) -> str:
    """Détermine le type de sol KadiPy pour un point GPS via SoilGrids v2.0.

    Implémente une stratégie en cascade :
    1. Recherche dans le cache local (~/.kadi/soilgrids_cache.json) : si un
       point géographiquement proche (< 25 km) est déjà connu, retourne son
       type directement sans appel réseau.
    2. Appel à l'API SoilGrids v2.0 (/classification/query) avec retry et
       backoff exponentiel. La classe WRB retournée est traduite vers la
       nomenclature KadiPy via la table _WRB_VERS_SOL_KADIPY.
    3. Fallback statique sur `default_soil` (par défaut 'ferrugineux', sol
       dominant du Bénin) si tous les appels API échouent.

    Types de sols KadiPy supportés (correspondance avec hydrology.py) :
        - 'ferrugineux'  : sol ferrugineux tropical lessivé (dominant, Centre/Nord)
        - 'ferrallitique': sol ferrallitique (zone subéquatoriale, Sud-Bénin)
        - 'sableux'      : sables côtiers et dunaires (littoral et Sahel)
        - 'limoneux'     : alluvions et couloirs fluviaux

    Args:
        lat (float): Latitude du point GPS (entre -90 et 90).
        lon (float): Longitude du point GPS (entre -180 et 180).
        default_soil (str): Type de sol de repli si SoilGrids est indisponible.
            Doit être l'une des quatre valeurs ci-dessus. Défaut : 'ferrugineux'.

    Returns:
        str: Type de sol KadiPy parmi 'ferrugineux', 'ferrallitique',
            'sableux' ou 'limoneux'.

    Examples:
        >>> fetch_soil_type(lat=9.33, lon=2.35)
        'ferrugineux'
        >>> fetch_soil_type(lat=6.36, lon=2.42)
        'ferrallitique'
    """
    # Validation silencieuse du type de sol par défaut
    types_valides = {"ferrugineux", "ferrallitique", "sableux", "limoneux"}
    if default_soil not in types_valides:
        logger.warning(
            "Type de sol par défaut '%s' non reconnu. Utilisation de '%s'.",
            default_soil, _SOL_DEFAUT,
        )
        default_soil = _SOL_DEFAUT

    # --- Étape 1 : vérification du cache local ---
    soil_depuis_cache = _lookup_cache(lat, lon)
    if soil_depuis_cache is not None:
        return soil_depuis_cache

    # --- Étape 2 : appel à l'API SoilGrids ---
    wrb_class = _call_api(lat, lon)

    if wrb_class is not None:
        # Traduction WRB -> type KadiPy
        soil_type = _wrb_to_soil(wrb_class)

        # Sauvegarde dans le cache pour les futurs appels
        points = _load_cache()
        points.append({
            "lat": lat,
            "lon": lon,
            "wrb_class": wrb_class,
            "soil_type": soil_type,
        })
        _save_cache(points)

        return soil_type

    # --- Étape 3 : fallback statique ---
    logger.warning(
        "SoilGrids indisponible pour (lat=%.4f, lon=%.4f). "
        "Type de sol de repli '%s' utilisé.",
        lat, lon, default_soil,
    )
    return default_soil


# Table des anciens noms -> (nouveau nom, classe cible)
_DEPRECATED = {
    "_charger_cache": ("_load_cache", _load_cache),
    "_sauvegarder_cache": ("_save_cache", _save_cache),
    "_chercher_dans_cache": ("_lookup_cache", _lookup_cache),
    "_traduire_classe_wrb": ("_wrb_to_soil", _wrb_to_soil),
    "_appeler_api_soilgrids": ("_call_api", _call_api),
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
