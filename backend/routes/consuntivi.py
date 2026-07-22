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

    if PERSISTENT_MODE:
        ok = salva_consuntivo(
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
        )
        return {"salvato": ok, "dipendente": dip["nome"], "settimana": lun.isoformat()}
    return {
        "salvato": True,
        "dipendente": dip["nome"],
        "settimana": lun.isoformat(),
        "nota": "Dati non persistenti (db non attivo)",
    }
