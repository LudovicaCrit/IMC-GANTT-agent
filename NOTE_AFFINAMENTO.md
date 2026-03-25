# IMC-Group GANTT Agent — Note di Affinamento
**Data:** 25 marzo 2026
**Stato:** Da implementare dopo completamento di tutte le sezioni

---

## A. Analisi e Interventi — Sezione Esplorazione

### A1. Modifica giorni ritardo dopo "Aggiungi"
La lista dei ritardi da simulare deve permettere di modificare il numero di giorni anche dopo aver cliccato "Aggiungi". Attualmente si può solo rimuovere e riaggiunere. Servono un campo editabile inline o un piccolo input accanto ai giorni nella lista.

### A2. Legenda colori nel GANTT di simulazione
I GANTT "Prima" e "Dopo" nella simulazione non hanno la legenda stati (Completato/In corso/Da iniziare/Sospeso). Senza legenda i colori delle barre non sono interpretabili. Aggiungere la stessa `StatusLegend` presente nella pagina GANTT principale.

### A3. Blocco selezione durante analisi agente
Nella sezione Interventi, quando si clicca una segnalazione e l'agente sta generando l'analisi, è possibile cliccare un'altra segnalazione, il che fa ripartire l'analisi e sovrascrive il risultato precedente dopo pochi secondi. Soluzione: disabilitare i click sulle altre segnalazioni mentre `analisiLoading === true`, oppure mostrare un overlay/blocco visivo.

---

## B. Testo dell'Agente — Prompt `analisi_segnalazioni.md`

### B1. Eliminare sigle tecniche (D001, T003)
L'agente deve usare SEMPRE nomi completi di dipendenti e task, MAI id tecnici. Regola da aggiungere nel prompt: "Non usare mai identificativi come D001, T003, P001. Usa sempre il nome completo: 'Marco Bianchi' non 'D001', 'Sviluppo modulo IoT' non 'T003', 'SmartCity Monitoring' non 'P001'."

### B2. Evitare critiche strutturali/organizzative ripetitive
L'agente non deve fare il consulente organizzativo. Non deve ripetere ogni volta che "l'organico è insufficiente" o che "avendo un solo tecnico mid ci saranno sempre problemi". Il management lo sa. L'agente deve proporre soluzioni con le risorse disponibili. Se non ci sono soluzioni fattibili, lo dice una volta come nota contestuale, non come allarme. Regola nel prompt: "Non commentare l'adeguatezza dell'organico. Proponi soluzioni con le risorse esistenti. Se le opzioni sono limitate, indicalo brevemente una sola volta."

### B3. Esplicitare numero task per dipendente
Oltre alla saturazione percentuale, il testo dell'agente dovrebbe indicare quanti task ha un dipendente e su quanti progetti lavora, in modo leggibile: "Alessandro Conte (5 task su 3 progetti, saturazione 133%)" invece di "Alessandro Conte (D005) al 133%".

---

## C. Bottone "Applica" — Funzionamento Reale

### C1. Endpoint backend per applicare opzioni
Serve un endpoint `POST /api/interventi/applica` che riceva le azioni di un'opzione (riassegnazioni, spostamenti date) e le applichi ai dati in memoria. Le modifiche devono riflettersi nel GANTT principale.

### C2. Anteprima cross-progetto prima dell'applicazione
Quando il management clicca "Applica", prima della conferma deve vedere i GANTT di TUTTI i progetti impattati, non solo quello di partenza. Esempio: se l'opzione sposta un task di SmartCity e questo impatta Digital Health Records, mostrare entrambi i GANTT prima/dopo. L'applicazione avviene solo dopo conferma esplicita.

### C3. Coerenza agente ↔ visualizzazione
Se l'agente nella sua analisi testuale dice "questo impatta anche il progetto X", la visualizzazione deve mostrare quell'impatto. Non ci devono essere impatti menzionati nel testo ma non visibili nei GANTT.

---

## D. Pipeline — Creazione GANTT per nuovi progetti

### D1. Strumento per disegnare GANTT
La sezione "Da pianificare" in Pipeline deve permettere di creare un GANTT per un progetto vinto. Il management definisce fasi, task, ore stimate, profili richiesti. Il sistema mostra la disponibilità delle risorse e suggerisce staffing. Alla conferma, genera il GANTT e lo aggiunge al portafoglio attivo. Da decidere: form strutturato passo-passo vs interfaccia drag-and-drop vs assistenza agente ("descrivi le fasi e ti propongo un GANTT").

