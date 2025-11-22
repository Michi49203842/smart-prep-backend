import requests
import pandas as pd
import json

# --- 1. ZIELE DEFINIEREN ---
# Wir wollen Daten zu echten Produkten. Hier sind Barcodes (EANs) für Tests:
# 3017620422003 = Nutella
# 4008400404127 = Kinder Riegel
# 5449000000996 = Coca Cola
barcodes = ["3017620422003", "4008400404127", "5449000000996"]

# Leere Liste für unsere Ergebnisse
products_data = []

print("📡 Starte Datenabruf aus dem Internet...\n")

# --- 2. DATEN LIVE HOLEN (Der Loop) ---
for code in barcodes:
    url = f"https://world.openfoodfacts.org/api/v0/product/{code}.json"
    
    try:
        # Der "Kellner" geht zur API und holt die Daten
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 1:
            product = data['product']
            nutriments = product.get('nutriments', {})
            
            # Wir extrahieren nur das, was wir brauchen
            info = {
                'Name': product.get('product_name', 'Unbekannt'),
                'Marke': product.get('brands', 'Unbekannt'),
                'Kalorien': nutriments.get('energy-kcal_100g', 0),
                'Zucker': nutriments.get('sugars_100g', 0),
                'Protein': nutriments.get('proteins_100g', 0)
            }
            products_data.append(info)
            print(f"✅ Gefunden: {info['Name']}")
        else:
            print(f"❌ Barcode {code} nicht gefunden.")
            
    except Exception as e:
        print(f"⚠️ Fehler bei {code}: {e}")

print("\n" + "="*50 + "\n")

# --- 3. ANALYSE MIT PANDAS ---
# Jetzt wandeln wir die rohen Daten in einen Pandas DataFrame um
df_web = pd.DataFrame(products_data)

print("--- DEINE LIVE-DATENBANK ---")
print(df_web)
print("\n" + "="*50 + "\n")

# Kleine Analyse: Wer hat am meisten Zucker?
sugar_king = df_web.sort_values(by='Zucker', ascending=False).iloc[0]
print(f"👑 Der Zuckerkönig ist: {sugar_king['Name']} ({sugar_king['Zucker']}g Zucker/100g)")
