"""
IMC-Group GANTT Agent — Backend API (FastAPI)
Espone endpoint REST per il frontend React.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from scenario_engine import simula_scenario, risultato_per_api, _to_date as scenario_to_date
from auth_routes import router as auth_router
from routes.dipendenti import router as dipendenti_router
from routes.progetti import router as progetti_router
from routes.economia import router as economia_router
from routes.risorse import router as risorse_router
from routes.gantt import router as gantt_router
from routes.segnalazioni import router as segnalazioni_router
from routes.pianificazione import router as pianificazione_router
from routes.consuntivi import router as consuntivi_router
from routes.tasks import router as tasks_router
from routes.simulazione import router as simulazione_router
from routes.attivita_interne import router as attivita_interne_router
from routes.configurazione import router as configurazione_router
from routes.agent import router as agent_router
from routes.scenario import router as scenario_router
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from deps import get_current_user, require_manager
from models import (
    Ruolo, Competenza, DipendentiCompetenze, FaseStandard, Fase, Utente, get_session, Dipendente,
)

import data as data_module
from data import (
    get_dipendente, get_tasks_progetto, get_progetti_dipendente,
    carico_settimanale_dipendente, ore_consuntivate_progetto,
    tasso_compilazione_progetto,
    aggiungi_task, modifica_task, cambia_stato_progetto,
    calcola_impatto_saturazione, get_progetto,
)

# Accesso ai DataFrame sempre via modulo (non copie statiche)
# Così dopo _reload() vediamo i dati aggiornati
def _DIPENDENTI(): return data_module.DIPENDENTI
def _PROGETTI(): return data_module.PROGETTI
def _TASKS(): return data_module.TASKS
def _CONSUNTIVI(): return data_module.CONSUNTIVI

# Prova a importare le funzioni persistenti (db mode)
try:
    from data import get_segnalazioni, aggiungi_segnalazione
    from data import salva_bozza_pianificazione, carica_bozza_pianificazione
    from data import salva_consuntivo
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False
from agent import (
    init_gemini, costruisci_contesto, chiedi_agente, is_agent_available,
)

app = FastAPI(title="IMC-Group GANTT Agent", version="0.1.0")

# Rate limiter - strategia: per IP del client
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router)
app.include_router(dipendenti_router)
app.include_router(progetti_router)
app.include_router(economia_router)
app.include_router(risorse_router)
app.include_router(gantt_router)
app.include_router(segnalazioni_router)
app.include_router(pianificazione_router)
app.include_router(consuntivi_router)
app.include_router(tasks_router)
app.include_router(simulazione_router)
app.include_router(attivita_interne_router)
app.include_router(configurazione_router)
app.include_router(agent_router)
app.include_router(scenario_router)

# CORS per permettere al frontend React di chiamare il backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_oggi():
    return datetime.now()

# ── Cache contesto per IA ──
_contesto_cache = {
    "data": None,
    "timestamp": None,
}

def get_contesto_ia():
    """Restituisce il contesto per l'IA, ricalcolandolo solo se i dati sono cambiati."""
    import json as json_mod
    
    # Invalida cache ogni 60 secondi (o dopo modifica dati)
    now = datetime.now()
    if (_contesto_cache["data"] is not None 
        and _contesto_cache["timestamp"] 
        and (now - _contesto_cache["timestamp"]).seconds < 60):
        return _contesto_cache["data"]
    
    # Ricostruisci contesto
    progetti_ctx = []
    for _, p in _PROGETTI().iterrows():
        if p["stato"] not in ("In esecuzione", "In bando"):
            continue
        tasks_prog = _TASKS()[_TASKS()["progetto_id"] == p["id"]]
        tasks_list = []
        for _, t in tasks_prog.iterrows():
            dip_nome = get_dipendente(t["dipendente_id"])["nome"] if t["dipendente_id"] else "Non assegnato"
            tasks_list.append({
                "id": t["id"], "nome": t["nome"],
                "assegnato_a": dip_nome,
                "inizio": t["data_inizio"].strftime("%Y-%m-%d") if t["data_inizio"] else "",
                "fine": t["data_fine"].strftime("%Y-%m-%d") if t["data_fine"] else "",
                "ore_stimate": int(t["ore_stimate"]),
                "stato": t["stato"],
            })
        progetti_ctx.append({
            "id": p["id"], "nome": p["nome"],
            "cliente": p["cliente"], "stato": p["stato"],
            "scadenza": p["data_fine"].strftime("%Y-%m-%d") if p["data_fine"] else "",
            "task": tasks_list,
        })

    dipendenti_ctx = []
    for _, d in _DIPENDENTI().iterrows():
        carico = carico_settimanale_dipendente(d["id"], get_oggi())
        dipendenti_ctx.append({
            "id": d["id"], "nome": d["nome"],
            "profilo": d["profilo"],
            "ore_sett": int(d["ore_sett"]),
            "saturazione_pct": round(carico / d["ore_sett"] * 100),
        })

    contesto = {
        "data_corrente": get_oggi().strftime("%Y-%m-%d"),
        "progetti": progetti_ctx,
        "dipendenti": dipendenti_ctx,
    }
    
    _contesto_cache["data"] = contesto
    _contesto_cache["timestamp"] = now
    
    return contesto

