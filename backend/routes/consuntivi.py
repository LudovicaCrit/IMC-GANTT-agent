"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/consuntivi.py — Router per endpoint /api/consuntivi
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint relativi ai consuntivi settimanali dei dipendenti.
È il cuore tecnico della pagina Consuntivazione e della futura Vista
Helena (Blocco 3 roadmap). Implementa rigorosamente il pattern
Scenario B + self-or-manager + Pattern Y (anti-impersonation in scrittura).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/consuntivi/settimana        │ GET      │ require_manager              │
│ /api/consuntivi/me               │ GET      │ AUTH-ONLY (intrinseco self)  │
│ /api/consuntivi/salva            │ POST     │ Pattern Y (self-or-manager)  │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/consuntivi/settimana
   - Manager-only.
   - Vista AZIENDALE: tutti i dipendenti, settimana corrente.
   - Per ogni dipendente: ore_per_task, totale_ore, flag `compilato`.
   - Include anche dipendenti che NON hanno compilato (totale_ore=0,
     compilato=False), purché abbiano almeno 1 task attivo.
   - Output ordinato: prima i compilati, poi per nome.

2. GET /api/consuntivi/me
   - AUTH-ONLY: nessun parametro `dipendente_id` accettato.
     L'identità del chiamante determina di chi mostrare i consuntivi.
   - Vista PERSONALE: il dipendente vede SOLO i propri consuntivi.
   - Funziona per user (Helena) e per manager (Ludovica può vedere se
     stessa così, anche se ha accesso a /settimana per la vista aziendale).
   - 400 se l'utente non è collegato a un dipendente
     (current_user.dipendente_id is None).
   - Layout A': parte dai TASK del dipendente (non dai Consuntivi),
     via data.task_settimana_dipendente (riusabile dalla Home-utente).
   - Query param opzionale `settimana` (ISO YYYY-MM-DD, qualsiasi giorno
     della settimana → normalizzato al lunedì da data.lunedi_settimana).
     Assente = settimana corrente. Ammesse solo corrente e precedente:
     qualsiasi altra → 400. Serve al recupero di chi non ha compilato in
     tempo; non si compila in anticipo né si riscrive un mese fa.
   - Restituisce: nome, profilo, ore_contrattuali, settimana (lunedì ISO),
     settimane_disponibili, totale_ore, task_settimana, compilato.
   - Ogni voce di `task_settimana` porta `in_ritardo` (bool): DERIVATO
     (finestra del task chiusa + task non chiuso), non dichiarato. Il ritardo
     non è uno stato che il dipendente sceglie — non è nella tendina: è una
     segnalazione che il sistema calcola e il frontend mostra accanto al task.
   - `settimane_disponibili`: le due settimane apribili, ciascuna con
     lunedi/etichetta/compilabile. CONSULTABILE ≠ COMPILABILE: la scorsa si
     apre sempre in lettura, ma `compilabile` è False se già completa (ore
     dichiarate >= ore contrattuali) — il recupero serve a chi non ha
     compilato, non a rivedere ciò che è chiuso. La guardia in scrittura sta
     su POST /salva, non qui.

3. POST /api/consuntivi/salva
   - Pattern Y (self-or-manager): l'user può salvare SOLO i propri
     consuntivi (controllo self via current_user.dipendente_id);
     il manager può salvare per chiunque.
   - Body: dipendente_id, ore_per_task, stati_per_task, note_per_task,
     giorni sede/remoto, ore_assenza, tipo_assenza, nota_assenza, spese.
   - Lo stato dichiarato NON resta sul Consuntivo: `salva_consuntivo` lo
     propaga su Task.stato passando da `modifica_task` (la stessa porta del
     Cantiere). È ciò che rende osservabile un "Completato": senza, il task
     ricompariva in /me la settimana dopo come se nulla fosse.
   - 400 se lo stato non è dichiarabile dal dipendente (solo In corso,
     Completato, Bloccato: vedi models.STATI_DICHIARABILI) o se un task è
     dichiarato Bloccato senza nota. Validato nel DTO, prima del data layer.
   - 403 se user prova a salvare per un altro dipendente.
   - 404 se dipendente non esiste.
   - Persiste in db (PERSISTENT_MODE) o ritorna conferma simulata altrimenti.

PATTERN AUTH USATI
──────────────────
- `require_manager`: per la vista aziendale aggregata.
- `get_current_user` + check `dipendente_id`: per il pattern self-or-manager
  in scrittura (Pattern Y) e per la vista personale intrinseca (`/me`).

NOTE DI DOMINIO
───────────────
La vista personale `/api/consuntivi/me` è esattamente quella che alimenterà
la pagina Consuntivazione di Helena nella Vista User (Blocco 3 roadmap).
Coerente con la "filosofia della settimana intera" e con Scenario B.

📌 TODO Blocco 3 roadmap (Vista Helena + Form Consuntivazione):
   Il payload restituito da `/api/consuntivi/me` potrebbe arricchirsi:
   - reminder integrati ("non hai ancora compilato")
   - task in scadenza
   - flag `motivo_richiesto` se task bloccato/in ritardo senza nota
   - storia delle ultime N settimane

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `salva_consuntivo` (in PERSISTENT_MODE).
- `models`: `Dipendente`, `Task`, `Consuntivo`, `get_session` (lettura
  diretta Postgres).
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
La vista `/me` non ha più early-return sulla tabella Consuntivi vuota: parte
dai Task attivi, quindi `task_settimana` è popolata anche alla prima
compilazione (ore_consumate=0), non lista vuota.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
Letture migrate da DataFrame in cache a Postgres diretto il 21 maggio 2026
(handoff migrazione §6-ter), preservando iso-comportamento.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from deps import get_current_user, require_manager
from models import (
    Utente, Dipendente, Task, Consuntivo, get_session, STATI_DICHIARABILI,
)
from data import (
    get_dipendente,
    task_settimana_dipendente,
    lunedi_settimana,
    settimane_selezionabili,
    note_consuntivi_settimana,
    note_sottotask_settimana,
    percentuali_successive,
)


