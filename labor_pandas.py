import pandas as pd
import os
import sys

# --- 1. DATEN LADEN (Das Fundament) ---
# Wir nutzen den Pfad-Trick, damit es immer funktioniert
try:
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
except:
    base_dir = os.path.dirname(os.path.abspath(__file__))

file_path = os.path.join(base_dir, 'food_data.csv')

# Der DataFrame ('df') ist deine programmierbare Excel-Tabelle
# Wir lesen die CSV ein. encoding='utf-8' ist Standard, aber wir sichern uns ab.
try:
    df = pd.read_csv(file_path, encoding='utf-8')
except:
    df = pd.read_csv(file_path, encoding='latin-1')

print(f"--- 1. DATENSATZ GELADEN ({len(df)} Produkte) ---")
# .head(3) zeigt die ersten 3 Zeilen zur Kontrolle
print(df.head(3)) 
print("\n" + "="*50 + "\n")


# --- 2. FILTERN (Die KI-Logik) ---
# Szenario: Finde Produkte mit viel Protein (>150g) die günstig sind (< 5€).
# Logik: Wir wenden eine "Maske" auf den DataFrame an.

# Die Logik: (Spalte Protein > 150) UND (Spalte Preis < 5.00)
high_protein_cheap = df[ (df['Protein_g_per_kg'] > 150) & (df['Price_per_kg_EUR'] < 5.00) ]

print("--- 2. FILTER: BILLIGES PROTEIN ---")
# Wir zeigen nur Name, Preis und Protein an
print(high_protein_cheap[['Product_Name', 'Price_per_kg_EUR', 'Protein_g_per_kg']])
print("\n" + "="*50 + "\n")


# --- 3. FEATURE ENGINEERING (Neues Wissen schaffen) ---
# Wir berechnen eine neue Kennzahl, die nicht in der CSV steht:
# "Gramm Protein pro Euro". Das hilft beim Sparen.

# Pandas rechnet hier mit der GANZEN SPALTE auf einmal (Vektorisierung)
df['Protein_per_Euro'] = df['Protein_g_per_kg'] / df['Price_per_kg_EUR']

# Wir sortieren die Tabelle nach dieser neuen Spalte (absteigend)
best_value = df.sort_values(by='Protein_per_Euro', ascending=False)

print("--- 3. PREIS-LEISTUNGS-SIEGER (Top 5) ---")
print(best_value[['Product_Name', 'Protein_per_Euro']].head(5))
print("\n" + "="*50 + "\n")


# --- 4. AGGREGATION (Statistik) ---
# Vergleich: Wie viel teurer ist Gemüse im Schnitt im Vergleich zu Nicht-Gemüse?
# 0 = Kein Gemüse, 1 = Gemüse

analyse = df.groupby('Is_Produce')['Price_per_kg_EUR'].mean()

print("--- 4. DURCHSCHNITTSPREISE ---")
# Wir nutzen .get(), um sicherzugehen, dass der Index existiert (falls keine 0 oder 1 da ist)
print(f"Tierisch/Getreide (0): {analyse.get(0, 0):.2f} €/kg")
print(f"Gemüse/Obst (1):       {analyse.get(1, 0):.2f} €/kg")
