from flask import Flask, request, jsonify
# Importiert PuLP als Modul und die notwendigen Funktionen
import pulp 
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, value, PULP_CBC_CMD
import pandas as pd
import os
import sys 

app = Flask(__name__)

# --- 1. DATEN VORBEREITEN (Liest die große CSV-Datei beim Start) ---
try:
    # Definiert den absoluten Pfad zur food_data.csv (behebt lokale und Server-Pfadfehler)
    # Nutzt immer den Ordner, in dem die app.py liegt
    base_dir = os.path.dirname(os.path.abspath(__file__))
        
    FILE_PATH = os.path.join(base_dir, 'food_data.csv')

    # Lade die Daten über den absolut korrekten Pfad
    df = pd.read_csv(FILE_PATH) 
    df.set_index('Product_Name', inplace=True)
    DATA_LOADED = True
except FileNotFoundError:
    df = pd.DataFrame()
    DATA_LOADED = False
    # Diese Meldung wird nur im Terminal angezeigt, wenn der Pfad fehlschlägt
    print(f"FATAL ERROR: CSV file not found at the expected path: {FILE_PATH}")
except pd.errors.ParserError as e:
    df = pd.DataFrame()
    DATA_LOADED = False
    print(f"FATAL CSV ERROR: Check formatting/commas. Error: {e}") 
    

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Zuerst prüfen, ob die Datenbasis beim Start geladen werden konnte
    if not DATA_LOADED:
        return jsonify({
            "status": "FATAL ERROR",
            "message": "Database file 'food_data.csv' could not be loaded. Please check file name, location, and column formatting."
        }), 500
    
    # --- 2. PARAMETER AUS DER ANFRAGE LESEN (Input vom Nutzer) ---
    try:
        # Liest die 5 Haupt-Constraints aus der URL
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0)) # Gram
        fett_max = float(request.args.get('fat', 700.0)) # Gram
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0)) # Gram
        gemuese_min = float(request.args.get('produce', 4.0)) # Kilogramm
        
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid parameter value. Please only send numbers."}), 400

    # --- 3. DAS OPTIMIERUNGSPROBLEM ERSTELLEN ---
    prob = pulp.LpProblem("Nutrition_Optimization", pulp.LpMinimize)
    produkte = df.index.tolist()
    
    # Definiere die Variablen (Menge x_i jedes Produkts)
    produkt_mengen = pulp.LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')

    # --- 4. ZIELFUNKTION (Minimiere die Gesamtkosten) ---
    prob += pulp.lpSum([df.loc[produkt, 'Price_per_kg_EUR'] * produkt_mengen[produkt]
                   for produkt in produkte]), "Total_Cost"

    # --- 5. NEBENBEDINGUNGEN (Constraints) ---

    # C1: Budget darf nicht überschritten werden
    prob += pulp.lpSum([df.loc[produkt, 'Price_per_kg_EUR'] * produkt_mengen[produkt]
                   for produkt in produkte]) <= budget_max, "Budget_Constraint"

    # C2: Minimales Protein muss erreicht werden
    prob += pulp.lpSum([df.loc[produkt, 'Protein_g_per_kg'] * produkt_mengen[produkt]
                   for produkt in produkte]) >= protein_min, "Protein_Constraint"

    # C3: Maximales Fett darf nicht überschritten werden
    prob += pulp.lpSum([df.loc[produkt, 'Fat_g_per_kg'] * produkt_mengen[produkt]
                   for produkt in produkte]) <= fett_max, "Fat_Constraint"

    # C4: Maximale Kohlenhydrate dürfen nicht überschritten werden
    prob += pulp.lpSum([df.loc[produkt, 'Carbs_g_per_kg'] * produkt_mengen[produkt]
                   for produkt in produkte]) <= kohlenhydrate_max, "Carbs_Constraint"

    # C5: Essbarkeit (Minimale Menge an Gemüse/Obst)
    gemuese_produkte = df[df['Is_Produce'] == 1].index.tolist()
    prob += pulp.lpSum([produkt_mengen[produkt] for produkt in gemuese_produkte]) >= gemuese_min, "Produce_Constraint"

    # --- 6. PROBLEM LÖSEN ---
    try:
        # ENDGÜLTIGER FIX: Nutzt den universellen CBC-Solver 
        prob.solve(pulp.PULP_CBC_CMD()) 
    except Exception as e:
         return jsonify({"status": "Error", "message": f"Fatal Optimization Error: {str(e)}"}), 500

    # --- 7. ERGEBNISSE FÜR JSON ZURÜCKGEBEN ---
    if pulp.LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            if pulp.value(v) > 0.001:
                # Macht die Produktnamen im Output wieder lesbar
                einkaufsliste[v.name.replace('Menge_', '').replace('_', ' ')] = f"{pulp.value(v):.2f} kg"

        return jsonify({
            "status": "Success",
            "total_cost": f"{pulp.value(prob.objective):.2f} €",
            "optimized_shopping_list": einkaufsliste
        })
    else:
        # Rückgabe, wenn keine Lösung gefunden wurde (z.B. Budget zu niedrig)
        return jsonify({
            "status": "Error",
            "message": f"Optimization failed. Status: {pulp.LpStatus[prob.status]}. Try loosening constraints (e.g., increase budget or lower goals)."
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
