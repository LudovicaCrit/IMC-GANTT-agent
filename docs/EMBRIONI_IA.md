# Embrioni IA — archivio prima della rimozione

**Scopo.** Il codice descritto qui sta per essere rimosso dal repo, insieme a Pipeline e Tavolo di Lavoro (PIANO.md, fase 1). Non si butta un'idea: si toglie codice che oggi non serve o lavora su un modello superato, e si lascia scritto cosa conteneva, dove trovarlo e cosa vale la pena riprendere quando arriverà la fase giusta. Tutto resta recuperabile da git.

**Commit da cui recuperare:** `f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a` (`f17a0e2`, 15/10/2026, «Fase 1: dati di prova con date relative, via grpcio e lxml»). Le righe indicate sotto si riferiscono a quel commit.

Per recuperare un file così com'era:
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- <percorso>
```
Per leggerlo senza riportarlo nel working tree:
```
git show f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a:<percorso>
```

Criteri usati per «superato», da DECISIONI.md: §2 (scala delle quattro ore: stimate in sola lettura, pianificate come piano corrente, consumate dalla vista `ore_settimanali`; saturazione sul piano e sulle ore vere affiancate), §6 (ruoli base più funzionali; competenze in M2M; attività interne fuori dai candidati da spostare), §7 (i numeri li calcola il codice, l'LLM ragiona e argomenta; ogni proposta la decide un umano e resta registrata; l'IA non valuta le persone; scenari con un risolutore a vincoli), §10 (modello da variabile d'ambiente).

Infrastruttura comune a tutti gli embrioni (`backend/gemini_client.py`, che resta): `init_gemini(prompt_file)` (righe 58-81) carica il system prompt da `backend/prompts/`; `chiedi_semplice` (252-271) fa una `generate_content` senza storia; `chiedi_agente` (205-249) la fa con storia. Nessuna chiamata ha timeout, retry, streaming o schema di output: il JSON si ottiene chiedendolo nel prompt e ripulendo i backtick a mano, ripetuto in ogni endpoint.

---

## 1. Pipeline — costruisci-GANTT

**Cosa fa.** Dal nome, cliente, descrizione, budget e periodo di un progetto, l'LLM propone una lista di task (nome, fase, ore, profilo, predecessori per indice). Il frontend li raggruppa per fase, crea le fasi con `ore_vendute` = somma delle ore dei loro task e apre l'editor dei deliverable; «Conferma e avvia» crea fasi e task veri e porta il progetto «In esecuzione».
- Input: `{progetto_nome, progetto_cliente, descrizione, budget_ore, data_inizio, data_fine}`.
- Output LLM: `{task_suggeriti: [{nome, fase, ore, profilo, predecessori: [indici 1-based]}], note}`.

**Dove.**
- Backend: `backend/routes/agent.py` 210-216 (DTO `SuggerisciTaskRequest`), 577-618 (`POST /api/agent/suggerisci-task`); prompt `backend/prompts/suggerisci_task.md` (90 righe).
- Frontend: `frontend/src/pages/Pipeline.jsx` 14-612 (`PianificazioneProgetto`), di cui 220-282 `handleSuggerisci` e 232-273 la trasformazione task suggeriti → fasi + deliverable; 163-216 `confermaProgetto` (POST grezzo `/api/fasi`, poi `applicaModifiche` con `cambia_stato_progetto`); 634-793 la pagina con le tre tab. `frontend/src/api.js` 415-417 `suggerisciTask`, 427-429 `applicaModifiche`.

**Dipende da.** Solo il body: nessuna lettura del DB nell'endpoint. Scrive (dal frontend) `fasi`, `task`, `progetti.stato` tramite `POST /api/fasi` e `POST /api/tasks/applica`. Raggiungibilità: oggi nessuna, perché le tab che aprono `PianificazioneProgetto` filtrano stati di progetto che non esistono più (INVENTARIO §1).

**Da recuperare.**
- L'idea e la forma dell'output: task con fase e predecessori per **indice** (non per nome), che il codice traduce in dipendenze vere. È un buon contratto per un LLM.
- La trasformazione deterministica `task_suggeriti` → fasi raggruppate (`Pipeline.jsx` 232-273): è codice, non IA, ed è il ponte fra la proposta e il Wizard.
- Le regole del prompt sulle dipendenze (righe 23-42: indici, niente cicli, la gestione corre in parallelo).

**Superato.**
- I **profili** del prompt (`suggerisci_task.md` 43-50: «Project Manager», «Tecnico Senior»…) non esistono nella tabella `ruoli`; il frontend poi ne prende solo il primo e ripiega su 'Senior Consultant' (`Pipeline.jsx` 261). Vanno passati i ruoli base veri dal DB.
- Le **stime orarie** sono cablate nel prompt (righe 52-60: «sviluppo backend 150-300h»…) e calcolate dall'LLM: contro DECISIONI §7 (i numeri li fa il codice) e §1 (impara dallo storico). Le stime vanno ricavate dallo storico e passate all'LLM.
- Il prompt prevede un task «Gestione progetto» (righe 39-41): contro DECISIONI §11 (il tempo di direzione del PM ha un meccanismo dedicato, non task-PM).
- Somma delle ore suggerite in `ore_vendute` della fase (`Pipeline.jsx` 245): le vendute le scrive solo il contratto (DECISIONI §2). Le ore proposte sono stime → `ore_stimate` e `ore_pianificate`.
- Usa `budget_ore` (DECISIONI §2: si toglie). Nessuno streaming né timeout.

**Dove andrebbe.** PIANO.md, fase 6: «Costruisci-GANTT nel Wizard del Cantiere (recupero dell'embrione di Pipeline)». Pagina: Cantiere, Wizard di creazione.

**Recupero.**
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/routes/agent.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/prompts/suggerisci_task.md
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- frontend/src/pages/Pipeline.jsx
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- frontend/src/api.js
```

