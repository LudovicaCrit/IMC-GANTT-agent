"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/tasks.py — Router per endpoint /api/tasks
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint per la lettura e modifica di task. È usato da
molteplici pagine del frontend:
  - GANTT (lettura)
  - Tavolo di Lavoro (applica modifiche)
  - Pipeline (applica per "Conferma e avvia progetto")
  - Analisi e Interventi (applica)

ENDPOINT ESPOSTI
────────────────
┌───────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                      │ Metodo   │ Auth                │
├───────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/tasks                                │ GET      │ AUTH+FILTRO (Sc B)  │
│ /api/tasks/applica                        │ POST     │ require_manager     │
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

2. POST /api/tasks/applica
   - Manager-only.
   - Body: {modifiche, nuovi_task, progetto_id, cambia_stato_progetto}
   - APPLICA le modifiche ai dati reali (modifica task, crea task, cambia
     stato progetto se richiesto).
   - Restituisce: risultati per ogni operazione, nuovi task ids, stato
     progetto cambiato.
   - Usato dai bottoni "Applica" / "Conferma e avvia progetto".

3. PATCH /api/tasks/{task_id}/elimina
   - Manager-only.
   - Soft delete: cambia lo stato a "Eliminato" (non rimuove la riga).
   - 404 se task non esiste.
   - Per cancellare attività interne, vedi `routes/attivita_interne.py`
     (DELETE /api/attivita-interne/{id}, con regola Pattern Y).

