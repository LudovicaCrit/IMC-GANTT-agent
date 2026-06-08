"""
Data layer — implementazione database.
Stessa interfaccia pubblica di data_legacy.py.
"""

import pandas as pd
from datetime import datetime, timedelta, date
from models import (
    get_session, Dipendente, Progetto, Task, Assegnazione,
    Consuntivo, Segnalazione,
)

# ══════════════════════════════════════════════════════════════════════
# UTILITY DI CONVERSIONE
# ══════════════════════════════════════════════════════════════════════

def _to_dt(d):
    """date → datetime per compatibilità con codice esistente."""
    if isinstance(d, date) and not isinstance(d, datetime):
        return datetime.combine(d, datetime.min.time())
    return d


# ══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS — lettura (stessa interfaccia di data_legacy.py)
# ══════════════════════════════════════════════════════════════════════

def get_dipendente(did):
    if not did or did == "":
        return pd.Series({"id": "", "nome": "Non assegnato", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []})
    session = get_session()
    r = session.query(Dipendente).filter(
        Dipendente.id == did,
        Dipendente.attivo == True,
    ).first()
    session.close()
    if r is None:
        return pd.Series({"id": did, "nome": f"Sconosciuto ({did})", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []})
    return pd.Series({
        "id": r.id, "nome": r.nome, "profilo": r.profilo,
        "ore_sett": r.ore_sett, "costo_ora": r.costo_ora or 0,
        "competenze": r.competenze or [],
    })

def get_progetto(pid):
    if not pid or pid == "":
        return pd.Series({"id": "", "nome": "Sconosciuto", "cliente": "", "stato": ""})
    session = get_session()
    r = session.query(Progetto).filter(Progetto.id == pid).first()
    session.close()
    if r is None:
        return pd.Series({"id": pid, "nome": f"Sconosciuto ({pid})", "cliente": "", "stato": ""})
    return pd.Series({
        "id": r.id, "nome": r.nome, "cliente": r.cliente, "stato": r.stato,
        "data_inizio": _to_dt(r.data_inizio), "data_fine": _to_dt(r.data_fine),
        "budget_ore": r.budget_ore or 0, "valore_contratto": r.valore_contratto or 0,
        "descrizione": r.descrizione or "", "fase_corrente": r.fase_corrente or "",
    })

def get_tasks_progetto(pid):
    """Tasks di un progetto come DataFrame pandas.

    ⚠ DEBITO NOTO — DataFrame come tipo di ritorno è residuo storico della
    migrazione DataFrame→Postgres (vedi HANDOFF_postgres_migration.md §6-ter,
    "ULTIMO PASSO: rimuovere TUTTE le _reload() + i DataFrame in cache"). È
    stato MANTENUTO di proposito anche dalla Migration #1 (Step 3.1, 25/05/2026)
    per limitare la superficie di cambio: la conversione del campo predecessore
    → dipendenze NON è il momento giusto per rimuovere anche il DataFrame.
    Da rimuovere nel Blocco 4 (ritiro helper-DataFrame, dopo le 3 migration
    Alembic): a quel punto questa funzione tornerà direttamente una lista di
    dict (o oggetti Task ORM), e i chiamanti smetteranno di usare pandas.

    Step 3.1 (25/05/2026): la colonna `dipendenze` contiene liste di dict
    `{task_predecessore_id, tipo_dipendenza}` — non scalari. Pandas accetta
    liste come valori di colonna ma non le normalizza: la normalizzazione
    (esplodere in righe figlie o esporre come array nested) è anch'essa
    rimandata al Blocco 4.
    """
    session = get_session()
    from sqlalchemy.orm import joinedload, selectinload
    # Step 3.1 (25/05/2026): `predecessore` stringa singola → `dipendenze`
    # lista (modello-grafo, vedi alembic e5f6a7b8c9d0). selectinload sulle
    # dipendenze entranti = 1 query in più, evita N+1 sulla lista.
    rows = session.query(Task).options(
        joinedload(Task.fase_rel),
        selectinload(Task.dipendenze_entranti),
    ).filter(Task.progetto_id == pid).all()
    data = [{"id": r.id, "progetto_id": r.progetto_id, "nome": r.nome,
             "fase_id": r.fase_id,
             "fase": r.fase_rel.nome if r.fase_rel else "",
             "ore_stimate": r.ore_stimate or 0,
             "data_inizio": _to_dt(r.data_inizio), "data_fine": _to_dt(r.data_fine),
             "stato": r.stato, "profilo_richiesto": r.profilo_richiesto or "",
             "dipendente_id": r.dipendente_id or "",
             "dipendenze": [
                 {"task_predecessore_id": d.task_predecessore_id,
                  "tipo_dipendenza": d.tipo_dipendenza}
                 for d in r.dipendenze_entranti
             ]} for r in rows]
    session.close()
    return pd.DataFrame(data) if data else pd.DataFrame(columns=[
        "id", "progetto_id", "nome", "fase_id", "fase", "ore_stimate",
        "data_inizio", "data_fine", "stato", "profilo_richiesto",
        "dipendente_id", "dipendenze",
    ])

