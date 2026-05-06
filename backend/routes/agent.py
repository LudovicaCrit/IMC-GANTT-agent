"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/agent.py — Router per endpoint /api/agent (IA Gemini)
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone i 6 endpoint REST che mediano il dialogo tra il frontend e
Gemini 2.5 Flash. Concentra tutta l'interfaccia HTTP-IA in un unico
file: chiunque cerchi "endpoint che chiamano l'IA" trova qui tutto.

La logica Gemini (init, prompt loader, chiamata bloccante, helper
`costruisci_contesto`) vive in `backend/agent.py` (modulo di servizio,
non da confondere con questo router).

Frontend
   ↓ HTTP
routes/agent.py    ← endpoint REST con auth, validazione, parsing
   ↓ chiama
agent.py           ← wrapper Gemini con logica di chiamata
   ↓ HTTPS
Gemini API

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                     │ Metodo   │ Auth                │
├──────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/agent/status                        │ GET      │ AUTH-ONLY           │
│ /api/agent/chat                          │ POST     │ Pattern Y           │
│ /api/agent/analisi-gantt                 │ POST     │ require_manager     │
│ /api/agent/suggerisci-task               │ POST     │ require_manager     │
│ /api/agent/verifica-pianificazione       │ POST     │ require_manager     │
│ /api/agent/interpreta-scenario           │ POST     │ require_manager     │
└──────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/agent/status
   - AUTH-ONLY: sapere se l'IA è accessibile è ok per chiunque sia loggato.
   - Restituisce {"available": bool}. Veloce, niente chiamata a Gemini.

2. POST /api/agent/chat
   - Pattern Y (anti-impersonation): se user → forza dipendente_id al proprio.
     Manager può chattare per qualunque dipendente (utile per assistenza).
   - È il chatbot della Consuntivazione. Riceve messaggio + stato form parziale
     (ore_compilate, stati, assenze, spese) e chiede a Gemini di:
     • aiutare il dipendente a esprimere ore/mappature
     • emettere blocchi strutturati [MAPPATURA_ORE] e [SEGNALAZIONE]
       che il backend parsa e processa
   - Risposta: {risposta (testo pulito), segnalazione, mappatura_ore, contesto_carico}.
   - Le segnalazioni emesse dall'IA vengono persistite (db o memoria).

3. POST /api/agent/analisi-gantt
   - Manager-only.
   - Riceve una segnalazione (es. "Helena ha sforato 200 ore su DORA") e
     chiede a Gemini di proporre redistribuzioni del carico.
   - Costruisce contesto con TUTTI i dipendenti + TUTTI i progetti attivi.
   - Usa il prompt specializzato `prompts/analisi_segnalazioni.md`.
   - Restituisce: proposte (JSON) + contesto (segnalazione + saturazione).

4. POST /api/agent/suggerisci-task
   - Manager-only.
   - Per Pipeline: dato un nuovo progetto (nome+cliente+budget+date), chiede
     a Gemini una struttura task suggerita.
   - Usa il prompt `prompts/suggerisci_task.md`.

5. POST /api/agent/verifica-pianificazione
   - Manager-only.
   - Per Pipeline: dato un GANTT pianificato, chiede a Gemini di verificarlo
     (task orfani, fasi mancanti, stime irrealistiche, sovraccarichi).
   - Usa il prompt `prompts/verifica_pianificazione.md`.

6. POST /api/agent/interpreta-scenario
   - Manager-only.
   - Per Tavolo di Lavoro: il manager scrive in linguaggio naturale ciò
     che vuole simulare ("se Helena va su DORA al 60% per 3 settimane...")
     e Gemini traduce in modifiche strutturate per /api/scenario/simula.
   - Usa il contesto IA completo (tutti i dipendenti + progetti attivi)
     per ragionare bene.
   - NON esegue la simulazione — restituisce le modifiche proposte che il
     frontend mostrerà al management per conferma/modifica.
   - Usa il prompt `prompts/interpreta_scenario.md`.
   - Spostato qui da /api/scenario/interpreta il 6 maggio 2026 (vedi
     STORIA in fondo).

