# -*- coding: utf-8 -*-
"""
Module implémentant ExcelDataSource pour la lecture/écriture de fichiers Excel.

Ce module gère les fichiers Excel (.xls, .xlsx) rencontrés dans les rapports
agricoles béninois : cellules fusionnées pour les communes et marchés,
en-têtes non standard sur des lignes variables, multi-feuilles, et dates
stockées sous formats hétérogènes.
"""

import logging
import os
from typing import List, Optional, Union

import pandas as pd

# Import de la classe de base et des exceptions personnalisées
from kadi.kidas.sources.base import DataSource
from kadi.exceptions import KidasReadError, KidasWriteError, KidasConnectionError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Nombre maximum de lignes inspectées pour la détection de l'en-tête
_MAX_HEADER_SCAN_ROWS = 15


class ExcelDataSource(DataSource):
    """Source de données pour les fichiers Excel agricoles (.xls, .xlsx).

    Gère la lecture robuste de fichiers Excel avec des structures complexes :
    cellules fusionnées (forward fill), en-têtes sur des lignes variables,
    lignes vides intercalées et feuilles multiples.

    Attributs:
        file_path (str): Chemin absolu ou relatif vers le fichier Excel.
        sheet_name (str | int): Nom ou index de la feuille à lire.
        header_row (str | int): Ligne d'en-tête. 'auto' pour la détection
            automatique.
        _detected_header_row (int | None): Ligne d'en-tête détectée en cache.

    Exemple:
        >>> source = ExcelDataSource('prix_marches_2024.xlsx')
        >>> print(source.list_sheets())
        ['Janvier', 'Fevrier']
        >>> df = source.read(sheet_name='Janvier')
    """

    def __init__(
        self,
        file_path: str,
        sheet_name: Union[str, int] = 0,
        header_row: Union[str, int] = "auto",
    ) -> None:
        """Initialise la source Excel avec détection automatique de l'en-tête.

        Args:
            file_path (str): Chemin vers le fichier Excel à lire.
            sheet_name (str | int): Nom ou index de la feuille par défaut.
                Par défaut 0 (première feuille).
            header_row (str | int): Ligne contenant les en-têtes de colonnes.
                'auto' pour la détection automatique. Par défaut 'auto'.
        """
        # Initialisation de la classe parente avec le type 'excel'
        super().__init__(
            source_path=file_path,
            source_type="excel",
            encoding="utf-8",
        )

        # Chemin vers le fichier Excel
        self.file_path: str = file_path

        # Feuille par défaut (nom ou index)
        self.sheet_name: Union[str, int] = sheet_name

        # Ligne d'en-tête (peut être 'auto' avant détection)
        self.header_row: Union[str, int] = header_row

        # Cache interne pour la ligne d'en-tête détectée
        self._detected_header_row: Optional[int] = None

    def detect_header_row(self) -> int:
        """Détecte automatiquement la ligne contenant les en-têtes de colonnes.

        Inspecte les premières lignes du fichier et cherche la première ligne
        contenant des valeurs non-null et hétérogènes (mélange de types),
        ce qui caractérise une ligne d'en-tête typique.

        Returns:
            int: Index (0-based) de la ligne d'en-tête détectée.

        Raises:
            KidasConnectionError: Si le fichier Excel n'est pas accessible.
            KidasReadError: Si la détection échoue.
        """
        if not self.validate_connection():
            raise KidasConnectionError(
                f"Fichier Excel introuvable : '{self.file_path}'"
            )

        try:
            # Lecture des premières lignes sans en-tête pour l'inspection
            df_brut = pd.read_excel(
                self.file_path,
                sheet_name=self.sheet_name,
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
                self.file_path,
            )

            # Mise en cache du résultat
            self._detected_header_row = ligne_entete
            return ligne_entete

        except Exception as erreur:
            raise KidasReadError(
                f"Impossible de détecter l'en-tête dans '{self.file_path}' : {erreur}"
            ) from erreur

    def list_sheets(self) -> List[str]:
        """Retourne la liste des noms de feuilles du fichier Excel.

        Returns:
            List[str]: Liste ordonnée des noms de feuilles dans le fichier.

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
            KidasReadError: Si la lecture de la structure échoue.
        """
        if not self.validate_connection():
            raise KidasConnectionError(
                f"Fichier Excel introuvable : '{self.file_path}'"
            )

        try:
            # Lecture de la liste des feuilles via ExcelFile
            with pd.ExcelFile(self.file_path) as classeur:
                feuilles = classeur.sheet_names

            logger.debug(
                "Feuilles trouvées dans '%s' : %s.", self.file_path, feuilles
            )
            return feuilles

        except Exception as erreur:
            raise KidasReadError(
                f"Impossible de lister les feuilles de '{self.file_path}' : {erreur}"
            ) from erreur

    def get_sheet_metadata(self, sheet_name: Union[str, int]) -> dict:
        """Retourne les métadonnées d'une feuille spécifique.

        Args:
            sheet_name (str | int): Nom ou index de la feuille à inspecter.

        Returns:
            dict: Dictionnaire contenant les clés :
                - 'sheet_name' (str) : nom de la feuille.
                - 'rows' (int) : nombre de lignes de données.
                - 'cols' (int) : nombre de colonnes.

        Raises:
            KidasReadError: Si la lecture de la feuille échoue.
        """
        try:
            # Lecture de la feuille entière pour les métadonnées
            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            return {
                "sheet_name": sheet_name,
                "rows": len(df),
                "cols": len(df.columns),
                "columns": list(df.columns),
            }
        except Exception as erreur:
            raise KidasReadError(
                f"Impossible de lire la feuille '{sheet_name}' "
                f"dans '{self.file_path}' : {erreur}"
            ) from erreur

    def unmerge_cells(self, df: pd.DataFrame) -> pd.DataFrame:
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
        sheet_name: Optional[Union[str, int]] = None,
    ) -> pd.DataFrame:
        """Lit une feuille Excel et retourne son contenu sous forme de DataFrame.

        Détecte automatiquement la ligne d'en-tête et applique un forward fill
        pour résoudre les cellules fusionnées.

        Args:
            sheet_name (str | int | None): Feuille à lire. Si None, utilise
                la valeur définie à l'initialisation. Par défaut None.

        Returns:
            pd.DataFrame: Les données de la feuille Excel.

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
            KidasReadError: Si la lecture échoue.
        """
        if not self.validate_connection():
            raise KidasConnectionError(
                f"Fichier Excel inaccessible : '{self.file_path}'"
            )

        # Détermination de la feuille à lire
        feuille = sheet_name if sheet_name is not None else self.sheet_name

        # Détermination de la ligne d'en-tête
        if self.header_row == "auto":
            ligne_entete = (
                self._detected_header_row
                if self._detected_header_row is not None
                else self.detect_header_row()
            )
        else:
            ligne_entete = int(self.header_row)

        try:
            # Lecture du fichier Excel avec la ligne d'en-tête correcte
            df = pd.read_excel(
                self.file_path,
                sheet_name=feuille,
                header=ligne_entete,
            )

            # Suppression des lignes entièrement vides
            df = df.dropna(how="all")

            # Résolution des cellules fusionnées par forward fill
            df = self.unmerge_cells(df)

            logger.info(
                "Fichier Excel '%s' (feuille '%s') lu : %d lignes, %d colonnes.",
                self.file_path,
                feuille,
                len(df),
                len(df.columns),
            )

            # Mise à jour de l'horodatage de lecture
            self._update_last_read()
            return df

        except Exception as erreur:
            raise KidasReadError(
                f"Erreur lors de la lecture de '{self.file_path}' "
                f"(feuille '{feuille}') : {erreur}"
            ) from erreur

    def write(
        self,
        data: pd.DataFrame,
        sheet_name: str = "Sheet1",
    ) -> bool:
        """Écrit un DataFrame vers le fichier Excel de la source.

        Args:
            data (pd.DataFrame): Les données à écrire dans le fichier Excel.
            sheet_name (str): Nom de la feuille de destination.
                Par défaut 'Sheet1'.

        Returns:
            bool: True si l'écriture s'est déroulée avec succès.

        Raises:
            KidasWriteError: Si l'écriture vers le fichier échoue.
        """
        try:
            # Écriture du DataFrame en format Excel
            data.to_excel(self.file_path, sheet_name=sheet_name, index=False)
            logger.info(
                "DataFrame écrit avec succès vers '%s' (feuille '%s', %d lignes).",
                self.file_path,
                sheet_name,
                len(data),
            )
            return True

        except Exception as erreur:
            raise KidasWriteError(
                f"Impossible d'écrire vers '{self.file_path}' : {erreur}"
            ) from erreur

    def get_metadata(self) -> dict:
        """Retourne les métadonnées descriptives du fichier Excel.

        Returns:
            dict: Dictionnaire contenant les clés suivantes :
                - 'source_path' (str) : chemin du fichier.
                - 'source_type' (str) : 'excel'.
                - 'sheets' (List[str]) : liste des feuilles disponibles.
                - 'active_sheet' (str | int) : feuille active courante.
                - 'size_kb' (float) : taille du fichier en kilo-octets.
                - 'last_read' (str | None) : horodatage de la dernière lecture.
        """
        # Récupération de la liste des feuilles
        try:
            feuilles = self.list_sheets()
        except KidasReadError:
            feuilles = []

        # Calcul de la taille du fichier
        taille_kb = os.path.getsize(self.file_path) / 1024 if os.path.isfile(
            self.file_path
        ) else 0.0

        return {
            "source_path": self.file_path,
            "source_type": "excel",
            "sheets": feuilles,
            "active_sheet": self.sheet_name,
            "detected_header_row": self._detected_header_row,
            "size_kb": round(taille_kb, 2),
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def validate_connection(self) -> bool:
        """Vérifie que le fichier Excel existe et est lisible.

        Returns:
            bool: True si le fichier est accessible en lecture, False sinon.
        """
        # Vérification de l'existence et de la lisibilité du fichier
        est_accessible = os.path.isfile(self.file_path) and os.access(
            self.file_path, os.R_OK
        )

        if not est_accessible:
            logger.warning(
                "Le fichier Excel '%s' n'existe pas ou n'est pas lisible.",
                self.file_path,
            )

        return est_accessible
