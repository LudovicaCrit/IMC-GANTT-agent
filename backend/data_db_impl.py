"""
Data layer — implementazione database.
Stessa interfaccia pubblica di data_legacy.py.
"""

import pandas as pd
from datetime import datetime, timedelta, date
from models import (
    get_session, Dipendente, Progetto, Task, Assegnazione,
    Consuntivo, Segnalazione, PianificazioneBozza,
)

# ══════════════════════════════════════════════════════════════════════
# CARICAMENTO DataFrame (cache — ricaricati dopo le modifiche)
# ══════════════════════════════════════════════════════════════════════

def _to_dt(d):
    """date → datetime per compatibilità con codice esistente."""
    if isinstance(d, date) and not isinstance(d, datetime):
        return datetime.combine(d, datetime.min.time())
    return d


def _load_dipendenti():
    session = get_session()
    rows = session.query(Dipendente).filter(Dipendente.attivo == True).all()
    data = [{"id": r.id, "nome": r.nome, "profilo": r.profilo,
             "ore_sett": r.ore_sett, "costo_ora": r.costo_ora or 0,
             "competenze": r.competenze or []} for r in rows]
    session.close()
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["id","nome","profilo","ore_sett","costo_ora","competenze"])


def _load_progetti():
    session = get_session()
    rows = session.query(Progetto).all()
    data = [{"id": r.id, "nome": r.nome, "cliente": r.cliente, "stato": r.stato,
             "data_inizio": _to_dt(r.data_inizio), "data_fine": _to_dt(r.data_fine),
             "budget_ore": r.budget_ore or 0, "valore_contratto": r.valore_contratto or 0,
             "descrizione": r.descrizione or "", "fase_corrente": r.fase_corrente or ""} for r in rows]
    session.close()
    return pd.DataFrame(data) if data else pd.DataFrame()


def _load_tasks():
    session = get_session()
    rows = session.query(Task).all()
    data = [{"id": r.id, "progetto_id": r.progetto_id, "nome": r.nome,
             "fase": r.fase or "", "ore_stimate": r.ore_stimate or 0,
             "data_inizio": _to_dt(r.data_inizio), "data_fine": _to_dt(r.data_fine),
             "stato": r.stato, "profilo_richiesto": r.profilo_richiesto or "",
             "dipendente_id": r.dipendente_id or "", "predecessore": r.predecessore or ""} for r in rows]
    session.close()
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=["id","progetto_id","nome","fase","ore_stimate","data_inizio","data_fine","stato","profilo_richiesto","dipendente_id","predecessore"])
    return df.fillna({"predecessore": ""})


def _load_consuntivi():
    session = get_session()
    rows = session.query(Consuntivo).all()
    data = [{"task_id": r.task_id, "dipendente_id": r.dipendente_id,
             "settimana": _to_dt(r.settimana), "ore_dichiarate": r.ore_dichiarate,
             "compilato": r.compilato, "data_compilazione": r.data_compilazione,
             "nota": r.nota or ""} for r in rows]
    session.close()
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["task_id","dipendente_id","settimana","ore_dichiarate","compilato","data_compilazione","nota"])


# Cache globale — usa un dict mutabile così _reload() funziona
# anche quando importato con "from data_db_impl import *"
_cache = {
    "DIPENDENTI": _load_dipendenti(),
    "PROGETTI": _load_progetti(),
    "TASKS": _load_tasks(),
    "CONSUNTIVI": _load_consuntivi(),
}

# Esponi come variabili di modulo (per compatibilità)
DIPENDENTI = _cache["DIPENDENTI"]
PROGETTI = _cache["PROGETTI"]
TASKS = _cache["TASKS"]
CONSUNTIVI = _cache["CONSUNTIVI"]


