"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/risorse.py — Router per endpoint /api/risorse
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint relativi alla gestione delle risorse umane dal punto
di vista del carico di lavoro: heatmap di saturazione (carico) e
suggerimenti di redistribuzione task (bilanciamento). Alimenta la pagina
Risorse del frontend (vista manager).

ENDPOINT ESPOSTI
────────────────
┌───────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                      │ Metodo   │ Auth                │
├───────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/risorse/carico                       │ GET      │ require_manager     │
│ /api/risorse/suggerisci-bilanciamento     │ GET      │ require_manager     │
└───────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/risorse/carico?settimane=N
   - Manager-only.
   - Parametro `settimane` (default 12): orizzonte temporale della heatmap.
   - Per ogni dipendente, ritorna le ore_assegnate e saturazione_pct
     settimana per settimana, per le prossime N settimane.
   - Saturazione cappata a 125% per evitare scale visive distorte.

2. GET /api/risorse/suggerisci-bilanciamento
   - Manager-only.
   - Analizza saturazioni correnti e propone redistribuzioni.
   - Logica:
     • Identifica sovraccarichi (saturazione > 100%) e sottoutilizzati
       (saturazione < 90%)
     • Per ogni task del sovraccarico, cerca candidati con profilo o
       competenza compatibile e spazio disponibile (almeno 50% delle ore_sett)
     • Ordina i candidati preferendo chi resterebbe vicino al 100% post-spostamento
   - Output: lista proposte ordinate per priorità (alta se saturazione > 125%).

PATTERN AUTH USATI
──────────────────
- `require_manager`: dato strategico aziendale.

NOTE DI DOMINIO
───────────────
La logica di suggerimento bilanciamento è il punto di partenza per la
"logica di redistribuzione compiti" che Ludovica ha sottolineato come
funzionalità prodotto importante. La versione attuale è basica
(profilo + competenza esatta + spazio disponibile); evoluzioni possibili:
- Considerare la durata residua del task vs disponibilità futura
- Considerare le preferenze/storico dei dipendenti
- Considerare i progetti su cui sono già impegnati (ridurre context-switch)

Sono evoluzioni R2.

DIPENDENZE
──────────
- `data` (modulo): `carico_settimanale_dipendente`, e DataFrame
  DIPENDENTI/PROGETTI/TASKS.
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper locali `_DIPENDENTI`, `_PROGETTI`, `_TASKS`, `get_oggi`.
📌 TODO: estrarre in moduli condivisi quando ≥3 router li replicano.

P010 (Attività Interne) escluso dal calcolo task attivi del bilanciamento:
non ha senso "redistribuire" la formazione interna.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends

from deps import require_manager
from models import Utente
import data as data_module
from data import carico_settimanale_dipendente


# ── Helper locali (TODO: estrarre in moduli condivisi) ───────────────────
def _DIPENDENTI(): return data_module.DIPENDENTI
def _PROGETTI(): return data_module.PROGETTI
def _TASKS(): return data_module.TASKS

def get_oggi():
    return datetime.now()


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/risorse", tags=["risorse"])


@router.get("/carico")
def carico_risorse(
    settimane: int = 12,
    _: Utente = Depends(require_manager),
):
    """Heatmap saturazione per tutte le risorse, prossime N settimane (default 12)."""
    result = []
    for _, d in _DIPENDENTI().iterrows():
        settimane_data = []
        for w in range(settimane):
            sett = get_oggi() + timedelta(weeks=w)
            lun = sett - timedelta(days=sett.weekday())
            carico = carico_settimanale_dipendente(d["id"], sett)
            settimane_data.append({
                "settimana": lun.strftime("%Y-%m-%d"),
                "settimana_label": lun.strftime("%d/%m"),
                "ore_assegnate": float(carico),
                "saturazione_pct": min(125, round(carico / d["ore_sett"] * 100)),
            })
        result.append({
            "dipendente_id": d["id"],
            "nome": d["nome"],
            "profilo": d["profilo"],
            "ore_sett": int(d["ore_sett"]),
            "settimane": settimane_data,
        })
    return result


