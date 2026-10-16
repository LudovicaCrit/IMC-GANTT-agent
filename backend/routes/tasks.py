"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/tasks.py — Router per endpoint /api/tasks
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint per la lettura e la modifica dei task, usati dal
Cantiere (creazione, modifica, dipendenze, eliminazione) e in lettura dalla
Consuntivazione e da Risorse.

ENDPOINT ESPOSTI
────────────────
┌───────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                      │ Metodo   │ Auth                │
├───────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/tasks                                │ GET      │ AUTH+FILTRO (Sc B)  │
│ /api/tasks/{task_id}/elimina              │ PATCH    │ require_manager     │
└───────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/tasks?progetto_id=P00X&profilo=XXX
   - AUTH+FILTRO (Scenario B): user vede solo i propri task; manager vede
     tutti i task aziendali.
   - Esclude task con stato "Eliminato" (soft delete).
   - Filtri opzionali: progetto_id, profilo.
   - Restituisce lista task con dati anagrafici (dipendente, progetto, fase).

2. PATCH /api/tasks/{task_id}/elimina
   - Manager-only.
   - Soft delete: cambia lo stato a "Eliminato" (non rimuove la riga).
   - 404 se task non esiste.
   - Per cancellare attività interne, vedi `routes/attivita_interne.py`
     (DELETE /api/attivita-interne/{id}, con regola Pattern Y).

PATTERN AUTH USATI
──────────────────
- `get_current_user` + filter manuale: per /tasks (Scenario B in lettura).
- `require_manager`: per le mutazioni (creazione, modifica, dipendenze,
  eliminazione).

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `aggiungi_task`, `modifica_task`,
  `sostituisci_dipendenze`.
- `models`: `Task`, `get_session` (lettura diretta Postgres).
- `data_db_impl._to_dt`: normalizza `Date` SQL → `datetime` a mezzanotte
  per preservare il formato ISO `YYYY-MM-DDT00:00:00` storicamente esposto
  dal DataFrame (pandas.Timestamp).
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
📌 TODO Blocco 2 roadmap (Macchina delle Fasi):
   `GET /api/tasks` andrà adattato per restituire i task strutturati per
   fase. Anche le modifiche dovranno coerentemente operare nel
   contesto della fase (un task appartiene a una fase, non solo a un
   progetto).

STORIA
──────
Estratto da main.py il 5 maggio 2026, dopo unificazione prefisso
/api/task → /api/tasks (commit precedente).
Letture migrate da DataFrame in cache a Postgres diretto il 21 maggio 2026
(handoff migrazione §6-ter), preservando iso-comportamento.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import joinedload

from deps import get_current_user, require_manager
from models import Utente, Task, get_session
from data import (
    get_dipendente,
    aggiungi_task, modifica_task,
    sostituisci_dipendenze,
)
from data_db_impl import _to_dt
from utils import get_oggi