### D2. Espansione progetti in corso
Un progetto in esecuzione può crescere (nuove feature richieste dal cliente, come il caso Reale Mutua/Resolver). Serve un meccanismo per aggiungere fasi/task a un progetto attivo senza ricrearlo da zero. Questo è ibrido tra "nuovo progetto" e "modifica GANTT esistente".

---

## E. Fase Pilota / Rodaggio

### E1. Popolazione database graduale
All'avvio reale, il sistema non avrà dati storici. Serve una fase di rodaggio in cui:
- I dipendenti iniziano a compilare le ore (consuntivazione) senza che l'agente faccia analisi aggressive
- Il database si popola gradualmente con dati reali
- L'agente viene "attivato" progressivamente: prima solo osserva, poi inizia a segnalare, poi propone interventi
- Il prompt dell'agente deve essere calibrato sui dati reali, non sui fittizi

### E2. Non bruciare lo strumento
Rischio concreto: se l'agente parte subito con segnalazioni e proposte su dati incompleti, i dipendenti lo odiano e il management lo ignora. La fase pilota deve essere soft:
- Settimane 1-4: solo compilazione ore, chatbot in modalità assistente gentile
- Settimane 5-8: l'agente inizia a generare report settimanali (non segnalazioni in tempo reale)
- Settimane 9+: segnalazioni attive, proposte di intervento, simulazioni
Questo piano va concordato con Vincenzo.

### E3. Affinamento continuo prompt
I prompt (consuntivazione.md e analisi_segnalazioni.md) andranno affinati sui dati reali. Le regole anti-allucinazione attuali sono basate su dati fittizi — con dati reali emergeranno nuovi edge case. Prevedere un ciclo di feedback: management segnala risposte inadeguate → si aggiorna il prompt → si ri-testa.

---

## F. Note minori

### F1. Saturazione e ore effettive vs contrattuali
La saturazione è calcolata su ore contrattuali (40h). Nella realtà, alcuni profili lavorano più di 40h. Valutare se aggiungere un campo `ore_effettive` per calcolo più realistico. Decisione di business, non tecnica.

### F2. Diversificazione dati per demo Vincenzo
I dati fittizi sono sud-centrici (clienti pugliesi). Per la demo servono clienti nazionali/internazionali (UBAE, Reale Mutua, Duferco, Boggi). Portare a ~12-15 dipendenti simulati. (Punto 10 del handoff originale)

### F3. Documento architetturale per Vincenzo
Architettura target, flusso dati, roadmap funzionalità. Da produrre quando il prototipo è completo. (Punto 11 del handoff originale)

---

## G. Consuntivazione — Approccio B (PRIORITÀ ALTA, sessione dedicata)

### G1. Chatbot che mappa in linguaggio naturale
Il dipendente racconta cosa ha fatto in linguaggio naturale anziché compilare ore per task. Esempio reale: "Martedì ho fatto la riunione col cliente, poi ho lavorato sul backend FHIR, mercoledì mattina ho fixato il bug del portale e il pomeriggio ho aiutato Laura sul testing."

L'agente deve:
1. Prendere la descrizione e mapparla sui task esistenti del dipendente
2. Proporre la mappatura: "Da quello che mi dici, stimo circa 8h su Sviluppo backend FHIR, 4h su Backend booking, e 4h su testing gestionale — ti torna?"
3. Il dipendente conferma o corregge
4. Le ore si compilano automaticamente nel form

Coesiste col form: chi preferisce compilare direttamente le ore lo fa, chi preferisce raccontare all'agente racconta. Il form si aggiorna in entrambi i casi.

Considerazioni critiche:
- Le persone ragionano per giornata e attività, non per task e ore
- Spesso si lavora a più task nella stessa giornata (anche 5), portandoli avanti un poco alla volta
- L'agente deve saper gestire frasi come "martedì ho lavorato a ciò E a ciò" senza chiedere ore precise per ogni micro-attività
- La stima dell'agente deve essere ragionevole ma il dipendente ha sempre l'ultima parola
- ZERO allucinazioni: se l'agente non riesce a mappare un'attività su un task esistente, deve chiedere chiarimento, non inventare
- Richiede: modifica prompt consuntivazione.md, risposta strutturata JSON dall'agente, logica frontend per precompilare i campi ore dalla risposta agente

