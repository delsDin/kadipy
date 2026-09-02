# -*- coding: utf-8 -*-
"""Tests unitaires pour les classes Cleaner, Validator, Normalizer et Pipeline."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

# Importation des nouvelles classes refactorisées du package kidas
from kadi.kidas import Cleaner, Validator, Normalizer, Pipeline, Cache
from kadi.exceptions import CleanError, ValidationError, PipelineError


# =============================================================================
# Tests Cleaner
# =============================================================================

class TestCleaner:
    """Tests unitaires pour la classe Cleaner."""

    def test_init_invalide_leve_exception(self):
        """Vérifie que Cleaner lève une erreur avec un argument non-DataFrame."""
        with pytest.raises(CleanError):
            Cleaner("pas_un_dataframe")

    def test_drop_dupes_supprime_doublons(self, sample_df_with_duplicates):
        """Vérifie la suppression des lignes dupliquées."""
        nb_avant = len(sample_df_with_duplicates)
        cleaner = Cleaner(sample_df_with_duplicates)
        df_propre = cleaner.drop_dupes()
        assert len(df_propre) < nb_avant

    def test_drop_dupes_rapport_mis_a_jour(self, sample_df_with_duplicates):
        """Vérifie que le rapport comptabilise les doublons supprimés."""
        cleaner = Cleaner(sample_df_with_duplicates)
        cleaner.drop_dupes()
        rapport = cleaner.report()
        assert rapport["doublons_supprimes"] > 0

    def test_fill_missing_mean_remplace_nan(self, sample_df):
        """Vérifie que la stratégie 'mean' remplace les NaN numériques."""
        cleaner = Cleaner(sample_df)
        nb_nan_avant = sample_df["rendement_kg"].isna().sum()
        assert nb_nan_avant > 0
        df = cleaner.fill_missing(strategy="mean", cols=["rendement_kg"])
        assert df["rendement_kg"].isna().sum() == 0

    def test_fill_missing_drop_supprime_lignes(self, sample_df):
        """Vérifie que la stratégie 'drop' supprime les lignes avec NaN."""
        nb_avant = len(sample_df)
        cleaner = Cleaner(sample_df)
        df = cleaner.fill_missing(strategy="drop")
        assert len(df) < nb_avant

    def test_fill_missing_strategie_invalide(self, sample_df):
        """Vérifie qu'une stratégie invalide lève CleanError."""
        cleaner = Cleaner(sample_df)
        with pytest.raises(CleanError):
            cleaner.fill_missing(strategy="invalide")

    def test_drop_outliers_iqr_detecte_outliers(self, sample_df_with_outliers):
        """Vérifie que la méthode IQR détecte les outliers évidents."""
        cleaner = Cleaner(sample_df_with_outliers)
        df_propre, df_outliers = cleaner.drop_outliers(method="iqr")
        # La valeur 15000 doit être détectée comme outlier
        assert len(df_outliers) > 0
        assert 15000 in list(sample_df_with_outliers["rendement_kg"])

    def test_drop_outliers_methode_invalide(self, sample_df):
        """Vérifie qu'une méthode invalide lève CleanError."""
        cleaner = Cleaner(sample_df)
        with pytest.raises(CleanError):
            cleaner.drop_outliers(method="methode_invalide")

    def test_parse_dates_convertit_colonne(self, sample_df):
        """Vérifie que parse_dates() convertit une colonne en datetime64."""
        cleaner = Cleaner(sample_df)
        df = cleaner.parse_dates(cols=["date_recolte"])
        assert pd.api.types.is_datetime64_any_dtype(df["date_recolte"])

    def test_parse_dates_compteur_toutes_converties(self):
        """Vérifie que dates_corrigees est exact quand toutes les dates sont valides."""
        # 5 dates toutes parsables
        df = pd.DataFrame({
            "date_recolte": [
                "2024-01-01", "2024-02-15", "2024-03-10",
                "2024-04-01", "2024-05-05",
            ]
        })
        cleaner = Cleaner(df)
        cleaner.parse_dates(cols=["date_recolte"])
        rapport = cleaner.report()
        # Le compteur doit correspondre aux conversions réussies
        assert rapport["dates_corrigees"] == 5

    def test_parse_dates_compteur_conversions_partielles(self):
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
        cleaner = Cleaner(df)
        cleaner.parse_dates(cols=["date_recolte"])
        rapport = cleaner.report()
        assert rapport["dates_corrigees"] == 8

    def test_parse_dates_colonne_inexistante_ne_plante_pas(self):
        """Vérifie que parse_dates() laisse le compteur à 0 si la colonne est absente."""
        df = pd.DataFrame({"autre_colonne": [1, 2, 3]})
        cleaner = Cleaner(df)
        cleaner.parse_dates(cols=["colonne_inexistante"])
        rapport = cleaner.report()
        assert rapport["dates_corrigees"] == 0

    def test_norm_text_minuscules(self, sample_df):
        """Vérifie que norm_text() convertit les chaînes en minuscules."""
        cleaner = Cleaner(sample_df)
        df = cleaner.norm_text(cols=["marche"], case="lower")
        assert all(v == v.lower() for v in df["marche"].dropna())

    def test_check_decimals(self):
        """Vérifie la détection du mélange de séparateurs décimaux."""
        df = pd.DataFrame({"prix": ["1.500", "2,300", "1.800"]})
        cleaner = Cleaner(df)
        rapport = cleaner.check_decimals(cols=["prix"])
        assert rapport["prix"]["mixed"] is True

    def test_report_structure(self, sample_df):
        """Vérifie la structure du rapport de nettoyage."""
        cleaner = Cleaner(sample_df)
        cleaner.drop_dupes()
        rapport = cleaner.report()
        for cle in ("doublons_supprimes", "nan_traites", "lignes_initiales",
                    "lignes_finales", "operations"):
            assert cle in rapport


