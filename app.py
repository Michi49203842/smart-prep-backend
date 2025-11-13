from flask import Flask, request, jsonify
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, value
import pandas as pd
import os

app = Flask(__name__)

# --- 1. DATEN VORBEREITEN (Liest die große CSV-Datei beim Start) ---
try:
    # Wichtig: Der Code sucht jetzt nach dem neuen Dateinamen 'food_data.csv'
    df = pd.read_csv('food_data.csv') 
    # Wichtig: Der Index ist nun 'Product_Name'
    df.set_index('Product_Name', inplace=True)
    DATA_LOADED = True
except FileNotFoundError:
    df = pd.DataFrame()
    DATA_LOADED = False
except pd.errors.ParserError as e:
    df = pd.DataFrame()
    DATA_LOADED = False
    print(f"--- PATH CHECK ---: The code tried to load the file at: {FILE_PATH}") 
    

@app.route('/optimize', methods=['GET'])
def run_optimization():
    # Zuerst prüfen, ob die Datenbasis geladen werden konnte
    if not DATA_LOADED:
        return jsonify({
            "status": "FATAL ERROR",
            "meldung": "Datenbankdatei 'food_data.csv' konnte nicht geladen werden. Bitte prüfen Sie den Dateinamen und die Spaltenformatierung."
        }), 500
    
    # --- 2. PARAMETER AUS DER ANFRAGE LESEN (Input vom Nutzer) ---
    try:
        # Liest die 5 Haupt-Constraints aus der URL
        budget_max = float(request.args.get('budget', 50.0))
        protein_min = float(request.args.get('protein', 1050.0))
        fett_max = float(request.args.get('fat', 700.0)) # URL-Parameter 'fat'
        kohlenhydrate_max = float(request.args.get('carbs', 3500.0)) # URL-Parameter 'carbs'
        gemuese_min = float(request.args.get('produce', 4.0)) # URL-Parameter 'produce' (in kg)
        
    except (TypeError, ValueError):
        return jsonify({"error": "Ungültiger Parameterwert. Bitte nur Zahlen senden."}), 400

    # --- 3. DAS OPTIMIERUNGSPROBLEM ERSTELLEN ---
    prob = LpProblem("Ernahrungsoptimierung", LpMinimize)
    produkte = df.index.tolist()
    
    # Definiere die Variablen (Menge x_i jedes Produkts)
    produkt_mengen = LpVariable.dicts("Menge", produkte, lowBound=0, cat='Continuous')

    # --- 4. ZIELFUNKTION (Minimiere die Gesamtkosten) ---
    # Nutzt den neuen Spaltennamen: 'Price_per_kg_EUR'
    prob += lpSum([df.loc[produkt, 'Price_per_kg_EUR'] * produkt_mengen[produkt]
                   for produkt in produkte]), "Gesamtkosten"

    # --- 5. NEBENBEDINGUNGEN (Constraints) ---

    # C1: Budget darf nicht überschritten werden
    prob += lpSum([df.loc[produkt, 'Price_per_kg_EUR'] * produkt_mengen[produkt]
                   for produkt in produkte]) <= budget_max, "Budget_Constraint"

    # C2: Minimales Protein muss erreicht werden (Nutzt neuen Spaltennamen)
    prob += lpSum([df.loc[produkt, 'Protein_g_per_kg'] * produkt_mengen[produkt]
                   for produkt in produkte]) >= protein_min, "Protein_Constraint"

    # C3: Maximales Fett darf nicht überschritten werden (Nutzt neuen Spaltennamen)
    prob += lpSum([df.loc[produkt, 'Fat_g_per_kg'] * produkt_mengen[produkt]
                   for produkt in produkte]) <= fett_max, "Fat_Constraint"

    # C4: Maximale Kohlenhydrate dürfen nicht überschritten werden (Nutzt neuen Spaltennamen)
    prob += lpSum([df.loc[produkt, 'Carbs_g_per_kg'] * produkt_mengen[produkt]
                   for produkt in produkte]) <= kohlenhydrate_max, "Carbs_Constraint"

    # C5: Essbarkeit (Minimale Menge an Gemüse/Obst - Nutzt neuen Spaltennamen)
    # Filtert nur Produkte, bei denen 'Is_Produce' auf 1 gesetzt ist
    gemuese_produkte = df[df['Is_Produce'] == 1].index.tolist()
    prob += lpSum([produkt_mengen[produkt] for produkt in gemuese_produkte]) >= gemuese_min, "Produce_Constraint"

    # --- 6. PROBLEM LÖSEN ---
    try:
        # Importiert die Solver-Klasse und wendet den Pfad an.
        solver = pulp.GLPK_CMD(path='glpsol.exe')
        prob.solve(solver)
    except Exception as e:
         return jsonify({"status": "Fehler", "meldung": f"Fehler bei der Lösungsberechnung: {str(e)}"})

    # --- 7. ERGEBNISSE FÜR JSON ZURÜCKGEBEN ---
    if LpStatus[prob.status] == "Optimal":
        einkaufsliste = {}
        for v in prob.variables():
            # Die Namen der Produkte werden bereinigt (Menge_Product_Name -> Product_Name)
            if v.varValue > 0.001:
                einkaufsliste[v.name.replace('Menge_', '').replace('_', ' ')] = f"{v.varValue:.2f} kg"

        return jsonify({
            "status": "Erfolgreich",
            "gesamtkosten": f"{value(prob.objective):.2f} €",
            "optimierte_einkaufsliste": einkaufsliste
        })
    else:
        return jsonify({
            "status": "Fehler",
            "meldung": f"Die Optimierung konnte keine Lösung finden. Der Status ist: {LpStatus[prob.status]}. Versuch, die Constraints zu lockern (z.B. Budget erhöhen oder Ziele senken)."
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
