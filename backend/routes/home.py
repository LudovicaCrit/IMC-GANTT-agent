"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/home.py — Router per endpoint /api/home (Home management)
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Aggrega le criticità dei progetti per la vista PM/manager (la "Home"
manageriale). Primo endpoint: lo sforamento ore (ore_consumate vs ore_vendute,
budget commerciale). È lavoro additivo: non tocca endpoint/modelli esistenti.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/home/criticita              │ GET      │ get_current_user (self-or-mgr)│
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/home/criticita
   - La route è sottile: delega tutto allo strato dati.
     • progetti_attivi_visibili(current_user): id dei progetti ATTIVI visibili
       (filtro self-or-manager — manager vede tutti, l'user solo i suoi via
       pm_id == dipendente_id).
     • criticita_sforamento_progetti(ids): calcolo sforamento col contratto
       fisso (liste-di-dict).
   - Tornano solo i progetti con almeno una criticità; i sani non compaiono.
   - Nessuna query SQL qui: la conoscenza del DB vive nello strato dati
     (coerente col Blocco 4 e con la futura conversione ORM).

PATTERN AUTH USATI
──────────────────
- `get_current_user`: l'endpoint è visibile sia agli user (filtrati ai propri
  progetti, nello strato dati) sia ai manager (tutti). Lo stile self-or-manager
  è quello di routes/dipendenti.py:dettaglio_dipendente.

DIPENDENZE
──────────
- `data` (modulo): `progetti_attivi_visibili`, `criticita_sforamento_progetti`.
- `deps`: `get_current_user`.
- `models`: `Utente` (solo type hint).

NOTE DI DIREZIONE
─────────────────
Il campo `tipo` delle criticità è una stringa-enum (oggi solo
"superamento_ore"), volutamente estendibile (futuri "slittamento_date",
"superamento_pianificato", ...). NON irrigidirlo a un booleano. Nessun
semaforo verde/giallo/rosso qui: arriverà col calcolo ritardabilità vero,
dopo il backend urgenza.

STORIA
──────
Aggiunto il 9 giugno 2026 come primo endpoint della Home management.
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends

from deps import get_current_user
from models import Utente
from data import progetti_attivi_visibili, criticita_sforamento_progetti


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("/criticita")
def lista_criticita(current_user: Utente = Depends(get_current_user)):
    """Criticità di sforamento ore dei progetti attivi (vista PM/manager).

    Filtro identità (self-or-manager) e calcolo sono entrambi delegati allo
    strato dati: la route si limita a comporre le due funzioni.
    """
    ids = progetti_attivi_visibili(current_user)
    return criticita_sforamento_progetti(ids)
