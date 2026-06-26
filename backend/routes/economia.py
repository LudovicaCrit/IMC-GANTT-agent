"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/economia.py — Router per endpoint /api/economia
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint di analisi economica. Alimenta la pagina Economia
(vista manager): marginalità per progetto + erosione da sovraccarico +
aggregato separato per azienda (Improve / Innovation).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/economia/margini            │ GET      │ require_manager              │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/economia/margini  (manager-only)
   Tutto il calcolo è nello strato dati (data_db_impl.margini_economia): la
   route è solo chiamante, niente SQL qui. Output a due livelli:
     • "progetti": per ogni progetto COMMERCIALE/BANDO (interni esclusi per
       tipologia) → azienda, i TRE margini (venduto / pianificato / consumato)
       e le DUE erosioni (commerciale e operativa, in € e punti %), più
       `costo_stimato` (flag: margine approssimato per dati incompleti).
     • "totali_per_azienda": aggregati di ramo (Improve / Innovation), stesse
       metriche; Σ per-progetto == totale per costruzione.

NOTE DI DOMINIO (Roberto)
─────────────────────────
Marginalità "versione B": mostra come il margine si erode col sovraccarico.
  - erosione_commerciale = margine_venduto − margine_consumato (sforo contratto)
  - erosione_operativa   = margine_pianificato − margine_consumato (sforo piano)
Il margine sul consumato coincide con la vecchia "versione A"
(valore_contratto − Σ ore_consuntivate × costo_ora): retro-compatibile
(`margine_attuale`/`margine_pct` restano nel payload per-progetto).

NOTE TECNICHE
─────────────
Gli interni (tipologia 'interna') sono esclusi PER TIPOLOGIA. Il vecchio filtro
`Progetto.id != "P010"` era un hack morto: dopo il redesign seed non escludeva
più gli interni (spacchettati in PC*/PI*/PN*) e per giunta tagliava fuori il
nuovo P010/Maida. Rimosso.

DIPENDENZE
──────────
- `data` (modulo): `margini_economia`.
- `deps`: `require_manager`. `models`: `Utente` (type hint).

STORIA
──────
Estratto da main.py il 5 maggio 2026 (refactoring strangler). Calcolo spostato
nello strato dati + erosione/aggregato per azienda (26/06/2026).
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends

from deps import require_manager
from models import Utente
from data import margini_economia


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/economia", tags=["economia"])


@router.get("/margini")
def economia_margini(_: Utente = Depends(require_manager)):
    """Marginalità + erosione per progetto e aggregato per azienda (versione B).

    Calcolo interamente nello strato dati; interni esclusi per tipologia.
    """
    return margini_economia()