---

## 2. Tavolo di Lavoro — scenari

**Cosa fa.** Il manager scrive in linguaggio naturale cosa cambia («Sparkasse anticipa di 20 giorni», «Marco su DORA al 100% per due settimane»); l'LLM lo traduce in modifiche strutturate; un motore deterministico simula la cascata sulle dipendenze, ricalcola le saturazioni settimanali e segnala le scadenze bucate; il manager vede il GANTT prima/dopo e conferma, e le modifiche vengono scritte.
- Input LLM: `{testo, contesto_extra}` più il contesto aziendale di `contesto.py` (sezione 7).
- Output LLM: `{interpretazione, modifiche: [{tipo: sposta_task|cambia_focus, task_id, nuovo_inizio, nuova_fine, nuove_ore, dipendente_id, progetto_focus, percentuale, durata_settimane, data_inizio_focus, motivo}], domande, note_contesto}`.
- Simulazione: `simula_scenario(tasks, dipendenti, progetti, modifiche, data_oggi)` → `{tasks_prima, tasks_dopo, task_modificati, conseguenze, saturazioni, scadenze_bucate}`.

**Dove.**
- Backend:
  - `backend/routes/agent.py` 228-231 (DTO `InterpretaRequest`), 704-754 (`POST /api/agent/interpreta-scenario`); prompt `backend/prompts/interpreta_scenario.md` (128 righe).
  - `backend/scenario_engine.py` (763 righe, tutto il file): utilità di calendario 29-86 (giorni lavorativi lun-ven, nessuna festività), `propaga_cascata` 88-212 (FS, SS, FF, SF a durata conservata, vince il vincolo più in avanti), `simula_scenario` 213-386, saturazioni 388-497, scadenze 499-546, conseguenze leggibili 548-715, serializzazione 717-763.
  - `backend/routes/scenario.py` (406 righe, tutto il file): DTO 123-148, adattatori 150-242 (`_carica_dati_per_engine` legge task, dipendenti, progetti e dipendenze), `POST /api/scenario/simula` 243-336, `POST /api/scenario/conferma` 338-406 (ri-simula lato server, poi scrive date e `ore_pianificate` con `modifica_task`).
  - `backend/tests/test_scenario_engine.py`: 9 test puri (utilità, cascata lineare, cambia_focus, scadenza bucata, SS, FF, SF, multi-tipo, FS senza warning).
