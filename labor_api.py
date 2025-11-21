import requests
import json

# --- 1. DIE BESTELLUNG (Der Request) ---
# Wir wollen Daten zu einem Produkt. Nehmen wir "Nutella" als Test.
# Der Barcode (EAN) für ein Standard-Nutella Glas ist: 3017620422003
barcode = "3017620422003"

# Das ist die Adresse der Küche (API Endpunkt) von OpenFoodFacts
url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"

print(f"📡 Frage Daten ab für Barcode: {barcode}...")
print(f"🔗 URL: {url}")

# Wir schicken den Kellner los (GET-Request)
response = requests.get(url)

# --- 2. DIE LIEFERUNG (Response prüfen) ---
# Status Code 200 bedeutet: "Alles okay, hier ist deine Bestellung."
# Status Code 404 bedeutet: "Nicht gefunden."
if response.status_code == 200:
    print("✅ Antwort erhalten!")
    
    # --- 3. DAS ESSEN AUSPACKEN (JSON Parsing) ---
    # Die Daten kommen als Textblock. Wir wandeln sie in ein Python-Dictionary um.
    data = response.json()
    
    # Prüfen, ob das Produkt in der Datenbank gefunden wurde
    if data['status'] == 1:
        product = data['product']
        
        # Wir greifen auf die verschachtelten Daten zu
        name = product.get('product_name', 'Unbekannt')
        marke = product.get('brands', 'Unbekannt')
        
        # Nährwerte stecken in einem Unter-Ordner namens 'nutriments'
        nutri = product.get('nutriments', {})
        kcal = nutri.get('energy-kcal_100g', 0)
        zucker = nutri.get('sugars_100g', 0)
        eiweiss = nutri.get('proteins_100g', 0)
        
        print("\n" + "="*30)
        print(f"🍫 Produkt: {name}")
        print(f"🏷️  Marke:   {marke}")
        print("-" * 30)
        print(f"🔥 Kalorien: {kcal} kcal")
        print(f"🍬 Zucker:   {zucker} g")
        print(f"💪 Eiweiß:   {eiweiss} g")
        print("="*30 + "\n")
        
    else:
        print("❌ Produkt existiert nicht in der OpenFoodFacts Datenbank.")
else:
    print(f"❌ Fehler bei der Verbindung: Status Code {response.status_code}")
