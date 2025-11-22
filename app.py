from flask import Flask, request, jsonify
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, value, PULP_CBC_CMD
from flask_cors import CORS
import pandas as pd
import os
import sys

app = Flask(__name__)
CORS(app)

# --- 1. DATEN VORBEREITEN ---
DATA_LOADED = False
DF = None
DEBUG_INFO = ""

def load_and_clean_data():
    global DATA_LOADED, DF, DEBUG_INFO
    try:
        # Pfad finden (Robust für Render)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        FILE_PATH = os.path.join(base_dir, 'food_data.csv')
        DEBUG_INFO = f"Suche Datei in: {FILE_PATH}"
        print(f"DEBUG: {DEBUG_INFO}")

        try:
            DF = pd.read_csv(FILE_PATH, encoding='utf-8')
        except UnicodeDecodeError:
            DF = pd.read_csv(FILE_PATH, encoding='latin-1')

        # Bereinigung
        DF.columns = DF.columns.str.strip()
        cols = ['Price_per_kg_EUR', 'Protein_g_per_kg', 'Fat_g_per_kg', 'Carbs_g_per_kg', 'Is_Produce']
        for col in cols:
            DF[col] = pd.to_numeric(DF[col], errors='coerce')
        
        DF.dropna(inplace=True)
        
        # Duplikate entfernen, um Fehler zu vermeiden
        DF.drop_duplicates(subset=['Product_Name'], keep='first', inplace=True)
        
        DF.set_index('Product_Name', inplace=True)
        
        DATA_LOADED = True
        print(f"SUCCESS: Database loaded successfully.")
        return True

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        DATA_LOADED = False
        return False

load_and_clean_data()

@app.route('/optimize', methods=['GET'])
def run_optimization():
    if not DATA_LOADED:
        load_and_clean_data()
        if not DATA_LOADED:
            return jsonify({"status": "FATAL ERROR", "message": "Database Error"}), 500

    try:
        # Parameter lesen
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0))
        fett_max = float(request.args.get('fat', 700.0))
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
        gemuese_min = float(request.args.get('produce', 4.0))
        
        # Vielfalts-Parameter
        max_per_item = 1.5 
        min_per_item = 0.2 
        min_unique_items = 6 
    except:
        return jsonify({"error": "Invalid parameters."}), 400

    # Optimierung aufbauen
    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = DF.index.tolist()
    
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')
    produkt_gewaehlt = pulp.LpVariable.dicts("Gewaehlt", produkte, cat='Binary')

    # Zielfunktion
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte])

    # Constraints
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]) <= budget_max
    prob += pulp.lpSum([DF.loc[p, 'Protein_g_per_kg'] * produkt_mengen[p] for p in produkte]) >= protein_min
    prob += pulp.lpSum([DF.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max
    prob += pulp.lpSum([DF.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max
    
    gemuese_produkte = DF[DF['Is_Produce'] == 1].index.tolist()
    if len(gemuese_produkte) > 0:
        prob += pulp.lpSum([produkt_mengen[p] for p in gemuese_produkte]) >= gemuese_min

    # Vielfalts-Regeln
    for p in produkte:
        limit = max_per_item
        if DF.loc[p, 'Is_Produce'] == 1: limit = 4.0
        prob += produkt_mengen[p] <= limit * produkt_gewaehlt[p]
        prob += produkt_mengen[p] >= min_per_item * produkt_gewaehlt[p]

    prob += pulp.lpSum([produkt_gewaehlt[p] for p in produkte]) >= min_unique_items

    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
         return jsonify({"status": "Error", "message": str(e)}), 500

    if pulp.LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            # Nur Mengen > 0.001 (Gleitkomma-Toleranz)
            if "Menge" in v.name and v.varValue > 0.001:
                # Den echten Namen aus der Variable holen (Menge_Name -> Name)
                raw_name = v.name.replace('Menge_', '')
                
                # Preis holen für detaillierte Ansicht
                try:
                    single_price = DF.loc[raw_name, 'Price_per_kg_EUR']
                except:
                    single_price = 0 # Fallback falls Name nicht matcht
                
                # Kosten für dieses Item berechnen
                item_cost = v.varValue * single_price
                
                # Schönen Namen für Anzeige bauen
                clean_name = raw_name.replace('_', ' ')
                
                # WICHTIG: Hier erstellen wir das Objekt, das dein Frontend erwartet!
                einkaufsliste[clean_name] = {
                    "amount": round(v.varValue, 2),
                    "cost": round(item_cost, 2)
                }

        return jsonify({
            "status": "Success",
            "total_cost": f"{pulp.value(prob.objective):.2f}",
            "optimized_shopping_list": einkaufsliste
        })
    else:
        return jsonify({
            "status": "Error", 
            "message": "Nicht lösbar! Budget zu niedrig für diese Ziele."
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