# Import condizionale per scrittura
try:
    from data import salva_consuntivo
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False


# ══════════════════════════════════════════════════════════════════════════
# DOVE VA UNA VALIDAZIONE — nota di metodo
# ══════════════════════════════════════════════════════════════════════════
# Le validazioni di POST /salva stanno in DUE punti diversi, e non è un caso
# né un'incoerenza da "sistemare" accorpandole. Il criterio è uno solo:
#
#   Il DTO vede SOLO il body. Qualunque regola che dipenda da cosa c'è già in
#   database non può stare lì, e va dove lo stato attuale è conoscibile.
#
# 1) Nel DTO (`SalvaConsuntivoRequest._valida_stati_dichiarabili`) le regole
#    che si decidono guardando il solo payload: «Bloccato non è uno stato che
#    il dipendente può dichiarare?» è vero o falso a prescindere dal DB.
#    Vantaggio: valgono per chiunque costruisca il DTO, e scattano prima che
#    si apra una sessione.
#
# 2) Nella route (`_valida_blocchi_motivati`) le regole che dipendono dallo
#    stato persistito. «Bloccato richiede una nota» sembra una regola sul
#    body, e all'inizio era scritta nel DTO come `not note_per_task.get(id)`:
#    sbagliata, perché il form manda solo le note MODIFICATE. Ridichiarare
#    Bloccato senza ritoccare una nota già salvata prendeva 400 — un
#    salvataggio legittimo rifiutato, per una regola messa dove non poteva
#    vedere la nota che esisteva.
#
# La morale per chi passa di qui: prima di aggiungere una regola al DTO,
# chiedersi «per rispondere mi basta il body?». Se la risposta è no — anche
# solo "dipende da cosa c'era prima" — la regola va in (2), non in (1).
# Le due strade convergono comunque su un 400 con messaggio parlante: la
# differenza è dove si può sapere la verità, non come la si comunica.


