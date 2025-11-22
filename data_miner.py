import requests
import pandas as pd
import time

# --- 1. KONFIGURATION ---
# Wir suchen nach Produkten in Deutschland, sortiert nach Beliebtheit
print("⛏️  Starte Data Mining bei OpenFoodFacts...")

url = "https://de.openfoodfacts.org/cgi/search.pl"
params = {
    "action": "process",
    "tagtype_0": "countries",
    "tag_contains_0": "contains",
    "tag_0": "germany",
    "sort_by": "popularity",
    "page_size": 50,  # Wir holen 50 Produkte auf einmal
    "json": 1
}

# --- 2. DATEN ABFRAGEN ---
try:
    response = requests.get(url, params=params)
    data = response.json()
    products = data.get('products', [])
    
    print(f"📦 Habe {len(products)} Produkte gefunden. Verarbeite Daten...")
    
    clean_products = []
    
    for p in products:
        # Wir brauchen Name, Preis (Fake, da API keine Preise hat), und Nährwerte
        name = p.get('product_name', 'Unbekannt')
        nutri = p.get('nutriments', {})
        
        # Nährwerte extrahieren (Standard ist 0 falls fehlt)
        protein = nutri.get('proteins_100g', 0)
        fat = nutri.get('fat_100g', 0)
        carbs = nutri.get('carbohydrates_100g', 0)
        
        # Da OpenFoodFacts keine Preise hat, simulieren wir für den PoC 
        # einen Preis basierend auf der Qualität (nur für den Test!)
        # In der Realität würdest du hier REWE/Aldi scrapen.
        fake_price = 2.00 
        if protein > 20: fake_price = 8.00 # Teures Fleisch/Protein
        if carbs > 50: fake_price = 1.50   # Billige Nudeln/Zucker
        
        # Einfache Logik für "Ist Gemüse/Obst"
        # Wir schauen, ob 'fruit' oder 'vegetable' in den Kategorien steht
        categories = p.get('categories', '').lower()
        is_produce = 1 if ('fruit' in categories or 'vegetable' in categories) else 0
        
        # Daten bereinigen (Namen ohne Kommas für CSV)
        clean_name = name.replace(',', ' ').replace('"', '').strip()
        
        # Nur hinzufügen, wenn der Name Sinn macht
        if len(clean_name) > 2:
            clean_products.append({
                "Product_Name": clean_name,
                "Price_per_kg_EUR": fake_price,
                "Protein_g_per_kg": protein * 10, # Umrechnung 100g -> 1kg
                "Fat_g_per_kg": fat * 10,
                "Carbs_g_per_kg": carbs * 10,
                "Is_Produce": is_produce
            })

    # --- 3. CSV ERSTELLEN ---
    df = pd.DataFrame(clean_products)
    
    # Speichern im gleichen Ordner
    df.to_csv('food_data_generated.csv', index=False, encoding='utf-8')
    
    print("\n" + "="*50)
    print(f"✅ ERFOLG! {len(df)} Produkte gespeichert in 'food_data_generated.csv'")
    print("Hier sind die Top 5 Proteinquellen aus deinem neuen Datensatz:")
    print(df.sort_values(by='Protein_g_per_kg', ascending=False).head(5)[['Product_Name', 'Protein_g_per_kg']])
    print("="*50 + "\n")

except Exception as e:
    print(f"❌ Fehler beim Mining: {e}")
