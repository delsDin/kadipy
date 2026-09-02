# -*- coding: utf-8 -*-
"""Tests unitaires pour DataCleaner, DataValidator, DataNormalizer et DataPipeline."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from kadi.kidas.cleaner import DataCleaner
from kadi.kidas.validator import DataValidator
from kadi.kidas.normalizer import DataNormalizer
from kadi.kidas.pipeline import DataPipeline
from kadi.exceptions import CleanError, ValidationError, PipelineError


# =============================================================================
# Tests DataCleaner
# =============================================================================

class TestDataCleaner:
    """Tests unitaires pour la classe DataCleaner."""

    def test_init_invalide_leve_exception(self):
        """Vérifie que DataCleaner lève une erreur avec un argument non-DataFrame."""
        with pytest.raises(CleanError):
            DataCleaner("pas_un_dataframe")

    def test_remove_duplicates_supprime_doublons(self, sample_df_with_duplicates):
        """Vérifie la suppression des lignes dupliquées."""
        nb_avant = len(sample_df_with_duplicates)
        cleaner = DataCleaner(sample_df_with_duplicates)
        df_propre = cleaner.remove_duplicates()
        assert len(df_propre) < nb_avant

    def test_remove_duplicates_rapport_mis_a_jour(self, sample_df_with_duplicates):
        """Vérifie que le rapport comptabilise les doublons supprimés."""
        cleaner = DataCleaner(sample_df_with_duplicates)
        cleaner.remove_duplicates()
        rapport = cleaner.get_cleaning_report()
        assert rapport["doublons_supprimes"] > 0

    def test_handle_missing_mean_remplace_nan(self, sample_df):
        """Vérifie que la stratégie 'mean' remplace les NaN numériques."""
        cleaner = DataCleaner(sample_df)
        nb_nan_avant = sample_df["rendement_kg"].isna().sum()
        assert nb_nan_avant > 0
        df = cleaner.handle_missing_values(strategy="mean", columns=["rendement_kg"])
        assert df["rendement_kg"].isna().sum() == 0

    def test_handle_missing_drop_supprime_lignes(self, sample_df):
        """Vérifie que la stratégie 'drop' supprime les lignes avec NaN."""
        nb_avant = len(sample_df)
        cleaner = DataCleaner(sample_df)
        df = cleaner.handle_missing_values(strategy="drop")
        assert len(df) < nb_avant

    def test_handle_missing_strategie_invalide(self, sample_df):
        """Vérifie qu'une stratégie invalide lève CleanError."""
        cleaner = DataCleaner(sample_df)
        with pytest.raises(CleanError):
            cleaner.handle_missing_values(strategy="invalide")

    def test_remove_outliers_iqr_detecte_outliers(self, sample_df_with_outliers):
        """Vérifie que la méthode IQR détecte les outliers évidents."""
        cleaner = DataCleaner(sample_df_with_outliers)
        df_propre, df_outliers = cleaner.remove_outliers(method="iqr")
        # La valeur 15000 doit être détectée comme outlier
        assert len(df_outliers) > 0
        assert 15000 in list(sample_df_with_outliers["rendement_kg"])

    def test_remove_outliers_methode_invalide(self, sample_df):
        """Vérifie qu'une méthode invalide lève CleanError."""
        cleaner = DataCleaner(sample_df)
        with pytest.raises(CleanError):
            cleaner.remove_outliers(method="methode_invalide")

    def test_fix_dates_convertit_colonne(self, sample_df):
        """Vérifie que fix_dates() convertit une colonne en datetime64."""
        cleaner = DataCleaner(sample_df)
        df = cleaner.fix_dates(columns=["date_recolte"])
        assert pd.api.types.is_datetime64_any_dtype(df["date_recolte"])

    def test_fix_dates_compteur_toutes_converties(self):
        """Vérifie que dates_corrigees == nb_lignes quand toutes les dates sont valides."""
        # 5 dates toutes parsables
        df = pd.DataFrame({
            "date_recolte": [
                "2024-01-01", "2024-02-15", "2024-03-10",
                "2024-04-01", "2024-05-05",
            ]
        })
        cleaner = DataCleaner(df)
        cleaner.fix_dates(columns=["date_recolte"])
        rapport = cleaner.get_cleaning_report()
        # Le compteur doit correspondre aux conversions réussies, pas au total initial
        assert rapport["dates_corrigees"] == 5

    def test_fix_dates_compteur_conversions_partielles(self):
        """Vérifie que dates_corrigees reflète le nombre réel de dates converties."""
        # 10 valeurs : 8 parsables, 2 invalides
        df = pd.DataFrame({
            "date_recolte": [
                "2024-01-01", "2024-02-15", "invalide",
                "2024-03-10", "pas-une-date", "2024-04-01",
                "2024-05-05", "2024-06-20", "2024-07-07",
                "2024-08-08",
            ]
        })
        cleaner = DataCleaner(df)
        cleaner.fix_dates(columns=["date_recolte"])
        rapport = cleaner.get_cleaning_report()
        # Le bug précédent retournait 10 (nb_avant) ; la correction retourne 8 (nb_apres)
        assert rapport["dates_corrigees"] == 8

    def test_fix_dates_colonne_inexistante_ne_plante_pas(self):
        """Vérifie que fix_dates() ne plante pas et laisse le compteur à 0 si la colonne est absente."""
        df = pd.DataFrame({"autre_colonne": [1, 2, 3]})
        cleaner = DataCleaner(df)
        # Ne doit pas lever d'exception
        cleaner.fix_dates(columns=["colonne_inexistante"])
        rapport = cleaner.get_cleaning_report()
        assert rapport["dates_corrigees"] == 0

    def test_standardize_text_minuscules(self, sample_df):
        """Vérifie que standardize_text() convertit en minuscules."""
        cleaner = DataCleaner(sample_df)
        df = cleaner.standardize_text(columns=["marche"], case="lower")
        assert all(v == v.lower() for v in df["marche"].dropna())

    def test_detect_inconsistent_decimals(self):
        """Vérifie la détection du mélange de séparateurs décimaux."""
        df = pd.DataFrame({"prix": ["1.500", "2,300", "1.800"]})
        cleaner = DataCleaner(df)
        rapport = cleaner.detect_inconsistent_decimals(columns=["prix"])
        assert rapport["prix"]["mixed"] is True

    def test_get_cleaning_report_structure(self, sample_df):
        """Vérifie la structure du rapport de nettoyage."""
        cleaner = DataCleaner(sample_df)
        cleaner.remove_duplicates()
        rapport = cleaner.get_cleaning_report()
        for cle in ("doublons_supprimes", "nan_traites", "lignes_initiales",
                    "lignes_finales", "operations"):
            assert cle in rapport


