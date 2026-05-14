"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/fasi.py — Router per endpoint /api/fasi
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint di lettura/scrittura sulle Fasi di progetto.

Nel sistema attuale (R1) le fasi sono ancora un livello sottoutilizzato:
- la pagina GANTT mostra task piatti, non raggruppati per fase
- la pagina Pipeline non orchestra le fasi nel modo voluto da Vincenzo/Francesco
- il consuntivo si fa per task, non per fase

📌 Questa è la situazione di partenza per il **Blocco 2 — Macchina delle Fasi**
   della roadmap v4 (target: gio 14 maggio). Quando il Blocco 2 sarà fatto,
   gli endpoint qui dentro cresceranno (PATCH, DELETE, GET aggregato per
   progetto con fasi raggruppate, validazioni di coerenza fase↔task).

Per ora, contiene solo i 2 endpoint MVP esistenti.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                     │ Metodo   │ Auth                │
├──────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/fasi                                │ POST     │ require_manager     │
│ /api/fasi/{progetto_id}                  │ GET      │ require_manager     │
└──────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. POST /api/fasi
   - Manager-only.
   - Body: dict free-form con `progetto_id`, `nome`, `ordine` (default 1),
     `data_inizio`, `data_fine`, `ore_vendute` (default 0).
   - Stato iniziale: "Da iniziare".
   - Restituisce {id, nome} della fase creata.
   - 📌 TODO: introdurre Pydantic DTO `FaseRequest` per validazione (oggi
     usa req: dict, accetta qualunque cosa).

2. GET /api/fasi/{progetto_id}
   - Manager-only.
   - Lista delle fasi di un progetto, ordinate per `ordine`.
   - Per ogni fase calcola `ore_consumate` aggregando i consuntivi dei
     task agganciati (via Task.fase_id).
   - Restituisce: lista di dict con id, nome, ordine, date, ore vendute/
     pianificate/consumate/rimanenti, stato, n_task, note.

PATTERN AUTH USATI
──────────────────
- `require_manager`: la struttura per fasi è informazione progettuale
  manageriale (al momento; in Blocco 2 potrebbe estendersi a user con
  pattern self-or-manager se Vista Helena userà le fasi).

DIPENDENZE
──────────
- `models`: `get_session`, `Utente`, `Fase`, `Task`, `Consuntivo`.
- `deps`: `require_manager`.
- `sqlalchemy.func`: per somma ore consumate.

NOTE TECNICHE
─────────────
Questo router NON usa i DataFrame `_DIPENDENTI()` / `_PROGETTI()` / ecc.
Lavora direttamente con SQLAlchemy via `get_session()`, come
`routes/configurazione.py`. Coerente: scrive/legge entità di base.

Importa esplicitamente `Task` e `Consuntivo`, mentre il main.py originale
li usava SENZA averli nell'import (riga 17). Funzionava per accidente
(probabile import implicito da altri moduli). Qui rendiamo la dipendenza
esplicita: principio "esplicito è meglio di implicito".

📌 TODO Blocco 2 (Macchina delle Fasi):
Questo router crescerà significativamente. Endpoint da aggiungere:
  - PATCH /api/fasi/{fase_id} (rinomina, sposta date, cambia ordine)
  - DELETE /api/fasi/{fase_id} (con check task agganciati)
  - GET /api/fasi/progetti/{progetto_id}/aggregato (vista per Pipeline:
    progetto → fasi → task tutti annidati)
  - POST /api/fasi/da-template (crea fasi da FaseStandard template,
    es. per i Bandi: 3 fasi standard Monitoraggio/Proposal/PM)

E dovrà gestire la coerenza fase↔task quando si modificheranno date
o si elimineranno fasi.

📌 TODO Pulizia:
Niente DTO orfani da rimuovere — il POST /api/fasi non ne aveva uno
in main.py (usava req: dict).

STORIA
──────
Estratto da main.py il 6 maggio 2026 nell'ambito del refactoring strangler.
È l'ULTIMO router del refactoring. Con questo, main.py passa da 2779
righe a ~150-200 (resta solo: imports, app FastAPI, CORS, rate limiter,
register_router, helpers che andranno in moduli condivisi).

Dopo questo router, il refactoring degli endpoint è chiuso. Resta:
- pulizia DTO orfani in main.py (commit dedicato)
- estrazione helper condivisi in utils.py / dataframes.py / contesto.py
- fix bug audit_permessi.py (auth_routes.py)
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func

from deps import require_manager
from models import get_session, Utente, Fase, Task, Consuntivo, STATI_FASE


# ── DTO ──────────────────────────────────────────────────────────────────
class FaseRequest(BaseModel):
    """Body request per POST /api/fasi.

    Sostituisce il dict free-form precedente (vedi handoff v14.3, D5).
    Lo `stato` non è nel DTO: viene settato server-side a "Da iniziare".
    """
    progetto_id: str = Field(..., min_length=1, max_length=10)
    nome: str = Field(..., min_length=1, max_length=100)
    ordine: int = Field(default=1, ge=1)
    data_inizio: Optional[date_type] = None
    data_fine: Optional[date_type] = None
    ore_vendute: float = Field(default=0, ge=0)
    ore_pianificate: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = None


