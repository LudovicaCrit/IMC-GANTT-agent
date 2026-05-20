"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/progetti.py — Router per endpoint /api/progetti
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint CRUD per i progetti aziendali, inclusi i progetti in
stato "Bozza". Una bozza è un progetto a tutti gli effetti (handoff v15
§3.3, Step 2.0 del Blocco 2 esteso) — non c'è più una tabella separata
`pianificazioni_bozza`.

Il GET con dati aggregati (ore consuntivate, tasso compilazione, task
completati) resta. POST/PATCH/DELETE aggiunti il 13 maggio 2026 nel
quadro di Step 2.0.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/progetti                    │ GET      │ require_manager (Scenario B) │
│ /api/progetti                    │ POST     │ require_manager              │
│ /api/progetti/{id}               │ PATCH    │ require_manager              │
│ /api/progetti/{id}               │ DELETE   │ require_manager (solo bozze) │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/progetti?stato=bozza|in esecuzione|sospeso|completato|annullato|attivi|all
   - Manager-only. Restituisce lista progetti con stato avanzamento.
   - Filtro `stato` opzionale (default: "attivi" = In esecuzione + Sospeso).
     Valori speciali: "all" (tutti), "attivi" (In esecuzione + Sospeso).
   - Default backward-compatible: chi consuma /api/progetti senza filtri
     riceve lo stesso subset di sempre (attivi + sospesi).

2. POST /api/progetti
   - Manager-only. Crea un nuovo progetto (bozza o attivo).
   - Body: ProgettoCreate (id opzionale, generato server-side se mancante).
   - Stato di default: "Bozza".

3. PATCH /api/progetti/{id}
   - Manager-only. Modifica anagrafica e/o stato.
   - Body: ProgettoUpdate (tutti i campi opzionali).
   - Transizioni di stato non vincolate qui. I vincoli (es. bozza→esecuzione
     richiede almeno una fase) sono responsabilità del frontend Cantiere/Wizard.

4. DELETE /api/progetti/{id}
   - Manager-only. Elimina un progetto **solo se in stato "Bozza"**.
     Gli altri stati hanno valore storico; per chiudere un progetto attivo
     si usa PATCH con stato="Annullato" o "Completato".
   - Cascata: fasi e task figli vengono eliminati (cascade già nel modello).

PATTERN AUTH USATI
──────────────────
- `require_manager`: dependency che blocca con 403 chi non è manager.

TODO R2 (ABAC): PATCH e DELETE potranno diventare PM-only sul progetto specifico.

DIPENDENZE
──────────
- `data`: `ore_consuntivate_progetto`, `tasso_compilazione_progetto`.
- `dataframes`: `_PROGETTI`, `_TASKS`.
- `data_db_impl`: `_next_progetto_id` per generazione id.
- `models`: `get_session`, `Utente`, `Progetto`.
- `deps`: `require_manager`.

STORIA
──────
- 5 mag 2026: estratto da main.py (refactoring strangler). Solo GET.
- 13 mag 2026: aggiunti POST/PATCH/DELETE + filtro stato nel quadro di
  Step 2.0 (handoff v15). Sostituisce in pratica routes/pianificazione.py
  per il caso d'uso "bozze di progetto".
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import require_manager
from models import (
    get_session, Utente, Progetto, Fase, Task, Assegnazione,
    STATI_PROGETTO, STATI_PROGETTO_ATTIVI,
)
from data import ore_consuntivate_progetto, tasso_compilazione_progetto
from data_db_impl import _next_progetto_id, genera_id_task_multipli, _reload
from dataframes import _PROGETTI, _TASKS


# ── DTO ──────────────────────────────────────────────────────────────────

# Stati ammessi: importati da models.STATI_PROGETTO (fonte di verità unica,
# allineata al CHECK constraint del DB tramite migration D3).
STATI_PROGETTO_AMMESSI = STATI_PROGETTO
STATI_ATTIVI = STATI_PROGETTO_ATTIVI