# ── DTO ──────────────────────────────────────────────────────────────────
class SalvaConsuntivoRequest(BaseModel):
    dipendente_id: str
    # Lunedì della settimana in ISO. Assente = settimana corrente. Qualsiasi
    # giorno è accettato e normalizzato al lunedì (data.lunedi_settimana).
    settimana: Optional[str] = None
    ore_per_task: dict[str, float] = {}
    # Lo STATO è il campo primario della compilazione: il dipendente dichiara
    # «a che punto sono», non «quanto ho lavorato». Ammessi solo i tre stati di
    # models.STATI_DICHIARABILI — vedi il validatore sotto.
    stati_per_task: dict[str, str] = {}
    # «A che punto sono», in parole. Obbligatoria su Bloccato, libera altrove.
    # None = il chiamante non gestisce le note, non toccarle (stessa
    # convenzione di `spese`); chiave presente e vuota = cancella la nota.
    note_per_task: Optional[dict[str, str]] = None
    # ── Il TASK come unità di lavoro (Step 4, 07/08/2026) ────────────────
    # Un task NON scomposto dichiara l'avanzamento come lo dichiara un pezzo.
    # Sono i due campi che mancavano: gli altri due di una dichiarazione — lo
    # stato e la nota — il task li ha GIÀ in `stati_per_task` e `note_per_task`,
    # e non si duplicano.
    #
    # Quando arriva `percentuale_per_task`, lo `stato_dichiarato` del task NON
    # viene più preso da `stati_per_task`: si DERIVA dal cursore (100→Completato,
    # 1-99→In corso, 0→nessuno stato), esattamente come sul sottotask. Di
    # `stati_per_task` resta significativo il solo «Bloccato», che è l'unica
    # cosa che una percentuale non può dire — un task fermo al 40% è
    # indistinguibile da uno che avanza piano.
    #
    # Su un task SCOMPOSTO questi due campi vengono IGNORATI: le sue ore vengono
    # dai pezzi (mutua esclusione, `tipo_unita_per_task`). Il chiamante lo scopre
    # dagli `avvisi` in risposta, non in silenzio.
    percentuale_per_task: dict[str, int] = {}
    ore_effettive_per_task: dict[str, float] = {}
    # Ore che MANCANO ancora per finire il task, secondo chi ci lavora
    # (04/09/2026): {task_id: ore}. Guarda AVANTI, mentre le due qui sopra
    # guardano indietro — «a che punto sono» e «quanto è costato» raccontano il
    # passato, questa è l'unica che dice dove si va a finire.
    #
    # Non è ricavabile da ciò che il backend già sa: `ore_rimanenti` in /me è
    # `ore_pianificate` meno il consumato, cioè quanto BUDGET avanza. Quanto
    # LAVORO manca lo sa solo chi lo sta facendo.
    #
    # Chiave assente = non stimato (NULL in colonna). Valore 0 = «non manca
    # niente», che è un'affermazione e va potuta fare.
    ore_stimate_residue_per_task: dict[str, float] = {}
    # Avanzamento dichiarato sui SOTTOTASK: {sottotask_id: percentuale 0-100}.
    # Step 4 (06/08/2026) — è l'input del motore ore-derivate: da qui NON
    # arrivano ore, arrivano percentuali, e le ore le calcola il backend
    # (Δpct × ore_stimate del sottotask) aggregandole sul task.
    # Chiavi INT e non str come gli altri dizionari: `Sottotask.id` è un
    # Integer, mentre task e progetti hanno id stringa. JSON manda comunque
    # chiavi stringa e pydantic le converte — dichiararle int qui evita che la
    # conversione la faccia a mano ogni lettore.
    # Default {} e non None: a differenza di `note_per_task` e `spese` non
    # esiste un «non gestisco questo campo, non toccarlo». Un avanzamento
    # assente non è un dato da preservare, è un avanzamento non dichiarato.
    avanzamenti_sottotask: dict[int, int] = {}
    # Ore REALI dichiarate a mano su un sottotask, per questa settimana
    # (Step 4 strato 2, 06/08/2026): {sottotask_id: ore}. Serve quando
    # l'avanzamento non cattura il costo — pezzo fermo che è comunque costato
    # tempo, o pezzo finito che è costato più della stima.
    # Quando arriva, SOSTITUISCE la derivata per quel sottotask in quella
    # settimana: non si somma. Chiave assente = nessuna ora effettiva, si
    # deriva; è la stessa distinzione NULL/0.0 della colonna.
    ore_effettive_sottotask: dict[int, float] = {}
    # Gemella di `ore_stimate_residue_per_task` sul PEZZO: {sottotask_id: ore
    # che mancano}. Stessa convenzione — chiave assente = non stimato, 0 =
    # «non manca niente». Chiavi int come gli altri dizionari-sottotask.
    ore_stimate_residue_sottotask: dict[int, float] = {}
    # Quali sottotask il dipendente dichiara BLOCCATI questa settimana.
    # È un flag ESPLICITO e non derivabile dall'avanzamento: un pezzo può
    # essere bloccato al 40% (fermo lì, in attesa di qualcosa) e la percentuale
    # da sola non lo direbbe mai — 40% e basta è indistinguibile da «avanza
    # piano». Gli altri due stati dichiarabili invece SI derivano dallo slider,
    # vedi `_stato_da_avanzamento` nel data layer.
    # `set` e non lista: è un'appartenenza, e i duplicati non vogliono dire
    # niente. Pydantic accetta un array JSON e lo converte.
    bloccati_sottotask: set[int] = set()
    # Nota per-sottotask, per-persona, per-settimana: il diario di quel pezzo.
    # Stessa convenzione di `note_per_task`, che è la ragione per cui è
    # Optional e non un dict vuoto: None = «non gestisco le note, non
    # toccarle»; chiave presente con stringa vuota = cancella; chiave assente
    # dentro un dict presente = lascia com'è. Il form manda solo le note
    # MODIFICATE, e appiattire i tre casi su due cancellerebbe testo che
    # nessuno ha chiesto di cancellare.
    note_sottotask: Optional[dict[int, str]] = None
    # ── PRESA IN VISIONE (nodo F-2, 02/09/2026) ──────────────────────────
    # Le unità su cui il dipendente ha confermato «l'ho guardata, è ancora
    # ferma, non è avanzata». È una TRACCIA SENZA AVANZAMENTO: fa risultare
    # l'unità dichiarata nel contatore della Consuntivazione senza costringere
    # nessuno a inventare un progresso che non c'è.
    #
    # DUE LISTE DI SOLI ID, e un canale PROPRIO invece del riuso di
    # `percentuale_per_task` / `avanzamenti_sottotask`. Non è ridondanza: per un
    # SOTTOTASK rimandare la percentuale invariata farebbe ricalcolare
    # `stato_dichiarato` (il data layer lo riderivata quando il pezzo compare
    # fra gli avanzamenti o fra i bloccati), e un pezzo Bloccato preso in
    # visione risulterebbe SBLOCCATO in silenzio. È il bug che il commento
    # «NON si manda la percentuale quando si ritocca solo la nota di un pezzo
    # fermo» già previene nel form: qui si evita alla radice, non mandando mai
    # la percentuale per dire «l'ho vista».
    #
    # PORTANO SOLO L'ID. Una nota nuova, se c'è, viaggia in `note_per_task` /
    # `note_sottotask` come qualunque altra nota scritta a mano. La
    # `nota_ereditata` che /me espone NON deve mai tornare indietro da qui né da
    # lì: è il promemoria di quello che qualcuno ha scritto in una settimana
    # precedente, e rispedirla come nota di questa settimana farebbe firmare al
    # dipendente parole non sue. Il canale a soli id rende la cosa impossibile
    # per costruzione.
    #
    # `set` e non lista, come `bloccati_sottotask`: è un'appartenenza, e i
    # duplicati non vogliono dire niente. Pydantic accetta un array JSON.
    viste_task: set[str] = set()
    viste_sottotask: set[int] = set()
    # Presenze: None = «non gestisco questo campo, non toccarlo» (stessa
    # convenzione di `spese` e `note_per_task`). I default 3/2/0 di prima non
    # erano dati dichiarati ma un'ipotesi di comodo, e finivano scritti in DB a
    # ogni salvataggio: un client che manda solo uno stato riportava a 3 e 2 i
    # giorni sede/remoto che il dipendente aveva impostato altrove. Un campo
    # assente ora non scrive niente; se arrivano solo alcuni campi, gli altri
    # restano com'erano.
    giorni_sede: Optional[int] = None
    giorni_remoto: Optional[int] = None
    ore_assenza: Optional[float] = None
    tipo_assenza: Optional[str] = None
    nota_assenza: Optional[str] = None
    # None = il chiamante non gestisce le spese, non toccarle. [] = «questa
    # settimana nessuna spesa», svuota. Il default è None e NON [] proprio
    # per tenere distinti i due casi: con [] come default, un client che
    # omette il campo cancellerebbe le spese senza volerlo.
    spese: Optional[list[dict]] = None

    @model_validator(mode="after")
    def _valida_stati_dichiarabili(self):
        """Gli stati che il dipendente può dichiarare.

        Sta QUI e non nella route perché è una proprietà del payload, non del
        caso d'uso: chiunque costruisca un SalvaConsuntivoRequest ottiene la
        stessa regola, e non serve conoscere il DB per applicarla. Soprattutto
        sta PRIMA del data layer: senza, uno stato fuori lista (es. "Annullato"
        da un client curioso) arriverebbe fino al CHECK ck_task_stato_ammessi e
        tornerebbe come IntegrityError, cioè un 500 opaco su quello che è un
        errore del chiamante.

        La regola «Bloccato richiede una nota» NON sta qui: dipende da cosa c'è
        già in DB, che il DTO non può sapere. Vive nella route — vedi
        `_valida_blocchi_motivati` e la nota di metodo «DOVE VA UNA
        VALIDAZIONE» sopra la definizione di questa classe.

        `HTTPException` invece di `ValueError` di proposito: pydantic converte
        i ValueError in errori di validazione (422 «Unprocessable Entity»),
        mentre le altre eccezioni attraversano la validazione e finiscono
        all'handler di FastAPI. Qui vogliamo un 400 con un messaggio che dica
        al dipendente cosa correggere, non un dump di validazione.
        """
        for task_id, stato in self.stati_per_task.items():
            if stato not in STATI_DICHIARABILI:
                raise HTTPException(
                    400,
                    f"Stato '{stato}' non dichiarabile sul task {task_id}: "
                    f"il dipendente può dichiarare solo "
                    f"{', '.join(STATI_DICHIARABILI)}. Gli altri stati "
                    f"(Da iniziare, Sospeso, Annullato) sono decisioni di "
                    f"pianificazione e si impostano dal Cantiere.",
                )

        # Range dell'avanzamento. Regola decidibile dal SOLO body → sta qui,
        # per lo stesso criterio del blocco sopra. Senza, un 150 arriverebbe al
        # CHECK ck_consuntivo_sottotask_percentuale come IntegrityError, cioè un
        # 500 opaco su un errore del chiamante — la trappola che la nota di
        # metodo qui sopra descrive per gli stati.
        # Gli stessi due range valgono per il TASK come unità di lavoro: la
        # regola è della DICHIARAZIONE, non dell'entità che la porta.
        for tid, pct in self.percentuale_per_task.items():
            if pct < 0 or pct > 100:
                raise HTTPException(
                    400,
                    f"Avanzamento {pct} non valido sul task {tid}: "
                    f"la percentuale va da 0 a 100.",
                )
        for tid, ore in self.ore_effettive_per_task.items():
            if ore < 0:
                raise HTTPException(
                    400,
                    f"Ore effettive {ore} non valide sul task {tid}: "
                    f"non possono essere negative.",
                )
        # Residuo non negativo. Nessun massimo — «ne mancano 300» su un task
        # pianificato 40 è una stima drammatica ma non è un errore di
        # battitura da respingere: è esattamente l'allarme che questo campo
        # esiste per far arrivare al PM prima dello sforamento.
        for tid, ore in self.ore_stimate_residue_per_task.items():
            if ore < 0:
                raise HTTPException(
                    400,
                    f"Ore residue {ore} non valide sul task {tid}: non possono "
                    f"essere negative. Zero è ammesso e significa «non manca "
                    f"più niente».",
                )

        for sid, pct in self.avanzamenti_sottotask.items():
            if pct < 0 or pct > 100:
                raise HTTPException(
                    400,
                    f"Avanzamento {pct} non valido sul sottotask {sid}: "
                    f"la percentuale va da 0 a 100.",
                )

        # Ore effettive non negative. Nessun massimo: le ore non hanno un
        # dominio chiuso come la percentuale, e infatti la colonna non ha un
        # CHECK (segue `consuntivi.ore_dichiarate`, non `percentuale`). Il
        # minimo però va imposto, e qui invece che a livello DB perché così
        # diventa un 400 leggibile e non un IntegrityError opaco.
        for sid, ore in self.ore_effettive_sottotask.items():
            if ore < 0:
                raise HTTPException(
                    400,
                    f"Ore effettive {ore} non valide sul sottotask {sid}: "
                    f"non possono essere negative. Zero è ammesso e significa "
                    f"«questa settimana non è costato niente».",
                )

        for sid, ore in self.ore_stimate_residue_sottotask.items():
            if ore < 0:
                raise HTTPException(
                    400,
                    f"Ore residue {ore} non valide sul sottotask {sid}: non "
                    f"possono essere negative. Zero è ammesso e significa "
                    f"«non manca più niente».",
                )
        return self


