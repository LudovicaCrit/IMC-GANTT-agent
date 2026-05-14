"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/pianificazione.py — DEPRECATO (Step 2.0, 13 mag 2026)
═══════════════════════════════════════════════════════════════════════════

STATO: deprecato. Gli endpoint qui sotto rispondono 410 Gone con un
messaggio esplicativo che rimanda ai nuovi endpoint progetto.

CONTESTO
────────
Fino al 12 maggio 2026, questo router esponeva:
- POST /api/pianificazione/salva-bozza  → salvava blob JSON in BOZZE_STORE (dict in memoria)
- GET  /api/pianificazione/bozza/{id}   → leggeva da BOZZE_STORE

Le bozze erano snapshot opachi delle variabili di stato React di Pipeline.jsx
e AnalisiInterventi.jsx (planFasi, planTasks, nextFaseId, nextTaskId). Lo
store era in memoria → bozze perse a ogni restart del server.

Con Step 2.0 del Blocco 2 esteso (handoff v15) il modello cambia:
- Una bozza è un Progetto con `stato="Bozza"` (gestito da routes/progetti.py)
- Le bozze di pianificazione "salva il foglio di lavoro a metà" non esistono
  più: il nuovo Cantiere salva direttamente sui modelli (Progetto + Fase +
  Task), niente più blob JSON intermedio.

PERIODO DI TRANSIZIONE (13 mag → ~17 mag)
──────────────────────────────────────────
Pipeline.jsx e AnalisiInterventi.jsx sono ancora vive fino a Step 2.7
(creazione pagina Cantiere.jsx). In questo intervallo le due pagine
funzionano in tutto tranne il pulsante "Salva bozza", che è disabilitato
nel frontend con un tooltip esplicativo.

Quando Pipeline.jsx e AnalisiInterventi.jsx verranno cancellate (Step 2.7),
questo file potrà essere rimosso del tutto insieme al suo register_router
in main.py.

ENDPOINT
────────
- POST /api/pianificazione/salva-bozza → 410 Gone
- GET  /api/pianificazione/bozza/{id}  → 410 Gone

Perché 410 e non 404: 410 ("Gone") significa "questa risorsa esisteva ma
è stata rimossa intenzionalmente". 404 sarebbe ambiguo (potrebbe sembrare
un bug). Vedi RFC 9110 §15.5.11.

STORIA
──────
- 5 mag 2026: estratto da main.py (refactoring strangler).
- 13 mag 2026: deprecazione (Step 2.0). Da rimuovere a Step 2.7.
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends, HTTPException

from deps import require_manager
from models import Utente


router = APIRouter(prefix="/api/pianificazione", tags=["pianificazione (deprecato)"])


_DEPRECATION_MSG = (
    "Endpoint deprecato dal 13 maggio 2026 (Step 2.0 della roadmap). "
    "Le bozze di progetto sono ora gestite da /api/progetti con stato='Bozza'. "
    "Vedi handoff v15 §3.3."
)


@router.post("/salva-bozza", status_code=410)
def salva_bozza_deprecato(_: Utente = Depends(require_manager)):
    raise HTTPException(status_code=410, detail=_DEPRECATION_MSG)


@router.get("/bozza/{progetto_id}", status_code=410)
def carica_bozza_deprecato(progetto_id: str, _: Utente = Depends(require_manager)):
    raise HTTPException(status_code=410, detail=_DEPRECATION_MSG)
