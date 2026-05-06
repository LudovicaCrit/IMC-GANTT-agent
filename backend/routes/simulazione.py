"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/simulazione.py — Router per endpoint /api/simulazione
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint per la simulazione di ritardi su task e la propagazione
a cascata sui task successori (predecessore → successore). È usato dal
GANTT (vista manager) e dal Tavolo di Lavoro per "what-if analysis":
"se questo task slitta di N giorni, cosa succede al resto del progetto?"

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────┬──────────┬─────────────────────────┐
│ Path                                 │ Metodo   │ Auth                    │
├──────────────────────────────────────┼──────────┼─────────────────────────┤
│ /api/simulazione/ritardo             │ POST     │ require_manager         │
│ /api/simulazione/ritardo-multiplo    │ POST     │ require_manager         │
└──────────────────────────────────────┴──────────┴─────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. POST /api/simulazione/ritardo
   - Manager-only.
   - Body: {task_id, giorni_ritardo}
   - Simula il ritardo di UN task e propaga a cascata sui successori.
   - Restituisce: task_ritardato, nuova_fine, impatti (lista task
     successori spostati con info sovraccarico), gantt simulato.
   - Logica ricorsiva `propaga()`: per ogni successore, sposta data_inizio
     e data_fine mantenendo durata; ricorre sui successori del successore.

2. POST /api/simulazione/ritardo-multiplo
   - Manager-only.
   - Body: {ritardi: [{task_id, giorni_ritardo}, ...]}
   - Simula ritardi su PIÙ task contemporaneamente con propagazione a
     cascata coordinata.
   - Set `already_shifted` evita doppi spostamenti se due ritardi convergono
     sullo stesso successore.
   - Restituisce: task_ritardati, impatti, gantt_prima/dopo, changed_ids.
   - Versione "multipla" usata principalmente da Analisi e Interventi
     quando si simulano più ritardi insieme; quella singola è il caso base.

PATTERN AUTH USATI
──────────────────
- `require_manager`: simulazioni e GANTT alterati sono dato strategico.

NOTE DI DOMINIO
───────────────
Le funzioni di propagazione sono **ricorsive**: se un task A ritarda e
ha 3 successori (B, C, D), anche B/C/D scivolano; se B ha a sua volta
2 successori (E, F), anche quelli scivolano. La ricorsione si ferma
quando non ci sono più successori.