class ProgettoCreate(BaseModel):
    """Body per POST /api/progetti.

    Solo `nome` obbligatorio: coerente con la logica "bozza = anagrafica
    minima". Tutto il resto può essere completato dopo dal Cantiere/Wizard.
    """
    id: Optional[str] = Field(default=None, min_length=1, max_length=10)
    nome: str = Field(..., min_length=1, max_length=150)
    cliente: Optional[str] = Field(default=None, max_length=150)
    stato: str = Field(default="Bozza", max_length=30)
    tipologia: str = Field(default="ordinario", max_length=20)
    priorita: str = Field(default="media", max_length=10)
    ritardabilita: Optional[str] = Field(default="media", max_length=10)
    data_inizio: Optional[date_type] = None
    data_fine: Optional[date_type] = None
    budget_ore: Optional[int] = Field(default=None, ge=0)
    giornate_vendute: Optional[float] = Field(default=None, ge=0)
    valore_contratto: Optional[float] = Field(default=None, ge=0)
    descrizione: Optional[str] = None
    fase_corrente: Optional[str] = Field(default=None, max_length=80)
    sede: Optional[str] = Field(default=None, max_length=40)
    pm_id: Optional[str] = Field(default=None, max_length=10)
    scadenza_bando: Optional[date_type] = None
    note: Optional[str] = None


class ProgettoUpdate(BaseModel):
    """Body per PATCH /api/progetti/{id}. Tutti i campi opzionali."""
    nome: Optional[str] = Field(default=None, min_length=1, max_length=150)
    cliente: Optional[str] = Field(default=None, max_length=150)
    stato: Optional[str] = Field(default=None, max_length=30)
    tipologia: Optional[str] = Field(default=None, max_length=20)
    priorita: Optional[str] = Field(default=None, max_length=10)
    ritardabilita: Optional[str] = Field(default=None, max_length=10)
    data_inizio: Optional[date_type] = None
    data_fine: Optional[date_type] = None
    budget_ore: Optional[int] = Field(default=None, ge=0)
    giornate_vendute: Optional[float] = Field(default=None, ge=0)
    valore_contratto: Optional[float] = Field(default=None, ge=0)
    descrizione: Optional[str] = None
    fase_corrente: Optional[str] = Field(default=None, max_length=80)
    sede: Optional[str] = Field(default=None, max_length=40)
    pm_id: Optional[str] = Field(default=None, max_length=10)
    scadenza_bando: Optional[date_type] = None
    motivo_sospensione: Optional[str] = None
    lezioni_apprese: Optional[str] = None
    note: Optional[str] = None


# ── DTO endpoint transazionale (Step 2.7, 20/05/2026) ────────────────────
# Il Wizard di Cantiere crea progetto + fasi + task iniziali in un colpo.
# Questi DTO descrivono il body annidato di POST /api/progetti/completo.

class FaseCompleta(BaseModel):
    """Una fase nel body del Wizard. Lo stato è settato server-side."""
    nome: str = Field(..., min_length=1, max_length=100)
    ordine: int = Field(default=1, ge=1)
    data_inizio: Optional[date_type] = None
    data_fine: Optional[date_type] = None
    ore_vendute: float = Field(default=0, ge=0)


class TaskInizialeCompleto(BaseModel):
    """Un task iniziale opzionale. Referenzia la fase per INDICE (fase_idx)
    nella lista `fasi`, non per id: gli id delle fasi non esistono ancora
    quando il Wizard compone il body."""
    nome: str = Field(..., min_length=1, max_length=200)
    fase_idx: int = Field(..., ge=0)
    dipendente_id: Optional[str] = Field(default=None, max_length=10)
    ore_stimate: int = Field(default=0, ge=0)
    data_inizio: Optional[date_type] = None
    data_fine: Optional[date_type] = None


class ProgettoCompletoCreate(BaseModel):
    """Body per POST /api/progetti/completo.

    `progetto` riusa ProgettoCreate (anagrafica). `fasi` deve contenere
    almeno una fase. `task_iniziali` è opzionale (i task sono dinamici,
    si aggiungono nel tempo dal Cantiere — handoff §0.3).
    """
    progetto: ProgettoCreate
    fasi: list[FaseCompleta] = Field(..., min_length=1)
    task_iniziali: list[TaskInizialeCompleto] = Field(default_factory=list)


