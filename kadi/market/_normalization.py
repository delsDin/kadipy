"""
Module de normalisation des noms et des unités pour le module kadi.market.

Ce module centralise tous les dictionnaires de correspondance nécessaires
pour convertir les noms de cultures (en français, en fon, en anglais) vers
les codes standards, ainsi que les unités locales vers XOF/kg.
"""

# -------------------------------------------------------------------------
# Dictionnaire de normalisation des cultures
# Clés : variantes connues (français, fon, anglais, fautes courantes)
# Valeurs : code standard utilisé en interne et dans l'API WFP
# -------------------------------------------------------------------------
CROP_NAME_MAPPING = {
    # Maïs
    "maïs": "maize",
    "mais": "maize",
    "maiz": "maize",
    "maïz": "maize",
    "maize": "maize",
    "corn": "maize",
    "blé_de_turquie": "maize",
    "gbadji": "maize",       # Nom fon du maïs

    # Riz
    "riz": "rice",
    "rice": "rice",
    "riz_local": "rice",
    "riz_importé": "rice",

    # Sorgho
    "sorgho": "sorghum",
    "sorghum": "sorghum",
    "gros_mil": "sorghum",
    "kafle": "sorghum",      # Nom fon du sorgho

    # Igname
    "igname": "yam",
    "yam": "yam",
    "igname_blanc": "yam",
    "wassaa": "yam",         # Variante locale

    # Manioc
    "manioc": "cassava",
    "cassava": "cassava",
    "tapioca": "cassava",
    "gari": "cassava",       # Produit transformé du manioc

    # Niébé
    "niébé": "cowpea",
    "niebe": "cowpea",
    "haricot": "cowpea",
    "cowpea": "cowpea",
    "black_eyed_peas": "cowpea",

    # Soja
    "soja": "soybean",
    "soy": "soybean",
    "soybean": "soybean",
    "soybeans": "soybean",
    "féverole": "soybean",

    # Tomate
    "tomate": "tomato",
    "tomato": "tomato",
    "tomatoes": "tomato",

    # Mil
    "mil": "millet",
    "millet": "millet",
    "petit_mil": "millet",
}

# -------------------------------------------------------------------------
# Dictionnaire de normalisation des marchés du Bénin
# Clés : variantes de noms (avec accents, sans accents, abréviations)
# Valeurs : code standard interne (minuscules, sans accents)
# -------------------------------------------------------------------------
MARKET_NAME_MAPPING = {
    # Cotonou et marchés satellites
    "cotonou": "cotonou",
    "dantokpa": "cotonou",
    "marché_dantokpa": "cotonou",
    "marche_dantokpa": "cotonou",

    # Parakou
    "parakou": "parakou",
    "marché_parakou": "parakou",
    "marche_parakou": "parakou",

    # Abomey
    "abomey": "abomey",
    "abomey_calavi": "abomey",
    "abomey-calavi": "abomey",

    # Savalou
    "savalou": "savalou",
    "savalou_market": "savalou",
    "marché_savalou": "savalou",

    # Natitingou
    "natitingou": "natitingou",
    "nati": "natitingou",

    # Porto-Novo
    "porto-novo": "porto_novo",
    "porto_novo": "porto_novo",
    "porto novo": "porto_novo",
    "adjarra": "porto_novo",

    # Malanville (nord, frontière Niger)
    "malanville": "malanville",
    "malanville_market": "malanville",

    # Bohicon
    "bohicon": "bohicon",

    # Kandi
    "kandi": "kandi",
    "marché_kandi": "kandi",

    # Lokossa
    "lokossa": "lokossa",

    # Azovè
    "azovè": "azoue",
    "azoue": "azoue",
    "azove": "azoue",
}

# -------------------------------------------------------------------------
# Poids de référence par contenant local (en kilogrammes)
# Ces valeurs correspondent aux conventions béninoises courantes
# -------------------------------------------------------------------------
CONTAINER_WEIGHTS_KG = {
    # Maïs
    "sac_maize": 100.0,          # 1 sac de maïs = ~100 kg
    "boisseau_maize": 25.0,      # 1 boisseau de maïs = ~25 kg
    "tine_maize": 12.5,          # 1 tine = ~12.5 kg

    # Riz
    "sac_rice": 80.0,            # 1 sac de riz = ~80 kg
    "boisseau_rice": 20.0,

    # Sorgho
    "sac_sorghum": 90.0,
    "boisseau_sorghum": 22.0,

    # Manioc
    "sac_cassava": 80.0,

    # Niébé
    "sac_cowpea": 60.0,
    "boisseau_cowpea": 15.0,

    # Soja
    "sac_soybean": 60.0,

    # Tomate
    "caisse_tomato": 20.0,       # 1 caisse de tomate = ~20 kg
    "boîte_tomato": 10.0,

    # Valeurs génériques si la culture est inconnue
    "sac": 80.0,
    "boisseau": 20.0,
    "tine": 12.0,
    "caisse": 20.0,
}