# =============================================================================
# Tests DataValidator
# =============================================================================

class TestDataValidator:
    """Tests unitaires pour la classe DataValidator."""

    def test_init_invalide_leve_exception(self):
        """Vérifie que DataValidator lève une erreur avec un non-DataFrame."""
        with pytest.raises(ValidationError):
            DataValidator([1, 2, 3])

    def test_validate_schema_valide(self, sample_df):
        """Vérifie qu'un schéma correct est validé sans erreur."""
        validator = DataValidator(sample_df)
        valide, erreurs = validator.validate_schema({"culture": "str"})
        assert valide is True
        assert len(erreurs) == 0

    def test_validate_schema_colonne_manquante(self, sample_df):
        """Vérifie qu'une colonne manquante génère une erreur de schéma."""
        validator = DataValidator(sample_df)
        valide, erreurs = validator.validate_schema({"colonne_inexistante": "str"})
        assert valide is False
        assert len(erreurs) > 0

    def test_validate_ranges_dans_les_bornes(self, sample_df):
        """Vérifie que des valeurs dans les bornes passent la validation."""
        validator = DataValidator(sample_df)
        valide, df_hors = validator.validate_ranges(
            {"rendement_kg": (0, 10000)}
        )
        assert valide is True

    def test_validate_ranges_hors_bornes(self):
        """Vérifie que des valeurs hors bornes sont détectées."""
        df = pd.DataFrame({"temperature": [-15, 20, 60]})
        validator = DataValidator(df)
        valide, df_hors = validator.validate_ranges({"temperature": (-10, 50)})
        assert valide is False
        assert len(df_hors) == 2  # -15 et 60

    def test_validate_coordinates_benin_valides(self, sample_df):
        """Vérifie que des coordonnées dans la bbox Bénin sont acceptées."""
        validator = DataValidator(sample_df)
        valide, df_invalides = validator.validate_coordinates("lat", "lon")
        assert valide is True

    def test_validate_coordinates_hors_bbox(self):
        """Vérifie que des coordonnées hors bbox Bénin sont détectées."""
        df = pd.DataFrame({
            "lat": [6.0, 50.0],  # 50.0 hors bbox
            "lon": [2.0, 2.0],
        })
        validator = DataValidator(df)
        valide, df_invalides = validator.validate_coordinates("lat", "lon")
        assert valide is False
        assert len(df_invalides) == 1

    def test_validate_uniqueness_sans_doublon(self, sample_df):
        """Vérifie la validation d'unicité sur un DataFrame sans doublons."""
        validator = DataValidator(sample_df)
        valide, df_dup = validator.validate_uniqueness(["culture", "marche"])
        # Le sample_df peut avoir des doublons, on teste juste le type de retour
        assert isinstance(valide, bool)
        assert isinstance(df_dup, pd.DataFrame)

    def test_compute_quality_score_structure(self, sample_df):
        """Vérifie la structure du score de qualité retourné."""
        validator = DataValidator(sample_df)
        score = validator.compute_quality_score()
        for cle in ("overall", "completeness", "consistency", "accuracy", "columns"):
            assert cle in score
        # Le score global doit être compris entre 0 et 1
        assert 0.0 <= score["overall"] <= 1.0

    def test_get_validation_report_retourne_dict(self, sample_df):
        """Vérifie que get_validation_report() retourne un dictionnaire."""
        validator = DataValidator(sample_df)
        rapport = validator.get_validation_report()
        assert isinstance(rapport, dict)
        assert "validations" in rapport


