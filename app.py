<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartPrep AI</title>
    <style>
        /* Modernes Mobile-App Design */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f2f2f7;
            display: flex;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }
        .app-container {
            background-color: white;
            width: 100%;
            max-width: 400px;
            min-height: 100vh;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
        }
        .header {
            background-color: #007AFF;
            color: white;
            padding: 20px;
            text-align: center;
            font-weight: bold;
            font-size: 1.2em;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .content {
            padding: 20px;
            flex: 1;
            overflow-y: auto;
        }
        .intro-text {
            color: #666;
            text-align: center;
            margin-bottom: 25px;
            font-size: 0.95em;
        }
        .input-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
            color: #333;
            font-size: 0.9em;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
            box-sizing: border-box;
            background-color: #f9f9f9;
            transition: border-color 0.3s;
        }
        input:focus {
            border-color: #007AFF;
            outline: none;
            background-color: white;
        }
        button {
            width: 100%;
            background-color: #34C759; /* Apple Green */
            color: white;
            padding: 16px;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
            box-shadow: 0 4px 6px rgba(52, 199, 89, 0.2);
            transition: transform 0.1s, background-color 0.2s;
        }
        button:active {
            background-color: #248a3d;
            transform: scale(0.98);
        }
        button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }
        
        /* Ergebnis-Bereich */
        #result-area {
            margin-top: 30px;
            background-color: #fff;
            border-radius: 12px;
            padding: 0;
            display: none; /* Standardmäßig ausgeblendet */
            border: 1px solid #eee;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            overflow: hidden;
        }
        .result-header {
            background-color: #f0f0f5;
            padding: 15px;
            font-weight: bold;
            color: #333;
            border-bottom: 1px solid #e0e0e0;
            text-align: center;
        }
        .list-container {
            padding: 10px 15px;
        }
        .list-item {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 0.95em;
        }
        .list-item:last-child {
            border-bottom: none;
        }
        .item-name {
            color: #333;
        }
        .item-amount {
            font-weight: 600;
            color: #007AFF;
        }
        .total-cost {
            background-color: #34C759;
            color: white;
            padding: 15px;
            text-align: center;
            font-weight: bold;
            font-size: 1.2em;
        }
        
        /* Fehler-Box */
        .error-box {
            color: #d8000c;
            background-color: #ffbaba;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            display: none;
            border: 1px solid #d8000c;
            font-size: 0.9em;
            text-align: center;
        }
    </style>
</head>
<body>

<div class="app-container">
    <div class="header">SmartPrep 🥗</div>
    
    <div class="content">
        <p class="intro-text">
            Definiere deine Ziele und lass die KI den günstigsten Einkaufsplan berechnen.
        </p>

        <!-- EINGABE FELDER -->
        <div class="input-group">
            <label>💰 Budget (€)</label>
            <input type="number" id="budget" value="40" placeholder="z.B. 50">
        </div>
        <div class="input-group">
            <label>💪 Protein Ziel (g)</label>
            <input type="number" id="protein" value="1500" placeholder="Wochenziel">
        </div>
        <div class="input-group">
            <label>🥑 Fett Limit (g)</label>
            <input type="number" id="fat" value="500">
        </div>
        <div class="input-group">
            <label>🍞 Kohlenhydrate Limit (g)</label>
            <input type="number" id="carbs" value="5000">
        </div>
        <div class="input-group">
            <label>🥦 Gemüse & Obst Min (kg)</label>
            <input type="number" id="produce" value="4">
        </div>

        <button onclick="getOptimizedPlan()">Plan berechnen 🚀</button>

        <!-- FEHLER ANZEIGE -->
        <div id="error-box" class="error-box"></div>

        <!-- ERGEBNIS ANZEIGE -->
        <div id="result-area">
            <div class="result-header">Dein optimaler Einkauf:</div>
            <div class="list-container" id="shopping-list-content">
                <!-- Hier werden die Items per JS eingefügt -->
            </div>
            <div class="total-cost" id="total-cost-display"></div>
        </div>
    </div>
</div>

<script>
    // KORREKTE URL IST HIER FEST EINGEBAUT:
    const baseURL = "https://smart-prep-michi-api.onrender.com";

    async function getOptimizedPlan() {
        // 1. Werte aus den Feldern holen
        const budget = document.getElementById('budget').value;
        const protein = document.getElementById('protein').value;
        const fat = document.getElementById('fat').value;
        const carbs = document.getElementById('carbs').value;
        const produce = document.getElementById('produce').value;

        // UI aufräumen (Ladezustand anzeigen)
        const btn = document.querySelector('button');
        const resultArea = document.getElementById('result-area');
        const errorBox = document.getElementById('error-box');
        
        btn.innerText = "KI rechnet... ⏳";
        btn.disabled = true;
        resultArea.style.display = 'none';
        errorBox.style.display = 'none';

        // Die URL zusammenbauen
        const fullURL = `${baseURL}/optimize?budget=${budget}&protein=${protein}&fat=${fat}&carbs=${carbs}&produce=${produce}`;

        try {
            console.log("Sende Anfrage an:", fullURL);
            
            // 2. Den Request senden (Fetch API)
            const response = await fetch(fullURL);
            
            // Prüfen ob der Server überhaupt antwortet (Netzwerk ok?)
            if (!response.ok) {
                throw new Error(`Server Fehler: ${response.status}`);
            }

            const data = await response.json();

            if (data.status === "Success") {
                // 3. Erfolg! Liste anzeigen
                renderList(data);
            } else {
                // Logischer Fehler vom Server (z.B. "Infeasible")
                let errorMsg = data.message || data.meldung || "Unbekannter Fehler";
                
                // Benutzerfreundliche Übersetzung für häufige Fehler
                if (errorMsg.includes("Infeasible")) {
                    errorMsg = "Nicht möglich! Dein Budget ist zu niedrig für diese Ziele. Erhöhe das Budget oder senke das Protein-Ziel.";
                }
                
                showError(errorMsg);
            }

        } catch (error) {
            console.error("Verbindungsfehler:", error);
            showError("Verbindungsfehler! Der Server antwortet nicht. (Schläft er vielleicht? Warte 1 Minute und versuche es erneut.)");
        }

        // Button zurücksetzen
        btn.innerText = "Plan berechnen 🚀";
        btn.disabled = false;
    }

    function renderList(data) {
        const listContainer = document.getElementById('shopping-list-content');
        listContainer.innerHTML = ""; // Liste leeren

        // Durch das Dictionary loopen und Zeilen bauen
        for (const [produkt, menge] of Object.entries(data.optimized_shopping_list)) {
            listContainer.innerHTML += `
                <div class="list-item">
                    <span class="item-name">${produkt}</span>
                    <span class="item-amount">${menge}</span>
                </div>
            `;
        }

        // Gesamtkosten anzeigen
        document.getElementById('total-cost-display').innerText = "Gesamt: " + data.total_cost;
        
        // Ergebnisbereich einblenden
        document.getElementById('result-area').style.display = 'block';
    }

    function showError(msg) {
        const errorBox = document.getElementById('error-box');
        errorBox.innerText = msg;
        errorBox.style.display = 'block';
    }
</script>

</body>
</html>
