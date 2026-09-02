# -*- coding: utf-8 -*-
"""
Module implémentant NetCDFSource pour la lecture de fichiers NetCDF.

Ce module gère les fichiers NetCDF (Network Common Data Form) utilisés
en agrométéorologie : données CHIRPS (précipitations), TAMSAT (Afrique),
GFS (prévisions globales). Il supporte l'extraction spatiale pour le Bénin
et la conversion vers pandas DataFrame pour les analyses tabulaires.

L'ancien nom NetCDFDataSource est conservé comme alias obsolète : il continue
de fonctionner mais émet un DeprecationWarning pour guider la migration.
"""

import logging
import os
import warnings
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr

# Import de la classe de base et des exceptions personnalisées
from kadi.kidas.sources.base import Source
from kadi.exceptions import ReadError, WriteError, ConnectError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Bounding box par défaut pour le Bénin
_BENIN_LAT_BOUNDS: Tuple[float, float] = (2.5, 12.5)
_BENIN_LON_BOUNDS: Tuple[float, float] = (-1.5, 4.0)


class NetCDFSource(Source):
    """Source de données pour les fichiers NetCDF agrométéorologiques.

    Gère la lecture de fichiers NetCDF avec extraction de sous-ensembles
    spatiaux et temporels, en utilisant xarray comme moteur de lecture.
    Supporte les grands fichiers via le chunking Dask.

    Attributs:
        path (str): Chemin absolu ou relatif vers le fichier NetCDF.
        use_dask (bool): Si True, utilise Dask pour le chargement paresseux
            (lazy loading) des grands fichiers.
        _ds (xr.Dataset | None): Dataset xarray chargé en cache.
        _da (xr.DataArray | None): DataArray extrait lors du dernier read().

    Exemple:
        >>> source = NetCDFSource('chirps_benin_2024.nc')
        >>> da = source.read(lat_bounds=(2.5, 12.5), lon_bounds=(-1.5, 4.0))
        >>> df = source.to_df()
        >>> print(source.dims())
        {'lat': 240, 'lon': 360, 'time': 365}
    """

    def __init__(
        self,
        path: str,
        use_dask: bool = False,
    ) -> None:
        """Initialise la source NetCDF avec support optionnel de Dask.

        Args:
            path (str): Chemin vers le fichier NetCDF (.nc) à lire.
            use_dask (bool): Si True, utilise le chunking automatique de Dask
                pour les fichiers volumineux (> 500 Mo). Par défaut False.
        """
        # Initialisation de la classe parente avec le type 'netcdf'
        super().__init__(
            path=path,
            kind="netcdf",
            encoding="utf-8",
        )

        # Activation du chargement paresseux via Dask
        self.use_dask: bool = use_dask

        # Cache interne du dataset xarray (chargé à la première lecture)
        self._ds: Optional[xr.Dataset] = None

        # Cache du DataArray extrait lors du dernier appel à read()
        self._da: Optional[xr.DataArray] = None

    def _open(self) -> xr.Dataset:
        """Charge le dataset xarray depuis le fichier NetCDF.

        Utilise le cache interne pour éviter de recharger le fichier
        à chaque appel. En mode Dask, le chargement est paresseux.

        Returns:
            xr.Dataset: Le dataset xarray chargé.

        Raises:
            ConnectError: Si le fichier n'est pas accessible.
            ReadError: Si le fichier NetCDF est corrompu.
        """
        # Retour du cache si déjà chargé
        if self._ds is not None:
            return self._ds

        if not self.ping():
            raise ConnectError(
                f"Fichier NetCDF introuvable : '{self.path}'"
            )

        try:
            # Arguments de chargement selon l'activation de Dask
            kwargs_chargement = {"chunks": "auto"} if self.use_dask else {}

            # Chargement du dataset xarray
            self._ds = xr.open_dataset(
                self.path, **kwargs_chargement
            )
            logger.debug(
                "Dataset NetCDF '%s' chargé (Dask=%s).",
                self.path,
                self.use_dask,
            )
            return self._ds

        except Exception as erreur:
            raise ReadError(
                f"Impossible de lire le fichier NetCDF '{self.path}' : {erreur}"
            ) from erreur

    def dims(self) -> Dict[str, int]:
        """Retourne les dimensions du dataset NetCDF.

        Returns:
            dict: Dictionnaire nom -> taille pour chaque dimension.
                Exemple : {'lat': 240, 'lon': 360, 'time': 1461}.

        Raises:
            ConnectError: Si le fichier n'est pas accessible.
            ReadError: Si la lecture du dataset échoue.
        """
        # Chargement du dataset (depuis le cache ou le disque)
        ds = self._open()

        # Extraction des dimensions du dataset via ds.sizes (compatible xarray futur)
        dimensions = {dim: int(taille) for dim, taille in ds.sizes.items()}
        logger.debug(
            "Dimensions du fichier '%s' : %s.", self.path, dimensions
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
            ConnectError: Si le fichier n'est pas accessible.
            ReadError: Si l'extraction du sous-ensemble échoue.
        """
        # Chargement du dataset
        ds = self._open()

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
                self.path,
                lat_min,
                lat_max,
                lon_min,
                lon_max,
            )

            # Mise en cache du DataArray et mise à jour de l'horodatage
            self._da = da
            self._touch()
            return da

        except Exception as erreur:
            raise ReadError(
                f"Erreur lors de l'extraction du sous-ensemble NetCDF : {erreur}"
            ) from erreur

    def to_df(self) -> pd.DataFrame:
        """Convertit le dernier DataArray extrait en pandas DataFrame.

        Utilise le DataArray issu du dernier appel à read(). Si read() n'a
        pas encore été appelé, lit l'ensemble du dataset avec la bbox Bénin.

        Returns:
            pd.DataFrame: Les données NetCDF sous forme tabulaire avec
                les dimensions comme colonnes (lat, lon, time, valeur).

        Raises:
            ReadError: Si la conversion échoue.
        """
        # Si read() n'a pas été appelé, effectuer une lecture par défaut
        if self._da is None:
            self.read()

        try:
            # Conversion du DataArray en DataFrame pandas
            df = self._da.to_dataframe().reset_index()
            logger.debug(
                "DataArray NetCDF converti en DataFrame : %d lignes, %d colonnes.",
                len(df),
                len(df.columns),
            )
            return df

        except Exception as erreur:
            raise ReadError(
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
            WriteError: Si l'écriture échoue.
        """
        try:
            # Conversion du DataFrame en Dataset xarray puis sauvegarde
            ds_sortie = xr.Dataset.from_dataframe(data)
            ds_sortie.to_netcdf(self.path)
            logger.info(
                "Données écrites vers le fichier NetCDF '%s'.", self.path
            )
            return True

        except Exception as erreur:
            raise WriteError(
                f"Impossible d'écrire vers '{self.path}' : {erreur}"
            ) from erreur

    def info(self) -> dict:
        """Retourne les métadonnées descriptives du fichier NetCDF.

        Returns:
            dict: Dictionnaire contenant les clés suivantes :
                - 'path' (str) : chemin du fichier.
                - 'kind' (str) : 'netcdf'.
                - 'dimensions' (dict) : nom -> taille de chaque dimension.
                - 'variables' (list) : liste des variables de données.
                - 'use_dask' (bool) : mode de chargement.
                - 'size_kb' (float) : taille du fichier en kilo-octets.
                - 'last_read' (str | None) : horodatage de la dernière lecture.
        """
        # Tentative de chargement des informations structurelles
        try:
            ds = self._open()
            dimensions = self.dims()
            variables = list(ds.data_vars)
        except (ReadError, ConnectError):
            dimensions = {}
            variables = []

        # Calcul de la taille du fichier
        taille_kb = os.path.getsize(self.path) / 1024 if os.path.isfile(
            self.path
        ) else 0.0

        return {
            "path": self.path,
            "kind": "netcdf",
            "dimensions": dimensions,
            "variables": variables,
            "use_dask": self.use_dask,
            "size_kb": round(taille_kb, 2),
            "last_read": (
                self.last_read.isoformat() if self.last_read else None
            ),
        }

    def ping(self) -> bool:
        """Vérifie que le fichier NetCDF existe et est lisible.

        Returns:
            bool: True si le fichier est accessible en lecture, False sinon.
        """
        # Vérification de l'existence et de la lisibilité du fichier
        est_accessible = os.path.isfile(self.path) and os.access(
            self.path, os.R_OK
        )

        if not est_accessible:
            logger.warning(
                "Le fichier NetCDF '%s' n'existe pas ou n'est pas lisible.",
                self.path,
            )

        return est_accessible


# Table des anciens noms -> (nouveau nom, classe cible)
# Utilisée par __getattr__ pour intercepter les imports de l'ancien nom.
_DEPRECATED = {
    "NetCDFDataSource": ("NetCDFSource", NetCDFSource),
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
            f"kadi.kidas.sources.netcdf_source.{name} est obsolète et sera supprimé "
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