class TaskStaffing(BaseModel):
    """Un task aggiunto a una fase ESISTENTE (staffing progressivo).

    Differenza da TaskInizialeCompleto: qui la fase esiste già nel DB,
    quindi si referenzia per `fase_id` reale, non per indice.
    """
    nome: str = Field(..., min_length=1, max_length=200)
    fase_id: int = Field(..., ge=1)
    dipendente_id: Optional[str] = Field(default=None, max_length=10)
    ore_stimate: int = Field(default=0, ge=0)
    data_inizio: Optional[date_type] = None
    data_fine: Optional[date_type] = None
    predecessore: Optional[str] = Field(default=None, max_length=10)


class StaffingRequest(BaseModel):
    """Body per POST /api/progetti/{id}/task-multipli.

    Aggiunge uno o più task a fasi esistenti di un progetto attivo/sospeso,
    in un'unica transazione (principio del dinamismo, handoff §0.3).
    """
    task: list[TaskStaffing] = Field(..., min_length=1)





# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/progetti", tags=["progetti"])


def _is_nat(v) -> bool:
    """Verifica robusta per NaT/NaN/None su valori pandas."""
    import pandas as pd
    try:
        return pd.isna(v)
    except (TypeError, ValueError):
        return False


def _serializza_progetto_con_aggregati(p) -> dict:
    """Serializza una riga DataFrame progetto con dati aggregati."""
    ore_cons = ore_consuntivate_progetto(p["id"])
    tasso = tasso_compilazione_progetto(p["id"])
    tasks_proj = _TASKS()[_TASKS()["progetto_id"] == p["id"]]
    completati = len(tasks_proj[tasks_proj["stato"] == "Completato"])

    def _opt(v, conv=lambda x: x):
        if v is None or _is_nat(v):
            return None
        try:
            return conv(v)
        except (ValueError, TypeError):
            return None

    return {
        "id": p["id"],
        "nome": p["nome"],
        "cliente": p.get("cliente"),
        "stato": p["stato"],
        "tipologia": p.get("tipologia", "ordinario"),
        "data_inizio": _opt(p.get("data_inizio"), lambda d: d.isoformat()),
        "data_fine": _opt(p.get("data_fine"), lambda d: d.isoformat()),
        "budget_ore": _opt(p.get("budget_ore"), int),
        "valore_contratto": _opt(p.get("valore_contratto"), float),
        "fase_corrente": p.get("fase_corrente"),
        "pm_id": p.get("pm_id"),
        "ore_consuntivate": float(ore_cons),
        "tasso_compilazione": round(tasso, 1),
        "task_completati": completati,
        "task_totali": len(tasks_proj),
    }


@router.get("")
def lista_progetti(stato: Optional[str] = None, _: Utente = Depends(require_manager)):
    """Lista progetti con stato avanzamento (manager-only).

    Filtro opzionale `?stato=`:
      - omesso o "attivi": In esecuzione + Sospeso (default backward-compat)
      - "bozza": solo bozze (per Cantiere "In cantiere")
      - "all": tutti i progetti
      - altro: filtro singolo case-insensitive su `stato`
    """
    df = _PROGETTI()

    if stato is None or stato.lower() == "attivi":
        df = df[df["stato"].isin(STATI_ATTIVI)]
    elif stato.lower() == "all":
        pass
    else:
        df = df[df["stato"].str.lower() == stato.lower()]

    return [_serializza_progetto_con_aggregati(p) for _, p in df.iterrows()]