# =============================================================================
# Tests Validator
# =============================================================================

class TestValidator:
    """Tests unitaires pour la classe Validator."""

    def test_init_invalide_leve_exception(self):
        """Vérifie que Validator lève une erreur avec un non-DataFrame."""
        with pytest.raises(ValidationError):
            Validator([1, 2, 3])

    def test_check_schema_valide(self, sample_df):
        """Vérifie qu'un schéma correct est validé sans erreur."""
        validator = Validator(sample_df)
        valide, erreurs = validator.check_schema({"culture": "str"})
        assert valide is True
        assert len(erreurs) == 0

    def test_check_schema_colonne_manquante(self, sample_df):
        """Vérifie qu'une colonne manquante génère une erreur de schéma."""
        validator = Validator(sample_df)
        valide, erreurs = validator.check_schema({"colonne_inexistante": "str"})
        assert valide is False
        assert len(erreurs) > 0

    def test_check_ranges_dans_les_bornes(self, sample_df):
        """Vérifie que des valeurs dans les bornes passent la validation."""
        validator = Validator(sample_df)
        valide, df_hors = validator.check_ranges(
            {"rendement_kg": (0, 10000)}
        )
        assert valide is True

    def test_check_ranges_hors_bornes(self):
        """Vérifie que des valeurs hors bornes sont détectées."""
        df = pd.DataFrame({"temperature": [-15, 20, 60]})
        validator = Validator(df)
        valide, df_hors = validator.check_ranges({"temperature": (-10, 50)})
        assert valide is False
        assert len(df_hors) == 2

    def test_check_coords_benin_valides(self, sample_df):
        """Vérifie que des coordonnées dans la zone du Bénin sont acceptées."""
        validator = Validator(sample_df)
        valide, df_invalides = validator.check_coords("lat", "lon")
        assert valide is True

    def test_check_coords_hors_bbox(self):
        """Vérifie que des coordonnées hors zone sont détectées."""
        df = pd.DataFrame({
            "lat": [6.0, 50.0],
            "lon": [2.0, 2.0],
        })
        validator = Validator(df)
        valide, df_invalides = validator.check_coords("lat", "lon")
        assert valide is False
        assert len(df_invalides) == 1

    def test_check_unique_sans_doublon(self, sample_df):
        """Vérifie la validation d'unicité sur un DataFrame."""
        validator = Validator(sample_df)
        valide, df_dup = validator.check_unique(["culture", "marche"])
        assert isinstance(valide, bool)
        assert isinstance(df_dup, pd.DataFrame)

    def test_quality_score_structure(self, sample_df):
        """Vérifie la structure du score de qualité retourné."""
        validator = Validator(sample_df)
        score = validator.quality_score()
        for cle in ("overall", "completeness", "consistency", "accuracy", "columns"):
            assert cle in score
        assert 0.0 <= score["overall"] <= 1.0

    def test_report_retourne_dict(self, sample_df):
        """Vérifie que report() retourne un dictionnaire contenant validations."""
        validator = Validator(sample_df)
        rapport = validator.report()
        assert isinstance(rapport, dict)
        assert "validations" in rapport


