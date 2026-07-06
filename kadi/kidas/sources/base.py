# -*- coding: utf-8 -*-
"""
Module définissant la classe abstraite DataSource.

DataSource est l'interface commune à toutes les sources de données
du module kidas. Chaque format (CSV, Excel, JSON, NetCDF, API) doit
implémenter ce contrat pour garantir une utilisation uniforme dans
les pipelines d'acquisition de données agricoles.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import pandas as pd

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Classe abstraite définissant l'interface commune à toutes les sources de données.

    Cette classe représente le contrat que chaque source concrète (CSV, Excel,
    JSON, NetCDF, API) doit respecter. Elle garantit que toutes les sources
    exposent les mêmes méthodes fondamentales : read(), write(), get_metadata()
    et validate_connection().

    Attributs:
        source_path (str): Chemin local du fichier ou URI de la ressource.
        source_type (str): Type de source parmi 'csv', 'excel', 'json',
            'netcdf' ou 'api'.
        encoding (str): Encodage des données (ex: 'utf-8', 'latin1').
            Peut être 'auto' pour une détection automatique.
        last_read (datetime | None): Horodatage de la dernière lecture
            réussie. None si la source n'a jamais été lue.
    """

    def __init__(
        self,
        source_path: str,
        source_type: str,
        encoding: str = "utf-8",
    ) -> None:
        """Initialise les attributs communs à toutes les sources de données.

        Args:
            source_path (str): Chemin local du fichier ou URI de la ressource.
            source_type (str): Type de la source (ex: 'csv', 'excel').
            encoding (str): Encodage des données. Par défaut 'utf-8'.
        """
        # Chemin ou URI de la source de données
        self.source_path: str = source_path

        # Type de source : 'csv', 'excel', 'json', 'netcdf' ou 'api'
        self.source_type: str = source_type

        # Encodage utilisé pour la lecture de la source
        self.encoding: str = encoding

        # Horodatage de la dernière lecture réussie (None si jamais lue)
        self.last_read: Optional[datetime] = None

    @abstractmethod
    def read(self, **kwargs) -> pd.DataFrame:
        """Lit les données depuis la source et les retourne sous forme de DataFrame.

        Cette méthode doit être implémentée par chaque sous-classe concrète
        selon le format de fichier concerné.

        Args:
            **kwargs: Arguments optionnels spécifiques à chaque format
                (ex: nrows, sheet_name, lat_bounds...).

        Returns:
            pd.DataFrame: Les données lues depuis la source.

        Raises:
            KidasReadError: Si la lecture échoue (fichier corrompu,
                format invalide, etc.).
            KidasConnectionError: Si la source n'est pas accessible.
        """
        pass

    @abstractmethod
    def write(self, data: pd.DataFrame, **kwargs) -> bool:
        """Écrit un DataFrame vers la source de données.

        Cette méthode doit être implémentée par chaque sous-classe concrète.

        Args:
            data (pd.DataFrame): Les données à écrire vers la source.
            **kwargs: Arguments optionnels spécifiques à chaque format
                (ex: index, sheet_name, orient...).

        Returns:
            bool: True si l'écriture s'est déroulée avec succès.

        Raises:
            KidasWriteError: Si l'écriture échoue.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> dict:
        """Retourne un dictionnaire de métadonnées décrivant la source.

        Les métadonnées varient selon le type de source, mais incluent
        généralement : le chemin, le type, le nombre de lignes et colonnes,
        la taille du fichier et l'encodage détecté.

        Returns:
            dict: Dictionnaire contenant les métadonnées de la source.
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Vérifie que la source de données est accessible et lisible.

        Pour les fichiers locaux, vérifie que le fichier existe et est
        lisible. Pour les APIs, vérifie que l'endpoint répond correctement.

        Returns:
            bool: True si la source est accessible, False sinon.
        """
        pass

    def _update_last_read(self) -> None:
        """Met à jour l'horodatage de la dernière lecture réussie.

        Cette méthode utilitaire est appelée par les sous-classes après
        chaque appel réussi à read().
        """
        # Enregistrement de l'heure de la lecture
        self.last_read = datetime.now()
        logger.debug(
            "Source '%s' lue avec succès à %s.",
            self.source_path,
            self.last_read.isoformat(),
        )

    def __repr__(self) -> str:
        """Retourne une représentation lisible de la source de données.

        Returns:
            str: Représentation de l'objet sous forme de chaîne.
        """
        return (
            f"{self.__class__.__name__}("
            f"source_path='{self.source_path}', "
            f"source_type='{self.source_type}', "
            f"encoding='{self.encoding}')"
        )