📌 ATTENZIONE - Funzionalità da rivedere insieme (segnalata nell'handoff):
   La logica di propagazione è quella tradizionale "predecessore vincola
   successore". Funziona, ma:
   - Non considera saturazione del dipendente (un task spostato potrebbe
     andare in periodo già pieno per quella persona)
   - Non considera vincoli esterni (vacanze, festivi, deadline cliente)
   - Non propone alternative (es. "potresti dare il task a un'altra
     persona che ha capacità libera")
   In Tavolo di Lavoro c'è già un endpoint `/api/scenario/*` che usa l'IA
   per fare queste cose in modo più ricco. Da decidere insieme:
   - mantenere i 2 endpoint legacy come "calcolo deterministico veloce"?
   - rimpiazzarli con quelli IA?
   - integrarli (deterministico + suggerimento IA)?

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `carico_settimanale_dipendente`,
  e DataFrame PROGETTI/TASKS.
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper locali `_PROGETTI`, `_TASKS`, `get_oggi`.
📌 TODO: estrarre in moduli condivisi.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import require_manager
from models import Utente
from data import get_dipendente, carico_settimanale_dipendente
from dataframes import _PROGETTI, _TASKS
from utils import get_oggi


# ── DTO ──────────────────────────────────────────────────────────────────
class SimulaRitardoRequest(BaseModel):
    task_id: str
    giorni_ritardo: int


class RitardoItem(BaseModel):
    task_id: str
    giorni_ritardo: int


class SimulaRitardoMultiploRequest(BaseModel):
    ritardi: list[RitardoItem]


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/simulazione", tags=["simulazione"])


@router.post("/ritardo")
def simula_ritardo(
    req: SimulaRitardoRequest,
    _: Utente = Depends(require_manager),
):
    """Simula il ritardo di un singolo task con propagazione a cascata."""
    tasks_sim = _TASKS().copy()
    task_sel = tasks_sim[tasks_sim["id"] == req.task_id]
    if len(task_sel) == 0:
        raise HTTPException(404, "Task non trovato")

    task_sel = task_sel.iloc[0]
    nuova_fine = task_sel["data_fine"] + timedelta(days=req.giorni_ritardo)
    tasks_sim.loc[tasks_sim["id"] == req.task_id, "data_fine"] = nuova_fine

    impatti = []

    def propaga(df, tid, nuova_fine_pred):
        successori = df[df["predecessore"] == tid]
        for idx, succ in successori.iterrows():
            durata = (succ["data_fine"] - succ["data_inizio"]).days
            nuovo_inizio = nuova_fine_pred + timedelta(days=1)
            nuova_fine_s = nuovo_inizio + timedelta(days=durata)
            df.loc[idx, "data_inizio"] = nuovo_inizio
            df.loc[idx, "data_fine"] = nuova_fine_s

            dip = get_dipendente(succ["dipendente_id"])
            carico = carico_settimanale_dipendente(succ["dipendente_id"], nuovo_inizio)

            impatti.append({
                "task_id": succ["id"],
                "task_nome": succ["nome"],
                "dipendente": dip["nome"],
                "nuovo_inizio": nuovo_inizio.isoformat(),
                "nuova_fine": nuova_fine_s.isoformat(),
                "sovraccarico": bool(carico > dip["ore_sett"]),
                "carico": float(carico),
                "capacita": int(dip["ore_sett"]),
            })
            propaga(df, succ["id"], nuova_fine_s)
        return df

    tasks_sim = propaga(tasks_sim, req.task_id, nuova_fine)

    # GANTT aggiornato
    gantt_sim = []
    for _, t in tasks_sim.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]
        gantt_sim.append({
            "id": t["id"],
            "name": t["nome"],
            "start": t["data_inizio"].strftime("%Y-%m-%d"),
            "end": t["data_fine"].strftime("%Y-%m-%d"),
            "progress": 100 if t["stato"] == "Completato" else 50 if t["stato"] == "In corso" else 0,
            "dependencies": t["predecessore"] if t["predecessore"] else "",
            "project": proj["nome"],
            "assignee": dip["nome"],
            "status": t["stato"],
        })

    return {
        "task_ritardato": task_sel["nome"],
        "nuova_fine": nuova_fine.isoformat(),
        "impatti": impatti,
        "gantt": gantt_sim,
    }


@router.post("/ritardo-multiplo")
def simula_ritardo_multiplo(
    req: SimulaRitardoMultiploRequest,
    _: Utente = Depends(require_manager),
):
    """Simula il ritardo di più task contemporaneamente con propagazione coordinata."""
    if not req.ritardi:
        raise HTTPException(400, "Nessun ritardo specificato")

    tasks_sim = _TASKS().copy()
    impatti = []
    task_ritardati = []

    def propaga(df, tid, nuova_fine_pred, already_shifted):
        successori = df[df["predecessore"] == tid]
        for idx, succ in successori.iterrows():
            if succ["id"] in already_shifted:
                continue
            durata = (succ["data_fine"] - succ["data_inizio"]).days
            nuovo_inizio = nuova_fine_pred + timedelta(days=1)
            nuova_fine_s = nuovo_inizio + timedelta(days=durata)
            df.loc[idx, "data_inizio"] = nuovo_inizio
            df.loc[idx, "data_fine"] = nuova_fine_s
            already_shifted.add(succ["id"])

            dip = get_dipendente(succ["dipendente_id"])
            carico = carico_settimanale_dipendente(succ["dipendente_id"], nuovo_inizio)
            proj = _PROGETTI()[_PROGETTI()["id"] == succ["progetto_id"]].iloc[0]

            impatti.append({
                "task_id": succ["id"],
                "task_nome": succ["nome"],
                "progetto": proj["nome"],
                "dipendente": dip["nome"],
                "nuovo_inizio": nuovo_inizio.isoformat(),
                "nuova_fine": nuova_fine_s.isoformat(),
                "sovraccarico": bool(carico > dip["ore_sett"]),
                "carico": float(carico),
                "capacita": int(dip["ore_sett"]),
            })
            propaga(df, succ["id"], nuova_fine_s, already_shifted)
        return df

    already_shifted = set()

    # Applica tutti i ritardi diretti prima
    for r in req.ritardi:
        task_sel = tasks_sim[tasks_sim["id"] == r.task_id]
        if len(task_sel) == 0:
            continue
        task_row = task_sel.iloc[0]
        proj = _PROGETTI()[_PROGETTI()["id"] == task_row["progetto_id"]].iloc[0]
        nuova_fine = task_row["data_fine"] + timedelta(days=r.giorni_ritardo)
        tasks_sim.loc[tasks_sim["id"] == r.task_id, "data_fine"] = nuova_fine
        already_shifted.add(r.task_id)
        task_ritardati.append({
            "task_id": r.task_id,
            "task_nome": task_row["nome"],
            "progetto": proj["nome"],
            "giorni": r.giorni_ritardo,
            "nuova_fine": nuova_fine.isoformat(),
        })

    # Propaga a cascata per ognuno
    for r in req.ritardi:
        nuova_fine = tasks_sim[tasks_sim["id"] == r.task_id].iloc[0]["data_fine"]
        tasks_sim = propaga(tasks_sim, r.task_id, nuova_fine, already_shifted)

    # GANTT prima (originale, per confronto)
    gantt_prima = []
    for _, t in _TASKS().iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]
        gantt_prima.append({
            "id": t["id"],
            "name": t["nome"],
            "start": t["data_inizio"].strftime("%Y-%m-%d"),
            "end": t["data_fine"].strftime("%Y-%m-%d"),
            "progress": 100 if t["stato"] == "Completato" else 50 if t["stato"] == "In corso" else 0,
            "dependencies": t["predecessore"] if t["predecessore"] else "",
            "project": proj["nome"],
            "assignee": dip["nome"],
            "profile": dip["profilo"],
            "status": t["stato"],
            "estimated_hours": int(t["ore_stimate"]),
        })

    # GANTT dopo (simulato)
    gantt_dopo = []
    changed_ids = already_shifted
    for _, t in tasks_sim.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]
        gantt_dopo.append({
            "id": t["id"],
            "name": t["nome"],
            "start": t["data_inizio"].strftime("%Y-%m-%d"),
            "end": t["data_fine"].strftime("%Y-%m-%d"),
            "progress": 100 if t["stato"] == "Completato" else 50 if t["stato"] == "In corso" else 0,
            "dependencies": t["predecessore"] if t["predecessore"] else "",
            "project": proj["nome"],
            "assignee": dip["nome"],
            "profile": dip["profilo"],
            "status": t["stato"],
            "estimated_hours": int(t["ore_stimate"]),
            "changed": bool(t["id"] in changed_ids),
        })

    return {
        "task_ritardati": task_ritardati,
        "impatti": impatti,
        "gantt_prima": gantt_prima,
        "gantt_dopo": gantt_dopo,
        "changed_ids": list(changed_ids),
    }
