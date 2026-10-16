# Piano della rifondazione dello schema (blocco B)

*Passo B-piano, sola lettura. Fotografia al commit `2a5758d` (baseline unica, 16/10/2026). Come INVENTARIO.md, non si aggiorna: lo stato dei passi sta in PIANO.md.*

**Scelte già prese**
- Si modifica `0001_baseline.py` invece di aggiungere migration (DECISIONI §10).
- Ogni passo lascia l'applicazione funzionante e i test verdi.
- Fonti: `RICOGNIZIONE_ID.md` per gli usi degli id; `AUDIT_PRODUZIONE.md` per i casi 3.1, 3.2, 5.3, 6.1, 8.3, 10.1, 10.7.

---

## 0. Cosa vale per tutti i passi

**Ogni passo cambia insieme tre cose**: `models.py`, `0001_baseline.py` e gantt_db, che va ricostruito (schema vuoto, `alembic upgrade head`, `seed.py`).
- Il passo A ha dimostrato una volta che baseline e modello coincidono, ma lo strumento di quel confronto non è nel repository.
- Da qui in avanti la baseline si scrive a mano, accanto al modello, per una dozzina di volte. Il rischio principale del blocco è che modello e baseline si separino senza che nessuno se ne accorga, come è già successo con i CHECK sugli stati (`models.py:257-269`).
- Per questo il primo passo è la rete di sicurezza (B0), e l'ordine richiesto viene dopo.

**Verifica comune**, oltre a quella specifica di ogni passo:
1. Test di allineamento del passo B0: catalogo della baseline uguale al catalogo di `create_all`.
2. `alembic check` senza operazioni.
3. `npm run build` senza avvisi nuovi e `npm run test:disegno`.
4. pytest verde, contando i test prima e dopo.
5. Ricostruzione di gantt_db con l'impronta dei dipendenti di CLAUDE.md calcolata prima e dopo.
   - La nuova impronta non contiene id né date tecniche, quindi **deve restare identica in tutti i passi**, compresi quelli sugli id.
   - L'unica eccezione prevista è il B5: vedi lì.
6. Suite e2e completa, spec per spec, dopo il controllo delle porte.
7. Elenco degli endpoint prima e dopo.

**Lavoro in parallelo.** gantt_db è uno solo per tutta la macchina, e ogni passo lo ricostruisce. Classifico così:
- **libero**: nessuna ricostruzione, file nuovi o isolati;
- **finestra**: altro lavoro può proseguire su file diversi, ma durante la ricostruzione di gantt_db e il giro e2e nessun'altra sessione deve avere server o e2e accesi. Dopo il commit l'altra sessione riavvia il backend, perché il modello è cambiato;
- **repo fermo**: il passo tocca abbastanza file (route, servizio, frontend, seed, e2e) da rendere un merge con altro lavoro più costoso del lavoro stesso.

`models.py`, `0001_baseline.py` e `seed.py` li toccano tutti i passi dal B1 in poi: **i passi B sono sempre in serie fra loro**.

---

## 1. La sequenza

| Passo | Contenuto | Tocca il codice applicativo? | Parallelo |
|---|---|---|---|
| B0 | Rete di sicurezza: test di allineamento e script di ricostruzione | no | libero |
| B1 | Naming convention dei vincoli | solo commenti | finestra |
| B2 | Indici mancanti | no | finestra |
| B3 | Tabelle e colonne morte via | DTO e serializzatori | finestra |
| B4 | Ore che nessuna cascata può cancellare | servizio progetti e sottotask | finestra |
| B5 | Soldi e ore in Numeric, a calcoli invariati | no (`asdecimal=False`) | finestra |
| B6 | Date e ore con fuso (`timestamptz`) | sì, chi scrive i timestamp e chi li mostra | finestra |
| B7 | API e frontend indifferenti al tipo degli id | sì, ma a schema invariato | repo fermo sul frontend |
| B8 | Fixture e2e senza id cablati | solo e2e | libero |
| B9 | Famiglie delle attività interne in tabella | sì | finestra |
| B10 | Progetti: id numerico più codice | tutto | **repo fermo** |
| B11 | Dipendenti: id numerico | tutto | **repo fermo** |
| B12 | Task: id numerico | tutto | **repo fermo** |
| B13 | Segnalazioni, pulizia finale, documenti | poco | finestra |