def get_consuntivi_task(tid):
    session = get_session()
    rows = session.query(Consuntivo).filter(Consuntivo.task_id == tid).all()
    data = [{"task_id": r.task_id, "dipendente_id": r.dipendente_id,
             "settimana": _to_dt(r.settimana), "ore_dichiarate": r.ore_dichiarate,
             "compilato": r.compilato, "data_compilazione": r.data_compilazione,
             "nota": r.nota or ""} for r in rows]
    session.close()
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["task_id","dipendente_id","settimana","ore_dichiarate","compilato","data_compilazione","nota"])

def get_consuntivi_dipendente(did):
    session = get_session()
    rows = session.query(Consuntivo).filter(Consuntivo.dipendente_id == did).all()
    data = [{"task_id": r.task_id, "dipendente_id": r.dipendente_id,
             "settimana": _to_dt(r.settimana), "ore_dichiarate": r.ore_dichiarate,
             "compilato": r.compilato, "data_compilazione": r.data_compilazione,
             "nota": r.nota or ""} for r in rows]
    session.close()
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["task_id","dipendente_id","settimana","ore_dichiarate","compilato","data_compilazione","nota"])

def ore_consuntivate_progetto(pid):
    from sqlalchemy import func
    session = get_session()
    total = session.query(
        func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0.0)
    ).join(Task, Consuntivo.task_id == Task.id).filter(
        Task.progetto_id == pid
    ).scalar()
    session.close()
    return total or 0

def tasso_compilazione_progetto(pid):
    session = get_session()
    base = session.query(Consuntivo).join(
        Task, Consuntivo.task_id == Task.id
    ).filter(Task.progetto_id == pid)
    n_tot = base.count()
    if n_tot == 0:
        session.close()
        return 0
    n_comp = base.filter(Consuntivo.compilato == True).count()
    session.close()
    return n_comp / n_tot * 100

def carico_settimanale_dipendente(did, settimana):
    """Carico di un dipendente in una settimana (in ore).

    ⚠ DEBITO DI DESIGN — distribuzione uniforme (decisione 18 mag, vedi handoff):
    Il calcolo assume che `ore_stimate` di un task siano distribuite
    UNIFORMEMENTE su tutte le settimane della sua durata. Questa è una
    semplificazione provvisoria: in realtà il PM dovrebbe poter dichiarare
    una distribuzione settimanale esplicita (es. "20h la prima settimana,
    5h le successive" per un task con setup iniziale concentrato).

    Step 2.7-pre del handoff v17 affronterà:
      1) Chiarimento semantica ore_stimate / ore_vendute / ore_pianificate /
         ore_consumate / ore_mancanti (storia: ore_pianificate ha avuto un
         significato bisecato durante l'evoluzione della specifica)
      2) Eventuale aggiunta campo Task.distribuzione_ore_per_settimana
      3) UI nel modale Task per dichiarare la distribuzione (default = uniforme)

    Fino allo Step 2.7-pre i numeri di saturazione mostrati sono onesti
    rispetto alla logica attuale, ma rappresentano una media uniformata
    della realtà operativa. NON costruire sopra logiche di redistribuzione
    automatica IA prima dello Step 2.7-pre.

    Filtri (iso-comportamento col vecchio DataFrame loader):
      - task del dipendente, stato NON in ("Completato", "Sospeso")
      - sovrapposizione con la settimana lunedì–venerdì
      - task senza data_inizio/data_fine (NULL): esclusi (in SQL WHERE)
    """
    lun = settimana - timedelta(days=settimana.weekday())
    ven = lun + timedelta(days=4)

    session = get_session()
    try:
        tasks_dip = (
            session.query(Task)
            .filter(
                Task.dipendente_id == did,
                Task.stato.notin_(["Completato", "Sospeso"]),
                Task.data_inizio <= ven,
                Task.data_fine >= lun,
            )
            .all()
        )
    finally:
        session.close()

    ore = 0
    for t in tasks_dip:
        # Distribuzione uniforme: ore_stimate / durata in settimane.
        # weeks = max(1, ...) per task brevi (< 1 settimana).
        weeks = max(1, (t.data_fine - t.data_inizio).days / 7)
        ore += (t.ore_stimate or 0) / weeks
    return round(ore, 1)

