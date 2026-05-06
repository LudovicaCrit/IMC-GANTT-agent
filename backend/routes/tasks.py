"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/tasks.py — Router per endpoint /api/tasks
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint per la lettura, modifica e simulazione di impatto
su task. È usato da molteplici pagine del frontend:
  - GANTT (lettura)
  - Tavolo di Lavoro (anteprima impatto + applica modifiche)
  - Pipeline (anteprima impatto + applica per "Conferma e avvia progetto")
  - Analisi e Interventi (applica)

ENDPOINT ESPOSTI
────────────────
┌───────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                      │ Metodo   │ Auth                │
├───────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/tasks                                │ GET      │ AUTH+FILTRO (Sc B)  │
│ /api/tasks/anteprima-impatto              │ POST     │ require_manager     │
│ /api/tasks/applica                        │ POST     │ require_manager     │
│ /api/tasks/{task_id}/elimina              │ PATCH    │ require_manager     │
└───────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/tasks?progetto_id=P00X&profilo=XXX
   - AUTH+FILTRO (Scenario B): user vede solo i propri task; manager vede
     tutti i task aziendali.
   - Esclude task con stato "Eliminato" (soft delete).
   - Filtri opzionali: progetto_id, profilo.
   - Restituisce lista task con dati anagrafici (dipendente, progetto, fase).

2. POST /api/tasks/anteprima-impatto
   - Manager-only.
   - Body: {modifiche: [...], nuovi_task: [...], progetto_id: ""}
   - NON applica nulla — è una preview pura.
   - Calcola saturazioni prima/dopo, alert per il management, GANTT
     simulato dei progetti impattati.
   - Usato da: Pipeline (anteprima nuovi task), Tavolo di Lavoro
     (anteprima modifica task esistenti), Analisi e Interventi.

3. POST /api/tasks/applica
   - Manager-only.
   - Body: {modifiche, nuovi_task, progetto_id, cambia_stato_progetto}
   - APPLICA le modifiche ai dati reali (modifica task, crea task, cambia
     stato progetto se richiesto).
   - Restituisce: risultati per ogni operazione + impatto post-applicazione.
   - Usato dai bottoni "Applica" / "Conferma e avvia progetto".

4. PATCH /api/tasks/{task_id}/elimina
   - Manager-only.
   - Soft delete: cambia lo stato a "Eliminato" (non rimuove la riga).
   - 404 se task non esiste.
   - Per cancellare attività interne, vedi `routes/attivita_interne.py`
     (DELETE /api/attivita-interne/{id}, con regola Pattern Y).

