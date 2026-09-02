# -*- coding: utf-8 -*-
"""
Module implémentant JSONSource pour la lecture/écriture de fichiers JSON.

Ce module gère les fichiers JSON plats ou imbriqués tels qu'ils sont retournés
par les APIs agricoles (FAO, WFP VAM, MAEP). La fonctionnalité principale est
l'aplatissement automatique des structures imbriquées via flatten().

L'ancien nom JSONDataSource est conservé comme alias obsolète : il continue
de fonctionner mais émet un DeprecationWarning pour guider la migration.
"""

import json
import logging
import os
import warnings
from typing import Any, Dict, Optional, Union

import pandas as pd

# Import de la classe de base et des exceptions personnalisées
from kadi.kidas.sources.base import Source
from kadi.exceptions import ReadError, WriteError, ConnectError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)


class JSONSource(Source):
    """Source de données pour les fichiers JSON agricoles.

    Gère la lecture de fichiers JSON plats ou fortement imbriqués.
    L'aplatissement automatique des clés imbriquées utilise la notation
    pointée (ex: {'location': {'lat': 9.3}} -> {'location.lat': 9.3}).

    Attributs:
        path (str | None): Chemin absolu ou relatif vers le fichier JSON.
            '<dict_en_memoire>' si la source est un dictionnaire Python.
        _raw (dict | None): Dictionnaire Python fourni directement
            comme source au lieu d'un fichier.

    Exemple:
        >>> # Depuis un fichier
        >>> source = JSONSource('donnees_fao.json')
        >>> df = source.read(flatten=True)
        >>>
        >>> # Depuis un dictionnaire Python
        >>> data = {'location': {'lat': 9.3, 'lon': 2.4}, 'crop': 'maize'}
        >>> source = JSONSource(data)
        >>> df = source.read()
    """

    def __init__(
        self,
        file_path_or_dict: Union[str, dict],
    ) -> None:
        """Initialise la source JSON depuis un fichier ou un dictionnaire.

        Args:
            file_path_or_dict (str | dict): Chemin vers le fichier JSON
                ou un dictionnaire Python à utiliser directement comme source.
        """
        # Détection du type de source : fichier ou dictionnaire en mémoire
        if isinstance(file_path_or_dict, dict):
            # Source : dictionnaire Python en mémoire
            self._raw: Optional[dict] = file_path_or_dict
            chemin = "<dict_en_memoire>"
        else:
            # Source : fichier JSON sur le disque
            self._raw = None
            chemin = file_path_or_dict

        # Initialisation de la classe parente avec le type 'json'
        super().__init__(
            path=chemin,
            kind="json",
            encoding="utf-8",
        )

        # Chemin du fichier (None si source est un dict)
        self._file: Optional[str] = (
            None if isinstance(file_path_or_dict, dict) else file_path_or_dict
        )

    def flatten(self, obj: Dict[str, Any], sep: str = ".") -> dict:
        """Aplatit récursivement un objet JSON imbriqué.

        Transforme les clés imbriquées en clés à notation pointée.
        Exemple : {'location': {'lat': 9.3}} -> {'location.lat': 9.3}.

        Args:
            obj (dict): L'objet JSON à aplatir (peut contenir des dicts
                et des listes imbriqués).
            sep (str): Caractère séparateur entre les niveaux de clés.
                Par défaut '.'.

        Returns:
            dict: Dictionnaire aplati avec des clés à notation pointée.
        """
        # Dictionnaire de sortie aplati
        resultat: dict = {}

        def _aplatir(o: Any, prefixe: str = "") -> None:
            """Fonction récursive interne réalisant l'aplatissement.

            Args:
                o (Any): L'objet courant à aplatir.
                prefixe (str): Le préfixe des clés parentes accumulées.
            """
            if isinstance(o, dict):
                # Récursion sur chaque clé du dictionnaire
                for cle, valeur in o.items():
                    # Construction de la clé complète avec préfixe
                    cle_complete = f"{prefixe}{sep}{cle}" if prefixe else cle
                    _aplatir(valeur, cle_complete)
            elif isinstance(o, list):
                # Indexation des éléments de liste avec leur position
                for index, valeur in enumerate(o):
                    cle_complete = f"{prefixe}{sep}{index}" if prefixe else str(index)
                    _aplatir(valeur, cle_complete)
            else:
                # Valeur scalaire : on l'enregistre dans le résultat
                resultat[prefixe] = o

        # Lancement de la récursion à la racine
        _aplatir(obj)
        return resultat

    def _load_raw(self) -> Any:
        """Charge les données JSON brutes depuis le fichier ou le dict source.

        Returns:
            Any: Les données JSON brutes (dict, list, etc.).

        Raises:
            ConnectError: Si le fichier n'est pas accessible.
            ReadError: Si le contenu JSON est invalide.
        """
        if self._raw is not None:
            # Source est un dictionnaire Python : retour direct
            return self._raw

        # Vérification de l'existence du fichier
        if not self.ping():
            raise ConnectError(
                f"Fichier JSON introuvable : '{self._file}'"
            )

        try:
            # Lecture et parse du fichier JSON
            with open(self._file, encoding="utf-8", errors="replace") as f:
                donnees = json.load(f)
            return donnees

        except json.JSONDecodeError as erreur:
            raise ReadError(
                f"Contenu JSON invalide dans '{self._file}' : {erreur}"
            ) from erreur
        except OSError as erreur:
            raise ConnectError(
                f"Impossible de lire '{self._file}' : {erreur}"
            ) from erreur

    def read(self, flatten: bool = True) -> pd.DataFrame:
        """Lit les données JSON et les retourne sous forme de DataFrame.

        Si flatten=True, les structures imbriquées sont automatiquement
        aplaties avant la conversion en DataFrame.

        Args:
            flatten (bool): Si True, applique self.flatten() sur chaque
                enregistrement avant normalisation. Par défaut True.

        Returns:
            pd.DataFrame: Les données JSON sous forme tabulaire.

        Raises:
            ConnectError: Si la source n'est pas accessible.
            ReadError: Si la conversion en DataFrame échoue.
        """
        # Chargement des données JSON brutes
        donnees_brutes = self._load_raw()

        # Normalisation en liste d'enregistrements si nécessaire
        if isinstance(donnees_brutes, dict):
            # Un seul enregistrement dict -> liste de un
            liste_enregistrements = [donnees_brutes]
        elif isinstance(donnees_brutes, list):
            # Déjà une liste d'enregistrements
            liste_enregistrements = donnees_brutes
        else:
            raise ReadError(
                f"Format JSON non supporté : attendu dict ou list, "
                f"reçu {type(donnees_brutes).__name__}."
            )

        try:
            if flatten:
                # Aplatissement de chaque enregistrement avant normalisation
                enregistrements_aplatis = [
                    self.flatten(enr) if isinstance(enr, dict) else enr
                    for enr in liste_enregistrements
                ]
                df = pd.DataFrame(enregistrements_aplatis)
            else:
                # Normalisation JSON directe sans aplatissement
                df = pd.json_normalize(liste_enregistrements)

            logger.info(
                "Source JSON '%s' lue : %d lignes, %d colonnes (flatten=%s).",
                self.path,
                len(df),
                len(df.columns),
                flatten,
            )

            # Mise à jour de l'horodatage de lecture
            self._touch()
            return df

        except Exception as erreur:
            raise ReadError(
                f"Impossible de convertir le JSON en DataFrame : {erreur}"
            ) from erreur

    def write(
        self,
        data: pd.DataFrame,
        orient: str = "records",
    ) -> bool:
        """Écrit un DataFrame vers le fichier JSON de la source.

        Args:
            data (pd.DataFrame): Les données à écrire au format JSON.
            orient (str): Orientation de la sérialisation JSON. Valeurs
                possibles : 'records', 'index', 'columns', 'values'.
                Par défaut 'records'.

        Returns:
            bool: True si l'écriture s'est déroulée avec succès.

        Raises:
            WriteError: Si la source est un dict en mémoire (pas de fichier)
                ou si l'écriture échoue.
        """
        # Vérification qu'on a bien un fichier de destination
        if self._file is None:
            raise WriteError(
                "Impossible d'écrire : la source JSON est un dictionnaire "
                "en mémoire, aucun fichier de destination n'est défini."
            )

        try:
            # Sérialisation du DataFrame en JSON
            data.to_json(
                self._file,
                orient=orient,
                force_ascii=False,
                indent=2,
            )
            logger.info(
                "DataFrame écrit avec succès vers '%s' (%d lignes, orient='%s').",
                self._file,
                len(data),
                orient,
            )
            return True

        except Exception as erreur:
            raise WriteError(
                f"Impossible d'écrire vers '{self._file}' : {erreur}"
            ) from erreur

    def info(self) -> dict:
        """Retourne les métadonnées descriptives de la source JSON.

        Returns:
            dict: Dictionnaire contenant les clés suivantes :
                - 'path' (str) : chemin du fichier ou '<dict_en_memoire>'.
                - 'kind' (str) : 'json'.
                - 'is_file' (bool) : True si la source est un fichier.
                - 'size_kb' (float) : taille du fichier (0 si dict en mémoire).
                - 'last_read' (str | None) : horodatage de la dernière lecture.
        """
        # Calcul de la taille du fichier si applicable
        taille_kb = 0.0
        if self._file and os.path.isfile(self._file):
            taille_kb = os.path.getsize(self._file) / 1024

        return {
            "path": self.path,
            "kind": "json",
            "is_file": self._file is not None,
            "size_kb": round(taille_kb, 2),
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def ping(self) -> bool:
        """Vérifie que la source JSON est accessible.

        Pour une source fichier, vérifie l'existence du fichier.
        Pour une source dict, retourne toujours True.

        Returns:
            bool: True si la source est accessible.
        """
        # Un dictionnaire en mémoire est toujours accessible
        if self._raw is not None:
            return True

        # Vérification de l'existence et de la lisibilité du fichier
        est_accessible = self._file is not None and os.path.isfile(
            self._file
        ) and os.access(self._file, os.R_OK)

        if not est_accessible:
            logger.warning(
                "Le fichier JSON '%s' n'existe pas ou n'est pas lisible.",
                self._file,
            )

        return est_accessible



# Table des anciens noms -> (nouveau nom, classe cible)
# Utilisée par __getattr__ pour intercepter les imports de l'ancien nom.
_DEPRECATED = {
    "JSONDataSource": ("JSONSource", JSONSource),
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
            f"kadi.kidas.sources.json_source.{name} est obsolète et sera supprimé "
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