def get_progetti_dipendente(did):
    session = get_session()
    rows = session.query(Task.progetto_id, Progetto.nome).join(
        Progetto, Task.progetto_id == Progetto.id
    ).filter(
        Task.dipendente_id == did,
        Task.stato.in_(["In corso", "Da iniziare"]),
    ).order_by(Task.id).all()
    session.close()
    seen, out = set(), []
    for pid, nome in rows:
        if pid not in seen:
            seen.add(pid)
            out.append(nome)
    return out


# ══════════════════════════════════════════════════════════════════════
# FUNZIONI DI MODIFICA — scrittura (scrivono nel db + ricaricano cache)
# ══════════════════════════════════════════════════════════════════════

def _next_task_id():
    session = get_session()
    from sqlalchemy import func
    max_id = session.query(func.max(Task.id)).scalar()
    session.close()
    if max_id and max_id.startswith("T") and max_id[1:].isdigit():
        return f"T{int(max_id[1:]) + 1:03d}"
    return "T001"


def genera_id_task_multipli(n, session=None):
    """Genera `n` id task consecutivi (formato T###) in un colpo solo.

    Step 2.7 (20/05/2026) — chiude la triplicazione del debito #22.
    Serve quando si creano PIÙ task nella stessa transazione: chiamare
    _next_task_id() in loop darebbe id duplicati, perché legge sempre lo
    stesso max() finché la transazione non è committata. Questa funzione
    legge il max UNA volta e poi incrementa un contatore locale.

    Parametri:
      n: quanti id servono (>= 0).
      session: se fornita, riusa quella sessione (caso transazionale: il
        chiamante sta già dentro una transazione aperta). Se None, ne apre
        e chiude una propria.

    Ritorna: lista di `n` stringhe id, es. ["T071", "T072", "T073"].

    NOTA (debito #22, forma residua): la generazione resta applicativa
    (max+1). La soluzione definitiva è una sequence lato DB — rimandata al
    ridisegno DB pilota (handoff §5.9). Questa utility elimina la
    triplicazione del pattern, non la sua natura applicativa.
    """
    if n <= 0:
        return []
    from sqlalchemy import func
    proprietaria = session is None
    if proprietaria:
        session = get_session()
    try:
        max_id = session.query(func.max(Task.id)).scalar()
        if max_id and max_id.startswith("T") and max_id[1:].isdigit():
            partenza = int(max_id[1:]) + 1
        else:
            partenza = 1
        return [f"T{partenza + i:03d}" for i in range(n)]
    finally:
        if proprietaria:
            session.close()


def _next_progetto_id():
    session = get_session()
    from sqlalchemy import func
    max_id = session.query(func.max(Progetto.id)).scalar()
    session.close()
    if max_id and max_id.startswith("P") and max_id[1:].isdigit():
        return f"P{int(max_id[1:]) + 1:03d}"
    return "P001"


