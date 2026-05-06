"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/economia.py — Router per endpoint /api/economia
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint di analisi economica: marginalità per progetto,
costi effettivi e stimati, dettaglio dei costi per persona. È il modulo
che alimenta la pagina Economia del frontend (vista manager).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/economia/margini            │ GET      │ require_manager              │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/economia/margini
   - Manager-only.
   - Per ogni progetto (esclusi P010 = Attività Interne):
     • valore_contratto, budget_ore
     • ore_consuntivate effettive
     • costo_effettivo (somma ore × costo_orario per dipendente)
     • margine_attuale = valore - costo_effettivo
     • margine_pct
     • costo_stimato_completamento (proiezione su budget_ore)
     • margine_stimato + margine_stimato_pct
     • dettaglio_persone: lista costi per dipendente, ordinata per costo
   - Output ordinato per `margine_pct` crescente (i più critici in cima).

PATTERN AUTH USATI
──────────────────
- `require_manager`: dato economico è strettamente manageriale.

NOTE DI DOMINIO (Roberto, 21 aprile 2026)
─────────────────────────────────────────
Questa è la "marginalità versione A" richiesta da Roberto:
  margine = valore_contratto - (ore_consuntivate × costo_ora_dipendente)

📌 TODO Marginalità avanzata (Blocco 5 roadmap, opzionale):
   Roberto ha proposto una versione che mostri come la marginalità si
   eroda con il sovraccarico delle risorse (progetti che si allungano
   per saturazione eccessiva). Da implementare se il buffer del 17 giugno
   lo permette, altrimenti R2.

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, e DataFrame PROGETTI/TASKS/CONSUNTIVI.
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
P010 (Attività Interne) escluso dal calcolo: non ha valore contrattuale,
ma è marginalità implicita "negativa" (costi senza ricavi). In R2 si
potrebbe decidere di mostrarlo separatamente come "costo struttura".

Helper `_PROGETTI()`, `_TASKS()`, `_CONSUNTIVI()` replicati localmente.
📌 TODO: estrarre in `backend/dataframes.py` quando ≥3 router li replicano.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends

from deps import require_manager
from models import Utente
from data import get_dipendente
from dataframes import _PROGETTI, _TASKS, _CONSUNTIVI


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/economia", tags=["economia"])


@router.get("/margini")
def economia_margini(_: Utente = Depends(require_manager)):
    """Calcola costi e margini per ogni progetto (versione A formula Roberto)."""
    result = []
    for _, p in _PROGETTI().iterrows():
        if p["id"] == "P010":  # Attività Interne escluse (no valore contratto)
            continue

        tasks_proj = _TASKS()[_TASKS()["progetto_id"] == p["id"]]
        task_ids = tasks_proj["id"].tolist()
        cons_proj = _CONSUNTIVI()[_CONSUNTIVI()["task_id"].isin(task_ids)]

        costo_totale = 0.0
        ore_totali = 0.0
        costi_per_persona = {}

        for _, c in cons_proj.iterrows():
            if c["ore_dichiarate"] <= 0:
                continue
            did = c["dipendente_id"]
            dip = get_dipendente(did)
            costo_ora = float(dip.get("costo_ora", 0)) if dip is not None else 0
            costo_riga = c["ore_dichiarate"] * costo_ora
            costo_totale += costo_riga
            ore_totali += c["ore_dichiarate"]

            if did not in costi_per_persona:
                costi_per_persona[did] = {
                    "nome": dip["nome"], "profilo": dip["profilo"],
                    "costo_ora": costo_ora, "ore": 0, "costo": 0,
                }
            costi_per_persona[did]["ore"] += c["ore_dichiarate"]
            costi_per_persona[did]["costo"] += costo_riga

        valore = float(p["valore_contratto"])
        margine = valore - costo_totale
        margine_pct = (margine / valore * 100) if valore > 0 else 0

        budget_ore = int(p["budget_ore"]) if p["budget_ore"] else 0
        if ore_totali > 0 and budget_ore > 0:
            costo_medio_ora = costo_totale / ore_totali
            costo_stimato_totale = costo_medio_ora * budget_ore
            margine_stimato = valore - costo_stimato_totale
            margine_stimato_pct = (margine_stimato / valore * 100) if valore > 0 else 0
        else:
            costo_stimato_totale = 0
            margine_stimato = valore
            margine_stimato_pct = 100

        result.append({
            "progetto_id": p["id"], "nome": p["nome"],
            "cliente": p["cliente"], "stato": p["stato"],
            "valore_contratto": valore, "budget_ore": budget_ore,
            "ore_consuntivate": round(ore_totali, 1),
            "costo_effettivo": round(costo_totale, 2),
            "margine_attuale": round(margine, 2),
            "margine_pct": round(margine_pct, 1),
            "costo_medio_ora": round(costo_totale / ore_totali, 2) if ore_totali > 0 else 0,
            "costo_stimato_completamento": round(costo_stimato_totale, 2),
            "margine_stimato": round(margine_stimato, 2),
            "margine_stimato_pct": round(margine_stimato_pct, 1),
            "dettaglio_persone": sorted(
                costi_per_persona.values(), key=lambda x: x["costo"], reverse=True
            ),
        })

    return sorted(result, key=lambda x: x["margine_pct"])