def _valida_blocchi_motivati(req: "SalvaConsuntivoRequest", settimana):
    """Un task dichiarato Bloccato deve avere una nota che spieghi il blocco.

    Il vincolo è che la nota ESISTA, non che sia arrivata in questa richiesta.
    Il form manda solo le note MODIFICATE: ridichiarare Bloccato la settimana
    dopo senza ritoccare il testo è il caso normale, e pretendere il rinvio
    significava rifiutare salvataggi legittimi di chi una nota ce l'aveva già.
    Da qui il controllo in due tempi — prima la richiesta, poi il DB — e da qui
    il fatto che viva nella route e non nel DTO, che vede solo il body: il
    perché per esteso sta nella nota di metodo «DOVE VA UNA VALIDAZIONE», sopra
    SalvaConsuntivoRequest. Se ti viene voglia di riportare questa regola nel
    DTO «per tenere le validazioni insieme», leggila prima: è già stata lì, e
    rifiutava salvataggi legittimi.

    Una stringa vuota in `note_per_task` NON è «campo assente»: è una
    cancellazione esplicita (la stessa convenzione con cui il data layer azzera
    la nota). Cancellare la spiegazione di un blocco lascia il PM davanti a un
    «fermo» senza motivo, quindi si rifiuta anche se in DB una nota c'era.

    La query sul DB parte solo se serve davvero: un salvataggio senza task
    bloccati, o con le note tutte in arrivo, non la esegue.
    """
    da_motivare = []
    note_esistenti = None

    for task_id, stato in req.stati_per_task.items():
        if stato != "Bloccato":
            continue
        if req.note_per_task is not None and task_id in req.note_per_task:
            if (req.note_per_task[task_id] or "").strip():
                continue          # nota in arrivo: basta questa
            da_motivare.append(task_id)   # cancellazione esplicita: rifiuta
            continue
        if note_esistenti is None:
            note_esistenti = note_consuntivi_settimana(req.dipendente_id, settimana)
        if not note_esistenti.get(task_id):
            da_motivare.append(task_id)

    if da_motivare:
        elenco = ", ".join(sorted(da_motivare))
        raise HTTPException(
            400,
            f"Dichiarati Bloccati senza una nota che spieghi cosa li blocca: "
            f"{elenco}. Scrivi il motivo in note_per_task (una nota già "
            f"salvata in questa settimana va bene: non serve rimandarla, ma "
            f"non si può svuotarla).",
        )