def aggiungi_task(progetto_id, nome, fase, ore_stimate, data_inizio, data_fine,
                  stato="Da iniziare", profilo_richiesto="", dipendente_id="",
                  dipendenze=None):
    """Crea un task. Step 2.1 D1: il parametro `fase` (stringa) viene risolto
    a `fase_id` cercando la `Fase` del progetto col nome corrispondente.

    Step 3.1 (25/05/2026): il vecchio parametro `predecessore` (stringa singola)
    è sostituito da `dipendenze`: lista di dict
    `{task_predecessore_id, tipo_dipendenza}`. Le righe corrispondenti vengono
    create nella tabella `dipendenza_task` dopo l'INSERT del task.

    Parametri:
      dipendenze: lista (opzionale) di dict con chiavi:
        - task_predecessore_id (str, obbligatorio): id del task predecessore
        - tipo_dipendenza (str, opzionale, default 'FS'): uno di TIPI_DIPENDENZA

    Errori:
      ValueError se:
        - la stringa `fase` non matcha nessuna Fase del progetto;
        - una delle dipendenze punta a un task inesistente (FK orfana);
        - una delle dipendenze ha task_predecessore_id == new_id (self-loop);
        - tipo_dipendenza non è in TIPI_DIPENDENZA;
        - la lista `dipendenze` contiene predecessori duplicati.
      Il chiamante (router) deve catturarle e convertirle in HTTP 4xx.

    Timing degli id e sequenza transazionale:
      `new_id` è generato applicativamente (`_next_task_id()` → "T###"), quindi
      è noto PRIMA dell'add — non serve aspettare il DB. La sequenza è:
        1. genera new_id (applicativo);
        2. valida `dipendenze` (predecessori esistenti, no self-loop, no
           duplicati, tipo ammesso) — errori chiari, niente FK violation grezza;
        3. session.add(task);
        4. session.flush() ← rende il task visibile alle FK delle
           DipendenzaTask successive (anche se SQLAlchemy ordina gli INSERT
           correttamente, il flush rende la sequenza esplicita);
        5. per ogni d in dipendenze: session.add(DipendenzaTask(...));
        6. eventuale assegnazione dipendente;
        7. session.commit() → INSERT cumulativo, transazione singola.
    """
    from models import Fase, DipendenzaTask, TIPI_DIPENDENZA  # import locale per evitare cicli

    new_id = _next_task_id()
    session = get_session()

    # Step 2.1 D1: risolvi fase stringa → fase_id (NOT NULL)
    fase_row = session.query(Fase).filter(
        Fase.progetto_id == progetto_id,
        Fase.nome == fase
    ).first()
    if not fase_row:
        session.close()
        raise ValueError(
            f"Fase '{fase}' non trovata nel progetto '{progetto_id}'. "
            f"Le fasi vanno create prima dei task."
        )

    # Step 3.1: valida le dipendenze a monte — errori applicativi chiari,
    # non FK/CHECK/UNIQUE violation grezze del DB.
    dipendenze = dipendenze or []
    if dipendenze:
        pred_ids = [d["task_predecessore_id"] for d in dipendenze]

        # Self-loop
        if new_id in pred_ids:
            session.close()
            raise ValueError(
                f"Dipendenza self-loop rifiutata: il task in creazione "
                f"({new_id}) non può essere predecessore di se stesso."
            )

        # Duplicati nella lista
        if len(set(pred_ids)) != len(pred_ids):
            session.close()
            raise ValueError(
                f"Predecessori duplicati nella lista dipendenze: "
                f"{[p for p in pred_ids if pred_ids.count(p) > 1]}. "
                f"Ogni (predecessore, successore) deve essere unico."
            )

        # Tipi dipendenza ammessi
        for d in dipendenze:
            tipo = d.get("tipo_dipendenza", "FS")
            if tipo not in TIPI_DIPENDENZA:
                session.close()
                raise ValueError(
                    f"Tipo dipendenza '{tipo}' non ammesso. "
                    f"Valori accettati: {TIPI_DIPENDENZA}."
                )

        # Predecessori esistenti (FK orfani) — una sola query
        esistenti = {r[0] for r in session.query(Task.id).filter(
            Task.id.in_(pred_ids)
        ).all()}
        orfani = [p for p in pred_ids if p not in esistenti]
        if orfani:
            session.close()
            raise ValueError(
                f"Predecessori inesistenti: {orfani}. "
                f"Creare i task predecessori prima, o rimuoverli dalla lista."
            )

    task = Task(
        id=new_id, progetto_id=progetto_id, nome=nome, fase_id=fase_row.id,
        ore_stimate=ore_stimate,
        data_inizio=data_inizio.date() if isinstance(data_inizio, datetime) else data_inizio,
        data_fine=data_fine.date() if isinstance(data_fine, datetime) else data_fine,
        stato=stato, profilo_richiesto=profilo_richiesto,
        dipendente_id=dipendente_id,
    )
    session.add(task)
    # Flush esplicito: il task diventa visibile alle FK delle DipendenzaTask
    # successive. Vedi docstring "Timing degli id e sequenza transazionale".
    session.flush()

    # Step 3.1: crea le righe DipendenzaTask (validate sopra)
    for d in dipendenze:
        session.add(DipendenzaTask(
            task_predecessore_id=d["task_predecessore_id"],
            task_successore_id=new_id,
            tipo_dipendenza=d.get("tipo_dipendenza", "FS"),
        ))

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
    return new_id