### Dove mi discosto dal criterio richiesto, e perché

1. **B0 prima di tutto.** Senza un confronto automatico, ogni passo dovrebbe rifare a mano la verifica del passo A, e prima o poi la salterebbe.
2. **B4 (ore protette) prima dei tipi.** Tocca un po' di codice, ma chiude un bloccante dell'audit (10.1) che distrugge dati veri, ed è indipendente da tutto il resto. Rimandarlo dopo i tipi non rende nulla più sicuro.
3. **B7 e B8 prima degli id.** Non cambiano lo schema, ma tolgono dal frontend e dagli e2e la dipendenza dalla forma degli id (RICOGNIZIONE §1.3.2 e §1.7). Fatti prima, i passi B10–B12 restano sullo schema e sul backend. Fatti insieme, ogni passo sugli id sarebbe tre passi in uno.
4. **B9 (famiglie) prima degli id.** Toglie l'ultimo significato del prefisso dell'id (`attivita_interne.py:117-126`). Fatto dopo, B10 dovrebbe tenere in vita una regola che sta per sparire.
5. **Fra gli id, progetti, poi dipendenti, poi task.**
   - **Progetti per primi:** hanno meno riferimenti (6 FK), una sequenza esiste già, e il cambio introduce il codice, cioè la parte visibile all'utente.
   - **Task per ultimi:** hanno più riferimenti (sei tabelle, una FK composta, la vista, gli snapshot JSONB e la validazione dei consuntivi).
   - Il bloccante 3.1 (T1000) si chiude con B12. Senza un'installazione vera non ha urgenza; se la si vuole, B12 non dipende da B10 e B11 e può venire subito dopo B9.

---

## 2. I passi

### B0 — Rete di sicurezza

**Perché qui.** Ogni passo successivo modifica a mano modello e baseline insieme: serve un controllo che fallisca da solo se i due divergono.

**Cosa cambia**
- **Test:** `backend/tests/test_schema_allineato.py`, sempre su gantt_test. Costruisce lo schema in due modi, con `alembic upgrade head` e con `Base.metadata.create_all`, in due schemi separati (`search_path` e `schema_translate_map`), poi confronta un'interrogazione normalizzata del catalogo:
  - colonne con tipo, nullabilità e default;
  - `pg_get_constraintdef` per nome;
  - indici;
  - `pg_get_viewdef`;
  - sequenze e identity.
- L'ordine delle colonne si esclude dal confronto: oggi la baseline lo tiene uguale a quello della vecchia catena, e i passi successivi non devono doverlo preservare.
- **Script:** `backend/scripts/ricostruisci_db.py`, Python e pathlib, senza psql. Prevede:
  - una guardia sul nome del database (una lista ammessa: gantt_db, gantt_test);
  - una conferma esplicita;
  - l'impronta dei dipendenti calcolata prima e dopo;
  - le stesse istruzioni che oggi stanno dentro `conftest.py:113-122`, che passa a chiamare la stessa funzione: una sola procedura, non due copie.
- **Baseline, modello, seed, frontend:** nessun cambio.

**Verifica**
- il test è verde sullo stato attuale;
- **lo stesso test diventa rosso** se si toglie a mano un CHECK dalla baseline su una copia locale, cioè sa davvero vedere il buco che deve coprire;
- lo script rifiuta un nome di database non ammesso;
- ricostruendo gantt_db l'impronta resta identica e la suite e2e è verde.

**Rischio.** Che due schemi in `gantt_test` non si possano creare con i permessi di `vicacrit`. Va provato per primo. In quel caso serve un secondo database, creato da chi ha i permessi: è una decisione tua (D1).

**Parallelo:** libero. La ricostruzione di gantt_db a fine passo richiede però una finestra.

### B1 — Naming convention dei vincoli

**Perché qui.** Riguarda solo lo schema, e da qui in avanti ogni vincolo nuovo (B2, B4, B9–B12) nasce con un nome prevedibile, senza nomi scelti a mano.