@router.post("", status_code=201)
def crea_progetto(req: ProgettoCreate, _: Utente = Depends(require_manager)):
    """Crea un nuovo progetto (bozza di default).

    L'id è generato server-side se non specificato (formato P###).
    """
    if req.stato not in STATI_PROGETTO_AMMESSI:
        raise HTTPException(
            status_code=422,
            detail=f"Stato '{req.stato}' non ammesso. Valori: {STATI_PROGETTO_AMMESSI}"
        )

    session = get_session()
    try:
        progetto_id = req.id or _next_progetto_id()

        if session.query(Progetto).filter(Progetto.id == progetto_id).first():
            raise HTTPException(status_code=409, detail=f"Progetto id '{progetto_id}' già esistente")

        nuovo = Progetto(
            id=progetto_id,
            nome=req.nome,
            cliente=req.cliente,
            stato=req.stato,
            tipologia=req.tipologia,
            priorita=req.priorita,
            ritardabilita=req.ritardabilita,
            data_inizio=req.data_inizio,
            data_fine=req.data_fine,
            budget_ore=req.budget_ore,
            giornate_vendute=req.giornate_vendute,
            valore_contratto=req.valore_contratto,
            descrizione=req.descrizione,
            fase_corrente=req.fase_corrente,
            sede=req.sede,
            pm_id=req.pm_id,
            scadenza_bando=req.scadenza_bando,
            note=req.note,
        )
        session.add(nuovo)
        session.commit()
        _reload()  # invalida cache DataFrame: il nuovo progetto è subito visibile alle GET
        return {"id": progetto_id, "nome": req.nome, "stato": req.stato}
    finally:
        session.close()