def _reload():
    global DIPENDENTI, PROGETTI, TASKS
    _cache["DIPENDENTI"] = _load_dipendenti()
    _cache["PROGETTI"] = _load_progetti()
    _cache["TASKS"] = _load_tasks()
    DIPENDENTI = _cache["DIPENDENTI"]
    PROGETTI = _cache["PROGETTI"]
    TASKS = _cache["TASKS"]
    # Aggiorna anche nel modulo data (il router)
    import data
    data.DIPENDENTI = DIPENDENTI
    data.PROGETTI = PROGETTI
    data.TASKS = TASKS


# ══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS — lettura (stessa interfaccia di data_legacy.py)
# ══════════════════════════════════════════════════════════════════════

def get_dipendente(did):
    if not did or did == "":
        return pd.Series({"id": "", "nome": "Non assegnato", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []})
    matches = DIPENDENTI[DIPENDENTI["id"] == did]
    if len(matches) == 0:
        return pd.Series({"id": did, "nome": f"Sconosciuto ({did})", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []})
    return matches.iloc[0]

def get_progetto(pid):
    if not pid or pid == "":
        return pd.Series({"id": "", "nome": "Sconosciuto", "cliente": "", "stato": ""})
    matches = PROGETTI[PROGETTI["id"] == pid]
    if len(matches) == 0:
        return pd.Series({"id": pid, "nome": f"Sconosciuto ({pid})", "cliente": "", "stato": ""})
    return matches.iloc[0]

def get_tasks_progetto(pid):
    return TASKS[TASKS["progetto_id"] == pid].copy()

def get_consuntivi_task(tid):
    return CONSUNTIVI[CONSUNTIVI["task_id"] == tid].copy()

def get_consuntivi_dipendente(did):
    return CONSUNTIVI[CONSUNTIVI["dipendente_id"] == did].copy()

def ore_consuntivate_progetto(pid):
    task_ids = TASKS[TASKS["progetto_id"] == pid]["id"].tolist()
    cons = CONSUNTIVI[CONSUNTIVI["task_id"].isin(task_ids)]
    return cons["ore_dichiarate"].sum()

def tasso_compilazione_progetto(pid):
    task_ids = TASKS[TASKS["progetto_id"] == pid]["id"].tolist()
    cons = CONSUNTIVI[CONSUNTIVI["task_id"].isin(task_ids)]
    if len(cons) == 0:
        return 0
    return cons["compilato"].sum() / len(cons) * 100

def carico_settimanale_dipendente(did, settimana):
    lun = settimana - timedelta(days=settimana.weekday())
    tasks_dip = TASKS[
        (TASKS["dipendente_id"] == did) &
        (~TASKS["stato"].isin(["Completato", "Sospeso"]))
    ]
    ore = 0
    for _, t in tasks_dip.iterrows():
        if t["data_inizio"] <= lun + timedelta(days=4) and t["data_fine"] >= lun:
            weeks = max(1, (t["data_fine"] - t["data_inizio"]).days / 7)
            ore += t["ore_stimate"] / weeks
    return round(ore, 1)

def get_progetti_dipendente(did):
    task_dip = TASKS[
        (TASKS["dipendente_id"] == did) &
        (TASKS["stato"].isin(["In corso", "Da iniziare"]))
    ]
    proj_ids = task_dip["progetto_id"].unique()
    return [PROGETTI[PROGETTI["id"] == pid].iloc[0]["nome"] for pid in proj_ids]


# ══════════════════════════════════════════════════════════════════════
# FUNZIONI DI MODIFICA — scrittura (scrivono nel db + ricaricano cache)
# ══════════════════════════════════════════════════════════════════════

def _next_task_id():
    existing = TASKS["id"].tolist()
    nums = [int(tid[1:]) for tid in existing if tid.startswith("T") and tid[1:].isdigit()]
    return f"T{max(nums) + 1:03d}" if nums else "T001"

def _next_progetto_id():
    existing = PROGETTI["id"].tolist()
    nums = [int(pid[1:]) for pid in existing if pid.startswith("P") and pid[1:].isdigit()]
    return f"P{max(nums) + 1:03d}" if nums else "P001"


