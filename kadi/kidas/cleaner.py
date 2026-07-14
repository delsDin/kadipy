# -*- coding: utf-8 -*-
"""
Module implémentant DataCleaner pour le nettoyage des données agricoles.

Ce module fournit des outils de nettoyage robustes adaptés aux données
rencontrées en AgriTech béninoise : doublons exacts, valeurs manquantes
avec plusieurs stratégies d'imputation, détection statistique d'outliers,
normalisation de dates hétérogènes et standardisation du texte.
"""

import logging
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# Import des exceptions personnalisées
from kadi.exceptions import KidasCleaningError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Stratégies supportées pour le traitement des valeurs manquantes
_STRATEGIES_MISSING = {"mean", "median", "forward_fill", "drop"}

# Méthodes supportées pour la détection des outliers
_METHODES_OUTLIERS = {"iqr", "zscore", "mad"}


class DataCleaner:
    """Classe de nettoyage des données agricoles tabulaires.

    Fournit une suite complète de méthodes pour détecter et corriger
    les anomalies courantes dans les fichiers agricoles : doublons,
    valeurs manquantes, outliers statistiques, dates incohérentes
    et texte non normalisé.

    Chaque méthode de nettoyage met à jour le rapport interne (_report)
    et retourne le DataFrame modifié. Cela permet un usage enchaîné.

    Attributs:
        df (pd.DataFrame): Le DataFrame en cours de nettoyage.
        _rapport (dict): Journal des opérations de nettoyage effectuées.

    Exemple:
        >>> cleaner = DataCleaner(df)
        >>> df_propre = (
        ...     cleaner
        ...     .remove_duplicates()
        ...     .handle_missing_values(strategy='mean')
        ...     .fix_dates(columns=['date_recolte'])
        ... )
        >>> print(cleaner.get_cleaning_report())
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """Initialise le nettoyeur avec le DataFrame à traiter.

        Args:
            df (pd.DataFrame): Le DataFrame source à nettoyer. Une copie
                interne est créée pour ne pas modifier l'original.

        Raises:
            KidasCleaningError: Si l'argument fourni n'est pas un DataFrame.
        """
        # Vérification du type d'entrée
        if not isinstance(df, pd.DataFrame):
            raise KidasCleaningError(
                f"DataCleaner attend un pandas DataFrame, "
                f"reçu : {type(df).__name__}."
            )

        # Copie de travail du DataFrame (préservation de l'original)
        self.df: pd.DataFrame = df.copy()

        # Rapport d'opérations initialisé à zéro
        self._rapport: Dict = {
            "doublons_supprimes": 0,
            "nan_traites": 0,
            "outliers_detectes": 0,
            "dates_corrigees": 0,
            "lignes_initiales": len(df),
            "colonnes_initiales": len(df.columns),
            "operations": [],
        }

    def remove_duplicates(
        self,
        subset: Optional[List[str]] = None,
        keep: str = "first",
    ) -> pd.DataFrame:
        """Supprime les lignes dupliquées du DataFrame.

        Args:
            subset (list[str] | None): Liste des colonnes à considérer pour
                la détection des doublons. None pour toutes les colonnes.
                Par défaut None.
            keep (str): Stratégie de conservation : 'first' pour garder
                la première occurrence, 'last' pour la dernière, False pour
                supprimer toutes les occurrences. Par défaut 'first'.

        Returns:
            pd.DataFrame: DataFrame sans doublons.
        """
        # Comptage des doublons avant suppression
        nb_doublons = self.df.duplicated(subset=subset).sum()

        if nb_doublons > 0:
            # Suppression des doublons
            self.df = self.df.drop_duplicates(subset=subset, keep=keep)
            logger.info(
                "%d doublon(s) supprimé(s) (subset=%s, keep='%s').",
                nb_doublons,
                subset,
                keep,
            )
        else:
            logger.debug("Aucun doublon détecté.")

        # Mise à jour du rapport
        self._rapport["doublons_supprimes"] += nb_doublons
        self._rapport["operations"].append(
            {"operation": "remove_duplicates", "doublons_supprimes": nb_doublons}
        )

        return self.df

    def handle_missing_values(
        self,
        strategy: str = "mean",
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Traite les valeurs manquantes (NaN) selon une stratégie donnée.

        Args:
            strategy (str): Stratégie d'imputation parmi :
                - 'mean' : remplace les NaN par la moyenne de la colonne.
                - 'median' : remplace par la médiane.
                - 'forward_fill' : propage la dernière valeur connue.
                - 'drop' : supprime les lignes contenant des NaN.
                Par défaut 'mean'.
            columns (list[str] | None): Colonnes cibles. None pour
                toutes les colonnes. Par défaut None.

        Returns:
            pd.DataFrame: DataFrame avec les valeurs manquantes traitées.

        Raises:
            KidasCleaningError: Si la stratégie fournie est invalide.
        """
        # Validation de la stratégie
        if strategy not in _STRATEGIES_MISSING:
            raise KidasCleaningError(
                f"Stratégie '{strategy}' invalide. Valeurs acceptées : "
                f"{_STRATEGIES_MISSING}."
            )

        # Sélection des colonnes cibles
        colonnes_cibles = columns if columns else list(self.df.columns)

        # Comptage des NaN avant traitement
        nb_nan_avant = self.df[colonnes_cibles].isna().sum().sum()

        if strategy == "drop":
            # Suppression des lignes contenant des NaN dans les colonnes cibles
            self.df = self.df.dropna(subset=colonnes_cibles)

        elif strategy == "forward_fill":
            # Propagation de la dernière valeur connue (bfill en backup)
            self.df[colonnes_cibles] = (
                self.df[colonnes_cibles].ffill().bfill()
            )

        elif strategy in ("mean", "median"):
            # Imputation par la moyenne ou médiane pour les colonnes numériques
            for colonne in colonnes_cibles:
                if pd.api.types.is_numeric_dtype(self.df[colonne]):
                    if strategy == "mean":
                        valeur_imputation = self.df[colonne].mean()
                    else:
                        valeur_imputation = self.df[colonne].median()

                    # Remplacement des NaN par la valeur calculée
                    self.df[colonne] = self.df[colonne].fillna(valeur_imputation)

        # Comptage des NaN traités
        nb_nan_apres = self.df[colonnes_cibles].isna().sum().sum()
        nb_nan_traites = int(nb_nan_avant - nb_nan_apres)

        logger.info(
            "%d valeur(s) manquante(s) traitée(s) avec la stratégie '%s'.",
            nb_nan_traites,
            strategy,
        )

        # Mise à jour du rapport
        self._rapport["nan_traites"] += nb_nan_traites
        self._rapport["operations"].append(
            {
                "operation": "handle_missing_values",
                "strategy": strategy,
                "nan_traites": nb_nan_traites,
            }
        )

        return self.df

    def remove_outliers(
        self,
        method: str = "iqr",
        threshold: float = 1.5,
        columns: Optional[List[str]] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Détecte et supprime les outliers statistiques du DataFrame.

        Args:
            method (str): Méthode de détection parmi :
                - 'iqr' : règle des 1.5 × IQR (interquartile range).
                - 'zscore' : seuil sur le Z-score standardisé.
                - 'mad' : Median Absolute Deviation, robuste aux outliers.
                Par défaut 'iqr'.
            threshold (float): Seuil de détection. Pour 'iqr' : 1.5 standard.
                Pour 'zscore' : 3.0 recommandé. Par défaut 1.5.
            columns (list[str] | None): Colonnes numériques à analyser.
                None pour toutes les colonnes numériques. Par défaut None.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]: Tuple contenant :
                - Le DataFrame sans outliers.
                - Le DataFrame des lignes identifiées comme outliers.

        Raises:
            KidasCleaningError: Si la méthode fournie est invalide.
        """
        # Validation de la méthode
        if method not in _METHODES_OUTLIERS:
            raise KidasCleaningError(
                f"Méthode '{method}' invalide. Valeurs acceptées : "
                f"{_METHODES_OUTLIERS}."
            )

        # Sélection des colonnes numériques cibles
        if columns:
            cols_num = [c for c in columns if pd.api.types.is_numeric_dtype(self.df[c])]
        else:
            cols_num = list(self.df.select_dtypes(include=[np.number]).columns)

        if not cols_num:
            logger.debug("Aucune colonne numérique disponible pour la détection d'outliers.")
            return self.df, pd.DataFrame()

        # Masque booléen : True = ligne normale, False = outlier
        masque_normal = pd.Series(True, index=self.df.index)

        for colonne in cols_num:
            serie = self.df[colonne].dropna()

            if method == "iqr":
                # Règle de Tukey : Q1 - 1.5*IQR ≤ x ≤ Q3 + 1.5*IQR
                q1 = serie.quantile(0.25)
                q3 = serie.quantile(0.75)
                iqr = q3 - q1
                borne_basse = q1 - threshold * iqr
                borne_haute = q3 + threshold * iqr
                masque_col = self.df[colonne].between(borne_basse, borne_haute)

            elif method == "zscore":
                # Z-score standardisé : |z| ≤ threshold
                z_scores = np.abs(stats.zscore(serie))
                # Alignement avec l'index original (NaN pour les valeurs manquantes)
                z_alignes = self.df[colonne].copy().astype(float)
                z_alignes.loc[serie.index] = z_scores
                masque_col = z_alignes <= threshold

            elif method == "mad":
                # MAD : valeur robuste, moins sensible aux outliers extrêmes
                mediane = serie.median()
                mad = np.median(np.abs(serie - mediane))
                # Facteur de cohérence pour distribution normale
                mad_facteur = mad * 1.4826
                if mad_facteur > 0:
                    z_mad = np.abs(self.df[colonne] - mediane) / mad_facteur
                    masque_col = z_mad <= threshold
                else:
                    masque_col = pd.Series(True, index=self.df.index)

            # Remplacement des NaN par True (les lignes sans valeur ne sont pas des outliers)
            masque_col = masque_col.fillna(True)
            masque_normal = masque_normal & masque_col

        # Séparation des outliers et des données normales
        df_outliers = self.df[~masque_normal].copy()
        self.df = self.df[masque_normal].copy()

        nb_outliers = len(df_outliers)
        logger.info(
            "%d outlier(s) détecté(s) et supprimé(s) (method='%s', threshold=%.2f).",
            nb_outliers,
            method,
            threshold,
        )

        # Mise à jour du rapport
        self._rapport["outliers_detectes"] += nb_outliers
        self._rapport["operations"].append(
            {
                "operation": "remove_outliers",
                "method": method,
                "threshold": threshold,
                "outliers_supprimes": nb_outliers,
            }
        )

        return self.df, df_outliers

    def fix_dates(
        self,
        columns: List[str],
        infer_format: bool = True,
    ) -> pd.DataFrame:
        """Normalise les formats de dates hétérogènes dans les colonnes spécifiées.

        Tente de parser les dates avec pd.to_datetime(), en inférant le format
        si possible. Les valeurs non parsables sont laissées comme NaT.

        Args:
            columns (list[str]): Liste des colonnes contenant des dates
                à normaliser.
            infer_format (bool): Si True, infère automatiquement le format
                de date. Par défaut True.

        Returns:
            pd.DataFrame: DataFrame avec les colonnes de dates normalisées
                en datetime64.
        """
        nb_dates_corrigees = 0

        for colonne in columns:
            if colonne not in self.df.columns:
                logger.warning(
                    "Colonne '%s' introuvable dans le DataFrame.", colonne
                )
                continue

            # Comptage des valeurs non-null avant conversion
            nb_avant = self.df[colonne].notna().sum()

            try:
                # Conversion en datetime avec gestion des formats mixtes (pandas 2.x+)
                self.df[colonne] = pd.to_datetime(
                    self.df[colonne],
                    format="mixed",
                    dayfirst=False,
                    errors="coerce",
                )

                # Comptage des conversions réussies
                nb_apres = self.df[colonne].notna().sum()
                nb_corrigees = int(nb_avant - (nb_avant - nb_apres))
                nb_dates_corrigees += nb_avant

                logger.debug(
                    "Colonne '%s' convertie en datetime (%d/%d valeurs parsées).",
                    colonne,
                    nb_apres,
                    nb_avant,
                )

            except Exception as erreur:
                logger.warning(
                    "Impossible de convertir la colonne '%s' en datetime : %s",
                    colonne,
                    erreur,
                )

        # Mise à jour du rapport
        self._rapport["dates_corrigees"] += nb_dates_corrigees
        self._rapport["operations"].append(
            {
                "operation": "fix_dates",
                "columns": columns,
                "dates_corrigees": nb_dates_corrigees,
            }
        )

        return self.df

    def standardize_text(
        self,
        columns: List[str],
        case: str = "lower",
    ) -> pd.DataFrame:
        """Standardise le texte des colonnes : trim, casse, suppression d'accents.

        Args:
            columns (list[str]): Colonnes texte à standardiser.
            case (str): Casse à appliquer : 'lower', 'upper' ou 'title'.
                Par défaut 'lower'.

        Returns:
            pd.DataFrame: DataFrame avec les colonnes texte standardisées.
        """
        for colonne in columns:
            if colonne not in self.df.columns:
                logger.warning(
                    "Colonne '%s' introuvable dans le DataFrame.", colonne
                )
                continue

            if not pd.api.types.is_string_dtype(self.df[colonne]):
                # Conversion en string si nécessaire
                self.df[colonne] = self.df[colonne].astype(str)

            # Suppression des espaces en début et fin de chaîne
            self.df[colonne] = self.df[colonne].str.strip()

            # Suppression des accents via unicodedata
            self.df[colonne] = self.df[colonne].apply(
                lambda x: unicodedata.normalize("NFD", x)
                .encode("ascii", "ignore")
                .decode("utf-8")
                if isinstance(x, str)
                else x
            )

            # Application de la casse demandée
            if case == "lower":
                self.df[colonne] = self.df[colonne].str.lower()
            elif case == "upper":
                self.df[colonne] = self.df[colonne].str.upper()
            elif case == "title":
                self.df[colonne] = self.df[colonne].str.title()

        logger.debug(
            "Standardisation texte appliquée aux colonnes : %s (case='%s').",
            columns,
            case,
        )

        self._rapport["operations"].append(
            {"operation": "standardize_text", "columns": columns, "case": case}
        )

        return self.df

    def remove_special_chars(
        self,
        columns: List[str],
        keep_chars: str = "",
    ) -> pd.DataFrame:
        """Supprime les caractères spéciaux des colonnes texte.

        Args:
            columns (list[str]): Colonnes texte à nettoyer.
            keep_chars (str): Chaîne de caractères à préserver même s'ils
                sont spéciaux (ex: '-' pour les codes). Par défaut ''.

        Returns:
            pd.DataFrame: DataFrame avec les caractères spéciaux supprimés.
        """
        # Construction du pattern regex : supprime tout sauf alphanum,
        # espaces et les caractères à préserver
        chars_securises = re.escape(keep_chars)
        pattern = rf"[^a-zA-Z0-9\s{chars_securises}]"

        for colonne in columns:
            if colonne not in self.df.columns:
                continue

            self.df[colonne] = self.df[colonne].apply(
                lambda x: re.sub(pattern, "", str(x)).strip()
                if isinstance(x, str) else x
            )

        logger.debug(
            "Caractères spéciaux supprimés dans les colonnes : %s.", columns
        )

        self._rapport["operations"].append(
            {
                "operation": "remove_special_chars",
                "columns": columns,
                "keep_chars": keep_chars,
            }
        )

        return self.df

    def detect_inconsistent_decimals(
        self,
        columns: List[str],
    ) -> Dict[str, dict]:
        """Détecte le mélange de séparateurs décimaux (. et ,) dans les colonnes.

        Args:
            columns (list[str]): Colonnes à inspecter (doivent être de type str
                ou object pour contenir les deux styles de décimales).

        Returns:
            dict: Dictionnaire par colonne avec les clés :
                - 'has_dot' (bool) : présence du séparateur '.'.
                - 'has_comma' (bool) : présence du séparateur ','.
                - 'mixed' (bool) : True si les deux coexistent.
                - 'count_dot' (int) : nombre de valeurs avec '.'.
                - 'count_comma' (int) : nombre de valeurs avec ','.
        """
        rapport_decimales: Dict[str, dict] = {}

        for colonne in columns:
            if colonne not in self.df.columns:
                continue

            # Conversion en string pour l'analyse de contenu
            serie_str = self.df[colonne].astype(str)

            # Détection des occurrences des deux séparateurs
            nb_point = serie_str.str.contains(r"\d\.\d", regex=True).sum()
            nb_virgule = serie_str.str.contains(r"\d,\d", regex=True).sum()

            rapport_decimales[colonne] = {
                "has_dot": bool(nb_point > 0),
                "has_comma": bool(nb_virgule > 0),
                "mixed": bool(nb_point > 0 and nb_virgule > 0),
                "count_dot": int(nb_point),
                "count_comma": int(nb_virgule),
            }

            if rapport_decimales[colonne]["mixed"]:
                logger.warning(
                    "Mélange de séparateurs décimaux détecté dans '%s' "
                    "(%d points, %d virgules).",
                    colonne,
                    nb_point,
                    nb_virgule,
                )

        return rapport_decimales

    def get_cleaning_report(self) -> dict:
        """Retourne le rapport complet des opérations de nettoyage effectuées.

        Returns:
            dict: Rapport structuré contenant :
                - 'lignes_initiales' (int) : nb de lignes avant nettoyage.
                - 'lignes_finales' (int) : nb de lignes après nettoyage.
                - 'colonnes_initiales' (int) : nb de colonnes à l'origine.
                - 'doublons_supprimes' (int) : total des doublons supprimés.
                - 'nan_traites' (int) : total des NaN traités.
                - 'outliers_detectes' (int) : total des outliers supprimés.
                - 'dates_corrigees' (int) : total des dates corrigées.
                - 'operations' (list) : historique détaillé des opérations.
        """
        # Ajout des statistiques finales au rapport
        rapport_final = self._rapport.copy()
        rapport_final["lignes_finales"] = len(self.df)
        rapport_final["colonnes_finales"] = len(self.df.columns)

        return rapport_final
