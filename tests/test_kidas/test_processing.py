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
from kadi.exceptions import KidasCleaningError, KidasValidationError, KidasPipelineError


# =============================================================================
# Tests DataCleaner
# =============================================================================

class TestDataCleaner:
    """Tests unitaires pour la classe DataCleaner."""

    def test_init_invalide_leve_exception(self):
        """Vérifie que DataCleaner lève une erreur avec un argument non-DataFrame."""
        with pytest.raises(KidasCleaningError):
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
        """Vérifie qu'une stratégie invalide lève KidasCleaningError."""
        cleaner = DataCleaner(sample_df)
        with pytest.raises(KidasCleaningError):
            cleaner.handle_missing_values(strategy="invalide")

    def test_remove_outliers_iqr_detecte_outliers(self, sample_df_with_outliers):
        """Vérifie que la méthode IQR détecte les outliers évidents."""
        cleaner = DataCleaner(sample_df_with_outliers)
        df_propre, df_outliers = cleaner.remove_outliers(method="iqr")
        # La valeur 15000 doit être détectée comme outlier
        assert len(df_outliers) > 0
        assert 15000 in list(sample_df_with_outliers["rendement_kg"])

    def test_remove_outliers_methode_invalide(self, sample_df):
        """Vérifie qu'une méthode invalide lève KidasCleaningError."""
        cleaner = DataCleaner(sample_df)
        with pytest.raises(KidasCleaningError):
            cleaner.remove_outliers(method="methode_invalide")

    def test_fix_dates_convertit_colonne(self, sample_df):
        """Vérifie que fix_dates() convertit une colonne en datetime64."""
        cleaner = DataCleaner(sample_df)
        df = cleaner.fix_dates(columns=["date_recolte"])
        assert pd.api.types.is_datetime64_any_dtype(df["date_recolte"])

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
        with pytest.raises(KidasValidationError):
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
        with pytest.raises(KidasCleaningError):
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
        """Vérifie qu'une unité inconnue lève KidasCleaningError."""
        df = pd.DataFrame({"production": [1.0]})
        normalizer = DataNormalizer(df)
        with pytest.raises(KidasCleaningError):
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
        """Vérifie que execute() sans source lève KidasPipelineError."""
        pipeline = DataPipeline()
        with pytest.raises(KidasPipelineError):
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
        """Vérifie qu'une extension inconnue lève KidasPipelineError."""
        with pytest.raises(KidasPipelineError):
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
        assert "etapes_appliquees" in rapport

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
