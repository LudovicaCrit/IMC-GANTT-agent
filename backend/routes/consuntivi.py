"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/consuntivi.py — Router per endpoint /api/consuntivi
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint relativi ai consuntivi settimanali dei dipendenti.
È il cuore tecnico della pagina Consuntivazione e della futura Vista
Helena (Blocco 3 roadmap). Implementa rigorosamente il pattern
Scenario B + self-or-manager + Pattern Y (anti-impersonation in scrittura).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/consuntivi/settimana        │ GET      │ require_manager              │
│ /api/consuntivi/me               │ GET      │ AUTH-ONLY (intrinseco self)  │
│ /api/consuntivi/salva            │ POST     │ Pattern Y (self-or-manager)  │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/consuntivi/settimana
   - Manager-only.
   - Vista AZIENDALE: tutti i dipendenti, settimana corrente.
   - Per ogni dipendente: ore_per_task, totale_ore, flag `compilato`.
   - Include anche dipendenti che NON hanno compilato (totale_ore=0,
     compilato=False), purché abbiano almeno 1 task attivo.
   - Output ordinato: prima i compilati, poi per nome.

2. GET /api/consuntivi/me
   - AUTH-ONLY: nessun parametro `dipendente_id` accettato.
     L'identità del chiamante determina di chi mostrare i consuntivi.
   - Vista PERSONALE: il dipendente vede SOLO i propri consuntivi.
   - Funziona per user (Helena) e per manager (Ludovica può vedere se
     stessa così, anche se ha accesso a /settimana per la vista aziendale).
   - 400 se l'utente non è collegato a un dipendente
     (current_user.dipendente_id is None).
   - Restituisce: nome, profilo, ore_contrattuali, totale_ore,
     ore_per_task, compilato.

3. POST /api/consuntivi/salva
   - Pattern Y (self-or-manager): l'user può salvare SOLO i propri
     consuntivi (controllo self via current_user.dipendente_id);
     il manager può salvare per chiunque.
   - Body: dipendente_id, ore_per_task, stati_per_task, giorni sede/remoto,
     ore_assenza, tipo_assenza, nota_assenza, spese.
   - 403 se user prova a salvare per un altro dipendente.
   - 404 se dipendente non esiste.
   - Persiste in db (PERSISTENT_MODE) o ritorna conferma simulata altrimenti.

PATTERN AUTH USATI
──────────────────
- `require_manager`: per la vista aziendale aggregata.
- `get_current_user` + check `dipendente_id`: per il pattern self-or-manager
  in scrittura (Pattern Y) e per la vista personale intrinseca (`/me`).

NOTE DI DOMINIO
───────────────
La vista personale `/api/consuntivi/me` è esattamente quella che alimenterà
la pagina Consuntivazione di Helena nella Vista User (Blocco 3 roadmap).
Coerente con la "filosofia della settimana intera" e con Scenario B.

📌 TODO Blocco 3 roadmap (Vista Helena + Form Consuntivazione):
   Il payload restituito da `/api/consuntivi/me` potrebbe arricchirsi:
   - reminder integrati ("non hai ancora compilato")
   - task in scadenza
   - flag `motivo_richiesto` se task bloccato/in ritardo senza nota
   - storia delle ultime N settimane

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `salva_consuntivo` (in PERSISTENT_MODE),
  e DataFrame DIPENDENTI/PROGETTI/TASKS/CONSUNTIVI.
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper locali `_DIPENDENTI`, `_PROGETTI`, `_TASKS`, `_CONSUNTIVI`.
📌 TODO: estrarre in `backend/dataframes.py` quando ≥3 router li replicano
(condizione largamente superata — da fare presto).

Helper privato `_consuntivo_vuoto_per_user` per coerenza del payload
quando l'utente non ha ancora consuntivi.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user, require_manager
from models import Utente
import data as data_module
from data import get_dipendente

# Import condizionale per scrittura
try:
    from data import salva_consuntivo
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False


# ── Helper locali (TODO: estrarre in moduli condivisi) ───────────────────
def _DIPENDENTI(): return data_module.DIPENDENTI
def _PROGETTI(): return data_module.PROGETTI
def _TASKS(): return data_module.TASKS
def _CONSUNTIVI(): return data_module.CONSUNTIVI


# ── DTO ──────────────────────────────────────────────────────────────────
class SalvaConsuntivoRequest(BaseModel):
    dipendente_id: str
    ore_per_task: dict[str, float] = {}
    stati_per_task: dict[str, str] = {}
    giorni_sede: int = 3
    giorni_remoto: int = 2
    ore_assenza: float = 0
    tipo_assenza: str = ""
    nota_assenza: str = ""
    spese: list[dict] = []


