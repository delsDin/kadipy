# -*- coding: utf-8 -*-
"""
Module implémentant DataPipeline, l'orchestrateur central du module kidas.

DataPipeline est le point d'entrée principal : il détecte automatiquement
le type de source depuis le chemin ou l'extension, chaîne les étapes de
nettoyage, validation et normalisation, puis met les résultats en cache.
Son API fluide (chainable) permet une utilisation concise et lisible.
"""

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

# Import des sources de données
from kadi.kidas.sources.csv_source import CSVDataSource
from kadi.kidas.sources.excel_source import ExcelDataSource
from kadi.kidas.sources.json_source import JSONDataSource
from kadi.kidas.sources.api_source import APIDataSource
from kadi.kidas.sources.base import DataSource

# Import conditionnel : xarray est requis pour NetCDF
try:
    from kadi.kidas.sources.netcdf_source import NetCDFDataSource
    _NETCDF_DISPONIBLE = True
except ImportError:
    NetCDFDataSource = None  # type: ignore[assignment]
    _NETCDF_DISPONIBLE = False

# Import des classes de traitement
from kadi.kidas.cleaner import DataCleaner
from kadi.kidas.validator import DataValidator
from kadi.kidas.normalizer import DataNormalizer
from kadi.kidas.cache import DataCache

# Import des exceptions personnalisées
from kadi.exceptions import PipelineError, ReadError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Extensions de fichiers reconnues par le pipeline
_EXT_CSV = {".csv", ".tsv", ".txt"}
_EXT_EXCEL = {".xls", ".xlsx", ".xlsm"}
_EXT_JSON = {".json"}
_EXT_NETCDF = {".nc", ".nc4", ".netcdf"}