### G2. Smart working e modalità lavoro
Aggiungere nella sezione presenze una riga "Modalità settimana":
- Quanti giorni in sede, quanti da remoto
- Non è un'assenza, è una modalità di lavoro
- Utile per: quadro settimanale completo, conteggio indiretto buoni pasto (giorni in sede > 4h), visibilità management su chi è dove
- Nella realtà IMC-Group: 2 giorni smart a settimana garantiti
- Implementazione: campo semplice, non invasivo, nella sezione presenze/assenze
- Caso d'uso reale: Roberto (capo IT) post-operatorio → giorni a riposo poi smart working da casa. Il sistema deve tracciare la differenza tra "assente per malattia" e "lavora da remoto"

### G3. Segnalazioni dal chatbot automatiche verso Analisi e Interventi
Le [SEGNALAZIONE] generate dal chatbot devono arrivare automaticamente nella pagina Analisi e Interventi. Meccanismo: lista in memoria nel backend (poi database), endpoint GET per recuperarle, la pagina Analisi e Interventi le carica al posto delle hardcodate.

### G4. Semantica "Bloccato" e stati task
Il termine "Bloccato" nel dropdown stato task è ambiguo:
- Per il dipendente che ha lavorato 0 ore su un task, "Bloccato" non è necessariamente corretto — potrebbe essere semplicemente "Non lavorato questa settimana" o "In attesa"
- Bisogna distinguere tra: "non ci ho lavorato per scelta/priorità", "non ci ho potuto lavorare perché dipende da altro", "è sospeso/freezato"
- I progetti freezati/sospesi (come P006 Migrazione Cloud) hanno già uno stato a livello progetto — qui serve lo stato a livello task-settimana
- Proposte: aggiungere opzioni come "Non lavorato", "In attesa di input", "Bloccato da dipendenze" oppure semplificare con "In corso / Completato / Fermo" dove "Fermo" apre un campo motivazione
- Da decidere con Vincenzo cosa sia più utile vs cosa crei solo confusione

### G5. Limite ore: permettere più di 40h
Attualmente il form non impedisce di inserire più di 40h totali, ma non è esplicito. Nella realtà IMC-Group i profili molto occupati lavorano oltre le 40h contrattuali. Il sistema deve:
- Permettere di dichiarare più di 40h senza allarmi aggressivi
- Mostrare il delta in modo informativo ("hai dichiarato 48h su 40h contrattuali") senza giudicare
- L'agente non deve commentare le ore extra se non esplicitamente chiesto

### G6. Latenza risposta agente
La latenza di Gemini 2.5 Flash è attualmente di qualche secondo. Per migliorare l'esperienza:
- Il TypingIndicator aiuta, ma se la risposta supera i 5-6 secondi l'utente potrebbe pensare che si sia bloccato
- Valutare: timeout con messaggio "L'agente sta impiegando più del solito...", oppure streaming reale (SSE) per mostrare il testo man mano che arriva
- Lo streaming richiederebbe modifiche a agent.py e al frontend (EventSource), ma darebbe un'esperienza molto più fluida
- Priorità media — funziona anche senza, ma per il "prodotto vendibile" sarebbe un differenziatore

### G7. Testing Approccio B — casi complessi
Quando implementiamo l'Approccio B, testare esplicitamente:
- "Ho lavorato un pochino a X, ho dato un'occhiata a Y" — stime vaghe
- "Martedì ho fatto X E Y" — multi-task nella stessa giornata
- "Ho fatto 5 cose diverse oggi, un po' alla volta" — micro-attività distribuite
- Attività non mappabili su task esistenti ("ho aiutato Laura con una cosa")
- Contraddizioni tra racconto e ore compilate nel form

---

## H. Visione prodotto — Note strategiche

### H1. Potenziale commerciale
Il sistema, se fatto bene, potrebbe diventare un prodotto vendibile ad altre aziende di consulenza/servizi con 10-50 dipendenti. Biglietto da visita per espansione internazionale (Svizzera). Questo implica:
- UI/UX deve essere professionale, non "prototipo universitario"
- L'architettura deve supportare multi-tenant (futuramente)
- La documentazione deve essere chiara per chi non conosce il progetto
- L'Approccio B (chatbot che mappa) è il differenziatore principale rispetto ai GANTT tradizionali

---

## I. Pipeline — Affinamenti strutturali

