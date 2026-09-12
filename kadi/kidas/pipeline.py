# -*- coding: utf-8 -*-
"""
Module implémentant Pipeline, l'orchestrateur central du module kidas.

Pipeline est le point d'entrée principal : il détecte automatiquement
le type de source depuis le chemin ou l'extension, chaîne les étapes de
nettoyage, validation et normalisation, puis met les résultats en cache.
Son API fluide (chainable) permet une utilisation concise et lisible.
"""

import hashlib
import logging
import os
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

# Import des sources de données (nouveaux noms Phase 2)
from kadi.kidas.sources import (
    CSVSource,
    ExcelSource,
    JSONSource,
    APISource,
    Source,
)

# Import conditionnel : xarray est requis pour NetCDF
try:
    from kadi.kidas.sources import NetCDFSource
    _NETCDF_DISPONIBLE = True
except ImportError:
    NetCDFSource = None  # type: ignore[assignment]
    _NETCDF_DISPONIBLE = False

# Import des classes de traitement (Phase 3 : nouveaux noms)
from kadi.kidas.cleaner import Cleaner
from kadi.kidas.validator import Validator
from kadi.kidas.normalizer import Normalizer
from kadi.kidas.cache import Cache

# Import des exceptions personnalisées
from kadi.exceptions import PipelineError, ReadError

# Initialisation du logger pour ce module
logger = logging.getLogger(__name__)

# Extensions de fichiers reconnues par le pipeline
_EXT_CSV = {".csv", ".tsv", ".txt"}
_EXT_EXCEL = {".xls", ".xlsx", ".xlsm"}
_EXT_JSON = {".json"}
_EXT_NETCDF = {".nc", ".nc4", ".netcdf"}


