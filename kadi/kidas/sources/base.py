# -*- coding: utf-8 -*-
"""
Module définissant la classe abstraite Source.

Source est l'interface commune à toutes les sources de données
du module kidas. Chaque format (CSV, Excel, JSON, NetCDF, API) doit
implémenter ce contrat pour garantir une utilisation uniforme dans
les pipelines d'acquisition de données agricoles.

L'ancien nom DataSource est conservé comme alias obsolète : il continue
de fonctionner mais émet un DeprecationWarning pour guider la migration.
"""

import logging
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import pandas as pd

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)


class Source(ABC):
    """Classe abstraite définissant l'interface commune à toutes les sources de données.

    Cette classe représente le contrat que chaque source concrète (CSV, Excel,
    JSON, NetCDF, API) doit respecter. Elle garantit que toutes les sources
    exposent les mêmes méthodes fondamentales : read(), write(), info()
    et ping().

    Attributs:
        path (str): Chemin local du fichier ou URI de la ressource.
        kind (str): Type de source parmi 'csv', 'excel', 'json',
            'netcdf' ou 'api'.
        encoding (str): Encodage des données (ex: 'utf-8', 'latin1').
            Peut être 'auto' pour une détection automatique.
        last_read (datetime | None): Horodatage de la dernière lecture
            réussie. None si la source n'a jamais été lue.
    """

    def __init__(
        self,
        path: str,
        kind: str,
        encoding: str = "utf-8",
    ) -> None:
        """Initialise les attributs communs à toutes les sources de données.

        Args:
            path (str): Chemin local du fichier ou URI de la ressource.
            kind (str): Type de la source (ex: 'csv', 'excel').
            encoding (str): Encodage des données. Par défaut 'utf-8'.
        """
        # Chemin ou URI de la source de données
        self.path: str = path

        # Type de source : 'csv', 'excel', 'json', 'netcdf' ou 'api'
        self.kind: str = kind

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
                (ex: n, sheet, lat_bounds...).

        Returns:
            pd.DataFrame: Les données lues depuis la source.

        Raises:
            ReadError: Si la lecture échoue (fichier corrompu,
                format invalide, etc.).
            ConnectError: Si la source n'est pas accessible.
        """
        pass

    @abstractmethod
    def write(self, data: pd.DataFrame, **kwargs) -> bool:
        """Écrit un DataFrame vers la source de données.

        Cette méthode doit être implémentée par chaque sous-classe concrète.

        Args:
            data (pd.DataFrame): Les données à écrire vers la source.
            **kwargs: Arguments optionnels spécifiques à chaque format
                (ex: index, sheet, orient...).

        Returns:
            bool: True si l'écriture s'est déroulée avec succès.

        Raises:
            WriteError: Si l'écriture échoue.
        """
        pass

    @abstractmethod
    def info(self) -> dict:
        """Retourne un dictionnaire de métadonnées décrivant la source.

        Les métadonnées varient selon le type de source, mais incluent
        généralement : le chemin, le type, le nombre de lignes et colonnes,
        la taille du fichier et l'encodage détecté.

        Returns:
            dict: Dictionnaire contenant les métadonnées de la source.
        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """Vérifie que la source de données est accessible et lisible.

        Pour les fichiers locaux, vérifie que le fichier existe et est
        lisible. Pour les APIs, vérifie que l'endpoint répond correctement.

        Returns:
            bool: True si la source est accessible, False sinon.
        """
        pass

    def _touch(self) -> None:
        """Met à jour l'horodatage de la dernière lecture réussie.

        Cette méthode utilitaire est appelée par les sous-classes après
        chaque appel réussi à read(). Le nom s'inspire de la commande
        UNIX touch, qui met à jour l'horodatage d'un fichier.
        """
        # Enregistrement de l'heure de la lecture
        self.last_read = datetime.now()
        logger.debug(
            "Source '%s' lue avec succès à %s.",
            self.path,
            self.last_read.isoformat(),
        )

    def __repr__(self) -> str:
        """Retourne une représentation lisible de la source de données.

        Returns:
            str: Représentation de l'objet sous forme de chaîne.
        """
        return (
            f"{self.__class__.__name__}("
            f"path='{self.path}', "
            f"kind='{self.kind}', "
            f"encoding='{self.encoding}')"
        )


# Table des anciens noms -> (nouveau nom, classe cible)
# Utilisée par __getattr__ pour intercepter les imports de l'ancien nom.
_DEPRECATED = {
    "DataSource": ("Source", Source),
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
            f"kadi.kidas.sources.base.{name} est obsolète et sera supprimé "
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