def aggiungi_task(progetto_id, nome, fase, ore_stimate, data_inizio, data_fine,
                  stato="Da iniziare", profilo_richiesto="", dipendente_id="",
                  predecessore=""):
    new_id = _next_task_id()
    session = get_session()
    task = Task(
        id=new_id, progetto_id=progetto_id, nome=nome, fase=fase,
        ore_stimate=ore_stimate,
        data_inizio=data_inizio.date() if isinstance(data_inizio, datetime) else data_inizio,
        data_fine=data_fine.date() if isinstance(data_fine, datetime) else data_fine,
        stato=stato, profilo_richiesto=profilo_richiesto,
        dipendente_id=dipendente_id, predecessore=predecessore,
    )
    session.add(task)
    if dipendente_id:
        existing_assegn = session.query(Assegnazione).filter(
            Assegnazione.task_id == new_id,
            Assegnazione.dipendente_id == dipendente_id
        ).first()
        if not existing_assegn:
            session.add(Assegnazione(
                task_id=new_id, dipendente_id=dipendente_id,
                ore_assegnate=ore_stimate, ruolo="responsabile",
            ))
    session.commit()
    session.close()
    _reload()
    return new_id


def modifica_task(task_id, **kwargs):
    session = get_session()
    task = session.query(Task).filter(Task.id == task_id).first()
    if not task:
        session.close()
        return False
    for campo, valore in kwargs.items():
        if hasattr(task, campo):
            if campo in ("data_inizio", "data_fine") and isinstance(valore, datetime):
                valore = valore.date()
            setattr(task, campo, valore)
    session.commit()
    session.close()
    _reload()
    return True


def cambia_stato_progetto(progetto_id, nuovo_stato):
    session = get_session()
    proj = session.query(Progetto).filter(Progetto.id == progetto_id).first()
    if not proj:
        session.close()
        return False
    proj.stato = nuovo_stato
    session.commit()
    session.close()
    _reload()
    return True


def calcola_impatto_saturazione(task_modifiche, task_nuovi=None):
    tasks_sim = TASKS.copy()
    for mod in (task_modifiche or []):
        idx = tasks_sim.index[tasks_sim["id"] == mod["task_id"]]
        if len(idx) > 0 and mod["campo"] in tasks_sim.columns:
            tasks_sim.loc[idx, mod["campo"]] = mod["nuovo_valore"]
    if task_nuovi:
        for nt in task_nuovi:
            tasks_sim = pd.concat([tasks_sim, pd.DataFrame([nt])], ignore_index=True)

    dipendenti_coinvolti = set()
    for mod in (task_modifiche or []):
        tr = TASKS[TASKS["id"] == mod["task_id"]]
        if len(tr) > 0:
            dipendenti_coinvolti.add(tr.iloc[0]["dipendente_id"])
            if mod["campo"] == "dipendente_id":
                dipendenti_coinvolti.add(mod["nuovo_valore"])
    for nt in (task_nuovi or []):
        if nt.get("dipendente_id"):
            dipendenti_coinvolti.add(nt["dipendente_id"])

    oggi = datetime(2026, 3, 9)
    risultati_dip = []
    for did in dipendenti_coinvolti:
        if not did:
            continue
        try:
            dip = get_dipendente(did)
        except (IndexError, KeyError):
            continue
        carico_prima = carico_settimanale_dipendente(did, oggi)
        sat_prima = round(carico_prima / dip["ore_sett"] * 100)
        tasks_dip_sim = tasks_sim[
            (tasks_sim["dipendente_id"] == did) &
            (~tasks_sim["stato"].isin(["Completato", "Sospeso"]))
        ]
        lun = oggi - timedelta(days=oggi.weekday())
        carico_dopo = 0
        for _, t in tasks_dip_sim.iterrows():
            if t["data_inizio"] <= lun + timedelta(days=4) and t["data_fine"] >= lun:
                weeks = max(1, (t["data_fine"] - t["data_inizio"]).days / 7)
                carico_dopo += t["ore_stimate"] / weeks
        carico_dopo = round(carico_dopo, 1)
        sat_dopo = round(carico_dopo / dip["ore_sett"] * 100)
        risultati_dip.append({
            "id": did, "nome": dip["nome"], "profilo": dip["profilo"],
            "saturazione_prima": sat_prima, "saturazione_dopo": sat_dopo,
            "delta": sat_dopo - sat_prima, "ore_sett": int(dip["ore_sett"]),
        })

    progetti_ids = set()
    for mod in (task_modifiche or []):
        tr = TASKS[TASKS["id"] == mod["task_id"]]
        if len(tr) > 0:
            progetti_ids.add(tr.iloc[0]["progetto_id"])
    for nt in (task_nuovi or []):
        if nt.get("progetto_id"):
            progetti_ids.add(nt["progetto_id"])

    progetti_impattati = []
    for pid in progetti_ids:
        try:
            proj = get_progetto(pid)
            progetti_impattati.append({"id": pid, "nome": proj["nome"]})
        except (IndexError, KeyError):
            pass

    alert = []
    for r in risultati_dip:
        if r["saturazione_dopo"] > 100 and r["saturazione_prima"] <= 100:
            alert.append(f"{r['nome']} passerebbe dal {r['saturazione_prima']}% al {r['saturazione_dopo']}% — sovraccarico!")
        elif r["saturazione_dopo"] > 100 and r["delta"] > 0:
            alert.append(f"{r['nome']} è già al {r['saturazione_prima']}% e salirebbe al {r['saturazione_dopo']}%")

    return {"dipendenti_impattati": risultati_dip, "progetti_impattati": progetti_impattati, "alert": alert}