**Cosa cambia**
- **Modello:** `Base = declarative_base(metadata=MetaData(naming_convention=…))` (`models.py:67`). I `name=` espliciti di oggi si tolgono dove la convenzione dà lo stesso risultato. I CHECK tengono un nome breve (`stato_ammessi`), da cui la convenzione ricava `ck_progetti_stato_ammessi`.
- **Baseline:** tutti i nomi di PK, FK, UNIQUE, CHECK e indici secondo la convenzione. Oggi una parte sono nomi di default di Postgres (`task_fase_id_fkey`, `azienda_pkey`) e una parte sono scritti a mano.
- **Backend e frontend:** solo i commenti che citano nomi di vincoli:
  - `routes/gantt.py:493`
  - `routes/sottotask.py:372`
  - `routes/fasi.py:167`
  - `routes/progetti.py:120, 184`
  - `data_db_impl.py:97`
  - `frontend/src/components/cantiere/_costanti.js:30, 36`

  Il codice non confronta mai il nome di un vincolo (verificato con grep).
- **Seed, test:** nessun cambio.

**Verifica:** quella comune, più un'interrogazione su `pg_constraint` in cui nessun nome resta fuori dalla convenzione.

**Parallelo:** finestra.

### B2 — Indici mancanti

**Perché qui.** Solo schema, e la convenzione appena fissata dà loro il nome. Audit 5.3.

**Cosa cambia**
- **Modello e baseline:** indici su:
  - `consuntivi(dipendente_id, settimana)`
  - `task(progetto_id)`, `task(fase_id)`, `task(dipendente_id)`
  - `fasi(progetto_id)`
  - `sottotask(task_id)`, `sottotask(dipendente_id)`
  - `dipendenza_task(task_successore_id)`
  - `consuntivo_sottotask(dipendente_id, settimana)`
  - `blocchi_ore(dipendente_id, giorno)`: da confermare, la UNIQUE comincia già da lì
- `assegnazioni` è esclusa perché sparisce con B3.
- **Codice:** nessun cambio.

**Verifica:** quella comune, più un `EXPLAIN` sulle tre interrogazioni più frequenti (`/consuntivi/me`, la lista dei task di un progetto, la Home) che mostri l'indice usato. Su 18 dipendenti il planner può preferire comunque una scansione sequenziale: in quel caso si riporta il piano con `SET enable_seqscan = off`, a dimostrare che l'indice è utilizzabile.

**Parallelo:** finestra.

### B3 — Tabelle e colonne morte via

**Perché qui.** Tolte prima dei cambi di tipo e di id, non vanno convertite. Ogni colonna tolta qui è una colonna in meno da portare in B5, B6 e B10–B12.

**Cosa cambia** (elenco da BACKLOG, da confermare: D3)
- **Tabelle:** `assegnazioni`, `note_progetto`, `interventi`.
- **Colonne:**
  - `dipendenti.data_assunzione`, `dipendenti.note`;
  - `progetti.giornate_vendute`, `sede`, `scadenza_bando`, `motivo_sospensione`, `lezioni_apprese`, `note`;
  - `fasi.urgenza`;
  - `task.motivo_blocco`, `task.note`.
- **Codice:** non sono morte del tutto. Compaiono ancora in DTO e serializzatori:
  - `progetti.py` (DTO di creazione e PATCH: `sede`, `scadenza_bando`, `motivo_sospensione`, `lezioni_apprese`, `note`, `giornate_vendute`);
  - `data_db_impl.py` (serializzazione);
  - `fasi.urgenza` è letta da `fasi.py`, `gantt.py`, `home.py`, `SezioneSAL.jsx` e `Home.jsx`. Va verificato prima se è davvero morta: il BACKLOG la dà per tale, ma grep la trova viva.

  Il passo comincia con un censimento lettori/scrittori per ogni colonna, e toglie solo quelle con zero lettori nel frontend e zero significato nel servizio.
- **Seed:** togliere ciò che le scrive; `seed_data.json` non le contiene.
- **Test:** quelli che le passano nei payload.

**Verifica:** quella comune, più un grep a fine passo senza più occorrenze dei nomi tolti, commenti esclusi.

**Parallelo:** finestra, con l'avvertenza che `progetti.py` è un file su cui si lavora spesso.

### B4 — Ore che nessuna cascata può cancellare

**Perché qui.** Bloccante 10.1 dell'audit e regola nuova di DECISIONI §3. È indipendente dai tipi, quindi conviene chiuderlo subito.