PATTERN AUTH USATI
──────────────────
- `get_current_user` + filter manuale: per /tasks (Scenario B in lettura).
- `require_manager`: per applica, elimina (mutazioni
  che impattano l'intero progetto/azienda).

NOTA STORICA — UNIFICAZIONE PREFISSO TASK
─────────────────────────────────────────
Fino al 5 maggio 2026 esistevano DUE prefissi divergenti:
  /api/task/*  (singolare): anteprima-impatto, applica
  /api/tasks/* (plurale):   lista, elimina
Eredità di scrittura non uniforme di main.py originale, senza ragione
tecnica. Il commit di refactoring del 5 maggio 2026 ha rinominato
tutti gli endpoint singolari al plurale, allineando frontend api.js.
Ora tutti i 4 endpoint vivono coerentemente sotto /api/tasks/*.

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `aggiungi_task`, `modifica_task`,
  `cambia_stato_progetto`.
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
   fase. Anche le modifiche/applica dovranno coerentemente operare nel
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
    aggiungi_task, modifica_task, cambia_stato_progetto,
)
from data_db_impl import _to_dt
from utils import get_oggi


# ── DTO ──────────────────────────────────────────────────────────────────
class AzioneModifica(BaseModel):
    task_id: str
    campo: str           # "data_fine", "data_inizio", "dipendente_id", "ore_stimate", "stato"
    nuovo_valore: str    # tutto come stringa, il backend converte


class DipendenzaInput(BaseModel):
    """Step 3.1 (25/05/2026): una dipendenza in input — sostituisce il vecchio
    campo `predecessore` stringa singola. Vedi alembic e5f6a7b8c9d0.

      - task_predecessore_id: id del task da cui dipende
      - tipo_dipendenza:      uno di TIPI_DIPENDENZA (FS/SS/FF/SF). Default 'FS'.
    """
    task_predecessore_id: str
    tipo_dipendenza: str = "FS"


class NuovoTask(BaseModel):
    nome: str
    fase: str = ""
    ore_stimate: int = 0
    data_inizio: str = ""        # ISO format
    data_fine: str = ""          # ISO format
    profilo_richiesto: str = ""
    dipendente_id: str = ""
    # Step 3.1 (25/05/2026): era `predecessore: str` (singolo, implicitamente
    # FS). Ora lista tipizzata che andrà in `dipendenza_task`. Vedi alembic
    # e5f6a7b8c9d0.
    dipendenze: list[DipendenzaInput] = []
    stato: str = "Da iniziare"


class ApplicaRequest(BaseModel):
    """Richiesta di applicazione reale — modifica i dati."""
    modifiche: list[AzioneModifica] = []
    nuovi_task: list[NuovoTask] = []
    progetto_id: str = ""
    cambia_stato_progetto: str = ""


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
    # in più, evita N+1 sul nuovo campo `dipendenze` (vedi alembic e5f6a7b8c9d0).
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
# esistente o modifica un task esistente. Questo è diverso dal pattern del
# Tavolo di Lavoro (`/applica`) che applica MODIFICHE BATCH simulate.
#
# Risoluzione fase: il body accetta sia `fase_id` (FK diretto, preferito)
# sia `fase` come stringa (nome fase risolta server-side, retrocompatibile
# con l'IA `/agent/suggerisci-task` che produce stringhe). Step 2.1 D1.

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
    # DipendenzaInput sopra + alembic e5f6a7b8c9d0.
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


@router.patch("/{task_id}")
def modifica_task_singolo(
    task_id: str,
    req: ModificaTaskSingolo,
    _: Utente = Depends(require_manager),
):
    """Modifica campi di un task esistente.

    Tutti i campi sono opzionali (semantica PATCH). Date come stringhe ISO
    vengono convertite a `date`. Cambio fase: passare `fase_id` numerico.
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
        from models import get_session as _gs, Task, Fase
        session = _gs()
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

    ok = modifica_task(task_id, **kwargs)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' non trovato")
    return {"id": task_id, "aggiornato": True}


@router.post("/applica")
def applica_modifiche(req: ApplicaRequest, _: Utente = Depends(require_manager)):
    """Applica le modifiche ai dati reali.

    Usato sia da Analisi e Interventi (bottone Applica)
    sia da Pipeline (Conferma e avvia progetto).
    """
    risultati = []

    # 1) Applica modifiche a task esistenti
    for mod in req.modifiche:
        # Step 3.1 (25/05/2026): predecessore non è più un campo del task —
        # le dipendenze vivono in `dipendenza_task`. Senza questo check
        # esplicito, `modifica_task` ignorerebbe il campo via hasattr-guard
        # ma risponderebbe ok=True → silent failure ingannevole. Rifiuto
        # esplicito con motivo. La modifica delle dipendenze richiede
        # endpoint dedicato (futuro, design Cantiere).
        if mod.campo == "predecessore":
            risultati.append({
                "task_id": mod.task_id,
                "campo": mod.campo,
                "applicato": False,
                "motivo": "Il campo 'predecessore' non esiste più (Step 3.1). "
                          "Le dipendenze si modificano via endpoint dedicato.",
            })
            continue

        valore = mod.nuovo_valore
        if mod.campo in ("data_inizio", "data_fine"):
            valore = datetime.fromisoformat(valore)
        elif mod.campo == "ore_stimate":
            valore = int(valore)

        ok = modifica_task(mod.task_id, **{mod.campo: valore})
        risultati.append({
            "task_id": mod.task_id,
            "campo": mod.campo,
            "applicato": ok,
        })

    # 2) Crea nuovi task
    nuovi_ids = []
    for nt in req.nuovi_task:
        try:
            new_id = aggiungi_task(
                progetto_id=req.progetto_id,
                nome=nt.nome,
                fase=nt.fase,
                ore_stimate=nt.ore_stimate,
                data_inizio=datetime.fromisoformat(nt.data_inizio) if nt.data_inizio else get_oggi(),
                data_fine=datetime.fromisoformat(nt.data_fine) if nt.data_fine else get_oggi(),
                stato=nt.stato,
                profilo_richiesto=nt.profilo_richiesto,
                dipendente_id=nt.dipendente_id,
                # Step 3.1 (25/05/2026): era `predecessore=nt.predecessore`.
                # Vedi DipendenzaInput in cima al file.
                dipendenze=[d.model_dump() for d in nt.dipendenze],
            )
        except ValueError as e:
            # Step 2.1 D1: aggiungi_task lancia ValueError se la stringa fase
            # non corrisponde a nessuna Fase del progetto.
            # Step 3.1: aggiungi_task lancia ValueError anche per dipendenze
            # invalide (predecessori inesistenti, self-loop, duplicati,
            # tipo non ammesso). Stesso 422 al chiamante.
            raise HTTPException(status_code=422, detail=str(e))
        nuovi_ids.append(new_id)
        risultati.append({
            "task_id": new_id,
            "campo": "creato",
            "applicato": True,
        })

    # 3) Cambia stato progetto se richiesto
    stato_cambiato = False
    if req.cambia_stato_progetto and req.progetto_id:
        stato_cambiato = cambia_stato_progetto(req.progetto_id, req.cambia_stato_progetto)

    return {
        "risultati": risultati,
        "nuovi_task_ids": nuovi_ids,
        "stato_progetto_cambiato": stato_cambiato,
    }


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
