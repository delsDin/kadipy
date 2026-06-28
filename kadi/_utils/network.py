"""
Utilitaires réseau pour KadiPy.

Fournit des fonctions pour exécuter des requêtes réseau avec 
mécanismes de retry (tentatives) et de fallback (repli).
"""

import time
import logging
from typing import Callable, Any

from kadi.exceptions import DataSourceError

logger = logging.getLogger(__name__)


def fetch_with_retry(
    fetch_func: Callable,
    attempts: int = 3,
    backoff_sec: int = 5,
    *args,
    **kwargs
) -> Any:
    """
    Exécute une fonction de récupération réseau avec un mécanisme de tentatives multiples.
    
    Args:
        fetch_func: La fonction à exécuter.
        attempts: Nombre maximum de tentatives (défaut: 3).
        backoff_sec: Temps d'attente (en secondes) entre deux tentatives (défaut: 5).
        *args, **kwargs: Arguments passés à fetch_func.
        
    Returns:
        Any: Les données retournées par fetch_func.
        
    Raises:
        DataSourceError: Si toutes les tentatives échouent.
    """
    last_exception = None
    
    for attempt in range(1, attempts + 1):
        try:
            return fetch_func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(
                f"Échec de la récupération (Tentative {attempt}/{attempts}) : {e}"
            )
            if attempt < attempts:
                time.sleep(backoff_sec)
                
    # Si on sort de la boucle, c'est que toutes les tentatives ont échoué
    logger.error(f"Toutes les tentatives ({attempts}) ont échoué.")
    raise DataSourceError(f"Échec définitif de récupération : {last_exception}")