def _valida_dichiarazioni_sottotask(req: "SalvaConsuntivoRequest", settimana):
    """Le regole sulle dichiarazioni-sottotask che il solo body non può decidere.

    Step 4 (06/08/2026), motore ore-derivate. Stanno QUI e non nel DTO per il
    criterio della nota di metodo sopra `SalvaConsuntivoRequest`: tutte hanno
    bisogno di sapere cosa c'è già in database. I range (0-100 sull'avanzamento,
    ore effettive non negative), che si decidono dal solo payload, sono rimasti
    nel DTO.

    1. IL SOTTOTASK DEVE ESISTERE. Non è pedanteria: `ore_derivate_sottotask`
       omette dal risultato le chiavi che non trova, quindi un id inventato
       farebbe sparire l'avanzamento in silenzio, con un salvataggio che
       risponde «ok» e non ha derivato niente.

    2. NIENTE AVANZAMENTO SU UN SOTTOTASK ANNULLATO. Un pezzo annullato è
       stato tolto dal piano — è la via che il Cantiere offre per cancellarlo
       CONSERVANDO le dichiarazioni già fatte (vedi migration a3b4c5d6e7f8).
       Dichiarare avanzamento sopra è contraddittorio, e soprattutto il form
       non dovrebbe averlo proposto: è un errore del chiamante e prende 400.
       I SOSPESI invece si accettano. La sospensione è una decisione di
       pianificazione del PM; se il dipendente ci ha lavorato comunque, il
       lavoro è successo, e rifiutarlo cancellerebbe ore reali per una scelta
       presa da un altro. Stessa asimmetria di `scostamento_stime_sottotask`,
       che esclude gli Annullati dalla somma e tiene i Sospesi.

    3. MONOTONIA. Recuperare una settimana passata è ammesso
       (`settimane_selezionabili` apre la precedente se incompleta), ma
       l'avanzamento non può tornare indietro nel tempo: dichiarare oggi che
       la settimana scorsa il pezzo era al 70% quando questa settimana risulta
       al 40% descrive un lavoro che si è disfatto.
       Serve la dichiarazione SUCCESSIVA, non la precedente — ed è la ragione
       per cui la regola non può stare nel DTO né dentro il calcolo del Δ, che
       guarda solo all'indietro.
       È anche ciò che tiene il ricalcolo a costo fisso: con le percentuali
       non-decrescenti, scrivere a W invalida la baseline di UNA sola settimana
       (la prima dichiarata dopo W) e non innesca cascate.
       Il confronto è per SOTTOTASK, non per dipendente, coerente con la
       baseline del Δ: la percentuale descrive il pezzo, non chi la scrive.

    4. UN SOTTOTASK BLOCCATO RICHIEDE UNA NOTA. Gemella di
       `_valida_blocchi_motivati`, che impone la stessa cosa un livello sopra —
       e ne ricalca la struttura per la stessa ragione: il vincolo è che la
       nota ESISTA, non che sia arrivata in questa richiesta. Il form manda le
       sole note modificate, quindi ridichiarare bloccato un pezzo fermo da tre
       settimane senza ritoccarne il testo è il caso normale. Da qui il
       controllo in due tempi — prima il body, poi il DB solo per i sottotask
       che nel body la nota non ce l'hanno.
       Una stringa VUOTA non è «campo assente»: è una cancellazione esplicita, e
       si rifiuta anche se in DB una nota c'era. Svuotare la spiegazione di un
       blocco lascia il PM davanti a un pezzo fermo senza sapere perché — che è
       precisamente l'informazione per cui il flag esiste.
    """
    if not (req.avanzamenti_sottotask or req.ore_effettive_sottotask
            or req.bloccati_sottotask or req.note_sottotask):
        return

    from models import Sottotask, ConsuntivoSottotask

    # Esistenza e stato si controllano sull'UNIONE dei quattro campi: un
    # sottotask può comparire solo fra le ore effettive (pezzo fermo,
    # avanzamento invariato) o solo fra i bloccati, e avrebbe comunque bisogno
    # di esistere e di non essere annullato. Senza l'unione, un id inventato in
    # uno di quei campi arriverebbe alla FK come IntegrityError, cioè un 500 su
    # un errore del chiamante. La MONOTONIA invece resta sui soli avanzamenti —
    # è una regola sulle percentuali, e le ore non hanno un ordine da rispettare.
    ids = list(dict.fromkeys(
        list(req.avanzamenti_sottotask) + list(req.ore_effettive_sottotask)
        + sorted(req.bloccati_sottotask) + list(req.note_sottotask or {})
    ))
    session = get_session()
    try:
        noti = {
            r.id: (r.nome, r.stato)
            for r in session.query(Sottotask.id, Sottotask.nome, Sottotask.stato)
            .filter(Sottotask.id.in_(ids)).all()
        }

        mancanti = [sid for sid in ids if sid not in noti]
        if mancanti:
            raise HTTPException(
                400,
                f"Sottotask inesistenti: {', '.join(map(str, sorted(mancanti)))}. "
                f"L'avanzamento non può essere registrato su un pezzo che non "
                f"c'è — ricarica il task e riprova.",
            )

        annullati = [f"{noti[sid][0]} (#{sid})" for sid in ids if noti[sid][1] == "Annullato"]
        if annullati:
            raise HTTPException(
                400,
                f"Avanzamento dichiarato su sottotask annullati: "
                f"{', '.join(sorted(annullati))}. Un pezzo annullato è stato "
                f"tolto dal piano e non si consuntiva. Se il lavoro è stato "
                f"fatto davvero, il PM deve riportarlo in piano dal Cantiere.",
            )

        # Monotonia: la prima dichiarazione SUCCESSIVA con percentuale non-NULL.
        # Una query sola per tutti i sottotask, ridotta in Python — stessa
        # scelta (e stessa ragione) di `ore_derivate_sottotask`.
        # ── Un sottotask Bloccato richiede una nota ──────────────────────
        # Struttura di `_valida_blocchi_motivati`, un livello più giù: prima si
        # guarda il body, poi — e solo per chi nel body non porta nulla — si
        # interroga il DB. La query parte una volta sola e solo se serve
        # davvero: dichiarare bloccato con le note tutte in arrivo non la
        # esegue.
        da_motivare = []
        note_esistenti = None
        for sottotask_id in sorted(req.bloccati_sottotask):
            if req.note_sottotask is not None and sottotask_id in req.note_sottotask:
                if (req.note_sottotask[sottotask_id] or "").strip():
                    continue                        # nota in arrivo: basta
                da_motivare.append(sottotask_id)    # svuotamento esplicito
                continue
            if note_esistenti is None:
                note_esistenti = note_sottotask_settimana(req.dipendente_id, settimana)
            if not note_esistenti.get(sottotask_id):
                da_motivare.append(sottotask_id)

        if da_motivare:
            elenco = ", ".join(f"'{noti[s][0]}'" for s in da_motivare)
            raise HTTPException(
                400,
                f"Sottotask dichiarati bloccati senza una nota che spieghi "
                f"cosa li blocca: {elenco}. Scrivi il motivo in "
                f"note_sottotask — una nota già salvata in questa settimana va "
                f"bene, non serve rimandarla, ma non si può svuotarla.",
            )

        if not req.avanzamenti_sottotask:
            return                       # niente percentuali, niente monotonia

        # La regola vive in `percentuali_successive` (data layer), gemella in
        # avanti di `_baseline_percentuali`: la stessa funzione serve i
        # sottotask qui e i task in `_valida_avanzamento_task`, così la
        # monotonia non ha due definizioni.
        minimo_dopo = percentuali_successive(
            session, "sottotask", list(req.avanzamenti_sottotask), settimana
        )

        violazioni = []
        for sid, pct in req.avanzamenti_sottotask.items():
            dopo = minimo_dopo.get(sid)
            if dopo is not None and pct > dopo[1]:
                violazioni.append(
                    f"'{noti[sid][0]}' al {pct}% mentre la settimana del "
                    f"{dopo[0].isoformat()} è già dichiarata al {dopo[1]}%"
                )

        if violazioni:
            raise HTTPException(
                400,
                f"Avanzamento incoerente col seguito: {'; '.join(violazioni)}. "
                f"Una settimana passata non può risultare più avanti di una "
                f"successiva: correggi la percentuale, oppure aggiorna prima "
                f"la settimana più recente.",
            )
    finally:
        session.close()