# ══════════════════════════════════════════════════════════════════════
# SEGNALAZIONI PERSISTENTI
# ══════════════════════════════════════════════════════════════════════

_segn_counter = 3

def get_segnalazioni():
    session = get_session()
    rows = session.query(Segnalazione).order_by(Segnalazione.created_at.desc()).all()
    result = []
    for r in rows:
        dip_nome = ""
        if r.dipendente_id:
            try:
                dip_nome = get_dipendente(r.dipendente_id)["nome"]
            except (IndexError, KeyError):
                pass
        result.append({
            "id": r.id, "tipo": r.tipo, "priorita": r.priorita,
            "dipendente_id": r.dipendente_id or "",
            "dipendente": dip_nome,
            "dettaglio": r.dettaglio,
            "timestamp": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        })
    session.close()
    return result


def aggiungi_segnalazione(tipo, priorita, dipendente_id, dettaglio):
    global _segn_counter
    _segn_counter += 1
    new_id = f"S{_segn_counter:03d}"
    session = get_session()
    session.add(Segnalazione(
        id=new_id, tipo=tipo, priorita=priorita,
        dipendente_id=dipendente_id, dettaglio=dettaglio,
        fonte="chatbot", stato="aperta",
    ))
    session.commit()
    session.close()
    return new_id


# ══════════════════════════════════════════════════════════════════════
# BOZZE PIANIFICAZIONE PERSISTENTI
# ══════════════════════════════════════════════════════════════════════

def salva_bozza_pianificazione(progetto_id, dati_json):
    session = get_session()
    existing = session.query(PianificazioneBozza).filter(
        PianificazioneBozza.progetto_id == progetto_id
    ).first()
    if existing:
        existing.dati_json = dati_json
        existing.updated_at = datetime.utcnow()
    else:
        session.add(PianificazioneBozza(progetto_id=progetto_id, dati_json=dati_json))
    session.commit()
    session.close()


def carica_bozza_pianificazione(progetto_id):
    session = get_session()
    bozza = session.query(PianificazioneBozza).filter(
        PianificazioneBozza.progetto_id == progetto_id
    ).first()
    result = bozza.dati_json if bozza else None
    session.close()
    return result