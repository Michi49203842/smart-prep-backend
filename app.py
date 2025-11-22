from flask import Flask, request, jsonify
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, value, PULP_CBC_CMD
from flask_cors import CORS
import pandas as pd
import os
import sys

app = Flask(__name__)
CORS(app)

# --- DEBUGGING & DATEN VORBEREITEN ---
DATA_LOADED = False
DF = None

try:
    # 1. Wo bin ich gerade? (Der Ordner dieser app.py Datei)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"DEBUG: App liegt in: {base_dir}")
    
    # 2. Was liegt hier noch? (Listet alle Dateien im Ordner auf)
    try:
        files_in_dir = os.listdir(base_dir)
        print(f"DEBUG: Dateien in diesem Ordner: {files_in_dir}")
    except:
        print("DEBUG: Konnte Ordnerinhalt nicht lesen.")

    # 3. Pfad bauen
    FILE_PATH = os.path.join(base_dir, 'food_data.csv')
    print(f"DEBUG: Versuche zu laden: {FILE_PATH}")

    # 4. Laden
    try:
        DF = pd.read_csv(FILE_PATH, encoding='utf-8')
    except UnicodeDecodeError:
        DF = pd.read_csv(FILE_PATH, encoding='latin-1')

    DF.set_index('Product_Name', inplace=True)
    DATA_LOADED = True
    print("SUCCESS: Database loaded successfully.")

except Exception as e:
    print(f"FATAL ERROR beim Start: {e}")

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Erweiterte Fehlermeldung für den Browser
    if not DATA_LOADED:
        # Wir geben dem Browser die Debug-Infos, damit du siehst, was fehlt
        debug_info = "Check Render Logs for file list."
        try:
            base_d = os.path.dirname(os.path.abspath(__file__))
            files = str(os.listdir(base_d))
            debug_info = f"Ordner: {base_d} | Dateien vorhanden: {files}"
        except:
            pass
            
        return jsonify({
            "status": "FATAL ERROR",
            "message": "Database 'food_data.csv' not found.",
            "debug_info": debug_info
        }), 500

    # --- Optimierung ---
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