**Cosa cambia**
- **Modello e baseline:**
  - `blocchi_ore.task_id`, `consuntivi.task_id`, `consuntivo_sottotask.sottotask_id` e la FK composta `blocchi_ore → sottotask` passano da `ON DELETE CASCADE` a `RESTRICT`;
  - la cascata ORM Progetto → Fase → Task (`models.py:627, 629, 776`) resta, perché le bozze senza ore devono potersi cancellare. Se una cascata ORM arriva a un task con ore, il database la ferma.
- **Servizio:** il database da solo darebbe un IntegrityError, cioè un 500. Prima di cancellare o di riportare a Bozza il servizio conta le ore e risponde 409 con il conteggio, nello stile di `elimina_sottotask` (`sottotask.py:640-676`):
  - PATCH dello stato a «Bozza» (`progetti.py:930-959`);
  - DELETE del progetto (`progetti.py:961-984`);
  - PUT `/completo` (cancellazione delle fasi a `progetti.py:682-687`);
  - `elimina_sottotask`, che oggi conta le dichiarazioni ma non i `blocchi_ore` del pezzo.
- La matrice completa delle transizioni di stato resta del blocco D; qui c'è solo la regola delle ore.
- **Frontend:** il 409 deve arrivare all'utente con il suo testo. Verificare `BannerStato` e l'eliminazione delle bozze.
- **Test pytest:** una matrice per ciascuno dei quattro percorsi (con ore, senza ore, caso nullo). Inoltre un test che cancella direttamente un task con ore via SQL e si aspetta che il database rifiuti.

**Verifica:** quella comune, più i test nuovi.

**Parallelo:** finestra.

### B5 — Soldi e ore in Numeric, a calcoli invariati

**Perché qui.** È il primo cambio di tipo, e il più semplice: con `asdecimal=False` (come `blocchi_ore.ore` oggi) il driver continua a restituire float, e il codice non cambia. Audit 10.7, per metà.

**Cosa cambia**
- **Modello e baseline**, con precisioni da confermare (D4):
  - `dipendenti.costo_ora` → `Numeric(10, 2)`;
  - `progetti.valore_contratto` → `Numeric(14, 2)`;
  - `fasi.ore_vendute`, `fasi.ore_pianificate`, `task.ore_pianificate`, `consuntivi.ore_stimate_residue` e `consuntivo_sottotask.ore_stimate_residue` → `Numeric(8, 2)`;
  - `fasi_standard.percentuale_ore` → `Numeric(5, 2)`;
  - in più un CHECK `>= 0` dove ha senso.
- **Calcoli:** **restano in float**. Il passaggio dei calcoli a Decimal (`margini_economia`, gli arrotondamenti in un punto solo) cambia il codice di Economia, e appartiene alla fase 2 «Economia onesta» o al blocco C (D5).
- **Seed:** i valori di `seed_data.json` hanno al massimo una cifra decimale (`costo_ora` ≤ 75.0, `valore_contratto` ≤ 240000.0). Le ore delle fasi però il seed le calcola da percentuali (`seed.py:411-412`), e possono avere più decimali: vanno arrotondate a 2 nel seed, esplicitamente, non dal database in silenzio.

**Verifica**
- Quella comune, più i totali di Economia, Home e Risorse confrontati prima e dopo su gantt_db: devono coincidere al centesimo.
- **Attenzione all'impronta.** Usa `r::text`, e `costo_ora` passa da `45.5` (double) a `45.50` (numeric): l'impronta cambia **per la sola rappresentazione**, con valori identici. La verifica del passo è quindi:
  - l'impronta prima, calcolata con `costo_ora::numeric(10,2)`;
  - deve essere uguale all'impronta dopo;
  - da lì in avanti vale la nuova impronta.

  Va dichiarato nel prompt del passo, perché CLAUDE.md richiede un'autorizzazione esplicita quando l'impronta cambia (D6).

**Parallelo:** finestra.

### B6 — Date e ore con fuso

**Perché qui.** È il secondo cambio di tipo, e tocca anche codice applicativo. Tolte le colonne morte, i `DateTime` da convertire sono quelli che restano. Audit 6.1.

