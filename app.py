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
        # Robuster Pfad-Fix
        base_dir = os.path.dirname(os.path.abspath(__file__))
        FILE_PATH = os.path.join(base_dir, 'food_data.csv')
        DEBUG_INFO = f"Lade Daten von: {FILE_PATH}"
        print(f"DEBUG: {DEBUG_INFO}")

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
        print(f"SUCCESS: {len(DF)} Produkte geladen.")
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
        
        # NEU: Vielfalts-Parameter
        # Maximale Menge pro Produkt (in kg), damit man nicht 5kg Mehl bekommt
        max_per_item = 1.5 
        # Mindestanzahl verschiedener Produkte
        min_unique_items = 6
        
    except:
        return jsonify({"error": "Invalid parameters."}), 400

    # --- Optimierung ---
    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = DF.index.tolist()
    
    # Variable 1: Die Menge (Wie viel kg kaufe ich?)
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')
    
    # Variable 2 (NEU): Der Schalter (Kaufe ich es überhaupt? 0 oder 1)
    produkt_gewaehlt = pulp.LpVariable.dicts("Gewaehlt", produkte, cat='Binary')

    # Zielfunktion: Kosten minimieren
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]), "Total_Cost"

    # --- Standard Constraints ---
    prob += pulp.lpSum([DF.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]) <= budget_max, "Budget"
    prob += pulp.lpSum([DF.loc[p, 'Protein_g_per_kg'] * produkt_mengen[p] for p in produkte]) >= protein_min, "Protein"
    prob += pulp.lpSum([DF.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max, "Fat"
    prob += pulp.lpSum([DF.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max, "Carbs"
    
    # Gemüse Constraint
    gemuese_produkte = DF[DF['Is_Produce'] == 1].index.tolist()
    if len(gemuese_produkte) > 0:
        prob += pulp.lpSum([produkt_mengen[p] for p in gemuese_produkte]) >= gemuese_min

    # --- NEUE VIELFALTS-REGELN ---
    for p in produkte:
        # Regel A: "Hamster-Bremse"
        # Wenn es Gemüse ist, erlauben wir etwas mehr (3kg), sonst nur 1.5kg
        limit = max_per_item
        if DF.loc[p, 'Is_Produce'] == 1:
            limit = 3.0
            
        # Verknüpft die Menge mit dem Schalter:
        # Menge <= Limit * Gewaehlt
        # Das heißt: Wenn Gewaehlt=0, MUSS Menge 0 sein. Wenn Gewaehlt=1, darf Menge bis zum Limit gehen.
        prob += produkt_mengen[p] <= limit * produkt_gewaehlt[p]

    # Regel B: "Vielfalts-Zwang"
    # Die Summe aller "Ja"-Schalter muss mindestens 6 sein
    prob += pulp.lpSum([produkt_gewaehlt[p] for p in produkte]) >= min_unique_items

    # --- Lösen ---
    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
         return jsonify({"status": "Error", "message": str(e)}), 500

    if pulp.LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            # Wir zeigen nur die Mengen an, die > 0 sind
            if "Menge" in v.name and v.varValue > 0.001:
                clean_name = v.name.replace('Menge_', '').replace('_', ' ')
                einkaufsliste[clean_name] = f"{pulp.value(v):.2f} kg"

        return jsonify({
            "status": "Success",
            "total_cost": f"{pulp.value(prob.objective):.2f} €",
            "optimized_shopping_list": einkaufsliste,
            "message": f"Optimiert mit mindestens {min_unique_items} verschiedenen Produkten."
        })
    else:
        return jsonify({
            "status": "Error",
            "message": "Nicht lösbar! Mit der neuen Vielfalts-Regel reicht das Budget evtl. nicht mehr. Erhöhe das Budget!"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
```

---

### 🚀 Schritt 2: Upload des Updates

Da wir die Logik geändert haben, müssen wir das Update hochladen.

Führe diese Befehle in deiner CMD (Ordner `FINAL_API`) aus:

```bash
git add .
git commit -m "Add variety constraints (humanizing the AI)"
git push origin master