### I1. Saturazione dinamica durante la pianificazione — INCROCIO GANTT (CRITICO)
La saturazione attuale è calcolata come media piatta (ore pianificate / durata progetto). Questo è INSUFFICIENTE. Il calcolo corretto DEVE incrociare tutti i GANTT settimana per settimana:
- Per ogni settimana del nuovo progetto, sommare le ore di TUTTI i task attivi della persona in TUTTI i progetti (esistenti + quello in pianificazione)
- Dividere per ore contrattuali settimanali → saturazione reale di quella settimana
- Il PICCO settimanale è il dato che conta, non la media
- Esempio: Marco ha 200h di backend dal 1 giu al 30 ago + 120h di integrazione dal 15 lug al 30 ago. A luglio-agosto ha DUE task sovrapposti del nuovo progetto PIÙ i task di SmartCity e Digital Health Records → il picco potrebbe essere 160% anche se la media è 121%
- Usa la stessa logica di `carico_settimanale_dipendente` in data.py, estendendola per includere i task in fase di pianificazione
- Questo è ciò che rende i GANTT "connessi" tra loro e il software diverso da un Excel

### I2. Impatto cross-GANTT con inserimento nuovo progetto
Quando il management sta pianificando un nuovo progetto, il bottone "Verifica risorse" deve mostrare:
- Per ogni persona assegnata: saturazione attuale + delta dal nuovo progetto
- Alert se qualcuno supera il 100% sommando nuovo + esistente
- Quali progetti esistenti sono impattati (perché condividono le stesse persone)
- Questo è IL punto di connessione tra Pipeline e il resto del sistema — è ciò che rende il software diverso da un Excel

### I3. Multi-persona per task
Un task può essere assegnato a più persone (es. 200h di sviluppo fatto da 2 tecnici). Implicazioni:
- La durata calendario si riduce proporzionalmente al numero di persone
- Le ore budget restano invariate (200h rimangono 200h)
- La saturazione si distribuisce tra le persone assegnate
- UI: permettere selezione multipla nel dropdown "Assegnato a" o aggiungere un campo "Risorse aggiuntive"

### I4. Bandi dalla pianificazione
La tab "Da pianificare" e "Bandi" condividono la stessa logica: definire task, assegnare persone, tracciare ore. Differenza: il bando ha scadenza fissa e non genera GANTT operativo fino alla vittoria. Valutare se unificare lo strumento di pianificazione per entrambi, con un flag "tipo: bando | progetto vinto" che cambia il comportamento (bando = countdown + task preparazione, vinto = GANTT completo + staffing).

### I5. Salvataggio bozza pianificazione
Per non perdere il lavoro durante la pianificazione:
- Fase 1 (ora): localStorage del browser — non persistente tra dispositivi ma salva il lavoro se si ricarica la pagina
- Fase 2 (con db): endpoint POST /api/pianificazione/bozza — persistente e condivisibile
- Auto-save ogni 30 secondi o al cambio di campo

---

## J. Architettura — Punto fondamentale sulle percentuali

### J1. La saturazione come tessuto connettivo
Le percentuali di saturazione sono il meccanismo che collega indirettamente tutti i GANTT tra loro. Ogni volta che un task viene creato, spostato, ritardato o riassegnato in qualsiasi progetto, le percentuali di tutti i dipendenti coinvolti cambiano, e questo si riflette su tutti gli altri progetti.

Questo principio deve essere rispettato in TUTTE le sezioni:
- **GANTT**: le percentuali mostrate nei filtri/dettagli devono essere sempre aggiornate
- **Analisi e Interventi**: la simulazione deve mostrare l'impatto sulle percentuali cross-progetto
- **Pipeline**: la pianificazione deve mostrare l'impatto preventivo prima della conferma
- **Risorse**: la heatmap deve riflettere tutto, inclusi i progetti in fase di pianificazione (opzionalmente)
- **Consuntivazione**: l'agente deve conoscere la saturazione reale (non solo stimata) per contestualizzare le segnalazioni

La funzione `carico_settimanale_dipendente` in data.py è il singolo punto di calcolo. Quando migreremo a PostgreSQL, questo diventerà una query — ma il principio resta: un'unica fonte di verità per la saturazione.

---

## K. Sottotask e tracciamento attività granulare

### K1. Sottotask nei consuntivi
Quando il dipendente descrive cosa ha fatto ("ho fixato il bug dell'autenticazione nel backend FHIR"), quello è un sottotask di "Sviluppo backend FHIR". Il sistema potrebbe tracciarli come note strutturate dentro il task principale:
- Non esplodono la complessità del GANTT (il GANTT resta a livello task)
- Creano un log di cosa è stato fatto concretamente
- Utile per il management ("cosa ha prodotto Marco questa settimana?")
- Utile per l'archivio/knowledge base ("cosa ha comportato lo sviluppo FHIR?")
- Utile per l'Approccio B: l'agente mappa la descrizione verbale su task e genera sottotask automaticamente