# ── Store segnalazioni in memoria (in futuro: database) ──
SEGNALAZIONI_STORE = []
_segn_counter = 0

def _next_segn_id():
    global _segn_counter
    _segn_counter += 1
    return f"S{_segn_counter:03d}"


# ══════════════════════════════════════════════════════════════════════
# MODELLI REQUEST/RESPONSE
# ══════════════════════════════════════════════════════════════════════
 
class AttivitaInternaRequest(BaseModel):
    dipendente_id: str
    nome: str
    categoria: str = "Formazione"
    ore_settimanali: int = 4
    ore_stimate: int = 0
    data_inizio: str
    data_fine: str
    note: str = ""


class ChatRequest(BaseModel):
    dipendente_id: str
    messaggio: str
    ore_compilate: dict[str, float] = {}
    stati_compilati: dict[str, str] = {}
    ore_assenza: float = 0.0
    tipo_assenza: str = ""
    nota_assenza: str = ""
    spese: list[dict] = []
    chat_history: list[dict] = []  # [{"role": "user"|"assistant", "content": "..."}]


class SimulaRitardoRequest(BaseModel):
    task_id: str
    giorni_ritardo: int


class RitardoItem(BaseModel):
    task_id: str
    giorni_ritardo: int


class SimulaRitardoMultiploRequest(BaseModel):
    ritardi: list[RitardoItem]


class SimulaRiassegnaRequest(BaseModel):
    task_id: str
    nuovo_dipendente_id: str



@app.post("/api/fasi")
def crea_fase(req: dict, _: Utente = Depends(require_manager)):
    session = get_session()
    fase = Fase(
        progetto_id=req["progetto_id"],
        nome=req["nome"],
        ordine=req.get("ordine", 1),
        data_inizio=req.get("data_inizio"),
        data_fine=req.get("data_fine"),
        ore_vendute=req.get("ore_vendute", 0),
        stato="Da iniziare",
    )
    session.add(fase)
    session.commit()
    result = {"id": fase.id, "nome": fase.nome}
    session.close()
    return result


# ── FASI DI PROGETTO ───────────────────────────────────────────────────

@app.get("/api/fasi/{progetto_id}")
def lista_fasi_progetto(progetto_id: str, _: Utente = Depends(require_manager)):
    """Lista fasi di un progetto con totali ore."""
    session = get_session()
    fasi = session.query(Fase).filter(Fase.progetto_id == progetto_id).order_by(Fase.ordine).all()
    result = []
    for f in fasi:
        # Calcola ore consumate dai consuntivi dei task in questa fase
        tasks_fase = session.query(Task).filter(Task.fase_id == f.id).all()
        task_ids = [t.id for t in tasks_fase]
        ore_consumate = 0
        if task_ids:
            from sqlalchemy import func
            ore_consumate = session.query(func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0)).filter(
                Consuntivo.task_id.in_(task_ids)
            ).scalar()

        result.append({
            "id": f.id,
            "nome": f.nome,
            "ordine": f.ordine,
            "data_inizio": f.data_inizio.isoformat() if f.data_inizio else None,
            "data_fine": f.data_fine.isoformat() if f.data_fine else None,
            "ore_vendute": f.ore_vendute,
            "ore_pianificate": f.ore_pianificate,
            "ore_consumate": float(ore_consumate),
            "ore_rimanenti": (f.ore_vendute or 0) - float(ore_consumate),
            "stato": f.stato,
            "n_task": len(tasks_fase),
            "note": f.note or "",
        })
    session.close()
    return result


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: ANTEPRIMA IMPATTO + APPLICA MODIFICHE
# ══════════════════════════════════════════════════════════════════════

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
    progetto_id: str = ""        # per nuovi task senza progetto esplicito


class ApplicaRequest(BaseModel):
    """Richiesta di applicazione reale — modifica i dati."""
    modifiche: list[AzioneModifica] = []
    nuovi_task: list[NuovoTask] = []
    progetto_id: str = ""
    cambia_stato_progetto: str = ""  # es. "In esecuzione"


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: PIPELINE — SALVA BOZZA PIANIFICAZIONE
# ══════════════════════════════════════════════════════════════════════

class SalvaBozzaRequest(BaseModel):
    progetto_id: str
    dati_json: dict  # snapshot completo della tabella task in pianificazione


# Store bozze in memoria (in futuro: database)
BOZZE_STORE = {}


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: SALVA CONSUNTIVO
# ══════════════════════════════════════════════════════════════════════

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
 

# ══════════════════════════════════════════════════════════════════════
# AVVIO
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)