from flask import Flask, request, jsonify
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, value, PULP_CBC_CMD
from flask_cors import CORS
import pandas as pd
import os
import sys
import traceback  # NEU: Das Werkzeug für den Fehlerbericht

app = Flask(__name__)
CORS(app)

# --- 1. DATEN VORBEREITEN ---
DATA_LOADED = False
DF = None
DEBUG_MSG = ""

def load_data():
    global DATA_LOADED, DF, DEBUG_MSG
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        FILE_PATH = os.path.join(base_dir, 'food_data.csv')
        DEBUG_MSG = f"Lade Pfad: {FILE_PATH}"

        try:
            DF = pd.read_csv(FILE_PATH, encoding='utf-8')
        except UnicodeDecodeError:
            DF = pd.read_csv(FILE_PATH, encoding='latin-1')

        # Bereinigung: Alles zu Zahlen machen, was Zahlen sein sollen
        cols = ['Price_per_kg_EUR', 'Protein_g_per_kg', 'Fat_g_per_kg', 'Carbs_g_per_kg', 'Is_Produce']
        for col in cols:
            DF[col] = pd.to_numeric(DF[col], errors='coerce')
        
        DF.dropna(inplace=True)
        DF.set_index('Product_Name', inplace=True)
        
        DATA_LOADED = True
        print(f"SUCCESS: {len(DF)} Produkte geladen.")
        return True

    except Exception as e:
        DEBUG_MSG = f"Fehler beim Laden: {str(e)}"
        print(f"FATAL ERROR: {DEBUG_MSG}")
        return False

load_data()

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Wir wickeln ALLES in einen Try-Block, damit der Server nicht abstürzt (500),
    # sondern uns den Fehler als JSON zeigt.
    try:
        if not DATA_LOADED:
            # Versuch neu zu laden
            if not load_data():
                return jsonify({
                    "status": "FATAL ERROR",
                    "message": "Database load failed.",
                    "details": DEBUG_MSG
                }), 500

        # Parameter lesen
        try:
            budget_max = float(request.args.get('budget', 50.0))
            protein_min = float(request.args.get('protein', 1050.0))
            fett_max = float(request.args.get('fat', 700.0))
            kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
            gemuese_min = float(request.args.get('produce', 4.0))
            
            # Vielfalts-Parameter
            max_per_item = 1.5 
            min_per_item = 0.2 
            min_unique_items = 6 
        except ValueError as e:
            return jsonify({"error": "Parameter Error", "details": str(e)}), 400

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

        # Vielfalts-Logik
        for p in produkte:
            limit = max_per_item
            if DF.loc[p, 'Is_Produce'] == 1: limit = 4.0
                
            prob += produkt_mengen[p] <= limit * produkt_gewaehlt[p]
            prob += produkt_mengen[p] >= min_per_item * produkt_gewaehlt[p]

        prob += pulp.lpSum([produkt_gewaehlt[p] for p in produkte]) >= min_unique_items

        # Lösen
        prob.solve(pulp.PULP_CBC_CMD(msg=0))

        if pulp.LpStatus[prob.status] == "Optimal":
            einkaufsliste = {}
            for v in prob.variables():
                if "Menge" in v.name and v.varValue > 0.001:
                    clean_name = v.name.replace('Menge_', '').replace('_', ' ')
                    einkaufsliste[clean_name] = f"{v.varValue:.2f} kg"

            return jsonify({
                "status": "Success",
                "total_cost": f"{pulp.value(prob.objective):.2f} €",
                "optimized_shopping_list": einkaufsliste
            })
        else:
            return jsonify({
                "status": "Error", 
                "message": f"Optimization failed. Status: {pulp.LpStatus[prob.status]}",
                "hint": "Budget too low or constraints too strict."
            }), 500

    except Exception as e:
        # HIER IST DER CRASH REPORTER:
        return jsonify({
            "status": "CRASH",
            "message": "Internal Code Error",
            "error_details": str(e),
            "traceback": traceback.format_exc()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