PATTERN AUTH USATI
──────────────────
- AUTH-ONLY (status): chiunque sia loggato.
- Pattern Y (chat): user può chattare solo per sé stesso. Manager può
  chattare per chiunque.
- require_manager (gli altri 4): le funzioni di pianificazione/analisi
  sono manageriali per scelta.

NOTE TECNICHE
─────────────
Tutti gli endpoint che chiamano Gemini fanno il classico parsing JSON
con fallback graceful: se Gemini risponde con testo non parsabile, il
payload include `{"raw_response": ..., "parse_error": True}` invece di
crashare. Pattern molto buono, da mantenere.

Helper locali `_DIPENDENTI`, `_PROGETTI`, `_TASKS`, `get_oggi`,
`get_contesto_ia`. Tutti TODO da estrarre in moduli condivisi.

`get_contesto_ia()` è la funzione (con cache TTL 60s) che produce il
contesto JSON completo del sistema (dipendenti+progetti attivi), usata
da interpreta-scenario per ragionare bene. È replicata localmente qui
e in routes/scenario.py — verrà estratta nel modulo `backend/contesto.py`
nel commit di pulizia finale del refactoring.

📌 TODO Pulizia DTO orfani: rimuovere da main.py le classi
ChatRequest, AnalisiRequest, SuggerisciTaskRequest,
VerificaPianificazioneRequest, InterpretaRequest nel commit dedicato
post-refactoring.