# ── Helper privato ───────────────────────────────────────────────────────
def _consuntivo_vuoto_per_user(dipendente_id: str):
    """Payload coerente quando l'utente non ha ancora consuntivi."""
    try:
        dip = get_dipendente(dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")
    return {
        "dipendente_id": dipendente_id,
        "nome": dip["nome"],
        "profilo": dip["profilo"],
        "ore_contrattuali": int(dip["ore_sett"]),
        "totale_ore": 0,
        "ore_per_task": [],
        "compilato": False,
    }


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/consuntivi", tags=["consuntivi"])


@router.get("/settimana")
def consuntivi_settimana_corrente(_: Utente = Depends(require_manager)):
    """Vista MANAGER-ONLY: riepilogo aziendale settimana corrente.
    Per la vista personale del dipendente vedi /api/consuntivi/me."""
    lun = datetime.now() - timedelta(days=datetime.now().weekday())
    lun_date = lun.date() if hasattr(lun, 'date') else lun

    consuntivi = _CONSUNTIVI()
    if consuntivi.empty:
        return []

    # Filtra per settimana corrente
    ven_date = lun_date + timedelta(days=6)
    cons_sett = consuntivi[consuntivi["settimana"].apply(
        lambda x: lun_date <= (x.date() if hasattr(x, 'date') else x) <= ven_date
    )]

    risultato = []
    for did in cons_sett["dipendente_id"].unique():
        try:
            dip = get_dipendente(did)
        except (IndexError, KeyError):
            continue
        cons_dip = cons_sett[cons_sett["dipendente_id"] == did]
        ore_per_task = []
        totale = 0
        for _, c in cons_dip.iterrows():
            if c["ore_dichiarate"] > 0:
                task_row = _TASKS()[_TASKS()["id"] == c["task_id"]]
                if not task_row.empty:
                    t = task_row.iloc[0]
                    proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
                    proj_nome = proj.iloc[0]["nome"] if not proj.empty else "?"
                    ore_per_task.append({
                        "task_nome": t["nome"],
                        "progetto": proj_nome,
                        "ore": float(c["ore_dichiarate"]),
                    })
                    totale += float(c["ore_dichiarate"])

        if ore_per_task:
            risultato.append({
                "dipendente_id": did,
                "nome": dip["nome"],
                "profilo": dip["profilo"],
                "ore_contrattuali": int(dip["ore_sett"]),
                "totale_ore": round(totale, 1),
                "ore_per_task": ore_per_task,
                "compilato": True,
            })

    # Aggiungi dipendenti che NON hanno compilato (con almeno 1 task attivo)
    for _, d in _DIPENDENTI().iterrows():
        if d["id"] not in [r["dipendente_id"] for r in risultato]:
            n_task = len(_TASKS()[
                (_TASKS()["dipendente_id"] == d["id"]) &
                (_TASKS()["stato"].isin(["In corso", "Da iniziare"]))
            ])
            if n_task > 0:
                risultato.append({
                    "dipendente_id": d["id"],
                    "nome": d["nome"],
                    "profilo": d["profilo"],
                    "ore_contrattuali": int(d["ore_sett"]),
                    "totale_ore": 0,
                    "ore_per_task": [],
                    "compilato": False,
                })

    return sorted(risultato, key=lambda x: (-x["compilato"], x["nome"]))


@router.get("/me")
def consuntivi_settimana_me(current_user: Utente = Depends(get_current_user)):
    """Vista PERSONALE: i consuntivi del solo chiamante (settimana corrente).
    Self intrinseco: il dipendente è l'utente loggato, niente parametri."""
    if not current_user.dipendente_id:
        raise HTTPException(400, "Utente non collegato a un dipendente")

    lun = datetime.now() - timedelta(days=datetime.now().weekday())
    lun_date = lun.date() if hasattr(lun, 'date') else lun
    ven_date = lun_date + timedelta(days=6)

    consuntivi = _CONSUNTIVI()
    if consuntivi.empty:
        return _consuntivo_vuoto_per_user(current_user.dipendente_id)

    cons_user = consuntivi[
        (consuntivi["dipendente_id"] == current_user.dipendente_id) &
        (consuntivi["settimana"].apply(
            lambda x: lun_date <= (x.date() if hasattr(x, 'date') else x) <= ven_date
        ))
    ]

    try:
        dip = get_dipendente(current_user.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    ore_per_task = []
    totale = 0
    for _, c in cons_user.iterrows():
        if c["ore_dichiarate"] > 0:
            task_row = _TASKS()[_TASKS()["id"] == c["task_id"]]
            if not task_row.empty:
                t = task_row.iloc[0]
                proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
                proj_nome = proj.iloc[0]["nome"] if not proj.empty else "?"
                ore_per_task.append({
                    "task_nome": t["nome"],
                    "progetto": proj_nome,
                    "ore": float(c["ore_dichiarate"]),
                })
                totale += float(c["ore_dichiarate"])

    return {
        "dipendente_id": current_user.dipendente_id,
        "nome": dip["nome"],
        "profilo": dip["profilo"],
        "ore_contrattuali": int(dip["ore_sett"]),
        "totale_ore": round(totale, 1),
        "ore_per_task": ore_per_task,
        "compilato": bool(ore_per_task),
    }


@router.post("/salva")
def salva_consuntivo_endpoint(
    req: SalvaConsuntivoRequest,
    current_user: Utente = Depends(get_current_user),
):
    """Salva il consuntivo settimanale (Pattern Y: self-or-manager)."""
    # User può salvare SOLO i propri consuntivi (anti-impersonation)
    if current_user.ruolo_app != "manager" and req.dipendente_id != current_user.dipendente_id:
        raise HTTPException(403, "Puoi salvare solo i tuoi consuntivi")

    try:
        dip = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    if PERSISTENT_MODE:
        ok = salva_consuntivo(
            dipendente_id=req.dipendente_id,
            settimana=datetime.now(),
            ore_per_task=req.ore_per_task,
            stati_per_task=req.stati_per_task,
            giorni_sede=req.giorni_sede,
            giorni_remoto=req.giorni_remoto,
            ore_assenza=req.ore_assenza,
            tipo_assenza=req.tipo_assenza,
            nota_assenza=req.nota_assenza,
            spese_lista=req.spese if req.spese else None,
        )
        return {"salvato": ok, "dipendente": dip["nome"]}
    return {
        "salvato": True,
        "dipendente": dip["nome"],
        "nota": "Dati non persistenti (db non attivo)",
    }
