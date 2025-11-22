from flask import Flask, request, jsonify
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, value, PULP_CBC_CMD
from flask_cors import CORS
import pandas as pd
import os
import sys

app = Flask(__name__)
CORS(app)

# Globale Variablen
DATA_LOADED = False
DF = None
DEBUG_MSG = ""

def load_and_clean_data():
    global DATA_LOADED, DF, DEBUG_MSG
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

        # --- REINIGUNG & TYPE CASTING (Der Fix) ---
        # Wir zwingen Pandas, alle Zahlen-Spalten auch als Zahlen zu lesen
        cols_to_fix = ['Price_per_kg_EUR', 'Protein_g_per_kg', 'Fat_g_per_kg', 'Carbs_g_per_kg', 'Is_Produce']
        
        for col in cols_to_fix:
            # 'coerce' macht aus Fehlern (wie " ") ein NaN (Not a Number)
            DF[col] = pd.to_numeric(DF[col], errors='coerce')
        
        # Zeilen mit Fehlern löschen
        DF.dropna(inplace=True)
        
        # Is_Produce muss explizit Integer sein
        DF['Is_Produce'] = DF['Is_Produce'].astype(int)

        DF.set_index('Product_Name', inplace=True)
        
        # Checken wie viele Gemüse wir haben
        gemuese_count = len(DF[DF['Is_Produce'] == 1])
        DEBUG_MSG = f"Gelanden: {len(DF)} Produkte. Davon Gemüse: {gemuese_count}"
        print(f"SUCCESS: {DEBUG_MSG}")
        
        DATA_LOADED = True
        return True

    except Exception as e:
        DEBUG_MSG = f"Fehler beim Laden: {str(e)}"
        print(f"FATAL ERROR: {DEBUG_MSG}")
        DATA_LOADED = False
        return False

# Starten
load_and_clean_data()

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Self-Healing: Falls Daten weg sind, neu laden
    if not DATA_LOADED:
        load_and_clean_data()
        if not DATA_LOADED:
            return jsonify({"status": "FATAL ERROR", "message": DEBUG_MSG}), 500

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
    prob += pulp.lpSum([df.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max
    prob += pulp.lpSum([DF.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max
    
    # Gemüse Constraint (Hier lag vermutlich der Fehler)
    gemuese_produkte = DF[DF['Is_Produce'] == 1].index.tolist()
    prob += pulp.lpSum([produkt_mengen[p] for p in gemuese_produkte]) >= gemuese_min

    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
         return jsonify({"status": "Error", "message": str(e)}), 500

    # Ergebnis-Auswertung mit detailliertem Fehlerstatus
    status_text = pulp.LpStatus[prob.status]
    
    if status_text == "Optimal":
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
        # Wir geben jetzt Infos zurück, woran es lag
        gemuese_count = len(gemuese_produkte)
        return jsonify({
            "status": "Error",
            "message": f"Optimization failed. Status: {status_text}",
            "debug_info": f"Budget: {budget_max}, Found Produce Items in DB: {gemuese_count}"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
