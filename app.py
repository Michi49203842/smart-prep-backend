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
    print(f"SUCCESS: Database loaded.")

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
        
        # NEU: Maximale Menge pro Produkt (Standard: 1.5kg, damit man nicht nur Mehl isst)
        max_per_item = float(request.args.get('variety', 1.5)) 
    except:
        return jsonify({"error": "Invalid parameters."}), 400

    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = DF.index.tolist()
    
    # Variablen definieren
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')
    
    # NEU: Binäre Variable (1 = Produkt wird gekauft, 0 = nicht gekauft)
    # Das brauchen wir, um "Anzahl verschiedener Produkte" zu zählen
    produkt_gewaehlt = pulp.LpVariable.dicts("Gewaehlt", produkte, cat='Binary')

    # Zielfunktion: Kosten minimieren
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]), "Total_Cost"

    # --- Constraints ---
    
    # Nährwerte & Budget
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]) <= budget_max
    prob += pulp.lpSum([DF.loc[p, 'Protein_g_per_kg'] * produkt_mengen[p] for p in produkte]) >= protein_min
    prob += pulp.lpSum([DF.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max
    prob += pulp.lpSum([DF.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max
    
    # Gemüse Constraint
    gemuese_produkte = DF[DF['Is_Produce'] == 1].index.tolist()
    if len(gemuese_produkte) > 0:
        prob += pulp.lpSum([produkt_mengen[p] for p in gemuese_produkte]) >= gemuese_min

    # --- NEUE REGELN FÜR ABWECHSLUNG (Humanizing AI) ---
    
    for p in produkte:
        # 1. Verknüpfung: Wenn Menge > 0, dann ist Gewaehlt = 1
        # (Menge <= Gewaehlt * Ein_Sehr_Großer_Wert)
        prob += produkt_mengen[p] <= produkt_gewaehlt[p] * 1000
        
        # 2. "Kein Hamstern": Kein Produkt darf mehr als 'max_per_item' kg haben
        # Ausnahme: Gemüse darf man mehr essen (z.B. Kartoffeln)
        limit = max_per_item
        if DF.loc[p, 'Is_Produce'] == 1: 
            limit = max_per_item * 2 # Gemüse darf doppelt so viel sein
            
        prob += produkt_mengen[p] <= limit

    # 3. "Vielfalt": Mindestens 5 verschiedene Produkte kaufen
    prob += pulp.lpSum([produkt_gewaehlt[p] for p in produkte]) >= 5

    # --- Lösen ---
    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
         return jsonify({"status": "Error", "message": str(e)}), 500

    if pulp.LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            # Wir wollen nur die Mengen-Variablen in der Ausgabe, nicht die Binär-Variablen
            if "Menge" in v.name and v.varValue > 0.001:
                clean_name = v.name.replace('Menge_', '').replace('_', ' ')
                einkaufsliste[clean_name] = f"{v.varValue:.2f} kg"

        return jsonify({
            "status": "Success",
            "total_cost": f"{pulp.value(prob.objective):.2f} €",
            "optimized_shopping_list": einkaufsliste,
            "variety_score": f"{len(einkaufsliste)} Produkte"
        })
    else:
        return jsonify({
            "status": "Error", 
            "message": "Nicht lösbar! Deine Regeln für Vielfalt oder Budget sind zu streng. Erhöhe das Budget etwas."
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
