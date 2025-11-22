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
        # Pfad finden
        try:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        except:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        FILE_PATH = os.path.join(base_dir, 'food_data.csv')

        # Laden
        try:
            DF = pd.read_csv(FILE_PATH, encoding='utf-8')
        except UnicodeDecodeError:
            DF = pd.read_csv(FILE_PATH, encoding='latin-1')

        # --- AGGRESSIVE REINIGUNG (Der Fix) ---
        # 1. Spaltennamen bereinigen (Leerzeichen entfernen)
        DF.columns = DF.columns.str.strip()

        # 2. Zahlen erzwingen
        cols_to_fix = ['Price_per_kg_EUR', 'Protein_g_per_kg', 'Fat_g_per_kg', 'Carbs_g_per_kg', 'Is_Produce']
        
        for col in cols_to_fix:
            # Wandelt alles in Zahlen um. Fehlerhafte Werte (wie "1\r") werden repariert.
            DF[col] = pd.to_numeric(DF[col], errors='coerce')
        
        # 3. Leere Zeilen löschen
        DF.dropna(inplace=True)
        
        # 4. Sicherstellen, dass Is_Produce wirklich 0 oder 1 ist
        DF['Is_Produce'] = DF['Is_Produce'].astype(int)

        DF.set_index('Product_Name', inplace=True)
        
        # DIAGNOSE: Wie viele Gemüse haben wir gefunden?
        gemuese_anzahl = len(DF[DF['Is_Produce'] == 1])
        DEBUG_INFO = f"Daten geladen. Produkte: {len(DF)}. Gemüse gefunden: {gemuese_anzahl}"
        print(f"SUCCESS: {DEBUG_INFO}")
        
        DATA_LOADED = True
        return True

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        DATA_LOADED = False
        return False

# Starten
load_and_clean_data()

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Self-Healing
    if not DATA_LOADED:
        load_and_clean_data()
        if not DATA_LOADED:
            return jsonify({"status": "FATAL ERROR", "message": "Server Error: Could not load data."}), 500

    try:
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0))
        fett_max = float(request.args.get('fat', 700.0))
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
        gemuese_min = float(request.args.get('produce', 4.0))
    except:
        return jsonify({"error": "Invalid parameters."}), 400

    # Optimierung
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
    
    # Sicherheitscheck: Wenn keine Gemüseprodukte erkannt wurden, wird diese Regel unmöglich
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
            "optimized_shopping_list": einkaufsliste,
            "debug_info": DEBUG_INFO
        })
    else:
        # Wir geben jetzt Debug-Infos zurück, damit du siehst, was los ist
        return jsonify({
            "status": "Error",
            "message": f"Optimization failed. Status: {pulp.LpStatus[prob.status]}.",
            "debug_info": DEBUG_INFO,
            "hint": f"Gefundene Gemüse-Produkte: {len(gemuese_produkte)}. Wenn das 0 ist, liegt es an der CSV."
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
