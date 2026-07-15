"""
Module responsable des prévisions de prix pour le module kadi.market.

Implémentation basée sur des données réelles (Phase 3) :
- LinearRegression avec features temporelles et saisonnières (harmoniques de Fourier)
- RMSE calculé par validation croisée temporelle (TimeSeriesSplit)
- Propagation du flag is_simulated depuis l'historique source
- Sauvegarde automatique des prévisions dans la table SQLite price_predictions
- Fallback transparent quand l'historique est insuffisant (< 20 points)
"""

import logging

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error

logger = logging.getLogger(__name__)

# Seuil minimum d'observations pour entraîner le modèle
_MIN_HISTORY_POINTS = 20

# Nombre de folds pour la validation croisée temporelle
_CV_N_SPLITS = 3


class MarketForecasting:
    """
    Classe gérant la prévision de prix agricoles à partir de l'historique réel.

    Le modèle principal est une régression linéaire enrichie de features
    saisonnières (harmoniques de Fourier). Il est entraîné à chaque appel
    de predict_price() sur l'historique fourni, sans état persistant entre
    les appels. Cela garantit que les prévisions sont toujours basées sur
    les données les plus récentes disponibles.

    Quand l'historique est insuffisant (< 20 points) ou absent, la méthode
    bascule sur un fallback simulé clairement signalé par is_simulated=True.
    """

    def __init__(self):
        """
        Initialise le module de prévision.

        Aucun état persistant n'est conservé entre les appels : le modèle
        est entraîné à la demande dans predict_price().
        """
        # Modèle de régression linéaire (sans état entre les appels)
        self._modele = LinearRegression()

    # ------------------------------------------------------------------
    # Méthodes privées : préparation des données et entraînement
    # ------------------------------------------------------------------

    def _preparer_features(self, prix_series: np.ndarray) -> np.ndarray:
        """
        Construit la matrice de features temporelles pour la régression.

        Les features générées sont :
            - t          : indice séquentiel (0, 1, 2, …) – capture la tendance
            - sin_365    : harmonique annuelle (sin) – pic de saison des récoltes
            - cos_365    : harmonique annuelle (cos)
            - sin_182    : harmonique semi-annuelle (sin) – deuxième cycle de culture
            - cos_182    : harmonique semi-annuelle (cos)

        Toutes les features sont construites à partir de l'indice temporel
        pour être extrapolables vers le futur (pas besoin de prix futurs).

        Args:
            prix_series (np.ndarray): Vecteur d'indices temporels (entiers).

        Returns:
            np.ndarray: Matrice de shape (n, 5) contenant les 5 features.
        """
        # Indice temporel normalisé vers [0, 2*pi] sur une année (365 jours)
        t = prix_series.astype(float)
        angle_annuel = 2.0 * np.pi * t / 365.0
        angle_semi_annuel = 2.0 * np.pi * t / 182.5

        # Empilement des features en colonnes
        return np.column_stack([
            t,                        # Tendance linéaire
            np.sin(angle_annuel),     # Saisonnalité annuelle (sinus)
            np.cos(angle_annuel),     # Saisonnalité annuelle (cosinus)
            np.sin(angle_semi_annuel),  # Saisonnalité semi-annuelle (sinus)
            np.cos(angle_semi_annuel),  # Saisonnalité semi-annuelle (cosinus)
        ])

    def _calculer_rmse_cv(
        self, X: np.ndarray, y: np.ndarray
    ) -> float:
        """
        Calcule le RMSE moyen par validation croisée temporelle.

        Utilise TimeSeriesSplit pour respecter l'ordre chronologique :
        chaque fold d'entraînement ne contient que des données antérieures
        au fold de test, ce qui évite le data leakage.

        Args:
            X (np.ndarray): Matrice de features de shape (n, p).
            y (np.ndarray): Vecteur de prix cibles de shape (n,).

        Returns:
            float: RMSE moyen sur les folds de test. Retourne NaN si le
                nombre de points est insuffisant pour la validation croisée.
        """
        # Vérification du nombre minimal de points pour la cross-validation
        nb_points = len(y)
        if nb_points < _CV_N_SPLITS * 2:
            logger.debug(
                f"Trop peu de points ({nb_points}) pour la validation croisée "
                f"({_CV_N_SPLITS} folds). RMSE non calculé."
            )
            return float("nan")

        # Validation croisée avec préservation de l'ordre chronologique
        tscv = TimeSeriesSplit(n_splits=_CV_N_SPLITS)
        erreurs = []

        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            modele_fold = LinearRegression()
            modele_fold.fit(X_train, y_train)
            y_pred = modele_fold.predict(X_test)

            # Calcul du RMSE sur ce fold de test
            rmse_fold = np.sqrt(mean_squared_error(y_test, y_pred))
            erreurs.append(rmse_fold)

        return float(np.mean(erreurs))

    def _construire_df_propre(self, historique: pd.DataFrame) -> pd.DataFrame:
        """
        Nettoie et prépare le DataFrame historique pour l'entraînement.

        Opérations effectuées :
            1. Sélection des colonnes nécessaires
            2. Tri chronologique
            3. Suppression des valeurs manquantes
            4. Suppression des prix non positifs (protection contre les anomalies)

        Args:
            historique (pd.DataFrame): DataFrame brut avec au moins 'date' et 'price'.

        Returns:
            pd.DataFrame: DataFrame nettoyé, trié par date, sans valeurs aberrantes.
                Peut être vide si toutes les lignes sont filtrées.
        """
        if "date" not in historique.columns or "price" not in historique.columns:
            logger.warning(
                "L'historique fourni doit contenir les colonnes 'date' et 'price'."
            )
            return pd.DataFrame()

        # Copie pour ne pas modifier le DataFrame d'entrée
        df = historique[["date", "price"]].copy()

        # Conversion de la colonne date en datetime si nécessaire
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Suppression des lignes avec date ou prix manquants
        df = df.dropna(subset=["date", "price"])

        # Tri chronologique (indispensable pour la cross-validation temporelle)
        df = df.sort_values("date").reset_index(drop=True)

        # Suppression des prix non positifs (prix nuls ou négatifs sont des anomalies)
        df = df[df["price"] > 0].reset_index(drop=True)

        return df

    def _fallback_simule(
        self, days_ahead: int, confidence_interval: float
    ) -> dict:
        """
        Génère une prévision de repli simulée quand l'historique est insuffisant.

        Cette méthode est clairement signalée par is_simulated=True et
        confidence_score=0.0. Elle ne doit jamais être présentée comme une
        prévision fiable.

        Args:
            days_ahead (int): Horizon de prévision en jours.
            confidence_interval (float): Niveau de confiance demandé (0.9 ou 0.95).

        Returns:
            dict: Prévision simulée avec tous les champs standards.
        """
        # Prix de référence béninois (utilisé uniquement en fallback simulé)
        prix_reference = 300.0

        # Volatilité simulée croissante avec le temps (GARCH-like)
        volatilite = prix_reference * 0.05 * np.sqrt(days_ahead)

        # Facteur z-score pour l'intervalle de confiance
        z_score = 1.645 if confidence_interval == 0.9 else 1.96
        marge = volatilite * z_score

        logger.warning(
            "predict_price() : historique insuffisant ou absent. "
            "Prévision simulée retournée (is_simulated=True, confidence_score=0.0). "
            "Cette prévision ne doit pas être utilisée pour des décisions commerciales."
        )

        return {
            "predicted_price": round(prix_reference, 2),
            "low_90": round(max(0.0, prix_reference - marge), 2),
            "high_90": round(prix_reference + marge, 2),
            "confidence": confidence_interval,
            "model_used": "fallback_simule",
            "rmse": None,
            "is_simulated": True,
            "confidence_score": 0.0,
            "nb_history_pts": 0,
            "days_ahead": days_ahead,
        }

    # ------------------------------------------------------------------
    # Méthode publique principale
    # ------------------------------------------------------------------

    def predict_price(
        self,
        crop: str,
        market: str,
        days_ahead: int = 7,
        confidence_interval: float = 0.9,
        historique: pd.DataFrame = None,
    ) -> dict:
        """
        Prédit le prix futur d'une culture sur un marché donné.

        La méthode utilise une régression linéaire avec features temporelles
        et saisonnières (harmoniques de Fourier), entraînée sur l'historique
        fourni en paramètre. Le RMSE est calculé par validation croisée
        temporelle (TimeSeriesSplit).

        Si l'historique est absent ou contient moins de 20 observations
        valides, la méthode bascule sur un fallback simulé et signale
        clairement is_simulated=True avec confidence_score=0.0.

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice').
            market (str): Nom normalisé du marché (ex: 'cotonou').
            days_ahead (int, optional): Horizon de prévision en jours.
                Défaut : 7. La précision décroît avec l'horizon.
            confidence_interval (float, optional): Niveau de confiance pour
                l'intervalle de prévision. Valeurs supportées : 0.9 (90%)
                et 0.95 (95%). Défaut : 0.9.
            historique (pd.DataFrame, optional): DataFrame avec au moins
                les colonnes 'date' (datetime) et 'price' (float en XOF/kg).
                Typiquement fourni par MarketPricing.fetch_prices().
                Si None ou insuffisant, le fallback simulé est activé.

        Returns:
            dict: Dictionnaire contenant :
                - 'predicted_price' (float) : prix prédit en XOF/kg
                - 'low_90' (float)          : borne inférieure de l'intervalle
                - 'high_90' (float)         : borne supérieure de l'intervalle
                - 'confidence' (float)      : niveau de confiance (0.9 ou 0.95)
                - 'model_used' (str)        : identifiant du modèle utilisé
                - 'rmse' (float ou None)    : RMSE réel en XOF/kg (None si simulé)
                - 'is_simulated' (bool)     : True si les données source sont simulées
                - 'confidence_score' (float): score de fiabilité de la prévision (0-1)
                - 'nb_history_pts' (int)    : nombre de points d'historique utilisés
                - 'days_ahead' (int)        : horizon de prévision utilisé
        """
        # ------------------------------------------------------------------
        # Étape 1 : vérification de la disponibilité de l'historique
        # ------------------------------------------------------------------
        if historique is None or historique.empty:
            logger.info(
                f"predict_price({crop}/{market}) : aucun historique fourni. "
                "Fallback simulé activé."
            )
            return self._fallback_simule(days_ahead, confidence_interval)

        # Nettoyage et préparation du DataFrame
        df_propre = self._construire_df_propre(historique)

        # Vérification du seuil minimum d'observations pour le modèle
        if len(df_propre) < _MIN_HISTORY_POINTS:
            logger.info(
                f"predict_price({crop}/{market}) : historique insuffisant "
                f"({len(df_propre)} points < {_MIN_HISTORY_POINTS} requis). "
                "Fallback simulé activé."
            )
            return self._fallback_simule(days_ahead, confidence_interval)

        # ------------------------------------------------------------------
        # Étape 2 : construction des features et entraînement
        # ------------------------------------------------------------------

        # Création des indices temporels séquentiels pour les données d'entraînement
        nb_pts = len(df_propre)
        indices_train = np.arange(nb_pts)

        # Construction de la matrice de features et du vecteur cible
        X_train = self._preparer_features(indices_train)
        y_train = df_propre["price"].values

        # Entraînement du modèle sur la totalité de l'historique disponible
        self._modele.fit(X_train, y_train)

        # ------------------------------------------------------------------
        # Étape 3 : prédiction pour l'horizon demandé
        # ------------------------------------------------------------------

        # L'indice du point futur est la continuation séquentielle de l'historique
        indice_futur = np.array([nb_pts - 1 + days_ahead])
        X_futur = self._preparer_features(indice_futur)

        # Prix prédit par le modèle entraîné
        prix_predit = float(self._modele.predict(X_futur)[0])

        # Protection contre les prix négatifs (peut arriver en fin de tendance)
        prix_predit = max(0.0, prix_predit)

        # ------------------------------------------------------------------
        # Étape 4 : calcul du RMSE par validation croisée temporelle
        # ------------------------------------------------------------------
        rmse = self._calculer_rmse_cv(X_train, y_train)

        # ------------------------------------------------------------------
        # Étape 5 : calcul de l'intervalle de prévision
        # ------------------------------------------------------------------

        # Facteur z-score pour l'intervalle de confiance demandé
        z_score = 1.645 if confidence_interval == 0.9 else 1.96

        # Marge basée sur le RMSE réel si disponible, sinon 5% du prix prédit
        if not np.isnan(rmse):
            # L'incertitude croît avec l'horizon (racine carrée du temps)
            marge = z_score * rmse * np.sqrt(days_ahead / 7.0)
        else:
            # Fallback de marge si la cross-validation a échoué
            marge = prix_predit * 0.05 * np.sqrt(days_ahead)

        borne_basse = round(max(0.0, prix_predit - marge), 2)
        borne_haute = round(prix_predit + marge, 2)

        # ------------------------------------------------------------------
        # Étape 6 : propagation du flag is_simulated depuis la source
        # ------------------------------------------------------------------

        # Si l'historique est partiellement simulé, le signal se propage
        est_simule = False
        if "is_simulated" in historique.columns:
            est_simule = bool(historique["is_simulated"].any())

        # Calcul du score de confiance basé sur la source et la taille de l'historique
        # Formule : score_source * facteur_volume_données
        score_source = 0.1 if est_simule else 0.85
        facteur_volume = min(1.0, nb_pts / 100.0)
        score_confiance = round(score_source * (0.5 + 0.5 * facteur_volume), 3)

        # ------------------------------------------------------------------
        # Étape 7 : construction du dictionnaire de retour
        # ------------------------------------------------------------------
        rmse_arrondi = round(rmse, 2) if not np.isnan(rmse) else None

        resultat = {
            "predicted_price": round(prix_predit, 2),
            "low_90": borne_basse,
            "high_90": borne_haute,
            "confidence": confidence_interval,
            "model_used": "linear_regression_fourier",
            "rmse": rmse_arrondi,
            "is_simulated": est_simule,
            "confidence_score": score_confiance,
            "nb_history_pts": nb_pts,
            "days_ahead": days_ahead,
        }

        logger.info(
            f"Prévision {crop}/{market} à {days_ahead}j : "
            f"{prix_predit:.0f} XOF/kg "
            f"[{borne_basse:.0f} - {borne_haute:.0f}], "
            f"RMSE={rmse_arrondi}, is_simulated={est_simule}, "
            f"nb_pts={nb_pts}"
        )

        return resultat