- Frontend: `frontend/src/pages/AnalisiInterventi.jsx` 352-753 (`EditorGanttUnificato`), di cui 441-452 `handleIA`, 454-475 `applicaModificheIAallaTabella`, 477-504 `verificaImpatto`, 507-541 `applicaTutto`; 115-243 `RisultatoSimulazione` (GANTT prima/dopo con `GanttChart` e `StatusLegend` importati da `pages/Gantt.jsx`); 28-108 `SidebarContesto`; 760-837 la pagina. `frontend/src/api.js` 595-600 `interpretaScenario`, 602-607 `simulaScenario`, 609-614 `confermaScenario`.

**Dipende da.** Prompt `interpreta_scenario.md`; `contesto.get_contesto_ia()`; tabelle lette `task`, `dipendenza_task`, `dipendenti`, `ruoli`, `progetti`; scritte `task` (date, `ore_pianificate`) da `/scenario/conferma` e, dal frontend, `task` (ore_stimate, assegnatario, stato, nuovi task) da `/api/tasks/applica`.

**Da recuperare.**
- **`scenario_engine.propaga_cascata`**: la propagazione sui quattro tipi di dipendenza, a durata conservata, con i suoi 9 test. È il pezzo più solido di tutto l'archivio e serve tale e quale al risolutore degli scenari e al semaforo strato 2.
- `_verifica_scadenze` e `genera_conseguenze`: la traduzione di un diff in frasi leggibili per il manager.
- Il **ciclo** interpreta → simula → mostra prima/dopo → conferma: è esattamente «l'IA propone, l'umano decide» di DECISIONI §7. Anche la ri-simulazione lato server alla conferma (non si fida del client).
- Il ruolo dell'LLM come solo traduttore (prompt righe 6-28: non propone, non commenta l'organico, chiede un chiarimento se ambiguo).

**Superato.**
- `cambia_focus` (engine 293-347) ragiona per percentuale di dedicazione e allunga le date in proporzione: un'euristica, non un risolutore a vincoli (DECISIONI §7 chiede OR-Tools).
- Le saturazioni (`_carico_settimana`, engine 448-497) e il contesto per l'LLM usano il **carico pianificato spalmato** (`ore_pianificate` / durata), mai le ore vere né il residuo dichiarato (DECISIONI §2). Il contesto passa `ore_stimate`.
- **L'LLM fa conti sulle date**: la tabella del prompt (righe 94-104) gli chiede «nuova_fine = data_fine_attuale − 20 giorni». Contro DECISIONI §7: l'LLM dovrebbe produrre il vincolo («−20 giorni sul progetto X»), e il calcolo lo fa il codice.
- Nessuna competenza (`task_competenze` non esiste), nessuna capacità che conti le assenze; giorni lavorativi senza festività (diverso dal frontend).
- Default cablato `data_oggi = date(2026, 3, 9)` (engine 248-249) se il chiamante non la passa.
- La conferma scrive task per task senza transazione (`modifica_task` committa a ogni chiamata) e **non registra chi ha deciso né cosa** (DECISIONI §7: resta registrata). Lo storico del Tavolo vive solo nello stato React (`AnalisiInterventi.jsx` 536).
- Il frontend confronta e scrive **`ore_stimate`** (`AnalisiInterventi.jsx` 486, 517-518), che per DECISIONI §2 sono in sola lettura; legge `t.predecessore`, che `/api/tasks` non restituisce più (dipendenze sempre vuote); confronta date `YYYY-MM-DD` con date `YYYY-MM-DDT00:00:00`. Passa da `/api/tasks/applica`, che accetta un campo libero (INVENTARIO §10).

**Dove andrebbe.** PIANO.md, fase 6: «task_competenze, semaforo strato 2, scenari con OR-Tools…» e, prima, «Estrazione da data_db_impl.py dei domini semaforo, scenari e SAL». Pagina: GANTT, scheda Scenari del dettaglio (DECISIONI §8); il Cantiere per l'applicazione delle modifiche (DECISIONI §7).

