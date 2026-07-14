import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kadi.market.data_ingestion import WFPDataBridgesClient

def tester_api():
    print("Initialisation du client WFP...")
    # On force l'utilisation de l'API avec use_local_mirror=False
    client = WFPDataBridgesClient(use_local_mirror=False, env_file='.env')
    
    print(f"Token chargé avec succès : {bool(client.token)}")
    
    if not client.token:
        print("Erreur : Aucun token trouvé dans le fichier .env.")
        return
        
    print("\nTentative de requête vers l'API WFP DataBridges...")
    print("Paramètres : Marché = 'savalou_market', Culture = 'maize'")
    
    # Appel de l'API avec une plage de temps
    df = client.get_market_prices('savalou_market', 'maize', time_range=('2024-01-01', '2024-06-01'))
    
    if df.empty:
        print("\nL'API a répondu, mais aucune donnée n'a été trouvée pour ces paramètres.")
    else:
        print(f"\nSuccès ! L'API a renvoyé {len(df)} enregistrements.")
        print("\nLes 5 premières lignes :")
        print(df.head())

if __name__ == "__main__":
    tester_api()