def _valida_avanzamento_task(req: "SalvaConsuntivoRequest", settimana):
    """Monotonia sull'avanzamento dichiarato a livello TASK.

    Gemella della regola 3 di `_valida_dichiarazioni_sottotask`, e ne riusa la
    STESSA funzione di ricerca (`percentuali_successive`, che prende il tipo):
    la monotonia ha una definizione sola, non una per entità.

    Le altre tre regole dei sottotask NON si generalizzano, e non per pigrizia:
      - «il sottotask deve esistere» → l'esistenza del task è già garantita a
        monte (la FK di `consuntivi` e il fatto che il payload nasce da /me);
      - «niente avanzamento su un sottotask Annullato» → il task ha sì uno stato
        "Annullato", ma è di pianificazione del PM su un'altra scala: un task
        annullato non compare in /me (`task_settimana_dipendente` lo filtra) e
        non è il caso che questa regola descrive;
      - «un Bloccato richiede una nota» → per il TASK esiste già, ed è
        `_valida_blocchi_motivati` qui sopra. Riscriverla sarebbe la
        duplicazione che tutto questo Step ha evitato.
    """
    if not req.percentuale_per_task:
        return

    session = get_session()
    try:
        minimo_dopo = percentuali_successive(
            session, "task", list(req.percentuale_per_task), settimana
        )
    finally:
        session.close()

    violazioni = []
    for task_id, pct in req.percentuale_per_task.items():
        dopo = minimo_dopo.get(task_id)
        if dopo is not None and pct > dopo[1]:
            violazioni.append(
                f"'{task_id}' al {pct}% mentre la settimana del "
                f"{dopo[0].isoformat()} è già dichiarata al {dopo[1]}%"
            )

    if violazioni:
        raise HTTPException(
            400,
            f"Avanzamento incoerente col seguito: {'; '.join(violazioni)}. "
            f"Una settimana passata non può risultare più avanti di una "
            f"successiva: correggi la percentuale, oppure aggiorna prima "
            f"la settimana più recente.",
        )


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/consuntivi", tags=["consuntivi"])


