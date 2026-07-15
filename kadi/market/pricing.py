"""
Module responsable de l'agrégation multi-sources, de la normalisation
des données de marché, et de la détection d'anomalies de prix.
"""

import pandas as pd
import numpy as np
import datetime
import logging

from kadi.market._normalization import (
    EXCHANGE_RATES_DEFAULT,
    get_container_weight_kg,
)

logger = logging.getLogger(__name__)

# Taux de change par défaut (remplacés par config.EXCHANGE_RATES si disponibles)
_EXCHANGE_RATES = EXCHANGE_RATES_DEFAULT


class MarketPricing:
    """
    Classe gérant l'ingestion, la normalisation et la détection d'anomalies
    pour les données de prix de marché agricole au Bénin.
    """

    def __init__(self, wfp_client=None):
        """
        Initialise le module de tarification.

        Args:
            wfp_client (WFPDataBridgesClient, optional): Instance de WFPDataBridgesClient pour récupérer les données.
                Si None, le module génère des données de simulation en fallback.
        """
        # Instance du client WFP DataBridges
        self.wfp_client = wfp_client

    def fetch_prices(self, crop: str, market: str, days_back: int = 365) -> pd.DataFrame:
        """
        Récupère les prix historiques pour une culture et un marché donnés.

        Le DataFrame retourné contient toujours une colonne ``is_simulated``
        indiquant si les données proviennent d'une source réelle (False)
        ou d'une simulation de secours (True).

        Args:
            crop (str): Code de la culture (ex: 'maize', 'rice').
            market (str): Nom normalisé du marché (ex: 'cotonou').
            days_back (int, optional): Nombre de jours d'historique. Défaut à 365.

        Returns:
            pd.DataFrame: DataFrame avec 'date', 'price', 'unit', 'is_simulated'.
        """
        # Calcul de la plage de dates pour la requête API
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days_back)
        time_range = (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

        if self.wfp_client is not None:
            # Appel au client WFP (qui gère lui-même le retry, le cache et le fallback)
            df_prices = self.wfp_client.get_market_prices(market, crop, time_range)
        else:
            # Pas de client configuré : on génère des données de simulation
            logger.warning(
                "Aucun client WFP configuré. Données simulées utilisées pour "
                f"{crop} / {market}."
            )
            dates = pd.date_range(end=end_date, periods=days_back, freq="D")
            prix_aleatoires = np.random.normal(loc=300, scale=20, size=days_back)
            maintenant = datetime.datetime.now(datetime.timezone.utc).isoformat()
            df_prices = pd.DataFrame(
                {
                    "date": dates,
                    "price": prix_aleatoires,
                    "unit": "XOF/kg",
                    # Champs standards attendus par le reste du module
                    "is_simulated": True,
                    "source": "simulated",
                    "fetched_at": maintenant,
                    "confidence_score": 0.1,
                }
            )

        return df_prices

    def normalize_units(self, value: float, unit_orig: str, crop: str = None) -> float:
        """
        Convertit une valeur de prix vers le standard XOF/kg.

        Gère les conversions suivantes :
        - XOF/Tonne  -> XOF/kg (division par 1000)
        - USD/kg     -> XOF/kg (multiplication par le taux de change)
        - EUR/kg     -> XOF/kg (multiplication par le taux de change)
        - XOF/sac    -> XOF/kg (division par le poids du sac en kg)
        - XOF/boisseau -> XOF/kg (division par le poids du boisseau)
        - XOF/tine   -> XOF/kg
        - XOF/caisse -> XOF/kg (pour les produits frais comme la tomate)
        - XOF/kg     -> sans changement (déjà à l'unité standard)

        Si l'unité est inconnue, la valeur est retournée sans modification
        et un avertissement est enregistré.

        Args:
            value (float): La valeur du prix à convertir.
            unit_orig (str): L'unité d'origine (ex: 'XOF/Tonne', 'USD/kg', 'XOF/sac').
            crop (str, optional): Code de la culture, utilisé pour les poids
                de contenants spécifiques (ex: poids d'un sac de maïs vs riz).

        Returns:
            float: Le prix normalisé en XOF/kg.
        """
        valeur = float(value)

        # Normalisation de l'unité pour la comparaison
        unite = unit_orig.strip().lower()

        # --- Conversion des tonnes ---
        if "tonne" in unite or "/t" == unite[-2:]:
            # 1 tonne = 1000 kg
            return valeur / 1000.0

        # --- Conversion des devises étrangères ---
        if unite.startswith("usd"):
            # USD vers XOF
            taux = _EXCHANGE_RATES.get("USD_TO_XOF", 620.0)
            return valeur * taux

        if unite.startswith("eur"):
            # EUR vers XOF (taux fixe UEMOA)
            taux = _EXCHANGE_RATES.get("EUR_TO_XOF", 655.957)
            return valeur * taux

        # --- Conversion des contenants locaux ---
        for conteneur in ("sac", "boisseau", "tine", "caisse", "boite", "panier"):
            if conteneur in unite:
                poids_kg = get_container_weight_kg(conteneur, crop)
                if poids_kg > 0:
                    return valeur / poids_kg
                # Poids inconnu : avertissement et valeur inchangée
                logger.warning(
                    f"Poids inconnu pour le conteneur '{conteneur}' / culture '{crop}'. "
                    "Le prix est retourné sans conversion."
                )
                return valeur

        # --- Unité déjà en XOF/kg ---
        if "xof/kg" in unite or unite == "kg":
            return valeur

        # --- Unité inconnue ---
        logger.warning(
            f"Unité inconnue : '{unit_orig}'. "
            "Le prix est retourné sans conversion."
        )
        return valeur

    def detect_anomalies(self, price_series: pd.DataFrame, z_threshold: float = 3.0) -> pd.DataFrame:
        """
        Détecte les anomalies dans une série de prix par la méthode du Z-score.

        Un prix est considéré comme anormal si son Z-score absolu dépasse
        le seuil configuré (par défaut : 3, soit environ 99.7% de la distribution).

        Args:
            price_series (pd.DataFrame): DataFrame contenant une colonne 'price'.
            z_threshold (float, optional): Seuil d'anomalie. Défaut à 3.0.

        Returns:
            pd.DataFrame: DataFrame original avec une colonne booléenne 'is_anomaly'.
        """
        # Copie pour ne pas modifier le DataFrame d'entrée
        df_result = price_series.copy()

        if "price" not in df_result.columns:
            logger.warning("Colonne 'price' absente du DataFrame. Aucune détection effectuée.")
            df_result["is_anomaly"] = False
            return df_result

        # Calcul des statistiques de la série
        moyenne = df_result["price"].mean()
        ecart_type = df_result["price"].std()

        if ecart_type > 0:
            # Calcul du Z-score pour chaque observation
            z_scores = (df_result["price"] - moyenne) / ecart_type
            # Marquage des anomalies au-delà du seuil
            df_result["is_anomaly"] = np.abs(z_scores) > z_threshold
        else:
            # Série constante : aucune variabilité, donc pas d'anomalie
            df_result["is_anomaly"] = False

        return df_result

    def interpolate_gaps(self, price_series: pd.DataFrame, max_gap_days: int = 7) -> pd.DataFrame:
        """
        Comble les valeurs manquantes dans une série de prix par interpolation linéaire.

        L'interpolation est limitée à un nombre configurable de jours consécutifs.
        Au-delà de cette limite, les valeurs restent manquantes (NaN) pour signaler
        un trou important dans les données.

        Args:
            price_series (pd.DataFrame): DataFrame contenant une colonne 'price'.
            max_gap_days (int, optional): Nombre maximum de jours à interpoler. Défaut à 7.

        Returns:
            pd.DataFrame: DataFrame avec les trous courts comblés par interpolation.
        """
        # Copie pour préserver le DataFrame d'entrée
        df_interpolated = price_series.copy()

        if "price" in df_interpolated.columns:
            # Interpolation linéaire avec limite sur la longueur des trous
            df_interpolated["price"] = df_interpolated["price"].interpolate(
                method="linear",
                limit=max_gap_days,
                limit_direction="both",
            )

        return df_interpolated

    def get_data_source(self, price_series: pd.DataFrame) -> str:
        """
        Identifie la source des données d'une série de prix.

        Si le DataFrame contient la colonne ``is_simulated``, la méthode
        retourne 'simulated' ou 'wfp-vam' selon le cas.

        Args:
            price_series (pd.DataFrame): DataFrame retourné par fetch_prices().

        Returns:
            str: La source identifiée ('wfp-vam', 'ratin', 'scrape-local', 'simulated').
        """
        # Vérification de la colonne is_simulated
        if "is_simulated" in price_series.columns:
            if price_series["is_simulated"].any():
                return "simulated"

        # Par défaut, on suppose WFP VAM (source primaire du V1)
        return "wfp-vam"

    def seasonality(
        self,
        historique: pd.DataFrame,
        min_observations_par_mois: int = 2,
    ) -> dict:
        """
        Calcule l'indice saisonnier mensuel des prix agricoles.

        La méthode utilise la décomposition par ratios : pour chaque mois,
        l'indice est le rapport entre le prix moyen de ce mois et le prix
        moyen global sur toute la période. Un indice supérieur à 1 indique
        un mois de prix élevés (pénurie), inférieur à 1 un mois bon marché
        (période post-récolte).

        L'historique doit couvrir au moins 12 mois pour que les indices
        soient fiables. En dessous de ce seuil, les indices sont calculés
        mais le champ ``confiance`` sera faible.

        Args:
            historique (pd.DataFrame): DataFrame avec au minimum les colonnes
                'date' (datetime ou str) et 'price' (float, en XOF/kg).
                Typiquement retourné par ``fetch_prices()``.
            min_observations_par_mois (int, optional): Nombre minimal
                d'observations pour qu'un mois soit inclus dans le calcul.
                Les mois en dessous de ce seuil sont marqués NaN.
                Défaut : 2.

        Returns:
            dict: Dictionnaire contenant les champs suivants :

                - ``indices`` (dict[int, float | None]) : dictionnaire des
                  12 indices saisonniers, indexé par numéro de mois (1 à 12).
                  La valeur est None si le mois a moins de
                  ``min_observations_par_mois`` entrées.
                - ``mois_pic`` (list[int]) : liste des mois où l'indice
                  dépasse 1.05 (5% au-dessus de la moyenne), triés par
                  indice décroissant.
                - ``mois_creux`` (list[int]) : liste des mois où l'indice
                  est en dessous de 0.95, triés par indice croissant.
                - ``prix_moyen_global`` (float) : prix moyen sur toute la
                  période historique, en XOF/kg.
                - ``prix_moyen_par_mois`` (dict[int, float | None]) :
                  prix moyen brut par mois, avant normalisation.
                - ``nb_observations`` (int) : nombre total d'observations
                  valides utilisées pour le calcul.
                - ``nb_mois_couverts`` (int) : nombre de mois avec au moins
                  ``min_observations_par_mois`` entrées.
                - ``confiance`` (float) : score de confiance de 0 à 1.
                  Reflète la densité des données (1.0 = 2+ ans de données
                  hebdomadaires, 0.0 = moins d'un mois de données).
                - ``is_simulated`` (bool) : True si l'historique source
                  contient des données simulées.
                - ``message`` (str | None) : avertissement si les données
                  sont insuffisantes pour un calcul fiable. None sinon.

        Raises:
            ValueError: Si l'historique est vide ou ne contient pas les
                colonnes 'date' et 'price'.
        """
        # --- Validation des entrées ---
        if historique is None or historique.empty:
            raise ValueError(
                "L'historique fourni est vide. "
                "Utilisez fetch_prices() pour obtenir des données avant "
                "d'appeler seasonality()."
            )

        colonnes_requises = {"date", "price"}
        if not colonnes_requises.issubset(historique.columns):
            raise ValueError(
                f"L'historique doit contenir les colonnes {colonnes_requises}. "
                f"Colonnes reçues : {set(historique.columns)}."
            )

        # --- Préparation du DataFrame ---
        # Copie pour ne pas modifier le DataFrame d'entrée
        df = historique[["date", "price"]].copy()

        # Conversion de la colonne date en datetime si nécessaire
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Suppression des lignes avec date ou prix manquants ou invalides
        df = df.dropna(subset=["date", "price"])
        df = df[df["price"] > 0]

        if df.empty:
            raise ValueError(
                "Aucune observation valide après nettoyage de l'historique "
                "(vérifiez les colonnes 'date' et 'price')."
            )

        # Extraction du numéro de mois (1 = janvier, 12 = décembre)
        df["mois"] = df["date"].dt.month

        # --- Calcul des statistiques par mois ---
        # Comptage des observations disponibles par mois
        compte_par_mois = df.groupby("mois")["price"].count()

        # Prix moyen brut par mois (tous mois confondus)
        moyenne_par_mois = df.groupby("mois")["price"].mean()

        # Prix moyen global sur toute la période (référence de normalisation)
        prix_moyen_global = float(df["price"].mean())

        # Noms des mois en français pour les messages lisibles
        _NOMS_MOIS = {
            1: "janvier", 2: "février", 3: "mars", 4: "avril",
            5: "mai", 6: "juin", 7: "juillet", 8: "août",
            9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
        }

        # --- Construction des indices saisonniers ---
        indices = {}
        prix_moyen_par_mois = {}

        for mois in range(1, 13):
            nb_obs = int(compte_par_mois.get(mois, 0))
            prix_moyen_par_mois[mois] = (
                round(float(moyenne_par_mois[mois]), 2)
                if mois in moyenne_par_mois.index
                else None
            )

            if nb_obs >= min_observations_par_mois and prix_moyen_global > 0:
                # Indice = ratio entre prix moyen du mois et prix moyen global
                # Indice > 1 : mois cher, < 1 : mois bon marché
                indice = float(moyenne_par_mois[mois]) / prix_moyen_global
                indices[mois] = round(indice, 4)
            else:
                # Données insuffisantes pour ce mois
                indices[mois] = None

        # --- Identification des mois de pic et de creux ---
        # Seuil de 5% au-dessus/en dessous de la moyenne pour éviter le bruit
        _SEUIL_PIC = 1.05
        _SEUIL_CREUX = 0.95

        mois_pic = sorted(
            [m for m, idx in indices.items() if idx is not None and idx >= _SEUIL_PIC],
            key=lambda m: indices[m],
            reverse=True,
        )
        mois_creux = sorted(
            [m for m, idx in indices.items() if idx is not None and idx <= _SEUIL_CREUX],
            key=lambda m: indices[m],
        )

        # --- Calcul du score de confiance ---
        nb_mois_couverts = sum(1 for v in indices.values() if v is not None)
        nb_observations = len(df)

        # La confiance dépend de deux facteurs :
        # 1. La couverture mensuelle : 12 mois = 1.0, 0 mois = 0.0
        facteur_couverture = nb_mois_couverts / 12.0
        # 2. La densité des données : on considère 104 obs (2 ans hebdo) comme optimal
        facteur_densite = min(1.0, nb_observations / 104.0)
        confiance = round((facteur_couverture + facteur_densite) / 2.0, 3)

        # --- Propagation du flag is_simulated depuis la source ---
        est_simule = False
        if "is_simulated" in historique.columns:
            est_simule = bool(historique["is_simulated"].any())

        # --- Message d'avertissement si données insuffisantes ---
        message = None
        if nb_mois_couverts < 6:
            message = (
                f"Seulement {nb_mois_couverts} mois couverts sur 12. "
                "Les indices saisonniers calculés sont peu fiables. "
                "Il est recommandé d'avoir au moins 12 mois d'historique."
            )
        elif nb_mois_couverts < 12:
            manquants = [_NOMS_MOIS[m] for m in range(1, 13) if indices[m] is None]
            message = (
                f"Données manquantes pour : {', '.join(manquants)}. "
                "L'indice saisonnier est None pour ces mois."
            )

        if est_simule:
            avert_simul = "Attention : l'historique est simulé. Les indices ne reflètent pas la réalité du marché."
            message = f"{avert_simul} {message}" if message else avert_simul

        logger.info(
            f"Saisonnalité calculée : {nb_mois_couverts}/12 mois couverts, "
            f"{nb_observations} observations, confiance={confiance}, "
            f"pic={mois_pic}, creux={mois_creux}."
        )

        return {
            "indices": indices,
            "mois_pic": mois_pic,
            "mois_creux": mois_creux,
            "prix_moyen_global": round(prix_moyen_global, 2),
            "prix_moyen_par_mois": prix_moyen_par_mois,
            "nb_observations": nb_observations,
            "nb_mois_couverts": nb_mois_couverts,
            "confiance": confiance,
            "is_simulated": est_simule,
            "message": message,
        }