@router.get("/suggerisci-bilanciamento")
def suggerisci_bilanciamento(_: Utente = Depends(require_manager)):
    """Analizza le saturazioni e propone redistribuzioni per bilanciare il carico."""
    oggi = datetime.now()

    # Calcola saturazione per tutti
    persone = []
    for _, d in _DIPENDENTI().iterrows():
        carico = carico_settimanale_dipendente(d["id"], oggi)
        sat = round(carico / d["ore_sett"] * 100)

        # Trova i task attivi di questa persona (escludendo Attività Interne)
        tasks_attivi = _TASKS()[
            (_TASKS()["dipendente_id"] == d["id"]) &
            (_TASKS()["stato"].isin(["In corso", "Da iniziare"])) &
            (_TASKS()["progetto_id"] != "P010")
        ]

        task_list = []
        for _, t in tasks_attivi.iterrows():
            # Calcola ore settimanali per questo task
            durata_giorni = max(1, (t["data_fine"] - t["data_inizio"]).days)
            durata_sett = max(1, durata_giorni / 7)
            ore_sett_task = round(t["ore_stimate"] / durata_sett, 1)

            proj = _PROGETTI()[_PROGETTI()["id"] == t["progetto_id"]]
            proj_nome = proj.iloc[0]["nome"] if len(proj) > 0 else "?"

            task_list.append({
                "task_id": t["id"],
                "task_nome": t["nome"],
                "progetto_id": t["progetto_id"],
                "progetto_nome": proj_nome,
                "profilo_richiesto": t["profilo_richiesto"],
                "ore_stimate": int(t["ore_stimate"]),
                "ore_sett": ore_sett_task,
                "stato": t["stato"],
            })

        persone.append({
            "id": d["id"],
            "nome": d["nome"],
            "profilo": d["profilo"],
            "competenze": d["competenze"] if isinstance(d["competenze"], list) else [],
            "ore_sett": int(d["ore_sett"]),
            "carico": float(carico),
            "saturazione": sat,
            "task_attivi": task_list,
        })

    # Trova sovraccarichi e sottoutilizzati
    sovraccarichi = [p for p in persone if p["saturazione"] > 100]
    sottoutilizzati = [p for p in persone if p["saturazione"] < 90]

    # Genera proposte
    proposte = []

    for sov in sorted(sovraccarichi, key=lambda x: -x["saturazione"]):
        for task in sorted(sov["task_attivi"], key=lambda t: t["ore_sett"]):
            profilo = task["profilo_richiesto"]

            candidati = []
            for sotto in sottoutilizzati:
                if sotto["id"] == sov["id"]:
                    continue
                # Match profilo o competenza
                if sotto["profilo"] == profilo or profilo in sotto["competenze"]:
                    spazio_disponibile = sotto["ore_sett"] - sotto["carico"]
                    if spazio_disponibile >= task["ore_sett"] * 0.5:  # almeno metà ore
                        nuova_sat_sotto = round(
                            (sotto["carico"] + task["ore_sett"]) / sotto["ore_sett"] * 100
                        )

                        candidati.append({
                            "candidato_id": sotto["id"],
                            "candidato_nome": sotto["nome"],
                            "candidato_profilo": sotto["profilo"],
                            "candidato_saturazione_attuale": sotto["saturazione"],
                            "candidato_saturazione_dopo": nuova_sat_sotto,
                            "spazio_disponibile_h": round(spazio_disponibile, 1),
                        })

            if candidati:
                # Preferisci chi arriva più vicino al 100% post-spostamento
                candidati.sort(key=lambda c: abs(c["candidato_saturazione_dopo"] - 100))
                migliore = candidati[0]

                proposte.append({
                    "tipo": "riassegnazione",
                    "priorita": "alta" if sov["saturazione"] > 125 else "media",
                    "da_persona": sov["nome"],
                    "da_persona_id": sov["id"],
                    "da_saturazione": sov["saturazione"],
                    "da_saturazione_dopo": round(
                        (sov["carico"] - task["ore_sett"]) / sov["ore_sett"] * 100
                    ),
                    "task_id": task["task_id"],
                    "task_nome": task["task_nome"],
                    "progetto": task["progetto_nome"],
                    "ore_sett_task": task["ore_sett"],
                    "profilo_richiesto": profilo,
                    "candidato_migliore": migliore,
                    "altri_candidati": candidati[1:3],  # max 2 alternative
                })

    # Ordina: alta priorità prima, poi per eccesso saturazione
    proposte.sort(key=lambda p: (0 if p["priorita"] == "alta" else 1, -p["da_saturazione"]))

    return {
        "n_sovraccarichi": len(sovraccarichi),
        "n_sottoutilizzati": len(sottoutilizzati),
        "proposte": proposte,
        "riepilogo": [
            {"nome": p["nome"], "profilo": p["profilo"], "saturazione": p["saturazione"]}
            for p in sorted(persone, key=lambda x: -x["saturazione"])
            if p["saturazione"] > 0
        ],
    }