@router.get("/settimana")
def consuntivi_settimana_corrente(_: Utente = Depends(require_manager)):
    """Vista MANAGER-ONLY: riepilogo aziendale settimana corrente.
    Per la vista personale del dipendente vedi /api/consuntivi/me."""
    lun = datetime.now() - timedelta(days=datetime.now().weekday())
    lun_date = lun.date() if hasattr(lun, 'date') else lun
    ven_date = lun_date + timedelta(days=6)

    session = get_session()
    # Iso-comportamento: l'originale fa early-return [] se la tabella
    # consuntivi è completamente vuota (db appena seedato, prima
    # compilazione mai avvenuta). Replicato con una query indicizzata
    # su PK, di costo trascurabile.
    has_any = session.query(Consuntivo.id).first() is not None
    if not has_any:
        session.close()
        return []

    # Una sola query con joinedload su Task → Progetto: evita N+1 nel
    # lookup di nome task/progetto durante il loop.
    cons_sett = session.query(Consuntivo).options(
        joinedload(Consuntivo.task).joinedload(Task.progetto)
    ).filter(
        Consuntivo.settimana >= lun_date,
        Consuntivo.settimana <= ven_date,
    ).all()

    # Raggruppa per dipendente_id (mantiene l'ordine di arrivo, come
    # `unique()` su pandas Series).
    cons_per_dip = {}
    for c in cons_sett:
        cons_per_dip.setdefault(c.dipendente_id, []).append(c)

    risultato = []
    for did, lista_cons in cons_per_dip.items():
        try:
            dip = get_dipendente(did)
        except (IndexError, KeyError):
            continue
        ore_per_task = []
        totale = 0
        for c in lista_cons:
            if c.ore_dichiarate > 0:
                t = c.task
                if t is not None:
                    proj_nome = t.progetto.nome if t.progetto else "?"
                    ore_per_task.append({
                        "task_nome": t.nome,
                        "progetto": proj_nome,
                        "ore": float(c.ore_dichiarate),
                    })
                    totale += float(c.ore_dichiarate)

        if ore_per_task:
            risultato.append({
                "dipendente_id": did,
                "nome": dip["nome"],
                "profilo": dip["profilo"],
                "ore_contrattuali": int(dip["ore_sett"]),
                "totale_ore": round(totale, 1),
                "ore_per_task": ore_per_task,
                "compilato": True,
            })

    # Aggiungi dipendenti che NON hanno compilato (con almeno 1 task attivo).
    # Conteggio task attivi per dipendente fatto in UNA query aggregata,
    # invece di un filtro DataFrame per ciascuno.
    dipendenti_attivi = session.query(Dipendente).filter(Dipendente.attivo == True).all()
    task_count_rows = session.query(
        Task.dipendente_id, func.count(Task.id)
    ).filter(
        Task.stato.in_(["In corso", "Da iniziare"])
    ).group_by(Task.dipendente_id).all()
    task_count = {row[0]: row[1] for row in task_count_rows}
    session.close()

    ids_gia_presenti = {r["dipendente_id"] for r in risultato}
    for d in dipendenti_attivi:
        if d.id in ids_gia_presenti:
            continue
        if task_count.get(d.id, 0) > 0:
            risultato.append({
                "dipendente_id": d.id,
                "nome": d.nome,
                "profilo": d.profilo,
                "ore_contrattuali": int(d.ore_sett),
                "totale_ore": 0,
                "ore_per_task": [],
                "compilato": False,
            })

    return sorted(risultato, key=lambda x: (-x["compilato"], x["nome"]))