**Cosa cambia**
- **Modello e baseline:**
  - tutti i `DateTime` diventano `DateTime(timezone=True)`, cioè `timestamptz`: `created_at`, `updated_at`, `ultimo_login`, `data_compilazione`, `data_snapshot`;
  - `default=datetime.utcnow` e `onupdate=datetime.utcnow` diventano `server_default=func.now()` e `onupdate=func.now()`. Un solo orologio per i timestamp, quello del database, che salva un istante assoluto (D7).
- I `Date` (giorni, settimane, date di task e progetti) **non cambiano**: sono giorni del calendario, non istanti.
- **Backend:**
  - `data_compilazione = datetime.utcnow()` (`data_db_impl.py:2866, 2913`) e `ultimo_login` (`auth_routes.py:139`) passano a `func.now()`, oppure a un istante con fuso;
  - le serializzazioni producono ISO con l'offset.
- **Frontend:** chi mostra un timestamp (`SezioneSAL.jsx:49-54` `fmtDataOra`, segnalazioni, bollettino) riceve un ISO con l'offset e lo mostra nel fuso del browser. Oggi riceve un valore senza fuso e lo legge come ora locale, sbagliando di una o due ore.
- **Seed:** nessun cambio, perché i default sono nel database.
- **Test:** un pytest che scrive un consuntivo e verifica che `data_compilazione` sia aware e vicina a `now()`; il caso dello snapshot SAL.

Il passo **non** tocca «oggi» (`get_oggi`, `date.today()`): quello è il blocco F, che riguarda i giorni e non gli istanti, e non dipende da questo.

**Verifica:** quella comune, più un controllo visivo dell'ora di un SAL consolidato e di una compilazione, confrontata con l'orologio.

**Parallelo:** finestra.

### B7 — API e frontend indifferenti al tipo degli id

**Perché qui.** Prepara gli id senza cambiare lo schema. Se si sbaglia, si vede con gli id ancora testuali e non dentro un passo che cambia tutto. Corrisponde a RICOGNIZIONE §1.3.2 e §1.2.5.

**Cosa cambia**
- **Frontend:**
  - i `<select>` che contengono id convertono il valore alla lettura (un helper unico, come già fa `AggiungiTaskModal.jsx:145` per la fase);
  - «nessuno» diventa `null`, non `''`: `SezioneFasiTask.jsx:762, 782`, `WizardCreazioneProgetto.jsx:150, 167`, `AggiungiTaskModal.jsx:71`;
  - niente `.trim()` su `pm_id` (`WizardCreazioneProgetto.jsx:122`);
  - i confronti fra un id di URL o di select e un id dell'API passano dallo stesso helper (`Gantt.jsx:131`, `SezioneFasiTask.jsx:733, 835`).
- **Backend:**
  - `dipendente_id: str = ""` diventa `Optional[...] = None` (`tasks.py:178`);
  - in uscita `null` invece di `""`: `gantt.py:174, 569, 745`, `tasks.py:146`, `data_db_impl.py:399, 2473`.
- **Test:** un e2e nuovo sulla modale task che sceglie il responsabile e fa scattare il controllo di saturazione: oggi quel percorso non ha copertura.
- **Schema, seed:** nessun cambio.

**Verifica:** quella comune. Con gli id ancora testuali tutto deve funzionare come prima.

**Parallelo:** repo fermo sul frontend, perché tocca molti componenti (anche quelli del blocco G). Il backend resta libero.

### B8 — Fixture e2e senza id cablati

**Perché qui.** Gli e2e oggi creano dati con id scelti a mano (T900–T907, T950–T954, T960–T961, PFASI, PPROVA) e con `fase_id` 8 e 31, che valgono solo su un seed appena caricato (RICOGNIZIONE §1.7). Con gli id generati dal database smetterebbero di funzionare tutti insieme.

**Cosa cambia**
- **e2e:**
  - `dati_prova.py`, `scenario_fasi.py` e `scenario_sottotask.py` creano senza id, trovano la fase per (progetto, nome) e scrivono un **manifesto** JSON con gli id ottenuti, nella cartella dei risultati, non nel repository;
  - gli spec leggono il manifesto;
  - la pulizia cancella esattamente gli id del manifesto, per chiave esatta come vuole CLAUDE.md;
  - `utenti.js` e gli spec legano i dipendenti per email, non per `D004` e `D011`;
  - `--impronta` di `dati_prova.py` non ordina più per id.
