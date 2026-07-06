# -*- coding: utf-8 -*-
"""
Module implémentant DataValidator pour la validation qualité des données agricoles.

Ce module fournit des outils de validation adaptés aux contextes AgriTech :
validation de schéma, vérification des types pandas, contrôle d'intervalles,
validation des coordonnées GPS avec bbox Bénin, et calcul d'un score
de qualité multicritère pour chaque jeu de données.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

# Import des exceptions personnalisées
from kadi.exceptions import KidasValidationError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Bounding box géographique du Bénin
_BENIN_LAT_MIN: float = 2.5
_BENIN_LAT_MAX: float = 12.5
_BENIN_LON_MIN: float = -1.5
_BENIN_LON_MAX: float = 4.0

# Correspondance types Python/SQL → types pandas attendus
_TYPE_MAP: Dict[str, type] = {
    "str": object,
    "string": object,
    "int": np.integer,
    "integer": np.integer,
    "float": np.floating,
    "datetime": np.datetime64,
    "bool": np.bool_,
}


class DataValidator:
    """Classe de validation qualité des données agricoles tabulaires.

    Fournit une suite de vérifications permettant de s'assurer que les
    données respectent un schéma, des types, des intervalles de valeurs
    et des contraintes géographiques propres au contexte béninois.

    Un score de qualité global est calculé à partir des dimensions de
    complétude, cohérence et précision.

    Attributs:
        df (pd.DataFrame): Le DataFrame à valider.
        _rapport (dict): Journal des résultats de validation.

    Exemple:
        >>> validator = DataValidator(df)
        >>> valide, erreurs = validator.validate_schema({
        ...     'culture': 'str',
        ...     'rendement_kg': 'float',
        ... })
        >>> score = validator.compute_quality_score()
        >>> print(score['overall'])
        0.87
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """Initialise le validateur avec le DataFrame à contrôler.

        Args:
            df (pd.DataFrame): Le DataFrame à valider.

        Raises:
            KidasValidationError: Si l'argument fourni n'est pas un DataFrame.
        """
        # Vérification du type d'entrée
        if not isinstance(df, pd.DataFrame):
            raise KidasValidationError(
                f"DataValidator attend un pandas DataFrame, "
                f"reçu : {type(df).__name__}."
            )

        # DataFrame de référence (sans copie : lecture seule)
        self.df: pd.DataFrame = df

        # Rapport de validation initialisé
        self._rapport: Dict = {
            "lignes": len(df),
            "colonnes": len(df.columns),
            "validations": [],
        }

    def validate_schema(
        self,
        schema: Dict[str, str],
    ) -> Tuple[bool, List[str]]:
        """Vérifie que le DataFrame possède les colonnes définies dans le schéma.

        Args:
            schema (dict[str, str]): Dictionnaire nom_colonne → type attendu.
                Les types acceptés sont : 'str', 'int', 'float', 'datetime', 'bool'.
                Exemple : {'culture': 'str', 'rendement_kg': 'float'}.

        Returns:
            tuple[bool, list[str]]: Tuple contenant :
                - True si le schéma est valide, False sinon.
                - Liste des messages d'erreur (vide si valide).
        """
        erreurs: List[str] = []

        for nom_col, type_attendu in schema.items():
            # Vérification de la présence de la colonne
            if nom_col not in self.df.columns:
                erreurs.append(
                    f"Colonne manquante : '{nom_col}' (type attendu : '{type_attendu}')."
                )
                continue

            # Vérification du type si spécifié et connu
            if type_attendu in _TYPE_MAP:
                type_pandas = _TYPE_MAP[type_attendu]
                est_correct = pd.api.types.is_dtype_equal(
                    self.df[nom_col].dtype,
                    type_pandas,
                ) or isinstance(self.df[nom_col].dtype.type, type_pandas) if hasattr(type_pandas, '__mro__') else False

                # Vérification simplifiée selon la catégorie de type
                if type_attendu in ("str", "string") and not pd.api.types.is_string_dtype(self.df[nom_col]):
                    if not pd.api.types.is_object_dtype(self.df[nom_col]):
                        erreurs.append(
                            f"Type incorrect pour '{nom_col}' : "
                            f"attendu '{type_attendu}', "
                            f"reçu '{self.df[nom_col].dtype}'."
                        )
                elif type_attendu in ("int", "integer") and not pd.api.types.is_integer_dtype(self.df[nom_col]):
                    erreurs.append(
                        f"Type incorrect pour '{nom_col}' : "
                        f"attendu '{type_attendu}', "
                        f"reçu '{self.df[nom_col].dtype}'."
                    )
                elif type_attendu == "float" and not pd.api.types.is_float_dtype(self.df[nom_col]):
                    erreurs.append(
                        f"Type incorrect pour '{nom_col}' : "
                        f"attendu '{type_attendu}', "
                        f"reçu '{self.df[nom_col].dtype}'."
                    )
                elif type_attendu == "datetime" and not pd.api.types.is_datetime64_any_dtype(self.df[nom_col]):
                    erreurs.append(
                        f"Type incorrect pour '{nom_col}' : "
                        f"attendu '{type_attendu}', "
                        f"reçu '{self.df[nom_col].dtype}'."
                    )

        est_valide = len(erreurs) == 0
        logger.info(
            "Validation schéma : %s (%d erreur(s)).",
            "OK" if est_valide else "ECHEC",
            len(erreurs),
        )

        # Enregistrement dans le rapport
        self._rapport["validations"].append(
            {
                "type": "schema",
                "valide": est_valide,
                "nb_erreurs": len(erreurs),
                "erreurs": erreurs,
            }
        )

        return est_valide, erreurs

    def validate_types(
        self,
        column_dtypes: Dict[str, str],
    ) -> Tuple[bool, pd.DataFrame]:
        """Vérifie la conformité des types pandas pour chaque colonne.

        Args:
            column_dtypes (dict[str, str]): Dictionnaire nom_colonne → type
                pandas attendu (ex: 'int64', 'float64', 'object', 'datetime64[ns]').

        Returns:
            tuple[bool, pd.DataFrame]: Tuple contenant :
                - True si tous les types correspondent.
                - DataFrame des colonnes avec des types incorrects (vide si OK).
        """
        lignes_erreurs = []

        for colonne, dtype_attendu in column_dtypes.items():
            if colonne not in self.df.columns:
                lignes_erreurs.append({
                    "colonne": colonne,
                    "dtype_attendu": dtype_attendu,
                    "dtype_reel": "ABSENT",
                })
                continue

            dtype_reel = str(self.df[colonne].dtype)

            # Comparaison des types (flexible pour les variantes d'int/float)
            types_compatibles = False
            if dtype_attendu in dtype_reel or dtype_reel in dtype_attendu:
                types_compatibles = True
            elif "int" in dtype_attendu and pd.api.types.is_integer_dtype(self.df[colonne]):
                types_compatibles = True
            elif "float" in dtype_attendu and pd.api.types.is_float_dtype(self.df[colonne]):
                types_compatibles = True

            if not types_compatibles:
                lignes_erreurs.append({
                    "colonne": colonne,
                    "dtype_attendu": dtype_attendu,
                    "dtype_reel": dtype_reel,
                })

        df_erreurs = pd.DataFrame(lignes_erreurs)
        est_valide = len(df_erreurs) == 0

        logger.info(
            "Validation types : %s (%d colonne(s) incorrecte(s)).",
            "OK" if est_valide else "ECHEC",
            len(df_erreurs),
        )

        self._rapport["validations"].append(
            {"type": "types", "valide": est_valide, "nb_erreurs": len(df_erreurs)}
        )

        return est_valide, df_erreurs

    def validate_ranges(
        self,
        column_bounds: Dict[str, Tuple[Any, Any]],
    ) -> Tuple[bool, pd.DataFrame]:
        """Vérifie que les valeurs numériques respectent des intervalles.

        Args:
            column_bounds (dict[str, tuple]): Dictionnaire nom_colonne →
                (valeur_min, valeur_max). Exemple :
                {'temperature': (-10, 50), 'rendement_kg': (0, 50000)}.

        Returns:
            tuple[bool, pd.DataFrame]: Tuple contenant :
                - True si toutes les valeurs respectent les bornes.
                - DataFrame des lignes hors-intervalle (vide si OK).
        """
        masque_erreurs = pd.Series(False, index=self.df.index)

        for colonne, (borne_min, borne_max) in column_bounds.items():
            if colonne not in self.df.columns:
                logger.warning(
                    "Colonne '%s' introuvable pour la validation d'intervalle.",
                    colonne,
                )
                continue

            # Détection des valeurs hors-intervalle
            hors_borne = (
                (self.df[colonne] < borne_min) | (self.df[colonne] > borne_max)
            ) & self.df[colonne].notna()

            masque_erreurs = masque_erreurs | hors_borne

            nb_hors_borne = hors_borne.sum()
            if nb_hors_borne > 0:
                logger.warning(
                    "%d valeur(s) hors intervalle [%.2f, %.2f] dans '%s'.",
                    nb_hors_borne,
                    borne_min,
                    borne_max,
                    colonne,
                )

        df_hors_borne = self.df[masque_erreurs].copy()
        est_valide = len(df_hors_borne) == 0

        self._rapport["validations"].append(
            {"type": "ranges", "valide": est_valide, "hors_borne": len(df_hors_borne)}
        )

        return est_valide, df_hors_borne

    def validate_coordinates(
        self,
        lat_col: str,
        lon_col: str,
        region: str = "benin",
    ) -> Tuple[bool, pd.DataFrame]:
        """Vérifie la cohérence géographique des coordonnées GPS.

        Vérifie que les valeurs de latitude et longitude sont dans la
        bounding box de la région spécifiée, et détecte les inversions
        lat/lon accidentelles.

        Args:
            lat_col (str): Nom de la colonne de latitude.
            lon_col (str): Nom de la colonne de longitude.
            region (str): Région de référence pour la bbox. 'benin' utilise
                lat∈[2.5, 12.5], lon∈[-1.5, 4.0]. Par défaut 'benin'.

        Returns:
            tuple[bool, pd.DataFrame]: Tuple contenant :
                - True si toutes les coordonnées sont valides.
                - DataFrame des lignes avec coordonnées invalides.

        Raises:
            KidasValidationError: Si les colonnes lat/lon sont absentes.
        """
        # Vérification de la présence des colonnes
        for colonne in (lat_col, lon_col):
            if colonne not in self.df.columns:
                raise KidasValidationError(
                    f"Colonne de coordonnées '{colonne}' introuvable dans le DataFrame."
                )

        # Définition des bornes selon la région
        if region == "benin":
            lat_min, lat_max = _BENIN_LAT_MIN, _BENIN_LAT_MAX
            lon_min, lon_max = _BENIN_LON_MIN, _BENIN_LON_MAX
        else:
            # Valeurs mondiales par défaut
            lat_min, lat_max = -90.0, 90.0
            lon_min, lon_max = -180.0, 180.0

        # Détection des coordonnées hors bbox
        hors_bbox = (
            (self.df[lat_col] < lat_min) |
            (self.df[lat_col] > lat_max) |
            (self.df[lon_col] < lon_min) |
            (self.df[lon_col] > lon_max)
        ) & self.df[lat_col].notna() & self.df[lon_col].notna()

        df_invalides = self.df[hors_bbox].copy()
        nb_invalides = len(df_invalides)

        if nb_invalides > 0:
            logger.warning(
                "%d coordonnée(s) hors bbox %s détectée(s). "
                "Vérifiez les inversions lat/lon éventuelles.",
                nb_invalides,
                region,
            )

        est_valide = nb_invalides == 0

        self._rapport["validations"].append(
            {
                "type": "coordinates",
                "region": region,
                "valide": est_valide,
                "coords_invalides": nb_invalides,
            }
        )

        return est_valide, df_invalides

    def validate_uniqueness(
        self,
        columns: List[str],
    ) -> Tuple[bool, pd.DataFrame]:
        """Vérifie l'unicité des valeurs sur les colonnes spécifiées.

        Args:
            columns (list[str]): Colonnes dont la combinaison doit être unique
                (équivalent d'une clé primaire composite).

        Returns:
            tuple[bool, pd.DataFrame]: Tuple contenant :
                - True si la combinaison est unique sur toutes les lignes.
                - DataFrame des lignes dupliquées (vide si OK).
        """
        # Détection des lignes dupliquées sur les colonnes spécifiées
        masque_doublons = self.df.duplicated(subset=columns, keep=False)
        df_doublons = self.df[masque_doublons].copy()

        est_valide = len(df_doublons) == 0

        logger.info(
            "Validation unicité sur %s : %s (%d doublon(s)).",
            columns,
            "OK" if est_valide else "ECHEC",
            len(df_doublons),
        )

        self._rapport["validations"].append(
            {"type": "uniqueness", "columns": columns, "valide": est_valide}
        )

        return est_valide, df_doublons

    def validate_referential_integrity(
        self,
        fk_col: str,
        reference_set: Set[Any],
    ) -> Tuple[bool, pd.DataFrame]:
        """Vérifie l'intégrité référentielle d'une clé étrangère.

        Args:
            fk_col (str): Nom de la colonne contenant la clé étrangère.
            reference_set (set): Ensemble des valeurs valides de référence
                (ex: ensemble des market_id existants).

        Returns:
            tuple[bool, pd.DataFrame]: Tuple contenant :
                - True si toutes les valeurs de clé existent dans la référence.
                - DataFrame des lignes avec des références manquantes.

        Raises:
            KidasValidationError: Si la colonne de clé est absente.
        """
        if fk_col not in self.df.columns:
            raise KidasValidationError(
                f"Colonne de clé étrangère '{fk_col}' introuvable."
            )

        # Détection des valeurs absentes de l'ensemble de référence
        masque_manquants = ~self.df[fk_col].isin(reference_set) & self.df[fk_col].notna()
        df_manquants = self.df[masque_manquants].copy()

        est_valide = len(df_manquants) == 0

        logger.info(
            "Validation intégrité référentielle '%s' : %s (%d réf. manquante(s)).",
            fk_col,
            "OK" if est_valide else "ECHEC",
            len(df_manquants),
        )

        self._rapport["validations"].append(
            {
                "type": "referential_integrity",
                "fk_col": fk_col,
                "valide": est_valide,
                "refs_manquantes": len(df_manquants),
            }
        )

        return est_valide, df_manquants

    def compute_quality_score(self) -> dict:
        """Calcule un score de qualité global et par dimension.

        Le score global est la moyenne pondérée de trois dimensions :
        - Complétude (40%) : proportion de valeurs non-null.
        - Cohérence (35%) : absence de doublons.
        - Précision (25%) : score personnalisé (1.0 si non calculé).

        Returns:
            dict: Dictionnaire contenant :
                - 'overall' (float) : score global ∈ [0.0, 1.0].
                - 'completeness' (float) : proportion de cellules non-null.
                - 'consistency' (float) : 1 - taux de doublons.
                - 'accuracy' (float) : 1.0 par défaut (extensible).
                - 'columns' (dict) : score de complétude par colonne.
        """
        nb_lignes, nb_colonnes = self.df.shape

        # Calcul de la complétude : proportion de cellules non-null
        if nb_lignes * nb_colonnes > 0:
            completude = float(
                1 - (self.df.isna().sum().sum() / (nb_lignes * nb_colonnes))
            )
        else:
            completude = 1.0

        # Calcul de la cohérence : absence de doublons
        nb_doublons = self.df.duplicated().sum()
        coherence = float(1 - (nb_doublons / nb_lignes)) if nb_lignes > 0 else 1.0

        # Précision : extensible, 1.0 par défaut
        precision = 1.0

        # Score global pondéré
        score_global = round(
            0.40 * completude + 0.35 * coherence + 0.25 * precision, 4
        )

        # Score de complétude par colonne
        scores_colonnes = {
            col: round(float(1 - self.df[col].isna().mean()), 4)
            for col in self.df.columns
        }

        score = {
            "overall": score_global,
            "completeness": round(completude, 4),
            "consistency": round(coherence, 4),
            "accuracy": round(precision, 4),
            "columns": scores_colonnes,
        }

        logger.info("Score qualité calculé : overall=%.2f", score_global)

        self._rapport["quality_score"] = score
        return score

    def get_validation_report(self) -> dict:
        """Retourne le rapport complet des validations effectuées.

        Returns:
            dict: Rapport structuré contenant l'ensemble des résultats
                de validation et le score de qualité (si calculé).
        """
        return self._rapport.copy()