### K2. Sottotask nella pianificazione GANTT
Nella creazione/aggiornamento del GANTT, il management potrebbe voler specificare sottotask per task complessi. Esempio: "Sviluppo backend API" (200h) potrebbe avere sottotask come "Setup ambiente", "Endpoint autenticazione", "Endpoint dati", "Documentazione API". Questi restano sotto il task padre nel GANTT (collapsibili) ma permettono una pianificazione più granulare.

### K3. Espansione progetti → nuovi prodotti
Funzionalità concepite come espansione di un progetto esistente (caso Reale Mutua/Resolver) che poi non entrano nel progetto originale ma diventano prodotti a sé per altri clienti. Il sistema deve supportare:
- Aggiungere fasi/task a un progetto in corso (espansione)
- "Staccare" un gruppo di task/funzionalità da un progetto e creare un nuovo progetto indipendente
- Tracciare la genealogia: "questo prodotto nasce dall'espansione del progetto X per il cliente Y"

---

## L. Persistenza e Database

### L1. Schema database — DA PROGETTARE
Tabelle previste (schema ricco, meglio campi vuoti che ristrutturare):
- **dipendenti**: id, nome, profilo, ore_sett, costo_ora, competenze, sede, email
- **progetti**: id, nome, cliente, stato, date, budget_ore, valore_contratto, descrizione, fase_corrente, sede, note
- **task**: id, progetto_id, nome, fase, ore_stimate, date, stato, profilo_richiesto, predecessore, tipo_dipendenza (FS/SS/FF)
- **assegnazioni**: task_id, dipendente_id (supporto multi-persona per task)
- **consuntivi**: task_id, dipendente_id, settimana, ore_dichiarate, compilato, data_compilazione, nota, modalita (sede/remoto)
- **segnalazioni**: id, tipo, priorita, dipendente_id, dettaglio, timestamp, fonte (chatbot/manuale/simulazione), stato (aperta/analizzata/risolta)
- **pianificazioni_bozza**: progetto_id, dati_json (tabella task in fase di pianificazione), timestamp
- **storico_interventi**: id, segnalazione_id, opzione_scelta, azioni_applicate, timestamp, esito
- **note_progetto**: progetto_id, testo, autore, timestamp (lezioni apprese, note archivio)

### L2. Migrazione da data.py a PostgreSQL
- Le funzioni helper in data.py (`get_dipendente`, `carico_settimanale_dipendente`, ecc.) diventano query SQL
- Il frontend NON cambia — parla solo con le API
- Il backend cambia solo la sorgente dati, non la logica
- Usare SQLAlchemy o simile come ORM per non scrivere SQL raw ovunque

### L3. Raccolta dati reali — il problema degli Excel volanti
- Oggi IMC-Group ha dati in Excel sparsi (se ci va bene)
- Opzioni: importazione manuale, script pandas che legge xlsx e popola db, fase pilota con popolazione graduale
- La fase pilota è probabilmente l'approccio migliore: il sistema parte vuoto, i dipendenti iniziano a compilare, i dati si accumulano
- Per i progetti storici: importazione leggera (nome, cliente, date, ore totali, team) senza pretendere il dettaglio task per task
- DA CHIEDERE A VINCENZO: che dati ha, in che formato, quanto è disposto a investire nell'importazione iniziale

---

## M. Osservazioni dalla sessione del 25 marzo — Pomeriggio

### M1. L'agente NON sposta pedine — il management redistribuisce il focus
La realtà aziendale di IMC-Group è che quando c'è un'emergenza (es. Sparkasse anticipa la scadenza di 20 giorni), il management non "riassegna" le persone da un progetto all'altro. Dice "ragazzi, questa settimana ci concentriamo su Sparkasse". Le persone continuano a portare avanti i loro task, ma cambiano le proporzioni (es. Roberto fa 8h su catalogo invece di 20h e le altre 12h le mette su Sparkasse). L'agente GANTT deve proporre redistribuzioni del focus, non spostamenti netti: "questa settimana Marco, Roberto e Alessandro dedicano il 60% del tempo a Sparkasse — ecco come slittano gli altri task di conseguenza", NON "togli Roberto da Y e mettilo su X".