def sostituisci_dipendenze(task_id, dipendenze):
    """Step 3.1 (Gruppo B): SOSTITUISCE l'intera lista di dipendenze entranti
    di un task esistente (approccio "replace").

    Mentre `aggiungi_task` imposta le dipendenze SOLO alla creazione, questo
    helper le modifica su un task già esistente: cancella tutte le righe
    `dipendenza_task` con `task_successore_id == task_id` e ricrea quelle
    passate. È il backend dell'endpoint PUT /api/tasks/{task_id}/dipendenze.

    Args:
      task_id: id del task SUCCESSORE (quello le cui dipendenze si modificano).
      dipendenze: lista di dict con chiavi:
        - task_predecessore_id (str, obbligatorio): id del task predecessore;
        - tipo_dipendenza (str, opzionale, default 'FS'): uno di TIPI_DIPENDENZA.
        Lista vuota → rimuove tutte le dipendenze entranti del task.

    Validazione (stesse regole di `aggiungi_task`, errori applicativi chiari
    invece di FK/UNIQUE/CHECK grezzi del DB):
      - il task_id deve esistere;
      - ogni task_predecessore_id deve esistere (no FK orfana);
      - no self-loop (predecessore == task_id);
      - no predecessori duplicati nella lista. NB: il vincolo UNIQUE è su
        (task_predecessore_id, task_successore_id), quindi — avendo qui un
        unico successore — due righe sullo stesso predecessore con tipi diversi
        (es. SS+FF sulla stessa coppia) NON sono ammesse: vengono rifiutate qui
        come duplicati (debito noto Step 3.1);
      - tipo_dipendenza ∈ TIPI_DIPENDENZA (default 'FS' se assente).

    Raises:
      ValueError: per ognuna delle violazioni sopra (il router → HTTP 400).

    Returns:
      list[dict]: la lista aggiornata delle dipendenze entranti del task,
        nel formato {task_predecessore_id, tipo_dipendenza}.
    """
    from models import DipendenzaTask, TIPI_DIPENDENZA  # import locale per evitare cicli

    dipendenze = dipendenze or []
    session = get_session()

    # Il task successore deve esistere.
    if not session.query(Task.id).filter(Task.id == task_id).first():
        session.close()
        raise ValueError(f"Task '{task_id}' inesistente.")

    if dipendenze:
        pred_ids = [d["task_predecessore_id"] for d in dipendenze]

        # Self-loop
        if task_id in pred_ids:
            session.close()
            raise ValueError(
                f"Dipendenza self-loop rifiutata: il task "
                f"({task_id}) non può essere predecessore di se stesso."
            )

        # Duplicati nella lista (copre anche il vincolo UNIQUE sulla coppia:
        # stesso predecessore con tipi diversi = stessa coppia ordinata).
        if len(set(pred_ids)) != len(pred_ids):
            session.close()
            raise ValueError(
                f"Predecessori duplicati nella lista dipendenze: "
                f"{sorted({p for p in pred_ids if pred_ids.count(p) > 1})}. "
                f"Ogni (predecessore, successore) deve essere unico: non è "
                f"ammesso lo stesso predecessore con tipi diversi sulla stessa "
                f"coppia."
            )

        # Tipi dipendenza ammessi
        for d in dipendenze:
            tipo = d.get("tipo_dipendenza", "FS")
            if tipo not in TIPI_DIPENDENZA:
                session.close()
                raise ValueError(
                    f"Tipo dipendenza '{tipo}' non ammesso. "
                    f"Valori accettati: {TIPI_DIPENDENZA}."
                )

        # Predecessori esistenti (FK orfani) — una sola query
        esistenti = {r[0] for r in session.query(Task.id).filter(
            Task.id.in_(pred_ids)
        ).all()}
        orfani = [p for p in pred_ids if p not in esistenti]
        if orfani:
            session.close()
            raise ValueError(
                f"Predecessori inesistenti: {orfani}. "
                f"Creare i task predecessori prima, o rimuoverli dalla lista."
            )

    # Transazione: cancella le entranti correnti, ricrea dalla lista.
    try:
        session.query(DipendenzaTask).filter(
            DipendenzaTask.task_successore_id == task_id
        ).delete(synchronize_session=False)

        for d in dipendenze:
            session.add(DipendenzaTask(
                task_predecessore_id=d["task_predecessore_id"],
                task_successore_id=task_id,
                tipo_dipendenza=d.get("tipo_dipendenza", "FS"),
            ))
        session.commit()

        righe = session.query(DipendenzaTask).filter(
            DipendenzaTask.task_successore_id == task_id
        ).all()
        return [
            {"task_predecessore_id": r.task_predecessore_id,
             "tipo_dipendenza": r.tipo_dipendenza}
            for r in righe
        ]
    finally:
        session.close()


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
    return True