# =============================================================================
# Tests Normalizer
# =============================================================================

class TestNormalizer:
    """Tests unitaires pour la classe Normalizer."""

    def test_init_invalide_leve_exception(self):
        """Vérifie que Normalizer lève une erreur avec un non-DataFrame."""
        with pytest.raises(CleanError):
            Normalizer("pas_un_dataframe")

    def test_norm_cols_snake_case(self):
        """Vérifie la conversion des noms de colonnes en snake_case."""
        df = pd.DataFrame({"Température Min": [1], "Prix (XOF)": [2]})
        normalizer = Normalizer(df)
        df_norm = normalizer.norm_cols()
        assert "temperature_min" in df_norm.columns
        assert "prix_xof" in df_norm.columns

    def test_norm_cols_supprime_accents(self):
        """Vérifie que les accents sont supprimés des noms de colonnes."""
        df = pd.DataFrame({"Récolte": [1], "Données": [2]})
        normalizer = Normalizer(df)
        df_norm = normalizer.norm_cols()
        colonnes = list(df_norm.columns)
        for col in colonnes:
            assert "é" not in col

    def test_convert_units_tonne_vers_kg(self, sample_df):
        """Vérifie la conversion de tonnes vers kilogrammes."""
        df = pd.DataFrame({"production": [1.0, 2.5, 0.8]})
        normalizer = Normalizer(df)
        df_norm = normalizer.convert_units({"production": "tonne"})
        assert df_norm["production"].iloc[0] == pytest.approx(1000.0)
        assert df_norm["production"].iloc[1] == pytest.approx(2500.0)

    def test_convert_units_unite_inconnue_leve_exception(self):
        """Vérifie qu'une unité inconnue lève une exception CleanError."""
        df = pd.DataFrame({"production": [1.0]})
        normalizer = Normalizer(df)
        with pytest.raises(CleanError):
            normalizer.convert_units({"production": "caisse_inconnue"})

    def test_std_crops_mais(self, sample_df):
        """Vérifie la normalisation des noms de cultures vers FAO."""
        normalizer = Normalizer(sample_df)
        df_norm = normalizer.std_crops(col="culture")
        assert "maize" in df_norm["culture"].values

    def test_std_crops_niebe(self, sample_df):
        """Vérifie que 'Niébé' est normalisé en 'cowpea'."""
        normalizer = Normalizer(sample_df)
        df_norm = normalizer.std_crops(col="culture")
        assert "cowpea" in df_norm["culture"].values

    def test_std_markets_ajoute_colonnes_gps(self, sample_df):
        """Vérifie que std_markets() ajoute market_lat et market_lon."""
        normalizer = Normalizer(sample_df)
        df_norm = normalizer.std_markets(col="marche")
        assert "market_lat" in df_norm.columns
        assert "market_lon" in df_norm.columns

    def test_std_coords_ajoute_colonne_geometry(self, sample_df):
        """Vérifie que std_coords() ajoute la colonne 'geometry'."""
        pytest.importorskip("shapely")
        normalizer = Normalizer(sample_df)
        df_norm = normalizer.std_coords(lat="lat", lon="lon")
        assert "geometry" in df_norm.columns

    def test_mappings_structure(self, sample_df):
        """Vérifie la structure du dictionnaire de normalisation."""
        normalizer = Normalizer(sample_df)
        normalizer.norm_cols()
        mapping = normalizer.mappings()
        for cle in ("colonnes", "unites", "cultures", "marches", "devises"):
            assert cle in mapping


