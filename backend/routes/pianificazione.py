"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/pianificazione.py — Router per endpoint /api/pianificazione
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint per il salvataggio e caricamento di "bozze di
pianificazione": stato intermedio della tabella task durante la creazione
di un nuovo progetto in Pipeline. Permette di chiudere il browser e
riprendere il lavoro più tardi senza perdere quanto fatto.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                     │ Metodo   │ Auth                │
├──────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/pianificazione/salva-bozza          │ POST     │ require_manager     │
│ /api/pianificazione/bozza/{progetto_id}  │ GET      │ require_manager     │
└──────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. POST /api/pianificazione/salva-bozza
   - Manager-only.
   - Body: {progetto_id: str, dati_json: dict}
     `dati_json` contiene lo snapshot completo della tabella task
     (struttura libera: dipende dalla pagina Pipeline frontend).
   - Persiste in db (tabella `pianificazioni_bozza`) o in memoria.

2. GET /api/pianificazione/bozza/{progetto_id}
   - Manager-only.
   - Restituisce {progetto_id, dati_json} se esiste una bozza, altrimenti
     {progetto_id, dati_json: None}.

PATTERN AUTH USATI
──────────────────
- `require_manager`: la pianificazione è funzione manageriale.
  📌 TODO R2 (ABAC): quando saranno introdotti i pm_id su progetto, questi
  endpoint potrebbero diventare PM-only sul progetto specifico
  (`require_pm_or_manager(progetto_id)`).

DIPENDENZE
──────────
- `data` (modulo): `salva_bozza_pianificazione`, `carica_bozza_pianificazione`
  (in PERSISTENT_MODE).
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Persistence dual-mode: db prima, memoria come fallback. Lo store
BOZZE_STORE vive ancora in main.py per retrocompatibilità.

📌 TODO Pipeline ridisegnata (Blocco 4 roadmap):
   Quando Pipeline sarà ridisegnata per il modello bando/ordinario
   (3 fasi standard per bando), valutare se la struttura `dati_json`
   resta libera o diventa schema-tipato (Pydantic model dedicato).

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import require_manager
from models import Utente

# Import condizionale: db disponibile?
try:
    from data import salva_bozza_pianificazione, carica_bozza_pianificazione
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False


# ── DTO ──────────────────────────────────────────────────────────────────
class SalvaBozzaRequest(BaseModel):
    progetto_id: str
    dati_json: dict  # snapshot della tabella task in pianificazione


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/pianificazione", tags=["pianificazione"])


@router.post("/salva-bozza")
def salva_bozza(req: SalvaBozzaRequest, _: Utente = Depends(require_manager)):
    """Salva o aggiorna una bozza di pianificazione."""
    if PERSISTENT_MODE:
        salva_bozza_pianificazione(req.progetto_id, req.dati_json)
    else:
        # Fallback memoria via main.py
        from main import BOZZE_STORE
        BOZZE_STORE[req.progetto_id] = {
            "progetto_id": req.progetto_id,
            "dati_json": req.dati_json,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    return {"salvato": True, "progetto_id": req.progetto_id}


@router.get("/bozza/{progetto_id}")
def carica_bozza(progetto_id: str, _: Utente = Depends(require_manager)):
    """Carica una bozza di pianificazione salvata."""
    if PERSISTENT_MODE:
        dati = carica_bozza_pianificazione(progetto_id)
        return {"progetto_id": progetto_id, "dati_json": dati}
    # Fallback memoria
    from main import BOZZE_STORE
    if progetto_id in BOZZE_STORE:
        return BOZZE_STORE[progetto_id]
    return {"progetto_id": progetto_id, "dati_json": None}