@router.post("/completo", status_code=201)
def crea_progetto_completo(req: ProgettoCompletoCreate, _: Utente = Depends(require_manager)):
    """Crea progetto + fasi + task iniziali in UN'UNICA TRANSAZIONE.

    Atomicità: una sola sessione, un solo commit finale. Se un qualunque
    passo fallisce, rollback totale — niente progetto orfano, niente fasi
    senza progetto. Vedi handoff Rischio 3.

    Differenza da POST /api/progetti (semplice): quello crea solo il
    progetto. Questo è il submit del Wizard di Cantiere (Step 2.7).
    """
    p = req.progetto

    # ── Validazioni preliminari (prima di toccare il DB) ─────────────────
    if p.stato not in STATI_PROGETTO_AMMESSI:
        raise HTTPException(
            status_code=422,
            detail=f"Stato '{p.stato}' non ammesso. Valori: {STATI_PROGETTO_AMMESSI}"
        )

    # Le ore vendute delle fasi devono quadrare col budget del progetto.
    # (Il Wizard lo verifica già lato UI, ma il backend non si fida del client.)
    totale_ore_fasi = sum(f.ore_vendute for f in req.fasi)
    if p.budget_ore is not None and totale_ore_fasi != p.budget_ore:
        raise HTTPException(
            status_code=422,
            detail=f"La somma delle ore vendute delle fasi ({totale_ore_fasi}h) "
                   f"non corrisponde al budget del progetto ({p.budget_ore}h)."
        )

    # Ogni task iniziale deve puntare a una fase esistente nella lista.
    for t in req.task_iniziali:
        if t.fase_idx >= len(req.fasi):
            raise HTTPException(
                status_code=422,
                detail=f"Il task '{t.nome}' referenzia la fase #{t.fase_idx}, "
                       f"ma sono state definite solo {len(req.fasi)} fasi."
            )

    # Retrodatazione task: ammessa SOLO se il progetto nasce "In esecuzione"
    # (decisione 20/05). Per Bozza e "Da iniziare" un task con data nel
    # passato è incoerente — il progetto non è ancora partito.
    oggi = date_type.today()
    consenti_date_passate = (p.stato == "In esecuzione")

    session = get_session()
    try:
        # ── 1. Progetto ──────────────────────────────────────────────────
        progetto_id = p.id or _next_progetto_id()
        if session.query(Progetto).filter(Progetto.id == progetto_id).first():
            raise HTTPException(
                status_code=409,
                detail=f"Progetto id '{progetto_id}' già esistente"
            )

        nuovo = Progetto(
            id=progetto_id, nome=p.nome, cliente=p.cliente, stato=p.stato,
            tipologia=p.tipologia, priorita=p.priorita, ritardabilita=p.ritardabilita,
            data_inizio=p.data_inizio, data_fine=p.data_fine, budget_ore=p.budget_ore,
            giornate_vendute=p.giornate_vendute, valore_contratto=p.valore_contratto,
            descrizione=p.descrizione, fase_corrente=p.fase_corrente, sede=p.sede,
            pm_id=p.pm_id, scadenza_bando=p.scadenza_bando, note=p.note,
        )
        session.add(nuovo)

        # ── 2. Fasi ──────────────────────────────────────────────────────
        # flush() invia le fasi al DB (così ottengono un id autoincrement)
        # SENZA renderle permanenti: restano dentro la transazione.
        fasi_orm = []
        for f in req.fasi:
            fase = Fase(
                progetto_id=progetto_id, nome=f.nome, ordine=f.ordine,
                data_inizio=f.data_inizio, data_fine=f.data_fine,
                ore_vendute=f.ore_vendute, ore_pianificate=None,
                stato="Da iniziare",
            )
            session.add(fase)
            fasi_orm.append(fase)
        session.flush()  # ora ogni fase_orm.id è valorizzato

        # ── 3. Task iniziali ─────────────────────────────────────────────
        # Gli id (T###) li ottengo in blocco dall'utility condivisa, che li
        # genera consecutivi e senza collisioni anche dentro la transazione
        # (vedi genera_id_task_multipli, debito #22).
        ids_task = genera_id_task_multipli(len(req.task_iniziali), session=session)

        for idx_t, t in enumerate(req.task_iniziali):
            fase_orm = fasi_orm[t.fase_idx]

            di = t.data_inizio
            df = t.data_fine
            # Coerenza date task
            if di and df and df < di:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}': data_fine precede data_inizio."
                )
            if di and di < oggi and not consenti_date_passate:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}': data_inizio nel passato ({di}) "
                           f"ammessa solo per progetti 'In esecuzione'."
                )
            # Coerenza date task ↔ fase
            if di and fase_orm.data_inizio and di < fase_orm.data_inizio:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}' inizia ({di}) prima della fase "
                           f"'{fase_orm.nome}' ({fase_orm.data_inizio})."
                )
            if df and fase_orm.data_fine and df > fase_orm.data_fine:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}' finisce ({df}) dopo la fase "
                           f"'{fase_orm.nome}' ({fase_orm.data_fine})."
                )

            task_id = ids_task[idx_t]

            task = Task(
                id=task_id, progetto_id=progetto_id, fase_id=fase_orm.id,
                nome=t.nome, ore_stimate=t.ore_stimate,
                data_inizio=di, data_fine=df,
                stato="Da iniziare",
                dipendente_id=t.dipendente_id or None,
                predecessore=None,
            )
            session.add(task)

            # Assegnazione: stesso comportamento di aggiungi_task() in
            # data_db_impl — se c'è un dipendente, gli si assegna il task.
            if t.dipendente_id:
                session.add(Assegnazione(
                    task_id=task_id, dipendente_id=t.dipendente_id,
                    ore_assegnate=t.ore_stimate, ruolo="responsabile",
                ))

        # ── 4. Commit unico: o tutto, o niente ───────────────────────────
        session.commit()
        _reload()  # invalida la cache DataFrame: tutto subito visibile alle GET

        return {
            "id": progetto_id,
            "nome": p.nome,
            "stato": p.stato,
            "n_fasi": len(req.fasi),
            "n_task": len(req.task_iniziali),
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Errore durante la creazione del progetto: {e}"
        )
    finally:
        session.close()