class DataPipeline:
    """Orchestrateur du flux de traitement de données agricoles kidas.

    DataPipeline est le point d'entrée unique pour les utilisateurs de kidas.
    Il permet de définir de manière déclarative et chainable un flux complet :
    chargement → nettoyage → validation → normalisation → cache.

    L'auto-détection du type de source (CSV, Excel, JSON, NetCDF, API) est
    basée sur l'extension du fichier ou le préfixe 'http' de l'URL.

    Attributs:
        _source (DataSource | None): Source de données configurée.
        _df (pd.DataFrame | None): Données courantes dans le pipeline.
        _etapes (list): Liste ordonnée des étapes de traitement configurées.
        _rapports (dict): Rapports agrégés de toutes les étapes.
        _cache (DataCache): Instance du gestionnaire de cache kidas.

    Exemple:
        >>> pipeline = DataPipeline()
        >>> df, rapport = (
        ...     pipeline
        ...     .load_data('recolte_2024.xlsx')
        ...     .add_cleaning_step('remove_duplicates')
        ...     .add_cleaning_step('handle_missing_values', strategy='mean')
        ...     .add_validation_step({'culture': 'str', 'rendement_kg': 'float'})
        ...     .add_normalization_step({'culture': 'fao_standard'})
        ...     .execute(cache=True)
        ... )
        >>> print(rapport['nb_rows_out'])
        150
        >>> print(rapport['quality_score']['overall'])
        0.97
    """

    def __init__(self) -> None:
        """Initialise un pipeline vide prêt à recevoir des étapes de traitement."""
        # Source de données (sera configurée par load_data())
        self._source: Optional[DataSource] = None

        # DataFrame courant (None jusqu'à l'appel de execute())
        self._df: Optional[pd.DataFrame] = None

        # Nombre de lignes brutes avant toute transformation
        self._lignes_avant: int = 0

        # Liste ordonnée des étapes : {'type', 'nom', 'params'}
        self._etapes: List[Dict[str, Any]] = []

        # Rapports agrégés internes des étapes de traitement
        self._rapports: Dict[str, Any] = {
            "source": None,
            "nettoyage": None,
            "validation": None,
            "normalisation": None,
            "cache_utilise": False,
        }

        # Instance du cache kidas
        self._cache: DataCache = DataCache()

    @staticmethod
    def _detecter_type_source(source: str) -> str:
        """Détecte le type de source de données à partir du chemin ou de l'URL.

        Args:
            source (str): Chemin vers le fichier ou URL de l'API.

        Returns:
            str: Type détecté parmi 'csv', 'excel', 'json', 'netcdf', 'api'.

        Raises:
            PipelineError: Si le type de source ne peut pas être déterminé.
        """
        # Détection des APIs par préfixe HTTP/HTTPS
        if source.startswith("http://") or source.startswith("https://"):
            return "api"

        # Détection par extension de fichier
        _, extension = os.path.splitext(source.lower())

        if extension in _EXT_CSV:
            return "csv"
        elif extension in _EXT_EXCEL:
            return "excel"
        elif extension in _EXT_JSON:
            return "json"
        elif extension in _EXT_NETCDF:
            return "netcdf"
        else:
            raise PipelineError(
                f"Impossible de détecter le type de source pour '{source}'. "
                f"Extensions supportées : CSV {_EXT_CSV}, Excel {_EXT_EXCEL}, "
                f"JSON {_EXT_JSON}, NetCDF {_EXT_NETCDF}, ou URL HTTP."
            )

    def load_data(
        self,
        source: Union[str, DataSource],
        **kwargs: Any,
    ) -> "DataPipeline":
        """Configure la source de données du pipeline.

        Auto-détecte le type de source si un chemin de fichier est fourni,
        ou utilise directement une instance DataSource existante.

        Args:
            source (str | DataSource): Chemin vers le fichier, URL de l'API,
                ou instance DataSource directement.
            **kwargs: Arguments optionnels transmis au constructeur de la
                DataSource (ex: encoding, sheet_name, use_dask).

        Returns:
            DataPipeline: L'instance courante (pour le chaînage).

        Raises:
            PipelineError: Si le type de source est indéterminable.
        """
        if isinstance(source, DataSource):
            # Utilisation directe d'une DataSource existante
            self._source = source
            type_source = source.source_type
        else:
            # Auto-détection et instanciation de la DataSource appropriée
            type_source = self._detecter_type_source(source)

            if type_source == "csv":
                self._source = CSVDataSource(source, **kwargs)
            elif type_source == "excel":
                self._source = ExcelDataSource(source, **kwargs)
            elif type_source == "json":
                self._source = JSONDataSource(source, **kwargs)
            elif type_source == "netcdf":
                self._source = NetCDFDataSource(source, **kwargs)
            elif type_source == "api":
                self._source = APIDataSource(source, **kwargs)

        # Enregistrement dans le rapport
        self._rapports["source"] = {
            "path": str(source),
            "type": type_source,
        }

        logger.info(
            "Pipeline kidas : source '%s' configurée (type: %s).",
            source,
            type_source,
        )

        return self

    def add_cleaning_step(
        self,
        step_name: str,
        **params: Any,
    ) -> "DataPipeline":
        """Ajoute une étape de nettoyage à la file du pipeline.

        Les étapes sont exécutées dans l'ordre de leur ajout lors de
        l'appel à execute().

        Args:
            step_name (str): Nom de la méthode DataCleaner à appeler.
                Valeurs acceptées : 'remove_duplicates', 'handle_missing_values',
                'remove_outliers', 'fix_dates', 'standardize_text',
                'remove_special_chars'.
            **params: Paramètres à passer à la méthode de nettoyage
                (ex: strategy='mean', method='iqr').

        Returns:
            DataPipeline: L'instance courante (pour le chaînage).
        """
        # Enregistrement de l'étape dans la file
        self._etapes.append({
            "type": "cleaning",
            "nom": step_name,
            "params": params,
        })

        logger.debug(
            "Étape de nettoyage ajoutée : '%s' (params: %s).", step_name, params
        )

        return self

    def add_validation_step(
        self,
        schema: Dict[str, str],
    ) -> "DataPipeline":
        """Ajoute une étape de validation de schéma à la file du pipeline.

        Args:
            schema (dict[str, str]): Schéma de validation : nom_colonne → type.
                Exemple : {'culture': 'str', 'rendement_kg': 'float'}.

        Returns:
            DataPipeline: L'instance courante (pour le chaînage).
        """
        self._etapes.append({
            "type": "validation",
            "nom": "validate_schema",
            "params": {"schema": schema},
        })

        logger.debug("Étape de validation ajoutée (schéma: %s).", schema)

        return self

    def add_normalization_step(
        self,
        mappings: Dict[str, Any],
    ) -> "DataPipeline":
        """Ajoute une étape de normalisation à la file du pipeline.

        Args:
            mappings (dict): Dictionnaire de normalisation. Les clés supportées
                sont 'columns' (snake_case), 'units' (unités), 'crops' (FAO),
                'markets' (Bénin). Exemple : {'crops': 'culture'}.

        Returns:
            DataPipeline: L'instance courante (pour le chaînage).
        """
        self._etapes.append({
            "type": "normalization",
            "nom": "normalize",
            "params": {"mappings": mappings},
        })

        logger.debug("Étape de normalisation ajoutée (mappings: %s).", mappings)

        return self

    def execute(
        self,
        cache: bool = True,
    ) -> Tuple[pd.DataFrame, Dict]:
        """Exécute toutes les étapes configurées du pipeline.

        Charge les données depuis la source, applique les étapes de
        nettoyage, validation et normalisation dans l'ordre, puis
        met le résultat en cache si demandé.

        Args:
            cache (bool): Si True, tente de charger depuis le cache avant
                la lecture et sauvegarde le résultat final. Par défaut True.

        Returns:
            tuple[pd.DataFrame, dict]: Tuple contenant :
                - Le DataFrame traité et prêt à l'emploi.
                - Le rapport structuré selon la documentation :
                    - ``nb_rows_in``    : nombre de lignes brutes chargées.
                    - ``nb_rows_out``   : nombre de lignes après traitement.
                    - ``steps_summary`` : liste des noms d'étapes appliquées.
                    - ``quality_score`` : score qualité (dict) ou None.
                    - ``warnings``      : liste des avertissements détectés.
                    - ``cache_utilise`` : True si les données viennent du cache.
                    - ``details``       : rapports internes (source, nettoyage,
                      validation, normalisation).

        Raises:
            PipelineError: Si aucune source n'a été configurée.
            ReadError: Si la lecture de la source échoue.
        """
        # Vérification qu'une source a été configurée
        if self._source is None:
            raise PipelineError(
                "Aucune source configurée. Appelez load_data() avant execute()."
            )

        # Génération d'une clé de cache sécurisée : hachage SHA-256 du chemin brut,
        # tronqué à 16 caractères hexadécimaux pour éviter les collisions et les
        # erreurs d'encodage avec des chemins contenant des espaces ou des accents.
        _empreinte = hashlib.sha256(
            str(self._source.source_path).encode("utf-8")
        ).hexdigest()[:16]
        cle_cache = f"pipeline_{_empreinte}"

        # Tentative de chargement depuis le cache
        if cache:
            df_cached, _ = self._cache.load(cle_cache)
            if df_cached is not None:
                logger.info(
                    "Pipeline kidas : données chargées depuis le cache (clé: '%s').",
                    cle_cache,
                )
                # Construction du rapport minimal pour un retour depuis le cache
                rapport_cache = {
                    "nb_rows_in":    len(df_cached),
                    "nb_rows_out":   len(df_cached),
                    "steps_summary": [e["nom"] for e in self._etapes],
                    "quality_score": None,
                    "warnings":      [],
                    "cache_utilise": True,
                    "details": {
                        "source":        self._rapports.get("source"),
                        "nettoyage":     None,
                        "validation":    None,
                        "normalisation": None,
                    },
                }
                return df_cached, rapport_cache

        # Lecture des données depuis la source et mémorisation du nombre de lignes brutes
        try:
            self._df = self._source.read()
            # Capture du nombre de lignes avant tout traitement
            self._lignes_avant = len(self._df)
            logger.info(
                "Pipeline kidas : %d lignes chargées depuis '%s'.",
                self._lignes_avant,
                self._source.source_path,
            )
        except Exception as erreur:
            raise ReadError(
                f"Échec de lecture dans le pipeline : {erreur}"
            ) from erreur

        # Exécution des étapes dans l'ordre
        for etape in self._etapes:
            self._df = self._executer_etape(etape)

        # Sauvegarde en cache du résultat final
        if cache and self._df is not None:
            self._cache.save(cle_cache, self._df)
            self._rapports["cache_utilise"] = True

        # Calcul du nombre de lignes en sortie
        nb_lignes_out = len(self._df) if self._df is not None else 0

        # Construction du rapport final aligné sur la documentation publique
        rapport_final = {
            "nb_rows_in":    self._lignes_avant,
            "nb_rows_out":   nb_lignes_out,
            "steps_summary": [e["nom"] for e in self._etapes],
            "quality_score": self._rapports.get("quality_score"),
            "warnings":      self._extraire_warnings(),
            "cache_utilise": self._rapports.get("cache_utilise", False),
            "details": {
                "source":        self._rapports.get("source"),
                "nettoyage":     self._rapports.get("nettoyage"),
                "validation":    self._rapports.get("validation"),
                "normalisation": self._rapports.get("normalisation"),
            },
        }

        return self._df, rapport_final

    def _extraire_warnings(self) -> List[str]:
        """Collecte les avertissements depuis les rapports internes.

        Parcourt la liste des validations du rapport de validation pour
        extraire les erreurs de schéma et les expose sous forme de liste
        plate à la racine du rapport final. Cela permet à l'utilisateur
        d'accéder aux avertissements sans naviguer dans la hiérarchie
        interne du rapport.

        Returns:
            list[str]: Liste des messages d'avertissement. Vide si aucune
                étape de validation n'a été exécutée ou si aucune anomalie
                n'a été détectée.
        """
        avertissements: List[str] = []

        # Extraction des erreurs issues du rapport de validation
        rapport_validation = self._rapports.get("validation")
        if rapport_validation and isinstance(rapport_validation, dict):
            # 'validations' est une liste de dicts, chacun représentant
            # le résultat d'une vérification (schema, ranges, coordinates…)
            validations = rapport_validation.get("validations", [])
            for entree in validations:
                if not isinstance(entree, dict):
                    continue
                # Seules les validations de schéma portent une clé 'erreurs'
                erreurs = entree.get("erreurs", [])
                if isinstance(erreurs, list) and erreurs:
                    type_validation = entree.get("type", "validation")
                    avertissements.extend(
                        f"[{type_validation}] {msg}" for msg in erreurs
                    )

        return avertissements

    def _executer_etape(self, etape: Dict) -> pd.DataFrame:
        """Exécute une étape individuelle du pipeline sur le DataFrame courant.

        Args:
            etape (dict): Dictionnaire décrivant l'étape :
                {'type', 'nom', 'params'}.

        Returns:
            pd.DataFrame: Le DataFrame résultant de l'étape.

        Raises:
            PipelineError: Si la méthode de l'étape est inconnue.
        """
        type_etape = etape["type"]
        nom_methode = etape["nom"]
        params = etape["params"]

        try:
            if type_etape == "cleaning":
                # Instanciation du nettoyeur et appel dynamique de la méthode
                cleaner = DataCleaner(self._df)

                if not hasattr(cleaner, nom_methode):
                    raise PipelineError(
                        f"Méthode de nettoyage '{nom_methode}' inconnue. "
                        f"Méthodes disponibles : remove_duplicates, "
                        f"handle_missing_values, remove_outliers, fix_dates, "
                        f"standardize_text, remove_special_chars."
                    )

                # Appel de la méthode avec les paramètres
                resultat = getattr(cleaner, nom_methode)(**params)

                # Certaines méthodes retournent un tuple (df, outliers_df)
                if isinstance(resultat, tuple):
                    self._df = resultat[0]
                else:
                    self._df = resultat

                # Mise à jour du rapport de nettoyage
                self._rapports["nettoyage"] = cleaner.get_cleaning_report()

            elif type_etape == "validation":
                # Validation du schéma et calcul du score qualité
                validator = DataValidator(self._df)
                est_valide, erreurs = validator.validate_schema(params["schema"])
                score = validator.compute_quality_score()

                # Journalisation du résultat de validation
                if not est_valide:
                    logger.warning(
                        "Validation du schéma : %d erreur(s) détectée(s).", len(erreurs)
                    )
                    for erreur in erreurs:
                        logger.warning("  - %s", erreur)

                self._rapports["validation"] = validator.get_validation_report()
                self._rapports["quality_score"] = score

            elif type_etape == "normalization":
                # Application des normalisations demandées
                normalizer = DataNormalizer(self._df)
                mappings = params["mappings"]

                # Normalisation des noms de colonnes si demandé
                if "columns" in mappings or mappings.get("normalize_columns"):
                    normalizer.normalize_column_names()

                # Normalisation des noms de cultures si demandé
                if "crops" in mappings:
                    normalizer.normalize_crop_names(col=mappings["crops"])

                # Normalisation des unités si demandé
                if "units" in mappings:
                    normalizer.normalize_units(unit_map=mappings["units"])

                # Normalisation des marchés si demandé
                if "markets" in mappings:
                    normalizer.normalize_market_names(col=mappings["markets"])

                self._df = normalizer.df
                self._rapports["normalisation"] = normalizer.get_normalization_mapping()

        except PipelineError:
            raise
        except Exception as erreur:
            raise PipelineError(
                f"Erreur lors de l'exécution de l'étape '{nom_methode}' : {erreur}"
            ) from erreur

        return self._df

    def get_pipeline_config(self) -> dict:
        """Retourne la configuration complète du pipeline (étapes définies).

        Returns:
            dict: Dictionnaire décrivant la source et les étapes configurées.
        """
        return {
            "source": self._rapports.get("source"),
            "nb_etapes": len(self._etapes),
            "etapes": [
                {"type": e["type"], "nom": e["nom"], "params": e["params"]}
                for e in self._etapes
            ],
        }

    def export_report(self, filepath: str) -> bool:
        """Exporte le rapport de pipeline dans un fichier JSON ou HTML.

        Args:
            filepath (str): Chemin de destination du rapport. L'extension
                détermine le format : '.json' ou '.html'.

        Returns:
            bool: True si l'export s'est déroulé avec succès.

        Raises:
            PipelineError: Si l'extension n'est pas supportée.
        """
        import json

        _, extension = os.path.splitext(filepath.lower())

        try:
            if extension == ".json":
                # Export au format JSON
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(self._rapports, f, ensure_ascii=False, indent=2, default=str)

            elif extension == ".html":
                # Export au format HTML simplifié
                contenu_json = json.dumps(
                    self._rapports, ensure_ascii=False, indent=2, default=str
                )
                html = (
                    "<html><head><meta charset='utf-8'>"
                    "<title>Rapport kidas Pipeline</title></head>"
                    "<body><h1>Rapport kidas DataPipeline</h1>"
                    f"<pre>{contenu_json}</pre></body></html>"
                )
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html)

            else:
                raise PipelineError(
                    f"Format d'export '{extension}' non supporté. "
                    f"Utilisez '.json' ou '.html'."
                )

            logger.info("Rapport pipeline exporté vers '%s'.", filepath)
            return True

        except OSError as erreur:
            raise PipelineError(
                f"Impossible d'écrire le rapport vers '{filepath}' : {erreur}"
            ) from erreur
