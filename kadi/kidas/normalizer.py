# -*- coding: utf-8 -*-
"""
Module implémentant DataNormalizer pour la normalisation des données agricoles.

Ce module fournit des outils de normalisation orientés AgriTech béninoise :
conversion snake_case des noms de colonnes, harmonisation des unités de mesure
agricoles (sacs, tonnes, tiya → kg), standardisation des noms de cultures
selon les codes FAO, géocodage des marchés, et création de géométries shapely.
"""

import logging
import re
import unicodedata
from typing import Dict, Optional

import pandas as pd

# Import des exceptions personnalisées
from kadi.exceptions import KidasCleaningError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# =============================================================================
# Dictionnaires de référence AgriTech Bénin
# =============================================================================

# Correspondance noms locaux de cultures → codes FAO standard
_CULTURE_ALIASES: Dict[str, str] = {
    # Maïs et variantes
    "maïs": "maize",
    "maiz": "maize",
    "mais": "maize",
    "corn": "maize",
    "maize": "maize",
    # Niébé (cowpea)
    "niébé": "cowpea",
    "niebe": "cowpea",
    "cowpea": "cowpea",
    "haricot": "cowpea",
    # Igname
    "igname": "yam",
    "yam": "yam",
    # Sorgho
    "sorgho": "sorghum",
    "sorghum": "sorghum",
    # Riz
    "riz": "rice",
    "rice": "rice",
    # Manioc
    "manioc": "cassava",
    "cassava": "cassava",
    # Arachide
    "arachide": "groundnut",
    "groundnut": "groundnut",
    "peanut": "groundnut",
    # Mil
    "mil": "millet",
    "millet": "millet",
    # Fonio
    "fonio": "fonio",
    # Soja
    "soja": "soybean",
    "soybean": "soybean",
    # Tomate
    "tomate": "tomato",
    "tomato": "tomato",
    # Oignon
    "oignon": "onion",
    "onion": "onion",
    # Piment
    "piment": "pepper",
    "pepper": "pepper",
}

# Correspondance marchés béninois → coordonnées GPS officielles
_MARCHE_COORDS: Dict[str, Dict] = {
    "dantokpa": {"lat": 6.366, "lon": 2.437, "ville": "Cotonou"},
    "cotonou": {"lat": 6.366, "lon": 2.437, "ville": "Cotonou"},
    "parakou": {"lat": 9.337, "lon": 2.629, "ville": "Parakou"},
    "bohicon": {"lat": 7.181, "lon": 2.067, "ville": "Bohicon"},
    "kandi": {"lat": 11.133, "lon": 2.940, "ville": "Kandi"},
    "natitingou": {"lat": 10.303, "lon": 1.381, "ville": "Natitingou"},
    "malanville": {"lat": 11.867, "lon": 3.383, "ville": "Malanville"},
    "abomey": {"lat": 7.183, "lon": 1.983, "ville": "Abomey"},
    "porto-novo": {"lat": 6.497, "lon": 2.627, "ville": "Porto-Novo"},
    "lokossa": {"lat": 6.617, "lon": 1.717, "ville": "Lokossa"},
}

# Facteurs de conversion vers le kilogramme (unité cible)
_FACTEURS_UNITE_KG: Dict[str, float] = {
    "kg": 1.0,
    "kilogramme": 1.0,
    "tonne": 1000.0,
    "tonnes": 1000.0,
    "t": 1000.0,
    "sac_100kg": 100.0,
    "sac_80kg": 80.0,
    "sac_50kg": 50.0,
    "sac": 100.0,  # sac standard au Bénin = 100 kg
    "tiya": 1.5,   # mesure locale Bénin ≈ 1.5 kg selon la culture
    "boisseau": 27.2,  # boisseau américain pour compatibilité FAO
    "quintal": 100.0,
    "livre": 0.4536,
    "g": 0.001,
    "gramme": 0.001,
}