@router.put("/{progetto_id}/completo", status_code=200)
def completa_progetto(progetto_id: str, req: ProgettoCompletoCreate,
                      _: Utente = Depends(require_manager)):
    """Completa una BOZZA: aggiorna anagrafica e RIMPIAZZA fasi + task.

    Step 2.7 parte 2 (20/05/2026). È il submit del Wizard in modalità
    "Riprendi bozza". Differenze da POST /completo:
      - il progetto esiste già: si aggiorna, non si crea
      - le fasi/task vecchi della bozza vengono cancellati e ricreati
        ("replace"): semplice e sicuro perché una bozza non ha consuntivi
      - ammesso SOLO se il progetto è in stato 'Bozza' (un progetto attivo
        ha dati reali: cancellarne le fasi sarebbe distruttivo).

    Tutto in un'unica transazione: o l'intero completamento va a buon fine,
    o la bozza resta esattamente com'era.
    """
    p = req.progetto

    # ── Validazioni preliminari ──────────────────────────────────────────
    if p.stato not in STATI_PROGETTO_AMMESSI:
        raise HTTPException(
            status_code=422,
            detail=f"Stato '{p.stato}' non ammesso. Valori: {STATI_PROGETTO_AMMESSI}"
        )

    totale_ore_fasi = sum(f.ore_vendute for f in req.fasi)
    if p.budget_ore is not None and totale_ore_fasi != p.budget_ore:
        raise HTTPException(
            status_code=422,
            detail=f"La somma delle ore vendute delle fasi ({totale_ore_fasi}h) "
                   f"non corrisponde al budget del progetto ({p.budget_ore}h)."
        )

    for t in req.task_iniziali:
        if t.fase_idx >= len(req.fasi):
            raise HTTPException(
                status_code=422,
                detail=f"Il task '{t.nome}' referenzia la fase #{t.fase_idx}, "
                       f"ma sono state definite solo {len(req.fasi)} fasi."
            )

    oggi = date_type.today()
    consenti_date_passate = (p.stato == "In esecuzione")

    session = get_session()
    try:
        # ── 0. La bozza deve esistere ed essere in stato 'Bozza' ─────────
        progetto = session.query(Progetto).filter(Progetto.id == progetto_id).first()
        if not progetto:
            raise HTTPException(
                status_code=404,
                detail=f"Progetto '{progetto_id}' non trovato."
            )
        if progetto.stato != "Bozza":
            raise HTTPException(
                status_code=409,
                detail=f"Il completamento è ammesso solo per progetti in stato "
                       f"'Bozza'. Il progetto '{progetto_id}' è in stato "
                       f"'{progetto.stato}'. Usa il Cantiere per modificarlo."
            )

        # ── 1. Aggiorna anagrafica del progetto esistente ────────────────
        progetto.nome = p.nome
        progetto.cliente = p.cliente
        progetto.stato = p.stato
        progetto.tipologia = p.tipologia
        progetto.priorita = p.priorita
        progetto.ritardabilita = p.ritardabilita
        progetto.data_inizio = p.data_inizio
        progetto.data_fine = p.data_fine
        progetto.budget_ore = p.budget_ore
        progetto.giornate_vendute = p.giornate_vendute
        progetto.valore_contratto = p.valore_contratto
        progetto.descrizione = p.descrizione
        progetto.fase_corrente = p.fase_corrente
        progetto.sede = p.sede
        progetto.pm_id = p.pm_id
        progetto.scadenza_bando = p.scadenza_bando
        progetto.note = p.note

        # ── 2. Cancella le fasi vecchie (i task figli vanno via in cascata,
        #       Fase.task ha cascade="all, delete-orphan"). Sicuro perché
        #       una bozza non ha consuntivi agganciati.
        fasi_vecchie = session.query(Fase).filter(
            Fase.progetto_id == progetto_id
        ).all()
        for fv in fasi_vecchie:
            session.delete(fv)
        session.flush()  # esegui le DELETE prima di reinserire

        # ── 3. Ricrea le fasi ────────────────────────────────────────────
        fasi_orm = []
        for f in req.fasi:
            fase = Fase(
                progetto_id=progetto_id, nome=f.nome, ordine=f.ordine,
                data_inizio=f.data_inizio, data_fine=f.data_fine,
                ore_vendute=f.ore_vendute, ore_pianificate=None,
                stato="Da iniziare",
            )
            session.add(fase)
            fasi_orm.append(fase)
        session.flush()  # ogni fase_orm.id ora è valorizzato

        # ── 4. Ricrea i task iniziali ────────────────────────────────────
        ids_task = genera_id_task_multipli(len(req.task_iniziali), session=session)

        for idx_t, t in enumerate(req.task_iniziali):
            fase_orm = fasi_orm[t.fase_idx]
            di = t.data_inizio
            df = t.data_fine

            if di and df and df < di:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}': data_fine precede data_inizio."
                )
            if di and di < oggi and not consenti_date_passate:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}': data_inizio nel passato ({di}) "
                           f"ammessa solo per progetti 'In esecuzione'."
                )
            if di and fase_orm.data_inizio and di < fase_orm.data_inizio:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}' inizia ({di}) prima della fase "
                           f"'{fase_orm.nome}' ({fase_orm.data_inizio})."
                )
            if df and fase_orm.data_fine and df > fase_orm.data_fine:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}' finisce ({df}) dopo la fase "
                           f"'{fase_orm.nome}' ({fase_orm.data_fine})."
                )

            task_id = ids_task[idx_t]

            task = Task(
                id=task_id, progetto_id=progetto_id, fase_id=fase_orm.id,
                nome=t.nome, ore_stimate=t.ore_stimate,
                data_inizio=di, data_fine=df,
                stato="Da iniziare",
                dipendente_id=t.dipendente_id or None,
                predecessore=None,
            )
            session.add(task)

            if t.dipendente_id:
                session.add(Assegnazione(
                    task_id=task_id, dipendente_id=t.dipendente_id,
                    ore_assegnate=t.ore_stimate, ruolo="responsabile",
                ))

        # ── 5. Commit unico ──────────────────────────────────────────────
        session.commit()
        _reload()

        return {
            "id": progetto_id,
            "nome": p.nome,
            "stato": p.stato,
            "n_fasi": len(req.fasi),
            "n_task": len(req.task_iniziali),
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Errore durante il completamento della bozza: {e}"
        )
    finally:
        session.close()