**Recupero.**
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/scenario_engine.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/routes/scenario.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/tests/test_scenario_engine.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/routes/agent.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/prompts/interpreta_scenario.md
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- frontend/src/pages/AnalisiInterventi.jsx
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- frontend/src/api.js
```

---

## 3. Bilanciamento

**Cosa fa.** Senza IA: calcola la saturazione settimanale di ogni dipendente, individua chi è sovraccarico e chi è sottoutilizzato, e per ogni task attivo dei sovraccarichi propone un candidato a cui riassegnarlo, con saturazione prima e dopo per entrambi.
- Input: nessuno (GET).
- Output: `{n_sovraccarichi, n_sottoutilizzati, proposte: [{tipo: "riassegnazione", priorita, da_persona, da_persona_id, da_saturazione, da_saturazione_dopo, task_id, task_nome, progetto, ore_sett_task, profilo_richiesto, candidato_migliore: {...}, altri_candidati: [max 2]}], riepilogo: [{nome, profilo, saturazione}]}`.

**Dove.**
- Backend: `backend/routes/risorse.py` 311-483 (`GET /api/risorse/suggerisci-bilanciamento`). Usa `carico_settimanale_dipendente` (`backend/data_db_impl.py` 1261-1324) e `_to_dt` (`data_db_impl.py` 21).
- Frontend: `frontend/src/pages/AnalisiInterventi.jsx` 250-345 (`BilanciamentoPanel`), montato a 571; `frontend/src/api.js` 220-222 `fetchBilanciamento`.

**Dipende da.** Tabelle lette: `dipendenti` con `ruoli` (inquadramento, `joinedload`) e `dipendenti_ruoli_aggiuntivi` → `ruoli` (`selectinload`), `task` con `progetti`. Nessuna scrittura: la proposta non si applica da qui.

**Come funziona il match — passo per passo.**
1. **Carico.** Per ogni dipendente attivo `carico = carico_settimanale_dipendente(id, oggi)`: somma, sui task non Completati né Sospesi la cui finestra interseca la settimana lun-ven, di `ore_pianificate / durata in settimane` (minimo 1 settimana). Saturazione = `carico / ore_sett × 100` (righe 347-349).
2. **Ore settimanali del singolo task**: stessa formula, `ore_pianificate / max(1, giorni/7)`; un task senza date vale 0 (righe 352-366). I task considerati sono «In corso» e «Da iniziare», escluso il progetto `P010` per id (riga 335).
3. **Classi.** Sovraccarico se saturazione > 100; sottoutilizzato se < 90 (righe 396-397). Fra 90 e 100 nessuno dei due.
4. **Per ogni sovraccarico** (dal più saturo) e **per ogni suo task** (dal più leggero in ore/settimana, righe 402-403), si scorrono i sottoutilizzati, esclusa la persona stessa.
5. **Predicato di ruolo (riga 432):**
   ```python
   profilo == sotto["profilo"] or profilo in sotto["ruoli_aggiuntivi"]
   ```
   - `profilo` è `Task.profilo_richiesto`, una **stringa** sul task (es. «Senior Consultant»).
   - `sotto["profilo"]` è il **nome dell'inquadramento** del candidato, da `Dipendente.ruolo_id` → `ruoli.nome`.
   - `sotto["ruoli_aggiuntivi"]` è la lista dei **nomi dei ruoli funzionali** ricoperti in aggiunta, dalla M2M `dipendenti_ruoli_aggiuntivi` (oggi solo «PM»).
   - Il confronto è quindi **ruolo contro ruolo, per uguaglianza esatta del nome**: lato persona i nomi vengono da FK verso `ruoli`, lato task da una stringa libera (non c'è FK da `task.profilo_richiesto` a `ruoli`). Un refuso o una differenza di maiuscole nel profilo del task fa fallire il match in silenzio; un task con profilo vuoto (44 su 114 nel DB di sviluppo, INVENTARIO §3) non trova nessuno.
   - Il commento alle righe 410-431 spiega perché non è più il vecchio «ramo B», che confrontava il ruolo con le competenze e matchava solo «PM» per omonimia, e dichiara che il match per competenze non esiste finché non esiste `task_competenze`.
6. **Capienza (righe 433-434).** Il candidato è ammesso se `ore_sett − carico ≥ 0,5 × ore_sett_task`: basta che possa assorbire **metà** del task.
7. **Scelta (righe 448-451).** Fra i candidati si sceglie chi, dopo lo spostamento, arriva più vicino al 100% (`|saturazione_dopo − 100|` minima); gli altri due migliori vanno in `altri_candidati`.
8. **Priorità (riga 455).** «alta» se il sovraccarico supera il 125%, altrimenti «media». Ordinamento finale: prima le alte, poi per saturazione decrescente.

**Da recuperare.**
- Il **predicato** ruolo base OR ruolo aggiuntivo: è la base strutturata del match di DECISIONI §6 («dati strutturati come base, IA semantica per i buchi»). Lo staffing per competenze lo estende con un terzo termine sulle competenze del task (`task_competenze`) contro quelle della persona (`dipendenti_competenze`), mantenendo l'uguaglianza per chiave e non per stringa.
- La forma della proposta (da chi, a chi, saturazione prima e dopo per entrambi, alternative): è la forma giusta da mostrare al PM perché decida.
- È deterministico e senza IA: va in un modulo di servizio, non in una route.

**Superato.**
- Carico solo sul **piano spalmato**, non sulle ore vere né sul residuo dichiarato (DECISIONI §2: saturazione su piano e su ore vere affiancate).
- **Greedy senza stato**: il carico del candidato non viene aggiornato dopo una proposta, quindi la stessa persona può ricevere più task e finire oltre il 100%; e si propone di spostare **ogni** task del sovraccarico, non il minimo necessario. È il problema che il risolutore a vincoli (DECISIONI §7) risolve per costruzione.
- Esclusione per id `P010` (che oggi è un progetto cliente) invece che per `tipologia = 'interna'`; le attività interne non sono escluse dai candidati da spostare (DECISIONI §6).
- Soglie cablate: 100, 90, 0,5, 125 (DECISIONI e CLAUDE.md: soglie in configurazione).
- Usa `datetime.now()` invece di `get_oggi()`.
- Non valuta le persone: ordina per spazio di calendario, non per merito. Passa la domanda AI Act.

**Dove andrebbe.** PIANO.md, fase 6 («task_competenze… scenari con OR-Tools, capacità che tiene conto dei periodi di assenza»); come anticipo strutturato, fase 2 («Risorse: un solo numero di carico, calcolato nel backend»). Pagina: Risorse, e il Cantiere quando si assegna un task.

**Recupero.**
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/routes/risorse.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- frontend/src/pages/AnalisiInterventi.jsx
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- frontend/src/api.js
```

