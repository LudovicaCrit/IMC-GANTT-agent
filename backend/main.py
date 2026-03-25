"""
IMC-Group GANTT Agent — Backend API (FastAPI)
Espone endpoint REST per il frontend React.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

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
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False
from agent import (
    init_gemini, costruisci_contesto, chiedi_agente, is_agent_available,
)

app = FastAPI(title="IMC-Group GANTT Agent", version="0.1.0")

# CORS per permettere al frontend React di chiamare il backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OGGI = datetime(2026, 3, 9)

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


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: _DIPENDENTI()
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/dipendenti")
def lista_dipendenti():
    result = []
    for _, d in _DIPENDENTI().iterrows():
        carico = carico_settimanale_dipendente(d["id"], OGGI)
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


@app.get("/api/dipendenti/{dip_id}")
def dettaglio_dipendente(dip_id: str):
    try:
        d = get_dipendente(dip_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    carico = carico_settimanale_dipendente(dip_id, OGGI)
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


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: _PROGETTI()
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/progetti")
def lista_progetti():
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


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: _TASKS() / GANTT
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/tasks")
def lista_tasks(progetto_id: Optional[str] = None, profilo: Optional[str] = None):
    tasks = _TASKS().copy()
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


@app.get("/api/gantt")
def dati_gantt(progetto_id: Optional[str] = None):
    """Restituisce i dati formattati per un componente GANTT."""
    tasks = _TASKS().copy()
    if progetto_id:
        tasks = tasks[tasks["progetto_id"] == progetto_id]

    result = []
    for _, t in tasks.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]
        result.append({
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
    return result


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: CARICO RISORSE (heatmap)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/risorse/carico")
def carico_risorse(settimane: int = 12):
    """Restituisce la heatmap di saturazione per tutte le risorse."""
    from datetime import timedelta
    result = []
    for _, d in _DIPENDENTI().iterrows():
        settimane_data = []
        for w in range(settimane):
            sett = OGGI + timedelta(weeks=w)
            lun = sett - timedelta(days=sett.weekday())
            carico = carico_settimanale_dipendente(d["id"], sett)
            settimane_data.append({
                "settimana": lun.strftime("%Y-%m-%d"),
                "settimana_label": lun.strftime("%d/%m"),
                "ore_assegnate": float(carico),
                "saturazione_pct": min(150, round(carico / d["ore_sett"] * 100)),
            })
        result.append({
            "dipendente_id": d["id"],
            "nome": d["nome"],
            "profilo": d["profilo"],
            "ore_sett": int(d["ore_sett"]),
            "settimane": settimane_data,
        })
    return result


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: CHATBOT CONSUNTIVAZIONE
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/agent/status")
def agent_status():
    return {"available": is_agent_available()}


@app.post("/api/agent/chat")
def agent_chat(req: ChatRequest):
    import json as json_mod

    try:
        dip = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    tasks_attivi = _TASKS()[
        (_TASKS()["dipendente_id"] == req.dipendente_id) &
        (_TASKS()["stato"].isin(["In corso", "Da iniziare"]))
    ]

    contesto = costruisci_contesto(
        dip_data=dip,
        ore_compilate=req.ore_compilate,
        stati_compilati=req.stati_compilati,
        tasks_attivi=tasks_attivi,
        ore_assenza=req.ore_assenza,
        tipo_assenza=req.tipo_assenza,
        nota_assenza=req.nota_assenza,
        spese=req.spese if req.spese else None,
        ore_contrattuali=dip["ore_sett"],
    )

    model = init_gemini()
    risposta = chiedi_agente(model, contesto, req.messaggio, chat_history=req.chat_history)

    # ── Parsa blocchi strutturati dalla risposta ──
    # Sia [MAPPATURA_ORE] che [SEGNALAZIONE] vengono estratti
    # e rimossi dalla risposta visibile al dipendente.

    risposta_pulita = risposta
    segnalazione = None
    mappatura_ore = None

    # 1) Parsa [MAPPATURA_ORE]
    if "[MAPPATURA_ORE]" in risposta_pulita:
        idx = risposta_pulita.index("[MAPPATURA_ORE]")
        mappatura_raw = risposta_pulita[idx + len("[MAPPATURA_ORE]"):]
        risposta_pulita = risposta_pulita[:idx].strip()

        # Se c'è anche una segnalazione dopo la mappatura, separale
        if "[SEGNALAZIONE]" in mappatura_raw:
            segn_idx = mappatura_raw.index("[SEGNALAZIONE]")
            segn_part = mappatura_raw[segn_idx:]
            mappatura_raw = mappatura_raw[:segn_idx]
            # La segnalazione la processiamo dopo
            risposta_pulita_con_segn = risposta_pulita + "\n" + segn_part
        else:
            risposta_pulita_con_segn = None

        # Estrai il JSON dalla mappatura
        mappatura_raw = mappatura_raw.strip()
        # Rimuovi eventuali backtick markdown
        if mappatura_raw.startswith("```json"):
            mappatura_raw = mappatura_raw[7:]
        if mappatura_raw.startswith("```"):
            mappatura_raw = mappatura_raw[3:]
        if mappatura_raw.endswith("```"):
            mappatura_raw = mappatura_raw[:-3]
        mappatura_raw = mappatura_raw.strip()

        try:
            mappatura_ore = json_mod.loads(mappatura_raw)
        except json_mod.JSONDecodeError:
            # Se non riesce a parsare, ignora la mappatura
            mappatura_ore = None

        # Se c'era una segnalazione dopo la mappatura, rimettila per il parsing
        if risposta_pulita_con_segn:
            risposta_pulita = risposta_pulita  # resta pulita
            # Processiamo la segnalazione dalla parte estratta
            risposta_per_segn = segn_part
        else:
            risposta_per_segn = ""
    else:
        risposta_per_segn = risposta_pulita

    # 2) Parsa [SEGNALAZIONE]
    testo_da_parsare = risposta_per_segn if "[SEGNALAZIONE]" in risposta_per_segn else risposta_pulita
    if "[SEGNALAZIONE]" in testo_da_parsare:
        idx = testo_da_parsare.index("[SEGNALAZIONE]")
        segnalazione_raw = testo_da_parsare[idx:]

        # Rimuovi dalla risposta visibile (se non già rimossa dalla mappatura)
        if "[SEGNALAZIONE]" in risposta_pulita:
            risposta_pulita = risposta_pulita[:risposta_pulita.index("[SEGNALAZIONE]")].strip()

        segnalazione = segnalazione_raw

        # Parsa tipo, dettaglio, priorità dalla segnalazione
        segn_tipo = "generico"
        segn_priorita = "media"
        segn_dettaglio = segnalazione_raw
        for line in segnalazione_raw.split("\n"):
            line_lower = line.strip().lower()
            if "tipo:" in line_lower:
                segn_tipo = line.split(":", 1)[1].strip().lower().replace(" ", "_")
            elif "priorit" in line_lower:
                val = line.split(":", 1)[1].strip().lower()
                if "alta" in val: segn_priorita = "alta"
                elif "bassa" in val: segn_priorita = "bassa"
            elif "dettaglio:" in line_lower or "descrizione:" in line_lower:
                segn_dettaglio = line.split(":", 1)[1].strip()

        if PERSISTENT_MODE:
            aggiungi_segnalazione(segn_tipo, segn_priorita, req.dipendente_id, segn_dettaglio)
        else:
            SEGNALAZIONI_STORE.append({
                "id": _next_segn_id(),
                "tipo": segn_tipo,
                "priorita": segn_priorita,
                "dipendente_id": req.dipendente_id,
                "dipendente": dip["nome"],
                "dettaglio": segn_dettaglio,
                "timestamp": OGGI.strftime("%Y-%m-%d %H:%M"),
            })

    return {
        "risposta": risposta_pulita,
        "segnalazione": segnalazione,
        "mappatura_ore": mappatura_ore,
        "contesto_carico": contesto.get("carico_complessivo"),
    }


@app.get("/api/segnalazioni")
def lista_segnalazioni():
    """Restituisce tutte le segnalazioni raccolte."""
    if PERSISTENT_MODE:
        return get_segnalazioni()
    return SEGNALAZIONI_STORE


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: SIMULAZIONI
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/simulazione/ritardo")
def simula_ritardo(req: SimulaRitardoRequest):
    from datetime import timedelta

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

    # Restituisci GANTT aggiornato
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


@app.post("/api/simulazione/ritardo-multiplo")
def simula_ritardo_multiplo(req: SimulaRitardoMultiploRequest):
    """Simula il ritardo di più task contemporaneamente con propagazione a cascata."""
    from datetime import timedelta

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

    # Poi propaga a cascata per ognuno
    for r in req.ritardi:
        nuova_fine = tasks_sim[tasks_sim["id"] == r.task_id].iloc[0]["data_fine"]
        tasks_sim = propaga(tasks_sim, r.task_id, nuova_fine, already_shifted)

    # GANTT originale (per confronto prima/dopo)
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

    # GANTT simulato
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
            "changed": bool(t["id"] in changed_ids),  # flag per evidenziare
        })

    return {
        "task_ritardati": task_ritardati,
        "impatti": impatti,
        "gantt_prima": gantt_prima,
        "gantt_dopo": gantt_dopo,
        "changed_ids": list(changed_ids),
    }


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: AGENTE ANALISI GANTT
# ══════════════════════════════════════════════════════════════════════

class AnalisiRequest(BaseModel):
    segnalazione_tipo: str
    segnalazione_dettaglio: str
    dipendente_id: str
    priorita: str = "media"


@app.post("/api/agent/analisi-gantt")
def analisi_gantt(req: AnalisiRequest):
    """Riceve una segnalazione e restituisce proposte di redistribuzione."""
    import json as json_mod

    # Costruisci contesto completo per l'agente
    try:
        dip_segnalante = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(400, f"Dipendente '{req.dipendente_id}' non trovato")

    # Tutti i dipendenti con carico
    dip_contesto = []
    for _, d in _DIPENDENTI().iterrows():
        carico = carico_settimanale_dipendente(d["id"], OGGI)
        progetti = get_progetti_dipendente(d["id"])
        tasks_attivi = _TASKS()[
            (_TASKS()["dipendente_id"] == d["id"]) &
            (_TASKS()["stato"].isin(["In corso", "Da iniziare"]))
        ]
        dip_contesto.append({
            "id": d["id"],
            "nome": d["nome"],
            "profilo": d["profilo"],
            "ore_sett": int(d["ore_sett"]),
            "carico_corrente": float(carico),
            "saturazione_pct": round(carico / d["ore_sett"] * 100),
            "progetti": progetti,
            "task_attivi": [
                {
                    "id": t["id"],
                    "nome": t["nome"],
                    "progetto": _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]].iloc[0]["nome"],
                    "ore_stimate": int(t["ore_stimate"]),
                    "data_inizio": t["data_inizio"].strftime("%Y-%m-%d"),
                    "data_fine": t["data_fine"].strftime("%Y-%m-%d"),
                    "stato": t["stato"],
                    "profilo_richiesto": t["profilo_richiesto"],
                    "predecessore": t["predecessore"] if t["predecessore"] else None,
                }
                for _, t in tasks_attivi.iterrows()
            ],
        })

    # Tutti i progetti con scadenze
    proj_contesto = []
    for _, p in _PROGETTI().iterrows():
        if p["stato"] in ["In esecuzione", "In bando"]:
            proj_contesto.append({
                "id": p["id"],
                "nome": p["nome"],
                "cliente": p["cliente"],
                "stato": p["stato"],
                "data_fine": p["data_fine"].strftime("%Y-%m-%d"),
                "budget_ore": int(p["budget_ore"]),
            })

    contesto_completo = {
        "segnalazione": {
            "tipo": req.segnalazione_tipo,
            "dettaglio": req.segnalazione_dettaglio,
            "dipendente": dip_segnalante["nome"],
            "dipendente_id": req.dipendente_id,
            "priorita": req.priorita,
        },
        "dipendenti": dip_contesto,
        "progetti": proj_contesto,
        "data_corrente": OGGI.strftime("%Y-%m-%d"),
    }

    # Chiama Gemini con il prompt specializzato
    model = init_gemini(prompt_file="analisi_segnalazioni.md")
    if model is None:
        raise HTTPException(503, "Agente AI non disponibile")

    contesto_json = json_mod.dumps(contesto_completo, ensure_ascii=False, indent=2)
    prompt = f"Analizza questa segnalazione e proponi redistribuzioni:\n\n```json\n{contesto_json}\n```"

    try:
        chat = model.start_chat(history=[])
        response = chat.send_message(prompt)
        risposta_raw = response.text

        # Tenta di parsare il JSON dalla risposta
        # Rimuovi eventiali backtick markdown
        cleaned = risposta_raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            proposte = json_mod.loads(cleaned)
        except json_mod.JSONDecodeError:
            # Se non riesce a parsare, restituisci il testo grezzo
            proposte = {"raw_response": risposta_raw, "parse_error": True}

        return {
            "proposte": proposte,
            "contesto": {
                "segnalazione": contesto_completo["segnalazione"],
                "dipendente_saturazione": next(
                    (d["saturazione_pct"] for d in dip_contesto if d["id"] == req.dipendente_id), 0
                ),
            },
        }

    except Exception as e:
        raise HTTPException(500, f"Errore agente: {str(e)}")


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


@app.post("/api/task/anteprima-impatto")
def anteprima_impatto(req: AnteprimaRequest):
    """
    Calcola l'impatto delle modifiche proposte SENZA applicarle.
    Restituisce saturazioni prima/dopo e alert per il management.
    """
    from datetime import datetime as dt

    # Converti modifiche nel formato atteso da calcola_impatto_saturazione
    task_modifiche = []
    for mod in req.modifiche:
        valore = mod.nuovo_valore
        # Converti date da stringa ISO a datetime
        if mod.campo in ("data_inizio", "data_fine"):
            valore = dt.fromisoformat(valore)
        elif mod.campo == "ore_stimate":
            valore = int(valore)
        task_modifiche.append({
            "task_id": mod.task_id,
            "campo": mod.campo,
            "nuovo_valore": valore,
        })

    # Converti nuovi task
    task_nuovi = []
    for nt in req.nuovi_task:
        task_nuovi.append({
            "id": f"PREVIEW_{len(task_nuovi)}",
            "progetto_id": req.progetto_id,
            "nome": nt.nome,
            "fase": nt.fase,
            "ore_stimate": nt.ore_stimate,
            "data_inizio": dt.fromisoformat(nt.data_inizio) if nt.data_inizio else OGGI,
            "data_fine": dt.fromisoformat(nt.data_fine) if nt.data_fine else OGGI,
            "stato": nt.stato,
            "profilo_richiesto": nt.profilo_richiesto,
            "dipendente_id": nt.dipendente_id,
            "predecessore": nt.predecessore,
        })

    impatto = calcola_impatto_saturazione(task_modifiche, task_nuovi if task_nuovi else None)

    # Aggiungi GANTT simulato dei progetti impattati
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


@app.post("/api/task/applica")
def applica_modifiche(req: ApplicaRequest):
    """
    Applica le modifiche ai dati reali.
    Usato sia da Analisi e Interventi (bottone Applica)
    sia da Pipeline (Conferma e avvia progetto).
    """
    from datetime import datetime as dt

    risultati = []

    # 1) Applica modifiche a task esistenti
    for mod in req.modifiche:
        valore = mod.nuovo_valore
        if mod.campo in ("data_inizio", "data_fine"):
            valore = dt.fromisoformat(valore)
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
            data_inizio=dt.fromisoformat(nt.data_inizio) if nt.data_inizio else OGGI,
            data_fine=dt.fromisoformat(nt.data_fine) if nt.data_fine else OGGI,
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


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: PIPELINE — SALVA BOZZA PIANIFICAZIONE
# ══════════════════════════════════════════════════════════════════════

class SalvaBozzaRequest(BaseModel):
    progetto_id: str
    dati_json: dict  # snapshot completo della tabella task in pianificazione


# Store bozze in memoria (in futuro: database)
BOZZE_STORE = {}


@app.post("/api/pianificazione/salva-bozza")
def salva_bozza(req: SalvaBozzaRequest):
    """Salva o aggiorna una bozza di pianificazione."""
    if PERSISTENT_MODE:
        salva_bozza_pianificazione(req.progetto_id, req.dati_json)
    else:
        BOZZE_STORE[req.progetto_id] = {
            "progetto_id": req.progetto_id,
            "dati_json": req.dati_json,
            "timestamp": OGGI.strftime("%Y-%m-%d %H:%M"),
        }
    return {"salvato": True, "progetto_id": req.progetto_id}


@app.get("/api/pianificazione/bozza/{progetto_id}")
def carica_bozza(progetto_id: str):
    """Carica una bozza di pianificazione salvata."""
    if PERSISTENT_MODE:
        dati = carica_bozza_pianificazione(progetto_id)
        return {"progetto_id": progetto_id, "dati_json": dati}
    if progetto_id in BOZZE_STORE:
        return BOZZE_STORE[progetto_id]
    return {"progetto_id": progetto_id, "dati_json": None}


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT: EXPORT GANTT PDF
# ══════════════════════════════════════════════════════════════════════

from fastapi.responses import Response

@app.get("/api/gantt/export-pdf")
def export_gantt_pdf(progetto_id: Optional[str] = None):
    """Genera e scarica un PDF del GANTT."""
    from gantt_pdf import genera_gantt_pdf

    # Riusa la logica di dati_gantt
    tasks = _TASKS().copy()
    if progetto_id:
        tasks = tasks[tasks["progetto_id"] == progetto_id]

    # Filtra solo progetti attivi (non sospesi)
    progetti_attivi = _PROGETTI()[~_PROGETTI()["stato"].isin(["Sospeso"])]["id"].tolist()
    if not progetto_id:
        tasks = tasks[tasks["progetto_id"].isin(progetti_attivi)]

    gantt_data = []
    for _, t in tasks.iterrows():
        dip = get_dipendente(t["dipendente_id"])
        proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
        proj_nome = proj.iloc[0]["nome"] if len(proj) > 0 else "?"
        gantt_data.append({
            "id": t["id"],
            "name": t["nome"],
            "start": t["data_inizio"].strftime("%Y-%m-%d"),
            "end": t["data_fine"].strftime("%Y-%m-%d"),
            "project": proj_nome,
            "assignee": dip["nome"],
            "status": t["stato"],
            "estimated_hours": int(t["ore_stimate"]),
        })

    # Titolo
    if progetto_id:
        proj = _PROGETTI()[_PROGETTI()["id"] == progetto_id]
        titolo = f"GANTT — {proj.iloc[0]['nome']}" if len(proj) > 0 else "GANTT"
    else:
        titolo = "GANTT IMC-Group — Tutti i progetti"

    pdf_bytes = genera_gantt_pdf(gantt_data, titolo=titolo, progetto_filtro=progetto_id)

    filename = f"gantt_{progetto_id or 'tutti'}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ══════════════════════════════════════════════════════════════════════
# AVVIO
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)