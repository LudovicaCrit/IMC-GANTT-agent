"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/scenario.py — Router per endpoint /api/scenario
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint del Tavolo di Lavoro per simulazione e applicazione
di modifiche scenario. Sono motori **deterministici** (no IA): dato un
set di modifiche, calcolano cascate, costruiscono GANTT prima/dopo,
oppure applicano al db.

NOTA ARCHITETTURALE: il terzo endpoint storicamente legato al Tavolo,
`POST /api/scenario/interpreta`, **NON è in questo file**. È stato
spostato in `routes/agent.py` come `POST /api/agent/interpreta-scenario`
perché chiama Gemini (IA) e tutti gli endpoint IA-based vivono lì,
indipendentemente dal contesto di business. Vedi STORIA in fondo.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                     │ Metodo   │ Auth                │
├──────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/scenario/simula                     │ POST     │ require_manager     │
│ /api/scenario/conferma                   │ POST     │ require_manager     │
└──────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. POST /api/scenario/simula
   - Manager-only.
   - Body: {modifiche: [ModificaScenario]} dove ogni modifica è di tipo
     "sposta_task" o "cambia_focus".
   - NON modifica il db. Lavora su copie in memoria via scenario_engine.
   - Restituisce:
     • gantt_prima e gantt_dopo (per ogni progetto impattato)
     • conseguenze (lista leggibile ordinata per gravità)
     • scadenze_bucate
     • saturazioni (per dipendente, settimana per settimana)
     • n_task_modificati
     • progetti_impattati

2. POST /api/scenario/conferma
   - Manager-only.
   - Stesso formato body di /simula.
   - Ri-simula per ottenere date propagate, POI scrive nel db chiamando
     `modifica_task` per ogni task cambiato.
   - Restituisce:
     • successo (bool)
     • n_applicati
     • applicati (lista task con kwargs applicati)
     • errori (lista task non riusciti)
     • conseguenze_applicate

PATTERN AUTH USATI
──────────────────
- `require_manager`: scenario è funzione manageriale (Tavolo di Lavoro).

WORKFLOW TIPICO TAVOLO DI LAVORO
─────────────────────────────────
1. Manager scrive in linguaggio naturale → chiama
   POST /api/agent/interpreta-scenario (in routes/agent.py)
   che restituisce: {modifiche: [...], note_contesto, domande}
2. Frontend mostra modifiche al manager
3. Manager conferma → chiama POST /api/scenario/simula con quelle modifiche
   che restituisce: {gantt_prima, gantt_dopo, conseguenze, ...}
4. Frontend mostra confronto prima/dopo
5. Manager dà ok finale → chiama POST /api/scenario/conferma con le
   stesse modifiche, che le applica al db

DIPENDENZE
──────────
- `scenario_engine`: motore deterministico con `simula_scenario()` e
  `_to_date()`. È il "cervello" delle propagazioni cascata.
- `data` (modulo): `get_dipendente`, `get_progetto`, `modifica_task`,
  e DataFrame DIPENDENTI/PROGETTI/TASKS.
- `deps`: `require_manager`.
- `models`: classe `Utente`.

NOTE TECNICHE
─────────────
Helper locali `_DIPENDENTI`, `_PROGETTI`, `_TASKS`, `get_oggi`.
📌 TODO: estrarre in moduli condivisi.

📌 TODO Pulizia DTO orfani: rimuovere da main.py le classi
ModificaScenario, SimulaRequest, ConfermaRequest, InterpretaRequest
nel commit dedicato post-refactoring. (InterpretaRequest è ora in
routes/agent.py).

📌 TODO `SimulaRiassegnaRequest` (vedi handoff v13 sezione F.1):
   In main.py c'è una classe SimulaRiassegnaRequest che non è usata
   da nessun endpoint visibile. Probabile funzionalità incompleta o
   futura. Da analizzare insieme prima di rimuoverla. Potrebbe avere
   un suo endpoint qui in scenario.py se completata.

STORIA
──────
Estratto da main.py il 6 maggio 2026 nell'ambito del refactoring strangler.
Inizialmente conteneva 3 endpoint (simula, conferma, interpreta).
Il 6 maggio (sera) `interpreta` è stato spostato in routes/agent.py come
`/api/agent/interpreta-scenario`, applicando il principio:
  "tutti gli endpoint che chiamano l'IA stanno in routes/agent.py,
   indipendentemente dal contesto di business".