# ── DTO ──────────────────────────────────────────────────────────────────
class DipendenzaInput(BaseModel):
    """Step 3.1 (25/05/2026): una dipendenza in input — sostituisce il vecchio
    campo `predecessore` stringa singola.

      - task_predecessore_id: id del task da cui dipende
      - tipo_dipendenza:      uno di TIPI_DIPENDENZA (FS/SS/FF/SF). Default 'FS'.
    """
    task_predecessore_id: str
    tipo_dipendenza: str = "FS"


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
def lista_tasks(
    progetto_id: Optional[str] = None,
    profilo: Optional[str] = None,
    current_user: Utente = Depends(get_current_user),
):
    """Lista task con filtri opzionali (Scenario B in lettura)."""
    # Step 3.1 (25/05/2026): selectinload sulle dipendenze entranti — 1 query
    # in più, evita N+1 sul nuovo campo `dipendenze`.
    from sqlalchemy.orm import selectinload
    session = get_session()
    # joinedload su progetto + fase_rel: evita N+1 nel render del nome
    # progetto e del nome fase.
    q = session.query(Task).options(
        joinedload(Task.progetto),
        joinedload(Task.fase_rel),
        selectinload(Task.dipendenze_entranti),
    ).filter(Task.stato != "Eliminato")
    # Scenario B: user vede solo i propri task, manager vede tutto
    if current_user.ruolo_app != "manager":
        q = q.filter(Task.dipendente_id == current_user.dipendente_id)
    if progetto_id:
        q = q.filter(Task.progetto_id == progetto_id)
    if profilo:
        q = q.filter(Task.profilo_richiesto == profilo)
    tasks = q.all()
    session.close()

    result = []
    for t in tasks:
        dip = get_dipendente(t.dipendente_id)
        result.append({
            "id": t.id,
            "nome": t.nome,
            "progetto_id": t.progetto_id,
            "progetto_nome": t.progetto.nome if t.progetto else "",
            "fase": t.fase_rel.nome if t.fase_rel else "",
            "stato": t.stato,
            "ore_stimate": int(t.ore_stimate or 0),
            "data_inizio": _to_dt(t.data_inizio).isoformat() if t.data_inizio else None,
            "data_fine": _to_dt(t.data_fine).isoformat() if t.data_fine else None,
            "profilo_richiesto": t.profilo_richiesto or "",
            "dipendente_id": t.dipendente_id or "",
            "dipendente_nome": dip["nome"],
            # Step 3.1 (25/05/2026): era `"predecessore": t.predecessore or ""`.
            # Ora lista tipizzata dalla tabella dipendenza_task.
            "dipendenze": [
                {"task_predecessore_id": d.task_predecessore_id,
                 "tipo_dipendenza": d.tipo_dipendenza}
                for d in t.dipendenze_entranti
            ],
        })
    return result


# ═════════════════════════════════════════════════════════════════════════
# CRUD task singolo (Step 2.4 Cantiere — handoff v15 §2.4)
# ═════════════════════════════════════════════════════════════════════════
# Endpoint POST/PATCH dedicati al Cantiere: il PM aggiunge un task a una fase
# esistente o modifica un task esistente.
#
# Risoluzione fase: il body accetta sia `fase_id` (FK diretto, preferito)
# sia `fase` come stringa (nome fase risolta server-side). Step 2.1 D1.

class NuovoTaskSingolo(BaseModel):
    """Body per POST /api/tasks (Cantiere)."""
    progetto_id: str
    nome: str
    fase_id: Optional[int] = None        # se passato, ha priorità su `fase`
    fase: Optional[str] = None           # nome fase (risolto a fase_id)
    ore_stimate: int = 0
    data_inizio: Optional[str] = None    # ISO
    data_fine: Optional[str] = None      # ISO
    profilo_richiesto: str = ""
    dipendente_id: str = ""
    # Step 3.1 (25/05/2026): era `predecessore: str` (singolo, implicitamente
    # FS). Ora lista tipizzata che andrà in `dipendenza_task`. Vedi
    # DipendenzaInput sopra.
    dipendenze: list[DipendenzaInput] = []
    stato: str = "Da iniziare"


class ModificaTaskSingolo(BaseModel):
    """Body per PATCH /api/tasks/{task_id}. Tutti i campi opzionali.

    Step 3.1 (25/05/2026): il campo `predecessore` è stato RIMOSSO da questo
    DTO. La modifica delle dipendenze tra task richiede un endpoint dedicato
    che non è ancora esposto — sarà parte del design di Cantiere
    (vedi PIANO_3_MIGRATION.md e handoff v19).

    Comportamento noto sui campi ignorati: Pydantic v2 con la config di
    default (`extra="ignore"`) scarta in silenzio i campi non dichiarati.
    Se un client invia ancora `predecessore` in PATCH, succede uno dei due:
      - payload SOLO `predecessore`: il PATCH risponde 400 "Nessun campo da
        modificare" — errore visibile, OK.
      - payload `predecessore` + altri campi validi: gli altri vengono
        applicati e `predecessore` ignorato → SILENT PARTIAL SUCCESS (il
        client crede di aver impostato la dipendenza, non è così).
    Accettato come comportamento noto per la Migration #1 (limitato e
    tracciato qui), da rivedere quando Cantiere avrà l'endpoint dedicato
    alla modifica delle dipendenze.
    """
    nome: Optional[str] = None
    fase_id: Optional[int] = None
    ore_stimate: Optional[int] = None
    data_inizio: Optional[str] = None
    data_fine: Optional[str] = None
    profilo_richiesto: Optional[str] = None
    dipendente_id: Optional[str] = None
    stato: Optional[str] = None


