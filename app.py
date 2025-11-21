from flask import Flask, request, jsonify import pulp from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, value, PULP_CBC_CMD from flask_cors import CORS import pandas as pd import os import sys

app = Flask(name) CORS(app)

try: try: base_dir = os.path.dirname(os.path.abspath(sys.argv[0])) except: base_dir = os.path.dirname(os.path.abspath(file))

FILE_PATH = os.path.join(base_dir, 'food_data.csv')

try:
    df = pd.read_csv(FILE_PATH, encoding='utf-8')
except UnicodeDecodeError:
    df = pd.read_csv(FILE_PATH, encoding='latin-1')

df.set_index('Product_Name', inplace=True)
DATA_LOADED = True
print(f"SUCCESS: Database loaded from {FILE_PATH}")
except Exception as e: df = pd.DataFrame() DATA_LOADED = False print(f"FATAL ERROR: {e}")

@app.route('/optimize', methods=['GET']) def run_optimization(): if not DATA_LOADED: return jsonify({"status": "FATAL ERROR", "message": "Database could not be loaded."}), 500

try:
    budget_max = float(request.args.get('budget', 50.0))
    protein_min = float(request.args.get('protein', 1050.0))
    fett_max = float(request.args.get('fat', 700.0))
    kohlenhydrate_max = float(request.args.get('carbs', 3500.0))
    gemuese_min = float(request.args.get('produce', 4.0))
except:
    return jsonify({"error": "Invalid parameters."}), 400

prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
produkte = df.index.tolist()
produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')

prob += pulp.lpSum([df.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte])

prob += pulp.lpSum([df.loc[p, 'Price_per_kg_EUR'] * produkt_mengen[p] for p in produkte]) <= budget_max
prob += pulp.lpSum([df.loc[p, 'Protein_g_per_kg'] * produkt_mengen[p] for p in produkte]) >= protein_min
prob += pulp.lpSum([df.loc[p, 'Fat_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= fett_max
prob += pulp.lpSum([df.loc[p, 'Carbs_g_per_kg'] * produkt_mengen[p] for p in produkte]) <= kohlenhydrate_max

gemuese_produkte = df[df['Is_Produce'] == 1].index.tolist()
prob += pulp.lpSum([produkt_mengen[p] for p in gemuese_produkte]) >= gemuese_min

try:
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
except Exception as e:
     return jsonify({"status": "Error", "message": str(e)}), 500

if pulp.LpStatus[prob.status] == "Optimal":
    einkaufsliste = {}
    for v in prob.variables():
        if pulp.value(v) > 0.001:
            einkaufsliste[v.name.replace('Menge_', '').replace('_', ' ')] = f"{pulp.value(v):.2f} kg"

    return jsonify({
        "status": "Success",
        "total_cost": f"{pulp.value(prob.objective):.2f} €",
        "optimized_shopping_list": einkaufsliste
    })
else:
    return jsonify({"status": "Error", "message": "Optimization failed."}), 500
if name == 'main': port = int(os.environ.get("PORT", 5000)) app.run(host='0.0.0.0', port=port)