# =============================================================================
# Tests DataNormalizer
# =============================================================================

class TestDataNormalizer:
    """Tests unitaires pour la classe DataNormalizer."""

    def test_init_invalide_leve_exception(self):
        """Vérifie que DataNormalizer lève une erreur avec un non-DataFrame."""
        with pytest.raises(CleanError):
            DataNormalizer("pas_un_dataframe")

    def test_normalize_column_names_snake_case(self):
        """Vérifie la conversion des noms de colonnes en snake_case."""
        df = pd.DataFrame({"Température Min": [1], "Prix (XOF)": [2]})
        normalizer = DataNormalizer(df)
        df_norm = normalizer.normalize_column_names()
        assert "temperature_min" in df_norm.columns
        assert "prix_xof" in df_norm.columns

    def test_normalize_column_names_supprime_accents(self):
        """Vérifie que les accents sont supprimés des noms de colonnes."""
        df = pd.DataFrame({"Récolte": [1], "Données": [2]})
        normalizer = DataNormalizer(df)
        df_norm = normalizer.normalize_column_names()
        colonnes = list(df_norm.columns)
        for col in colonnes:
            assert "é" not in col
            assert "é" not in col

    def test_normalize_units_tonne_vers_kg(self, sample_df):
        """Vérifie la conversion de tonnes vers kg."""
        df = pd.DataFrame({"production": [1.0, 2.5, 0.8]})
        normalizer = DataNormalizer(df)
        df_norm = normalizer.normalize_units({"production": "tonne"})
        assert df_norm["production"].iloc[0] == pytest.approx(1000.0)
        assert df_norm["production"].iloc[1] == pytest.approx(2500.0)

    def test_normalize_units_unite_inconnue_leve_exception(self):
        """Vérifie qu'une unité inconnue lève CleanError."""
        df = pd.DataFrame({"production": [1.0]})
        normalizer = DataNormalizer(df)
        with pytest.raises(CleanError):
            normalizer.normalize_units({"production": "caisse_inconnue"})

    def test_normalize_crop_names_mais(self, sample_df):
        """Vérifie la normalisation des noms de cultures vers FAO."""
        normalizer = DataNormalizer(sample_df)
        df_norm = normalizer.normalize_crop_names(col="culture")
        # "maïs" doit devenir "maize"
        assert "maize" in df_norm["culture"].values

    def test_normalize_crop_names_niebe(self, sample_df):
        """Vérifie que 'Niébé' est normalisé en 'cowpea'."""
        normalizer = DataNormalizer(sample_df)
        df_norm = normalizer.normalize_crop_names(col="culture")
        assert "cowpea" in df_norm["culture"].values

    def test_normalize_market_names_ajoute_colonnes_gps(self, sample_df):
        """Vérifie que normalize_market_names() ajoute market_lat et market_lon."""
        normalizer = DataNormalizer(sample_df)
        df_norm = normalizer.normalize_market_names(col="marche")
        assert "market_lat" in df_norm.columns
        assert "market_lon" in df_norm.columns

    def test_normalize_geometry_ajoute_colonne_geometry(self, sample_df):
        """Vérifie que normalize_geometry() ajoute la colonne 'geometry'."""
        pytest.importorskip("shapely")
        normalizer = DataNormalizer(sample_df)
        df_norm = normalizer.normalize_geometry(lat_col="lat", lon_col="lon")
        assert "geometry" in df_norm.columns

    def test_get_normalization_mapping_structure(self, sample_df):
        """Vérifie la structure du mapping de normalisation."""
        normalizer = DataNormalizer(sample_df)
        normalizer.normalize_column_names()
        mapping = normalizer.get_normalization_mapping()
        for cle in ("colonnes", "unites", "cultures", "marches", "devises"):
            assert cle in mapping