@router.get("/me")
def consuntivi_settimana_me(
    settimana: Optional[str] = Query(
        None,
        description="Lunedì della settimana in ISO (YYYY-MM-DD). Assente = "
                    "settimana corrente. Ammesse solo la corrente e la "
                    "precedente; qualsiasi giorno della settimana è accettato "
                    "e viene normalizzato al lunedì.",
    ),
    current_user: Utente = Depends(get_current_user),
):
    """Vista PERSONALE (Layout A'): «ecco cosa era previsto per te in questa
    settimana». Self intrinseco: il dipendente è l'utente loggato, niente
    parametro `dipendente_id`.

    Parte dai TASK del dipendente (non dai Consuntivi): la lista
    `task_settimana` contiene sempre i task da compilare, con le ore già
    dichiarate attaccate (0 se non ancora compilato). La logica riusabile
    sta in data.task_settimana_dipendente (la userà anche la Home-utente).

    Il param `settimana` serve al recupero all'indietro: chi non ha compilato
    entro domenica deve poter tornare sulla settimana scorsa. Si ferma lì —
    non si compila in anticipo e non si riscrive un mese fa. La
    normalizzazione al lunedì passa da data.lunedi_settimana (la stessa regola
    della scrittura: mai ricalcolarla qui).

    Attenzione alla differenza fra CONSULTABILE e COMPILABILE: la settimana
    scorsa è sempre consultabile (la si apre in sola lettura), ma è
    `compilabile` solo se incompleta. La guardia sulla scrittura sta su
    POST /salva, non qui.
    """
    if not current_user.dipendente_id:
        raise HTTPException(400, "Utente non collegato a un dipendente")

    try:
        dip = get_dipendente(current_user.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    disponibili = settimane_selezionabili(current_user.dipendente_id)

    if settimana is None:
        lun = lunedi_settimana()
    else:
        try:
            lun = lunedi_settimana(settimana)
        except ValueError:
            raise HTTPException(
                400,
                f"Settimana '{settimana}' non è una data ISO valida "
                f"(atteso YYYY-MM-DD)",
            )
        ammesse = [s["lunedi"] for s in disponibili]
        if lun.isoformat() not in ammesse:
            raise HTTPException(
                400,
                f"Settimana '{lun.isoformat()}' non consultabile: sono "
                f"ammesse solo la corrente e la precedente "
                f"({', '.join(ammesse)})",
            )

    task_settimana = task_settimana_dipendente(current_user.dipendente_id, lun)
    totale = sum(t["ore_consumate"] for t in task_settimana)

    return {
        "dipendente_id": current_user.dipendente_id,
        "nome": dip["nome"],
        "profilo": dip["profilo"],
        "ore_contrattuali": int(dip["ore_sett"]),
        "settimana": lun.isoformat(),
        "settimane_disponibili": disponibili,
        "totale_ore": round(totale, 1),
        "task_settimana": task_settimana,
        # ⚠️ DIVERGENZA NOTA — `compilato` e `compilabile` (dentro
        # settimane_disponibili) misurano due cose diverse e possono
        # contraddirsi:
        #   compilato   = totale_ore > 0, sui soli task VISIBILI questa
        #                 settimana. Vero appena si dichiara un'ora.
        #   compilabile = ore dichiarate + assenze < ore contrattuali, su
        #                 TUTTI i consuntivi del dip. Guarda la copertura.
        # Una settimana con 4h su 40 è `compilato: True` e `compilabile:
        # True` insieme. `compilato` è un contratto già consumato dal
        # frontend: si allinea quando rifacciamo la pagina, non prima.
        "compilato": totale > 0,
    }


@router.post("/salva")
def salva_consuntivo_endpoint(
    req: SalvaConsuntivoRequest,
    current_user: Utente = Depends(get_current_user),
):
    """Salva il consuntivo settimanale (Pattern Y: self-or-manager).

    La settimana di destinazione arriva dal body (`settimana`, opzionale) e
    viene normalizzata al lunedì da data.lunedi_settimana. Prima era
    `datetime.now()`, cioè il giorno della compilazione: vedi la docstring di
    salva_consuntivo per il meccanismo dei duplicati che ne seguiva.

    La guardia sta QUI, non solo nel frontend: si scrive sulla settimana
    corrente sempre, sulla precedente solo se ancora incompleta. Nascondere il
    bottone non è una guardia — la POST resta raggiungibile.
    """
    # User può salvare SOLO i propri consuntivi (anti-impersonation)
    if current_user.ruolo_app != "manager" and req.dipendente_id != current_user.dipendente_id:
        raise HTTPException(403, "Puoi salvare solo i tuoi consuntivi")

    try:
        dip = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    # Settimana bersaglio: sempre quella del DIPENDENTE consuntivato, non di
    # chi salva — un manager che compila per altri deve ricadere sulle
    # settimane aperte per quel dipendente.
    if req.settimana is None:
        lun = lunedi_settimana()
    else:
        try:
            lun = lunedi_settimana(req.settimana)
        except ValueError:
            raise HTTPException(
                400,
                f"Settimana '{req.settimana}' non è una data ISO valida "
                f"(atteso YYYY-MM-DD)",
            )

    disponibili = {s["lunedi"]: s for s in settimane_selezionabili(req.dipendente_id)}
    scelta = disponibili.get(lun.isoformat())
    if scelta is None:
        raise HTTPException(
            400,
            f"Settimana '{lun.isoformat()}' non compilabile: sono ammesse solo "
            f"la corrente e la precedente ({', '.join(disponibili)})",
        )
    if not scelta["compilabile"]:
        raise HTTPException(
            400,
            f"La {scelta['etichetta'].lower()} risulta già compilata: il "
            f"recupero è previsto per chi non ha compilato, non per rivedere "
            f"una settimana chiusa",
        )

    # Dopo le guardie sulla settimana: la nota di un blocco si valuta sulla
    # settimana bersaglio, che qui è ormai decisa.
    _valida_blocchi_motivati(req, lun)
    _valida_dichiarazioni_sottotask(req, lun)
    _valida_avanzamento_task(req, lun)

    if PERSISTENT_MODE:
        esito = salva_consuntivo(
            dipendente_id=req.dipendente_id,
            settimana=lun,
            ore_per_task=req.ore_per_task,
            stati_per_task=req.stati_per_task,
            note_per_task=req.note_per_task,
            giorni_sede=req.giorni_sede,
            giorni_remoto=req.giorni_remoto,
            ore_assenza=req.ore_assenza,
            tipo_assenza=req.tipo_assenza,
            nota_assenza=req.nota_assenza,
            # req.spese passa così com'è: None e [] hanno significati diversi
            # (vedi DTO). Il vecchio `req.spese if req.spese else None`
            # collassava [] su None, rendendo impossibile svuotare le spese.
            spese_lista=req.spese,
            avanzamenti_sottotask=req.avanzamenti_sottotask,
            ore_effettive_sottotask=req.ore_effettive_sottotask,
            bloccati_sottotask=req.bloccati_sottotask,
            note_sottotask=req.note_sottotask,
            percentuale_per_task=req.percentuale_per_task,
            ore_effettive_per_task=req.ore_effettive_per_task,
            viste_task=req.viste_task,
            viste_sottotask=req.viste_sottotask,
            ore_stimate_residue_per_task=req.ore_stimate_residue_per_task,
            ore_stimate_residue_sottotask=req.ore_stimate_residue_sottotask,
        )
        # `avvisi`: segnalazioni non bloccanti del motore ore-derivate (Step 4).
        # Lista vuota nel caso normale — il campo c'è sempre, così il client non
        # deve distinguere «assente» da «nessun avviso».
        return {
            "salvato": esito["ok"],
            "dipendente": dip["nome"],
            "settimana": lun.isoformat(),
            "avvisi": esito["avvisi"],
        }
    return {
        "salvato": True,
        "dipendente": dip["nome"],
        "settimana": lun.isoformat(),
        "avvisi": [],
        "nota": "Dati non persistenti (db non attivo)",
    }
