"""
═══════════════════════════════════════════════════════════════════════════
backend/contesto.py — Costruzione contesto per IA Gemini con cache TTL
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Costruisce il contesto JSON che viene passato a Gemini quando deve
"ragionare" sull'azienda intera (interpretazione scenari, analisi GANTT,
verifica pianificazione). Implementa una cache in-memory con TTL 60s
per evitare di ricostruire il dump ad ogni richiesta.

QUANDO USATA
────────────
- `routes/agent.py` → endpoint `interpreta-scenario` (Tavolo di Lavoro):
  l'IA traduce linguaggio naturale del management in modifiche scenario,
  e per farlo bene serve sapere quali progetti sono attivi e chi ha
  carico libero.

- (potenziali estensioni R2) Altri endpoint che vogliano "il quadro
  generale aziendale" come prompt context.

NB: NON usata da `agent/chat`, `agent/analisi-gantt`, `agent/suggerisci-task`,
`agent/verifica-pianificazione` perché ognuno costruisce contesto custom
specifico per il proprio task (chat usa contesto del singolo dipendente,
analisi-gantt costruisce contesto specifico per la segnalazione, ecc.).

CONTENUTO PAYLOAD
─────────────────
{
  "data_corrente": "2026-05-06",
  "progetti": [
    {
      "id": "P001", "nome": "Adeguamento DORA", "cliente": "Sparkasse",
      "stato": "In esecuzione", "scadenza": "2026-06-30",
      "task": [
        {"id": "T001", "nome": "Gap analysis DORA",
         "assegnato_a": "Helena Ullah",
         "inizio": "2025-09-01", "fine": "2025-11-15",
         "ore_stimate": 160, "stato": "Completato"},
        ...
      ]
    },
    ...
  ],
  "dipendenti": [
    {"id": "D001", "nome": "Vincenzo Carolla", "profilo": "AD",
     "ore_sett": 40, "saturazione_pct": 93},
    ...
  ]
}

Sono inclusi SOLO progetti con stato "In esecuzione" o "In bando" — no
progetti completati (irrilevanti per scenari futuri).

CACHE TTL 60s
─────────────
Per evitare di ricostruire il dump JSON a ogni richiesta IA. Limiti
attuali noti:
  📌 TODO 1 — La cache NON viene invalidata in `_reload()` dopo le
     scritture. Conseguenza: per max 60s, l'IA può vedere dati vecchi.
     Fix: aggiungere `invalida_cache_contesto()` chiamato in `_reload()`.

  📌 TODO 2 — TTL 60s è basso. La prima richiesta ogni minuto paga
     il rebuild. Considerare:
     - alzare TTL a 5 minuti (con invalidazione esplicita su scrittura)
     - oppure pre-warming del cache al boot dell'app

  📌 TODO 3 — Performance: il dump è grosso (tutti dipendenti + tutti
     progetti attivi + tutti task). Per progetti "non rilevanti per la
     query corrente" potremmo ridurre. Ma richiede capire ANTE quali
     siano "rilevanti" — più complesso. Per ora dump completo.

DIPENDENZE
──────────
- `data` — `carico_settimanale_dipendente`.
- `models` — `Dipendente`, `Progetto`, `Task`, `get_session`
  (lettura SQLAlchemy diretta nel modulo: strategia B, il contesto è
  globale e non dipende dalla richiesta del chiamante).
- `utils` — `get_oggi`.

STORIA
──────
Estratto da main.py il 6 maggio 2026 — era replicato anche in
`routes/agent.py` durante il refactoring (necessario per evitare
dipendenze circolari su main). Ora che esiste come modulo separato,
i router possono importarlo correttamente.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from data import carico_settimanale_dipendente
from models import Dipendente, Progetto, Task, get_session
from utils import get_oggi


# ── Cache in-memory con TTL ──────────────────────────────────────────────
_contesto_cache = {
    "data": None,
    "timestamp": None,
}


def get_contesto_ia():
    """Restituisce il contesto JSON per l'IA, ricalcolandolo solo se TTL scaduto.

    TTL: 60 secondi. Vedi note nell'header del modulo per limitazioni
    attuali (mancanza invalidazione su scrittura, TTL basso).
    """
    # Cache hit?
    now = datetime.now()
    if (_contesto_cache["data"] is not None
        and _contesto_cache["timestamp"]
        and (now - _contesto_cache["timestamp"]).seconds < 60):
        return _contesto_cache["data"]

    # ── Cache miss: ricostruisci ──
    # Strategia B: il modulo apre lui la session e fa le 3 query.
    # Filtri iso-comportamento col vecchio loader DataFrame:
    #  - progetti: stato in ("In esecuzione","In bando")
    #  - task: nessun filtro (vecchio _load_tasks non filtrava)
    #  - dipendenti: attivo=True (come _load_dipendenti)
    session = get_session()
    try:
        progetti_rows = (
            session.query(Progetto)
            .filter(Progetto.stato.in_(["In esecuzione", "In bando"]))
            .all()
        )
        tasks_rows = session.query(Task).all()
        dipendenti_rows = (
            session.query(Dipendente)
            .filter(Dipendente.attivo == True)
            .all()
        )
    finally:
        session.close()

    # Indici precostruiti: sostituiscono la bool-index ripetuta su PROGETTI
    # e il N+1 di get_dipendente() del vecchio codice.
    # Nota iso-comportamento: l'originale chiamava get_dipendente() che a
    # sua volta filtra attivo=True e per id non trovato ritorna
    # "Sconosciuto ({did})" — qui replichiamo lo stesso fallback.
    dipendenti_nomi = {d.id: d.nome for d in dipendenti_rows}
    tasks_per_progetto = {}
    for t in tasks_rows:
        tasks_per_progetto.setdefault(t.progetto_id, []).append(t)

    progetti_ctx = []
    for p in progetti_rows:
        tasks_list = []
        for t in tasks_per_progetto.get(p.id, []):
            if not t.dipendente_id:
                dip_nome = "Non assegnato"
            else:
                dip_nome = dipendenti_nomi.get(
                    t.dipendente_id, f"Sconosciuto ({t.dipendente_id})"
                )
            tasks_list.append({
                "id": t.id, "nome": t.nome,
                "assegnato_a": dip_nome,
                "inizio": t.data_inizio.strftime("%Y-%m-%d") if t.data_inizio else "",
                "fine": t.data_fine.strftime("%Y-%m-%d") if t.data_fine else "",
                # bugfix: ore_stimate da ORM può essere None (era 0 in _load_tasks).
                "ore_stimate": int(t.ore_stimate or 0),
                "stato": t.stato,
            })
        progetti_ctx.append({
            "id": p.id, "nome": p.nome,
            "cliente": p.cliente, "stato": p.stato,
            "scadenza": p.data_fine.strftime("%Y-%m-%d") if p.data_fine else "",
            "task": tasks_list,
        })

    dipendenti_ctx = []
    for d in dipendenti_rows:
        carico = carico_settimanale_dipendente(d.id, get_oggi())
        dipendenti_ctx.append({
            "id": d.id, "nome": d.nome,
            "profilo": d.profilo,
            "ore_sett": int(d.ore_sett),
            "saturazione_pct": round(carico / d.ore_sett * 100),
        })

    contesto = {
        "data_corrente": get_oggi().strftime("%Y-%m-%d"),
        "progetti": progetti_ctx,
        "dipendenti": dipendenti_ctx,
    }

    # Aggiorna cache
    _contesto_cache["data"] = contesto
    _contesto_cache["timestamp"] = now

    return contesto


def invalida_cache_contesto():
    """Forza ricostruzione del contesto al prossimo get_contesto_ia().

    📌 TODO: chiamare questa funzione in `data._reload()` dopo le scritture
    per garantire che l'IA non veda mai dati vecchi.
    """
    _contesto_cache["data"] = None
    _contesto_cache["timestamp"] = None