@router.post("/{progetto_id}/task-multipli", status_code=201)
def aggiungi_task_multipli(progetto_id: str, req: StaffingRequest,
                           _: Utente = Depends(require_manager)):
    """Aggiunge più task a fasi esistenti di un progetto, in UNA transazione.

    Step 2.7 parte 3 (20/05/2026) — staffing progressivo. È il submit del
    mini-Wizard "Aggiungi task" del Cantiere. Principio del dinamismo
    (handoff §0.3): i task si sviluppano nel tempo, si aggiungono alle
    fasi man mano che il progetto procede.

    Vincoli:
      - il progetto deve essere 'In esecuzione' o 'Sospeso' (non Bozza:
        per le bozze si usa il completamento; non Completato/Annullato:
        sono chiusi).
      - ogni fase_id referenziato deve appartenere a QUESTO progetto.
      - retrodatazione task ammessa solo se il progetto è 'In esecuzione'.

    Atomicità: o entrano tutti i task, o nessuno.
    """
    oggi = date_type.today()

    session = get_session()
    try:
        # ── 0. Il progetto deve esistere ed essere attivo/sospeso ────────
        progetto = session.query(Progetto).filter(Progetto.id == progetto_id).first()
        if not progetto:
            raise HTTPException(
                status_code=404,
                detail=f"Progetto '{progetto_id}' non trovato."
            )
        if progetto.stato not in STATI_ATTIVI:
            raise HTTPException(
                status_code=409,
                detail=f"L'aggiunta di task è ammessa solo per progetti attivi o "
                       f"sospesi. Il progetto '{progetto_id}' è in stato "
                       f"'{progetto.stato}'."
            )
        consenti_date_passate = (progetto.stato == "In esecuzione")

        # ── 1. Carico le fasi del progetto, indicizzate per id ───────────
        fasi_progetto = {
            f.id: f for f in
            session.query(Fase).filter(Fase.progetto_id == progetto_id).all()
        }

        # ── 2. Valido ogni task PRIMA di inserire (fail-fast) ────────────
        for t in req.task:
            if t.fase_id not in fasi_progetto:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}': la fase #{t.fase_id} non esiste "
                           f"o non appartiene al progetto '{progetto_id}'."
                )
            fase = fasi_progetto[t.fase_id]
            di = t.data_inizio
            df = t.data_fine
            if di and df and df < di:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}': data_fine precede data_inizio."
                )
            if di and di < oggi and not consenti_date_passate:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}': data_inizio nel passato ({di}) "
                           f"ammessa solo per progetti 'In esecuzione'."
                )
            if di and fase.data_inizio and di < fase.data_inizio:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}' inizia ({di}) prima della fase "
                           f"'{fase.nome}' ({fase.data_inizio})."
                )
            if df and fase.data_fine and df > fase.data_fine:
                raise HTTPException(
                    status_code=422,
                    detail=f"Task '{t.nome}' finisce ({df}) dopo la fase "
                           f"'{fase.nome}' ({fase.data_fine})."
                )

        # ── 3. Inserisco i task (tutte le validazioni sono passate) ──────
        ids_task = genera_id_task_multipli(len(req.task), session=session)
        creati = []
        for idx_t, t in enumerate(req.task):
            task_id = ids_task[idx_t]
            task = Task(
                id=task_id, progetto_id=progetto_id, fase_id=t.fase_id,
                nome=t.nome, ore_stimate=t.ore_stimate,
                data_inizio=t.data_inizio, data_fine=t.data_fine,
                stato="Da iniziare",
                dipendente_id=t.dipendente_id or None,
                predecessore=t.predecessore or None,
            )
            session.add(task)
            if t.dipendente_id:
                session.add(Assegnazione(
                    task_id=task_id, dipendente_id=t.dipendente_id,
                    ore_assegnate=t.ore_stimate, ruolo="responsabile",
                ))
            creati.append({"id": task_id, "nome": t.nome, "fase_id": t.fase_id})

        # ── 4. Commit unico ──────────────────────────────────────────────
        session.commit()
        _reload()

        return {
            "progetto_id": progetto_id,
            "n_task_aggiunti": len(creati),
            "task": creati,
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Errore durante l'aggiunta dei task: {e}"
        )
    finally:
        session.close()