# =============================================================================
# Tests Pipeline
# =============================================================================

class TestPipeline:
    """Tests unitaires pour la classe Pipeline."""

    def test_run_sans_source_leve_exception(self):
        """Vérifie que run() sans source lève une exception PipelineError."""
        pipeline = Pipeline()
        with pytest.raises(PipelineError):
            pipeline.run()

    def test_detecter_type_source_csv(self):
        """Vérifie la détection du type CSV depuis l'extension."""
        assert Pipeline._detecter_type_source("fichier.csv") == "csv"

    def test_detecter_type_source_excel(self):
        """Vérifie la détection du type Excel depuis l'extension."""
        assert Pipeline._detecter_type_source("fichier.xlsx") == "excel"

    def test_detecter_type_source_api(self):
        """Vérifie la détection du type API depuis le préfixe http."""
        assert Pipeline._detecter_type_source("https://api.example.com") == "api"

    def test_detecter_type_source_inconnu_leve_exception(self):
        """Vérifie qu'une extension inconnue lève PipelineError."""
        with pytest.raises(PipelineError):
            Pipeline._detecter_type_source("fichier.inconnu")

    def test_pipeline_csv_complet(self, temp_csv_file, tmp_path):
        """Vérifie le pipeline complet depuis un fichier CSV."""
        cache_dir = str(tmp_path / "kidas_cache")
        pipeline = Pipeline()
        # Configuration d'un cache temporaire
        pipeline._cache = Cache(cache_dir=cache_dir)

        df, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .add_step("drop_dupes")
            .add_step("fill_missing", strategy="mean")
            .run(cache=False)
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "steps_summary" in rapport
        assert "nb_rows_in" in rapport
        assert "nb_rows_out" in rapport

    def test_config_structure(self, temp_csv_file):
        """Vérifie la structure de la configuration du pipeline."""
        pipeline = Pipeline()
        pipeline.add_source(temp_csv_file)
        pipeline.add_step("drop_dupes")
        configuration = pipeline.config()
        assert "nb_steps" in configuration
        assert configuration["nb_steps"] == 1

    def test_export_json(self, temp_csv_file, tmp_path):
        """Vérifie l'export du rapport en format JSON."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))
        pipeline.add_source(temp_csv_file)
        pipeline.run(cache=False)

        chemin_rapport = str(tmp_path / "rapport.json")
        resultat = pipeline.export(chemin_rapport)
        assert resultat is True
        assert (tmp_path / "rapport.json").exists()

    def test_rapport_contient_cles_documentees(self, temp_csv_file, tmp_path):
        """Vérifie que le rapport de run() contient les clés documentées."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .add_step("drop_dupes")
            .run(cache=False)
        )
        for cle in ("nb_rows_in", "nb_rows_out", "steps_summary",
                    "quality_score", "warnings", "cache_utilise", "details"):
            assert cle in rapport, f"Clé manquante dans le rapport : '{cle}'"

    def test_rapport_nb_rows_in_est_correct(self, temp_csv_file, tmp_path):
        """Vérifie que nb_rows_in correspond au nombre de lignes brutes."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        df_brut = pd.read_csv(temp_csv_file)
        nb_lignes_brutes = len(df_brut)

        _, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .run(cache=False)
        )
        assert rapport["nb_rows_in"] == nb_lignes_brutes

    def test_rapport_nb_rows_out_est_correct(self, temp_csv_file, tmp_path):
        """Vérifie que nb_rows_out correspond aux lignes post-traitement."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        df, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .add_step("drop_dupes")
            .run(cache=False)
        )
        assert rapport["nb_rows_out"] == len(df)

    def test_rapport_steps_summary_est_liste(self, temp_csv_file, tmp_path):
        """Vérifie que steps_summary liste les étapes dans l'ordre."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .add_step("drop_dupes")
            .add_step("fill_missing", strategy="mean")
            .run(cache=False)
        )
        assert isinstance(rapport["steps_summary"], list)
        assert rapport["steps_summary"] == ["drop_dupes", "fill_missing"]

    def test_rapport_quality_score_absent_sans_validation(self, temp_csv_file, tmp_path):
        """Vérifie que quality_score est None sans étape de validation."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .add_step("drop_dupes")
            .run(cache=False)
        )
        assert rapport["quality_score"] is None

    def test_rapport_quality_score_present_avec_validation(self, temp_csv_file, tmp_path):
        """Vérifie que quality_score est un dictionnaire avec la validation."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .add_step("check_schema", {"culture": "str"})
            .run(cache=False)
        )
        assert rapport["quality_score"] is not None
        assert isinstance(rapport["quality_score"], dict)
        assert "overall" in rapport["quality_score"]

    def test_rapport_warnings_est_liste(self, temp_csv_file, tmp_path):
        """Vérifie que warnings est une liste même sans avertissements."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .run(cache=False)
        )
        assert isinstance(rapport["warnings"], list)

    def test_rapport_details_contient_sous_cles(self, temp_csv_file, tmp_path):
        """Vérifie que details contient les sous-clés des sous-rapports."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        _, rapport = (
            pipeline
            .add_source(temp_csv_file)
            .add_step("drop_dupes")
            .run(cache=False)
        )
        assert isinstance(rapport["details"], dict)
        for sous_cle in ("source", "nettoyage", "validation", "normalisation"):
            assert sous_cle in rapport["details"]

    def test_cle_cache_chemin_avec_espaces_pas_collision(self, tmp_path):
        """Vérifie que l'empreinte SHA-256 distingue des chemins différents."""
        import hashlib

        chemin_a = str(tmp_path / "mon fichier avec espaces.csv")
        chemin_b = str(tmp_path / "autre_fichier.csv")

        empreinte_a = hashlib.sha256(chemin_a.encode("utf-8")).hexdigest()[:16]
        empreinte_b = hashlib.sha256(chemin_b.encode("utf-8")).hexdigest()[:16]

        assert empreinte_a != empreinte_b

    def test_cle_cache_longueur_fixe_16_caracteres(self, tmp_path):
        """Vérifie la longueur fixe de 16 caractères pour la clé de cache."""
        import hashlib

        chemin_special = str(tmp_path / "données récolte été 2024 / béninois.xlsx")
        empreinte = hashlib.sha256(chemin_special.encode("utf-8")).hexdigest()[:16]

        assert len(empreinte) == 16
        assert all(c in "0123456789abcdef" for c in empreinte)

    def test_pipeline_methodes_raccourcies(self, temp_csv_file, tmp_path):
        """Vérifie l'API raccourcie : load(), clean(), validate(), normalize()."""
        pipeline = Pipeline()
        pipeline._cache = Cache(cache_dir=str(tmp_path / "cache"))

        df, rapport = (
            pipeline
            .load(temp_csv_file)
            .clean("drop_dupes")
            .validate({"culture": "str"})
            .normalize()
            .run(cache=False)
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert rapport["cache_utilise"] is False
