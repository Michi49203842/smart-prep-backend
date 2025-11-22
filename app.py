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
try:
    # Robuste Pfad-Logik für Windows und Linux (Render)
    try:
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    except:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    FILE_PATH = os.path.join(base_dir, 'food_data.csv')

    # Versuche utf-8, falle zurück auf latin-1 wenn nötig
    try:
        df = pd.read_csv(FILE_PATH, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(FILE_PATH, encoding='latin-1')

    df.set_index('Product_Name', inplace=True)
    DATA_LOADED = True
    print(f"SUCCESS: Database loaded from {FILE_PATH}")

except FileNotFoundError:
    df = pd.DataFrame()
    DATA_LOADED = False
    print("FATAL ERROR: CSV file not found.")
except Exception as e:
    df = pd.DataFrame()
    DATA_LOADED = False
    print(f"FATAL ERROR: {e}")


@app.route('/optimize', methods=['GET'])
def run_optimization():
    if not DATA_LOADED:
        return jsonify({
            "status": "FATAL ERROR",
            "message": "Database file 'food_data.csv' could not be loaded."
        }), 500

    # --- Parameter lesen ---
    try:
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0))
        fett_max = float(request.args.get('fat', 700.0))
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
        gemuese_min = float(request.args.get('produce', 4.0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid parameter value."}), 400

    # --- Optimierung starten ---
    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = df.index.tolist()
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')

    # Zielfunktion: Kosten minimieren
    prob += pulp.lpSum([df.loc[produkt, 'Price_per_kg_EUR'] * produkt_mengen[produkt] for produkt in produkte]), "Total_Cost"

    # Constraints
    prob += pulp.lpSum([df.loc[produkt, 'Price_per_kg_EUR'] * produkt_mengen[produkt] for produkt in produkte]) <= budget_max, "Budget_Constraint"
    prob += pulp.lpSum([df.loc[produkt, 'Protein_g_per_kg'] * produkt_mengen[produkt] for produkt in produkte]) >= protein_min, "Protein_Constraint"
    prob += pulp.lpSum([df.loc[produkt, 'Fat_g_per_kg'] * produkt_mengen[produkt] for produkt in produkte]) <= fett_max, "Fat_Constraint"
    prob += pulp.lpSum([df.loc[produkt, 'Carbs_g_per_kg'] * produkt_mengen[produkt] for produkt in produkte]) <= kohlenhydrate_max, "Carbs_Constraint"
    
    gemuese_produkte = df[df['Is_Produce'] == 1].index.tolist()
    prob += pulp.lpSum([produkt_mengen[produkt] for produkt in gemuese_produkte]) >= gemuese_min, "Produce_Constraint"

    # --- Lösen ---
    try:
        # WICHTIG: Nutzt den internen CBC Solver (Universell für Linux/Render)
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
         return jsonify({"status": "Error", "message": f"Fatal Optimization Error: {str(e)}"}), 500

    # --- Ergebnis ---
    if pulp.LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            if pulp.value(v) > 0.001:
                # Namen bereinigen (Unterstriche weg für schönere Anzeige)
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
    app.run(host='0.0.0.0', port=port, debug=True)