# -------------------------------------------------------------------------
# Taux de conversion de devises (base de référence, mis à jour dans config.py)
# Ces taux sont des valeurs par défaut. La configuration principale
# les remplace au besoin.
# -------------------------------------------------------------------------
EXCHANGE_RATES_DEFAULT = {
    "USD_TO_XOF": 620.0,   # 1 USD ≈ 620 XOF (à ajuster régulièrement)
    "EUR_TO_XOF": 655.957, # 1 EUR = 655.957 XOF (taux fixe UEMOA)
}


def normalize_crop_name(name: str) -> str:
    """
    Convertit un nom de culture en son code standard anglais.

    Accepte les noms en français, en fon, en anglais et les fautes
    de frappe courantes. La comparaison est insensible à la casse.

    Args:
        name (str): Le nom de la culture à normaliser (ex: 'Maïs', 'mais').

    Returns:
        str: Le code standard de la culture (ex: 'maize').

    Raises:
        ValueError: Si le nom de la culture est inconnu du dictionnaire.

    Exemples:
        >>> normalize_crop_name("Maïs")
        'maize'
        >>> normalize_crop_name("haricot")
        'cowpea'
    """
    # Normalisation de la clé : minuscules, espaces remplacés par underscores
    cle_normalisee = name.strip().lower().replace(" ", "_").replace("-", "_")

    # Recherche dans le dictionnaire de mapping
    if cle_normalisee in CROP_NAME_MAPPING:
        return CROP_NAME_MAPPING[cle_normalisee]

    # Si introuvable, on lève une exception claire
    raise ValueError(
        f"Culture inconnue : '{name}'. "
        f"Cultures acceptées : {sorted(set(CROP_NAME_MAPPING.values()))}"
    )


def normalize_market_name(name: str) -> str:
    """
    Convertit un nom de marché béninois en son code standard interne.

    Accepte les variantes avec ou sans accents, avec ou sans espace.
    La comparaison est insensible à la casse.

    Args:
        name (str): Le nom du marché à normaliser (ex: 'Dantokpa', 'Porto-Novo').

    Returns:
        str: Le code standard du marché (ex: 'cotonou', 'porto_novo').

    Raises:
        ValueError: Si le marché est inconnu.

    Exemples:
        >>> normalize_market_name("Dantokpa")
        'cotonou'
        >>> normalize_market_name("Porto-Novo")
        'porto_novo'
    """
    # Normalisation de la clé
    cle_normalisee = name.strip().lower().replace(" ", "_").replace("-", "_")

    # Recherche dans le dictionnaire
    if cle_normalisee in MARKET_NAME_MAPPING:
        return MARKET_NAME_MAPPING[cle_normalisee]

    # Si introuvable, on retourne le nom normalisé (peut être un marché non listé)
    # On ne lève pas d'exception ici car l'API peut connaître des marchés
    # que notre dictionnaire ne couvre pas encore.
    return cle_normalisee


def get_container_weight_kg(conteneur: str, crop: str = None) -> float:
    """
    Retourne le poids en kilogrammes d'un contenant local.

    Essaie d'abord de trouver le poids spécifique à la culture,
    puis retombe sur le poids générique du contenant.

    Args:
        conteneur (str): Le type de contenant (ex: 'sac', 'boisseau').
        crop (str, optional): Le code de la culture (ex: 'maize').

    Returns:
        float: Le poids en kilogrammes. Retourne 80.0 par défaut si inconnu.

    Exemples:
        >>> get_container_weight_kg("boisseau", "maize")
        25.0
        >>> get_container_weight_kg("sac")
        80.0
    """
    conteneur_norm = conteneur.strip().lower().replace(" ", "_")

    # Essai avec la clé spécifique à la culture
    if crop:
        cle_specifique = f"{conteneur_norm}_{crop}"
        if cle_specifique in CONTAINER_WEIGHTS_KG:
            return CONTAINER_WEIGHTS_KG[cle_specifique]

    # Fallback sur le poids générique
    if conteneur_norm in CONTAINER_WEIGHTS_KG:
        return CONTAINER_WEIGHTS_KG[conteneur_norm]

    # Valeur par défaut si rien n'est trouvé
    return 80.0
