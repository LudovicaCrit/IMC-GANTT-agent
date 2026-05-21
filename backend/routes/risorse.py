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
- `data` (modulo): `carico_settimanale_dipendente` (trappola §4 della
  migrazione DataFrame→Postgres, lasciata intatta).
- `models`: `Dipendente`, `Task`, `Progetto`, `get_session` (lettura
  diretta Postgres).
- `data_db_impl._to_dt`: normalizza `Date` SQL → `datetime` a mezzanotte
  per i confronti con `lun_w_dt + timedelta(...)` (storicamente i task
  erano `pandas.Timestamp` a 00:00).
- `deps`: `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
P010 (Attività Interne) escluso dal calcolo task attivi del bilanciamento:
non ha senso "redistribuire" la formazione interna.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
Letture migrate da DataFrame in cache a Postgres diretto il 21 maggio 2026
(handoff migrazione §6-ter), preservando iso-comportamento.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import joinedload

from deps import require_manager
from models import Utente, Dipendente, Task, get_session
from data import carico_settimanale_dipendente
from data_db_impl import _to_dt
from utils import get_oggi


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/risorse", tags=["risorse"])

@router.get("/carico")
def carico_risorse(
    settimane: int = 12,
    _: Utente = Depends(require_manager),
):
    """Heatmap saturazione per tutte le risorse, prossime N settimane (default 12).

    Ritorna saturazione GREZZA, non cappata: i numeri devono dire la verità
    sempre, le soglie di display (verde/giallo/arancione/rosso, badge "oltre
    soft cap 125%", hard ceiling 150% in palette) sono responsabilità del
    frontend. Coerente con /saturazione-periodo.

    Note sul calcolo (vedi anche carico_settimanale_dipendente):
    - I task hanno date a 00:00 (pandas.Timestamp), quindi normalizziamo
      "oggi" a mezzanotte prima del confronto, altrimenti perdiamo i task
      che finiscono nel giorno corrente (bug confine settimana).
    - Il calcolo distribuisce ore_stimate uniformemente sulle settimane
      della durata del task. È una semplificazione provvisoria: a Step
      2.7-pre il PM potrà dichiarare una distribuzione settimanale esplicita
      delle ore (handoff v17 §2.7-pre).
    """
    result = []
    oggi_raw = get_oggi()
    # Normalizza a mezzanotte per allineare il confronto a pandas.Timestamp
    # dei task (sempre a 00:00). Vedi handoff v16 §15 Passo 2 e routes/risorse.py
    # saturazione-periodo riga 191 dove lo stesso fix è già applicato.
    oggi = datetime.combine(
        oggi_raw.date() if hasattr(oggi_raw, 'date') else oggi_raw,
        datetime.min.time()
    )
    session = get_session()
    dipendenti = session.query(Dipendente).filter(Dipendente.attivo == True).all()
    session.close()
    for d in dipendenti:
        settimane_data = []
        for w in range(settimane):
            sett = oggi + timedelta(weeks=w)
            lun = sett - timedelta(days=sett.weekday())
            carico = carico_settimanale_dipendente(d.id, sett)
            settimane_data.append({
                "settimana": lun.strftime("%Y-%m-%d"),
                "settimana_label": lun.strftime("%d/%m"),
                "ore_assegnate": float(carico),
                "saturazione_pct": round(carico / d.ore_sett * 100),
            })
        result.append({
            "dipendente_id": d.id,
            "nome": d.nome,
            "profilo": d.profilo,
            "ore_sett": int(d.ore_sett),
            "settimane": settimane_data,
        })
    return result


@router.get("/saturazione-periodo")
def saturazione_periodo(
    dipendente_id: str,
    data_inizio: str,
    data_fine: str,
    escludi_task_id: str = None,
    _: Utente = Depends(require_manager),
):
    """Saturazione di un dipendente in un periodo specifico (Step 2.4-bis §14.4).

    Usato dal modale Task di /cantiere/{id}: quando il PM seleziona un dipendente
    o cambia date del task, mostra la saturazione media/max/min nelle settimane
    coperte dal task, così il PM vede subito se la persona è sovraccarica.

    Params:
        dipendente_id: id dipendente da analizzare
        data_inizio, data_fine: periodo del task (ISO date)
        escludi_task_id: id task corrente da escludere dal calcolo (utile in
            modifica: vogliamo vedere la saturazione SENZA contare il task che
            stiamo modificando, altrimenti avremmo il doppio conteggio).

    Returns:
        {
            "dipendente_id": str,
            "nome": str,
            "ore_sett": int,
            "settimane_coperte": int,
            "saturazione_media_pct": int,    # media nelle settimane del task
            "saturazione_max_pct": int,      # picco
            "saturazione_min_pct": int,      # minimo (utile per capire margine)
            "ore_assegnate_totali": float,   # somma carichi nelle settimane
            "settimane_dettaglio": [          # per debug/visualizzazione
                {"settimana": "2026-05-18", "saturazione_pct": 95, "ore": 38},
                ...
            ]
        }
    """
    try:
        di = datetime.fromisoformat(data_inizio).date()
        df = datetime.fromisoformat(data_fine).date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato date non valido (atteso ISO yyyy-mm-dd).")

    if df < di:
        raise HTTPException(status_code=422, detail="data_fine precede data_inizio.")

    session = get_session()
    d = session.query(Dipendente).filter(
        Dipendente.id == dipendente_id,
        Dipendente.attivo == True,
    ).first()
    if d is None:
        session.close()
        raise HTTPException(status_code=404, detail=f"Dipendente '{dipendente_id}' non trovato.")
    ore_sett_dip = int(d.ore_sett)
    nome_dip = d.nome

    # Lookup del task da escludere (al massimo uno: filtro per id + dipendente
    # + stato non terminale). Una sola query fuori dal loop sulle settimane.
    task_da_escludere = None
    if escludi_task_id:
        task_da_escludere = session.query(Task).filter(
            Task.dipendente_id == dipendente_id,
            Task.id == escludi_task_id,
            ~Task.stato.in_(["Completato", "Sospeso", "Eliminato"]),
        ).first()
    session.close()

    # Calcolo settimane coperte: dalla settimana del data_inizio alla settimana del data_fine
    lun_start = di - timedelta(days=di.weekday())  # lunedì della settimana di data_inizio
    lun_end = df - timedelta(days=df.weekday())    # lunedì della settimana di data_fine
    n_sett = ((lun_end - lun_start).days // 7) + 1

    settimane_dettaglio = []
    saturazioni = []
    ore_totali = 0.0

    for w in range(n_sett):
        lun_w = lun_start + timedelta(weeks=w)
        # carico_settimanale_dipendente confronta con pandas Timestamp,
        # serve datetime non date pura
        lun_w_dt = datetime.combine(lun_w, datetime.min.time())
        carico_w = carico_settimanale_dipendente(dipendente_id, lun_w_dt)

        # Escludi il task corrente (se in modifica) dal calcolo
        if task_da_escludere is not None:
            t_inizio = _to_dt(task_da_escludere.data_inizio)
            t_fine = _to_dt(task_da_escludere.data_fine)
            # Calcola se questo task si sovrappone alla settimana w
            # NB: confronto con datetime (lun_w_dt), non date pura (lun_w)
            # perché pandas Timestamp non supporta confronto con date.
            if t_inizio <= lun_w_dt + timedelta(days=4) and t_fine >= lun_w_dt:
                weeks_task = max(1, (t_fine - t_inizio).days / 7)
                ore_task_in_w = (task_da_escludere.ore_stimate or 0) / weeks_task
                carico_w = max(0, carico_w - ore_task_in_w)

        sat_pct = round(carico_w / ore_sett_dip * 100) if ore_sett_dip > 0 else 0
        saturazioni.append(sat_pct)
        ore_totali += float(carico_w)
        settimane_dettaglio.append({
            "settimana": lun_w.strftime("%Y-%m-%d"),
            "settimana_label": lun_w.strftime("%d/%m"),
            "saturazione_pct": sat_pct,
            "ore": round(carico_w, 1),
        })

    if not saturazioni:
        sat_media = sat_max = sat_min = 0
    else:
        sat_media = round(sum(saturazioni) / len(saturazioni))
        sat_max = max(saturazioni)
        sat_min = min(saturazioni)

    return {
        "dipendente_id": dipendente_id,
        "nome": nome_dip,
        "ore_sett": ore_sett_dip,
        "settimane_coperte": n_sett,
        "saturazione_media_pct": sat_media,
        "saturazione_max_pct": sat_max,
        "saturazione_min_pct": sat_min,
        "ore_assegnate_totali": round(ore_totali, 1),
        "settimane_dettaglio": settimane_dettaglio,
    }


@router.get("/suggerisci-bilanciamento")
def suggerisci_bilanciamento(_: Utente = Depends(require_manager)):
    """Analizza le saturazioni e propone redistribuzioni per bilanciare il carico."""
    oggi = datetime.now()

    session = get_session()
    dipendenti = session.query(Dipendente).filter(Dipendente.attivo == True).all()
    # Pre-fetch dei task attivi (escluso P010) con joinedload sul progetto per
    # evitare N+1 query nel lookup del nome progetto. Una sola query SQL.
    tasks_rows = session.query(Task).options(joinedload(Task.progetto)).filter(
        Task.stato.in_(["In corso", "Da iniziare"]),
        Task.progetto_id != "P010",
    ).all()
    session.close()

    # Raggruppa i task per dipendente_id
    tasks_per_dip = {}
    for t in tasks_rows:
        if t.dipendente_id:
            tasks_per_dip.setdefault(t.dipendente_id, []).append(t)

    # Calcola saturazione per tutti
    persone = []
    for d in dipendenti:
        carico = carico_settimanale_dipendente(d.id, oggi)
        sat = round(carico / d.ore_sett * 100)

        task_list = []
        for t in tasks_per_dip.get(d.id, []):
            # Calcola ore settimanali per questo task
            t_inizio = _to_dt(t.data_inizio)
            t_fine = _to_dt(t.data_fine)
            durata_giorni = max(1, (t_fine - t_inizio).days)
            durata_sett = max(1, durata_giorni / 7)
            ore_stimate = t.ore_stimate or 0
            ore_sett_task = round(ore_stimate / durata_sett, 1)

            proj_nome = t.progetto.nome if t.progetto else "?"

            task_list.append({
                "task_id": t.id,
                "task_nome": t.nome,
                "progetto_id": t.progetto_id,
                "progetto_nome": proj_nome,
                "profilo_richiesto": t.profilo_richiesto or "",
                "ore_stimate": int(ore_stimate),
                "ore_sett": ore_sett_task,
                "stato": t.stato,
            })

        persone.append({
            "id": d.id,
            "nome": d.nome,
            "profilo": d.profilo,
            "competenze": d.competenze if isinstance(d.competenze, list) else [],
            "ore_sett": int(d.ore_sett),
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
