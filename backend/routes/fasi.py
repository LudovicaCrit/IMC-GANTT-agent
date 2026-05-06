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

from fastapi import APIRouter, Depends
from sqlalchemy import func

from deps import require_manager
from models import get_session, Utente, Fase, Task, Consuntivo


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/fasi", tags=["fasi"])


@router.post("")
def crea_fase(req: dict, _: Utente = Depends(require_manager)):
    """Crea una nuova fase di progetto.

    Body: dict free-form con progetto_id, nome, ordine, data_inizio, data_fine, ore_vendute.
    Stato iniziale: "Da iniziare".

    📌 TODO: introdurre Pydantic DTO FaseRequest per validazione body.
    """
    session = get_session()
    fase = Fase(
        progetto_id=req["progetto_id"],
        nome=req["nome"],
        ordine=req.get("ordine", 1),
        data_inizio=req.get("data_inizio"),
        data_fine=req.get("data_fine"),
        ore_vendute=req.get("ore_vendute", 0),
        stato="Da iniziare",
    )
    session.add(fase)
    session.commit()
    result = {"id": fase.id, "nome": fase.nome}
    session.close()
    return result


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