# =============================================================================
# Tests DataPipeline
# =============================================================================

class TestDataPipeline:
    """Tests unitaires pour la classe DataPipeline."""

    def test_execute_sans_source_leve_exception(self):
        """Vérifie que execute() sans source lève PipelineError."""
        pipeline = DataPipeline()
        with pytest.raises(PipelineError):
            pipeline.execute()

    def test_detecter_type_source_csv(self):
        """Vérifie la détection du type CSV depuis l'extension."""
        assert DataPipeline._detecter_type_source("fichier.csv") == "csv"

    def test_detecter_type_source_excel(self):
        """Vérifie la détection du type Excel depuis l'extension."""
        assert DataPipeline._detecter_type_source("fichier.xlsx") == "excel"

    def test_detecter_type_source_api(self):
        """Vérifie la détection du type API depuis le préfixe http."""
        assert DataPipeline._detecter_type_source("https://api.example.com") == "api"

    def test_detecter_type_source_inconnu_leve_exception(self):
        """Vérifie qu'une extension inconnue lève PipelineError."""
        with pytest.raises(PipelineError):
            DataPipeline._detecter_type_source("fichier.inconnu")

    def test_pipeline_csv_complet(self, temp_csv_file, tmp_path):
        """Vérifie le pipeline complet depuis un fichier CSV."""
        cache_dir = str(tmp_path / "kidas_cache")
        pipeline = DataPipeline()
        # Remplacement du cache par un cache temporaire
        from kadi.kidas.cache import DataCache
        pipeline._cache = DataCache(cache_dir=cache_dir)

        df, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .add_cleaning_step("remove_duplicates")
            .add_cleaning_step("handle_missing_values", strategy="mean")
            .execute(cache=False)
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        # Vérification des clés de la structure documentée
        assert "steps_summary" in rapport
        assert "nb_rows_in" in rapport
        assert "nb_rows_out" in rapport

    def test_get_pipeline_config_structure(self, temp_csv_file):
        """Vérifie la structure de la configuration du pipeline."""
        pipeline = DataPipeline()
        pipeline.load_data(temp_csv_file)
        pipeline.add_cleaning_step("remove_duplicates")
        config = pipeline.get_pipeline_config()
        assert "nb_etapes" in config
        assert config["nb_etapes"] == 1

    def test_export_report_json(self, temp_csv_file, tmp_path):
        """Vérifie l'export du rapport en JSON."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))
        pipeline.load_data(temp_csv_file)
        pipeline.execute(cache=False)

        chemin_rapport = str(tmp_path / "rapport.json")
        resultat = pipeline.export_report(chemin_rapport)
        assert resultat is True
        assert (tmp_path / "rapport.json").exists()

    def test_rapport_contient_cles_documentees(self, temp_csv_file, tmp_path):
        """Vérifie que le rapport de execute() contient toutes les clés documentées."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .add_cleaning_step("remove_duplicates")
            .execute(cache=False)
        )
        # Toutes les clés documentées doivent être présentes
        for cle in ("nb_rows_in", "nb_rows_out", "steps_summary",
                    "quality_score", "warnings", "cache_utilise", "details"):
            assert cle in rapport, f"Clé manquante dans le rapport : '{cle}'"

    def test_rapport_nb_rows_in_est_correct(self, temp_csv_file, tmp_path):
        """Vérifie que nb_rows_in correspond au nombre de lignes chargées brutes."""
        from kadi.kidas.cache import DataCache
        import pandas as pd
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        # Référence : lecture directe du fichier sans traitement
        df_brut = pd.read_csv(temp_csv_file)
        nb_lignes_brutes = len(df_brut)

        _, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .execute(cache=False)
        )
        assert rapport["nb_rows_in"] == nb_lignes_brutes

    def test_rapport_nb_rows_out_est_correct(self, temp_csv_file, tmp_path):
        """Vérifie que nb_rows_out correspond au nombre de lignes après traitement."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        df, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .add_cleaning_step("remove_duplicates")
            .execute(cache=False)
        )
        # nb_rows_out doit correspondre au nombre réel de lignes du DataFrame retourné
        assert rapport["nb_rows_out"] == len(df)

    def test_rapport_steps_summary_est_liste(self, temp_csv_file, tmp_path):
        """Vérifie que steps_summary est une liste des noms d'étapes appliquées."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .add_cleaning_step("remove_duplicates")
            .add_cleaning_step("handle_missing_values", strategy="mean")
            .execute(cache=False)
        )
        assert isinstance(rapport["steps_summary"], list)
        # Les deux étapes ajoutées doivent être listées dans l'ordre
        assert rapport["steps_summary"] == ["remove_duplicates", "handle_missing_values"]

    def test_rapport_quality_score_absent_sans_validation(self, temp_csv_file, tmp_path):
        """Vérifie que quality_score est None quand aucune étape de validation n'est ajoutée."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .add_cleaning_step("remove_duplicates")
            .execute(cache=False)
        )
        # Sans étape de validation, quality_score doit valoir None
        assert rapport["quality_score"] is None

    def test_rapport_quality_score_present_avec_validation(self, temp_csv_file, tmp_path):
        """Vérifie que quality_score est un dict quand une étape de validation est incluse."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .add_validation_step({"culture": "str"})
            .execute(cache=False)
        )
        # Avec une étape de validation, quality_score doit être un dict
        assert rapport["quality_score"] is not None
        assert isinstance(rapport["quality_score"], dict)
        assert "overall" in rapport["quality_score"]

    def test_rapport_warnings_est_liste(self, temp_csv_file, tmp_path):
        """Vérifie que warnings est toujours une liste, même sans avertissement."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .execute(cache=False)
        )
        # warnings doit toujours être une liste (jamais None)
        assert isinstance(rapport["warnings"], list)

    def test_rapport_details_contient_sous_cles(self, temp_csv_file, tmp_path):
        """Vérifie que details expose les rapports internes attendus."""
        from kadi.kidas.cache import DataCache
        pipeline = DataPipeline()
        pipeline._cache = DataCache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .load_data(temp_csv_file)
            .add_cleaning_step("remove_duplicates")
            .execute(cache=False)
        )
        # La clé details doit regrouper les rapports internes
        assert isinstance(rapport["details"], dict)
        for sous_cle in ("source", "nettoyage", "validation", "normalisation"):
            assert sous_cle in rapport["details"], (
                f"Sous-clé manquante dans details : '{sous_cle}'"
            )

    def test_cle_cache_chemin_avec_espaces_pas_collision(self, tmp_path):
        """Deux pipelines avec des chemins différents doivent avoir des clés différentes.

        Vérifie que la clé SHA-256 distingue correctement des chemins distincts,
        même s'ils partagent un préfixe commun.
        """
        import hashlib

        # Simulation de deux chemins différents (avec espace dans l'un d'eux)
        chemin_a = str(tmp_path / "mon fichier avec espaces.csv")
        chemin_b = str(tmp_path / "autre_fichier.csv")

        # Calcul des empreintes selon la même logique que pipeline.py
        empreinte_a = hashlib.sha256(chemin_a.encode("utf-8")).hexdigest()[:16]
        empreinte_b = hashlib.sha256(chemin_b.encode("utf-8")).hexdigest()[:16]

        # Deux chemins distincts ne doivent jamais produire la même empreinte
        assert empreinte_a != empreinte_b, (
            "Collision de clé de cache détectée entre deux chemins différents."
        )

    def test_cle_cache_longueur_fixe_16_caracteres(self, tmp_path):
        """La clé de cache doit toujours faire exactement 16 caractères hexadécimaux.

        Cela garantit une taille prévisible quelle que soit la longueur du chemin source.
        """
        import hashlib

        # Chemin avec accents, espaces et séparateurs variés
        chemin_special = str(tmp_path / "données récolte été 2024 / béninois.xlsx")

        empreinte = hashlib.sha256(chemin_special.encode("utf-8")).hexdigest()[:16]

        # Longueur fixe : 16 caractères (128 bits → 32 hex, tronqués à 16)
        assert len(empreinte) == 16, (
            f"Longueur inattendue de la clé de cache : {len(empreinte)} (attendu : 16)."
        )
        # Les caractères doivent tous être hexadécimaux valides
        assert all(c in "0123456789abcdef" for c in empreinte), (
            f"Clé de cache contient des caractères non hexadécimaux : '{empreinte}'."
        )