---

## 4. Analisi GANTT da una segnalazione

**Cosa fa.** Riceve una segnalazione di un dipendente (sovraccarico, blocco, richiesta di supporto) e chiede all'LLM da una a tre proposte di redistribuzione (riassegna, sposta date, aggiungi supporto), con benefici, rischi, fattibilità e urgenza.
- Input: `{segnalazione_tipo, segnalazione_dettaglio, dipendente_id, priorita}`.
- Output: `{proposte: {analisi, segnalazione_ricevuta, contesto_rilevante, proposte: [{id, titolo, azioni: [...], impatto: {benefici, rischi, fattibilita}}], conflitti, urgenza}, contesto: {segnalazione, dipendente_saturazione}}`.

**Dove.**
- Backend: `backend/routes/agent.py` 203-207 (DTO `AnalisiRequest`), 436-570 (`POST /api/agent/analisi-gantt`); prompt `backend/prompts/analisi_segnalazioni.md` (91 righe).
- Frontend: nessuno oggi (`api.js` 407-409 `richiediAnalisiGantt` non è chiamata). L'ultima interfaccia era `frontend/src/pages/CentroSegnalazioni.jsx`, eliminata dal commit `de5cbcc`; si recupera dal suo genitore `e67fc647e8aba0f9a2dcecdb77e9314d4b65481a`.

**Dipende da.** Tabelle lette: `dipendenti`, `ruoli`, `task` (In corso, Da iniziare) con `progetti` e `dipendenza_task`, `progetti` (stati «In esecuzione», «In bando»); per ogni dipendente `carico_settimanale_dipendente` e `get_progetti_dipendente` (una query ciascuno: N+1). Nessuna scrittura.

**Da recuperare.**
- Il prompt ha buone regole di condotta (righe 12-31): proporre e non decidere, niente commenti sull'organico, niente analisi economiche, nomi e non sigle, al massimo tre opzioni con pro e contro. Riusabili in qualunque IA di proposta.
- La forma della risposta (proposte con azioni tipizzate e impatto) si sovrappone a quella degli scenari: va fusa con l'embrione 2, non tenuta a parte.