Il prefisso URL esplicita la separazione architetturale:
  /api/scenario/* = motore deterministico (cascate, simulazioni, conferme)
  /api/agent/*    = chiamate IA (interpretazioni, suggerimenti, analisi)
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import require_manager
from models import Utente
import data as data_module
from data import get_dipendente, get_progetto, modifica_task
from scenario_engine import simula_scenario, _to_date


# ── Helper locali (TODO: estrarre in moduli condivisi) ───────────────────
def _DIPENDENTI(): return data_module.DIPENDENTI
def _PROGETTI(): return data_module.PROGETTI
def _TASKS(): return data_module.TASKS

def get_oggi():
    return datetime.now()


# ── DTO ──────────────────────────────────────────────────────────────────
class ModificaScenario(BaseModel):
    """Singola modifica nello scenario."""
    tipo: str                          # "sposta_task" | "cambia_focus"
    # Per sposta_task:
    task_id: str = ""
    nuovo_inizio: str = ""             # ISO date
    nuova_fine: str = ""               # ISO date
    nuove_ore: int = 0
    # Per cambia_focus:
    dipendente_id: str = ""
    progetto_focus: str = ""
    percentuale: int = 100
    durata_settimane: int = 2
    data_inizio_focus: str = ""


class SimulaRequest(BaseModel):
    """Richiesta di simulazione scenario."""
    modifiche: list[ModificaScenario]


class ConfermaRequest(BaseModel):
    """Richiesta di conferma e applicazione scenario."""
    modifiche: list[ModificaScenario]


# ── Helper di conversione modifiche ──────────────────────────────────────
def _converti_modifiche_per_engine(modifiche_dto: list[ModificaScenario]) -> list[dict]:
    """Traduce le modifiche dal formato DTO (Pydantic) al formato motore (dict).

    Ridotta in helper perché identica in /simula e /conferma.
    """
    modifiche = []
    for mod in modifiche_dto:
        m = {"tipo": mod.tipo}
        if mod.tipo == "sposta_task":
            m["task_id"] = mod.task_id
            if mod.nuovo_inizio:
                m["nuovo_inizio"] = mod.nuovo_inizio
            if mod.nuova_fine:
                m["nuova_fine"] = mod.nuova_fine
            if mod.nuove_ore > 0:
                m["nuove_ore"] = mod.nuove_ore
        elif mod.tipo == "cambia_focus":
            m["dipendente_id"] = mod.dipendente_id
            m["progetto_focus"] = mod.progetto_focus
            m["percentuale"] = mod.percentuale
            m["durata_settimane"] = mod.durata_settimane
            if mod.data_inizio_focus:
                m["data_inizio_focus"] = mod.data_inizio_focus
        modifiche.append(m)
    return modifiche


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/scenario", tags=["scenario"])


# ═════════════════════════════════════════════════════════════════════════
# 1. POST /api/scenario/simula — Simulazione senza scrittura
# ═════════════════════════════════════════════════════════════════════════

@router.post("/simula")
def scenario_simula(req: SimulaRequest, _: Utente = Depends(require_manager)):
    """Simula uno scenario SENZA modificare il database.

    Riceve modifiche, calcola cascata, restituisce GANTT prima/dopo
    + conseguenze + saturazioni.
    """
    modifiche = _converti_modifiche_per_engine(req.modifiche)

    # Esegui simulazione (motore deterministico, no IA)
    risultato = simula_scenario(
        _TASKS(), _DIPENDENTI(), _PROGETTI(),
        modifiche, data_oggi=get_oggi()
    )

    # Costruisci GANTT prima/dopo per i progetti impattati
    gantt_prima = {}
    gantt_dopo = {}
    progetti_impattati = set()

    for tid in risultato["task_modificati"]:
        if tid in risultato["tasks_dopo"]:
            pid = risultato["tasks_dopo"][tid].get("progetto_id", "")
            if pid:
                progetti_impattati.add(pid)

    for pid in progetti_impattati:
        proj = get_progetto(pid)

        # GANTT prima
        tasks_prima_prog = []
        for t in risultato["tasks_prima"].values():
            if t.get("progetto_id") != pid:
                continue
            t_inizio = _to_date(t.get("data_inizio"))
            t_fine = _to_date(t.get("data_fine"))
            tasks_prima_prog.append({
                "id": t["id"],
                "name": t.get("nome", ""),
                "start": t_inizio.isoformat() if t_inizio else "",
                "end": t_fine.isoformat() if t_fine else "",
                "status": t.get("stato", ""),
                "assignee": get_dipendente(t.get("dipendente_id", ""))["nome"],
                "estimated_hours": t.get("ore_stimate", 0),
                "project": proj["nome"],
            })

        # GANTT dopo
        tasks_dopo_prog = []
        for t in risultato["tasks_dopo"].values():
            if t.get("progetto_id") != pid:
                continue
            t_inizio = _to_date(t.get("data_inizio"))
            t_fine = _to_date(t.get("data_fine"))
            tasks_dopo_prog.append({
                "id": t["id"],
                "name": t.get("nome", ""),
                "start": t_inizio.isoformat() if t_inizio else "",
                "end": t_fine.isoformat() if t_fine else "",
                "status": t.get("stato", ""),
                "assignee": get_dipendente(t.get("dipendente_id", ""))["nome"],
                "estimated_hours": t.get("ore_stimate", 0),
                "project": proj["nome"],
            })

        gantt_prima[pid] = {
            "progetto": proj["nome"],
            "cliente": proj.get("cliente", ""),
            "tasks": tasks_prima_prog,
        }
        gantt_dopo[pid] = {
            "progetto": proj["nome"],
            "cliente": proj.get("cliente", ""),
            "tasks": tasks_dopo_prog,
        }

    return {
        "gantt_prima": gantt_prima,
        "gantt_dopo": gantt_dopo,
        "conseguenze": risultato["conseguenze"],
        "scadenze_bucate": risultato["scadenze_bucate"],
        "saturazioni": risultato["saturazioni"],
        "n_task_modificati": len(risultato["task_modificati"]),
        "progetti_impattati": [
            {"id": pid, "nome": get_progetto(pid)["nome"]}
            for pid in progetti_impattati
        ],
    }


# ═════════════════════════════════════════════════════════════════════════
# 2. POST /api/scenario/conferma — Applicazione scenario al database
# ═════════════════════════════════════════════════════════════════════════

@router.post("/conferma")
def scenario_conferma(req: ConfermaRequest, _: Utente = Depends(require_manager)):
    """Applica le modifiche dello scenario al database.

    Prima ri-simula per ottenere le date propagate, poi scrive tutto nel db.
    """
    from datetime import datetime as dt

    modifiche = _converti_modifiche_per_engine(req.modifiche)

    risultato = simula_scenario(
        _TASKS(), _DIPENDENTI(), _PROGETTI(),
        modifiche, data_oggi=get_oggi()
    )

    # Applica al db ogni task che è cambiato
    applicati = []
    errori = []

    for tid in risultato["task_modificati"]:
        task_dopo = risultato["tasks_dopo"].get(tid)
        task_prima = risultato["tasks_prima"].get(tid)
        if not task_dopo or not task_prima:
            continue

        kwargs = {}
        nuovo_inizio = _to_date(task_dopo.get("data_inizio"))
        vecchio_inizio = _to_date(task_prima.get("data_inizio"))
        nuova_fine = _to_date(task_dopo.get("data_fine"))
        vecchia_fine = _to_date(task_prima.get("data_fine"))

        if nuovo_inizio and vecchio_inizio and nuovo_inizio != vecchio_inizio:
            kwargs["data_inizio"] = dt.combine(nuovo_inizio, dt.min.time())
        if nuova_fine and vecchia_fine and nuova_fine != vecchia_fine:
            kwargs["data_fine"] = dt.combine(nuova_fine, dt.min.time())

        nuove_ore = task_dopo.get("ore_stimate")
        vecchie_ore = task_prima.get("ore_stimate")
        if nuove_ore and vecchie_ore and nuove_ore != vecchie_ore:
            kwargs["ore_stimate"] = nuove_ore

        if kwargs:
            ok = modifica_task(tid, **kwargs)
            if ok:
                applicati.append({
                    "task_id": tid,
                    "task_nome": task_dopo.get("nome", ""),
                    "progetto": get_progetto(task_dopo.get("progetto_id", ""))["nome"],
                    "modifiche_applicate": {k: str(v) for k, v in kwargs.items()},
                })
            else:
                errori.append({
                    "task_id": tid,
                    "task_nome": task_dopo.get("nome", ""),
                    "errore": "Modifica non riuscita",
                })

    return {
        "successo": len(errori) == 0,
        "n_applicati": len(applicati),
        "applicati": applicati,
        "errori": errori,
        "conseguenze_applicate": risultato["conseguenze"],
    }
