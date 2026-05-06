"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/progetti.py — Router per endpoint /api/progetti
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint di lettura dei progetti aziendali, con dati aggregati
sullo stato di avanzamento (ore consuntivate, tasso compilazione, task
completati). NON contiene endpoint di Configurazione progetti — quelli
saranno in `routes/configurazione.py`. NON contiene endpoint di scrittura
(POST/PATCH/DELETE) progetti — verranno aggiunti durante Pipeline ridisegnata
(Blocco 4 della roadmap).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/progetti                    │ GET      │ require_manager (Scenario B) │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/progetti
   - Manager-only. Restituisce lista completa progetti con stato avanzamento.
   - Per ogni progetto: anagrafica + ore_consuntivate + tasso_compilazione +
     task_completati / task_totali.
   - Filosofia Scenario B: il quadro aziendale dei progetti è informazione
     manageriale; gli user (Helena) accedono ai propri progetti via
     /api/dipendenti/{id} con pattern self-or-manager.

PATTERN AUTH USATI
──────────────────
- `require_manager`: dependency che blocca con 403 chi non è manager.

DIPENDENZE
──────────
- `data` (modulo): `ore_consuntivate_progetto`, `tasso_compilazione_progetto`,
  e DataFrame PROGETTI/TASKS via `data_module.<NOME>`.
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper `_PROGETTI()` e `_TASKS()` replicati localmente.
📌 TODO: estrarre in `backend/dataframes.py` quando ≥3 router li replicano.

📌 TODO Pipeline ridisegnata (Blocco 4):
   - Aggiungere POST /api/progetti (usa `_next_progetto_id()` già presente
     in data_db_impl.py)
   - Aggiungere PATCH /api/progetti/{id}
   - Filtro per `tipologia` (bando/ordinario) quando schema db estesa

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends

from deps import require_manager
from models import Utente
from data import ore_consuntivate_progetto, tasso_compilazione_progetto
from dataframes import _PROGETTI, _TASKS


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/progetti", tags=["progetti"])


@router.get("")
def lista_progetti(_: Utente = Depends(require_manager)):
    """Lista progetti con stato avanzamento (manager-only).

    Scenario B: il quadro aziendale è solo per il management.
    """
    result = []
    for _, p in _PROGETTI().iterrows():
        ore_cons = ore_consuntivate_progetto(p["id"])
        tasso = tasso_compilazione_progetto(p["id"])
        tasks_proj = _TASKS()[_TASKS()["progetto_id"] == p["id"]]
        completati = len(tasks_proj[tasks_proj["stato"] == "Completato"])

        result.append({
            "id": p["id"],
            "nome": p["nome"],
            "cliente": p["cliente"],
            "stato": p["stato"],
            "data_inizio": p["data_inizio"].isoformat(),
            "data_fine": p["data_fine"].isoformat(),
            "budget_ore": int(p["budget_ore"]),
            "valore_contratto": float(p["valore_contratto"]),
            "fase_corrente": p["fase_corrente"],
            "ore_consuntivate": float(ore_cons),
            "tasso_compilazione": round(tasso, 1),
            "task_completati": completati,
            "task_totali": len(tasks_proj),
        })
    return result