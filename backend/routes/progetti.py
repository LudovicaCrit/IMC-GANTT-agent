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
from models import get_session, Utente, Progetto, STATI_PROGETTO, STATI_PROGETTO_ATTIVI
from data import ore_consuntivate_progetto, tasso_compilazione_progetto
from data_db_impl import _next_progetto_id, _reload
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