"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/segnalazioni.py — Router per endpoint /api/segnalazioni
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint relativi alle segnalazioni interne (problemi
identificati dal chatbot di consuntivazione, dai dipendenti, dal sistema).
Per ora c'è solo un endpoint di lettura; le scritture avvengono
indirettamente via il chatbot di consuntivazione (`/api/agent/chat`).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/segnalazioni                │ GET      │ require_manager              │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/segnalazioni
   - Manager-only.
   - Restituisce tutte le segnalazioni raccolte:
     • Persistent mode (db): legge dalla tabella `segnalazioni`
     • Memory mode (legacy): legge dalla lista in memoria SEGNALAZIONI_STORE
   - Una segnalazione contiene: tipo, priorità, dipendente_id, progetto_id,
     dettaglio testuale libero (utile per layer semantico R2).

PATTERN AUTH USATI
──────────────────
- `require_manager`: le segnalazioni sono trasversali al management.

DIPENDENZE
──────────
- `data` (modulo): `get_segnalazioni` (in PERSISTENT_MODE).
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Lo store in memoria SEGNALAZIONI_STORE vive ancora in `main.py` per
retrocompatibilità con casi in cui il database non è attivo. Quando il
refactoring sarà completo e PostgreSQL sarà la fonte di verità unica,
si potrà rimuovere il fallback memoria.

📌 TODO Layer semantico R2:
   I campi `dettaglio` e `nota` sono testo libero apposta — saranno la
   base per il vector database / Neo4J / MongoDB di R2 (decisione
   tecnica ancora aperta, vedi handoff v13).

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends

from deps import require_manager
from models import Utente

# Import condizionale: se db disponibile, usa funzioni persistenti
try:
    from data import get_segnalazioni
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/segnalazioni", tags=["segnalazioni"])


@router.get("")
def lista_segnalazioni(_: Utente = Depends(require_manager)):
    """Restituisce tutte le segnalazioni raccolte (manager-only)."""
    if PERSISTENT_MODE:
        return get_segnalazioni()
    # Fallback memoria: importa dinamicamente il store da main.py
    # Questo è temporaneo finché PERSISTENT_MODE non sarà sempre True
    from main import SEGNALAZIONI_STORE
    return SEGNALAZIONI_STORE
