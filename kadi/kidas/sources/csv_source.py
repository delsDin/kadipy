# -*- coding: utf-8 -*-
"""
Module implémentant CSVDataSource pour la lecture/écriture de fichiers CSV.

Ce module gère les fichiers CSV bancals rencontrés en terrain AgriTech :
encodages mixtes (UTF-8, Latin-1), délimiteurs variables (virgule, point-virgule,
tabulation), décimales françaises (virgule) vs anglaises (point).
"""

import csv
import logging
import os
from typing import Optional

import chardet
import pandas as pd

# Import de la classe de base et des exceptions personnalisées
from kadi.kidas.sources.base import DataSource
from kadi.exceptions import KidasReadError, KidasWriteError, KidasConnectionError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Nombre d'octets lu pour la détection de l'encodage
_CHARDET_SAMPLE_SIZE = 10_000

# Délimiteurs testés lors de l'auto-détection
_CANDIDATE_DELIMITERS = [",", ";", "\t", "|"]


class CSVDataSource(DataSource):
    """Source de données pour les fichiers CSV agricoles.

    Gère la lecture robuste de fichiers CSV avec détection automatique
    de l'encodage, du délimiteur et du séparateur décimal. Conçue pour
    traiter les exports de capteurs IoT, de coopératives et des bases
    de données nationales (INSAE, MAEP).

    Attributs:
        file_path (str): Chemin absolu ou relatif vers le fichier CSV.
        delimiter (str): Délimiteur de colonnes (auto-détecté si 'auto').
        decimal (str): Séparateur décimal (auto-détecté si 'auto').
        _detected_delimiter (str | None): Délimiteur détecté en cache.
        _detected_encoding (str | None): Encodage détecté en cache.

    Exemple:
        >>> source = CSVDataSource('recoltes_2024.csv')
        >>> df = source.read()
        >>> print(source.get_metadata())
    """

    def __init__(
        self,
        file_path: str,
        encoding: str = "auto",
        delimiter: str = "auto",
        decimal: str = "auto",
    ) -> None:
        """Initialise la source CSV avec détection automatique des paramètres.

        Args:
            file_path (str): Chemin vers le fichier CSV à lire.
            encoding (str): Encodage du fichier. 'auto' pour la détection
                automatique via chardet. Par défaut 'auto'.
            delimiter (str): Délimiteur de colonnes. 'auto' pour l'auto-
                détection. Par défaut 'auto'.
            decimal (str): Séparateur décimal. 'auto' pour l'inférence
                (détecte les fichiers français avec ','). Par défaut 'auto'.
        """
        # Initialisation de la classe parente avec le type 'csv'
        super().__init__(
            source_path=file_path,
            source_type="csv",
            encoding=encoding,
        )

        # Chemin vers le fichier CSV
        self.file_path: str = file_path

        # Paramètres de lecture (peuvent être 'auto' avant détection)
        self.delimiter: str = delimiter
        self.decimal: str = decimal

        # Cache interne pour éviter de re-détecter à chaque lecture
        self._detected_delimiter: Optional[str] = None
        self._detected_encoding: Optional[str] = None

    def detect_encoding(self) -> str:
        """Détecte automatiquement l'encodage du fichier CSV via chardet.

        Lit un échantillon du fichier (10 000 octets) pour minimiser
        le temps de détection tout en gardant une bonne précision.
        Retourne 'utf-8' comme encodage par défaut si la détection échoue.

        Returns:
            str: L'encodage détecté (ex: 'utf-8', 'ISO-8859-1').

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
        """
        # Vérification de l'existence du fichier avant de lire
        if not os.path.isfile(self.file_path):
            raise KidasConnectionError(
                f"Fichier CSV introuvable : '{self.file_path}'"
            )

        try:
            # Lecture d'un échantillon d'octets bruts pour chardet
            with open(self.file_path, "rb") as fichier:
                echantillon = fichier.read(_CHARDET_SAMPLE_SIZE)

            # Analyse de l'encodage via chardet
            resultat = chardet.detect(echantillon)
            encodage = resultat.get("encoding") or "utf-8"

            logger.debug(
                "Encodage détecté pour '%s' : %s (confiance : %.0f%%).",
                self.file_path,
                encodage,
                (resultat.get("confidence") or 0) * 100,
            )

            # Mise en cache du résultat
            self._detected_encoding = encodage
            return encodage

        except OSError as erreur:
            raise KidasConnectionError(
                f"Impossible de lire le fichier CSV '{self.file_path}' : {erreur}"
            ) from erreur

    def detect_delimiter(self) -> str:
        """Détecte automatiquement le délimiteur de colonnes du fichier CSV.

        Utilise csv.Sniffer sur les premières lignes du fichier. En cas
        d'échec, teste successivement les délimiteurs candidats (, ; \\t |)
        et choisit celui produisant le plus de colonnes.

        Returns:
            str: Le délimiteur détecté (ex: ',', ';', '\\t', '|').

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
        """
        # Détermination de l'encodage pour ouvrir le fichier correctement
        encodage = self._detected_encoding or self.detect_encoding()

        try:
            # Tentative 1 : utilisation du Sniffer de la bibliothèque csv
            with open(self.file_path, encoding=encodage, errors="replace") as f:
                echantillon = f.read(2048)

            try:
                dialect = csv.Sniffer().sniff(echantillon, _CANDIDATE_DELIMITERS)
                delimiteur = dialect.delimiter
                logger.debug(
                    "Délimiteur détecté via Sniffer pour '%s' : '%s'.",
                    self.file_path,
                    delimiteur,
                )
            except csv.Error:
                # Tentative 2 : compter les occurrences de chaque délimiteur
                premiere_ligne = echantillon.splitlines()[0] if echantillon else ""
                delimiteur = max(
                    _CANDIDATE_DELIMITERS,
                    key=lambda d: premiere_ligne.count(d),
                )
                logger.debug(
                    "Délimiteur détecté par comptage pour '%s' : '%s'.",
                    self.file_path,
                    delimiteur,
                )

            # Mise en cache du résultat
            self._detected_delimiter = delimiteur
            return delimiteur

        except OSError as erreur:
            raise KidasConnectionError(
                f"Impossible d'accéder au fichier '{self.file_path}' : {erreur}"
            ) from erreur

    def read(
        self,
        nrows: Optional[int] = None,
        skip_rows: Optional[int] = None,
    ) -> pd.DataFrame:
        """Lit le fichier CSV et retourne son contenu sous forme de DataFrame.

        Effectue la détection automatique de l'encodage et du délimiteur
        si nécessaire. Tente plusieurs encodages en fallback si la lecture
        principale échoue.

        Args:
            nrows (int | None): Nombre maximum de lignes à lire. None pour
                lire toutes les lignes. Par défaut None.
            skip_rows (int | None): Nombre de lignes à ignorer en début
                de fichier (hors en-tête). Par défaut None.

        Returns:
            pd.DataFrame: Les données du fichier CSV.

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
            KidasReadError: Si la lecture échoue malgré les fallbacks.
        """
        # Vérification préalable de l'accessibilité
        if not self.validate_connection():
            raise KidasConnectionError(
                f"Le fichier CSV '{self.file_path}' n'est pas accessible."
            )

        # Détermination de l'encodage (détection si 'auto')
        encodage = (
            self._detected_encoding or self.detect_encoding()
            if self.encoding == "auto"
            else self.encoding
        )

        # Détermination du délimiteur (détection si 'auto')
        delimiteur = (
            self._detected_delimiter or self.detect_delimiter()
            if self.delimiter == "auto"
            else self.delimiter
        )

        # Détermination du séparateur décimal
        # Heuristique : si le délimiteur est ';', le décimal est souvent ','
        if self.decimal == "auto":
            separateur_decimal = "," if delimiteur == ";" else "."
        else:
            separateur_decimal = self.decimal

        # Séquence d'encodages à essayer en cas d'échec
        encodages_fallback = [encodage, "utf-8", "latin-1", "cp1252"]
        # Déduplication tout en conservant l'ordre
        encodages_a_tester = list(dict.fromkeys(encodages_fallback))

        dernier_erreur = None

        # Tentative de lecture avec chaque encodage dans la liste
        for enc in encodages_a_tester:
            try:
                df = pd.read_csv(
                    self.file_path,
                    sep=delimiteur,
                    encoding=enc,
                    decimal=separateur_decimal,
                    nrows=nrows,
                    skiprows=skip_rows,
                    on_bad_lines="warn",
                )
                logger.info(
                    "Fichier CSV '%s' lu avec succès : %d lignes, %d colonnes "
                    "(encodage: %s, délimiteur: '%s').",
                    self.file_path,
                    len(df),
                    len(df.columns),
                    enc,
                    delimiteur,
                )
                # Mise à jour de l'horodatage de lecture
                self._update_last_read()
                return df

            except UnicodeDecodeError as erreur:
                # Échec d'encodage : on essaie le suivant
                logger.debug(
                    "Échec de lecture avec encodage '%s' pour '%s' : %s",
                    enc,
                    self.file_path,
                    erreur,
                )
                dernier_erreur = erreur
                continue

            except Exception as erreur:
                raise KidasReadError(
                    f"Erreur inattendue lors de la lecture de "
                    f"'{self.file_path}' : {erreur}"
                ) from erreur

        # Si tous les encodages ont échoué
        raise KidasReadError(
            f"Impossible de lire '{self.file_path}' avec les encodages "
            f"testés : {encodages_a_tester}. Dernière erreur : {dernier_erreur}"
        )

    def write(self, data: pd.DataFrame, index: bool = False) -> bool:
        """Écrit un DataFrame vers le fichier CSV de la source.

        Utilise le délimiteur détecté ou configuré. Si l'encodage est
        'auto', écrit en UTF-8 par défaut.

        Args:
            data (pd.DataFrame): Le DataFrame à écrire dans le fichier CSV.
            index (bool): Si True, inclut l'index du DataFrame dans le
                fichier CSV. Par défaut False.

        Returns:
            bool: True si l'écriture s'est déroulée avec succès.

        Raises:
            KidasWriteError: Si l'écriture vers le fichier échoue.
        """
        # Détermination de l'encodage de sortie
        encodage_sortie = (
            "utf-8" if self.encoding == "auto" else self.encoding
        )

        # Détermination du délimiteur de sortie
        delimiteur_sortie = (
            self._detected_delimiter or ","
            if self.delimiter == "auto"
            else self.delimiter
        )

        try:
            # Écriture du DataFrame au format CSV
            data.to_csv(
                self.file_path,
                sep=delimiteur_sortie,
                encoding=encodage_sortie,
                index=index,
            )
            logger.info(
                "DataFrame écrit avec succès vers '%s' (%d lignes).",
                self.file_path,
                len(data),
            )
            return True

        except OSError as erreur:
            raise KidasWriteError(
                f"Impossible d'écrire vers '{self.file_path}' : {erreur}"
            ) from erreur

    def get_metadata(self) -> dict:
        """Retourne les métadonnées descriptives du fichier CSV.

        Effectue une lecture légère du fichier pour en extraire les
        statistiques sans charger toutes les données en mémoire.

        Returns:
            dict: Dictionnaire contenant les clés suivantes :
                - 'source_path' (str) : chemin du fichier.
                - 'source_type' (str) : 'csv'.
                - 'encoding' (str) : encodage détecté ou configuré.
                - 'delimiter' (str) : délimiteur détecté ou configuré.
                - 'decimal' (str) : séparateur décimal utilisé.
                - 'rows' (int) : nombre de lignes de données.
                - 'cols' (int) : nombre de colonnes.
                - 'size_kb' (float) : taille du fichier en kilo-octets.
                - 'last_read' (str | None) : horodatage de la dernière lecture.
        """
        # Détection de l'encodage et du délimiteur si nécessaire
        encodage = (
            self._detected_encoding or self.detect_encoding()
            if self.encoding == "auto"
            else self.encoding
        )
        delimiteur = (
            self._detected_delimiter or self.detect_delimiter()
            if self.delimiter == "auto"
            else self.delimiter
        )

        # Lecture rapide pour obtenir le nombre de lignes et colonnes
        try:
            df_apercu = pd.read_csv(
                self.file_path,
                sep=delimiteur,
                encoding=encodage,
                nrows=0,
            )
            nb_colonnes = len(df_apercu.columns)

            # Comptage des lignes sans charger tout le fichier en mémoire
            with open(self.file_path, encoding=encodage, errors="replace") as f:
                nb_lignes = sum(1 for _ in f) - 1  # -1 pour l'en-tête

        except Exception:
            nb_lignes = -1
            nb_colonnes = -1

        # Calcul de la taille du fichier
        taille_kb = os.path.getsize(self.file_path) / 1024 if os.path.isfile(
            self.file_path
        ) else 0.0

        return {
            "source_path": self.file_path,
            "source_type": "csv",
            "encoding": encodage,
            "delimiter": delimiteur,
            "decimal": self.decimal if self.decimal != "auto" else "inféré",
            "rows": nb_lignes,
            "cols": nb_colonnes,
            "size_kb": round(taille_kb, 2),
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def validate_connection(self) -> bool:
        """Vérifie que le fichier CSV existe et est lisible.

        Returns:
            bool: True si le fichier est accessible en lecture, False sinon.
        """
        # Vérification de l'existence et de la lisibilité du fichier
        est_accessible = os.path.isfile(self.file_path) and os.access(
            self.file_path, os.R_OK
        )

        if not est_accessible:
            logger.warning(
                "Le fichier CSV '%s' n'existe pas ou n'est pas lisible.",
                self.file_path,
            )

        return est_accessible