# ══════════════════════════════════════════════════════════════════════
# SEGNALAZIONI PERSISTENTI
# ══════════════════════════════════════════════════════════════════════

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
    session = get_session()
    # Leggi MAX id dal database
    from sqlalchemy import func
    max_id = session.query(func.max(Segnalazione.id)).scalar()
    if max_id and max_id.startswith("S") and max_id[1:].isdigit():
        next_num = int(max_id[1:]) + 1
    else:
        next_num = 1
    new_id = f"S{next_num:03d}"
    session.add(Segnalazione(
        id=new_id, tipo=tipo, priorita=priorita,
        dipendente_id=dipendente_id, dettaglio=dettaglio,
        fonte="chatbot", stato="aperta",
    ))
    session.commit()
    session.close()
    return new_id


# ══════════════════════════════════════════════════════════════════════
# CONSUNTIVI — SALVATAGGIO
# ══════════════════════════════════════════════════════════════════════

def salva_consuntivo(dipendente_id, settimana, ore_per_task, stati_per_task,
                     giorni_sede=0, giorni_remoto=0,
                     ore_assenza=0, tipo_assenza="", nota_assenza="",
                     spese_lista=None):
    """
    Salva il consuntivo settimanale completo di un dipendente.
    ore_per_task: dict {task_id: ore}
    stati_per_task: dict {task_id: stato}
    """
    from models import PresenzaSettimanale, Spesa

    session = get_session()
    settimana_date = settimana.date() if isinstance(settimana, datetime) else settimana

    # 1) Salva/aggiorna ore per ogni task
    for task_id, ore in ore_per_task.items():
        if ore == 0 and not stati_per_task.get(task_id):
            continue  # salta task senza ore né stato

        existing = session.query(Consuntivo).filter(
            Consuntivo.task_id == task_id,
            Consuntivo.dipendente_id == dipendente_id,
            Consuntivo.settimana == settimana_date,
        ).first()

        if existing:
            existing.ore_dichiarate = ore
            existing.compilato = True
            existing.data_compilazione = datetime.utcnow()
            stato = stati_per_task.get(task_id, "In corso")
            if stato == "Bloccato":
                existing.motivo_fermo = "Segnalato come bloccato dal dipendente"
        else:
            session.add(Consuntivo(
                task_id=task_id,
                dipendente_id=dipendente_id,
                settimana=settimana_date,
                ore_dichiarate=ore,
                compilato=True,
                data_compilazione=datetime.utcnow(),
                motivo_fermo="Segnalato come bloccato" if stati_per_task.get(task_id) == "Bloccato" else None,
            ))

    # 2) Salva presenze settimanali (smart working + assenze)
    existing_pres = session.query(PresenzaSettimanale).filter(
        PresenzaSettimanale.dipendente_id == dipendente_id,
        PresenzaSettimanale.settimana == settimana_date,
    ).first()

    if existing_pres:
        existing_pres.giorni_sede = giorni_sede
        existing_pres.giorni_remoto = giorni_remoto
        existing_pres.ore_assenza = ore_assenza
        existing_pres.tipo_assenza = tipo_assenza if ore_assenza > 0 else None
        existing_pres.nota_assenza = nota_assenza if ore_assenza > 0 else None
    else:
        session.add(PresenzaSettimanale(
            dipendente_id=dipendente_id,
            settimana=settimana_date,
            giorni_sede=giorni_sede,
            giorni_remoto=giorni_remoto,
            ore_assenza=ore_assenza,
            tipo_assenza=tipo_assenza if ore_assenza > 0 else None,
            nota_assenza=nota_assenza if ore_assenza > 0 else None,
        ))

    # 3) Salva spese
    if spese_lista:
        for spesa in spese_lista:
            if spesa.get("importo", 0) > 0:
                session.add(Spesa(
                    dipendente_id=dipendente_id,
                    settimana=settimana_date,
                    descrizione=spesa.get("descrizione", ""),
                    importo=spesa["importo"],
                    categoria=spesa.get("categoria", ""),
                ))

    session.commit()
    session.close()

    return True