class DataNormalizer:
    """Classe de normalisation des données agricoles pour le contexte béninois.

    Fournit des méthodes de transformation pour uniformiser les conventions
    de dénomination, les unités de mesure, les devises, les noms de cultures
    et de marchés, et pour créer des géométries GPS.

    Toutes les opérations sont tracées dans un mapping interne récupérable
    via get_normalization_mapping().

    Attributs:
        df (pd.DataFrame): Le DataFrame en cours de normalisation.
        _mappings (dict): Historique des transformations appliquées.

    Exemple:
        >>> normalizer = DataNormalizer(df)
        >>> df_norm = (
        ...     normalizer
        ...     .normalize_column_names()
        ...     .normalize_crop_names(col='culture')
        ...     .normalize_units(unit_map={'production': 'tonne'})
        ... )
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """Initialise le normaliseur avec le DataFrame à transformer.

        Args:
            df (pd.DataFrame): Le DataFrame source à normaliser. Une copie
                interne est créée pour préserver l'original.

        Raises:
            KidasCleaningError: Si l'argument fourni n'est pas un DataFrame.
        """
        # Vérification du type d'entrée
        if not isinstance(df, pd.DataFrame):
            raise KidasCleaningError(
                f"DataNormalizer attend un pandas DataFrame, "
                f"reçu : {type(df).__name__}."
            )

        # Copie de travail du DataFrame
        self.df: pd.DataFrame = df.copy()

        # Historique des mappings de normalisation appliqués
        self._mappings: Dict = {
            "colonnes": {},
            "unites": {},
            "cultures": {},
            "marches": {},
            "devises": {},
        }

    @staticmethod
    def _vers_snake_case(texte: str) -> str:
        """Convertit une chaîne de caractères en snake_case.

        Supprime les accents, remplace les espaces et tirets par des
        underscores, et convertit en minuscules.

        Args:
            texte (str): La chaîne à convertir.

        Returns:
            str: La chaîne en snake_case, sans accents ni caractères spéciaux.
        """
        # Suppression des accents via NFD + encodage ASCII
        sans_accent = (
            unicodedata.normalize("NFD", texte)
            .encode("ascii", "ignore")
            .decode("utf-8")
        )

        # Remplacement des espaces, tirets et parenthèses par des underscores
        snake = re.sub(r"[\s\-\(\)/]+", "_", sans_accent)

        # Suppression des caractères non alphanumériques restants
        snake = re.sub(r"[^a-zA-Z0-9_]", "", snake)

        # Conversion en minuscules et nettoyage des underscores multiples
        snake = re.sub(r"_+", "_", snake).lower().strip("_")

        return snake

    def normalize_column_names(
        self,
        style: str = "snake_case",
    ) -> pd.DataFrame:
        """Normalise les noms de colonnes du DataFrame.

        Convertit les noms de colonnes en snake_case en supprimant les
        accents, les espaces et les caractères spéciaux.
        Exemple : 'Température Min (°C)' → 'temperature_min_c'.

        Args:
            style (str): Style de nommage cible. Seul 'snake_case' est
                supporté actuellement. Par défaut 'snake_case'.

        Returns:
            pd.DataFrame: DataFrame avec les noms de colonnes normalisés.
        """
        if style != "snake_case":
            logger.warning(
                "Style '%s' non supporté. Utilisation de 'snake_case'.", style
            )

        # Construction du mapping ancien_nom → nouveau_nom
        mapping_colonnes = {
            col: self._vers_snake_case(col)
            for col in self.df.columns
        }

        # Application du renommage
        self.df = self.df.rename(columns=mapping_colonnes)

        # Journalisation des transformations
        changements = {
            ancien: nouveau
            for ancien, nouveau in mapping_colonnes.items()
            if ancien != nouveau
        }

        logger.info(
            "Normalisation noms de colonnes : %d colonne(s) renommée(s).",
            len(changements),
        )

        # Mise à jour du mapping de traçabilité
        self._mappings["colonnes"].update(mapping_colonnes)

        return self.df

    def normalize_units(
        self,
        unit_map: Dict[str, str],
    ) -> pd.DataFrame:
        """Convertit les valeurs de colonnes numériques vers le kilogramme.

        Applique les facteurs de conversion définis dans le dictionnaire
        de référence _FACTEURS_UNITE_KG pour chaque colonne spécifiée.

        Args:
            unit_map (dict[str, str]): Dictionnaire nom_colonne → unité_source.
                Exemple : {'production': 'tonne', 'recolte': 'sac_100kg'}.

        Returns:
            pd.DataFrame: DataFrame avec les valeurs converties en kg.

        Raises:
            KidasCleaningError: Si une unité source est inconnue.
        """
        for colonne, unite_source in unit_map.items():
            if colonne not in self.df.columns:
                logger.warning(
                    "Colonne '%s' introuvable pour la normalisation d'unités.",
                    colonne,
                )
                continue

            # Normalisation du nom d'unité (minuscules, sans espaces)
            unite_normalisee = unite_source.lower().strip()

            if unite_normalisee not in _FACTEURS_UNITE_KG:
                raise KidasCleaningError(
                    f"Unité '{unite_source}' inconnue. Unités supportées : "
                    f"{list(_FACTEURS_UNITE_KG.keys())}."
                )

            # Application du facteur de conversion
            facteur = _FACTEURS_UNITE_KG[unite_normalisee]
            self.df[colonne] = self.df[colonne] * facteur

            logger.debug(
                "Colonne '%s' convertie : %s × %.4f → kg.",
                colonne,
                unite_source,
                facteur,
            )

            # Traçabilité de la conversion
            self._mappings["unites"][colonne] = {
                "unite_source": unite_source,
                "facteur_kg": facteur,
                "unite_cible": "kg",
            }

        return self.df

    def normalize_currencies(
        self,
        col: str,
        from_currency: str = "XOF",
        to_currency: str = "XOF",
        exchange_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Convertit les valeurs monétaires d'une colonne.

        Note : Dans sa version actuelle, cette méthode applique un taux
        de change fixe. Une intégration avec une API de change peut être
        ajoutée en Phase 2 du module.

        Args:
            col (str): Nom de la colonne à convertir.
            from_currency (str): Devise source (ex: 'USD', 'XOF', 'EUR').
                Par défaut 'XOF'.
            to_currency (str): Devise cible. Par défaut 'XOF'.
            exchange_date (str | None): Date de référence pour le taux
                de change (format 'YYYY-MM-DD'). None pour le taux actuel.

        Returns:
            pd.DataFrame: DataFrame avec la colonne convertie.
        """
        if col not in self.df.columns:
            logger.warning(
                "Colonne '%s' introuvable pour la conversion de devises.", col
            )
            return self.df

        # Taux de change fixes de référence (vers XOF)
        taux_vers_xof: Dict[str, float] = {
            "XOF": 1.0,
            "EUR": 655.957,   # Taux fixe XOF/EUR (UMOA)
            "USD": 600.0,     # Taux approximatif
            "GBP": 750.0,     # Taux approximatif
        }

        if from_currency not in taux_vers_xof or to_currency not in taux_vers_xof:
            logger.warning(
                "Paire de devises %s/%s non disponible. Aucune conversion.",
                from_currency,
                to_currency,
            )
            return self.df

        # Calcul du taux de conversion croisé
        taux_conversion = taux_vers_xof[from_currency] / taux_vers_xof[to_currency]

        # Application de la conversion
        self.df[col] = self.df[col] * taux_conversion

        logger.info(
            "Colonne '%s' convertie de %s vers %s (taux: %.4f).",
            col,
            from_currency,
            to_currency,
            taux_conversion,
        )

        # Traçabilité de la conversion
        self._mappings["devises"][col] = {
            "from": from_currency,
            "to": to_currency,
            "taux": taux_conversion,
        }

        return self.df

    def normalize_crop_names(
        self,
        col: str,
        target_standard: str = "fao",
    ) -> pd.DataFrame:
        """Normalise les noms de cultures vers un standard international.

        Utilise le dictionnaire de référence _CULTURE_ALIASES pour mapper
        les noms locaux béninois (avec ou sans accents) vers les codes FAO.

        Args:
            col (str): Nom de la colonne contenant les noms de cultures.
            target_standard (str): Standard cible. 'fao' utilise les codes
                officiels FAO (ex: 'maize', 'cowpea'). Par défaut 'fao'.

        Returns:
            pd.DataFrame: DataFrame avec la colonne de cultures normalisée.
        """
        if col not in self.df.columns:
            logger.warning(
                "Colonne '%s' introuvable pour la normalisation des cultures.", col
            )
            return self.df

        def _normaliser_culture(valeur: str) -> str:
            """Normalise un nom de culture individuel.

            Args:
                valeur (str): Le nom de culture brut.

            Returns:
                str: Le code FAO correspondant ou la valeur originale en minuscules.
            """
            if not isinstance(valeur, str):
                return valeur

            # Normalisation : minuscules et suppression des accents
            valeur_norm = (
                unicodedata.normalize("NFD", valeur.lower().strip())
                .encode("ascii", "ignore")
                .decode("utf-8")
            )

            # Recherche dans le dictionnaire de référence
            return _CULTURE_ALIASES.get(valeur_norm, valeur_norm)

        # Application du mapping sur toute la colonne
        avant = self.df[col].copy()
        self.df[col] = self.df[col].apply(_normaliser_culture)

        # Calcul des correspondances trouvées
        mapping_applique = {
            ancien: nouveau
            for ancien, nouveau in zip(avant, self.df[col])
            if ancien != nouveau
        }

        logger.info(
            "%d nom(s) de culture normalisé(s) vers standard '%s'.",
            len(mapping_applique),
            target_standard,
        )

        self._mappings["cultures"].update(mapping_applique)

        return self.df

    def normalize_market_names(
        self,
        col: str,
        region: str = "benin",
    ) -> pd.DataFrame:
        """Normalise les noms de marchés et assigne les coordonnées GPS.

        Mappe les noms de marchés béninois vers leur forme officielle
        et ajoute les colonnes 'market_lat' et 'market_lon' correspondantes.

        Args:
            col (str): Nom de la colonne contenant les noms de marchés.
            region (str): Région de référence pour le dictionnaire de marchés.
                Par défaut 'benin'.

        Returns:
            pd.DataFrame: DataFrame avec les noms de marchés normalisés
                et les colonnes 'market_lat' / 'market_lon' ajoutées.
        """
        if col not in self.df.columns:
            logger.warning(
                "Colonne '%s' introuvable pour la normalisation des marchés.", col
            )
            return self.df

        lats, lons = [], []

        for valeur in self.df[col]:
            if not isinstance(valeur, str):
                lats.append(None)
                lons.append(None)
                continue

            # Normalisation du nom de marché (minuscules, sans accents)
            nom_norm = (
                unicodedata.normalize("NFD", valeur.lower().strip())
                .encode("ascii", "ignore")
                .decode("utf-8")
            )

            # Recherche du marché dans la référence (correspondance partielle)
            coords_trouvees = None
            for cle_marche, coords in _MARCHE_COORDS.items():
                if cle_marche in nom_norm or nom_norm in cle_marche:
                    coords_trouvees = coords
                    break

            if coords_trouvees:
                lats.append(coords_trouvees["lat"])
                lons.append(coords_trouvees["lon"])
            else:
                lats.append(None)
                lons.append(None)

        # Ajout des colonnes de coordonnées au DataFrame
        self.df["market_lat"] = lats
        self.df["market_lon"] = lons

        nb_geolocalises = sum(1 for lat in lats if lat is not None)
        logger.info(
            "%d/%d marché(s) géolocalisé(s) dans '%s'.",
            nb_geolocalises,
            len(self.df),
            col,
        )

        return self.df

    def normalize_geometry(
        self,
        lat_col: str,
        lon_col: str,
    ) -> pd.DataFrame:
        """Crée une colonne 'geometry' contenant des points GPS shapely.

        Args:
            lat_col (str): Nom de la colonne de latitude.
            lon_col (str): Nom de la colonne de longitude.

        Returns:
            pd.DataFrame: DataFrame avec la colonne 'geometry' ajoutée.
                Les lignes avec lat ou lon manquante ont geometry = None.
        """
        try:
            # Import conditionnel de shapely (dépendance optionnelle)
            from shapely.geometry import Point
        except ImportError:
            logger.warning(
                "Le package 'shapely' n'est pas installé. "
                "Installez-le avec : pip install shapely>=2.0"
            )
            return self.df

        if lat_col not in self.df.columns or lon_col not in self.df.columns:
            logger.warning(
                "Colonnes '%s' ou '%s' introuvables pour la création de géométrie.",
                lat_col,
                lon_col,
            )
            return self.df

        # Création de la colonne 'geometry' avec des points shapely
        self.df["geometry"] = self.df.apply(
            lambda ligne: Point(ligne[lon_col], ligne[lat_col])
            if pd.notna(ligne[lat_col]) and pd.notna(ligne[lon_col])
            else None,
            axis=1,
        )

        nb_points = self.df["geometry"].notna().sum()
        logger.info(
            "%d point(s) géométrique(s) créé(s) depuis '%s'/'%s'.",
            nb_points,
            lat_col,
            lon_col,
        )

        return self.df

    def get_normalization_mapping(self) -> dict:
        """Retourne l'historique complet des normalisations appliquées.

        Returns:
            dict: Dictionnaire structuré par type de normalisation :
                - 'colonnes' (dict) : ancien → nouveau nom de colonne.
                - 'unites' (dict) : colonne → {unite_source, facteur_kg, unite_cible}.
                - 'cultures' (dict) : nom_local → code_fao.
                - 'marches' (dict) : nom_local → coordonnées.
                - 'devises' (dict) : colonne → {from, to, taux}.
        """
        return self._mappings.copy()
