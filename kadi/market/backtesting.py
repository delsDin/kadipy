# -*- coding: utf-8 -*-
"""
Module de backtesting des prévisions de prix agricoles pour KadiPy.

Principe :
    1. Prendre un historique de prix (N jours).
    2. Couper l'historique à J-k (point de prévision simulé).
    3. Prédire les k jours suivants avec MarketForecasting.predict_price().
    4. Comparer les prédictions aux prix réels observés.
    5. Calculer les métriques d'erreur : MAE, RMSE, MAPE et précision
       directionnelle (pourcentage de bonnes directions hausse/baisse).

Usage typique :
    >>> from kadi.market.backtesting import MarketBacktester
    >>> from kadi.market.forecasting import MarketForecasting
    >>> backtester = MarketBacktester(MarketForecasting())
    >>> resultats = backtester.run("maize", "cotonou", window_days=90,
    ...                           horizon_days=7, nb_fenetre=5)
    >>> rapport = backtester.summary_report()
    >>> print(rapport["mae_moyen"])
"""

import logging

import numpy as np
import pandas as pd

from kadi.market.forecasting import MarketForecasting

# Logger du module backtesting
logger = logging.getLogger(__name__)

# Nombre minimal d'observations pour qu'une fenêtre de test soit valide
_MIN_POINTS_FENETRE = 20


