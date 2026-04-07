# Percorso Demo — IMC-Group GANTT Agent
## Presentazione a Vincenzo Carolla

**Durata stimata:** 15-20 minuti
**Prerequisiti:** backend avviato, frontend su localhost:3000, dati fittizi con clienti reali

---

## Apertura (2 minuti)

**Cosa dici:**
"Ho costruito un prototipo di sistema GANTT con supporto IA che centralizza tutti i nostri progetti in un'unica piattaforma e calcola automaticamente l'impatto sugli altri progetti quando qualcosa cambia. Ti mostro cosa fa e poi ne parliamo."

**Nota:** non dire "è finito" — dì "è un prototipo funzionante su cui possiamo ragionare".

---

## Atto 1 — La vista d'insieme (3 minuti)

### 📊 Home
- Mostra i KPI: 5 progetti attivi, 13 dipendenti, 48 task
- Scorri la Panoramica Progetti: Vincenzo vede Sparkasse, Reale Mutua, Duferco, BNP, Boggi
- "Tutto in un posto, sempre aggiornato"

### 📅 GANTT
- Mostra il GANTT completo con le bande cromatiche per progetto
- Clicca su un task (es. "Implementazione framework ICT" di Sparkasse)
- Il pannello dettaglio si apre: ore fatte/stimate, % avanzamento, predecessore/successori
- Clicca su "vedi cosa fa" nella sezione persona → lista completa dei task di Stefano Colombo
- "Con un click vedi chi fa cosa, quanto ci sta lavorando, e cosa fa in parallelo"

**Frase chiave:** "Oggi queste informazioni stanno nella testa di chi gestisce i progetti o in Excel che nessuno aggiorna. Qui sono centralizzate e sempre aggiornate."

---

## Atto 2 — Il cuore: cosa succede quando cambia qualcosa (5 minuti)

### 🔬 Tavolo di Lavoro

**Scenario da mostrare:**

Vai sulla pagina Tavolo di Lavoro e scrivi nel campo:

> Sparkasse ci ha chiesto di anticipare l'adeguamento DORA di 20 giorni

1. L'IA interpreta: "Ho capito che i task del progetto Adeguamento DORA devono finire 20 giorni prima..."
2. Mostra le modifiche proposte: 5-6 task spostati
3. Clicca "Calcola impatto a cascata"
4. Il sistema mostra:
   - GANTT Prima/Dopo — le barre si accorciano visivamente
   - Conseguenze ordinate per gravità
   - Saturazioni settimanali con dettaglio attività

**Cosa dire durante:**
"Non ho toccato nulla manualmente. Ho scritto una frase e il sistema ha calcolato tutto: quali task slittano, di quanto, chi si sovraccarica, e quali altri progetti ne risentono. Questo calcolo a mano su Excel richiede ore."

**Secondo scenario (se c'è tempo):**

Clicca "Nuovo scenario" e scrivi:

> Silvia Moretti si concentra al 100% su Sparkasse per 3 settimane

"Quando una persona si dedica a un'emergenza, il sistema mostra automaticamente cosa succede ai suoi altri progetti."

**NON cliccare "Conferma e applica"** — mostra solo la simulazione.

**Frase chiave:** "Il sistema non propone soluzioni — mostra le conseguenze. Le decisioni restano vostre. Ma almeno le prendete vedendo il quadro completo."

---

## Atto 3 — La consuntivazione intelligente (3 minuti)

### ⏱️ Consuntivazione

- Seleziona un dipendente (es. Stefano Colombo)
- Nel chatbot scrivi: "Questa settimana ho lavorato sul framework ICT per Sparkasse e ho dato una mano a Paolo sulla mappatura controlli per Reale Mutua"
- L'IA mappa le attività sui task esistenti e propone le ore
- "Invece di compilare un form con ore per task, il dipendente racconta cosa ha fatto. Il sistema traduce."

**Frase chiave:** "Le ore sono un dettaglio burocratico. Il sistema parla la lingua delle persone."

---

## Atto 4 — La pianificazione assistita (3 minuti)

### 📋 Pipeline

- Mostra i bandi attivi (ITAS, Banco Desio) con countdown
- Vai su "Da pianificare" → Framework ESG Reporting (A2A)
- Clicca "Avvia pianificazione"
- Clicca "Suggerisci con IA" e scrivi: "Framework per il reporting ESG integrato con raccolta dati, calcolo KPI sostenibilità e dashboard direzionale"
- L'IA genera 7-8 task con dipendenze collegate
- "Il PM descrive il progetto a parole e il sistema propone una struttura di partenza. Poi si modifica come si vuole."

**Se c'è tempo:** clicca "Verifica pianificazione IA" per mostrare che l'IA segnala task orfani o stime irrealistiche.

---

## Chiusura — Prossimi passi e MCP (3 minuti)

**Cosa dici:**

"Questo è un prototipo funzionante. Per metterlo in produzione servono tre cose:

1. **Dati reali**: l'anagrafica dipendenti, i progetti attuali, le ore. Il sistema è pronto a riceverli — basta un'importazione iniziale e poi i dati si accumulano con l'uso quotidiano.

2. **Fase pilota graduale**: le prime settimane i dipendenti compilano solo le ore, senza che l'agente faccia analisi. Poi si attivano gradualmente le segnalazioni e le simulazioni. Così non bruciamo lo strumento.

3. **Integrazione Teams/Outlook (futuro)**: tecnicamente è possibile che il sistema riceva notifiche da Teams o legga email per intercettare cambiamenti — ad esempio un cliente che anticipa una scadenza. Ma questo richiede una discussione sulla privacy e sui permessi che ho preparato come documento separato. La versione base funziona anche senza questa integrazione."

**Frase chiave finale:** "Il valore principale non è l'IA — è avere tutti i GANTT in un posto che si aggiornano a cascata quando qualcosa cambia. L'IA è l'interfaccia che rende tutto questo utilizzabile senza dover cliccare su 50 menu."

---

## Note per la demo

### Cosa NON dire:
- "L'IA decide cosa fare" — l'IA mostra conseguenze, non decide
- "È finito" — è un prototipo su cui ragionare
- "Può fare tutto" — è specifico per la gestione GANTT e carichi

### Cosa fare se qualcosa si rompe:
- Se l'IA non risponde: "Gemini ogni tanto ha latenza, in produzione useremmo streaming per mostrare la risposta in tempo reale"
- Se i dati sembrano strani: "I dati sono fittizi per la demo, con i dati reali i numeri sarebbero calibrati"
- Se Vincenzo chiede qualcosa che non c'è: "Ottima idea, la segno. Il sistema è modulare, possiamo aggiungerlo"

### Scenari di backup (se i principali non funzionano):
- Tavolo di Lavoro: "Il testing di DORA slitta di 2 settimane"
- Tavolo di Lavoro: "Luca Martinelli aiuta su Reale Mutua per una settimana"
- Consuntivazione: "Oggi ho fatto call col cliente Sparkasse tutto il giorno e poi ho lavorato un po' sulla piattaforma GRC"
