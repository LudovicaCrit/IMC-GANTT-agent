# Piano di lavoro — IMC-GANTT-agent

*Ogni passo è piccolo e committabile da solo. Legenda: ✅ fatto · ▶ in corso · ☐ da fare · 🖐 contiene lavoro manuale non delegabile a Code. Le scelte di fondo stanno in DECISIONI.md; lo stato del codice in INVENTARIO.md; il debito minuto in BACKLOG.md.*

*Due traguardi distinti. La presentazione al management chiude la fase 8: lì il prodotto è completo, IA, avatar, presenze, notifiche e accesso da smartphone compresi. L'inaugurazione con i dati veri viene dopo, ed è lì che le IA si affinano.*

## Fase 0 — Metodo
- ✅ Inventario del codice (INVENTARIO.md)
- ✅ CLAUDE.md e DECISIONI.md
- ✅ pytest e cartella backend/tests/, test puri convertiti
- ✅ Database di test gantt_test costruito dalle migration, confronto schema con il DB di sviluppo
- ✅ Modello e migration allineati (migration b7c8d9e0f1a2)
- ✅ PIANO.md e BACKLOG.md
- ✅ Seed su gantt_test e spostamento in backend/tests/ dei test che scrivono sul DB
- ☐ Ricostruire il DB di sviluppo gantt_db da migration e seed
- ☐ Pulizia requirements: via google-ai-generativelanguage, python-jose (resta PyJWT), passlib (resta argon2)

**Chiusura**: Code lavora con regole scritte e una rete di test che non tocca il DB di sviluppo.