📌 TODO Lentezza endpoint /agent/* (vedi handoff v13 sezione F.3):
   - Dimensione contesto inviato (analisi-gantt manda TUTTI i dipendenti +
     TUTTI i progetti attivi → JSON grosso)
   - Modello Gemini 2.5 Flash dovrebbe essere veloce ma valutare
   - Network/latency di Gemini API
   - Streaming response invece di blocking?
   - Cache contesto: oggi TTL 60s, valutare aumento e invalidazione su _reload()

DIPENDENZE
──────────
- `agent` (modulo locale): `init_gemini`, `costruisci_contesto`,
  `chiedi_agente`, `is_agent_available`. NON da confondere con questo router.
- `data` (modulo): `get_dipendente`, `carico_settimanale_dipendente`,
  `get_progetti_dipendente`, e DataFrame DIPENDENTI/PROGETTI/TASKS.
  Persistenza segnalazioni: `aggiungi_segnalazione` se PERSISTENT_MODE.
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente`.

STORIA
──────
Estratto da main.py il 6 maggio 2026 nell'ambito del refactoring strangler.
Inizialmente 5 endpoint; il 6 maggio (sera) è stato aggiunto
`interpreta-scenario` che era originariamente `/api/scenario/interpreta`.
Decisione architetturale: tutti gli endpoint che chiamano Gemini
appartengono semanticamente a "agent", indipendentemente dal contesto
di business (Consuntivazione, Pipeline, Tavolo di Lavoro). Il prefisso
URL esplicita questa coerenza. Frontend api.js aggiornato in coerenza.
═══════════════════════════════════════════════════════════════════════════
"""

import json as json_mod
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user, require_manager
from models import Utente
import data as data_module
from data import (
    get_dipendente, carico_settimanale_dipendente, get_progetti_dipendente,
)
from agent import (
    init_gemini, costruisci_contesto, chiedi_agente, is_agent_available,
)

# Persistenza opzionale per segnalazioni (chat)
try:
    from data import aggiungi_segnalazione
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False


# ── Helper locali (TODO: estrarre in moduli condivisi) ───────────────────
def _DIPENDENTI(): return data_module.DIPENDENTI
def _PROGETTI(): return data_module.PROGETTI
def _TASKS(): return data_module.TASKS

def get_oggi():
    return datetime.now()


# ── Cache contesto IA (TODO: estrarre in backend/contesto.py) ────────────
_contesto_cache = {
    "data": None,
    "timestamp": None,
}

def get_contesto_ia():
    """Restituisce il contesto per l'IA, ricalcolandolo solo se i dati sono cambiati."""
    # Invalida cache ogni 60 secondi
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


# ── DTO ──────────────────────────────────────────────────────────────────
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


class AnalisiRequest(BaseModel):
    segnalazione_tipo: str
    segnalazione_dettaglio: str
    dipendente_id: str
    priorita: str = "media"


class SuggerisciTaskRequest(BaseModel):
    progetto_nome: str = ""
    progetto_cliente: str = ""
    descrizione: str = ""
    budget_ore: int = 0
    data_inizio: str = ""
    data_fine: str = ""


class VerificaPianificazioneRequest(BaseModel):
    progetto_nome: str = ""
    progetto_cliente: str = ""
    budget_ore: int = 0
    data_inizio: str = ""
    data_fine: str = ""
    task_pianificati: list[dict] = []


class InterpretaRequest(BaseModel):
    """Richiesta di interpretazione linguaggio naturale → modifiche scenario."""
    testo: str
    contesto_extra: str = ""


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/agent", tags=["agent"])


# ═════════════════════════════════════════════════════════════════════════
# 1. GET /api/agent/status — Health check Gemini
# ═════════════════════════════════════════════════════════════════════════

@router.get("/status")
def agent_status(_: Utente = Depends(get_current_user)):
    """Restituisce se l'agente Gemini è accessibile."""
    return {"available": is_agent_available()}


# ═════════════════════════════════════════════════════════════════════════
# 2. POST /api/agent/chat — Chatbot Consuntivazione
# ═════════════════════════════════════════════════════════════════════════

@router.post("/chat")
def agent_chat(
    req: ChatRequest,
    current_user: Utente = Depends(get_current_user),
):
    """Chatbot della Consuntivazione (Pattern Y self-or-manager).

    Riceve messaggio + stato form parziale, chiama Gemini, parsa eventuali
    blocchi strutturati [MAPPATURA_ORE] e [SEGNALAZIONE].
    """
    # User può chattare solo per sé stesso (anti-impersonation)
    if current_user.ruolo_app != "manager":
        req.dipendente_id = current_user.dipendente_id
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
            risposta_pulita_con_segn = risposta_pulita + "\n" + segn_part
        else:
            risposta_pulita_con_segn = None

        # Estrai il JSON dalla mappatura
        mappatura_raw = mappatura_raw.strip()
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
            mappatura_ore = None

        if risposta_pulita_con_segn:
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
            # Fallback memoria: usa store di main.py
            from main import SEGNALAZIONI_STORE, _next_segn_id
            SEGNALAZIONI_STORE.append({
                "id": _next_segn_id(),
                "tipo": segn_tipo,
                "priorita": segn_priorita,
                "dipendente_id": req.dipendente_id,
                "dipendente": dip["nome"],
                "dettaglio": segn_dettaglio,
                "timestamp": get_oggi().strftime("%Y-%m-%d %H:%M"),
            })

    return {
        "risposta": risposta_pulita,
        "segnalazione": segnalazione,
        "mappatura_ore": mappatura_ore,
        "contesto_carico": contesto.get("carico_complessivo"),
    }


# ═════════════════════════════════════════════════════════════════════════
# 3. POST /api/agent/analisi-gantt — Proposte redistribuzione carico
# ═════════════════════════════════════════════════════════════════════════

@router.post("/analisi-gantt")
def analisi_gantt(
    req: AnalisiRequest,
    _: Utente = Depends(require_manager),
):
    """Riceve una segnalazione e restituisce proposte di redistribuzione (manager-only)."""
    try:
        dip_segnalante = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(400, f"Dipendente '{req.dipendente_id}' non trovato")

    # Tutti i dipendenti con carico
    dip_contesto = []
    for _, d in _DIPENDENTI().iterrows():
        carico = carico_settimanale_dipendente(d["id"], get_oggi())
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
        "data_corrente": get_oggi().strftime("%Y-%m-%d"),
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

        # Tenta di parsare il JSON dalla risposta (rimuovi backtick markdown)
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


# ═════════════════════════════════════════════════════════════════════════
# 4. POST /api/agent/suggerisci-task — IA per Pipeline (suggerisci struttura task)
# ═════════════════════════════════════════════════════════════════════════

@router.post("/suggerisci-task")
def suggerisci_task(
    req: SuggerisciTaskRequest,
    _: Utente = Depends(require_manager),
):
    """Chiede all'agente di suggerire task per un nuovo progetto (manager-only)."""
    contesto = {
        "progetto": req.progetto_nome,
        "cliente": req.progetto_cliente,
        "descrizione": req.descrizione,
        "budget_ore": req.budget_ore,
        "periodo": f"{req.data_inizio} — {req.data_fine}" if req.data_inizio else "Non specificato",
    }

    model = init_gemini(prompt_file="suggerisci_task.md")
    if model is None:
        raise HTTPException(503, "Agente AI non disponibile")

    contesto_json = json_mod.dumps(contesto, ensure_ascii=False, indent=2)
    prompt = f"Suggerisci i task per questo progetto:\n\n```json\n{contesto_json}\n```"

    try:
        chat = model.start_chat(history=[])
        response = chat.send_message(prompt)
        risposta_raw = response.text

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
            risultato = {"raw_response": risposta_raw, "parse_error": True}

        return risultato

    except Exception as e:
        raise HTTPException(500, f"Errore agente: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════
# 5. POST /api/agent/verifica-pianificazione — IA per validare GANTT pianificato
# ═════════════════════════════════════════════════════════════════════════

@router.post("/verifica-pianificazione")
def verifica_pianificazione(
    req: VerificaPianificazioneRequest,
    _: Utente = Depends(require_manager),
):
    """Chiede all'agente di verificare la pianificazione GANTT (manager-only).

    Valuta task orfani, fasi mancanti, stime irrealistiche, sovraccarichi.
    """
    contesto = {
        "progetto": {
            "nome": req.progetto_nome,
            "cliente": req.progetto_cliente,
            "budget_ore": req.budget_ore,
            "data_inizio": req.data_inizio,
            "data_fine": req.data_fine,
        },
        "task_pianificati": req.task_pianificati,
        "dipendenti_coinvolti": [],
    }

    # Aggiungi info saturazione per i dipendenti coinvolti
    nomi_coinvolti = set()
    for t in req.task_pianificati:
        if t.get("assegnato"):
            nomi_coinvolti.add(t["assegnato"])

    for nome in nomi_coinvolti:
        dip_match = _DIPENDENTI()[_DIPENDENTI()["nome"] == nome]
        if len(dip_match) > 0:
            d = dip_match.iloc[0]
            carico = carico_settimanale_dipendente(d["id"], get_oggi())
            contesto["dipendenti_coinvolti"].append({
                "nome": nome,
                "profilo": d["profilo"],
                "saturazione_attuale": round(carico / d["ore_sett"] * 100),
            })

    # Chiama Gemini
    model = init_gemini(prompt_file="verifica_pianificazione.md")
    if model is None:
        raise HTTPException(503, "Agente AI non disponibile")

    contesto_json = json_mod.dumps(contesto, ensure_ascii=False, indent=2)
    prompt = f"Verifica questa pianificazione GANTT:\n\n```json\n{contesto_json}\n```"

    try:
        chat = model.start_chat(history=[])
        response = chat.send_message(prompt)
        risposta_raw = response.text

        # Parsa JSON
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
            risultato = {"raw_response": risposta_raw, "parse_error": True}

        return risultato

    except Exception as e:
        raise HTTPException(500, f"Errore agente: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════
# 6. POST /api/agent/interpreta-scenario — IA per Tavolo di Lavoro
# ═════════════════════════════════════════════════════════════════════════

@router.post("/interpreta-scenario")
def interpreta_scenario(req: InterpretaRequest, _: Utente = Depends(require_manager)):
    """Traduce linguaggio naturale del management in modifiche strutturate.

    Il manager scrive in linguaggio naturale ciò che vuole simulare
    ("se Helena va su DORA al 60% per 3 settimane..."). Gemini traduce
    in modifiche strutturate per il successivo /api/scenario/simula.

    NON esegue la simulazione — restituisce le modifiche proposte che il
    frontend mostrerà al management per conferma/modifica.
    """
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