**Superato.**
- **L'LLM calcola**: fattibilità e urgenza sono soglie di saturazione che il prompt gli chiede di applicare (righe 77-86: «sotto il 70%», «sopra il 120%»), e l'impatto delle opzioni lo stima lui. Contro DECISIONI §7: la saturazione prima e dopo la calcola il codice (come fa già il bilanciamento), l'LLM argomenta.
- Contesto su `ore_stimate` e carico pianificato, non ore vere.
- Filtra lo stato «In bando», che non esiste più.
- Le segnalazioni come ingresso sono un canale quasi vuoto (3 righe, tutte da seed): il flusso dal basso è ora l'appunto al volo e la coda da ratificare (DECISIONI §4).
- Usa `budget_ore` nel contesto progetti.

**Dove andrebbe.** Confluisce negli scenari di fase 6 (stessa pagina, scheda Scenari) o nella sintesi per il management («i progetti da guardare e perché», fase 6, cruscotto di Economia). Non merita un endpoint proprio.

**Recupero.**
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/routes/agent.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/prompts/analisi_segnalazioni.md
git show e67fc647e8aba0f9a2dcecdb77e9314d4b65481a:frontend/src/pages/CentroSegnalazioni.jsx > frontend/src/pages/CentroSegnalazioni.jsx
```

---

## 5. Verifica della pianificazione

**Cosa fa.** Prima di avviare un progetto, l'LLM esamina il GANTT pianificato e segnala task orfani (senza successori), fasi mancanti, stime irrealistiche, dipendenze sospette e incoerenze di profilo, con un esito ok / attenzione / problemi.
- Input: `{progetto_nome, progetto_cliente, budget_ore, data_inizio, data_fine, task_pianificati: [dict liberi, con «assegnato» come nome]}`.
- Output: `{esito, riepilogo, segnalazioni: [{tipo, gravita, task_coinvolto, descrizione, suggerimento}], nota_positiva}` (prompt righe 58-89).

**Dove.**
- Backend: `backend/routes/agent.py` 219-225 (DTO `VerificaPianificazioneRequest`), 625-697 (`POST /api/agent/verifica-pianificazione`); prompt `backend/prompts/verifica_pianificazione.md` (94 righe).
- Frontend: nessuno. `api.js` 411-413 `verificaPianificazione` è importata in `Pipeline.jsx` riga 2 ma mai chiamata; la chiamata è stata tolta nel commit `a7f2a9c` (04/05/2026).

**Dipende da.** Body; per i dipendenti citati per **nome** nel body, una query su `dipendenti` + `ruoli` e `carico_settimanale_dipendente` per la saturazione. Nessuna scrittura.

**Da recuperare.**
- Il **catalogo dei controlli** (prompt righe 18-48) e l'«equilibrio nel giudizio» (righe 50-56: al massimo 4-5 segnalazioni, raggruppate, esito bilanciato).

**Superato.**
- **Quasi tutto è programmabile** e va fatto dal codice (DECISIONI §1: «se si può programmare, si programma»): task senza successori, catene troppo lunghe, ore al giorno per persona sopra soglia, task senza predecessori che non sono il primo, profilo del task diverso dall'inquadramento dell'assegnato. All'LLM resta solo «manca una fase che di solito c'è?» e la formulazione del riepilogo.
- Soglie cablate nel prompt (10, 12, 16 h/giorno; 110% di saturazione).
- Riconosce le persone per nome invece che per id.
- Fasi «tipiche» di un progetto software (prompt righe 27-31): il dominio di IMC è GRC e consulenza; le fasi vanno prese dai modelli in Configurazione.

**Dove andrebbe.** Fase 6, insieme a costruisci-GANTT: un controllo deterministico nel Wizard e nel Cantiere, prima dell'avvio, con eventuale commento dell'LLM. Le regole programmabili possono anticipare in fase 1 o 2 come igiene del piano (criticità, DECISIONI §5).

**Recupero.**
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/routes/agent.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/prompts/verifica_pianificazione.md
```

---

## 6. Chat della consuntivazione — compila-consuntivazione e avatar vocale

