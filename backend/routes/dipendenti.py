"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/dipendenti.py — Router per endpoint /api/dipendenti
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint REST per la lettura dei dati anagrafici e operativi
dei dipendenti (carico, saturazione, progetti attivi, task in corso).
NON contiene endpoint di Configurazione (CRUD admin) — quelli stanno in
`routes/configurazione.py`. NON contiene endpoint di gestione consuntivi
o assegnazioni — quelli stanno nei rispettivi router.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/dipendenti                  │ GET      │ require_manager (Scenario B) │
│ /api/dipendenti/{dip_id}         │ GET      │ self-or-manager              │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/dipendenti
   - Manager-only. Restituisce lista completa dei dipendenti aziendali con
     dati aggregati: profilo, ore_sett, competenze, carico_corrente,
     saturazione_pct, progetti_attivi, n_task_attivi.
   - Filosofia Scenario B: il dato aggregato sui colleghi è informazione
     manageriale, non visibile agli user (Helena vede solo se stessa).

2. GET /api/dipendenti/{dip_id}
   - Pattern self-or-manager. User può consultare SOLO il proprio profilo
     (verifica `dip_id == current_user.dipendente_id`); manager può
     consultare qualunque dipendente.
   - Restituisce dati anagrafici + carico + lista task in corso.
   - 403 se user prova ad accedere a un altro dipendente.
   - 404 se dipendente non esiste.

PATTERN AUTH USATI
──────────────────
- `require_manager`: dependency che blocca con 403 chi non è manager.
- `get_current_user` + check manuale `current_user.dipendente_id`: usato
  per il pattern self-or-manager dove la logica self richiede il dato
  dell'utente loggato.

DIPENDENZE
──────────
- `data` (modulo): funzioni `get_dipendente`, `get_progetti_dipendente`,
  `carico_settimanale_dipendente`, e accesso ai DataFrame
  DIPENDENTI/PROGETTI/TASKS via `data_module.<NOME>`.
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Gli helper _DIPENDENTI(), _PROGETTI(), _TASKS() e get_oggi() sono
replicati localmente in questo file (inizialmente erano in main.py).
Sono temporanei: quando il refactoring sarà avanzato e più di 2 router
li useranno, andranno estratti in `backend/dataframes.py` (cache DF) e
`backend/utils.py` (clock).

📌 TODO — REFACTORING SUCCESSIVO
   Estrarre _DIPENDENTI/_PROGETTI/_TASKS/get_oggi quando avremo ≥3 router
   che li replicano. Vedi `backend/routes/README.md` per stato generale.

STORIA
──────
Estratto da main.py il 5 maggio 2026 come primo router del refactoring
"strangler" finalizzato a passare main.py da ~2780 righe a ≤200, lasciando
a Roberto un codice modulare per R2 (settembre 2026).
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from deps import get_current_user, require_manager
from models import Utente
import data as data_module
from data import (
    get_dipendente, get_progetti_dipendente, carico_settimanale_dipendente,
)


# ── Helper locali (TODO: estrarre in moduli condivisi) ───────────────────
def _DIPENDENTI(): return data_module.DIPENDENTI
def _PROGETTI(): return data_module.PROGETTI
def _TASKS(): return data_module.TASKS

def get_oggi():
    return datetime.now()


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/dipendenti", tags=["dipendenti"])


@router.get("")
def lista_dipendenti(_: Utente = Depends(require_manager)):
    """Lista dipendenti con saturazione e progetti attivi (manager-only).

    Scenario B: il dettaglio aggregato sui colleghi è informazione
    manageriale, non visibile agli user.
    """
    result = []
    for _, d in _DIPENDENTI().iterrows():
        carico = carico_settimanale_dipendente(d["id"], get_oggi())
        progetti = get_progetti_dipendente(d["id"])
        result.append({
            "id": d["id"],
            "nome": d["nome"],
            "profilo": d["profilo"],
            "ore_sett": int(d["ore_sett"]),
            "competenze": d["competenze"],
            "carico_corrente": float(carico),
            "saturazione_pct": round(carico / d["ore_sett"] * 100),
            "progetti_attivi": progetti,
            "n_task_attivi": len(_TASKS()[
                (_TASKS()["dipendente_id"] == d["id"]) &
                (_TASKS()["stato"].isin(["In corso", "Da iniziare"]))
            ]),
        })
    return result


@router.get("/{dip_id}")
def dettaglio_dipendente(
    dip_id: str,
    current_user: Utente = Depends(get_current_user),
):
    """Dettaglio dipendente (pattern self-or-manager).

    User può vedere solo il proprio profilo (verifica self via
    current_user.dipendente_id); manager può vedere chiunque.
    """
    if current_user.ruolo_app != "manager" and dip_id != current_user.dipendente_id:
        raise HTTPException(403, "Puoi vedere solo il tuo profilo")
    try:
        d = get_dipendente(dip_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    carico = carico_settimanale_dipendente(dip_id, get_oggi())
    progetti = get_progetti_dipendente(dip_id)
    tasks = _TASKS()[
        (_TASKS()["dipendente_id"] == dip_id) &
        (_TASKS()["stato"].isin(["In corso", "Da iniziare"]))
    ]

    return {
        "id": d["id"],
        "nome": d["nome"],
        "profilo": d["profilo"],
        "ore_sett": int(d["ore_sett"]),
        "competenze": d["competenze"],
        "carico_corrente": float(carico),
        "saturazione_pct": round(carico / d["ore_sett"] * 100),
        "progetti_attivi": progetti,
        "tasks": [
            {
                "id": t["id"],
                "nome": t["nome"],
                "progetto": _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]["nome"],
                "fase": t["fase"],
                "stato": t["stato"],
                "ore_stimate": int(t["ore_stimate"]),
                "data_inizio": t["data_inizio"].isoformat(),
                "data_fine": t["data_fine"].isoformat(),
            }
            for _, t in tasks.iterrows()
        ],
    }