@router.patch("/{progetto_id}")
def aggiorna_progetto(progetto_id: str, req: ProgettoUpdate, _: Utente = Depends(require_manager)):
    """Aggiorna campi di un progetto (anagrafica e/o stato).

    Vincoli di transizione di stato sono responsabilità del frontend
    Cantiere/Wizard, non di questo endpoint.
    """
    if req.stato is not None and req.stato not in STATI_PROGETTO_AMMESSI:
        raise HTTPException(
            status_code=422,
            detail=f"Stato '{req.stato}' non ammesso. Valori: {STATI_PROGETTO_AMMESSI}"
        )

    session = get_session()
    try:
        prog = session.query(Progetto).filter(Progetto.id == progetto_id).first()
        if not prog:
            raise HTTPException(status_code=404, detail=f"Progetto '{progetto_id}' non trovato")

        for field, value in req.model_dump(exclude_unset=True).items():
            setattr(prog, field, value)

        session.commit()
        _reload()  # invalida cache DataFrame
        return {"id": progetto_id, "aggiornato": True, "stato": prog.stato}
    finally:
        session.close()


@router.delete("/{progetto_id}", status_code=204)
def elimina_progetto(progetto_id: str, _: Utente = Depends(require_manager)):
    """Elimina un progetto. SOLO se in stato 'Bozza'.

    Per chiudere un progetto attivo usa PATCH con stato='Annullato' o 'Completato'.
    """
    session = get_session()
    try:
        prog = session.query(Progetto).filter(Progetto.id == progetto_id).first()
        if not prog:
            raise HTTPException(status_code=404, detail=f"Progetto '{progetto_id}' non trovato")

        if prog.stato != "Bozza":
            raise HTTPException(
                status_code=409,
                detail=f"Solo i progetti in stato 'Bozza' possono essere eliminati. "
                       f"Progetto '{progetto_id}' è in stato '{prog.stato}'. "
                       "Per chiudere un progetto attivo usa PATCH con stato='Annullato' o 'Completato'."
            )

        session.delete(prog)
        session.commit()
        _reload()  # invalida cache DataFrame
        return None
    finally:
        session.close()