## Fase 1 — Ciò che l'utente tocca non si rompe
- ✅ Modello Gemini da variabile d'ambiente
- ☐ Pipeline e Tavolo di Lavoro fuori dal menu e dal codice, con i loro endpoint orfani (/api/tasks/applica, /api/agent/* non usati, /api/pianificazione/*), le funzioni morte di api.js e la dipendenza frappe-gantt. Prima si archiviano gli embrioni IA da recuperare. Attenzione: il webServer degli e2e usa /api/agent/status come healthcheck, va sostituito nello stesso passo.
- ☐ Export GANTT: PDF funzionante (dipendenza mancante), PNG senza pdftoppm
- ☐ Progetti "Da iniziare" visibili in Cantiere e GANTT
- ☐ PUT /api/progetti/{id}/completo non azzera i campi che il Wizard non manda
- ☐ Configurazione: salvare un dipendente non azzera la sede
- ☐ azienda_id assegnata alla creazione del progetto (Wizard + backend)
- ☐ GANTT: tendina progetti senza lo stato inesistente "In bando", Sospesi selezionabili
- ☐ Colori degli stati in un solo punto: legenda, GanttChartFasi e TimelineBars coerenti
- ☐ VistaManagement: nome del dipendente invece dell'id
- ☐ Risorse: filtro per tipologia interna invece dell'id P010 cablato
- ☐ Home: il clic su un progetto non porta al 403 per chi non è manager (si riapre in fase 3)

**Chiusura**: un giro completo di tutte le pagine da manager senza 500, 403 o dati spariti; un test per ogni correzione.

## Fase 2 — Modello ore ed Economia onesta
- ☐ Via Progetto.budget_ore; il gauge si riaggancia a un denominatore vero. Chiude anche il 422 sulle bozze
- ☐ Pianificate uguali alle stimate alla nascita, in tutti i punti di creazione dei task
- ☐ Stimate in sola lettura dopo la creazione
- ☐ Da decidere a inizio fase: come il PM ripianifica a livello di fase senza creare una seconda sorgente (fase derivata dalla somma dei task con distribuzione come azione, oppure fase come input). Poi il campo nel Cantiere
- ☐ ore_rimanenti: due formule con lo stesso nome, rinominate
- ☐ Risorse: un solo numero di carico, calcolato nel backend
- ☐ Economia, etichette che dicono il vero: postilla falsa, "Margine reale", "Efficienza netta", alias morti del payload
- ☐ Soldi in Decimal, arrotondati in un punto solo
- ☐ margini: le quattro ore affiancate, delta in ore, dipendente_id in dettaglio_persone
- ☐ Cruscotto in Economia: testata anagrafica (descrizione esposta, valore del contratto nel Wizard), quattro ore, delta, erosioni, lente sulla dispersione
- ☐ Saturazione sulle ore vere, affiancata a quella sul piano
- ☐ GANTT: lenti portafoglio e per-dipendente nella stessa pagina

**Chiusura**: ogni numero di Economia e Risorse ha formula ed etichetta coerenti, coperte da test pytest.

## Fase 3 — Utenti e ruoli
- ☐ Gestione account da Configurazione, legata al dipendente; reset da parte del manager
- ☐ Cambio password self-service
- ☐ Matrice di accesso pagina per pagina (management, PM, amministrazione, dipendente), da decidere in chat
- ☐ Autorizzazione per progetto nel backend (GANTT, dettaglio, Cantiere) per il PM sui suoi progetti; Home riaperta
- ☐ GET /api/attivita-interne filtrato per persona
- ☐ Urgenza modificabile da interfaccia
- ☐ Configurazione: inquadramento base + ruoli aggiuntivi
- ☐ 🖐 Account per tutti i dipendenti; pm_id assegnato ai progetti

**Chiusura**: ogni ruolo vede e modifica esattamente ciò che la matrice prevede, verificato da e2e per ruolo.

## Fase 4 — Dal basso verso il piano
- ☐ Modello: origine, stato di ratifica e "richiesto da" sui pezzi; task "Emerso in corsa" per progetto
- ☐ Appunto al volo in Home e nella griglia
- ☐ Coda "da ratificare" del PM
- ☐ Stima residua resa evidente; oltre soglia il PM ri-stanzia
- ☐ Avanzamento da ore in GANTT, Cantiere e Home
- ☐ Soccorso con conferma dell'aiutato

**Chiusura**: un'assegnazione a voce arriva nel piano in meno di un minuto, e il PM la vede.

## Fase 5 — Periodi di assenza, presenze e rimborsi
- ☐ Periodo di assenza segnato dal dipendente in Consuntivazione, dal giorno al giorno, con nota facoltativa. La comunicazione ufficiale all'azienda resta fuori dall'app
- ☐ Approvazione del management o di un PM di uno dei progetti su cui la persona lavora; basta la prima. Finché non è approvato, il periodo non ha effetto
- ☐ Periodo approvato: nessuna consuntivazione richiesta, nessun promemoria, la copertura conta quei giorni come resi conto
- ☐ Chiusure aziendali con lo stesso meccanismo: le dichiara il management, già approvate, per tutti
- ☐ Presenze giornaliere leggere, agganciate alla griglia dei giorni
- ☐ Rimborsi spese dichiarati dal dipendente
- ☐ Vista amministrazione: presenze e spese di tutti, con esportazione

**Chiusura**: un dipendente segna due settimane di ferie, il PM approva, e in quel periodo l'app non gli chiede nulla; l'amministrazione vede presenze e rimborsi del mese e li esporta.

## Fase 6 — IA
- ☐ Infrastruttura comune: streaming, timeout lungo la catena, output strutturato con schema, retry
- ☐ Registro delle transizioni di stato
- ☐ Sintesi per il management nel cruscotto
- ☐ Costruisci-GANTT nel Wizard del Cantiere (recupero dell'embrione di Pipeline)
- ☐ task_competenze, semaforo strato 2, scenari con OR-Tools, capacità che tiene conto dei periodi di assenza approvati 🖐 (competenze da popolare)
- ☐ Archivio: SAL consolidati, scheda di valutazione, lezioni
- ☐ Compila-consuntivazione con avatar vocale, anche come ingresso dell'appunto al volo

**Chiusura**: ogni IA ha streaming, timeout, test con fixture e passa la domanda AI Act.

## Fase 7 — Notifiche e accesso da smartphone e PC
- ☐ 🖐 Notifiche Teams: autorizzazione lato azienda (webhook o flusso Teams), poi notifica il giorno stesso in cui un task o un pezzo finisce, quando c'è qualcosa da ratificare o un periodo di assenza da approvare, e promemoria di consuntivazione che tacciono nei periodi di assenza approvati
- ☐ Pagine responsive per l'uso quotidiano: consuntivazione, appunto al volo, Home
- ☐ Sito installabile dal browser come icona su smartphone e PC (manifest), senza cache offline e senza store
- ☐ 🖐 Accesso da fuori ufficio tramite la VPN aziendale, configurato con l'IT

**Chiusura**: un dipendente consuntiva, prende un appunto e segna le ferie dal telefono; il PM riceve la notifica in Teams.

## Fase 8 — Pronti per la presentazione
- ☐ Python 3.12 o 3.13 in sviluppo e produzione; verifica dei pacchetti su Windows
- ☐ DB di produzione da migration (secondo l'esito del confronto della fase 0)
- ☐ Seed di produzione senza password in chiaro
- ☐ Produzione blindata: HTTPS, COOKIE_SECURE, /docs chiuso, CORS da env, rate limit corretto dietro IIS
- ☐ Fuso orario esplicito nel backend e date locali nel frontend
- ☐ Servizio NSSM, PYTHONUTF8=1, backup del DB
- ☐ Dataset dimostrativo: dati sintetici credibili, separati e cancellabili, con date recenti e ore consuntivate fino al giorno della presentazione

**Chiusura**: un giro completo della demo su Windows Server, con ogni ruolo, anche da smartphone, senza interventi tecnici.

## Dopo la presentazione
- Inaugurazione con un gruppo pilota e dati veri
- Affinamento delle IA e delle soglie coi dati veri
- Test frontend (Vitest)