- **Schema, backend, frontend:** nessun cambio.

**Verifica:** suite e2e verde due volte di fila, così la pulizia lascia davvero il database com'era. L'impronta dei dati di prova è identica prima e dopo la suite.

**Parallelo:** libero, se nessun altro tocca `e2e/`.

### B9 — Famiglie delle attività interne in tabella

**Perché qui.** Toglie l'ultimo significato del prefisso dell'id (RICOGNIZIONE §2.1, audit 8.3) prima che gli id cambino.

**Cosa cambia**
- **Modello e baseline:**
  - la tabella `categorie_attivita` (`id`, `nome` UNIQUE, `ordine`, `attivo`);
  - `progetti.categoria_id` nullable, FK;
  - CHECK `tipologia = 'interna' OR categoria_id IS NULL`.
- **Seed:** crea le tre categorie oggi dedotte da PC, PI e PN e le assegna ai 27 progetti interni.
- **Backend:**
  - `_famiglia` (`attivita_interne.py:117-126`) legge il dato;
  - la lista delle categorie nell'ordine della tabella;
  - un'attività senza categoria va in «Altre», come oggi.
- **Frontend:** la pagina Attività interne non cambia aspetto. Se la gestione da Configurazione entra in questo passo (D8), si aggiunge una sezione come quelle di ruoli e competenze.
- **Test:** il raggruppamento, il CHECK, il caso nullo.

**Verifica:** quella comune, più la pagina Attività interne con gli stessi gruppi e gli stessi conteggi di prima, confrontati sul payload.

**Parallelo:** finestra.

### B10 — Progetti: id numerico più codice

**Perché qui.** È il primo degli id: ha meno riferimenti degli altri e introduce il codice leggibile. B7, B8 e B9 hanno già tolto le dipendenze dalla forma dell'id.

**Cosa cambia**
- **Modello e baseline:**
  - `progetti.id` diventa `Integer` con `Identity()`;
  - `codice VARCHAR(20) NOT NULL UNIQUE`, con CHECK `codice = upper(codice)`;
  - `progetti_numero_seq` diventa la sequenza del codice;
  - le 6 FK verso progetti diventano `Integer`.
- **Backend:**
  - parametri di path `int`;
  - `ProgettoCreate.id` sparisce e al suo posto c'è un `codice` facoltativo;
  - generazione del codice nel servizio con `nextval`, nella stessa transazione;
  - via `_ID_NUMERICO`, `_NUMERO_ID` e `ordine_progetti()`, con nuovo ordinamento (D9);
  - nome file dell'Excel con il codice;
  - snapshot SAL e bollettino con il codice accanto all'id;
  - messaggi che citano il codice.
- **Frontend:**
  - gli URL restano `/cantiere/:id` e `/elenco/:id`, con l'id numerico;
  - dove oggi si mostra l'id si mostra il codice;
  - `nomeBaseFile` usa il codice.
- **Seed:** il codice viene dal JSON (P001…PN03); l'id lo genera il database; i riferimenti `pm_id` e `progetto_id` si risolvono attraverso un dizionario codice → id.
- **Test:**
  - `test_id_progetti.py` riscritto sul codice: generato, scritto a mano, collisione → 409, minuscole, due creazioni concorrenti, P999 → P1000;
  - `test_ciclo_progetto.py` senza id espliciti;
  - `ciclo-progetto.spec.js:94` sul codice;
  - `letture-intatte.spec.js:34-35` con l'id letto dall'API.

**Verifica:** quella comune; l'impronta resta identica, perché la tabella dipendenti non cambia; per i progetti, codice, nome e numero di fasi e task uguali prima e dopo, confrontati per codice.

**Parallelo:** **repo fermo**.

### B11 — Dipendenti: id numerico

**Perché qui.** Dopo i progetti, perché `progetti.pm_id` passa a `Integer` in questo passo, e B10 lo lascia testuale. Prima dei task, che hanno più riferimenti. Audit 3.2.