class MarketBacktester:
    """Évalue a posteriori la qualité des prévisions de prix de MarketForecasting.

    Le backtester simule des prévisions passées en coupant l'historique à
    différents points, en prédisant vers l'avant, puis en comparant avec les
    prix réellement observés. Cela permet de mesurer objectivement la fiabilité
    du modèle sur des données non vues.

    Attributs:
        _forecaster (MarketForecasting): Instance du module de prévision.
        _resultats (list[dict]): Liste des résultats de chaque fenêtre.
    """

    def __init__(self, forecaster: MarketForecasting = None) -> None:
        """Initialise le backtester avec un module de prévision.

        Args:
            forecaster (MarketForecasting, optional): Instance de
                MarketForecasting à évaluer. Si None, une instance par défaut
                est créée automatiquement.
        """
        # Module de prévision à évaluer (instance par défaut si non fourni)
        self._forecaster = forecaster if forecaster is not None else MarketForecasting()

        # Stockage des résultats par fenêtre (rempli par run())
        self._resultats: list = []

    # ------------------------------------------------------------------
    # Méthodes privées : métriques d'erreur
    # ------------------------------------------------------------------

    @staticmethod
    def _calculer_mae(y_reel: np.ndarray, y_pred: np.ndarray) -> float:
        """Calcule la Mean Absolute Error (MAE) entre prévisions et réalisations.

        Args:
            y_reel (np.ndarray): Valeurs observées.
            y_pred (np.ndarray): Valeurs prédites.

        Returns:
            float: MAE en XOF/kg. Retourne NaN si les tableaux sont vides.
        """
        # Protection contre les tableaux vides
        if len(y_reel) == 0:
            return float("nan")

        # Moyenne des erreurs absolues
        return float(np.mean(np.abs(y_reel - y_pred)))

    @staticmethod
    def _calculer_rmse(y_reel: np.ndarray, y_pred: np.ndarray) -> float:
        """Calcule la Root Mean Square Error (RMSE).

        Args:
            y_reel (np.ndarray): Valeurs observées.
            y_pred (np.ndarray): Valeurs prédites.

        Returns:
            float: RMSE en XOF/kg. Retourne NaN si les tableaux sont vides.
        """
        # Protection contre les tableaux vides
        if len(y_reel) == 0:
            return float("nan")

        # Racine carrée de la moyenne des carrés des erreurs
        return float(np.sqrt(np.mean((y_reel - y_pred) ** 2)))

    @staticmethod
    def _calculer_mape(y_reel: np.ndarray, y_pred: np.ndarray) -> float:
        """Calcule la Mean Absolute Percentage Error (MAPE) en pourcentage.

        Les observations avec un prix réel nul sont exclues du calcul pour
        éviter les divisions par zéro.

        Args:
            y_reel (np.ndarray): Valeurs observées (prix réels en XOF/kg).
            y_pred (np.ndarray): Valeurs prédites (prix en XOF/kg).

        Returns:
            float: MAPE en pourcentage (0-100). Retourne NaN si aucune
                observation valide (prix réel non nul).
        """
        # Masque pour exclure les prix réels nuls (division par zéro)
        masque_valide = y_reel != 0
        if not masque_valide.any():
            return float("nan")

        # MAPE calculé uniquement sur les observations valides
        y_reel_valide = y_reel[masque_valide]
        y_pred_valide = y_pred[masque_valide]

        return float(np.mean(np.abs((y_reel_valide - y_pred_valide) / y_reel_valide)) * 100)

    @staticmethod
    def _calculer_precision_directionnelle(
        y_reel: np.ndarray, y_pred: np.ndarray
    ) -> float:
        """Calcule le pourcentage de bonnes prédictions directionnelles.

        La direction est correcte si le modèle prédit une hausse (ou baisse)
        et que le prix réel monte (ou baisse) effectivement par rapport au
        dernier prix observé dans la fenêtre d'entraînement.

        Args:
            y_reel (np.ndarray): Valeurs observées.
            y_pred (np.ndarray): Valeurs prédites.

        Returns:
            float: Pourcentage de bonnes directions (0-100). Retourne NaN
                si moins de 2 observations sont disponibles.
        """
        # On a besoin d'au moins 2 points pour mesurer une direction
        if len(y_reel) < 2:
            return float("nan")

        # Direction réelle : 1 si hausse, -1 si baisse, 0 si stable
        direction_reelle = np.sign(np.diff(y_reel))
        direction_predite = np.sign(np.diff(y_pred))

        # Proportion de directions identiques
        return float(np.mean(direction_reelle == direction_predite) * 100)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def run(
        self,
        crop: str,
        market: str,
        historique: pd.DataFrame,
        window_days: int = 90,
        horizon_days: int = 7,
        nb_fenetres: int = 5,
    ) -> list:
        """Exécute le backtesting par fenêtres glissantes sur l'historique fourni.

        Pour chaque fenêtre, la méthode :
            1. Coupe l'historique au point de prévision.
            2. Entraîne le modèle sur la fenêtre d'entraînement.
            3. Prédit les horizon_days jours suivants.
            4. Compare avec les prix réels observés (fenêtre de test).
            5. Calcule les métriques (MAE, RMSE, MAPE, direction).

        Args:
            crop (str): Code de la culture à évaluer (ex: 'maize', 'rice').
            market (str): Nom du marché (ex: 'cotonou', 'parakou').
            historique (pd.DataFrame): DataFrame avec colonnes 'date' (datetime)
                et 'price' (float en XOF/kg), trié par ordre chronologique.
            window_days (int, optional): Taille de la fenêtre d'entraînement
                en jours. Défaut : 90.
            horizon_days (int, optional): Horizon de prévision en jours.
                Défaut : 7.
            nb_fenetres (int, optional): Nombre de fenêtres glissantes à
                évaluer. Défaut : 5.

        Returns:
            list[dict]: Liste de dictionnaires, un par fenêtre évaluée.
                Chaque dictionnaire contient :
                - 'fenetre'         (int)   : Numéro de la fenêtre (1-indexé).
                - 'date_fin_train'  (str)   : Date de coupure (fin de l'entrainement).
                - 'nb_train_pts'    (int)   : Nombre de points d'entraînement.
                - 'prix_predit'     (float) : Prix prédit par le modèle.
                - 'prix_reel_moyen' (float) : Moyenne des prix réels dans la fenêtre test.
                - 'mae'             (float) : MAE en XOF/kg.
                - 'rmse'            (float) : RMSE en XOF/kg.
                - 'mape'            (float) : MAPE en pourcentage.
                - 'precision_dir'   (float) : Précision directionnelle (%).
                - 'is_simulated'    (bool)  : True si la prévision est simulée.
        """
        # Réinitialisation des résultats pour une nouvelle exécution
        self._resultats = []

        # Vérification des colonnes obligatoires
        if "date" not in historique.columns or "price" not in historique.columns:
            logger.warning(
                "Backtesting : l'historique doit contenir les colonnes "
                "'date' et 'price'. Aucun résultat produit."
            )
            return self._resultats

        # Copie et tri chronologique de l'historique
        df = historique[["date", "price"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = df.dropna(subset=["price"])

        # Nombre total de points disponibles
        nb_total = len(df)

        # Taille minimale pour exécuter une fenêtre
        taille_min = window_days + horizon_days
        if nb_total < taille_min:
            logger.warning(
                "Backtesting : historique trop court (%d points) pour "
                "window_days=%d + horizon_days=%d. Ajustez les paramètres.",
                nb_total, window_days, horizon_days,
            )
            return self._resultats

        # Calcul des positions de départ de chaque fenêtre glissante
        # On distribue les fenetres uniformément sur l'historique disponible
        positions_fin_train = np.linspace(
            window_days,
            nb_total - horizon_days,
            nb_fenetres,
            dtype=int,
        )

        logger.info(
            "Backtesting %s/%s : %d fenêtres, window=%d j, horizon=%d j.",
            crop, market, nb_fenetres, window_days, horizon_days,
        )

        # Évaluation de chaque fenêtre
        for idx, pos_fin in enumerate(positions_fin_train, start=1):
            # Fenêtre d'entraînement : [pos_fin - window_days, pos_fin[
            debut_train = max(0, pos_fin - window_days)
            df_train = df.iloc[debut_train:pos_fin].copy()

            # Fenêtre de test : [pos_fin, pos_fin + horizon_days[
            fin_test = min(pos_fin + horizon_days, nb_total)
            df_test = df.iloc[pos_fin:fin_test].copy()

            # Saut si l'une des fenêtres est trop petite
            if len(df_train) < _MIN_POINTS_FENETRE or df_test.empty:
                logger.debug(
                    "Fenêtre %d ignorée : train=%d pts, test=%d pts.",
                    idx, len(df_train), len(df_test),
                )
                continue

            # Appel au modèle de prévision avec l'historique de la fenêtre
            resultat_pred = self._forecaster.predict_price(
                crop=crop,
                market=market,
                days_ahead=horizon_days,
                historique=df_train,
            )

            # Prix prédit et prix réels observés dans la fenêtre de test
            prix_predit = resultat_pred.get("predicted_price", float("nan"))
            y_reel = df_test["price"].values

            # Construction d'un vecteur de prévisions constant pour le calcul
            # des métriques (le modèle retourne une seule valeur scalaire)
            y_pred = np.full(len(y_reel), prix_predit)

            # Calcul des métriques
            mae = self._calculer_mae(y_reel, y_pred)
            rmse = self._calculer_rmse(y_reel, y_pred)
            mape = self._calculer_mape(y_reel, y_pred)
            precision_dir = self._calculer_precision_directionnelle(y_reel, y_pred)

            # Date de coupure (fin de la fenêtre d'entraînement)
            date_fin_train = str(df_train["date"].iloc[-1].date())

            # Enregistrement du résultat de cette fenêtre
            self._resultats.append({
                "fenetre": idx,
                "date_fin_train": date_fin_train,
                "nb_train_pts": len(df_train),
                "prix_predit": round(prix_predit, 1),
                "prix_reel_moyen": round(float(np.mean(y_reel)), 1),
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "mape": round(mape, 2),
                "precision_dir": round(precision_dir, 1),
                "is_simulated": resultat_pred.get("is_simulated", True),
            })

            logger.debug(
                "Fenêtre %d/%d (%s) : MAE=%.1f, RMSE=%.1f, MAPE=%.1f%%, Dir=%.0f%%.",
                idx, nb_fenetres, date_fin_train, mae, rmse, mape, precision_dir,
            )

        logger.info(
            "Backtesting terminé : %d fenêtres évaluées sur %d.",
            len(self._resultats), nb_fenetres,
        )

        return self._resultats

    def summary_report(self) -> dict:
        """Produit un rapport récapitulatif agrégé sur toutes les fenêtres évaluées.

        Les métriques (MAE, RMSE, MAPE, précision directionnelle) sont moyennées
        sur toutes les fenêtres dont les résultats sont valides (non NaN).

        Returns:
            dict: Rapport agrégé contenant :
                - 'nb_fenetres_evaluees' (int)   : Nombre de fenêtres évaluées.
                - 'mae_moyen'            (float) : MAE moyen en XOF/kg.
                - 'rmse_moyen'           (float) : RMSE moyen en XOF/kg.
                - 'mape_moyen'           (float) : MAPE moyen en pourcentage.
                - 'precision_dir_moy'    (float) : Précision directionnelle moyenne (%).
                - 'pct_simule'           (float) : Pourcentage de fenêtres simulées.
                - 'meilleure_fenetre'    (dict)  : Fenêtre avec la MAE la plus faible.
                - 'pire_fenetre'         (dict)  : Fenêtre avec la MAE la plus élevée.
                - 'details'              (list)  : Liste complète des résultats par fenêtre.

        Raises:
            RuntimeError: Si run() n'a pas encore été appelé ou n'a produit
                aucun résultat.
        """
        # Vérification qu'un backtesting a bien été exécuté
        if not self._resultats:
            raise RuntimeError(
                "Aucun résultat disponible. Appelez run() avant summary_report()."
            )

        # Extraction des métriques valides (non NaN)
        maes = [r["mae"] for r in self._resultats if not np.isnan(r["mae"])]
        rmses = [r["rmse"] for r in self._resultats if not np.isnan(r["rmse"])]
        mapes = [r["mape"] for r in self._resultats if not np.isnan(r["mape"])]
        dirs = [r["precision_dir"] for r in self._resultats if not np.isnan(r["precision_dir"])]

        # Pourcentage de fenêtres dont les prévisions sont simulées
        nb_simule = sum(1 for r in self._resultats if r["is_simulated"])
        pct_simule = round(nb_simule / len(self._resultats) * 100, 1)

        # Identification de la meilleure et de la pire fenêtres (selon MAE)
        fenetres_valides = [r for r in self._resultats if not np.isnan(r["mae"])]
        meilleure = min(fenetres_valides, key=lambda r: r["mae"]) if fenetres_valides else None
        pire = max(fenetres_valides, key=lambda r: r["mae"]) if fenetres_valides else None

        return {
            "nb_fenetres_evaluees": len(self._resultats),
            "mae_moyen": round(float(np.mean(maes)), 2) if maes else float("nan"),
            "rmse_moyen": round(float(np.mean(rmses)), 2) if rmses else float("nan"),
            "mape_moyen": round(float(np.mean(mapes)), 2) if mapes else float("nan"),
            "precision_dir_moy": round(float(np.mean(dirs)), 1) if dirs else float("nan"),
            "pct_simule": pct_simule,
            "meilleure_fenetre": meilleure,
            "pire_fenetre": pire,
            "details": self._resultats,
        }
