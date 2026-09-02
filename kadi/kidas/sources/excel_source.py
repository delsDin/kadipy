# -*- coding: utf-8 -*-
"""
Module implémentant ExcelSource pour la lecture/écriture de fichiers Excel.

Ce module gère les fichiers Excel (.xls, .xlsx) rencontrés dans les rapports
agricoles béninois : cellules fusionnées pour les communes et marchés,
en-têtes non standard sur des lignes variables, multi-feuilles, et dates
stockées sous formats hétérogènes.

L'ancien nom ExcelDataSource est conservé comme alias obsolète : il continue
de fonctionner mais émet un DeprecationWarning pour guider la migration.
"""

import logging
import os
import warnings
from typing import List, Optional, Union

import pandas as pd

# Import de la classe de base et des exceptions personnalisées
from kadi.kidas.sources.base import Source
from kadi.exceptions import ReadError, WriteError, ConnectError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Nombre maximum de lignes inspectées pour la détection de l'en-tête
_MAX_HEADER_SCAN_ROWS = 15


class ExcelSource(Source):
    """Source de données pour les fichiers Excel agricoles (.xls, .xlsx).

    Gère la lecture robuste de fichiers Excel avec des structures complexes :
    cellules fusionnées (forward fill), en-têtes sur des lignes variables,
    lignes vides intercalées et feuilles multiples.

    Attributs:
        path (str): Chemin absolu ou relatif vers le fichier Excel.
        sheet (str | int): Nom ou index de la feuille à lire.
        header (str | int): Ligne d'en-tête. 'auto' pour la détection
            automatique.
        _header (int | None): Ligne d'en-tête détectée en cache.

    Exemple:
        >>> source = ExcelSource('prix_marches_2024.xlsx')
        >>> print(source.sheets())
        ['Janvier', 'Fevrier']
        >>> df = source.read(sheet='Janvier')
    """

    def __init__(
        self,
        path: str,
        sheet: Union[str, int] = 0,
        header: Union[str, int] = "auto",
    ) -> None:
        """Initialise la source Excel avec détection automatique de l'en-tête.

        Args:
            path (str): Chemin vers le fichier Excel à lire.
            sheet (str | int): Nom ou index de la feuille par défaut.
                Par défaut 0 (première feuille).
            header (str | int): Ligne contenant les en-têtes de colonnes.
                'auto' pour la détection automatique. Par défaut 'auto'.
        """
        # Initialisation de la classe parente avec le type 'excel'
        super().__init__(
            path=path,
            kind="excel",
            encoding="utf-8",
        )

        # Feuille par défaut (nom ou index)
        self.sheet: Union[str, int] = sheet

        # Ligne d'en-tête (peut être 'auto' avant détection)
        self.header: Union[str, int] = header

        # Cache interne pour la ligne d'en-tête détectée
        self._header: Optional[int] = None

    def _sniff_header(self) -> int:
        """Détecte automatiquement la ligne contenant les en-têtes de colonnes.

        Inspecte les premières lignes du fichier et cherche la première ligne
        contenant des valeurs non-null et hétérogènes (mélange de types),
        ce qui caractérise une ligne d'en-tête typique.

        Returns:
            int: Index (0-based) de la ligne d'en-tête détectée.

        Raises:
            ConnectError: Si le fichier Excel n'est pas accessible.
            ReadError: Si la détection échoue.
        """
        if not self.ping():
            raise ConnectError(
                f"Fichier Excel introuvable : '{self.path}'"
            )

        try:
            # Lecture des premières lignes sans en-tête pour l'inspection
            df_brut = pd.read_excel(
                self.path,
                sheet_name=self.sheet,
                header=None,
                nrows=_MAX_HEADER_SCAN_ROWS,
            )

            # Recherche de la ligne la plus hétérogène (types mixtes = en-tête)
            ligne_entete = 0
            meilleur_score = -1

            for i, ligne in df_brut.iterrows():
                # Filtrage des valeurs non nulles
                valeurs_non_null = ligne.dropna()

                if len(valeurs_non_null) == 0:
                    # Ligne vide : on passe
                    continue

                # Score = nb de valeurs non-null (ligne dense = probable en-tête)
                score = len(valeurs_non_null)

                if score > meilleur_score:
                    meilleur_score = score
                    ligne_entete = int(i)

            logger.debug(
                "En-tête détecté à la ligne %d pour '%s'.",
                ligne_entete,
                self.path,
            )

            # Mise en cache du résultat
            self._header = ligne_entete
            return ligne_entete

        except Exception as erreur:
            raise ReadError(
                f"Impossible de détecter l'en-tête dans '{self.path}' : {erreur}"
            ) from erreur

    def sheets(self) -> List[str]:
        """Retourne la liste des noms de feuilles du fichier Excel.

        Returns:
            List[str]: Liste ordonnée des noms de feuilles dans le fichier.

        Raises:
            ConnectError: Si le fichier n'est pas accessible.
            ReadError: Si la lecture de la structure échoue.
        """
        if not self.ping():
            raise ConnectError(
                f"Fichier Excel introuvable : '{self.path}'"
            )

        try:
            # Lecture de la liste des feuilles via ExcelFile
            with pd.ExcelFile(self.path) as classeur:
                feuilles = classeur.sheet_names

            logger.debug(
                "Feuilles trouvées dans '%s' : %s.", self.path, feuilles
            )
            return feuilles

        except Exception as erreur:
            raise ReadError(
                f"Impossible de lister les feuilles de '{self.path}' : {erreur}"
            ) from erreur

    def sheet_info(self, sheet: Union[str, int]) -> dict:
        """Retourne les métadonnées d'une feuille spécifique.

        Args:
            sheet (str | int): Nom ou index de la feuille à inspecter.

        Returns:
            dict: Dictionnaire contenant les clés :
                - 'sheet' (str) : nom de la feuille.
                - 'rows' (int) : nombre de lignes de données.
                - 'cols' (int) : nombre de colonnes.
                - 'columns' (list) : liste des noms de colonnes.

        Raises:
            ReadError: Si la lecture de la feuille échoue.
        """
        try:
            # Lecture de la feuille entière pour les métadonnées
            df = pd.read_excel(self.path, sheet_name=sheet)
            return {
                "sheet": sheet,
                "rows": len(df),
                "cols": len(df.columns),
                "columns": list(df.columns),
            }
        except Exception as erreur:
            raise ReadError(
                f"Impossible de lire la feuille '{sheet}' "
                f"dans '{self.path}' : {erreur}"
            ) from erreur

    def _unmerge(self, df: pd.DataFrame) -> pd.DataFrame:
        """Résout les cellules fusionnées par un forward fill vertical.

        Dans les fichiers Excel africains, les colonnes 'Commune' ou 'Marché'
        contiennent souvent des cellules fusionnées sur plusieurs lignes.
        Cette méthode propage la dernière valeur non-null vers le bas.

        Args:
            df (pd.DataFrame): Le DataFrame lu depuis Excel (avant forward fill).

        Returns:
            pd.DataFrame: DataFrame avec les cellules fusionnées résolues.
        """
        # Forward fill sur toutes les colonnes pour résoudre les cellules fusionnées
        df_resolu = df.ffill(axis=0)
        logger.debug(
            "Forward fill appliqué sur le DataFrame (%d lignes).", len(df_resolu)
        )
        return df_resolu

    def read(
        self,
        sheet: Optional[Union[str, int]] = None,
    ) -> pd.DataFrame:
        """Lit une feuille Excel et retourne son contenu sous forme de DataFrame.

        Détecte automatiquement la ligne d'en-tête et applique un forward fill
        pour résoudre les cellules fusionnées.

        Args:
            sheet (str | int | None): Feuille à lire. Si None, utilise
                la valeur définie à l'initialisation. Par défaut None.

        Returns:
            pd.DataFrame: Les données de la feuille Excel.

        Raises:
            ConnectError: Si le fichier n'est pas accessible.
            ReadError: Si la lecture échoue.
        """
        if not self.ping():
            raise ConnectError(
                f"Fichier Excel inaccessible : '{self.path}'"
            )

        # Détermination de la feuille à lire
        feuille = sheet if sheet is not None else self.sheet

        # Détermination de la ligne d'en-tête
        if self.header == "auto":
            ligne_entete = (
                self._header
                if self._header is not None
                else self._sniff_header()
            )
        else:
            ligne_entete = int(self.header)

        try:
            # Lecture du fichier Excel avec la ligne d'en-tête correcte
            df = pd.read_excel(
                self.path,
                sheet_name=feuille,
                header=ligne_entete,
            )

            # Suppression des lignes entièrement vides
            df = df.dropna(how="all")

            # Résolution des cellules fusionnées par forward fill
            df = self._unmerge(df)

            logger.info(
                "Fichier Excel '%s' (feuille '%s') lu : %d lignes, %d colonnes.",
                self.path,
                feuille,
                len(df),
                len(df.columns),
            )

            # Mise à jour de l'horodatage de lecture
            self._touch()
            return df

        except Exception as erreur:
            raise ReadError(
                f"Erreur lors de la lecture de '{self.path}' "
                f"(feuille '{feuille}') : {erreur}"
            ) from erreur

    def write(
        self,
        data: pd.DataFrame,
        sheet: str = "Sheet1",
    ) -> bool:
        """Écrit un DataFrame vers le fichier Excel de la source.

        Args:
            data (pd.DataFrame): Les données à écrire dans le fichier Excel.
            sheet (str): Nom de la feuille de destination.
                Par défaut 'Sheet1'.

        Returns:
            bool: True si l'écriture s'est déroulée avec succès.

        Raises:
            WriteError: Si l'écriture vers le fichier échoue.
        """
        try:
            # Écriture du DataFrame en format Excel
            data.to_excel(self.path, sheet_name=sheet, index=False)
            logger.info(
                "DataFrame écrit avec succès vers '%s' (feuille '%s', %d lignes).",
                self.path,
                sheet,
                len(data),
            )
            return True

        except Exception as erreur:
            raise WriteError(
                f"Impossible d'écrire vers '{self.path}' : {erreur}"
            ) from erreur

    def info(self) -> dict:
        """Retourne les métadonnées descriptives du fichier Excel.

        Returns:
            dict: Dictionnaire contenant les clés suivantes :
                - 'path' (str) : chemin du fichier.
                - 'kind' (str) : 'excel'.
                - 'sheets' (List[str]) : liste des feuilles disponibles.
                - 'active_sheet' (str | int) : feuille active courante.
                - 'detected_header' (int | None) : ligne d'en-tête détectée.
                - 'size_kb' (float) : taille du fichier en kilo-octets.
                - 'last_read' (str | None) : horodatage de la dernière lecture.
        """
        # Récupération de la liste des feuilles
        try:
            feuilles = self.sheets()
        except ReadError:
            feuilles = []

        # Calcul de la taille du fichier
        taille_kb = os.path.getsize(self.path) / 1024 if os.path.isfile(
            self.path
        ) else 0.0

        return {
            "path": self.path,
            "kind": "excel",
            "sheets": feuilles,
            "active_sheet": self.sheet,
            "detected_header": self._header,
            "size_kb": round(taille_kb, 2),
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def ping(self) -> bool:
        """Vérifie que le fichier Excel existe et est lisible.

        Returns:
            bool: True si le fichier est accessible en lecture, False sinon.
        """
        # Vérification de l'existence et de la lisibilité du fichier
        est_accessible = os.path.isfile(self.path) and os.access(
            self.path, os.R_OK
        )

        if not est_accessible:
            logger.warning(
                "Le fichier Excel '%s' n'existe pas ou n'est pas lisible.",
                self.path,
            )

        return est_accessible


# Table des anciens noms -> (nouveau nom, classe cible)
# Utilisée par __getattr__ pour intercepter les imports de l'ancien nom.
_DEPRECATED = {
    "ExcelDataSource": ("ExcelSource", ExcelSource),
}


def __getattr__(name: str):
    """Intercepte l'accès aux anciens noms de classes pour émettre un avertissement.

    Args:
        name (str): Nom de l'attribut demandé dans ce module.

    Returns:
        type: La classe correspondant à l'ancien nom.

    Raises:
        AttributeError: Si le nom demandé n'est ni un symbole courant
            ni un ancien nom connu.
    """
    if name in _DEPRECATED:
        # Récupère le nouveau nom et la classe cible
        new_name, cls = _DEPRECATED[name]
        warnings.warn(
            f"kadi.kidas.sources.excel_source.{name} est obsolète et sera supprimé "
            f"dans KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            # stacklevel=2 pointe vers la ligne de code de l'utilisateur,
            # pas vers cette fonction interne
            stacklevel=2,
        )
        return cls
    raise AttributeError(
        f"Le module '{__name__}' n'a pas d'attribut '{name}'."
    )
