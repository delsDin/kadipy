"""
Package principal de KadiPy.

KadiPy est le "pandas" de l'agriculture africaine, facilitant le traitement
et l'analyse des données météorologiques, de marché et de récoltes locales
avec une approche "offline-first".
"""

import logging

# ------------------------------------------------------------------
# Version du package
# ------------------------------------------------------------------

__version__ = "1.0.0"

# ------------------------------------------------------------------
# Configuration du logger racine de KadiPy
#
# Tous les sous-modules utilisent logging.getLogger(__name__), ce qui
# crée des loggers de la forme "kadi.market.pricing", "kadi.weather.risk",
# etc. Ces loggers héritent automatiquement du niveau défini ici sur
# le logger racine "kadi". Il suffit donc de configurer ce seul logger
# pour contrôler l'ensemble de la bibliothèque.
# ------------------------------------------------------------------

# Logger racine du package (silence par défaut : WARNING)
_logger_kadi = logging.getLogger("kadi")
_logger_kadi.setLevel(logging.WARNING)

# Handler console minimal (affiché uniquement si aucun handler n'est
# configuré en amont dans l'application de l'utilisateur)
if not _logger_kadi.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    )
    _logger_kadi.addHandler(_handler)


def set_verbosity(level: str = "WARNING") -> None:
    """Configure le niveau de log pour tous les sous-modules de KadiPy.

    Cette fonction est le point d'entrée unique pour contrôler la
    verbosité de la bibliothèque. Elle s'applique au logger racine
    "kadi", dont héritent automatiquement tous les sous-loggers
    (kadi.market, kadi.weather, kadi.kidas, etc.).

    Args:
        level (str): Niveau de log souhaité. Valeurs acceptées :
            - "DEBUG"   : logs détaillés (requêtes API, calculs internes).
            - "INFO"    : messages d'état du pipeline.
            - "WARNING" : uniquement les avertissements (defaut).
            - "ERROR"   : uniquement les erreurs critiques.

    Raises:
        ValueError: Si le niveau fourni n'est pas reconnu par le module
            standard logging.

    Exemple:
        >>> import kadi
        >>> kadi.set_verbosity("DEBUG")   # Active les logs détaillés
        >>> kadi.set_verbosity("WARNING") # Remet en mode silencieux (défaut)
    """
    # Conversion du niveau texte en constante numérique logging
    niveau_numerique = getattr(logging, level.upper(), None)

    # Vérification que le niveau est valide
    if not isinstance(niveau_numerique, int):
        niveaux_valides = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        raise ValueError(
            f"Niveau de log invalide : '{level}'. "
            f"Valeurs acceptées : {niveaux_valides}"
        )

    # Application du niveau sur le logger racine du package
    _logger_kadi.setLevel(niveau_numerique)

    # Journalisation du changement (visible uniquement si le niveau
    # sélectionné est DEBUG ou INFO)
    _logger_kadi.info(
        "kadi : niveau de verbosité défini à '%s'.", level.upper()
    )
