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
# ENDPOINT: SCENARIO — TAVOLO DI LAVORO
# ══════════════════════════════════════════════════════════════════════
 
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
 
 
class InterpretaRequest(BaseModel):
    """Richiesta di interpretazione linguaggio naturale."""
    testo: str
    contesto_extra: str = ""
 
 
# ── POST /api/scenario/simula ─────────────────────────────────────────
 
@app.post("/api/scenario/simula")
def scenario_simula(req: SimulaRequest, _: Utente = Depends(require_manager)):
    """
    Simula uno scenario SENZA modificare il database.
    Riceve modifiche, calcola cascata, restituisce GANTT prima/dopo
    + conseguenze + saturazioni.
    """
    from scenario_engine import simula_scenario, _to_date
 
    # Converti request → formato motore
    modifiche = []
    for mod in req.modifiche:
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
 
    # Esegui simulazione
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
 
 
# ── POST /api/scenario/conferma ───────────────────────────────────────
 
@app.post("/api/scenario/conferma")
def scenario_conferma(req: ConfermaRequest, _: Utente = Depends(require_manager)):
    """
    Applica le modifiche dello scenario al database.
    Prima ri-simula per ottenere le date propagate,
    poi scrive tutto nel db.
    """
    from scenario_engine import simula_scenario, _to_date
    from datetime import datetime as dt
 
    # Converti request → formato motore (stessa logica di /simula)
    modifiche = []
    for mod in req.modifiche:
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
 
 
# ── POST /api/scenario/interpreta ─────────────────────────────────────
 
@app.post("/api/scenario/interpreta")
def scenario_interpreta(req: InterpretaRequest, _: Utente = Depends(require_manager)):
    """
    L'IA interpreta il linguaggio naturale del management
    e lo traduce in modifiche strutturate per /scenario/simula.
    NON esegue la simulazione — restituisce le modifiche proposte
    che il frontend mostrerà al management per conferma/modifica.
    """
    import json as json_mod
 
    model = init_gemini(prompt_file="interpreta_scenario.md")
    if model is None:
        raise HTTPException(503, "Agente AI non disponibile")
 
    contesto = get_contesto_ia()
    contesto_json = json_mod.dumps(contesto, ensure_ascii=False, indent=2)
 
    prompt = f"Il management dice:\n\n\"{req.testo}\"\n\n"
    if req.contesto_extra:
        prompt += f"Contesto aggiuntivo dal management: {req.contesto_extra}\n\n"
    prompt += f"Stato attuale del sistema:\n\n```json\n{contesto_json}\n```"
 
    try:
        chat = model.start_chat(history=[])
        response = chat.send_message(prompt)
        risposta_raw = response.text
 
        # Pulisci e parsa JSON
        cleaned = risposta_raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
 
        try:
            risultato = json_mod.loads(cleaned)
        except json_mod.JSONDecodeError:
            risultato = {
                "interpretazione": risposta_raw,
                "modifiche": [],
                "domande": "",
                "note_contesto": "",
                "parse_error": True,
            }
 
        return risultato
 
    except Exception as e:
        raise HTTPException(500, f"Errore agente: {str(e)}")


# ══════════════════════════════════════════════════════════════════════
# AVVIO
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)