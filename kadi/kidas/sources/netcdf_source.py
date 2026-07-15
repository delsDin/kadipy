# -*- coding: utf-8 -*-
"""
Module implémentant NetCDFDataSource pour la lecture de fichiers NetCDF.

Ce module gère les fichiers NetCDF (Network Common Data Form) utilisés
en agrométéorologie : données CHIRPS (précipitations), TAMSAT (Afrique),
GFS (prévisions globales). Il supporte l'extraction spatiale pour le Bénin
et la conversion vers pandas DataFrame pour les analyses tabulaires.
"""

import logging
import os
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr

# Import de la classe de base et des exceptions personnalisées
from kadi.kidas.sources.base import DataSource
from kadi.exceptions import KidasReadError, KidasWriteError, KidasConnectionError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Bounding box par défaut pour le Bénin
_BENIN_LAT_BOUNDS: Tuple[float, float] = (2.5, 12.5)
_BENIN_LON_BOUNDS: Tuple[float, float] = (-1.5, 4.0)


class NetCDFDataSource(DataSource):
    """Source de données pour les fichiers NetCDF agrométéorologiques.

    Gère la lecture de fichiers NetCDF avec extraction de sous-ensembles
    spatiaux et temporels, en utilisant xarray comme moteur de lecture.
    Supporte les grands fichiers via le chunking Dask.

    Attributs:
        file_path (str): Chemin absolu ou relatif vers le fichier NetCDF.
        use_dask (bool): Si True, utilise Dask pour le chargement paresseux
            (lazy loading) des grands fichiers.
        _dataset (xr.Dataset | None): Dataset xarray chargé en cache.

    Exemple:
        >>> source = NetCDFDataSource('chirps_benin_2024.nc')
        >>> da = source.read(lat_bounds=(2.5, 12.5), lon_bounds=(-1.5, 4.0))
        >>> df = source.to_dataframe()
        >>> print(source.get_dimensions())
        {'lat': 240, 'lon': 360, 'time': 365}
    """

    def __init__(
        self,
        file_path: str,
        use_dask: bool = False,
    ) -> None:
        """Initialise la source NetCDF avec support optionnel de Dask.

        Args:
            file_path (str): Chemin vers le fichier NetCDF (.nc) à lire.
            use_dask (bool): Si True, utilise le chunking automatique de Dask
                pour les fichiers volumineux (> 500 Mo). Par défaut False.
        """
        # Initialisation de la classe parente avec le type 'netcdf'
        super().__init__(
            source_path=file_path,
            source_type="netcdf",
            encoding="utf-8",
        )

        # Chemin vers le fichier NetCDF
        self.file_path: str = file_path

        # Activation du chargement paresseux via Dask
        self.use_dask: bool = use_dask

        # Cache interne du dataset xarray (chargé à la première lecture)
        self._dataset: Optional[xr.Dataset] = None

        # Cache du DataArray extrait lors du dernier appel à read()
        self._last_data_array: Optional[xr.DataArray] = None

    def _charger_dataset(self) -> xr.Dataset:
        """Charge le dataset xarray depuis le fichier NetCDF.

        Utilise le cache interne pour éviter de recharger le fichier
        à chaque appel. En mode Dask, le chargement est paresseux.

        Returns:
            xr.Dataset: Le dataset xarray chargé.

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
            KidasReadError: Si le fichier NetCDF est corrompu.
        """
        # Retour du cache si déjà chargé
        if self._dataset is not None:
            return self._dataset

        if not self.validate_connection():
            raise KidasConnectionError(
                f"Fichier NetCDF introuvable : '{self.file_path}'"
            )

        try:
            # Arguments de chargement selon l'activation de Dask
            kwargs_chargement = {"chunks": "auto"} if self.use_dask else {}

            # Chargement du dataset xarray
            self._dataset = xr.open_dataset(
                self.file_path, **kwargs_chargement
            )
            logger.debug(
                "Dataset NetCDF '%s' chargé (Dask=%s).",
                self.file_path,
                self.use_dask,
            )
            return self._dataset

        except Exception as erreur:
            raise KidasReadError(
                f"Impossible de lire le fichier NetCDF '{self.file_path}' : {erreur}"
            ) from erreur

    def get_dimensions(self) -> Dict[str, int]:
        """Retourne les dimensions du dataset NetCDF.

        Returns:
            dict: Dictionnaire nom → taille pour chaque dimension.
                Exemple : {'lat': 240, 'lon': 360, 'time': 1461}.

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
            KidasReadError: Si la lecture du dataset échoue.
        """
        # Chargement du dataset (depuis le cache ou le disque)
        ds = self._charger_dataset()

        # Extraction des dimensions du dataset via ds.sizes (compatible xarray futur)
        dimensions = {dim: int(taille) for dim, taille in ds.sizes.items()}
        logger.debug(
            "Dimensions du fichier '%s' : %s.", self.file_path, dimensions
        )
        return dimensions

    def read(
        self,
        lat_bounds: Optional[Tuple[float, float]] = None,
        lon_bounds: Optional[Tuple[float, float]] = None,
        time_bounds: Optional[Tuple[str, str]] = None,
    ) -> xr.DataArray:
        """Extrait un sous-ensemble spatial et temporel du fichier NetCDF.

        Par défaut, extrait les données couvrant le Bénin si aucune
        bounding box n'est spécifiée.

        Args:
            lat_bounds (tuple[float, float] | None): Intervalle de latitude
                (lat_min, lat_max). Par défaut la bbox du Bénin (2.5, 12.5).
            lon_bounds (tuple[float, float] | None): Intervalle de longitude
                (lon_min, lon_max). Par défaut la bbox du Bénin (-1.5, 4.0).
            time_bounds (tuple[str, str] | None): Intervalle temporel sous
                forme de chaînes ISO (ex: ('2024-01-01', '2024-12-31')).
                None pour toute la période disponible.

        Returns:
            xr.DataArray: Le sous-ensemble de données extrait.

        Raises:
            KidasConnectionError: Si le fichier n'est pas accessible.
            KidasReadError: Si l'extraction du sous-ensemble échoue.
        """
        # Chargement du dataset
        ds = self._charger_dataset()

        # Application des bounding boxes par défaut (Bénin) si non spécifiées
        lat_min, lat_max = lat_bounds if lat_bounds else _BENIN_LAT_BOUNDS
        lon_min, lon_max = lon_bounds if lon_bounds else _BENIN_LON_BOUNDS

        try:
            # Détection des noms de variables lat/lon dans le dataset
            # (peuvent s'appeler 'lat', 'latitude', 'y', etc.)
            noms_lat = [d for d in ds.sizes if "lat" in d.lower()]
            noms_lon = [d for d in ds.sizes if "lon" in d.lower() or d.lower() == "x"]

            nom_lat = noms_lat[0] if noms_lat else "lat"
            nom_lon = noms_lon[0] if noms_lon else "lon"

            # Sélection de la première variable de données si plusieurs existent
            variable_principale = list(ds.data_vars)[0]
            da = ds[variable_principale]

            # Extraction du sous-ensemble spatial
            da = da.sel(
                {
                    nom_lat: slice(lat_min, lat_max),
                    nom_lon: slice(lon_min, lon_max),
                }
            )

            # Extraction du sous-ensemble temporel si spécifié
            if time_bounds is not None:
                noms_time = [d for d in ds.sizes if "time" in d.lower()]
                nom_time = noms_time[0] if noms_time else "time"
                da = da.sel(
                    {nom_time: slice(time_bounds[0], time_bounds[1])}
                )

            logger.info(
                "Extraction NetCDF '%s' : lat[%.1f, %.1f], lon[%.1f, %.1f].",
                self.file_path,
                lat_min,
                lat_max,
                lon_min,
                lon_max,
            )

            # Mise en cache du DataArray et mise à jour de l'horodatage
            self._last_data_array = da
            self._update_last_read()
            return da

        except Exception as erreur:
            raise KidasReadError(
                f"Erreur lors de l'extraction du sous-ensemble NetCDF : {erreur}"
            ) from erreur

    def to_dataframe(self) -> pd.DataFrame:
        """Convertit le dernier DataArray extrait en pandas DataFrame.

        Utilise le DataArray issu du dernier appel à read(). Si read() n'a
        pas encore été appelé, lit l'ensemble du dataset avec la bbox Bénin.

        Returns:
            pd.DataFrame: Les données NetCDF sous forme tabulaire avec
                les dimensions comme colonnes (lat, lon, time, valeur).

        Raises:
            KidasReadError: Si la conversion échoue.
        """
        # Si read() n'a pas été appelé, effectuer une lecture par défaut
        if self._last_data_array is None:
            self.read()

        try:
            # Conversion du DataArray en DataFrame pandas
            df = self._last_data_array.to_dataframe().reset_index()
            logger.debug(
                "DataArray NetCDF converti en DataFrame : %d lignes, %d colonnes.",
                len(df),
                len(df.columns),
            )
            return df

        except Exception as erreur:
            raise KidasReadError(
                f"Impossible de convertir le DataArray en DataFrame : {erreur}"
            ) from erreur

    def write(self, data: pd.DataFrame) -> bool:
        """Écrit les données vers le fichier NetCDF de la source.

        Note: L'écriture de fichiers NetCDF complexes nécessite une structure
        précise (dimensions, coordonnées, attributs). Cette implémentation
        effectue une conversion basique du DataFrame en Dataset xarray.

        Args:
            data (pd.DataFrame): Les données à sauvegarder au format NetCDF.

        Returns:
            bool: True si l'écriture s'est déroulée avec succès.

        Raises:
            KidasWriteError: Si l'écriture échoue.
        """
        try:
            # Conversion du DataFrame en Dataset xarray puis sauvegarde
            ds_sortie = xr.Dataset.from_dataframe(data)
            ds_sortie.to_netcdf(self.file_path)
            logger.info(
                "Données écrites vers le fichier NetCDF '%s'.", self.file_path
            )
            return True

        except Exception as erreur:
            raise KidasWriteError(
                f"Impossible d'écrire vers '{self.file_path}' : {erreur}"
            ) from erreur

    def get_metadata(self) -> dict:
        """Retourne les métadonnées descriptives du fichier NetCDF.

        Returns:
            dict: Dictionnaire contenant les clés suivantes :
                - 'source_path' (str) : chemin du fichier.
                - 'source_type' (str) : 'netcdf'.
                - 'dimensions' (dict) : nom → taille de chaque dimension.
                - 'variables' (list) : liste des variables de données.
                - 'use_dask' (bool) : mode de chargement.
                - 'size_kb' (float) : taille du fichier en kilo-octets.
                - 'last_read' (str | None) : horodatage de la dernière lecture.
        """
        # Tentative de chargement des informations structurelles
        try:
            ds = self._charger_dataset()
            dimensions = self.get_dimensions()
            variables = list(ds.data_vars)
        except (KidasReadError, KidasConnectionError):
            dimensions = {}
            variables = []

        # Calcul de la taille du fichier
        taille_kb = os.path.getsize(self.file_path) / 1024 if os.path.isfile(
            self.file_path
        ) else 0.0

        return {
            "source_path": self.file_path,
            "source_type": "netcdf",
            "dimensions": dimensions,
            "variables": variables,
            "use_dask": self.use_dask,
            "size_kb": round(taille_kb, 2),
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def validate_connection(self) -> bool:
        """Vérifie que le fichier NetCDF existe et est lisible.

        Returns:
            bool: True si le fichier est accessible en lecture, False sinon.
        """
        # Vérification de l'existence et de la lisibilité du fichier
        est_accessible = os.path.isfile(self.file_path) and os.access(
            self.file_path, os.R_OK
        )

        if not est_accessible:
            logger.warning(
                "Le fichier NetCDF '%s' n'existe pas ou n'est pas lisible.",
                self.file_path,
            )

        return est_accessible