class Pipeline:
    """Orchestrateur du flux de traitement de données agricoles kidas.

    Pipeline est le point d'entrée unique pour les utilisateurs de kidas.
    Il permet de définir de manière déclarative et chainable un flux complet :
    chargement → nettoyage → validation → normalisation → cache.

    L'auto-détection du type de source (CSV, Excel, JSON, NetCDF, API) est
    basée sur l'extension du fichier ou le préfixe 'http' de l'URL.

    Attributs:
        _source (Source | None): Source de données configurée.
        _df (pd.DataFrame | None): Données courantes dans le pipeline.
        _steps (list): Liste ordonnée des étapes de traitement configurées.
        _reports (dict): Rapports agrégés de toutes les étapes.
        _cache (Cache): Instance du gestionnaire de cache kidas.

    Exemple:
        >>> pipeline = Pipeline()
        >>> df, rapport = (
        ...     pipeline
        ...     .add_source('recolte_2024.xlsx')
        ...     .add_step('drop_dupes')
        ...     .add_step('fill_missing', strategy='mean')
        ...     .add_step('check_schema', {'culture': 'str', 'rendement_kg': 'float'})
        ...     .run(cache=True)
        ... )
        >>> print(rapport['nb_rows_out'])
        150
        >>> print(rapport['quality_score']['overall'])
        0.97
    """

    def __init__(self) -> None:
        """Initialise un pipeline vide prêt à recevoir des étapes de traitement."""
        # Source de données (sera configurée par add_source())
        self._source: Optional[Source] = None

        # DataFrame courant (None jusqu'à l'appel de run())
        self._df: Optional[pd.DataFrame] = None

        # Nombre de lignes brutes avant toute transformation
        self._nrows_in: int = 0
        self._lignes_avant: int = 0  # Alias de rétrocompatibilité

        # Liste ordonnée des étapes : {'type', 'nom', 'params'}
        self._steps: List[Dict[str, Any]] = []

        # Rapports agrégés internes des étapes de traitement
        self._reports: Dict[str, Any] = {
            "source": None,
            "nettoyage": None,
            "validation": None,
            "normalisation": None,
            "cache_utilise": False,
        }

        # Instance du cache kidas
        self._cache: Cache = Cache()

    @staticmethod
    def _detect_kind(source: str) -> str:
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
                f"Extension '{extension}' non reconnue pour la source '{source}'. "
                f"Extensions supportées : CSV, Excel, JSON, NetCDF, API."
            )

    # Alias statique de rétrocompatibilité
    _detecter_type_source = _detect_kind

    def add_source(
        self,
        source: Union[str, Source],
        **kwargs: Any,
    ) -> "Pipeline":
        """Configure la source de données du pipeline.

        Auto-détecte le type de source si un chemin de fichier est fourni,
        ou utilise directement une instance Source existante.

        Args:
            source (str | Source): Chemin vers le fichier, URL de l'API,
                ou instance Source directement.
            **kwargs: Arguments optionnels transmis au constructeur de la
                Source (ex: encoding, sheet_name, use_dask).

        Returns:
            Pipeline: L'instance courante (pour le chaînage).

        Raises:
            PipelineError: Si le type de source est indéterminable.
        """
        if isinstance(source, Source):
            # Utilisation directe d'une Source existante
            self._source = source
            type_source = source.kind
        else:
            # Auto-détection et instanciation de la Source appropriée
            type_source = self._detecter_type_source(source)

            if type_source == "csv":
                self._source = CSVSource(source, **kwargs)
            elif type_source == "excel":
                self._source = ExcelSource(source, **kwargs)
            elif type_source == "json":
                self._source = JSONSource(source, **kwargs)
            elif type_source == "netcdf":
                self._source = NetCDFSource(source, **kwargs)
            elif type_source == "api":
                self._source = APISource(source, **kwargs)

        # Enregistrement dans le rapport
        self._reports["source"] = {
            "path": str(source),
            "type": type_source,
        }

        logger.info(
            "Pipeline kidas : source '%s' configurée (type: %s).",
            source,
            type_source,
        )

        return self

    def add_step(
        self,
        step_name: str,
        schema_or_mappings: Any = None,
        **params: Any,
    ) -> "Pipeline":
        """Ajoute une étape de traitement à la file du pipeline.

        Accepte des étapes de nettoyage, de validation ou de normalisation
        en un seul point d'entrée. Le type de l'étape est déterminé
        automatiquement selon le nom passé.

        Args:
            step_name (str): Nom de l'étape. Valeurs acceptées :
                - Nettoyage : 'drop_dupes', 'fill_missing', 'drop_outliers',
                  'parse_dates', 'norm_text', 'strip_chars'.
                - Validation : 'check_schema', 'check_types',
                  'check_ranges', 'check_coords', 'check_unique', 'check_fk'.
                - Normalisation : 'norm_cols', 'convert_units',
                  'convert_currency', 'std_crops', 'std_markets', 'std_coords'.
            schema_or_mappings: Argument positionnel optionnel pour les étapes
                de validation (schema dict) ou normalisation (mappings dict).
            **params: Paramètres supplémentaires à passer à la méthode
                (ex: strategy='mean', cols=['id', 'date']).

        Returns:
            Pipeline: L'instance courante (pour le chaînage).
        """
        # Détermination automatique du type d'étape
        _cleaning = {
            "drop_dupes", "fill_missing", "drop_outliers",
            "parse_dates", "norm_text", "strip_chars",
            "check_decimals", "report",
            "remove_duplicates", "handle_missing_values", "remove_outliers",
            "fix_dates", "standardize_text", "remove_special_chars",
            "detect_inconsistent_decimals", "get_cleaning_report",
        }
        _validation = {
            "check_schema", "check_types", "check_ranges",
            "check_coords", "check_unique", "check_fk",
            "quality_score", "validate_schema", "validate_types",
            "validate_ranges", "validate_coordinates", "validate_uniqueness",
        }
        _normalisation = {
            "norm_cols", "convert_units", "convert_currency",
            "std_crops", "std_markets", "std_coords", "mappings",
            "normalize_column_names", "normalize_units", "normalize_currencies",
            "normalize_crop_names", "normalize_market_names", "normalize_geometry",
            "get_normalization_mapping", "normalize",
        }

        if step_name in _cleaning:
            type_etape = "cleaning"
        elif step_name in _validation:
            type_etape = "validation"
        elif step_name in _normalisation:
            type_etape = "normalization"
        else:
            type_etape = "cleaning"  # Fallback tolérant

        # Gestion du premier argument positionnel
        if schema_or_mappings is not None:
            if type_etape == "validation":
                params["schema"] = schema_or_mappings
            elif type_etape == "normalization":
                params["mappings"] = schema_or_mappings

        # Enregistrement de l'étape dans la file
        self._steps.append({
            "type": type_etape,
            "nom": step_name,
            "params": params,
        })

        logger.debug(
            "Etape '%s' (type: %s) ajoutée (params: %s).",
            step_name, type_etape, params,
        )

        return self

    def load(self, source: Union[str, Source], **kwargs: Any) -> "Pipeline":
        """Configure la source de données du pipeline (alias court de add_source).

        Args:
            source (str | Source): Chemin vers le fichier, URL ou instance Source.
            **kwargs: Arguments transmis au constructeur de la Source.

        Returns:
            Pipeline: L'instance courante pour le chaînage.
        """
        return self.add_source(source, **kwargs)

    def clean(self, step: str, **params: Any) -> "Pipeline":
        """Ajoute une étape de nettoyage au pipeline (alias court de add_step).

        Args:
            step (str): Nom de l'étape de nettoyage (ex: 'drop_dupes').
            **params: Paramètres de l'étape de nettoyage.

        Returns:
            Pipeline: L'instance courante pour le chaînage.
        """
        return self.add_step(step, **params)

    def validate(self, schema: Any = None, **params: Any) -> "Pipeline":
        """Ajoute une étape de validation au pipeline (alias court de add_step).

        Args:
            schema (dict | str): Schéma de validation ou nom de l'étape.
            **params: Paramètres de validation.

        Returns:
            Pipeline: L'instance courante pour le chaînage.
        """
        if isinstance(schema, str):
            return self.add_step(schema, **params)
        return self.add_step("check_schema", schema, **params)

    def normalize(self, mappings: Any = None, **params: Any) -> "Pipeline":
        """Ajoute une étape de normalisation au pipeline (alias court de add_step).

        Args:
            mappings (dict | str): Mappings de normalisation ou nom de l'étape.
            **params: Paramètres de normalisation.

        Returns:
            Pipeline: L'instance courante pour le chaînage.
        """
        if isinstance(mappings, str):
            return self.add_step(mappings, **params)
        return self.add_step("norm_cols", mappings, **params)

    def run(
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
                "Aucune source configurée. Appelez add_source() avant run()."
            )

        # Génération d'une clé de cache sécurisée : hachage SHA-256 du chemin brut,
        # tronqué à 16 caractères hexadécimaux pour éviter les collisions et les
        # erreurs d'encodage avec des chemins contenant des espaces ou des accents.
        _empreinte = hashlib.sha256(
            str(self._source.path).encode("utf-8")
        ).hexdigest()[:16]
        cle_cache = f"pipeline_{_empreinte}"

        # Tentative de chargement depuis le cache
        if cache:
            df_cached, _ = self._cache.get(cle_cache)
            if df_cached is not None:
                logger.info(
                    "Pipeline kidas : données chargées depuis le cache (clé: '%s').",
                    cle_cache,
                )
                # Construction du rapport minimal pour un retour depuis le cache
                rapport_cache = {
                    "nb_rows_in":    len(df_cached),
                    "nb_rows_out":   len(df_cached),
                    "steps_summary": [e["nom"] for e in self._steps],
                    "quality_score": None,
                    "warnings":      [],
                    "cache_utilise": True,
                    "details": {
                        "source":        self._reports.get("source"),
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
                self._source.path,
            )
        except Exception as erreur:
            raise ReadError(
                f"Echec de lecture dans le pipeline : {erreur}"
            ) from erreur

        # Exécution des étapes dans l'ordre
        for etape in self._steps:
            self._df = self._exec_step(etape)

        # Sauvegarde en cache du résultat final
        if cache and self._df is not None:
            self._cache.set(cle_cache, self._df)
            self._reports["cache_utilise"] = True

        # Calcul du nombre de lignes en sortie
        nb_lignes_out = len(self._df) if self._df is not None else 0

        # Construction du rapport final aligné sur la documentation publique
        rapport_final = {
            "nb_rows_in":    self._lignes_avant,
            "nb_rows_out":   nb_lignes_out,
            "steps_summary": [e["nom"] for e in self._steps],
            "quality_score": self._reports.get("quality_score"),
            "warnings":      self._collect_warnings(),
            "cache_utilise": self._reports.get("cache_utilise", False),
            "details": {
                "source":        self._reports.get("source"),
                "nettoyage":     self._reports.get("nettoyage"),
                "validation":    self._reports.get("validation"),
                "normalisation": self._reports.get("normalisation"),
            },
        }

        return self._df, rapport_final

    def _collect_warnings(self) -> List[str]:
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
        rapport_validation = self._reports.get("validation")
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

    def _exec_step(self, etape: Dict) -> pd.DataFrame:
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
                cleaner = Cleaner(self._df)

                if not hasattr(cleaner, nom_methode):
                    raise PipelineError(
                        f"Méthode de nettoyage '{nom_methode}' inconnue. "
                        f"Méthodes disponibles : drop_dupes, fill_missing, "
                        f"drop_outliers, parse_dates, norm_text, strip_chars."
                    )

                # Appel de la méthode avec les paramètres
                resultat = getattr(cleaner, nom_methode)(**params)

                # Certaines méthodes retournent un tuple (df, outliers_df)
                if isinstance(resultat, tuple):
                    self._df = resultat[0]
                else:
                    self._df = resultat

                # Mise à jour du rapport de nettoyage
                self._reports["nettoyage"] = cleaner.report()

            elif type_etape == "validation":
                # Validation du schéma et calcul du score qualité
                validator = Validator(self._df)
                est_valide, erreurs = validator.check_schema(params.get("schema", {}))
                score = validator.quality_score()

                # Journalisation du résultat de validation
                if not est_valide:
                    logger.warning(
                        "Validation du schéma : %d erreur(s) détectée(s).", len(erreurs)
                    )
                    for erreur in erreurs:
                        logger.warning("  - %s", erreur)

                self._reports["validation"] = validator.report()
                self._reports["quality_score"] = score

            elif type_etape == "normalization":
                # Application des normalisations demandées
                normalizer = Normalizer(self._df)

                # Méthodes disponibles directement par nom via add_step
                _methodes_directes = {
                    "norm_cols", "convert_units", "convert_currency",
                    "std_crops", "std_markets", "std_coords", "mappings",
                }

                if nom_methode in _methodes_directes:
                    # Dispatch direct : appel de la méthode par son nom
                    if not hasattr(normalizer, nom_methode):
                        raise PipelineError(
                            f"Méthode de normalisation '{nom_methode}' inconnue."
                        )
                    resultat = getattr(normalizer, nom_methode)(**params)
                    # mappings() retourne un dict, les autres retournent un DataFrame
                    if isinstance(resultat, pd.DataFrame):
                        self._df = resultat

                else:
                    # Ancien mécanisme via le dict 'mappings' (rétrocompatibilité)
                    mappings = params.get("mappings", {})

                    # Normalisation des noms de colonnes si demandé
                    if "columns" in mappings or mappings.get("normalize_columns"):
                        normalizer.norm_cols()

                    # Normalisation des noms de cultures si demandé
                    if "crops" in mappings:
                        normalizer.std_crops(col=mappings["crops"])

                    # Normalisation des unités si demandé
                    if "units" in mappings:
                        normalizer.convert_units(unit_map=mappings["units"])

                    # Normalisation des marchés si demandé
                    if "markets" in mappings:
                        normalizer.std_markets(col=mappings["markets"])

                    self._df = normalizer.df

                self._reports["normalisation"] = normalizer.mappings()

        except PipelineError:
            raise
        except Exception as erreur:
            raise PipelineError(
                f"Erreur lors de l'exécution de l'étape '{nom_methode}' : {erreur}"
            ) from erreur

        return self._df

    # Alias interne pour conformité renommage.md
    _run_step = _exec_step

    def config(self) -> dict:
        """Retourne la configuration complète du pipeline (étapes définies).

        Returns:
            dict: Dictionnaire décrivant la source et les étapes configurées.
        """
        steps_list = [
            {"type": e["type"], "nom": e["nom"], "params": e["params"]}
            for e in self._steps
        ]
        return {
            "source": self._reports.get("source"),
            "nb_steps": len(self._steps),
            "nb_etapes": len(self._steps),  # Rétrocompatibilité
            "steps": steps_list,
            "etapes": steps_list,  # Rétrocompatibilité
        }

    def export(
        self,
        filepath: str,
        **kwargs,
    ) -> bool:
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
                    json.dump(self._reports, f, ensure_ascii=False, indent=2, default=str)

            elif extension == ".html":
                # Export au format HTML simplifié
                contenu_json = json.dumps(
                    self._reports, ensure_ascii=False, indent=2, default=str
                )
                html = (
                    "<html><head><meta charset='utf-8'>"
                    "<title>Rapport kidas Pipeline</title></head>"
                    "<body><h1>Rapport kidas Pipeline</h1>"
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

    # --- Méthodes de rétrocompatibilité ---

    def load_data(
        self,
        source: Union[str, Source],
        **kwargs: Any,
    ) -> "Pipeline":
        """Alias de rétrocompatibilité pour add_source()."""
        warnings.warn(
            "Pipeline.load_data() est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Pipeline.add_source() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.add_source(source, **kwargs)

    def add_cleaning_step(
        self,
        step_name: str,
        **params: Any,
    ) -> "Pipeline":
        """Alias de rétrocompatibilité pour add_step()."""
        warnings.warn(
            "Pipeline.add_cleaning_step() est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Pipeline.add_step() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.add_step(step_name, **params)

    def add_validation_step(
        self,
        schema: Dict[str, str],
    ) -> "Pipeline":
        """Alias de rétrocompatibilité pour add_step('check_schema', schema)."""
        warnings.warn(
            "Pipeline.add_validation_step() est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Pipeline.add_step() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.add_step("check_schema", schema=schema)

    def add_normalization_step(
        self,
        mappings: Dict[str, Any],
    ) -> "Pipeline":
        """Alias de rétrocompatibilité pour add_step('mappings', mappings)."""
        warnings.warn(
            "Pipeline.add_normalization_step() est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Pipeline.add_step() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.add_step("mappings", mappings=mappings)

    def execute(
        self,
        cache: bool = True,
    ) -> Tuple[pd.DataFrame, Dict]:
        """Alias de rétrocompatibilité pour run()."""
        warnings.warn(
            "Pipeline.execute() est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Pipeline.run() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.run(cache=cache)

    def get_pipeline_config(self) -> dict:
        """Alias de rétrocompatibilité pour config()."""
        warnings.warn(
            "Pipeline.get_pipeline_config() est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Pipeline.config() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.config()

    def export_report(
        self,
        filepath: str,
        **kwargs,
    ) -> bool:
        """Alias de rétrocompatibilité pour export()."""
        warnings.warn(
            "Pipeline.export_report() est obsolète et sera supprimé dans KadiPy v2.0. "
            "Utilisez Pipeline.export() à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.export(filepath, **kwargs)


# Table des anciens noms -> (nouveau nom, classe cible)
_DEPRECATED = {
    "DataPipeline": ("Pipeline", Pipeline),
}


def __getattr__(name: str):
    """Intercepte les anciens noms importés depuis ce module.

    Args:
        name (str): Nom du symbole demandé dans ce module.

    Returns:
        type: La classe correspondante.

    Raises:
        AttributeError: Si le nom n'est pas un alias connu.
    """
    import warnings as _warnings
    if name in _DEPRECATED:
        new_name, cls = _DEPRECATED[name]
        _warnings.warn(
            f"kadi.kidas.pipeline.{name} est obsolète et sera supprimé dans "
            f"KadiPy v2.0. Utilisez {new_name} à la place.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return cls
    raise AttributeError(
        f"Le module 'kadi.kidas.pipeline' n'a pas d'attribut '{name}'."
    )