### M2. Task orfani nella pianificazione — caso reale
Il task "Integrazione sistemi bike/car sharing" del progetto App Mobilità Sostenibile è agganciato al task "Sviluppo backend API" con dipendenza SS (parallelismo), ma nessun task successivo dipende dalla sua conclusione. Questo significa che se ritardasse, nessun altro task nel GANTT ne risentirebbe — è un task "orfano". Questo è un errore di pianificazione classico che l'IA di verifica (placeholder "Chiedi all'IA di verificare la pianificazione") dovrebbe segnalare. Nella realtà, "Testing e QA" dovrebbe probabilmente dipendere anche dall'integrazione.

### M3. Export GANTT — formati aggiuntivi
Il PDF è operativo. Mancano:
- **PNG**: per incollare in presentazioni PowerPoint o email
- **Excel**: per chi vuole manipolare i dati in tabella (PM che vogliono rielaborare)
- Entrambi sono lavori circoscritti (un endpoint + un bottone)

### M4. GANTT web — bande cromatiche per progetto
Il GANTT "tutti i progetti" nell'interfaccia web è confusionario: tutti i task sono su sfondo uniforme e non si capisce dove finisce un progetto e inizia un altro. Servono bande colorate alternate (come nel PDF esportato) per raggruppare visivamente i task per progetto. Nel PDF funziona già — va replicata la logica nel componente React GanttChart.

### M5. Dettaglio task nella pagina GANTT — ripensare
La sezione "Dettaglio" sotto il GANTT (tabella espandibile con 69 task) non è particolarmente utile nella forma attuale. Opzioni:
- Pannello laterale che appare al click su una barra del GANTT (più intuitivo)
- Mini-card con info essenziali al hover
- Rimuoverla del tutto e lasciare solo il GANTT visivo
- Da decidere con Vincenzo cosa preferisce

### M6. Straordinari — da chiedere a Vincenzo
Non sappiamo come IMC-Group gestisce le ore extra. Il sistema attualmente registra le ore dichiarate senza commenti se superano le 40h contrattuali. Prima di implementare qualsiasi logica sugli straordinari, chiedere a Vincenzo: "Come gestite le ore extra? Il sistema deve tracciarle in modo specifico o basta il totale dichiarato?" La risposta determina se serve un campo dedicato nel db o no.

### M7. Due placeholder IA in Pipeline — chiarire i ruoli
In Pipeline "Da pianificare" ci sono due bottoni IA placeholder:
- **"Suggerisci con IA"** (sopra la tabella): l'idea è descrivere il progetto a parole e l'IA propone una struttura di task. Aiuto alla *creazione* da zero.
- **"Chiedi all'IA di verificare"** (sotto il GANTT): l'IA analizza la pianificazione esistente e segnala problemi (task orfani, stime irrealistiche, fasi mancanti, dipendenze sospette). Aiuto alla *revisione*.
- Rischio sovrapposizione col pannello "Impatto sulle risorse" (che mostra saturazioni) — la verifica IA ha senso solo se aggiunge qualcosa che il pannello numerico non può fare (analisi strutturale, non solo percentuali).
- Decisione: implementare prima la verifica (M2 è il caso d'uso perfetto), poi valutare il suggerisci.

### M8. Restyling UI — non deve sembrare una demo
L'interfaccia attuale è funzionale ma esteticamente "da prototipo": dark mode generico con bordi grigi, tipografia standard, nessuna identità visiva. Per un prodotto vendibile (e per impressionare Vincenzo) serve:
- Tipografia curata (font, pesi, spaziatura)
- Palette colori raffinata e coerente
- Micro-interazioni (transizioni, hover states)
- Layout più arioso
- Potenzialmente un logo/brand IMC-Group
- Da fare in una sessione dedicata con lo skill frontend-design

### M9. Priorità progetto — decisione management, non calcolata
Il campo `priorità` nella tabella `progetti` del database (alta/media/bassa) è un dato che il management imposta manualmente. NON è calcolato dal sistema. Serve come contesto per l'agente: se Sparkasse ha priorità alta e il progetto LOG ha priorità media, in caso di conflitto risorse l'agente propone di rallentare il LOG. È una decisione umana, non algoritmica.

### M10. Raccolta dati per il db — approccio misto
La popolazione del database reale sarà mista:
- Excel esistenti in azienda → script di importazione Python
- Anagrafica dipendenti → compilazione (semi-)manuale
- Specifiche progetti → compilazione manuale + eventuale importazione
- Dati dettagliati (ore, task) → si accumulano con l'uso nella fase pilota
- I progetti storici: importazione leggera (nome, cliente, date, ore totali, team) senza pretendere il dettaglio task per task