**Cosa cambia**
- **Modello e baseline:**
  - `dipendenti.id` diventa `Integer` con `Identity()`;
  - le 10 FK rimaste dopo B3 diventano `Integer`, più `consolidato_da`;
  - se la vuoi, `matricola VARCHAR(20) NULL UNIQUE` (D10).
- **Backend:**
  - via il generatore `max()` (`configurazione.py:506-511`);
  - parametri di path `int` (`dipendenti.py:192`, `configurazione.py:538, 585`, `sottotask.py:362`, `risorse.py:126`);
  - `UserResponse.dipendente_id` intero;
  - i confronti di 1.2.6 tra tipi uguali.
- **Frontend:** già pronto dopo B7. Restano da controllare `Configurazione.jsx` (client `useCrud`) e `VistaManagement.jsx:221`.
- **Seed:** i dipendenti senza id; gli utenti collegati per email (`seed.py:594-619`); i riferimenti del JSON (`D001`…) risolti tramite un dizionario chiave del seed → id.
- **Test:** chi usa `D004`, `D011` o `D002`, se B8 non li ha già tolti tutti.

**Verifica:** quella comune; **l'impronta resta identica**, perché non contiene l'id, ed è la prova più forte che le persone sono le stesse.

**Parallelo:** **repo fermo**.

### B12 — Task: id numerico

**Perché qui.** Ultimo, perché tocca più tabelle e più logica di tutti. Chiude il bloccante 3.1 dell'audit.

**Cosa cambia**
- **Modello e baseline:**
  - `task.id` diventa `Integer` con `Identity()`;
  - FK in `dipendenza_task` (2), `sottotask`, `consuntivi` e `blocchi_ore`;
  - la FK composta `blocchi_ore → sottotask (id, task_id)` e la UNIQUE `sottotask (id, task_id)`;
  - la vista `ore_settimanali`, insieme alla sua `Table` di lettura (`models.py:1285-1286`).
- **Backend:**
  - via `_next_task_id` e `genera_id_task_multipli`, e la creazione restituisce l'id generato;
  - `UnitaConsuntivoIn.id` intero, validato sul solo `tipo` (`consuntivi.py:213-214, 244-248`);
  - `ORDER BY ordine, id` dove oggi c'è `Task.id` testuale (RICOGNIZIONE §1.2.3);
  - `TaskStaffing.predecessore` verificato nello stesso progetto (`progetti.py:893`);
  - messaggi «task #id»;
  - snapshot SAL con `schema_version` 3.
- **Frontend:**
  - `leggiErrori` (`ConsuntivazioneOre.jsx:817-828`) allineato al nuovo testo dei messaggi;
  - il «codice» della griglia (`ConsuntivazioneOre.jsx:177`) e le opzioni delle dipendenze (`SezioneFasiTask.jsx:887`) mostrano «#id».
- **Seed:**
  - i task senza id; `predecessore` e le 9 dipendenze SS/FF cablate (`seed.py:483-495`) risolte tramite un dizionario;
  - i consuntivi agganciati attraverso lo stesso dizionario.
- **Test:**
  - creazione di oltre mille task di fila senza collisioni;
  - due creazioni concorrenti;
  - consuntivi con unità task e sottotask con lo stesso numero di id: la chiave `(tipo, id)` li tiene separati.

**Verifica:** quella comune; ore totali per progetto e per persona uguali prima e dopo su gantt_db.

**Parallelo:** **repo fermo**.

### B13 — Segnalazioni, pulizia finale, documenti

**Perché qui.** Chiude il blocco, e toglie ciò che i passi precedenti hanno reso inutile.

**Cosa cambia**
- `segnalazioni.id` diventa `Integer` con `Identity()`; il seed le crea senza id.
- Via:
  - `riallinea_numero_progetti`, se dopo B10 serve solo al seed: allora si sposta nel seed;
  - `add_p010.py`, `diagnostico_d1.py`, `_snapshot_dipendenze.py`;
  - `test_solidita.sh`.
- Aggiornati:
  - il PIANO, dove il blocco B diventa ✅;
  - il BACKLOG, dove si tolgono indici, colonne morte, orari misti e naming convention;
  - INVENTARIO superato, da segnalare in testa;
  - `ARCHITETTURA.md`, se nel frattempo esiste.

