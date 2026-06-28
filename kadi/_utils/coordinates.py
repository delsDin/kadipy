"""
Utilitaires de gestion des coordonnées GPS pour KadiPy.

Dans cette version V1, la résolution des villes se fait via un dictionnaire
statique pour les principales villes du Bénin, afin de permettre les tests
(mocking).
"""

from typing import Tuple
from kadi.exceptions import LocationNotFound

# Dictionnaire mocké pour la résolution des localisations (Villes du Bénin)
BENIN_CITIES = {
    "cotonou": (6.36536, 2.41833),
    "porto-novo": (6.49722, 2.605),
    "parakou": (9.33716, 2.63031),
    "abomey": (7.18286, 1.99119),
    "natitingou": (10.30416, 1.37962),
    "djougou": (9.70853, 1.66598),
    "bohicon": (7.17826, 2.0667),
    "ouidah": (6.36408, 2.08383),
}


def normalize_location(location: str) -> Tuple[float, float]:
    """
    Transforme un nom de ville en un tuple de coordonnées (latitude, longitude).
    
    Args:
        location: Le nom de la ville (ex: "Abomey", "Cotonou").
        
    Returns:
        Tuple[float, float]: (latitude, longitude).
        
    Raises:
        LocationNotFound: Si la ville n'est pas dans notre dictionnaire mocké.
    """
    # Nettoyage de la chaîne : passage en minuscules et suppression des espaces
    loc_clean = location.strip().lower()
    
    if loc_clean in BENIN_CITIES:
        return BENIN_CITIES[loc_clean]
    
    raise LocationNotFound(
        f"La localisation '{location}' n'est pas reconnue dans la base du Bénin."
    )
