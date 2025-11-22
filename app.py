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

try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    FILE_PATH = os.path.join(base_dir, 'food_data.csv')

    try:
        DF = pd.read_csv(FILE_PATH, encoding='utf-8')
    except UnicodeDecodeError:
        DF = pd.read_csv(FILE_PATH, encoding='latin-1')

    # Datenbereinigung
    DF.columns = DF.columns.str.strip()
    cols = ['Price_per_kg_EUR', 'Protein_g_per_kg', 'Fat_g_per_kg', 'Carbs_g_per_kg', 'Is_Produce']
    for col in cols:
        DF[col] = pd.to_numeric(DF[col], errors='coerce')
    
    DF.dropna(inplace=True)
    DF.set_index('Product_Name', inplace=True)
    DATA_LOADED = True
    print(f"SUCCESS: Database loaded from {FILE_PATH}")

except Exception as e:
    print(f"FATAL ERROR: {e}")

@app.route('/optimize', methods=['GET'])
def run_optimization():
    if not DATA_LOADED:
        return jsonify({"status": "FATAL ERROR", "message": "Database not loaded."}), 500

    try:
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0))
        fett_max = float(request.args.get('fat', 700.0))
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
        gemuese_min = float(request.args.get('produce', 4.0))
        
        # --- REGELN FÜR VIELFALT ---
        # Wir erlauben max 1.5 kg pro Produkt (außer Gemüse)
        # Das zwingt die KI, MEHR verschiedene Dinge zu kaufen.
        max_per_item = 1.5 
        min_per_item = 0.2 # Keine Mini-Mengen unter 200g
        min_unique_items = 6 # Mindestens 6 verschiedene Produkte
        
    except:
        return jsonify({"error": "Invalid parameters."}), 400

    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = DF.index.tolist()
    
    # Variablen: Menge (kg) UND Auswahl (Ja/Nein)
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')
    produkt_gewaehlt = pulp.LpVariable.dicts("Gewaehlt", produkte, cat='Binary')

    # Zielfunktion
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]), "Total_Cost"

    # Nährwert Constraints
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]) <= budget_max, "Budget"
    prob += pulp.lpSum([DF.loc[p, 'Protein_g_per_kg'] * produkt_mengen[p] for p in produkte]) >= protein_min, "Protein"
    prob += pulp.lpSum([DF.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max, "Fat"
    prob += pulp.lpSum([DF.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max, "Carbs"
    
    # Gemüse Constraint
    gemuese_produkte = DF[DF['Is_Produce'] == 1].index.tolist()
    if len(gemuese_produkte) > 0:
        prob += pulp.lpSum([produkt_mengen[p] for p in gemuese_produkte]) >= gemuese_min

    # --- VIELFALTS-LOGIK ---
    for p in produkte:
        limit = max_per_item
        # Gemüse darf man mehr essen (bis 3kg)
        if DF.loc[p, 'Is_Produce'] == 1:
            limit = 3.0
            
        # Obergrenze: Menge <= Limit * Gewaehlt (Wenn nicht gewählt, dann 0)
        prob += produkt_mengen[p] <= limit * produkt_gewaehlt[p]
        
        # Untergrenze: Menge >= 0.2 * Gewaehlt (Wenn gewählt, dann mind. 200g)
        prob += produkt_mengen[p] >= min_per_item * produkt_gewaehlt[p]

    # Erzwinge mindestens 6 verschiedene Produkte
    prob += pulp.lpSum([produkt_gewaehlt[p] for p in produkte]) >= min_unique_items

    # --- Lösen ---
    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
         return jsonify({"status": "Error", "message": str(e)}), 500

    if pulp.LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            # Nur Mengen > 0 anzeigen
            if "Menge" in v.name and v.varValue > 0.001:
                clean_name = v.name.replace('Menge_', '').replace('_', ' ')
                einkaufsliste[clean_name] = f"{v.varValue:.2f} kg"

        return jsonify({
            "status": "Success",
            "total_cost": f"{pulp.value(prob.objective):.2f} €",
            "optimized_shopping_list": einkaufsliste,
            "item_count": len(einkaufsliste)
        })
    else:
        return jsonify({
            "status": "Error", 
            "message": "Nicht lösbar! Mit den neuen Vielfalts-Regeln (max 1.5kg pro Produkt) reicht dein Budget evtl. nicht. Erhöhe das Budget!"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