**Verifica:** quella comune, più un grep senza più occorrenze di `startswith("P"|"T"|"D")`, `[1:].isdigit`, `^P[0-9]`, `String(10)` sulle chiavi.

**Parallelo:** finestra.

---

## 3. Decisioni che servono da te prima di partire

| # | Decisione | Proposta |
|---|---|---|
| D1 | Dove fare il confronto del B0, se due schemi dentro `gantt_test` non si possono creare con `vicacrit` | un database `gantt_schema`, creato una volta da chi ha i permessi |
| D2 | Formato della naming convention | quello raccomandato da SQLAlchemy: `pk_%(table_name)s`, `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`, `uq_%(table_name)s_%(column_0_N_name)s`, `ck_%(table_name)s_%(constraint_name)s`, `ix_%(column_0_label)s` |
| D3 | Elenco definitivo di tabelle e colonne morte. In particolare `fasi.urgenza` (grep la trova letta), e `scadenza_bando`, `motivo_sospensione` e `lezioni_apprese`, che sembrano funzioni future più che resti | via le tre tabelle e le colonne con zero lettori; le funzioni future, se servono, rientreranno con il loro passo |
| D4 | Precisioni dei Numeric, e se le **ore** (vendute, pianificate, stimate residue) entrano nel B5 insieme ai soldi | sì alle ore: il confronto con `!=` fra somme di ore in float (audit 10.7) è lo stesso difetto |
| D5 | Quando i calcoli passano a Decimal | fase 2 «Economia onesta», non il blocco B |
| D6 | Nel prompt del B5, l'autorizzazione all'impronta che cambia per la sola rappresentazione di `costo_ora`, con la verifica descritta lì | — |
| D7 | Orologio dei timestamp: il database (`now()`) o l'applicazione | il database |
| D8 | Famiglie delle attività interne: gestibili da Configurazione già nel B9, o solo dal seed per ora; obbligatorie per le interne | gestibili da subito, facoltative (chi non ne ha una va in «Altre») |
| D9 | Ordine delle liste di progetti senza `ordine_progetti()` | per codice dove l'utente sceglie l'ordine, per id altrove |
| D10 | Matricola dei dipendenti: sì o no | no adesso; si aggiunge quando un cliente la chiede |
| D11 | Formato e posizione del prefisso del codice di progetto. Oggi è una costante in `models.py` e una tabella di parametri non esiste ancora | per ora una variabile di configurazione, con default `P`, cifre 3; si sposta in Configurazione con i parametri dell'azienda |
| D12 | Chi tiene il repo fermo durante B10–B12, e come lo sa l'altra sessione | un passo per volta, annunciato prima; l'altra sessione lavora solo su `docs/` o su file nominati nel prompt |
| D13 | Riferimento breve a un task nell'interfaccia: «#id» basta? | sì |

---

## Cosa questo piano non ha verificato

- Che si possano usare due schemi in `gantt_test` per il confronto del B0.
- Lettori e scrittori di ogni colonna «morta»: il grep li trova ancora in DTO e serializzatori, quindi il censimento è il primo compito del B3.
- Che con `asdecimal=False` nessun lettore riceva comunque un `Decimal` (per esempio da una somma SQL su Numeric, che psycopg restituisce come Decimal anche quando la colonna è dichiarata così). Vale già per `blocchi_ore.ore`, ed è da controllare caso per caso nel B5.
- I tempi: nessuna stima.

## 4. Decisioni prese il 16/10/2026

Accettate le proposte da D1 a D13 della tabella del § 3, con queste precisazioni:

- **D1:** il confronto del B0 si fa in due schemi dentro `gantt_test`. Il database separato `gantt_schema` resta solo un ripiego, se un giorno i due schemi non bastassero.
- **D3:** si tolgono le tre tabelle morte e le colonne che dopo il censimento risultano con zero lettori, comprese quelle delle funzioni future (`scadenza_bando`, `motivo_sospensione`, `lezioni_apprese`, se il censimento le conferma senza lettori). Se una funzione futura servirà, rientrerà con il suo passo.
- **D6:** nessun cambio d'impronta nel B5. Dal passo B0 l'impronta dei dipendenti scrive i numeri con due decimali fissi ed è indipendente dal tipo delle colonne, quindi il passaggio di `costo_ora` a Numeric non la cambia.
