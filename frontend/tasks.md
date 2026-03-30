Ecco una struttura realistica per l'App Mobilità Sostenibile (Comune di Lecce — car sharing e bike sharing comunale, 900h budget, 7 mesi):

Task da inserire in ordine:

Analisi requisiti e stakeholder — Analisi — 60h — Project Manager — nessuna dipendenza
Design UX/UI app mobile — Design — 80h — UX/UI Designer — dipende da #1 (FS)
Architettura backend e API — Design — 50h — Tecnico Senior — dipende da #1 (FS)
Sviluppo backend API — Sviluppo — 200h — Tecnico Senior — dipende da #3 (FS)
Sviluppo app mobile — Sviluppo — 180h — Tecnico Mid — dipende da #2 (FS), dipende da #3 (SS, perché può partire quando parte il design architettura, lavorando in parallelo sulle parti indipendenti)
Integrazione sistemi bike/car sharing — Sviluppo — 120h — Tecnico Senior — dipende da #4 (SS, lavora in parallelo col backend)
Testing e QA — Testing — 80h — Tecnico Junior — dipende da #4 (FS), dipende da #5 (FS)
Deploy e collaudo — Deploy — 40h — Tecnico Mid — dipende da #7 (FS)
Gestione progetto — Gestione — 70h — Project Manager — dipende da #1 (SS, parte insieme e dura tutto il progetto)
Demo e consegna Comune — Vendita — 20h — Commerciale/Pre-sales — dipende da #8 (FS)


Martedì e mercoledì ho lavorato al modulo IoT, giovedì ho portato avanti il catalogo open data, venerdì mezza giornata di ferie.
Ho anche lavorato un po' alle iscrizioni e fatto roba per il booking.
Ho anche dato una mano ad Alessandro sulla dashboard

Versione meno lunga Alessandro, scritta peggio. NOTA: mi viene difficile produrre un testo sintatticamente confuso per testare la comprensione dell'agente, però potrei provare a scrivere una montagna di specifiche con parentesi per vedere se non si confonde. 



Perfetto! Ecco i task per "Piattaforma HR Interna" (800h) — con difetti intenzionali nascosti per testare l'IA:
#NomeFaseOreProfiloAssegnato aDipendenze
1 .Analisi requisiti HR Analisi 60 Project Manager Giuseppe Russo nessuna
2 .Design interfaccia HR Design 80 UX/UI Designer Sara Lombardi #1 FS
3 .Sviluppo backend HR Sviluppo 250 Tecnico Senior Marco Bianchi #1 FS
4 .Sviluppo frontend HR Sviluppo 200 Tecnico Junior Laura Verdi #2 FS
5 .Integrazione payroll Sviluppo 100 Tecnico Mid Roberto Esposito #3 SS
6 .Deploy e collaudo Deploy 40 Tecnico Mid Roberto Esposito #4 FS
7 .Gestione progetto HR Gestione 70 Project Manager Giuseppe Russo #1 SS
I difetti nascosti che l'IA dovrebbe trovare:

Task orfano: "Integrazione payroll" (#5) dipende da #3 con SS, ma nessun task successivo dipende da esso — stesso pattern del bike/car sharing
Fase mancante: non c'è testing — si passa da sviluppo direttamente a deploy
Deploy dipende solo dal frontend: il deploy (#6) dipende da #4 (frontend) ma non da #3 (backend) né da #5 (payroll) — potresti deployare senza che backend e payroll siano pronti
Budget sforato: 60+80+250+200+100+40+70 = 800h — quadra esattamente, ma è sospetto che non ci sia margine

Compila questi, salva la bozza, poi clicca "🧠 Chiedi all'IA di verificare". Vediamo quanti difetti Gemini coglie!


Ecco il GANTT corretto per P010 — correggi i task che hai già compilato:
#NomeFaseOreProfiloAssegnato aDipendenze
1 .Analisi requisiti HR Analisi 60 Project Manager Giuseppe Russo nessuna
2 .Design interfaccia HR Design 80 UX/UI Designer Sara Lombardi #1 FS
3 .Sviluppo backend HR Sviluppo 250 Tecnico Senior  Marco Bianchi  #2 FS
4 .Sviluppo frontend HR  Sviluppo 200 Tecnico Junior Laura Verdi #2 FS
5 .Integrazione payroll Sviluppo 100 Tecnico Mid Roberto Esposito #3 SS
6 .Testing e QA Testing 80 Tecnico Junior Laura Verdi #3 FS, #4 FS, #5 FS
7 .Deploy e collaudo Deploy 40 Tecnico Mid  Roberto Esposito #6 FS
8 .Gestione progetto HR Gestione 120  Project Manager Giuseppe Russo #1 SS
Cosa ho cambiato rispetto al GANTT difettoso:

Aggiunto Testing e QA (#6) — la fase che mancava
Testing dipende da backend (#3), frontend (#4) E integrazione (#5) — niente task orfani
Deploy dipende dal testing (#6) — catena corretta
Gestione progetto portata a 120h — più realistica per un progetto lungo
Le ore totali ora sono 930h (sopra budget 800h — vediamo se l'IA lo segnala!)

Se il GANTT precedente ha ancora 7 task, cancella tutto e ricrea con questi 8. Poi lancia la verifica!


Ci serve un sistema interno per gestire le presenze dei dipendenti, le richieste di ferie e permessi, e le note spese. Deve avere un portale dove ogni dipendente può inserire le proprie richieste e vedere lo storico, e una dashboard per l'ufficio HR dove approvare/rifiutare le richieste e avere una visione d'insieme. Vorremmo anche integrare il calcolo delle buste paga con il sistema payroll esistente. Il progetto è interno, non ha un cliente esterno.