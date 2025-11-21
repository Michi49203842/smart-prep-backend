import pandas as pd
import os
import sys

# --- 1. DATEN LADEN ---
try:
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
except:
    base_dir = os.path.dirname(os.path.abspath(__file__))

file_path = os.path.join(base_dir, 'food_data.csv')
df = pd.read_csv(file_path)

print("--- 1. DATENSATZ GELADEN ---")
print(f"Anzahl Produkte: {len(df)}")
print("\n" + "="*50 + "\n")


# --- 2. FILTERN (LÖSUNG: Vegan Low Carb) ---
# Aufgabe: Nur pflanzliche Produkte (Is_Produce == 1) mit wenig Kohlenhydraten (< 50g).

# Die Logik: Zwei Bedingungen verknüpft mit & (UND)
vegan_low_carb = df[ (df['Is_Produce'] == 1) & (df['Carbs_g_per_kg'] < 50) ]

print("--- 2. FILTER: VEGAN LOW CARB ---")
# Wir zeigen Name, Kohlenhydrate und Preis an
print(vegan_low_carb[['Product_Name', 'Carbs_g_per_kg', 'Price_per_kg_EUR']].head(10))
print("\n" + "="*50 + "\n")


# --- 3. FEATURE ENGINEERING ---
df['Protein_per_Euro'] = df['Protein_g_per_kg'] / df['Price_per_kg_EUR']
best_value = df.sort_values(by='Protein_per_Euro', ascending=False)

print("--- 3. PREIS-LEISTUNGS-SIEGER ---")
print(best_value[['Product_Name', 'Protein_per_Euro']].head(5))
print("\n" + "="*50 + "\n")


# --- 4. AGGREGATION ---
analyse = df.groupby('Is_Produce')['Price_per_kg_EUR'].mean()

print("--- 4. DURCHSCHNITTSPREISE ---")
print(f"Tierisch/Getreide (0): {analyse[0]:.2f} €/kg")
print(f"Gemüse/Obst (1):       {analyse[1]:.2f} €/kg")
