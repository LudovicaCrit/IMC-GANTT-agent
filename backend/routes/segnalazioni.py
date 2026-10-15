"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/segnalazioni.py — Router per endpoint /api/segnalazioni
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint relativi alle segnalazioni interne (problemi
identificati dal chatbot di consuntivazione, dai dipendenti, dal sistema).
C'è solo un endpoint di lettura. Oggi nessun percorso dell'applicazione
scrive segnalazioni: le righe presenti vengono dal seed. Il chatbot che le
scriveva è archiviato in docs/EMBRIONI_IA.md §6.

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
   - Restituisce tutte le segnalazioni della tabella `segnalazioni`.
   - Una segnalazione contiene: tipo, priorità, dipendente_id, progetto_id,
     dettaglio testuale libero (utile per layer semantico R2).

PATTERN AUTH USATI
──────────────────
- `require_manager`: le segnalazioni sono trasversali al management.

DIPENDENZE
──────────
- `data` (modulo): `get_segnalazioni`.
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
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

from data import get_segnalazioni


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/segnalazioni", tags=["segnalazioni"])


@router.get("")
def lista_segnalazioni(_: Utente = Depends(require_manager)):
    """Restituisce tutte le segnalazioni raccolte (manager-only)."""
    return get_segnalazioni()
