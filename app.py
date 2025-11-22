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

def load_data():
    global DATA_LOADED, DF, DEBUG_INFO
    try:
        # FINALER FIX: Wir nutzen NUR __file__. 
        # Das garantiert, dass wir im Ordner der app.py suchen.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        FILE_PATH = os.path.join(base_dir, 'food_data.csv')
        
        # Wir speichern den Pfad für Fehlermeldungen
        DEBUG_INFO = f"Suche Datei in: {FILE_PATH}"
        print(f"DEBUG: {DEBUG_INFO}")

        # Versuche utf-8, falle zurück auf latin-1 wenn nötig
        try:
            DF = pd.read_csv(FILE_PATH, encoding='utf-8')
        except UnicodeDecodeError:
            DF = pd.read_csv(FILE_PATH, encoding='latin-1')

        # Bereinigung der Daten (Leerzeichen entfernen, Zahlen erzwingen)
        DF.columns = DF.columns.str.strip()
        cols = ['Price_per_kg_EUR', 'Protein_g_per_kg', 'Fat_g_per_kg', 'Carbs_g_per_kg', 'Is_Produce']
        for col in cols:
            DF[col] = pd.to_numeric(DF[col], errors='coerce')
        
        DF.dropna(inplace=True)
        DF.set_index('Product_Name', inplace=True)
        
        DATA_LOADED = True
        print(f"SUCCESS: Database loaded successfully.")
        return True

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        DATA_LOADED = False
        return False

# Initialer Start
load_data()

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Wenn Daten nicht geladen sind, versuche es noch einmal (Self-Healing)
    if not DATA_LOADED:
        load_data()
        if not DATA_LOADED:
            # Wir geben den Pfad zurück, damit du siehst, wo er gesucht hat
            return jsonify({
                "status": "FATAL ERROR",
                "message": "Server Error: Could not load data.",
                "debug_path": DEBUG_INFO
            }), 500

    # --- Parameter lesen ---
    try:
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0))
        fett_max = float(request.args.get('fat', 700.0))
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
        gemuese_min = float(request.args.get('produce', 4.0))
    except:
        return jsonify({"error": "Invalid parameters."}), 400

    # --- Optimierung ---
    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = DF.index.tolist()
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')

    # Zielfunktion
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte])

    # Constraints
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]) <= budget_max
    prob += pulp.lpSum([DF.loc[p, 'Protein_g_per_kg'] * produkt_mengen[p] for p in produkte]) >= protein_min
    prob += pulp.lpSum([DF.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max
    prob += pulp.lpSum([DF.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max
    
    # Gemüse Constraint
    gemuese_produkte = DF[DF['Is_Produce'] == 1].index.tolist()
    if len(gemuese_produkte) > 0:
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
        return jsonify({
            "status": "Error",
            "message": "Optimization failed. Budget too low or goals too high."
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