**Cosa fa.** Il dipendente racconta la settimana a parole; l'LLM la mappa sui suoi task, propone le ore, e alla conferma emette un blocco `[MAPPATURA_ORE]` con il JSON da applicare al form; raccoglie anche segnalazioni (`[SEGNALAZIONE]`) che vengono salvate.
- Input: `{dipendente_id, messaggio, ore_compilate: {task_id: ore}, stati_compilati, ore_assenza, tipo_assenza, nota_assenza, spese, chat_history}`.
- Output: `{risposta, segnalazione, mappatura_ore: {ore: {task_id: ore}, assenza: {tipo, ore}, giorni_sede, giorni_remoto, note_extra}, contesto_carico}`.

**Dove.**
- Backend: `backend/routes/agent.py` 191-200 (DTO `ChatRequest`), 252-429 (`POST /api/agent/chat`): caricamento dati 276-320, contesto 322-335, chiamata 337-338, **parser** di `[MAPPATURA_ORE]` 345-380 e di `[SEGNALAZIONE]` 382-422. `backend/gemini_client.py` 84-202 (`costruisci_contesto`) e 205-249 (`chiedi_agente`, con la storia della chat). Prompt `backend/prompts/consuntivazione.md` (215 righe). `backend/data_db_impl.py` 2504 (`aggiungi_segnalazione`).
- Frontend: nessuno oggi (`api.js` 403-405 `sendChatMessage` non è chiamata). L'ultima interfaccia era `frontend/src/pages/Consuntivazione.jsx`, eliminata dal commit `167dd36`; si recupera dal genitore `840747766f35c01f724d828b58e117c786e8de56` (chiamata a riga 134, uso di `mappatura_ore` a 148).

**Dipende da.** Prompt `consuntivazione.md`; tabelle lette `dipendenti`, `task` (del dipendente e dei colleghi, In corso e Da iniziare), `fasi`, `progetti`; `carico_settimanale_dipendente` e `get_progetti_dipendente`; scrive `segnalazioni`. Fallback in memoria `main.SEGNALAZIONI_STORE` (righe 409-422), di fatto irraggiungibile.

**Da recuperare.**
- **L'interazione**: racconto libero → proposta → conferma → applicazione. È esattamente la compila-consuntivazione di DECISIONI §7, e il racconto si presta all'avatar vocale.
- Le regole di tono del prompt (righe 10-15, 61-66): mai far sentire il dipendente sotto esame, niente richiesta di ore mancanti a chi esprime fatica. Coerenti con la regola AI Act.
- L'idea di emettere un blocco strutturato separato dal testo, che il frontend presenta come pannello da confermare.
- La lista chiusa dei task su cui si può mappare (`task_assegnati`) e i colleghi per «ho aiutato X» (che ora è il soccorso, DECISIONI §4).

**Superato.**
- **Il contratto d'ingresso è della vecchia pagina**: ore **settimanali per task** prese dal body, assenze e spese che non hanno più tabelle. La consuntivazione è a blocchi per giorno (`POST /api/consuntivi/salva-blocchi`): la mappatura deve produrre blocchi `{giorno, task o pezzo, ore}`, e il contesto deve venire dal DB (`/me`), non dal body.
- **L'LLM fa i conti**: le regole di stima (prompt 47-59: giornata = 8h, «un'oretta» = 2h, arrotondare a multipli di 2) sono numeri che deve calcolare il codice, e sono cablati su IMC (8h, 40h contrattuali). L'LLM deve estrarre attività e durate dichiarate; la conversione in blocchi la fa il codice con le ore contrattuali della persona.
- Il **parser** a stringhe (`index("[MAPPATURA_ORE]")`, pulizia dei backtick, righe `tipo:`/`priorità:` lette a mano) è fragile: va sostituito dall'output strutturato con schema (fase 6, infrastruttura comune).
- Le segnalazioni libere come canale di uscita: oggi il flusso è l'appunto al volo, un pezzo con origine e stato di ratifica (DECISIONI §4).
- Carico dal piano spalmato, `ore_stimate` dei task (`gemini_client.py` 154).

**Dove andrebbe.** PIANO.md, fase 6: «Compila-consuntivazione con avatar vocale, anche come ingresso dell'appunto al volo». Pagina: Consuntivazione (griglia), e Home per l'appunto al volo.

