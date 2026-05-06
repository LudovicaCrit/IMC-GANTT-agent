"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/attivita_interne.py — Router per /api/attivita-interne
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint per la creazione e cancellazione di "attività interne":
task speciali agganciati al progetto P010 (Attività Interne) usato come
contenitore per formazione, autoapprendimento, attività commerciali
(monitoraggio bandi, prevendita), ecc.

Concettualmente diverse dai task di progetto:
  - non hanno un cliente
  - non concorrono a marginalità (P010 escluso da /api/economia/margini)
  - sono spesso ricorrenti, non scadenze fisse
  - le ore consuntivate qui sono "costo struttura"

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────┬──────────┬─────────────────────────┐
│ Path                                 │ Metodo   │ Auth                    │
├──────────────────────────────────────┼──────────┼─────────────────────────┤
│ /api/attivita-interne                │ POST     │ Pattern Y self-or-manager│
│ /api/attivita-interne/{task_id}      │ DELETE   │ Pattern Y (lookup task) │
└──────────────────────────────────────┴──────────┴─────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. POST /api/attivita-interne
   - Pattern Y (self-or-manager): user può creare attività solo PER SÉ
     stesso (controllo via `current_user.dipendente_id`); manager può
     crearle per chiunque.
   - Body: {dipendente_id, nome, categoria, ore_settimanali, ore_stimate,
     data_inizio, data_fine, note}
   - Crea un task su P010 con progetto_id="P010", fase=categoria,
     stato="In corso", profilo_richiesto = profilo del dipendente.
   - 403 se user prova a creare per altro dipendente.
   - 404 se dipendente non esiste.
   - 400 se P010 non trovato (errore di seed).
   - C'è un `time.sleep(0.3)` per evitare race condition su _next_task_id
     in modalità memoria (legacy).

2. DELETE /api/attivita-interne/{task_id}
   - Pattern Y "doppio": prima recupera il task, poi verifica che il
     dipendente_id del task corrisponda al chiamante (se non manager).
   - Vincolo aggiuntivo: solo task con progetto_id == "P010" sono
     cancellabili da qui (per altri task usare /api/tasks/{id}/elimina).
   - Soft delete: stato → "Eliminato".
   - Errori: 404 (task non trovato), 400 (non è P010), 403 (non sei
     proprietario), 500 (errore eliminazione).

PATTERN AUTH USATI
──────────────────
- `get_current_user` + check manuale del `dipendente_id`:
  • In POST: confronto diretto req.dipendente_id vs current_user.dipendente_id
  • In DELETE: confronto del dipendente_id del task (lookup necessario)

NOTE DI DOMINIO (Francesco Carolla, modello bandi)
──────────────────────────────────────────────────
La categoria "Attività commerciale" è una delle categorie standard delle
attività interne. È stata introdotta dopo il modello bandi del 28 aprile
2026: le ore di "monitoraggio bandi", "preparazione proposal", "prevendita"
si consuntivano qui (come Attività Interne categoria "Attività commerciale"),
NON come task di un progetto in stato "In bando" (stato rimosso).

📌 TODO Blocco 3 roadmap (Form Consuntivazione + Vista Helena):
   Il form di Consuntivazione dovrà permettere di creare facilmente
   nuove attività interne dalla pagina stessa, non più solo da
   Configurazione. Questo endpoint è già pronto per questo uso.

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `aggiungi_task`, `modifica_task`,
  e DataFrame PROGETTI/TASKS.
- `deps`: `get_current_user`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper locali `_PROGETTI`, `_TASKS`.
📌 TODO: estrarre in moduli condivisi.

Lo `time.sleep(0.3)` in POST è un workaround legacy per la race condition
sul contatore `_next_task_id` in modalità memoria. In modalità db
persistente NON serve (il SELECT MAX è atomico). Quando rimuoveremo il
fallback memoria, eliminiamo anche questo sleep.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user
from models import Utente
from data import get_dipendente, aggiungi_task, modifica_task
from dataframes import _PROGETTI, _TASKS


# ── DTO ──────────────────────────────────────────────────────────────────
class AttivitaInternaRequest(BaseModel):
    dipendente_id: str
    nome: str
    categoria: str = "Formazione"
    ore_settimanali: int = 4
    ore_stimate: int = 0
    data_inizio: str
    data_fine: str
    note: str = ""


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/attivita-interne", tags=["attivita-interne"])


@router.post("")
def crea_attivita_interna(
    req: AttivitaInternaRequest,
    current_user: Utente = Depends(get_current_user),
):
    """Crea un task su P010 per un dipendente (Pattern Y self-or-manager)."""
    # User può creare attività SOLO per sé stesso
    if current_user.ruolo_app != "manager" and req.dipendente_id != current_user.dipendente_id:
        raise HTTPException(403, "Puoi creare attività solo per te stesso")

    try:
        dip = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    p010 = _PROGETTI()[_PROGETTI()["id"] == "P010"]
    if p010.empty:
        raise HTTPException(400, "Progetto P010 non trovato")

    time.sleep(0.3)  # workaround race condition contatore in legacy memory mode

    new_id = aggiungi_task(
        progetto_id="P010",
        nome=req.nome,
        fase=req.categoria,
        ore_stimate=req.ore_stimate if req.ore_stimate > 0 else req.ore_settimanali * 20,
        data_inizio=datetime.fromisoformat(req.data_inizio),
        data_fine=datetime.fromisoformat(req.data_fine),
        stato="In corso",
        profilo_richiesto=dip.get("profilo", ""),
        dipendente_id=req.dipendente_id,
    )

    return {
        "ok": True,
        "task_id": new_id,
        "messaggio": f"Attività '{req.nome}' creata per {dip['nome']}",
    }


@router.delete("/{task_id}")
def elimina_attivita_interna(
    task_id: str,
    current_user: Utente = Depends(get_current_user),
):
    """Elimina (soft) un task di attività interna (solo P010, Pattern Y)."""
    tasks = _TASKS()
    task = tasks[tasks["id"] == task_id]
    if task.empty:
        raise HTTPException(404, "Task non trovato")
    if task.iloc[0]["progetto_id"] != "P010":
        raise HTTPException(400, "Solo task di Attività Interne possono essere eliminati da qui")

    # User può cancellare SOLO le proprie attività (anti-impersonation)
    if current_user.ruolo_app != "manager" and task.iloc[0]["dipendente_id"] != current_user.dipendente_id:
        raise HTTPException(403, "Puoi cancellare solo le tue attività")

    ok = modifica_task(task_id, stato="Eliminato")
    if ok:
        return {"ok": True, "messaggio": f"Task {task_id} eliminato"}
    raise HTTPException(500, "Errore nell'eliminazione")