@router.post("", status_code=201)
def crea_task_singolo(req: NuovoTaskSingolo, _: Utente = Depends(require_manager)):
    """Crea un task singolo in una fase esistente del progetto.

    Risoluzione fase:
    - Se `fase_id` è fornito, viene usato direttamente.
    - Altrimenti `fase` (stringa) viene risolta cercando nella tabella
      `fasi` per (progetto_id, nome). Pattern di D1.
    - Se nessuno dei due è fornito o la stringa non matcha, HTTP 422.
    """
    from models import get_session, Fase

    # Risoluzione fase_id
    fase_id = req.fase_id
    if fase_id is None and req.fase:
        session = get_session()
        try:
            fase_row = session.query(Fase).filter(
                Fase.progetto_id == req.progetto_id,
                Fase.nome == req.fase
            ).first()
            if fase_row:
                fase_id = fase_row.id
        finally:
            session.close()

    if fase_id is None:
        raise HTTPException(
            status_code=422,
            detail=f"Devi specificare 'fase_id' oppure una 'fase' che corrisponda a una "
                   f"fase esistente del progetto {req.progetto_id}."
        )

    # Risolvi nome fase + date (per validazione date task vs fase)
    from models import get_session as _gs
    session = _gs()
    try:
        fase_row = session.query(Fase).filter(Fase.id == fase_id).first()
        if not fase_row or fase_row.progetto_id != req.progetto_id:
            raise HTTPException(
                status_code=422,
                detail=f"Fase id {fase_id} non esiste o non appartiene a {req.progetto_id}."
            )
        nome_fase = fase_row.nome
        fase_data_inizio = fase_row.data_inizio
        fase_data_fine = fase_row.data_fine
    finally:
        session.close()

    # Parse date
    di = datetime.fromisoformat(req.data_inizio) if req.data_inizio else get_oggi()
    df = datetime.fromisoformat(req.data_fine) if req.data_fine else get_oggi()

    # Validazione coerenza date (Step 2.4-bis §14.2)
    # Validazione coerenza date (Step 2.4-bis §14.2 + 18 mag §14.6 retroattivo)
    if df < di:
        raise HTTPException(
            status_code=422,
            detail="data_fine non può precedere data_inizio."
        )
    # Vincolo "non pianificare nel passato" alla creazione (handoff v17).
    # In modifica un task esistente può avere data_inizio nel passato
    # (è iniziato davvero), quindi questo check vale solo in POST.
    oggi_date = get_oggi().date()
    if di.date() < oggi_date:
        raise HTTPException(
            status_code=422,
            detail=f"Non puoi creare un task con data_inizio nel passato "
                   f"({di.date()} < oggi {oggi_date}). Per task già iniziati, "
                   f"crea con data_inizio = oggi e poi aggiorna successivamente."
        )
    if fase_data_inizio and di.date() < fase_data_inizio:
        raise HTTPException(
            status_code=422,
            detail=f"Il task inizia ({di.date()}) prima della fase '{nome_fase}' "
                   f"({fase_data_inizio}). Estendi prima le date della fase."
        )
    if fase_data_fine and df.date() > fase_data_fine:
        raise HTTPException(
            status_code=422,
            detail=f"Il task finisce ({df.date()}) dopo la fase '{nome_fase}' "
                   f"({fase_data_fine}). Estendi prima le date della fase."
        )

    # Normalizza FK: stringa vuota → None (Postgres rifiuta '' come FK valido)
    dip_id = req.dipendente_id or None

    try:
        new_id = aggiungi_task(
            progetto_id=req.progetto_id,
            nome=req.nome,
            fase=nome_fase,
            ore_stimate=req.ore_stimate,
            data_inizio=di,
            data_fine=df,
            stato=req.stato,
            profilo_richiesto=req.profilo_richiesto,
            dipendente_id=dip_id,
            # Step 3.1 (25/05/2026): era `predecessore=pred` (stringa singola).
            # `aggiungi_task` valida le dipendenze a monte (predecessori
            # esistenti, no self-loop, no duplicati, tipo ammesso) e converte
            # ValueError → HTTP 422 sotto.
            dipendenze=[d.model_dump() for d in req.dipendenze],
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {"id": new_id, "nome": req.nome, "fase_id": fase_id}


class SostituisciDipendenzeRequest(BaseModel):
    """Body per PUT /api/tasks/{task_id}/dipendenze (Step 3.1 Gruppo B).

    Sostituisce l'INTERA lista di dipendenze entranti del task (approccio
    "replace", più prevedibile di add/remove singoli). Lista vuota → rimuove
    tutte le dipendenze entranti del task. Riusa `DipendenzaInput`.
    """
    dipendenze: list[DipendenzaInput] = []


@router.put("/{task_id}/dipendenze")
def sostituisci_dipendenze_task(
    task_id: str,
    req: SostituisciDipendenzeRequest,
    _: Utente = Depends(require_manager),
):
    """Sostituisce le dipendenze entranti di un task esistente (replace).

    Step 3.1 (Gruppo B): colma il debito annunciato in ModificaTaskSingolo —
    le dipendenze, impostabili finora solo alla creazione (POST), ora si
    modificano qui su un task già esistente.

    La validazione vive in `data.sostituisci_dipendenze` (task esistente,
    predecessori esistenti, no self-loop, no duplicati/coppia UNIQUE, tipo
    ammesso): ogni violazione → ValueError → HTTP 400 con messaggio chiaro,
    senza far emergere FK/UNIQUE grezzi. Restituisce la lista aggiornata.
    """
    try:
        dipendenze = sostituisci_dipendenze(
            task_id, [d.model_dump() for d in req.dipendenze]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"task_id": task_id, "dipendenze": dipendenze}


@router.patch("/{task_id}")
def modifica_task_singolo(
    task_id: str,
    req: ModificaTaskSingolo,
    _: Utente = Depends(require_manager),
):
    """Modifica campi di un task esistente.

    Tutti i campi sono opzionali (semantica PATCH). Date come stringhe ISO
    vengono convertite a `date`. Cambio fase: passare `fase_id` numerico.

    422 anche se la modifica lascerebbe il task "In corso" senza assegnatario
    (Step 4, 06/08/2026 — vedi la guardia in fondo alla funzione).
    """
    kwargs = {}
    payload = req.model_dump(exclude_unset=True)

    # Campi FK: stringa vuota → None (Postgres rifiuta '' come FK valido)
    # Step 3.1 (25/05/2026): rimosso "predecessore" dalla tupla — il campo
    # non è più nel DTO ModificaTaskSingolo (vedi sua docstring).
    CAMPI_FK = ("dipendente_id",)

    for k, v in payload.items():
        if k in ("data_inizio", "data_fine") and v is not None:
            kwargs[k] = datetime.fromisoformat(v).date()
        elif k in CAMPI_FK and v == "":
            kwargs[k] = None
        else:
            kwargs[k] = v

    if not kwargs:
        raise HTTPException(status_code=400, detail="Nessun campo da modificare.")

    # Validazione coerenza date (Step 2.4-bis §14.2)
    # Se modifico almeno una delle due date, devo verificare la coerenza con la fase
    if "data_inizio" in kwargs or "data_fine" in kwargs:
        # Solo `Fase`: `Task` e `get_session` arrivano dall'import di modulo
        # (riga 101). Reimportarli QUI li renderebbe locali all'INTERA funzione
        # — Python decide lo scope per funzione, non per blocco — e la guardia
        # assegnatario più sotto troverebbe `Task` non inizializzato ogni volta
        # che questo ramo non gira, cioè su ogni PATCH senza date.
        from models import Fase
        session = get_session()
        try:
            task_row = session.query(Task).filter(Task.id == task_id).first()
            if not task_row:
                raise HTTPException(status_code=404, detail=f"Task '{task_id}' non trovato")
            # Date finali dopo la modifica
            nuova_di = kwargs.get("data_inizio", task_row.data_inizio)
            nuova_df = kwargs.get("data_fine", task_row.data_fine)
            if nuova_df < nuova_di:
                raise HTTPException(
                    status_code=422,
                    detail="data_fine non può precedere data_inizio."
                )
            # Date della fase
            fase_row = session.query(Fase).filter(Fase.id == task_row.fase_id).first()
            if fase_row:
                if fase_row.data_inizio and nuova_di < fase_row.data_inizio:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Il task inizierebbe ({nuova_di}) prima della fase "
                               f"'{fase_row.nome}' ({fase_row.data_inizio})."
                    )
                if fase_row.data_fine and nuova_df > fase_row.data_fine:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Il task finirebbe ({nuova_df}) dopo la fase "
                               f"'{fase_row.nome}' ({fase_row.data_fine})."
                    )
        finally:
            session.close()

    # ── Guardia: nessun task in lavorazione senza assegnatario ────────────
    # Step 4 sottotask (06/08/2026). Un task può stare senza assegnatario
    # finché è in pianificazione; quando entra in lavorazione ("In corso")
    # l'assegnatario è dovuto.
    #
    # Si valuta lo stato FINALE — il merge del body sulla riga corrente — non
    # i due campi isolati. Un PATCH che porta insieme stato="In corso" e
    # dipendente_id è un avvio con assegnazione contestuale, ed è LEGITTIMO:
    # guardando il solo `dipendente_id` a DB (ancora NULL) lo rifiuteremmo,
    # costringendo il PM a due richieste per un'operazione sola.
    # Simmetricamente, il merge intercetta anche il caso opposto — togliere
    # l'assegnatario a un task GIÀ "In corso" — che produce esattamente lo
    # stato che la regola vieta. L'invariante presidiato è «un task In corso
    # ha un assegnatario», non solo «l'istante della transizione».
    #
    # La guardia sta QUI e non in `modifica_task`: quella è attraversata anche
    # dalla propagazione di `salva_blocchi_settimana`, dove a scrivere è il dipendente
    # che dichiara «ci sto lavorando». L'obbligo è del PM che avvia il task dal
    # Cantiere, non di chi lo consuntiva — vedi il commento gemello in
    # `data_db_impl.aggiungi_task`.
    if "stato" in kwargs or "dipendente_id" in kwargs:
        session = get_session()
        try:
            task_row = session.query(Task).filter(Task.id == task_id).first()
            # Riga inesistente: nessun 404 qui, ci pensa `modifica_task` sotto
            # ritornando False — un solo punto per quel messaggio.
            if task_row is not None:
                stato_finale = kwargs.get("stato", task_row.stato)
                dip_finale = kwargs.get("dipendente_id", task_row.dipendente_id)
                if stato_finale == "In corso" and not dip_finale:
                    # Due modi di violare lo stesso invariante, due messaggi:
                    # dire «non può passare In corso» a chi sta rimuovendo
                    # l'assegnatario di un task che già ci si trova manderebbe
                    # il PM a cercare una transizione che non ha chiesto.
                    if task_row.stato != "In corso":
                        motivo = (
                            f"non può passare in stato 'In corso' senza "
                            f"assegnatario: un task che entra in lavorazione "
                            f"deve avere un responsabile. Indica "
                            f"`dipendente_id` nella stessa richiesta"
                        )
                    else:
                        motivo = (
                            f"è 'In corso': non puoi rimuoverne l'assegnatario "
                            f"senza indicarne un altro. Un task in lavorazione "
                            f"deve sempre avere un responsabile"
                        )
                    raise HTTPException(
                        status_code=422,
                        detail=f"Il task '{task_id}' {motivo}."
                    )
        finally:
            session.close()

    ok = modifica_task(task_id, **kwargs)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' non trovato")
    return {"id": task_id, "aggiornato": True}


@router.patch("/{task_id}/elimina")
def elimina_task_generico(task_id: str, _: Utente = Depends(require_manager)):
    """Elimina (soft) qualsiasi task cambiando lo stato a 'Eliminato'."""
    session = get_session()
    task = session.query(Task).filter(Task.id == task_id).first()
    session.close()
    if task is None:
        raise HTTPException(404, "Task non trovato")

    task_nome = task.nome
    ok = modifica_task(task_id, stato="Eliminato")
    if ok:
        return {"ok": True, "messaggio": f"Task '{task_nome}' eliminato"}
    raise HTTPException(500, "Errore nell'eliminazione")