**Recupero.**
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/routes/agent.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/gemini_client.py
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/prompts/consuntivazione.md
git show 840747766f35c01f724d828b58e117c786e8de56:frontend/src/pages/Consuntivazione.jsx > frontend/src/pages/Consuntivazione.jsx
```

---

## 7. contesto.py — il quadro aziendale per l'IA

**Cosa costruisce.** `get_contesto_ia()` (`backend/contesto.py` 105-196) produce un JSON con: `data_corrente`; i progetti in stato «In esecuzione» o «In bando», ciascuno con id, nome, cliente, stato, scadenza e la lista completa dei suoi task (id, nome, assegnatario per nome, inizio, fine, `ore_stimate`, stato); i dipendenti attivi con id, nome, profilo (inquadramento), `ore_sett` e saturazione della settimana. Tiene una cache in memoria di 60 secondi (righe 99-116). `invalida_cache_contesto()` (199-206) esiste ma nessuno la chiama.

**Per chi.** Solo `POST /api/agent/interpreta-scenario` (`routes/agent.py` 719). Gli altri endpoint costruiscono un contesto proprio (docstring, righe 20-24).

**Dipende da.** Tabelle `progetti`, `task` (tutti, anche Eliminati), `dipendenti`, `ruoli`; `carico_settimanale_dipendente` per ogni dipendente (una query ciascuno: N+1, 18 query oggi, 500 a scala prodotto).

**Da recuperare.**
- L'idea di **un solo costruttore del contesto aziendale**, condiviso fra le IA, con nomi leggibili accanto agli id (l'LLM usa gli id solo nei campi strutturati).

**Superato.**
- Ore stimate e carico pianificato spalmato; nessuna ora vera, nessun residuo dichiarato, nessuna vendute/pianificate (DECISIONI §2). Il contesto giusto è quello che i numeri del cruscotto di Economia e del semaforo strato 2 calcolano già.
- Include i task Eliminati e filtra lo stato inesistente «In bando».
- Cache in memoria per processo, mai invalidata dopo le scritture; il controllo `(now − timestamp).seconds < 60` ignora i giorni (dopo un giorno e pochi secondi la cache sembra fresca).
- `datetime.now()` per la cache e `get_oggi()` per i dati: due orologi.

**Dove andrebbe.** Fase 6, «Infrastruttura comune»: un modulo di servizio che costruisce il contesto da numeri già calcolati, condiviso da sintesi, scenari e costruisci-GANTT.

**Recupero.**
```
git restore --source=f17a0e27c9a47bd7c33bc4dd00be6a7719c98b7a -- backend/contesto.py
```

---

## Riepilogo

| Embrione | Fase del piano | Pagina di destinazione | Recuperare / riscrivere |
|---|---|---|---|
| 1. Pipeline, costruisci-GANTT | 6 — Costruisci-GANTT nel Wizard | Cantiere (Wizard) | **Riscrivere**, recuperando il contratto dell'output (task con predecessori per indice) e la trasformazione task → fasi |
| 2a. `scenario_engine.propaga_cascata` + 9 test | 6 — scenari, semaforo strato 2 | — (modulo di servizio) | **Recuperare** così com'è |
| 2b. Tavolo: interpreta → simula → conferma | 6 — scenari con OR-Tools | GANTT, scheda Scenari; Cantiere | **Riscrivere** il motore (vincoli, ore vere, competenze); recuperare il ciclo e il ruolo dell'LLM come traduttore; aggiungere il registro delle decisioni |
| 3. Bilanciamento | 6 (staffing per competenze); anticipo strutturato in 2 | Risorse, Cantiere | **Recuperare** il predicato ruolo base OR aggiuntivo e la forma della proposta; **riscrivere** carico e scelta |
| 4. Analisi GANTT da segnalazione | 6 — scenari o sintesi management | GANTT Scenari / Economia | **Riscrivere** dentro gli scenari; recuperare le regole di condotta del prompt |
| 5. Verifica pianificazione | 6 (con costruisci-GANTT); regole anche in 1-2 come igiene del piano | Cantiere (Wizard) | **Riscrivere** in codice; recuperare il catalogo dei controlli |
| 6. Chat consuntivazione, MAPPATURA_ORE | 6 — compila-consuntivazione e avatar | Consuntivazione, Home | **Riscrivere** sul modello a blocchi con output strutturato; recuperare interazione e tono |
| 7. contesto.py | 6 — infrastruttura comune | — (modulo di servizio) | **Riscrivere** su ore vere e numeri calcolati; recuperare l'idea del costruttore unico |
