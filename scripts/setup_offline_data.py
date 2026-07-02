"""
Script pour préparer l'environnement offline de KadiPy.
Ce script télécharge les grilles de SoilGrids, prépare le fichier CHIRPS (mocké pour l'instant)
et télécharge les taux de change.
"""

import os
import json
import logging
from pathlib import Path
import random

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

CACHE_DIR = Path.home() / ".kadipy_cache"

def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    logging.info(f"Dossier de cache assuré: {CACHE_DIR}")

def setup_chirps_data():
    """
    Simule la création ou le téléchargement d'un fichier CSV CHIRPS.
    Dans un environnement réel, cela téléchargerait un fichier NetCDF et l'extrairait.
    """
    chirps_file = CACHE_DIR / "historical_rainfall_1981_2024.csv"
    if chirps_file.exists():
        logging.info("Fichier CHIRPS existant. Ignoré.")
        return
        
    logging.info("Génération du fichier de fallback CHIRPS...")
    # On va simuler un fichier CSV vide pour l'instant avec les en-têtes
    # lat, lon, date, precip
    with open(chirps_file, "w") as f:
        f.write("date,latitude,longitude,precipitation\n")
        # Exemple de ligne : 2024-01-01,9.3041,2.0890,0.0
    logging.info(f"Fichier CHIRPS mock créé: {chirps_file}")

def setup_soilgrids_cache():
    """
    Pré-télécharge une grille de points clés pour le Bénin pour SoilGrids.
    (Mock simplifié pour le développement)
    """
    soil_file = CACHE_DIR / "soilgrids_cache.json"
    if soil_file.exists():
        logging.info("Fichier cache SoilGrids existant. Ignoré.")
        return
        
    logging.info("Création du cache SoilGrids (points du Bénin)...")
    # Simulation des points clés du Bénin
    mock_data = [
        {"lat": 6.36536, "lon": 2.41833, "soil_type": "sableux"},       # Cotonou
        {"lat": 7.18286, "lon": 1.99119, "soil_type": "ferrallitique"}, # Abomey
        {"lat": 9.33716, "lon": 2.63031, "soil_type": "ferrugineux"},   # Parakou
        {"lat": 10.30416, "lon": 1.37962, "soil_type": "limoneux"}      # Natitingou
    ]
    
    with open(soil_file, "w") as f:
        json.dump(mock_data, f, indent=4)
    logging.info(f"Fichier cache SoilGrids créé: {soil_file}")

if __name__ == "__main__":
    ensure_cache_dir()
    setup_chirps_data()
    setup_soilgrids_cache()
    logging.info("Configuration hors ligne terminée avec succès.")