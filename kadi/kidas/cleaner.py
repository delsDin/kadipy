# -*- coding: utf-8 -*-
"""
Module implémentant Cleaner pour le nettoyage des données agricoles.

Ce module fournit des outils de nettoyage robustes adaptés aux données
rencontrées en AgriTech béninoise : doublons exacts, valeurs manquantes
avec plusieurs stratégies d'imputation, détection statistique d'outliers,
normalisation de dates hétérogènes et standardisation du texte.
"""

import logging
import re
import unicodedata
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# Import des exceptions personnalisées
from kadi.exceptions import CleanError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Stratégies supportées pour le traitement des valeurs manquantes
_STRATEGIES_MISSING = {"mean", "median", "forward_fill", "drop"}

# Méthodes supportées pour la détection des outliers
_METHODES_OUTLIERS = {"iqr", "zscore", "mad"}


class Cleaner:
    """Classe de nettoyage des données agricoles tabulaires.

    Fournit une suite complète de méthodes pour détecter et corriger
    les anomalies courantes dans les fichiers agricoles : doublons,
    valeurs manquantes, outliers statistiques, dates incohérentes
    et texte non normalisé.

    Chaque méthode de nettoyage met à jour le rapport interne (_report)
    et retourne le DataFrame modifié. Cela permet un usage enchaîné.

    Attributs:
        df (pd.DataFrame): Le DataFrame en cours de nettoyage.
        _report (dict): Journal des opérations de nettoyage effectuées.

    Exemple:
        >>> cleaner = Cleaner(df)
        >>> df_propre = (
        ...     cleaner
        ...     .drop_dupes()
        ...     .fill_missing(strategy='mean')
        ...     .parse_dates(cols=['date_recolte'])
        ... )
        >>> print(cleaner.report())
    """

    # Table de rétrocompatibilité des méthodes d'instance.
    # Intercept les anciens noms appelés via cleaner.remove_duplicates() etc.
    _METHODES_DEPRECATED = {
        "remove_duplicates":           "drop_dupes",
        "handle_missing_values":       "fill_missing",
        "remove_outliers":             "drop_outliers",
        "fix_dates":                   "parse_dates",
        "standardize_text":            "norm_text",
        "remove_special_chars":        "strip_chars",
        "detect_inconsistent_decimals":"check_decimals",
        "get_cleaning_report":         "report",
    }

    def __init__(self, df: pd.DataFrame) -> None:
        """Initialise le nettoyeur avec le DataFrame à traiter.

        Args:
            df (pd.DataFrame): Le DataFrame source à nettoyer. Une copie
                interne est créée pour ne pas modifier l'original.

        Raises:
            CleanError: Si l'argument fourni n'est pas un DataFrame.
        """
        # Vérification du type d'entrée
        if not isinstance(df, pd.DataFrame):
            raise CleanError(
                f"Cleaner attend un pandas DataFrame, "
                f"reçu : {type(df).__name__}."
            )

        # Copie de travail du DataFrame (préservation de l'original)
        self.df: pd.DataFrame = df.copy()

        # Rapport d'opérations initialisé à zéro
        self._report: Dict = {
            "doublons_supprimes": 0,
            "nan_traites": 0,
            "outliers_detectes": 0,
            "dates_corrigees": 0,
            "lignes_initiales": len(df),
            "colonnes_initiales": len(df.columns),
            "operations": [],
        }

    def __getattr__(self, name: str):
        """Intercepte les anciens noms de méthodes pour la rétrocompatibilité.

        Permet aux scripts utilisant les anciens noms (ex: remove_duplicates)
        de continuer à fonctionner avec un DeprecationWarning.

        Args:
            name (str): Nom de la méthode demandée.

        Returns:
            callable: La méthode correspondant au nouveau nom.

        Raises:
            AttributeError: Si le nom n'est pas un alias connu.
        """
        if name in Cleaner._METHODES_DEPRECATED:
            # Récupération du nouveau nom équivalent
            nouveau_nom = Cleaner._METHODES_DEPRECATED[name]
            warnings.warn(
                f"Cleaner.{name}() est obsolète et sera supprimé dans KadiPy v2.0. "
                f"Utilisez Cleaner.{nouveau_nom}() à la place.",
                category=DeprecationWarning,
                # stacklevel=2 pointe vers la ligne de code de l'utilisateur
                stacklevel=2,
            )
            return getattr(self, nouveau_nom)
        raise AttributeError(
            f"'Cleaner' n'a pas de méthode '{name}'."
        )

    def drop_dupes(
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
        self._report["doublons_supprimes"] += nb_doublons
        self._report["operations"].append(
            {"operation": "drop_dupes", "doublons_supprimes": nb_doublons}
        )

        return self.df

    def fill_missing(
        self,
        strategy: str = "mean",
        cols: Optional[List[str]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Traite les valeurs manquantes (NaN) selon une stratégie donnée.

        Args:
            strategy (str): Stratégie d'imputation parmi :
                - 'mean' : remplace les NaN par la moyenne de la colonne.
                - 'median' : remplace par la médiane.
                - 'forward_fill' : propage la dernière valeur connue.
                - 'drop' : supprime les lignes contenant des NaN.
                Par défaut 'mean'.
            cols (list[str] | None): Colonnes cibles. None pour
                toutes les colonnes. Par défaut None.
                Alias accepté : columns= (rétrocompatibilité).

        Returns:
            pd.DataFrame: DataFrame avec les valeurs manquantes traitées.

        Raises:
            CleanError: Si la stratégie fournie est invalide.
        """
        # Rétrocompatibilité : ancien paramètre 'columns' accepté
        if "columns" in kwargs:
            cols = kwargs.pop("columns")

        # Validation de la stratégie
        if strategy not in _STRATEGIES_MISSING:
            raise CleanError(
                f"Stratégie '{strategy}' invalide. Valeurs acceptées : "
                f"{_STRATEGIES_MISSING}."
            )

        # Sélection des colonnes cibles
        colonnes_cibles = cols if cols else list(self.df.columns)

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
        self._report["nan_traites"] += nb_nan_traites
        self._report["operations"].append(
            {
                "operation": "fill_missing",
                "strategy": strategy,
                "nan_traites": nb_nan_traites,
            }
        )

        return self.df

    def drop_outliers(
        self,
        method: str = "iqr",
        thresh: float = 1.5,
        cols: Optional[List[str]] = None,
        **kwargs,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Détecte et supprime les outliers statistiques du DataFrame.

        Args:
            method (str): Méthode de détection parmi :
                - 'iqr' : règle des 1.5 × IQR (interquartile range).
                - 'zscore' : seuil sur le Z-score standardisé.
                - 'mad' : Median Absolute Deviation, robuste aux outliers.
                Par défaut 'iqr'.
            thresh (float): Seuil de détection. Pour 'iqr' : 1.5 standard.
                Pour 'zscore' : 3.0 recommandé. Par défaut 1.5.
                Alias accepté : threshold= (rétrocompatibilité).
            cols (list[str] | None): Colonnes numériques à analyser.
                None pour toutes les colonnes numériques. Par défaut None.
                Alias accepté : columns= (rétrocompatibilité).

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]: Tuple contenant :
                - Le DataFrame sans outliers.
                - Le DataFrame des lignes identifiées comme outliers.

        Raises:
            CleanError: Si la méthode fournie est invalide.
        """
        # Rétrocompatibilité : anciens paramètres acceptés
        if "threshold" in kwargs:
            thresh = kwargs.pop("threshold")
        if "columns" in kwargs:
            cols = kwargs.pop("columns")

        # Validation de la méthode
        if method not in _METHODES_OUTLIERS:
            raise CleanError(
                f"Méthode '{method}' invalide. Valeurs acceptées : "
                f"{_METHODES_OUTLIERS}."
            )

        # Sélection des colonnes numériques cibles
        if cols:
            cols_num = [c for c in cols if pd.api.types.is_numeric_dtype(self.df[c])]
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
                borne_basse = q1 - thresh * iqr
                borne_haute = q3 + thresh * iqr
                masque_col = self.df[colonne].between(borne_basse, borne_haute)

            elif method == "zscore":
                # Z-score standardisé : |z| ≤ thresh
                z_scores = np.abs(stats.zscore(serie))
                # Alignement avec l'index original (NaN pour les valeurs manquantes)
                z_alignes = self.df[colonne].copy().astype(float)
                z_alignes.loc[serie.index] = z_scores
                masque_col = z_alignes <= thresh

            elif method == "mad":
                # MAD : valeur robuste, moins sensible aux outliers extrêmes
                mediane = serie.median()
                mad = np.median(np.abs(serie - mediane))
                # Facteur de cohérence pour distribution normale
                mad_facteur = mad * 1.4826
                if mad_facteur > 0:
                    z_mad = np.abs(self.df[colonne] - mediane) / mad_facteur
                    masque_col = z_mad <= thresh
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
            "%d outlier(s) détecté(s) et supprimé(s) (method='%s', thresh=%.2f).",
            nb_outliers,
            method,
            thresh,
        )

        # Mise à jour du rapport
        self._report["outliers_detectes"] += nb_outliers
        self._report["operations"].append(
            {
                "operation": "drop_outliers",
                "method": method,
                "thresh": thresh,
                "outliers_supprimes": nb_outliers,
            }
        )

        return self.df, df_outliers

    def parse_dates(
        self,
        cols: Optional[List[str]] = None,
        infer: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """Normalise les formats de dates hétérogènes dans les colonnes spécifiées.

        Tente de parser les dates avec pd.to_datetime(), en inférant le format
        si possible. Les valeurs non parsables sont laissées comme NaT.

        Args:
            cols (list[str] | None): Liste des colonnes contenant des dates.
                Alias accepté : columns= (rétrocompatibilité).
            infer (bool): Si True, infère automatiquement le format de date.
                Par défaut True. Alias accepté : infer_format= (rétrocompatibilité).

        Returns:
            pd.DataFrame: DataFrame avec les colonnes de dates normalisées
                en datetime64.
        """
        # Rétrocompatibilité : anciens paramètres acceptés
        if "columns" in kwargs:
            cols = kwargs.pop("columns")
        if "infer_format" in kwargs:
            infer = kwargs.pop("infer_format")

        # Valeur par défaut : toutes les colonnes objet du DataFrame
        if cols is None:
            cols = [c for c in self.df.columns if self.df[c].dtype == object]

        nb_dates_corrigees = 0

        for colonne in cols:
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

                # Comptage des conversions réussies après le parsing
                nb_apres = self.df[colonne].notna().sum()
                # On comptabilise uniquement les dates effectivement converties
                nb_corrigees = int(nb_apres)
                nb_dates_corrigees += nb_corrigees

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
        self._report["dates_corrigees"] += nb_dates_corrigees
        self._report["operations"].append(
            {
                "operation": "parse_dates",
                "cols": cols,
                "dates_corrigees": nb_dates_corrigees,
            }
        )

        return self.df

    def norm_text(
        self,
        cols: Optional[List[str]] = None,
        case: str = "lower",
        **kwargs,
    ) -> pd.DataFrame:
        """Standardise le texte des colonnes : trim, casse, suppression d'accents.

        Args:
            cols (list[str] | None): Colonnes texte à standardiser.
                Par défaut None : toutes les colonnes texte.
                Alias accepté : columns= (rétrocompatibilité).
            case (str): Casse à appliquer : 'lower', 'upper' ou 'title'.
                Par défaut 'lower'.

        Returns:
            pd.DataFrame: DataFrame avec les colonnes texte standardisées.
        """
        # Rétrocompatibilité : ancien paramètre 'columns' accepté
        if "columns" in kwargs:
            cols = kwargs.pop("columns")

        # Valeur par défaut : toutes les colonnes texte
        if cols is None:
            cols = [c for c in self.df.columns if self.df[c].dtype == object]

        for colonne in cols:
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
            "Normalisation texte appliquée aux colonnes : %s (case='%s').",
            cols,
            case,
        )

        self._report["operations"].append(
            {"operation": "norm_text", "cols": cols, "case": case}
        )

        return self.df

    def strip_chars(
        self,
        cols: Optional[List[str]] = None,
        keep: str = "",
        **kwargs,
    ) -> pd.DataFrame:
        """Supprime les caractères spéciaux des colonnes texte.

        Args:
            cols (list[str] | None): Colonnes texte à nettoyer.
                Par défaut None : toutes les colonnes texte.
                Alias accepté : columns= (rétrocompatibilité).
            keep (str): Chaîne de caractères à préserver même s'ils
                sont spéciaux (ex: '-' pour les codes). Par défaut ''.
                Alias accepté : keep_chars= (rétrocompatibilité).

        Returns:
            pd.DataFrame: DataFrame avec les caractères spéciaux supprimés.
        """
        # Rétrocompatibilité : anciens paramètres acceptés
        if "columns" in kwargs:
            cols = kwargs.pop("columns")
        if "keep_chars" in kwargs:
            keep = kwargs.pop("keep_chars")

        # Valeur par défaut : toutes les colonnes texte
        if cols is None:
            cols = [c for c in self.df.columns if self.df[c].dtype == object]

        # Construction du pattern regex : supprime tout sauf alphanum,
        # espaces et les caractères à préserver
        chars_securises = re.escape(keep)
        pattern = rf"[^a-zA-Z0-9\s{chars_securises}]"

        for colonne in cols:
            if colonne not in self.df.columns:
                continue

            self.df[colonne] = self.df[colonne].apply(
                lambda x: re.sub(pattern, "", str(x)).strip()
                if isinstance(x, str) else x
            )

        logger.debug(
            "Caractères spéciaux supprimés dans les colonnes : %s.", cols
        )

        self._report["operations"].append(
            {
                "operation": "strip_chars",
                "cols": cols,
                "keep": keep,
            }
        )

        return self.df

    def check_decimals(
        self,
        cols: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, dict]:
        """Détecte le mélange de séparateurs décimaux (. et ,) dans les colonnes.

        Args:
            cols (list[str]): Colonnes à inspecter (doivent être de type str
                ou object pour contenir les deux styles de décimales).
                Alias accepté : columns= (rétrocompatibilité).

        Returns:
            dict: Dictionnaire par colonne avec les clés :
                - 'has_dot' (bool) : présence du séparateur '.'.
                - 'has_comma' (bool) : présence du séparateur ','.
                - 'mixed' (bool) : True si les deux coexistent.
                - 'count_dot' (int) : nombre de valeurs avec '.'.
                - 'count_comma' (int) : nombre de valeurs avec ','.
        """
        # Rétrocompatibilité : ancien paramètre 'columns' accepté
        if "columns" in kwargs:
            cols = kwargs.pop("columns")

        # Valeur par défaut : toutes les colonnes objet du DataFrame
        if cols is None:
            cols = [c for c in self.df.columns if self.df[c].dtype == object]

        rapport_decimales: Dict[str, dict] = {}

        for colonne in cols:
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

    def report(self) -> dict:
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
        rapport_final = self._report.copy()
        rapport_final["lignes_finales"] = len(self.df)
        rapport_final["colonnes_finales"] = len(self.df.columns)

        return rapport_final


# Table des anciens noms -> (nouveau nom, classe cible)
# Utilisée par __getattr__ pour intercepter les imports du style :
#   from kadi.kidas.cleaner import DataCleaner
_DEPRECATED = {
    "DataCleaner": ("Cleaner", Cleaner),
}


def __getattr__(name: str):
    """Intercepte les anciens noms importés depuis ce module.

    Permet la rétrocompatibilité pour les imports du style :
    ``from kadi.kidas.cleaner import DataCleaner``.

    Args:
        name (str): Nom du symbole demandé dans ce module.

    Returns:
        type: La classe correspondante.

    Raises:
        AttributeError: Si le nom n'est pas un alias connu.
    """
    import warnings as _warnings
    if name in _DEPRECATED:
        # Récupère le nouveau nom et la classe
        new_name, cls = _DEPRECATED[name]
        _warnings.warn(
            f"kadi.kidas.cleaner.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return cls
    raise AttributeError(
        f"Le module 'kadi.kidas.cleaner' n'a pas d'attribut '{name}'."
    )