PATTERN AUTH USATI
──────────────────
- `get_current_user` + filter manuale: per /tasks (Scenario B in lettura).
- `require_manager`: per anteprima-impatto, applica, elimina (mutazioni
  che impattano l'intero progetto/azienda).

NOTA STORICA — UNIFICAZIONE PREFISSO TASK
─────────────────────────────────────────
Fino al 5 maggio 2026 esistevano DUE prefissi divergenti:
  /api/task/*  (singolare): anteprima-impatto, applica
  /api/tasks/* (plurale):   lista, elimina
Eredità di scrittura non uniforme di main.py originale, senza ragione
tecnica. Il commit di refactoring del 5 maggio 2026 ha rinominato
tutti gli endpoint singolari al plurale, allineando frontend api.js.
Ora tutti i 4 endpoint vivono coerentemente sotto /api/tasks/*.

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `get_tasks_progetto`, `aggiungi_task`,
  `modifica_task`, `cambia_stato_progetto`, `calcola_impatto_saturazione`,
  e DataFrame DIPENDENTI/PROGETTI/TASKS/CONSUNTIVI.
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper locali `_DIPENDENTI`, `_PROGETTI`, `_TASKS`, `_CONSUNTIVI`, `get_oggi`.
📌 TODO: estrarre in moduli condivisi (debito comune a tutti i router).

📌 TODO Blocco 2 roadmap (Macchina delle Fasi):
   `GET /api/tasks` andrà adattato per restituire i task strutturati per
   fase. Anche le modifiche/applica dovranno coerentemente operare nel
   contesto della fase (un task appartiene a una fase, non solo a un
   progetto).

STORIA
──────
Estratto da main.py il 5 maggio 2026, dopo unificazione prefisso
/api/task → /api/tasks (commit precedente).
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user, require_manager
from models import Utente
from data import (
    get_dipendente, get_tasks_progetto,
    aggiungi_task, modifica_task, cambia_stato_progetto,
    calcola_impatto_saturazione,
)
from dataframes import _DIPENDENTI, _PROGETTI, _TASKS, _CONSUNTIVI
from utils import get_oggi


# ── DTO ──────────────────────────────────────────────────────────────────
class AzioneModifica(BaseModel):
    task_id: str
    campo: str           # "data_fine", "data_inizio", "dipendente_id", "ore_stimate", "stato"
    nuovo_valore: str    # tutto come stringa, il backend converte


class NuovoTask(BaseModel):
    nome: str
    fase: str = ""
    ore_stimate: int = 0
    data_inizio: str = ""        # ISO format
    data_fine: str = ""          # ISO format
    profilo_richiesto: str = ""
    dipendente_id: str = ""
    predecessore: str = ""
    stato: str = "Da iniziare"


class AnteprimaRequest(BaseModel):
    """Richiesta di anteprima impatto — non modifica nulla."""
    modifiche: list[AzioneModifica] = []
    nuovi_task: list[NuovoTask] = []
    progetto_id: str = ""


class ApplicaRequest(BaseModel):
    """Richiesta di applicazione reale — modifica i dati."""
    modifiche: list[AzioneModifica] = []
    nuovi_task: list[NuovoTask] = []
    progetto_id: str = ""
    cambia_stato_progetto: str = ""


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
def lista_tasks(
    progetto_id: Optional[str] = None,
    profilo: Optional[str] = None,
    current_user: Utente = Depends(get_current_user),
):
    """Lista task con filtri opzionali (Scenario B in lettura)."""
    tasks = _TASKS().copy()
    tasks = tasks[tasks["stato"] != "Eliminato"]
    # Scenario B: user vede solo i propri task, manager vede tutto
    if current_user.ruolo_app != "manager":
        tasks = tasks[tasks["dipendente_id"] == current_user.dipendente_id]
    if progetto_id:
        tasks = tasks[tasks["progetto_id"] == progetto_id]
    if profilo:
        tasks = tasks[tasks["profilo_richiesto"] == profilo]

    result = []
    for _, t in tasks.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]
        result.append({
            "id": t["id"],
            "nome": t["nome"],
            "progetto_id": t["progetto_id"],
            "progetto_nome": proj["nome"],
            "fase": t["fase"],
            "stato": t["stato"],
            "ore_stimate": int(t["ore_stimate"]),
            "data_inizio": t["data_inizio"].isoformat(),
            "data_fine": t["data_fine"].isoformat(),
            "profilo_richiesto": t["profilo_richiesto"],
            "dipendente_id": t["dipendente_id"],
            "dipendente_nome": dip["nome"],
            "predecessore": t["predecessore"],
        })
    return result


@router.post("/anteprima-impatto")
def anteprima_impatto(req: AnteprimaRequest, _: Utente = Depends(require_manager)):
    """Calcola l'impatto delle modifiche proposte SENZA applicarle.

    Restituisce saturazioni prima/dopo, alert per il management, e GANTT
    simulato dei progetti impattati.
    """
    task_modifiche = []
    for mod in req.modifiche:
        valore = mod.nuovo_valore
        if mod.campo in ("data_inizio", "data_fine"):
            valore = datetime.fromisoformat(valore)
        elif mod.campo == "ore_stimate":
            valore = int(valore)
        task_modifiche.append({
            "task_id": mod.task_id,
            "campo": mod.campo,
            "nuovo_valore": valore,
        })

    task_nuovi = []
    for nt in req.nuovi_task:
        task_nuovi.append({
            "id": f"PREVIEW_{len(task_nuovi)}",
            "progetto_id": req.progetto_id,
            "nome": nt.nome,
            "fase": nt.fase,
            "ore_stimate": nt.ore_stimate,
            "data_inizio": datetime.fromisoformat(nt.data_inizio) if nt.data_inizio else get_oggi(),
            "data_fine": datetime.fromisoformat(nt.data_fine) if nt.data_fine else get_oggi(),
            "stato": nt.stato,
            "profilo_richiesto": nt.profilo_richiesto,
            "dipendente_id": nt.dipendente_id,
            "predecessore": nt.predecessore,
        })

    impatto = calcola_impatto_saturazione(task_modifiche, task_nuovi if task_nuovi else None)

    # GANTT simulato dei progetti impattati
    gantt_impattati = {}
    for proj in impatto["progetti_impattati"]:
        tasks_proj = get_tasks_progetto(proj["id"])
        gantt_tasks = []
        for _, t in tasks_proj.iterrows():
            try:
                dip = get_dipendente(t["dipendente_id"])
                gantt_tasks.append({
                    "id": t["id"],
                    "name": t["nome"],
                    "start": t["data_inizio"].strftime("%Y-%m-%d"),
                    "end": t["data_fine"].strftime("%Y-%m-%d"),
                    "progress": 100 if t["stato"] == "Completato" else 50 if t["stato"] == "In corso" else 0,
                    "assignee": dip["nome"],
                    "status": t["stato"],
                })
            except (IndexError, KeyError):
                pass
        gantt_impattati[proj["id"]] = gantt_tasks

    return {
        "impatto": impatto,
        "gantt_progetti_impattati": gantt_impattati,
    }


@router.post("/applica")
def applica_modifiche(req: ApplicaRequest, _: Utente = Depends(require_manager)):
    """Applica le modifiche ai dati reali.

    Usato sia da Analisi e Interventi (bottone Applica)
    sia da Pipeline (Conferma e avvia progetto).
    """
    risultati = []

    # 1) Applica modifiche a task esistenti
    for mod in req.modifiche:
        valore = mod.nuovo_valore
        if mod.campo in ("data_inizio", "data_fine"):
            valore = datetime.fromisoformat(valore)
        elif mod.campo == "ore_stimate":
            valore = int(valore)

        ok = modifica_task(mod.task_id, **{mod.campo: valore})
        risultati.append({
            "task_id": mod.task_id,
            "campo": mod.campo,
            "applicato": ok,
        })

    # 2) Crea nuovi task
    nuovi_ids = []
    for nt in req.nuovi_task:
        new_id = aggiungi_task(
            progetto_id=req.progetto_id,
            nome=nt.nome,
            fase=nt.fase,
            ore_stimate=nt.ore_stimate,
            data_inizio=datetime.fromisoformat(nt.data_inizio) if nt.data_inizio else get_oggi(),
            data_fine=datetime.fromisoformat(nt.data_fine) if nt.data_fine else get_oggi(),
            stato=nt.stato,
            profilo_richiesto=nt.profilo_richiesto,
            dipendente_id=nt.dipendente_id,
            predecessore=nt.predecessore,
        )
        nuovi_ids.append(new_id)
        risultati.append({
            "task_id": new_id,
            "campo": "creato",
            "applicato": True,
        })

    # 3) Cambia stato progetto se richiesto
    stato_cambiato = False
    if req.cambia_stato_progetto and req.progetto_id:
        stato_cambiato = cambia_stato_progetto(req.progetto_id, req.cambia_stato_progetto)

    # 4) Ricalcola impatto post-applicazione
    impatto_post = calcola_impatto_saturazione(
        [{"task_id": r["task_id"], "campo": "stato", "nuovo_valore": "check"} for r in risultati if r["applicato"]],
        None
    )

    return {
        "risultati": risultati,
        "nuovi_task_ids": nuovi_ids,
        "stato_progetto_cambiato": stato_cambiato,
        "impatto_post": impatto_post,
    }


@router.patch("/{task_id}/elimina")
def elimina_task_generico(task_id: str, _: Utente = Depends(require_manager)):
    """Elimina (soft) qualsiasi task cambiando lo stato a 'Eliminato'."""
    tasks = _TASKS()
    task = tasks[tasks["id"] == task_id]
    if task.empty:
        raise HTTPException(404, "Task non trovato")

    task_nome = task.iloc[0]["nome"]
    ok = modifica_task(task_id, stato="Eliminato")
    if ok:
        return {"ok": True, "messaggio": f"Task '{task_nome}' eliminato"}
    raise HTTPException(500, "Errore nell'eliminazione")