class FaseUpdate(BaseModel):
    """Body request per PATCH /api/fasi/{fase_id}. Tutti i campi opzionali."""
    nome: Optional[str] = Field(default=None, min_length=1, max_length=100)
    ordine: Optional[int] = Field(default=None, ge=1)
    data_inizio: Optional[date_type] = None
    data_fine: Optional[date_type] = None
    ore_vendute: Optional[float] = Field(default=None, ge=0)
    ore_pianificate: Optional[float] = Field(default=None, ge=0)
    stato: Optional[str] = Field(default=None, max_length=20)
    note: Optional[str] = None


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/fasi", tags=["fasi"])


@router.post("")
def crea_fase(req: FaseRequest, _: Utente = Depends(require_manager)):
    """Crea una nuova fase di progetto.

    Body validato da FaseRequest (Pydantic). Stato iniziale: "Da iniziare"
    (settato server-side, non dal client).

    Vedi handoff v14.3 D5 per il contesto del refactoring da dict free-form
    a DTO Pydantic.
    """
    
    session = get_session()
    fase = Fase(
        progetto_id=req.progetto_id,
        nome=req.nome,
        ordine=req.ordine,
        data_inizio=req.data_inizio,
        data_fine=req.data_fine,
        ore_vendute=req.ore_vendute,
        ore_pianificate=req.ore_pianificate,
        note=req.note,
        stato="Da iniziare",
    )
    session.add(fase)
    session.commit()
    result = {"id": fase.id, "nome": fase.nome}
    session.close()
    return result


@router.patch("/{fase_id}")
def aggiorna_fase(fase_id: int, req: FaseUpdate, _: Utente = Depends(require_manager)):
    """Aggiorna campi di una fase (nome, date, ore, stato, ecc.).

    Step 2.1 D2 (13 mag 2026): aggiunto come endpoint complementare al
    DELETE. Utile anche per cambiare stato fase (Da iniziare → In corso →
    Completata) prima dell'introduzione formale di stato_derivato (D3).
    """
    session = get_session()
    try:
        fase = session.query(Fase).filter(Fase.id == fase_id).first()
        if not fase:
            raise HTTPException(status_code=404, detail=f"Fase {fase_id} non trovata")

        # Validazione stato contro STATI_FASE (allineato al CHECK constraint DB)
        if req.stato is not None and req.stato not in STATI_FASE:
            raise HTTPException(
                status_code=422,
                detail=f"Stato fase '{req.stato}' non ammesso. Valori: {STATI_FASE}"
            )

        for field, value in req.model_dump(exclude_unset=True).items():
            setattr(fase, field, value)

        session.commit()
        return {"id": fase_id, "aggiornato": True}
    finally:
        session.close()


@router.delete("/{fase_id}", status_code=204)
def elimina_fase(fase_id: int, _: Utente = Depends(require_manager)):
    """Elimina una fase. SOLO se non ha task agganciati.

    Step 2.1 D2 (handoff v15 §2.1): comportamento di cancellazione fase.
    R1: blocca con HTTP 409 se la fase ha task figli. L'utente deve prima
    spostare i task in un'altra fase (via PATCH /api/tasks/{id}) o eliminarli.

    Coerente col vincolo DB `ondelete="RESTRICT"` su `Task.fase_id` (D1):
    il DB rifiuterebbe comunque la cancellazione, qui restituiamo un
    messaggio applicativo prima che il vincolo scatti.

    Niente cascade automatica: troppo distruttiva per R1. R2 potrà valutare
    un parametro `?force=true` con riassegnazione esplicita.
    """
    session = get_session()
    try:
        fase = session.query(Fase).filter(Fase.id == fase_id).first()
        if not fase:
            raise HTTPException(status_code=404, detail=f"Fase {fase_id} non trovata")

        n_task = session.query(Task).filter(Task.fase_id == fase_id).count()
        if n_task > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Impossibile eliminare la fase '{fase.nome}': ha {n_task} task agganciati. "
                    "Sposta i task in un'altra fase (PATCH /api/tasks/{id} con fase=...) "
                    "o eliminali prima."
                )
            )

        session.delete(fase)
        session.commit()
        return None  # 204 No Content
    finally:
        session.close()


@router.get("/{progetto_id}")
def lista_fasi_progetto(progetto_id: str, _: Utente = Depends(require_manager)):
    """Lista fasi di un progetto con totali ore (vendute/pianificate/consumate).

    Per ogni fase aggrega i consuntivi dei task agganciati per calcolare
    ore_consumate e ore_rimanenti.
    """
    session = get_session()
    fasi = session.query(Fase).filter(Fase.progetto_id == progetto_id).order_by(Fase.ordine).all()
    result = []
    for f in fasi:
        # Calcola ore consumate dai consuntivi dei task in questa fase
        tasks_fase = session.query(Task).filter(Task.fase_id == f.id).all()
        task_ids = [t.id for t in tasks_fase]
        ore_consumate = 0
        if task_ids:
            ore_consumate = session.query(
                func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0)
            ).filter(Consuntivo.task_id.in_(task_ids)).scalar()

        result.append({
            "id": f.id,
            "nome": f.nome,
            "ordine": f.ordine,
            "data_inizio": f.data_inizio.isoformat() if f.data_inizio else None,
            "data_fine": f.data_fine.isoformat() if f.data_fine else None,
            "ore_vendute": f.ore_vendute,
            "ore_pianificate": f.ore_pianificate,
            "ore_consumate": float(ore_consumate),
            "ore_rimanenti": (f.ore_vendute or 0) - float(ore_consumate),
            "stato": f.stato,
            "n_task": len(tasks_fase),
            "note": f.note or "",
        })
    session.close()
    return result