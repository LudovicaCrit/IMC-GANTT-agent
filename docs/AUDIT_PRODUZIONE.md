# Audit di robustezza per la produzione

*Passo A0, sola lettura. Fotografia del codice al commit `0bb3a88` più le modifiche non committate presenti sul disco il 16/10/2026 (lavoro in corso di un'altra sessione: `backend/routes/progetti.py` e un suo test; vedi 10.3). Come INVENTARIO.md, non si aggiorna: lo stato dei lavori sta in PIANO.md.*

Domanda: che cosa oggi funziona ma, in produzione — più utenti, più dati, Windows Server dietro IIS — si rompe o dà risultati sbagliati.

**Gravità**
- **bloccante**: dati persi o sbagliati, sistema fermo o falla di sicurezza in condizioni normali di esercizio. Da chiudere prima di andare in produzione.
- **serio**: guasto probabile sotto carico o in un caso realistico.
- **minore**: igiene, o guasto in casi rari.

**Metodo.** Lettura statica del codice. Non ho avviato server, test né query. Ogni riga citata è stata letta. I bloccanti li ho ricontrollati io sul codice, uno per uno. Dove un caso dipende da dati o configurazioni che non ho visto, lo dico. Accanto ai casi già registrati c'è «(già in BACKLOG)» o «(già in SECURITY_BACKLOG)».

---

## 1. Transazioni

**1.1 — Sessioni non chiuse se c'è un'eccezione.** · serio
- Dove: `get_session()` è usato senza `try/finally` e senza `with` in:
  - `data_db_impl.py`:
    - `get_dipendente` 401-446
    - `ore_consuntivate_progetto` 451-459
    - `tasso_compilazione_progetto` 1237-1247
    - `get_progetti_dipendente` 1315-1322
    - `_next_task_id` 2020-2023
    - `aggiungi_task` 2190-2320: chiude a mano sui ValueError, ma non su flush e commit
    - `sostituisci_dipendenze` 2362-2412
    - `modifica_task` 2441-2453
    - `get_segnalazioni` 2461-2479
  - `routes/configurazione.py`: tutte le scritture fanno commit fuori dal try (242, 259, 273, 302, 317, 532, 579, 593, 635, 650, 713, 728).
  - `routes/consuntivi.py:378-550`, `routes/dipendenti.py:98-186`, `routes/progetti.py:362-381`, `routes/fasi.py:416-473`, `routes/tasks.py:114-130` e `498-500`, `routes/gantt.py:194-224`.
- In produzione: un errore lascia la connessione «in uso», con la transazione abortita, finché il garbage collector non la recupera. Il pool, già piccolo (vedi 10.2), si esaurisce prima, e le richieste successive aspettano 30 s e rispondono 500.
- Correzione: `with get_session() as s:` (o la dependency `get_db`) ovunque, con rollback sull'eccezione.

**1.2 — Salvataggio delle ore: lo stato del task si propaga fuori dalla transazione.** · serio
- Dove: `data_db_impl.py:2916`, poi `2939-2965`.
- In produzione: le ore e le dichiarazioni vengono committate. Dopo, ogni task si aggiorna con `modifica_task` in una sessione propria. Se un passo fallisce, le ore restano salvate e lo stato no. Inoltre, fra la lettura (2943) e la scrittura, il PM può aver sospeso il task, e la propagazione lo riscrive.
- Correzione: aggiornare `Task.stato` nella stessa sessione e prima del commit, rileggendo con `with_for_update`.

**1.3 — Modifica di un task in due chiamate dal frontend.** · serio
- Dove: `CantiereDettaglio.jsx:302-313`: prima `updateTask`, poi `sostituisciDipendenzeTask`. La modale manda sempre le dipendenze (`SezioneFasiTask.jsx:784`).
- In produzione: se la seconda chiamata fallisce, i campi sono già scritti. L'utente vede un errore e pensa che non sia stato salvato nulla.
- Correzione: un endpoint unico e transazionale.

**1.4 — Snapshot SAL e bollettino.** · minore
- Dove: `data_db_impl.py:3128-3139` e `3492-3503`.
- In produzione: lettura e scrittura avvengono in sessioni diverse, quindi lo snapshot può fotografare uno stato già superato.
- Correzione: una sola sessione.

## 2. Ordine fra validazione e scrittura

**2.1 — Il PATCH del dipendente sovrascrive tutti i campi con i default del DTO.** · **bloccante**
- Dove:
  - `routes/configurazione.py:165-169`: DTO con `ore_sett=40`, `costo_ora=None`, `sede=""`, `competenze=[]`.
  - `routes/configurazione.py:566-577`: assegna tutti i campi e cancella e ricrea le competenze.
  - Il form (`Configurazione.jsx:229`, `234`) non manda `sede`.
- In produzione: **ogni salvataggio di un dipendente da Configurazione azzera la sede**. Un client che manda una PATCH parziale cancella anche costo orario e competenze.
- Correzione: applicare solo i campi presenti in `req.model_fields_set`, da una whitelist esplicita.

**2.2 — Un null esplicito su un campo NOT NULL diventa 500.** · serio
- Dove:
  - `routes/progetti.py:951-952` (nome, stato, tipologia, priorita, urgenza; il commento a 243-245, «None = non tocca», non è vero con `exclude_unset`);
  - `routes/fasi.py:338-339` (l'autoflush scatta già alla query di 345);
  - `routes/tasks.py:384-390` e `modifica_task`.
- In produzione: IntegrityError e un 500 opaco su un errore del client.
- Correzione: respingere con 422 i null sui campi NOT NULL, come già fa `sottotask.py:255-267`.

**2.3 — Chiavi esterne e CHECK non validati prima della scrittura.** · serio
- Dove:
  - `pm_id`: `progetti.py:197`, `235`, scritto a 426, 500, 677, 952;
  - `dipendente_id` dei task: `progetti.py:269`, `295`, scritto a 572, 749, 879;
  - `ruolo_id` del dipendente: `configurazione.py:519`, `565`;
  - `fase_id` del task: `tasks.py:207`;
  - `tipologia`: `progetti.py:181`, `224`;
  - stato del task: `tasks.py:183`, `213`;
  - nome del task senza `max_length`: `tasks.py:171`, `206`;
  - competenze duplicate: `configurazione.py:413-418`;
  - date: `datetime.fromisoformat` fuori da un try (`tasks.py:266-267`, `386`), e `None < date` (`tasks.py:412`, `420`, `426`).
- In produzione: un input sbagliato dà 500 invece di un 422 che spiega cosa correggere.
- Correzione: tipi `date`, `Literal` e `max_length` nei DTO, e controllo dell'esistenza delle chiavi esterne prima di scrivere.

**2.4 — `ore_sett` e `costo_ora` senza limiti.** · serio
- Dove: `configurazione.py:165-166`.
- In produzione:
  - un solo dipendente con `ore_sett = 0` causa ZeroDivisionError in `dipendenti.py:182`, `dipendenti.py:225` e `risorse.py:112`, e manda in 500 **tutta** `/api/dipendenti` e `/api/risorse/carico`;
  - un valore oltre 32767 sfora lo SmallInteger (DataError, 500);
  - `costo_ora` accetta valori negativi.
- Correzione: `Field(gt=0, le=…)` e `Field(ge=0)`.

**2.5 — Un task può finire in una fase di un altro progetto.** · serio
- Dove: `tasks.py:207`, `384-390`, poi `data_db_impl.py:2440-2456`. Le date sono validate contro la fase vecchia (`tasks.py:418`).
- In produzione: il task resta del progetto A ma sta sotto una fase di B. Le ore e l'economia vanno su A, il GANTT lo mostra in B.
- Correzione: caricare la nuova fase, verificare che sia dello stesso progetto e validare le date contro di lei.

**2.6 — Valori NaN e Infinity accettati.** · minore
- Dove: `consuntivi.py:217`, `ore_stimate_residue: Optional[float]`. Il controllo `< 0` (r.300) non li ferma.
- In produzione: arrivano nel DB e poi nelle risposte, che diventano JSON non valido per il browser.
- Correzione: `Field(ge=0, allow_inf_nan=False)`.

## 3. Concorrenza

**3.1 — Id dei task calcolato con `max()` su una stringa.** · **bloccante**
- Dove: `data_db_impl.py:2019-2026` (`_next_task_id`) e `2100-2117` (`genera_id_task_multipli`). Chiamate da `progetti.py:524`, `703`, `862` e da `tasks.py:304` attraverso `aggiungi_task`.
- In produzione:
  - `Task.id` è `String`, quindi il massimo è alfabetico. Superato T999, `max()` restituisce sempre «T999», perché «T999» > «T1000». Ogni creazione rigenera T1000, viola la chiave primaria e risponde 500. **Dalla seconda creazione dopo T1000 non si crea più nessun task.** Con 500 dipendenti la soglia si supera presto.
  - Due manager che salvano nello stesso momento ottengono lo stesso id.
- Correzione: una sequenza Postgres, come fatto per i progetti in `0bb3a88`.

**3.2 — Id dei dipendenti calcolato con `max()` su una stringa.** · serio
- Dove: `configurazione.py:506-511`.
- In produzione: stesso meccanismo del 3.1, con il tetto a D999, che comprende anche i dipendenti disattivati. Due creazioni concorrenti danno lo stesso id e 500.
- Correzione: una sequenza.

**3.3 — Salvataggio della settimana di consuntivi senza lock.** · serio
- Dove:
  - `data_db_impl.py:2762-2789`, `2818-2858`, `2901-2915`: leggi-poi-inserisci su blocchi_ore, consuntivi e consuntivo_sottotask;
  - `routes/consuntivi.py:761-764` intercetta solo `ConsuntivoNonValido`.
- In produzione:
  - con un doppio clic o due schede aperte, le due richieste vedono entrambe «nessun blocco», la UNIQUE scatta e una delle due prende 500;
  - il tetto delle 24 ore al giorno (`2689-2730`) si controlla prima di scrivere: due salvataggi concorrenti su attività diverse passano entrambi e insieme lo superano.
- Correzione: `pg_advisory_xact_lock(dipendente, settimana)` all'inizio della transazione, e IntegrityError → 409.

**3.4 — PUT /completo della bozza senza lock.** · serio
- Dove: `progetti.py:657`.
- In produzione: due invii cancellano le stesse fasi vecchie e inseriscono ciascuno le proprie, quindi le fasi risultano duplicate.
- Correzione: `.with_for_update()` sul progetto.

**3.5 — Creazioni senza difesa dal doppio invio.** · serio
- Dove:
  - lato server: POST /api/progetti, POST /completo, `crea_fase`, task-multipli, POST /api/tasks, ruoli, competenze, dipendenti, SAL (`sal.py:59`), bollettino (`bollettino.py:47`);
  - lato client: vedi 9.1.
- In produzione: record duplicati, cioè due dipendenti, due fasi o due fotografie SAL immutabili.
- Correzione: pulsanti disabilitati durante la richiesta e, dove serve, una chiave di idempotenza o un vincolo UNIQUE.

**3.6 — Altri leggi-poi-scrivi.** · minore
- Dove:
  - `contatore_ordine_task` (`data_db_impl.py:2073`) e `sottotask.py:418-421`: max(ordine)+1, ordine duplicato (l'id fa da spareggio);
  - `sostituisci_dipendenze` (2415-2426): delete più insert, con due PUT concorrenti si ha UniqueViolation e 500, e non c'è controllo sui cicli A→B→A;
  - `progetti.py:406-407`: id esplicito controllato e poi inserito.
- Correzione: lock sulla riga padre, vincoli UNIQUE, controllo dei cicli.

## 4. Errori

**4.1 — `str(e)` nel detail delle risposte.** · serio
- Dove: `progetti.py:599`, `773`, `923` (500 con `{e}`); `data_db_impl.py:2951`, `2964` (avvisi del salvataggio ore con `{e}`); `bollettino.py:54`.
- In produzione: un IntegrityError di SQLAlchemy porta al client testo SQL, nomi di vincoli e parametri.
- Correzione: un messaggio generico al client, con il dettaglio nel log (vedi 10.4).

**4.2 — IntegrityError non tradotti.** · serio
- Dove: configurazione (rinomina di un ruolo su un nome esistente, r.256; ruoli e competenze concorrenti), consuntivi (3.3), dipendenze (3.6).
- In produzione: 500 dove serve un 409.
- Correzione: `except IntegrityError` → 409 parlante, in un punto comune.

**4.3 — Un dipendente disattivato risulta «Sconosciuto» e non solleva errori.** · serio
- Dove: `data_db_impl.py:409-411`: `get_dipendente` restituisce `{"nome": "Sconosciuto (…)", "ore_sett": 40}`. Gli `except (IndexError, KeyError)` di `consuntivi.py:454`, `609`, `717` e `dipendenti.py:204` sono quindi codice morto.
- In produzione: nella vista PM compaiono righe «Sconosciuto» con 40 ore inventate.
- Correzione: restituire None e gestirlo nei chiamanti. Vedi anche 7.3.

**4.4 — Export Excel in 500 quando mancano le date di fine.** · serio
- Dove: `gantt.py:859`: `max(date_fine)` su una lista vuota.
- In produzione: basta un progetto i cui task hanno solo la data di inizio.
- Correzione: `max(..., default=…)`.

**4.5 — `stati_colori.py` legge il JSON a ogni richiesta, senza gestire file assente o malformato.** · minore
- Dove: `stati_colori.py:12-20`.
- In produzione: se il deploy non copia `condiviso/` accanto a `backend/`, l'Excel risponde 500.
- Correzione: leggere il file all'avvio e fallire subito se manca; indicarlo nella procedura di installazione.

## 5. Query che crescono coi dati

**5.1 — N+1 sulle pagine principali.** · serio
- Dove:
  - `consuntivi.py:453`: `get_dipendente` per dipendente, con una sessione e 2 query a testa.
  - `configurazione.py:356` e `375`: competenze e azienda lette con una query per dipendente.
  - `risorse.py:104-107`: `carico_settimanale_dipendente` per dipendente per settimana, cioè 500 × 12 = 6000 sessioni.
  - `risorse.py:71` e `195-206`: numero di settimane senza limite.
  - `home.py:318-321`: carico per persona a ogni apertura della Home.
  - `dipendenti.py:172`.
  - `progetti.py:326-327`: 3 query per progetto; la docstring dice «evita N+1».
  - `tasks.py:134`, `gantt.py:228`, e l'export (`gantt.py:780`, `898`): `get_dipendente` per riga, due volte per task.
  - `_serializza_stato_progetto` (`data_db_impl.py:3056`, `3067`, `3080`).
  - `lista_snapshot_progetto` (3175), `lista_bollettini_progetto` (3534), `get_segnalazioni` (2468).
- In produzione: a 500 dipendenti, migliaia di query per apertura di pagina, e il pool si esaurisce (10.2).
- Correzione: versioni batch (lista di id → dict) con una query `IN` o un join, e `Query(le=…)` sui periodi.

**5.2 — La vista `ore_settimanali` aggrega tutta `blocchi_ore` a ogni chiamata.** · serio, da confermare
- Dove: join della vista con `task` in `data_db_impl.py:454-458`, `713-721`, `3036-3046`, `3296-3299`. La moltiplicano:
  - `margini_economia`, 3 query per progetto su tutti i progetti;
  - `criticita_sforamento_progetti`, nella Home;
  - la lista dei progetti;
  - `_serializza_economia_progetto` (3460), che ricalcola tutta l'economia per congelare un solo bollettino.
- In produzione: il filtro su `Task.progetto_id` non viene portato dentro il GROUP BY, quindi con anni di blocchi (10⁵–10⁶ righe l'anno) Home ed Economia rallentano col passare del tempo. È un ragionamento sul planner: va confermato con `EXPLAIN ANALYZE` su volumi realistici.
- Correzione: aggregare `blocchi_ore` in join diretto con `task`, oppure filtrare per `task_id IN (subquery)`; nel bollettino, filtrare il solo progetto.

**5.3 — Indici mancanti.** · serio (già in BACKLOG, in parte)
- Mancano su:
  - `consuntivi(dipendente_id, settimana)`: la UNIQUE comincia da `task_id`, e `/me` (`data_db_impl.py:1586-1588`) fa seq scan;
  - `task.progetto_id`, `task.fase_id`, `task.dipendente_id`;
  - `fasi.progetto_id`;
  - `sottotask.task_id`, `sottotask.dipendente_id`;
  - `dipendenza_task.task_successore_id`, anche per la cascata dal task;
  - `assegnazioni.dipendente_id`.
- Oggi esistono solo quelli su `blocchi_ore` e su sal/bollettino.
- Correzione: una migration scritta a mano.

**5.4 — Liste senza limite.** · serio
- Dove:
  - `tasks.py:117-129`: al manager arrivano tutti i task, anche chiusi;
  - `get_segnalazioni`;
  - export Excel con `stato=all` costruito in memoria con pandas e openpyxl;
  - lato client:
    - Risorse: tre liste da 500 righe, `fetchTasks()` di tutta l'azienda e `progetti.find` dentro un map, alla r.95;
    - AggiungiRiga (135): scarica tutti i task aziendali per tenerne i propri;
    - Archivio (35);
    - Wizard, Gantt e CantiereDettaglio chiamano `/api/dipendenti`, un aggregato pesante, solo per riempire una tendina.
- Correzione: paginazione, un endpoint dei task «miei», e un endpoint leggero id/nome per le tendine.

**5.5 — Endpoint inutilizzato e pesante.** · minore
- Dove: `gantt.py:188-264`: GET /api/gantt carica tutti i task senza filtro di stato, e nessuno lo chiama.
- Correzione: toglierlo (regola 2).

**5.6 — `_note_ereditate` riduce in Python tutte le note storiche.** · minore
- Dove: `data_db_impl.py:1143-1156`.
- Correzione: `DISTINCT ON (unità) ORDER BY settimana DESC, id DESC`.

## 6. Tempo

**6.1 — Tre orologi diversi nello stesso database.** · serio (già in BACKLOG)
- Dove:
  - `default=datetime.utcnow` nei modelli (`models.py` da 352 a 1335);
  - `data_compilazione = datetime.utcnow()` (`data_db_impl.py:2866`, `2913`);
  - `ultimo_login` con utcnow (`auth_routes.py:139`);
  - `server_default=func.now()` su `DateTime` senza fuso (`models.py:1367`, `1391`): fuso della sessione Postgres;
  - `get_oggi()` = `datetime.now()` naive, fuso del server.
- In produzione: nella stessa tabella convivono UTC e ora locale, con 1-2 ore di scarto. Le segnalazioni (2476) e l'ora degli snapshot SAL (`SezioneSAL.jsx:49-54`) si vedono sfasate. `utcnow` è deprecato da Python 3.12.
- Correzione: un solo orologio, `get_oggi()` con il fuso preso da configurazione (`zoneinfo`), e colonne `timestamptz`.

**6.2 — `date.today()` e `datetime.now()` fuori da `get_oggi`.** · serio se il server non è in ora italiana (già in BACKLOG)
- Dove: `data_db_impl.py:153`, `1345` (`_lunedi`), `1448`, `2000`; `consuntivi.py:373`, `376`, `725`; `progetti.py:480`, `651`, `798`; `gantt.py:991`.
- In produzione: con Windows Server in UTC, fra mezzanotte e l'una del lunedì italiano la «settimana corrente» è ancora la precedente, e i blocchi di oggi risultano «nel futuro» (`consuntivi.py:735`).
- Correzione: tutto attraverso `get_oggi()`.

**6.3 — Il frontend conta male i giorni lavorativi attorno al cambio d'ora.** · serio
- Dove: `frontend/src/utils/festivita.js:105-106` e `125-126`: `new Date('YYYY-MM-DD')` è la mezzanotte UTC, e il cursore avanza in ora locale.
- In produzione: un intervallo che attraversa la fine dell'ora legale perde l'ultimo giorno. Per esempio 01/10–30/10/2026 non conta il 30. La saturazione mostrata nella modale task (`SezioneFasiTask.jsx:536-548`) risulta gonfiata e può far scattare a torto la conferma «oltre 125%».
- Correzione: iterare sulle stringhe ISO con `Date.UTC` e `getUTCDay`.

**6.4 — Date di oggi da `toISOString` e confronti con la mezzanotte UTC.** · minore (già in BACKLOG)
- Dove:
  - `SezioneFasiTask.jsx:846`, `848`: data minima «ieri» fra le 0 e le 2;
  - `ElencoDettaglio.jsx:72-74`, `95-97`: una scadenza di oggi risulta «superata»;
  - `TimelineBars.jsx`: linea di oggi.
- Correzione: `isoLocale(new Date())`, che c'è già in `ganttSvg.js`.

## 7. Sicurezza

**7.1 — /docs, /redoc e /openapi.json aperti.** · **bloccante** (già in BACKLOG)
- Dove: `main.py:55`: `FastAPI(...)` senza `docs_url`, `redoc_url` e `openapi_url`.
- In produzione: lo schema completo dell'API è pubblico. È contro DECISIONI.md e contro la regola di sicurezza di CLAUDE.md.
- Correzione: impostare i tre URL a None quando una variabile d'ambiente indica la produzione.

**7.2 — Il seed si può lanciare su un database di produzione e crea account con password note.** · **bloccante** (in parte in BACKLOG)
- Dove: `seed.py:66-72`. La guardia controlla soltanto che `dipendenti` sia vuota, e `create_tables()` (`create_all`) viene eseguito prima della guardia. Le righe 594-618 creano 4 account, due dei quali manager, con `admin123` e `user123`.
- In produzione: una prima installazione ha `dipendenti` vuota dopo `alembic upgrade`. Il seed passa, carica dati sintetici e apre due account manager con password pubbliche. Se viene lanciato prima di alembic, crea tabelle senza `alembic_version`, e la `upgrade` successiva fallisce.
- Correzione: rifiutare l'esecuzione senza un flag esplicito, o quando l'ambiente è di produzione; togliere `create_all`.

**7.3 — Chi lascia l'azienda continua ad accedere, e gli account non si gestiscono dall'applicazione.** · **bloccante**
- Dove:
  - `configurazione.py:592`: «elimina dipendente» mette `attivo=False` solo sul Dipendente.
  - `deps.py:57`: `get_current_user` controlla solo `Utente.attivo`.
  - Non esistono endpoint né script per creare utenti, disattivarli o cambiare password: gli unici `Utente(` sono in `seed.py:595-613`.
- In produzione:
  - la persona disattivata fa login e salva consuntivi (`consuntivi.py:715-762`), e nessuno può revocarle l'accesso senza SQL a mano;
  - il primo utente reale si crea solo con SQL e un hash Argon2 generato fuori dall'applicazione;
  - nessuno può cambiare la propria password.
- Correzione:
  - disattivare il Dipendente disattiva anche l'Utente, oppure `get_current_user` respinge chi ha il dipendente inattivo;
  - uno script `crea_utente` con la password chiesta a prompt;
  - un endpoint per cambiare la password.

**7.4 — Rate limit del login per IP, dietro IIS.** · **bloccante** se IIS non inoltra l'IP del client; da verificare sul server
- Dove:
  - `auth_routes.py:20`, `108`: `5/minute` con chiave `get_remote_address`, cioè `request.client.host`;
  - `main.py:104`: uvicorn con i default, che si fida di X-Forwarded-For solo da 127.0.0.1.
- In produzione: se ARR si collega via `::1`, o non scrive X-Forwarded-For, tutta l'azienda ha lo stesso IP. Allora:
  - bastano 5 login al minuto (l'apertura degli uffici) per dare 429 a tutti;
  - chiunque, con 5 richieste al minuto, blocca il login di tutti;
  - con più worker il limite si moltiplica, perché sta in memoria.
- Correzione: uvicorn con `--proxy-headers --forwarded-allow-ips=<IP di IIS>`, ARR con l'IP del client in X-Forwarded-For, storage del limiter condiviso.

**7.5 — Un utente senza dipendente collegato passa i controlli «è il PM?».** · serio; bloccante se esistono utenti non manager senza `dipendente_id`
- Dove: `Utente.dipendente_id` è nullable (`models.py:465`), quindi `None == None` passa:
  - `sal.py:41`: `current_user.dipendente_id != meta["pm_id"]`, riusato da `bollettino.py:45`, `70`, `81`;
  - `attivita_interne.py:284`;
  - `data_db_impl.py:548-561` (`progetti_attivi_visibili`, chiamato da `home.py:86`, `265-266`);
  - `tasks.py:123-124`.
- In produzione: quell'utente legge e crea SAL e bollettini, che contengono `costo_ora` per persona, di ogni progetto senza PM. Vede i progetti e i task non assegnati di tutti, e cancella le attività interne senza assegnatario.
- Correzione: se `dipendente_id is None`, negare o restituire una lista vuota, prima di ogni confronto.

**7.6 — Il PM vede il costo orario dei colleghi nel bollettino.** · serio, da decidere
- Dove: `bollettino.py:37-82`; `dettaglio_persone.costo_ora` in `data_db_impl.py:3452`.
- In produzione: un PM con `ruolo_app="user"` legge i costi orari, che AUTH_MODEL riserva alla direzione.
- Correzione: `require_manager` sul bollettino, oppure togliere `costo_ora` dalla serializzazione per chi non è manager.

**7.7 — Visibilità del ruolo user più larga di AUTH_MODEL.** · serio, da decidere
- Dove: `attivita_interne.py:134` e `216-223` (attività interne e ore contrattuali di tutti i colleghi); `home.py:80` e `197` (con un solo task su un progetto, se ne vedono ore vendute e consumate e la saturazione del team).
- In produzione: è contro lo scenario «vede solo se stesso».
- Correzione: filtrare per `dipendente_id` chi non è manager né PM.

**7.8 — Il logout non invalida il token.** · serio
- Dove: `auth_routes.py:173` cancella solo il cookie. Il JWT vale 8 ore (`auth.py:18`, `56`) e non ha né `jti` né versione.
- In produzione: un cookie copiato resta valido dopo il logout e dopo un cambio di password. Il ruolo e `attivo` invece si rileggono dal DB a ogni richiesta.
- Correzione: una colonna `token_version` su `utenti`, scritta nel JWT e verificata in `get_current_user`.

**7.9 — `COOKIE_SECURE` falso per default, e `.env.example` incompleto.** · serio (il default è già in BACKLOG)
- Dove: `auth_routes.py:49`. `.env.example` non elenca `SECRET_KEY`, `COOKIE_SECURE`, `COOKIE_SAMESITE`, `JWT_*` né `GEMINI_API_KEY`, anche se il README lo definisce «l'elenco completo».
- In produzione: chi parte dall'esempio manda il cookie di sessione anche su HTTP.
- Correzione: Secure attivo per default, o obbligatorio in produzione; completare `.env.example`.

**7.10 — Backend in ascolto su `0.0.0.0`.** · serio
- Dove: `main.py:104`.
- In produzione: se il firewall di Windows lascia aperta la porta, il backend si raggiunge direttamente, senza HTTPS e senza passare da IIS.
- Correzione: l'host da variabile d'ambiente, `127.0.0.1` in produzione.

**7.11 — `modifica_task` fa setattr su qualunque attributo esistente.** · serio
- Dove: `data_db_impl.py:2446-2450`.
- In produzione: oggi i chiamanti passano campi fissi, ma la whitelist dipende da loro, contro la regola di sicurezza.
- Correzione: un insieme esplicito di campi ammessi dentro la funzione.

**7.12 — Login: enumerazione delle email e chiavi incoerenti.** · minore
- Dove:
  - `auth_routes.py:126-131`: Argon2 gira solo se l'email esiste, quindi un'email inesistente risponde subito;
  - la chiave del limite è in minuscolo (r.120), la query no (r.126), e la UNIQUE su `Utente.email` distingue maiuscole e minuscole (`models.py:460`);
  - `_email_attempts` (r.39) non perde mai chiavi, quindi la memoria cresce.
- Correzione: verifica su un hash fittizio, email normalizzata in un punto solo, pulizia del dizionario.

**7.13 — Varie di sicurezza.** · minore
- Due istanze di Limiter (`auth_routes.py:20`, `main.py:58`, già in BACKLOG).
- Nessuna lunghezza minima per `SECRET_KEY` (`auth.py:21`).
- `python models.py` stampa `DATABASE_URL` con la password (`models.py:1417`).
- `console.log('DEBUG …', progetto)` a ogni render (`AggiungiTaskModal.jsx:28`).
- CORS: senza `GANTT_ORIGINI_CORS` resta ammesso `localhost:3100`, da azzerare in produzione.
- `Content-Disposition` dell'Excel con `progetto_id` non ripulito (`gantt.py:991-995`).

## 8. Configurazione

**8.1 — Soglie e ore cablate, e in copie diverse.** · serio (in parte già in BACKLOG)
- Saturazione 90/100/125/150: `Risorse.jsx:17-28`, `135`, `217` (0,85), `279-282`; `SezioneFasiTask.jsx:566-577`, `620-624`.
- Erosione 15/5: `Economia.jsx:19-20`, `257`.
- Gauge 70/90: `Economia.jsx:413`, `421`.
- Budget 90/70: `VistaManagement.jsx:181`.
- 30/14/0,5: `ElencoDettaglio.jsx:65`, `76`, `88`, `99`.
- 8 h × 5 giorni: `SezioneFasiTask.jsx:540`.
- 40 h: `configurazione.py:165`, `data_db_impl.py:399`, `411`, `models.py:521`, `Configurazione.jsx:230`, `240`, `247`.
- 5 giorni: `ConsuntivazioneOre.jsx:330`, `soglie.js:87`.
- Stati dei task scritti come stringhe nelle route: `consuntivi.py:547`, `dipendenti.py:127`, `risorse.py:188`.
- In produzione: cambiarle richiede un rilascio, e ogni pagina può dire una cosa diversa.
- Correzione: parametri in DB o in configurazione, letti da un solo punto.

**8.2 — Festività solo nel frontend, e italiane cablate.** · serio (già in BACKLOG)
- Dove: `festivita.js:69-86`.
- In produzione: il backend non conosce le festività, e nella stessa modale la saturazione calcolata dal server (`PannelloSaturazione`) e quella calcolata dal client (`IndicatoreCapacita`) non coincidono. Manca il patrono.
- Correzione: un calendario in DB, usato dal backend.

**8.3 — Valori di IMC nel codice.** · minore (regola 5)
- `WizardCreazioneProgetto.jsx:340`: nomi di clienti reali nel placeholder.
- `WizardCreazioneProgetto.jsx:347`: «progetto sviluppato da IMC».
- `App.jsx:62`, `66`: alt «IMC-Group».
- `attivita_interne.py:122`: famiglie dedotte dai prefissi PC/PI/PN degli id del seed.
- `gantt.py`: mappa `colori_progetto` con nomi di progetto reali, se ancora presente dopo le modifiche in corso.
- Nomi di persone reali nei commenti: `fasi.py:52`, `gantt.py:57`, `70`, `99`.
- Correzione: spostarli in configurazione, o toglierli.

**8.4 — Pool di connessioni non configurabile.** · vedi 10.2

## 9. Frontend

**9.1 — Pulsanti che inviano due volte.** · serio
- Dove:
  - `Configurazione.jsx:75`/`78`, `132`/`135`, `181`/`184` (aggiunta di ruolo, competenza e fase, con Invio o con clic), `347` (salva dipendente);
  - `SezioneSAL.jsx:447`: l'Invio chiama `consolida()` senza guardare `occupato`;
  - `SezioneFasiTask.jsx:470`, `474`, `486` (`salvando={false}` a 420);
  - `BannerStato.jsx:84-93`.
- In produzione: due dipendenti, due ruoli, due fotografie SAL immutabili.
- Correzione: uno stato `salvando` che disabilita pulsante e Invio.

**9.2 — Fetch grezzi senza controllo di `res.ok` né gestione del 401.** · serio (Configurazione già in BACKLOG)
- Dove:
  - `Configurazione.jsx:16-19`, `26-30`, `36-40`, `45`: su un errore la lista diventa `[]` («Nessun ruolo censito»), una cancellazione fallita non dà nessun messaggio, e una pagina d'errore HTML di IIS fa fallire `res.json()`;
  - `VistaManagement.jsx:54-55`: su 401 o 500, `{detail}` finisce in `setProgetti`, e `progetti.filter` (r.71) **fa crollare la pagina**.
- Correzione: tutto attraverso `apiFetch`.

**9.3 — Nessun ErrorBoundary.** · serio
- Dove: `main.jsx` e `App.jsx`.
- In produzione: un'eccezione in render, per esempio quella del 9.2, `carico_corrente.toFixed` su null (`Risorse.jsx:292`, `337`) o `dp.ore.toFixed` (`Economia.jsx:358`), lascia l'app tutta bianca, menu e Logout compresi.
- Correzione: un ErrorBoundary attorno a `<Routes>`.

**9.4 — Sessione scaduta durante la compilazione delle ore.** · serio
- Dove: `api.js:68-78` (redirect a /login su 401), sessione di 8 ore fisse.
- In produzione: chi compila a lungo e salva dopo la scadenza viene mandato al login. Le modifiche non salvate vanno perse, se conferma l'avviso di `beforeunload`.
- Correzione: con modifiche pendenti, un avviso «sessione scaduta, accedi in un'altra scheda» invece del redirect.

**9.5 — Errori mostrati come «nessun dato».** · serio
- Dove:
  - `Gantt.jsx:87-99`: fetch senza catch e senza annullamento. Al cambio di filtro una risposta vecchia può sovrascrivere la nuova, e l'export PDF/PNG disegna i dati del filtro precedente. Mentre carica dice «Nessuna fase da visualizzare».
  - `Risorse.jsx:51-53`: `Promise.all` senza catch (già in BACKLOG).
  - `Home.jsx:436`: «0/0 compilate · Nessun task assegnato» quando la chiamata è fallita.
  - `Economia.jsx:95`: `.catch(() => [])`.
  - `WizardCreazioneProgetto.jsx:96-97` e `AggiungiTaskModal.jsx:38`: tendine vuote senza spiegazione; senza aziende il passo 1 del Wizard non diventa mai valido.
  - `SezioneSAL.jsx:466`.
  - `AttivitaInterne.jsx:78-84`: l'errore resta dopo un caricamento riuscito.
  - `ConsuntivazioneOre.jsx:592`, `725`: cambiando settimana la griglia vecchia resta modificabile, e le modifiche fatte intanto vengono azzerate in silenzio.
- In produzione: l'utente scambia un guasto per assenza di dati e prende decisioni su numeri vuoti.
- Correzione: stati distinti di caricamento ed errore, e annullamento delle richieste superate.

**9.6 — AggiungiRiga ripete la richiesta all'infinito se fallisce.** · serio
- Dove: `AggiungiRiga.jsx:131-139`: l'effect dipende da `[aperto, tasks, caricamento]`. Su errore `tasks` resta `null` e `caricamento` torna `false`, quindi l'effect riparte.
- In produzione: un ciclo di richieste continuo finché il pannello resta aperto, moltiplicato per gli utenti.
- Correzione: non riprovare se `errore` è valorizzato.

**9.7 — La Home manda PM e dipendenti su una pagina riservata ai manager.** · serio
- Dove: `Home.jsx:455`, `531`, `537` portano a `/elenco/:id`, che `App.jsx:218-220` protegge con RequireManager.
- In produzione: ogni clic su un progetto mostra il 403.
- Correzione: elemento non cliccabile per chi non è manager, oppure la rotta aperta ai PM con controllo lato server.

**9.8 — Il frontend ricalcola formule.** · serio (regola 3, in parte già in BACKLOG)
- Dove:
  - `Economia.jsx:112-121`: euro sommati in float;
  - `Economia.jsx:136-149`: avanzamento, che con `data_inizio` null parte dal 1970 e segna 100%;
  - `calcolaCriticita` in due versioni diverse (`CantiereDettaglio.jsx:84-146`, `ElencoDettaglio.jsx:56-125`);
  - `Risorse.jsx:89-104`: carico spalmato su tutti i giorni di calendario, diverso dalla heatmap del backend, e r.81, che conta i task Annullati;
  - regole di cascata replicate (`SezioneFasiTask.jsx:404-409`).
- In produzione: la stessa persona nella stessa settimana ha due numeri diversi su due pagine.
- Correzione: un solo calcolo, nel backend.

**9.9 — `apiFetch` senza timeout, e messaggi del server scartati.** · minore
- Dove: `api.js:59-65`: «Salvataggio…» resta appeso finché il proxy non risponde. `api.js:68-83`: una password sbagliata mostra «Non autenticato» e non «Credenziali non valide», e il `detail` del 403 va perso.
- Correzione: `AbortController` con un timeout, e il `detail` del server mostrato all'utente.

**9.10 — `alert()` come unico canale d'errore, cancellazioni senza conferma.** · minore
- Dove:
  - alert: `CantiereDettaglio.jsx:258`, `264`, `270`, `286`, `293`, `318`; `Configurazione.jsx:248`; `Gantt.jsx:136`;
  - cancellazioni senza conferma: `SottotaskManager.jsx:279`; «Rimuovi» in Configurazione (99, 145, 197).

## 10. Altro, per chi gestirà la produzione

**10.1 — Dati consuntivati cancellabili riportando un progetto a «Bozza».** · **bloccante**
- Dove:
  - `progetti.py:928-956`: il PATCH accetta qualunque stato ammesso; la docstring delega le transizioni al frontend, contro la regola 3;
  - DELETE (`progetti.py:959-981`) e PUT /completo (`663`, `682-687`) controllano solo che lo stato sia «Bozza»;
  - cascata ORM Progetto → Fase → Task (`models.py:627`, `629`, `776`), poi `blocchi_ore.task_id ON DELETE CASCADE` (`models.py:1218`).
- In produzione: due chiamate di un manager, PATCH a «Bozza» e poi DELETE o PUT /completo, cancellano **tutte le ore consuntivate** del progetto, senza conferma e senza traccia.
- Correzione:
  - transizioni di stato nel servizio, senza ritorno a «Bozza»;
  - prima di cancellare, una guardia che conti `blocchi_ore` e `consuntivi`.

**10.2 — Pool di connessioni dell'engine con i valori di default.** · serio
- Dove: `models.py:65`: `create_engine(DATABASE_URL, echo=False)`.
- In produzione:
  - il pool di default è di 5 connessioni più 10 di overflow, contro i circa 40 thread delle route sincrone;
  - `get_current_user` tiene una connessione per tutta la richiesta (`deps.py:35`, `56`), e le funzioni dati ne aprono altre, anche in loop (5.1). Sotto carico: attesa di 30 s e 500;
  - senza `pool_pre_ping`, dopo un riavvio di Postgres o la caduta delle connessioni inattive, la prima richiesta su ogni connessione morta dà 500;
  - con più worker il pool si moltiplica contro `max_connections`.
- Correzione: `pool_pre_ping=True`, e `pool_size`, `max_overflow`, `pool_recycle` e `statement_timeout` da variabili d'ambiente; la sessione di `get_current_user` chiusa appena letto l'utente.

**10.3 — Regressione nelle modifiche non committate di `progetti.py`.** · serio, lavoro in corso
- Dove: `progetti.py:948-950`: `_valida_societa` gira su **ogni** PATCH, ma `ProgettoUpdate` (219-239) non ha `azienda_id`, quindi `_valore_risultante` usa il valore attuale.
- In produzione: un progetto ordinario o bando con `azienda_id` NULL diventa immodificabile. Qualunque PATCH, anche il solo cambio di stato, risponde 422, e la società non si può assegnare via PATCH.
- Non ho verificato se esistono progetti così.
- Correzione: validare solo se `tipologia` o `azienda_id` sono nel body, e aggiungere `azienda_id` al DTO.

**10.4 — Nessun logging.** · serio (già in SECURITY_BACKLOG)
- Dove: nel backend non c'è nessun `logging` o `getLogger`, solo `print`, e non ci sono handler globali delle eccezioni.
- In produzione: sotto un servizio Windows gli errori vanno solo dove è rediretto stderr. Dei login falliti non resta traccia. Senza log i 500 non si diagnosticano.
- Correzione: `logging` su file con rotazione, più un handler per `Exception` che registra il dettaglio e risponde con un messaggio generico.

**10.5 — Installazione su Windows non documentata, README sbagliato.** · serio (in parte già in BACKLOG)
- Dove: `README.md:340` scrive `JWT_SECRET`, ma `auth.py:16` legge `SECRET_KEY`: seguendo il README il backend non parte. Le istruzioni sono solo Linux (327-374), e `data.py:73`/`90` suggerisce `sudo service postgresql start`.
- In produzione:
  - `data.py` verifica Postgres all'import, senza ritentare: se il servizio del backend parte prima di Postgres, il processo muore;
  - in `frontend/public` non c'è un `web.config` per la riscrittura degli URL, quindi con BrowserRouter un refresh su `/consuntivazione` dà 404 di IIS (non verificato su IIS).
- Correzione: una sezione Windows (servizio, dipendenza da PostgreSQL, riavvio automatico, ARR, riscrittura SPA) e README allineato al codice.

**10.6 — Il carico settimanale conta anche i task Annullati ed Eliminati.** · serio
- Dove: `data_db_impl.py:1295` esclude solo «Completato» e «Sospeso».
- In produzione: Risorse, Home e saturazione mostrano persone occupate da task cancellati.
- Correzione: escludere anche «Annullato» ed «Eliminato», salvo una ragione che oggi la docstring non dà.

**10.7 — Soldi in float.** · serio (regola 7)
- Dove:
  - colonne `costo_ora` (`models.py:522`) e `valore_contratto` (592);
  - calcoli e `round()` sparsi in `margini_economia` (`data_db_impl.py:3357-3359`, `3373-3375`, `3415-3418`);
  - DTO float (`progetti.py:193`, `231`, `340`; `configurazione.py:166`);
  - ore vendute sommate in float e confrontate con `!=` (`progetti.py:461`, `636`), che può dare un 422 ingiustificato.
- In produzione: centesimi diversi fra progetto, totale e bollettino congelato.
- Correzione: `Numeric`/`Decimal` e un solo arrotondamento, `ROUND_HALF_UP`.

**10.8 — Task aggiunti a progetti chiusi.** · serio
- Dove: `tasks.py:216-323`: il POST singolo non controlla lo stato del progetto, a differenza di task-multipli (`progetti.py:811`).
- Correzione: lo stesso controllo su `STATI_PROGETTO_IN_PIANO`.

**10.9 — Il PM riceve 403 da un endpoint pensato per lui.** · minore
- Dove: `risorse.py:130`: `saturazione-periodo` è `require_manager`, ma la docstring (134) dice che lo usa il PM nel Cantiere.

**10.10 — Ruoli e competenze eliminati non si possono ricreare.** · minore
- Dove: `configurazione.py:236`, `296`: il controllo dei duplicati conta anche gli inattivi, che però non compaiono in lista.
- Correzione: riattivare quello esistente.

**10.11 — Una fase con soli task eliminati non si cancella mai.** · minore
- Dove: `fasi.py:391` conta anche i task «Eliminato».

**10.12 — Script di manutenzione.** · minore (in parte già in BACKLOG)
- `add_p010.py` scrive senza guardie uno stato che non esiste più.
- `_snapshot_dipendenze.py:19` usa `/tmp`, e alle righe 50 e 64 apre file senza encoding.
- `_snapshot_dipendenze.py` e `diagnostico_d1.py` sono tracciati benché `.gitignore` li escluda.
- `test_solidita.sh` è bash, punta alla porta 8000 e non si autentica.
- `scripts/audit_permessi.py:161-165` classifica `/api/salute` come MISSING ed esce con 1.
- `alembic/env.py:46`: senza `DATABASE_URL` dà un errore oscuro.

**10.13 — Ordinamenti senza id come spareggio.** · minore (regola 6)
- Dove:
  - `data_db_impl.py:698`, `1517`, `2462`, `3051`, `3436`;
  - `configurazione.py:223`, `286`, `338`, `353`, `609`, `670`, `674`;
  - nessun ORDER BY in `dipendenti.py:102-107`, `risorse.py:100`, `tasks.py:129`, `gantt.py:203`;
  - `fasi.py:417`, `gantt.py:525`, `consuntivi.py:570`, `attivita_interne.py:228`.

**10.14 — Client Gemini senza timeout.** · minore (già in BACKLOG)
- Dove: `gemini_client.py:92`. Oggi nessun endpoint lo usa.

**10.15 — Documenti non veri.** · minore
- SECURITY_BACKLOG.md:122 e 155 parlano di bcrypt e passlib, ma il codice usa Argon2. SECURITY_BACKLOG.md:192 dà Alembic come futuro, ma è già in uso.
- Le tabelle degli endpoint nelle docstring di `progetti.py:19-26`, `tasks.py:14-19` e `fasi.py:19-39` non corrispondono al codice.

---

## Riepilogo per gravità

| Gravità | N. | Casi |
|---|---|---|
| **Bloccante** | 7 | 2.1 il PATCH del dipendente azzera la sede e sovrascrive i campi · 3.1 id dei task con `max()` su stringa, fermo dopo T1000 · 7.1 /docs e /openapi.json aperti · 7.2 il seed su un DB di produzione crea account manager con password note · 7.3 chi lascia l'azienda conserva l'accesso, account non gestibili · 7.4 rate limit del login sull'IP del proxy (da verificare su IIS) · 10.1 ore consuntivate cancellabili riportando il progetto a Bozza |
| **Serio** | 46 | 1.1 1.2 1.3 · 2.2 2.3 2.4 2.5 · 3.2 3.3 3.4 3.5 · 4.1 4.2 4.3 4.4 · 5.1 5.2 5.3 5.4 · 6.1 6.2 6.3 · 7.5 7.6 7.7 7.8 7.9 7.10 7.11 · 8.1 8.2 · 9.1 9.2 9.3 9.4 9.5 9.6 9.7 9.8 · 10.2 10.3 10.4 10.5 10.6 10.7 10.8 |
| **Minore** | 19 | 1.4 · 2.6 · 3.6 · 4.5 · 5.5 5.6 · 6.4 · 7.12 7.13 · 8.3 · 9.9 9.10 · 10.9 10.10 10.11 10.12 10.13 10.14 10.15 |

Il conteggio è per voce: alcune voci raggruppano più casi dello stesso schema. La 8.4 rimanda alla 10.2 e non si conta.

## Cosa questo audit non ha verificato

- Comportamento a runtime: niente server, test, browser né query avviati.
- I numeri reali di query e la conferma con `EXPLAIN ANALYZE` del 5.2.
- I dati: se esistono utenti non manager senza `dipendente_id` (7.5), progetti ordinari senza società (10.3), quanti id di task mancano a T999 (3.1).
- La configurazione reale di IIS e ARR (header inoltrati, IPv4 o IPv6, riscrittura SPA), il numero di worker, il fuso del server Windows e di Postgres.
- La cartella `frontend/dist` e il contenuto delle migration oltre a indici e vincoli.
