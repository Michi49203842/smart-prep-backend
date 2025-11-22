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
DEBUG_PATH = "Unbekannt"

def load_data():
    global DATA_LOADED, DF, DEBUG_PATH
    try:
        # FINALER PFAD-FIX:
        # __file__ ist immer der Pfad zu DIESER app.py Datei.
        # Wir holen uns den Ordner, in dem diese Datei liegt.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Wir bauen den Pfad zur CSV
        FILE_PATH = os.path.join(base_dir, 'food_data.csv')
        DEBUG_PATH = FILE_PATH

        print(f"DEBUG: Versuche Daten zu laden von: {FILE_PATH}")

        # Versuche utf-8, falle zurück auf latin-1 wenn nötig
        try:
            DF = pd.read_csv(FILE_PATH, encoding='utf-8')
        except UnicodeDecodeError:
            DF = pd.read_csv(FILE_PATH, encoding='latin-1')

        # Einfache Datenreinigung (String zu Zahl)
        cols = ['Price_per_kg_EUR', 'Protein_g_per_kg', 'Fat_g_per_kg', 'Carbs_g_per_kg', 'Is_Produce']
        for col in cols:
            DF[col] = pd.to_numeric(DF[col], errors='coerce')
        
        DF.dropna(inplace=True)
        DF.set_index('Product_Name', inplace=True)
        
        DATA_LOADED = True
        print(f"SUCCESS: Database loaded successfully.")
        return True

    except Exception as e:
        print(f"FATAL ERROR beim Laden von {DEBUG_PATH}: {e}")
        # Wir listen den Ordnerinhalt auf, um zu sehen, was da ist
        try:
            print(f"Dateien im Ordner {base_dir}: {os.listdir(base_dir)}")
        except:
            pass
        return False

# Initialer Startversuch
load_data()

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Wenn Daten fehlen, versuche Neu-Laden (Self-Healing)
    if not DATA_LOADED:
        load_data()
        if not DATA_LOADED:
            return jsonify({
                "status": "FATAL ERROR",
                "message": f"Server Error: Database file not found at {DEBUG_PATH}.",
                "hint": "Check Render logs to see file structure."
            }), 500

    try:
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0))
        fett_max = float(request.args.get('fat', 700.0))
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
        gemuese_min = float(request.args.get('produce', 4.0))
    except:
        return jsonify({"error": "Invalid parameters."}), 400

    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = DF.index.tolist()
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')

    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte])

    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]) <= budget_max
    prob += pulp.lpSum([DF.loc[p, 'Protein_g_per_kg'] * produkt_mengen[p] for p in produkte]) >= protein_min
    prob += pulp.lpSum([DF.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max
    prob += pulp.lpSum([DF.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max
    
    gemuese_produkte = DF[DF['Is_Produce'] == 1].index.tolist()
    prob += pulp.lpSum([produkt_mengen[p] for p in gemuese_produkte]) >= gemuese_min

    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
         return jsonify({"status": "Error", "message": str(e)}), 500

    if pulp.LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            if pulp.value(v) > 0.001:
                clean_name = v.name.replace('Menge_', '').replace('_', ' ')
                einkaufsliste[clean_name] = f"{pulp.value(v):.2f} kg"

        return jsonify({
            "status": "Success",
            "total_cost": f"{pulp.value(prob.objective):.2f} €",
            "optimized_shopping_list": einkaufsliste
        })
    else:
        return jsonify({"status": "Error", "message": "Optimization failed."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
