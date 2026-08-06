"""
Data layer — implementazione database.
Stessa interfaccia pubblica di data_legacy.py.
"""

from datetime import datetime, timedelta, date
from models import (
    get_session, Dipendente, Progetto, Task,
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
        return {"id": "", "nome": "Non assegnato", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []}
    session = get_session()
    r = session.query(Dipendente).filter(
        Dipendente.id == did,
        Dipendente.attivo == True,
    ).first()
    session.close()
    if r is None:
        return {"id": did, "nome": f"Sconosciuto ({did})", "profilo": "-", "ore_sett": 40, "costo_ora": 0, "competenze": []}
    return {
        "id": r.id, "nome": r.nome, "profilo": r.profilo,
        "ore_sett": r.ore_sett, "costo_ora": r.costo_ora or 0,
        "competenze": r.competenze or [],
    }

def get_progetto(pid):
    if not pid or pid == "":
        return {"id": "", "nome": "Sconosciuto", "cliente": "", "stato": ""}
    session = get_session()
    r = session.query(Progetto).filter(Progetto.id == pid).first()
    session.close()
    if r is None:
        return {"id": pid, "nome": f"Sconosciuto ({pid})", "cliente": "", "stato": ""}
    return {
        "id": r.id, "nome": r.nome, "cliente": r.cliente, "stato": r.stato,
        "data_inizio": _to_dt(r.data_inizio), "data_fine": _to_dt(r.data_fine),
        "budget_ore": r.budget_ore or 0, "valore_contratto": r.valore_contratto or 0,
        "descrizione": r.descrizione or "", "fase_corrente": r.fase_corrente or "",
    }

def get_tasks_progetto(pid):
    """Tasks di un progetto come lista di dict (uno per task).

    Blocco 4 (ritiro helper-DataFrame): questa funzione tornava un DataFrame
    pandas, residuo storico della migrazione DataFrame→Postgres. Ora restituisce
    direttamente la lista di dict `data` (e `[]` se il progetto non ha task).

    Ogni task espone `dipendenze`: lista di dict
    `{task_predecessore_id, tipo_dipendenza}` (modello-grafo Step 3.1,
    25/05/2026) — già nella forma nested corretta, niente normalizzazione.
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
    return data

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

def progetti_attivi_visibili(current_user):
    """Id dei progetti ATTIVI visibili a `current_user` (filtro self-or-manager).

    Confina nello strato dati la conoscenza del DB del filtro di visibilità,
    così lo stesso filtro è riusabile identico dalla Home management, dalla Home
    dipendente e dalla Consuntivazione (coerente col Blocco 4 e con la futura
    conversione ORM).

    Attivi = Progetto.stato in STATI_PROGETTO_ATTIVI.
    Identità:
      - manager → tutti gli attivi;
      - altrimenti → UNIONE (senza duplicati) di:
          a) progetti attivi di cui è PM (Progetto.pm_id == dipendente_id);
          b) progetti attivi con almeno un task assegnato a lui
             (Task.dipendente_id == dipendente_id), anche se il PM è un altro.
             Così un membro vede i progetti su cui lavora, non solo quelli che
             dirige.

    NB: il confronto è con `dipendente_id` (FK a dipendenti), NON con
    `current_user.id` (PK di utenti, dominio diverso): sbagliarlo darebbe un
    filtro che non matcha mai, silenziosamente.

    Step 4 sottotask (06/08/2026) — il ramo (b) leggeva la tabella
    `Assegnazione` con un secondo join. Ora legge `Task.dipendente_id`, che è
    l'UNICA verità sull'assegnazione. Erano due sorgenti per lo stesso fatto e
    solo una veniva mantenuta: `modifica_task` aggiorna `Task.dipendente_id` e
    non tocca `Assegnazione`, quindi ogni riassegnazione dal Cantiere faceva
    divergere il mirror — un dipendente continuava a "vedere" il progetto da
    cui era stato tolto, e non vedeva quello su cui era stato messo. Al momento
    del taglio le due sorgenti erano ancora allineate (114 coppie identiche):
    il drift era latente, non ancora materializzato. Il rischio si chiude
    togliendo il secondo termine, non riparando il mirror.

    La tabella resta in schema ma è fuori dal giro: nessuno la legge più,
    nessuno la scrive più. Il DROP è rimandato a una sessione di pulizia
    monconi dedicata.

    Ritorna list[str] (gli id progetto sono String(10)).
    """
    from models import STATI_PROGETTO_ATTIVI

    session = get_session()
    try:
        if current_user.ruolo_app == "manager":
            q = session.query(Progetto.id).filter(
                Progetto.stato.in_(STATI_PROGETTO_ATTIVI)
            )
            return [pid for (pid,) in q.all()]

        did = current_user.dipendente_id
        # a) progetti attivi di cui è PM
        pm_q = session.query(Progetto.id).filter(
            Progetto.stato.in_(STATI_PROGETTO_ATTIVI),
            Progetto.pm_id == did,
        )
        # b) progetti attivi con almeno un task assegnato a lui
        membro_q = (
            session.query(Progetto.id)
            .join(Task, Task.progetto_id == Progetto.id)
            .filter(
                Progetto.stato.in_(STATI_PROGETTO_ATTIVI),
                Task.dipendente_id == did,
            )
        )
        # Unione senza duplicati (un progetto può matchare entrambi i rami).
        ids = {pid for (pid,) in pm_q.all()} | {pid for (pid,) in membro_q.all()}
        return list(ids)
    finally:
        session.close()


def criticita_sforamento_progetti(progetti_ids):
    """Criticità di sforamento ore (consumate vs vendute) per i progetti dati.

    Home management — vista PM/manager. Restituisce SOLO i progetti che hanno
    almeno una criticità; i progetti sani non compaiono. `progetti_ids` è già
    la lista filtrata a monte (attivi + filtro identità); qui non si filtra per
    stato né per identità, si calcola e basta.

    DIREZIONE — "superamento_ore" confronta ore_consumate vs ore_vendute (budget
    commerciale, contratto col cliente). Il confronto con ore_pianificate (piano
    interno del PM) è una criticità di tipo DIVERSO, prevista in futuro come
    tipo: "superamento_pianificato", da affiancare a questa SENZA ridisegnare il
    payload (tipo è una stringa-enum, non un booleano). NON implementarlo ora.

    Calcolo unico (vincolante): un solo metodo di aggregazione applicato sia
    alle fasi sia al totale. ore_consumate di fase = SUM(Consuntivo.ore_dichiarate)
    sui task della fase (stesso pattern di routes/fasi.py:lista_fasi_progetto,
    concentrato qui). Il totale di progetto è la SOMMA delle ore_consumate di
    fase appena calcolate — NON una query separata, NON ore_consuntivate_progetto.
    Così fase e progetto sono coerenti per costruzione: il progetto sfora se e
    solo se la somma delle sue fasi sfora.

    ore_vendute di fase NULL/0: la fase non genera criticità di fase (nessun
    budget, niente /0), MA le sue ore_consumate entrano comunque nel totale di
    progetto (sottostimare il consumo nasconderebbe una criticità). Progetto con
    somma_vendute 0/NULL: saltato (non calcolabile, non è errore).
    """
    from sqlalchemy import func
    from models import Fase

    if not progetti_ids:
        return []

    session = get_session()
    try:
        progetti = (
            session.query(Progetto)
            .filter(Progetto.id.in_(progetti_ids))
            .all()
        )
        out = []
        for p in progetti:
            fasi = (
                session.query(Fase)
                .filter(Fase.progetto_id == p.id)
                .order_by(Fase.ordine)
                .all()
            )
            criticita = []
            somma_consumate = 0.0
            somma_vendute = 0.0
            for f in fasi:
                # Stessa aggregazione di routes/fasi.py: SUM(ore_dichiarate)
                # sui consuntivi dei task agganciati a questa fase.
                ore_consumate = float(
                    session.query(
                        func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0.0)
                    ).join(Task, Consuntivo.task_id == Task.id)
                    .filter(Task.fase_id == f.id)
                    .scalar() or 0.0
                )
                # Contributo al totale: SEMPRE, anche se la fase non ha budget.
                somma_consumate += ore_consumate
                ore_vendute = f.ore_vendute
                if ore_vendute:  # non None e non 0 → fase con budget
                    somma_vendute += ore_vendute
                    if ore_consumate > ore_vendute:
                        criticita.append({
                            "tipo": "superamento_ore",
                            "livello": "fase",
                            "fase_id": f.id,
                            "fase_nome": f.nome,
                            "dimensione_pct": round(ore_consumate / ore_vendute, 2),
                            "ore_consumate": ore_consumate,
                            "ore_vendute": float(ore_vendute),
                            "focus": f"fase-{f.id}",
                        })

            # Progetto senza budget complessivo: non calcolabile, si salta.
            if not somma_vendute:
                continue
            if somma_consumate > somma_vendute:
                criticita.append({
                    "tipo": "superamento_ore",
                    "livello": "progetto",
                    "fase_id": None,
                    "fase_nome": None,
                    "dimensione_pct": round(somma_consumate / somma_vendute, 2),
                    "ore_consumate": somma_consumate,
                    "ore_vendute": somma_vendute,
                    "focus": None,
                })

            if criticita:
                out.append({
                    "progetto_id": p.id,
                    "progetto_nome": p.nome,
                    "pm_id": p.pm_id,
                    "criticita": criticita,
                })
        return out
    finally:
        session.close()


def scostamento_stime_sottotask(task_ids):
    """Scostamento tra la scomposizione in sottotask e il piano del task.

    Step 2.3 sottotask (30/07/2026). SEGNALA, NON IMPONE: espone tre numeri e
    basta. Nessun vincolo, nessun blocco alla creazione o modifica di un
    sottotask se la somma sfora, nessun ribilanciamento automatico — il PM
    guarda e decide. (`routes/progetti.py`, che rifiuta con 422 se la somma
    delle ore di fase non quadra col budget di progetto, è il CONTRO-esempio:
    lì è un vincolo di creazione, qui è informazione.)

    FIRMA BATCH — accetta una LISTA di task_id e restituisce un dict
    {task_id: {...}}. È la forma che serve al chiamante più esigente
    (gantt_strutturato, che serializza tutti i task dei progetti attivi e non
    può permettersi una query per task). Chi ne vuole uno solo passa [task_id] e
    fa `.get(task_id)`. Stesso pattern di `ore_per_task` in routes/gantt.py:
    una GROUP BY, poi lookup con default.

    I TRE NUMERI, per ogni task calcolabile:
      - somma_stime_sottotask : SUM(Sottotask.ore_stimate) dei sottotask che
                                contano (vedi sotto)
      - ore_pianificate_task  : Task.ore_pianificate, il piano CORRENTE
      - differenza            : ore_pianificate_task − somma_stime_sottotask

    Segno della differenza: POSITIVA = il piano del task è più grande della
    somma delle stime, c'è piano non ancora coperto dalla scomposizione;
    NEGATIVA = i sottotask sforano il piano. Stessa convenzione di
    `ore_rimanenti` in routes/fasi.py (ore_vendute − ore_consumate), dove il
    positivo è il margine che resta e il negativo lo sforo: il PM legge i due
    scostamenti nello stesso verso.

    RIFERIMENTO = ore_pianificate e non ore_stimate. Sono due grandezze vive
    che si confrontano: le stime dei sottotask si aggiornano, il piano si
    rivede. `Task.ore_stimate` è il budget storico congelato (convenzione R1,
    non si tocca dopo l'avvio): confrontarci una somma che cambia darebbe uno
    scostamento che cresce da solo senza che nessuno abbia sbagliato piano.

    QUALI SOTTOTASK CONTANO — tutti tranne gli "Annullato" (i "Sospeso" SÌ).
    La domanda a cui questo numero risponde è «il piano di questo task quadra?»,
    ed è una domanda sul PIANO: un sottotask sospeso è in pausa ma resta nel
    piano, un annullato ne è stato tolto e le sue ore non sono più lavoro
    previsto. Precedente affine: `task_settimana_dipendente` filtra
    `Task.stato != "Annullato"` per la stessa ragione (cosa c'è nel piano di
    quella persona), mentre i filtri del carico/saturazione in routes/risorse.py
    escludono anche i Sospesi — ma quelli rispondono a «quanto lavoro c'è ORA»,
    che è un'altra domanda.

    QUANDO NON SI SEGNALA (la chiave manca dal dict, il chiamante legge None):
      - `Task.ore_pianificate` NULL: manca il termine di confronto. Non è un
        errore, non è calcolabile — come il "progetto senza budget complessivo:
        saltato" di `criticita_sforamento_progetti`.
      - task senza NESSUN sottotask che conta (mai scomposto, o scomposto e poi
        annullato tutto): la domanda non si pone. Senza questa esclusione ogni
        task non scomposto del sistema — cioè tutti e 114 quelli in DB oggi —
        risulterebbe "scostante" dell'intero piano: un falso positivo di massa
        che renderebbe la segnalazione inutile. Coerente con «i progetti sani
        non compaiono» di criticita_sforamento_progetti.
    NB: un task CON sottotask attivi ma tutti senza `ore_stimate` compare invece
    con somma 0 — lì la scomposizione esiste ma non è stimata, ed è
    informazione buona da mostrare, non un caso da nascondere. La GROUP BY
    distingue i due casi da sola: nessuna riga contro una riga che somma 0.
    """
    from sqlalchemy import func
    from models import Sottotask

    if not task_ids:
        return {}

    session = get_session()
    try:
        # Somma delle stime per task, in UNA query. I sottotask annullati sono
        # esclusi qui, non dopo: non devono nemmeno entrare nell'aggregato.
        somme = dict(
            session.query(
                Sottotask.task_id,
                func.coalesce(func.sum(Sottotask.ore_stimate), 0.0),
            )
            .filter(
                Sottotask.task_id.in_(task_ids),
                Sottotask.stato != "Annullato",
            )
            .group_by(Sottotask.task_id)
            .all()
        )
        if not somme:
            return {}

        # Il piano corrente dei soli task che hanno una scomposizione.
        piani = dict(
            session.query(Task.id, Task.ore_pianificate)
            .filter(Task.id.in_(list(somme.keys())))
            .all()
        )

        out = {}
        for tid, somma in somme.items():
            piano = piani.get(tid)
            if piano is None:  # niente piano corrente → non calcolabile
                continue
            somma = float(somma or 0.0)
            piano = float(piano)
            out[tid] = {
                "somma_stime_sottotask": round(somma, 1),
                "ore_pianificate_task": round(piano, 1),
                "differenza": round(piano - somma, 1),
            }
        return out
    finally:
        session.close()


def ore_derivate_sottotask(avanzamenti, settimana=None):
    """Ore derivate dall'avanzamento dichiarato su uno o più sottotask.

    Step 4 sottotask — STRATO 1 del motore ore-derivate (06/08/2026). Calcola e
    basta: NON scrive niente, né su ConsuntivoSottotask né su Consuntivo. Dato
    lo stato del database ritorna dei numeri, e chi la chiama decide cosa
    farne. Isolarla così la rende testabile senza montare un salvataggio
    completo, ed è la ragione per cui esiste come funzione a sé.

    LA FORMULA
    ----------
        Δpct  = percentuale − baseline
        ore   = (Δpct / 100) × Sottotask.ore_stimate       [clamp Δ<0 → 0 ore]

    La `baseline` è l'ultima percentuale non-NULL dichiarata su QUEL SOTTOTASK
    in una settimana PRECEDENTE — non il lunedì-calendario prima: l'ultima
    settimana in cui qualcuno si è espresso. Se non esiste, è 0 (prima
    dichiarazione: Δ = percentuale intera).

    BASELINE PER SOTTOTASK, NON PER DIPENDENTE — è la scelta che regge tutto.
    La percentuale descrive il PEZZO DI LAVORO («a che punto è questo
    sottotask»), non la persona. La grana di ConsuntivoSottotask include il
    dipendente perché la DICHIARAZIONE ha un autore, ma il fatto dichiarato è
    del pezzo. Cercando la baseline per (sottotask, dipendente) ogni passaggio
    di consegne produrrebbe una falsa prima dichiarazione: riassegnato il
    sottotask da X a Y (override cambiato, o task riassegnato — vedi
    Sottotask.dipendente_id), Y non ha storia propria, la sua baseline sarebbe
    0, e su un pezzo già portato al 60% da X una dichiarazione al 70% di Y
    deriverebbe il 70% delle ore invece del 10%. Si ri-deriverebbe lavoro già
    derivato, e proprio nel momento in cui sbagliare costa di più.

    Se nella settimana-baseline ci sono PIÙ dichiarazioni non-NULL (grana
    unique per sottotask+dipendente+settimana: possibile se due collaboratori
    si esprimono entrambi, anche se la regola vuole che scriva solo
    l'assegnatario), si prende la percentuale PIÙ ALTA. Il pezzo è avanzato
    almeno quanto la dichiarazione più avanti, e una baseline più alta produce
    un Δ più piccolo: sbaglia dalla parte di derivare MENO ore, mai di più.

    INPUT
    -----
    avanzamenti: dict {sottotask_id: percentuale}. La percentuale può essere
                 None — è il caso «slider fermo» previsto dal design: il
                 dipendente si è espresso sullo stato ma non sull'avanzamento,
                 e da lì non si deriva nessuna ora. NON si inventa un default.
    settimana:   la settimana della dichiarazione. Normalizzata al lunedì con
                 `_lunedi`, come ovunque. Una sola per chiamata: in un
                 salvataggio la settimana è una, e il ricalcolo di una settimana
                 diversa (quella la cui baseline è stata invalidata) è una
                 SECONDA chiamata, non un caso da infilare qui.

    FIRMA BATCH, come `scostamento_stime_sottotask` — una chiamata, due query,
    nessun N+1. Il motore vero processerà tutti i sottotask di un salvataggio in
    un colpo; chi ne vuole uno solo passa un dict di un elemento.

    OUTPUT — {sottotask_id: {...}}, una voce per ogni sottotask ESISTENTE:
      task_id      : il task padre. Lo restituisce questa funzione perché lo ha
                     già in mano: il chiamante deve aggregare le ore per task
                     (su Consuntivo.ore_dichiarate) e senza questo dovrebbe
                     rifare la stessa query.
      ore          : float, le ore derivate. Oppure **None = NON DERIVABILE**,
                     vedi sotto.
      baseline_pct : la percentuale da cui si è partiti (0 se prima dichiarazione)
      delta_pct    : Δ GREZZO, col segno. Un negativo resta visibile qui anche
                     se `ore` è già 0: è il sintomo, e va potuto leggere.
      ore_stimate  : la stima usata, per ricostruire il conto a posteriori.

    `ore = None` È IL SENTINELLA, E NON È 0.0 — la distinzione è il punto.
      - `ore = 0.0`  → derivato, e fa zero ore: nessun avanzamento (Δ=0), o
                       regressione clampata, o slider non mosso. È un numero.
      - `ore = None` → NON derivabile: il sottotask non ha `ore_stimate`, quindi
                       Δpct × NULL non è definito. Il chiamante deve SEGNALARLO
                       («sottotask non stimato, ore non derivate»), non sommare
                       zero in silenzio: chi ha dichiarato ha lavorato davvero, e
                       far sparire quelle ore senza dirlo è il modo peggiore di
                       gestire una stima che manca al PM, non a lui.
      Qui si diverge da `scostamento_stime_sottotask`, che il NULL lo tratta con
      `coalesce(..., 0.0)` — e giustamente: lì la domanda è «il piano quadra?» e
      0 è una risposta informativa («non stimato»). Qui la domanda è «quante ore
      ha prodotto questo avanzamento?», e 0 sarebbe una bugia.

    PRECEDENZA DEI CONTROLLI — `percentuale is None` viene PRIMA di
    `ore_stimate is None`. Su un pezzo su cui nessuno ha dichiarato avanzamento
    la stima mancante non è un problema di nessuno: segnalarla produrrebbe un
    avviso per ogni sottotask non stimato toccato di striscio dal salvataggio,
    cioè rumore che nasconde i pochi casi veri.

    CHIAVE ASSENTE dal risultato = sottotask inesistente (stessa convenzione di
    `scostamento_stime_sottotask`, dove la chiave manca quando non c'è niente da
    dire). Le route validano l'esistenza a monte, come fa `_task_o_404` in
    routes/sottotask.py; qui non si alza, si omette.

    NON FA — e non per dimenticanza: la validazione della MONOTONIA (dipende
    anche dalla dichiarazione SUCCESSIVA, è regola del data layer/route, non di
    un calcolo puro), il ricalcolo della settimana la cui baseline è stata
    invalidata, l'aggregazione per task, l'innesto in `salva_consuntivo`. Questa
    funzione calcola una fotografia, non gestisce il tempo.
    """
    from models import Sottotask, ConsuntivoSottotask

    if not avanzamenti:
        return {}

    sett = _lunedi(settimana)
    ids = list(avanzamenti)

    session = get_session()
    try:
        # 1) Anagrafica dei sottotask: task padre e stima. Una query.
        righe = (
            session.query(Sottotask.id, Sottotask.task_id, Sottotask.ore_stimate)
            .filter(Sottotask.id.in_(ids))
            .all()
        )
        anagrafica = {r.id: (r.task_id, r.ore_stimate) for r in righe}
        if not anagrafica:
            return {}

        # 2) Baseline: tutte le dichiarazioni non-NULL PRECEDENTI, in una query
        # sola, ridotte poi in Python. Non una query per sottotask (N+1), e non
        # una window function: il fallback SQLite di `data.py` non è un dialetto
        # su cui contare, e le righe in gioco sono poche — una per persona per
        # settimana, sulla vita di un sottotask.
        storiche = (
            session.query(
                ConsuntivoSottotask.sottotask_id,
                ConsuntivoSottotask.settimana,
                ConsuntivoSottotask.percentuale,
            )
            .filter(
                ConsuntivoSottotask.sottotask_id.in_(list(anagrafica)),
                ConsuntivoSottotask.settimana < sett,
                # Una riga con percentuale NULL non è una baseline: è qualcuno
                # che si è espresso sullo stato e non sull'avanzamento. Senza
                # questo filtro diventerebbe una baseline fantasma a 0 e
                # rideriverebbe da capo tutto l'avanzamento precedente.
                ConsuntivoSottotask.percentuale.isnot(None),
            )
            .all()
        )

        # Riduzione: per ogni sottotask la settimana più recente, e dentro
        # quella la percentuale più alta (vedi docstring).
        baseline = {}      # sottotask_id → (settimana, percentuale)
        for sid, sett_storica, pct in storiche:
            corrente = baseline.get(sid)
            if corrente is None or sett_storica > corrente[0]:
                baseline[sid] = (sett_storica, pct)
            elif sett_storica == corrente[0] and pct > corrente[1]:
                baseline[sid] = (sett_storica, pct)

        out = {}
        for sid in ids:
            if sid not in anagrafica:
                continue                      # inesistente: chiave omessa
            task_id, stima = anagrafica[sid]
            pct = avanzamenti[sid]
            base = baseline.get(sid, (None, 0))[1]

            # Slider fermo: nessuna derivazione, e la stima mancante non si
            # segnala (vedi PRECEDENZA DEI CONTROLLI).
            if pct is None:
                out[sid] = {
                    "task_id": task_id, "ore": 0.0, "baseline_pct": base,
                    "delta_pct": None, "ore_stimate": stima,
                }
                continue

            delta = pct - base

            if stima is None:
                out[sid] = {
                    "task_id": task_id, "ore": None, "baseline_pct": base,
                    "delta_pct": delta, "ore_stimate": None,
                }
                continue

            # Clamp sul Δ, non sulle ore: «l'avanzamento può tornare indietro,
            # le ore no». Con la monotonia imposta a monte non dovrebbe mai
            # scattare — se scatta, `delta_pct` resta negativo nel risultato ed
            # è il sintomo di una dichiarazione entrata da un'altra porta.
            ore = (max(delta, 0) / 100.0) * stima
            out[sid] = {
                "task_id": task_id,
                # round a 1 decimale: è la precisione di TUTTE le ore di questo
                # modulo (ore_settimanali_task, ore_dichiarate_settimana,
                # lista_fasi_progetto...). Serve anche a tagliare il rumore
                # float, che qui è tutt'altro che raro: un Δ del 10% su una
                # stima da 3h vale 0.30000000000000004 senza arrotondamento, e
                # le stime piccole sono la norma sui sottotask.
                "ore": round(ore, 1),
                "baseline_pct": base,
                "delta_pct": delta,
                "ore_stimate": stima,
            }
        return out
    finally:
        session.close()


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
        # Distribuzione uniforme: ore_pianificate (piano corrente) / durata.
        # Migrazione #3 passo 2 (#1): il carico usa il PIANO CORRENTE, non la
        # stima storica. Post-backfill pianificate == stimate → oracolo invariato.
        # weeks = max(1, ...) per task brevi (< 1 settimana).
        weeks = max(1, (t.data_fine - t.data_inizio).days / 7)
        ore += (t.ore_pianificate or 0) / weeks
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


def _lunedi(d=None):
    """Normalizza una data al lunedì della sua settimana ISO.

    Regola UNICA condivisa da lettura (task_settimana_dipendente) e scrittura
    (salva_consuntivo): la colonna `settimana` di Consuntivo / Presenza /
    Spesa contiene SEMPRE un lunedì. Se la scrittura ci mette un giorno
    qualsiasi (era `datetime.now()`), la UNIQUE task+dip+settimana non
    intercetta il doppione e la stessa settimana si sdoppia in righe diverse:
    è l'origine del bug duplicati.

    Accetta date, datetime, stringa ISO 'YYYY-MM-DD' o None (= oggi).
    Solleva ValueError se la stringa non è una data ISO valida.
    """
    if d is None:
        d = date.today()
    if isinstance(d, str):
        d = date.fromisoformat(d)      # ValueError se malformata
    if isinstance(d, datetime):
        d = d.date()
    return d - timedelta(days=d.weekday())


def task_settimana_dipendente(dipendente_id, settimana=None):
    """I task schedulati sul dipendente per una settimana, con le ore già
    consuntivate da LUI in QUELLA settimana attaccate sopra.

    Riusabile: alimenta sia GET /api/consuntivi/me sia la futura Home-utente
    («su cosa sto lavorando, come procedono i progetti»). La logica sta qui,
    non nella route, così un secondo endpoint la riusa senza duplicare la query.

    Parte dai Task assegnati (NON dai Consuntivi): il dipendente vede «cosa era
    previsto per lui quella settimana» anche se non ha ancora compilato
    (ore_consumate = 0 in quel caso, non lista vuota).

    Criterio di inclusione: PURAMENTE TEMPORALE — il task compare se la sua
    finestra data_inizio..data_fine interseca la settimana richiesta. Lo stato
    NON filtra (si esclude solo 'Annullato'): «schedulato» e «stato» sono assi
    indipendenti — un task può essere schedulato per questa settimana ed essere
    Bloccato, o schedulato per la scorsa e ancora In corso perché in ritardo.
    Il criterio precedente (stato IN 'In corso','Da iniziare') era
    settimana-cieco: guardando la settimana scorsa mostrava i task attivi
    OGGI, così un task chiuso venerdì spariva e le ore fatte su di esso
    diventavano indichiarabili.
    I task con date NULL restano inclusi (non si può dire che NON intersecano,
    e vanno comunque consuntivati). Assegnazione via Task.dipendente_id.

    Una query con joinedload(Task.progetto) per nome/tipologia progetto (niente
    N+1); una seconda query indicizzata prende i Consuntivi del dip/settimana e
    li attacca per task_id.

    Ritorna list[dict] ordinata per task_id:
      task_id, task_nome, progetto_id, progetto_nome, interna (bool),
      ore_iniziale (= ore_stimate congelata), ore_pianificate (totale del task),
      ore_pianificate_settimana (quota della settimana corrente: ore_pianificate
        spalmate sulla durata del task; None se date NULL, 0 se la finestra non
        tocca la settimana), ore_consumate (dichiarate dal dip in settimana),
      ore_rimanenti (residuo del task = ore_pianificate − consumato TOTALE del
        task su tutti i dipendenti/settimane, calcolato al volo), stato,
      in_ritardo (bool), nota (str|None: «a che punto sono», scritta dal dip in
        QUELLA settimana — è il round-trip di note_per_task in scrittura),
      dichiarato (bool: esiste una riga Consuntivo compilata di QUESTO dip su
        QUESTO task in QUELLA settimana),
      stato_dichiarato (str|None: lo stato che il dipendente ha dichiarato in
        QUELLA settimana; None se non si è espresso).
    `stato`, `dichiarato` e `stato_dichiarato` sono tre assi indipendenti: a che
    punto è il task oggi, se il dipendente ha compilato, e cosa ha dichiarato.
    Solo il terzo è attribuibile a lui — `stato` può essere stato scritto dal PM
    in Cantiere e non dice né chi né quando.

    `in_ritardo` NON è uno stato: è DERIVATO da data_fine e stato, ricalcolato
    a ogni lettura. Non è nella lista di ciò che il dipendente può dichiarare e
    non ha una colonna — il ritardo non si «dichiara», succede: la finestra del
    task si è chiusa e il task non è chiuso. Il frontend lo rende come
    segnalazione automatica accanto al task, non come opzione della tendina.
    """
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func, or_, and_

    lun = _lunedi(settimana)
    fine_sett = lun + timedelta(days=6)  # lun..dom, come /me e /settimana

    session = get_session()
    try:
        tasks = (
            session.query(Task)
            .options(joinedload(Task.progetto))
            .filter(
                Task.dipendente_id == dipendente_id,
                Task.stato != "Annullato",
                # intersezione finestra-task × settimana; date NULL incluse
                or_(
                    Task.data_inizio.is_(None),
                    Task.data_fine.is_(None),
                    and_(Task.data_inizio <= fine_sett, Task.data_fine >= lun),
                ),
            )
            .order_by(Task.id)
            .all()
        )
        task_ids = [t.id for t in tasks]

        # Ore dichiarate e nota scritta da QUESTO dip in QUESTA settimana, per
        # task_id. (UNIQUE task+dip+settimana → di norma una riga per task;
        # sommiamo comunque per robustezza.)
        cons_rows = (
            session.query(Consuntivo.task_id, Consuntivo.ore_dichiarate,
                          Consuntivo.nota, Consuntivo.compilato,
                          Consuntivo.stato_dichiarato)
            .filter(
                Consuntivo.dipendente_id == dipendente_id,
                Consuntivo.settimana >= lun,
                Consuntivo.settimana <= fine_sett,
            )
            .all()
        )
        # Consumato TOTALE per task (tutti i dipendenti, tutte le settimane):
        # serve per ore_rimanenti. La colonna Task.ore_rimanenti è denormalizzata
        # e stale (il seed non la aggiorna dopo i consuntivi) → la ricalcolo al
        # volo, stesso principio del serializzatore SAL su ore_consumate.
        tot_rows = []
        if task_ids:
            tot_rows = (
                session.query(Consuntivo.task_id, func.sum(Consuntivo.ore_dichiarate))
                .filter(Consuntivo.task_id.in_(task_ids))
                .group_by(Consuntivo.task_id)
                .all()
            )
    finally:
        session.close()

    consumate_per_task = {}
    note_per_task = {}
    dichiarati = set()
    stato_dichiarato_per_task = {}
    for tid, ore, nota, compilato, stato_dich in cons_rows:
        consumate_per_task[tid] = consumate_per_task.get(tid, 0.0) + float(ore or 0)
        if compilato:
            dichiarati.add(tid)
        # Come la nota: non si somma, e la prima valorizzata vince.
        if stato_dich and not stato_dichiarato_per_task.get(tid):
            stato_dichiarato_per_task[tid] = stato_dich
        # La nota NON si somma: è testo. Se per qualche ragione ci fossero due
        # righe nel range, vince la prima non vuota — meglio mostrare una nota
        # vecchia che perderla e costringere a riscriverla.
        if nota and not note_per_task.get(tid):
            note_per_task[tid] = nota

    consumato_totale_task = {tid: float(s or 0) for tid, s in tot_rows}

    def _quota_settimana(t):
        """Quota di ore per la settimana corrente: ore_pianificate spalmate
        uniformemente sulle settimane di durata del task. Riusa la stessa logica
        di carico_settimanale_dipendente, così le due viste restano coerenti.
        Casi limite: date NULL → None; finestra fuori settimana → 0; durata < 1
        settimana → tutte le ore nella settimana (weeks = max(1, ...))."""
        if t.data_inizio is None or t.data_fine is None:
            return None
        if t.data_inizio > fine_sett or t.data_fine < lun:
            return 0.0
        weeks = max(1, (t.data_fine - t.data_inizio).days / 7)
        return round((t.ore_pianificate or 0) / weeks, 1)

    oggi = date.today()

    def _in_ritardo(t):
        """Finestra chiusa (data_fine passata) e task non chiuso.
        Il confronto è con OGGI, non con la settimana visualizzata: un task
        scaduto resta in ritardo anche riaprendo la settimana scorsa.
        Date NULL → non si può dire che sia scaduto, quindi False.
        'Sospeso' è escluso con 'Completato': è una decisione del PM, non un
        ritardo del dipendente — segnalarlo accuserebbe del contrario."""
        if t.data_fine is None:
            return False
        return t.data_fine < oggi and t.stato not in ("Completato", "Sospeso")

    out = []
    for t in tasks:
        prog = t.progetto
        pianificate = float(t.ore_pianificate or 0)
        out.append({
            "task_id": t.id,
            "task_nome": t.nome,
            "progetto_id": t.progetto_id,
            "progetto_nome": prog.nome if prog else "?",
            # interna = tipologia progetto, NON id P010 (vedi economia: il
            # filtro per id era un hack morto). Per il badge blu/grigio.
            "interna": bool(prog and prog.tipologia == "interna"),
            "ore_iniziale": int(t.ore_stimate or 0),
            "ore_pianificate": pianificate,             # totale del task (contesto)
            "ore_pianificate_settimana": _quota_settimana(t),  # quota settimana
            "ore_consumate": round(consumate_per_task.get(t.id, 0.0), 1),
            # residuo del TASK (non del singolo/settimana): piano − consumato tot.
            "ore_rimanenti": round(pianificate - consumato_totale_task.get(t.id, 0.0), 1),
            "stato": t.stato,
            "in_ritardo": _in_ritardo(t),
            # «A che punto sono», come l'ha scritta il dipendente in QUESTA
            # settimana (None se non ha scritto nulla). Serve a riaprire una
            # settimana già compilata senza perdere il testo: su un task
            # Bloccato la nota è obbligatoria in scrittura, quindi senza
            # rileggerla un ri-salvataggio verrebbe rifiutato con 400.
            "nota": note_per_task.get(t.id),
            # Il dipendente ha dichiarato qualcosa su questo task IN QUESTA
            # settimana? È un asse diverso da `stato`: `stato` è Task.stato,
            # che esiste da quando il PM ha creato il task e vale "Da iniziare"
            # o "In corso" anche se nessuno ha mai compilato nulla. Senza
            # questo flag la pagina non può distinguere «non dichiarato» da
            # «dichiarato In corso», e il salvataggio non lascia traccia
            # visibile. Le righe del seed hanno compilato=True e risultano
            # dichiarate: è corretto, sono consuntivi a tutti gli effetti.
            "dichiarato": t.id in dichiarati,
            # CHE COSA ha dichiarato il dipendente in questa settimana (None se
            # non si è espresso). Terzo asse, distinto dagli altri due: `stato`
            # è il task oggi, `dichiarato` è se ha compilato, questo è la sua
            # dichiarazione. Solo questo può essere attribuito a lui.
            "stato_dichiarato": stato_dichiarato_per_task.get(t.id),
        })
    return out


def lunedi_settimana(d=None):
    """Alias PUBBLICO di `_lunedi`. Non è una seconda regola: delega, punto.

    Esiste solo per attraversare il confine di `data.py`, che fa
    `from data_db_impl import *` — e `import *` non porta con sé i nomi che
    iniziano con underscore. Le route devono poter normalizzare la settimana
    richiesta (query param / body) con la STESSA regola usata qui dentro,
    invece di ricalcolare il lunedì per conto loro: è esattamente la
    duplicazione che ha generato il bug dei duplicati.
    """
    return _lunedi(d)


def note_consuntivi_settimana(dipendente_id, settimana=None):
    """{task_id: nota} delle note NON VUOTE già scritte dal dipendente in quella
    settimana. I task senza nota non compaiono nel dict.

    Serve alla validazione «Bloccato richiede una nota», che deve guardare ciò
    che ESISTE e non solo ciò che è arrivato nella richiesta: il form manda solo
    le note MODIFICATE, quindi ridichiarare Bloccato senza ritoccare la nota è
    il caso normale, non un errore. La lettura sta qui e non nella route perché
    è una domanda sul DB, e le route non fanno SQL.

    Query indicizzata su (dipendente_id, settimana), le stesse colonne del resto
    del modulo; il range lun..dom è quello di /me e /settimana.
    """
    lun = _lunedi(settimana)
    fine_sett = lun + timedelta(days=6)

    session = get_session()
    try:
        rows = (
            session.query(Consuntivo.task_id, Consuntivo.nota)
            .filter(
                Consuntivo.dipendente_id == dipendente_id,
                Consuntivo.settimana >= lun,
                Consuntivo.settimana <= fine_sett,
                Consuntivo.nota.isnot(None),
            )
            .all()
        )
    finally:
        session.close()

    # Lo strip finale: in DB una nota vuota è NULL (vedi _nota_task), ma righe
    # scritte da altri percorsi potrebbero portare spazi — «vuota» resta vuota.
    return {tid: nota for tid, nota in rows if (nota or "").strip()}


_MESI_ABBR = ["gen", "feb", "mar", "apr", "mag", "giu",
              "lug", "ago", "set", "ott", "nov", "dic"]


def _etichetta_intervallo(lun):
    """'13–19 lug' se la settimana sta in un mese solo, '29 giu – 5 lug' se
    scavalca. Solo presentazione: il frontend mostra la stringa così com'è."""
    dom = lun + timedelta(days=6)
    if lun.month == dom.month:
        return f"{lun.day}–{dom.day} {_MESI_ABBR[dom.month - 1]}"
    return (f"{lun.day} {_MESI_ABBR[lun.month - 1]} – "
            f"{dom.day} {_MESI_ABBR[dom.month - 1]}")


def ore_dichiarate_settimana(dipendente_id, settimana=None):
    """Ore COPERTE dal dipendente in una settimana (float): ore dichiarate sui
    task + ore di assenza. È l'input del criterio di completezza.

    Le assenze contano. Chi è in ferie tutta la settimana HA compilato
    correttamente — ha dichiarato l'assenza. Se contassimo solo i Consuntivi
    resterebbe a 0 ore, quindi «incompleto», e il sistema gli chiederebbe in
    eterno di fare una cosa che ha già fatto.

    Indipendente dai task: somma TUTTI i Consuntivi del dip in quella
    settimana, anche quelli su task che non intersecano più la finestra.
    `task_settimana_dipendente` invece somma solo i task che vede — va bene
    per il totale mostrato accanto alla lista, non per decidere se una
    settimana è «compilata» (un task chiuso e uscito dalla finestra
    renderebbe la settimana incompleta per sempre).

    Range lun..dom, non `== lunedì`: rete di sicurezza per righe storiche o
    scritte da altre fonti con una data non normalizzata. Sommarle è il
    comportamento corretto in quel caso.
    """
    from sqlalchemy import func
    from models import PresenzaSettimanale

    lun = _lunedi(settimana)
    dom = lun + timedelta(days=6)
    session = get_session()
    try:
        ore_task = (
            session.query(func.sum(Consuntivo.ore_dichiarate))
            .filter(
                Consuntivo.dipendente_id == dipendente_id,
                Consuntivo.settimana >= lun,
                Consuntivo.settimana <= dom,
            )
            .scalar()
        )
        # Due query invece di un join: le presenze stanno su una tabella
        # separata con cardinalità 1-per-settimana, un join produrrebbe
        # righe moltiplicate e una somma gonfiata.
        ore_assenza = (
            session.query(func.sum(PresenzaSettimanale.ore_assenza))
            .filter(
                PresenzaSettimanale.dipendente_id == dipendente_id,
                PresenzaSettimanale.settimana >= lun,
                PresenzaSettimanale.settimana <= dom,
            )
            .scalar()
        )
    finally:
        session.close()
    return round(float(ore_task or 0) + float(ore_assenza or 0), 1)


def settimane_selezionabili(dipendente_id):
    """Le settimane che il dipendente può aprire in consuntivazione: la
    corrente e la precedente. Nient'altro — non si compila in anticipo, e il
    recupero all'indietro si ferma a una settimana.

    Ogni voce: {lunedi (ISO), etichetta, compilabile}.

    `compilabile` sulla settimana corrente è sempre True. Sulla precedente è
    True solo se INCOMPLETA: il recupero serve a chi non ha compilato, non a
    rivedere ciò che è chiuso. Criterio di completezza: ore dichiarate >= ore
    contrattuali del dipendente.

    Nota: la voce resta nella lista anche quando `compilabile` è False — il
    frontend la mostra disabilitata («già compilata») invece di farla sparire,
    così l'utente capisce perché non può tornarci.
    """
    corrente = _lunedi()
    precedente = corrente - timedelta(days=7)

    ore_sett = int(get_dipendente(dipendente_id).get("ore_sett") or 0)
    dichiarate_prec = ore_dichiarate_settimana(dipendente_id, precedente)

    return [
        {
            "lunedi": corrente.isoformat(),
            "etichetta": "Questa settimana",
            "compilabile": True,
        },
        {
            "lunedi": precedente.isoformat(),
            "etichetta": f"Settimana scorsa ({_etichetta_intervallo(precedente)})",
            "compilabile": dichiarate_prec < ore_sett,
        },
    ]


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
        - `stato` è "In corso" e `dipendente_id` è vuoto (Step 4, 06/08/2026:
          un task non entra in lavorazione senza assegnatario);
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
        6. session.commit() → INSERT cumulativo, transazione singola.

      Il passo «eventuale assegnazione dipendente» che stava fra il 5 e il 6 è
      stato rimosso (Step 4, 06/08/2026): l'assegnatario è già su
      `Task.dipendente_id`, unica sorgente. Vedi il commento a fine funzione.
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

    # Step 4 sottotask (06/08/2026): un task NON entra in lavorazione senza
    # assegnatario. `stato` è client-settable (NuovoTask.stato, DTO dei router),
    # quindi un task può NASCERE "In corso" saltando del tutto `modifica_task`:
    # senza questo check la regola avrebbe una porta di servizio aperta.
    #
    # L'obbligo scatta SOLO su "In corso" e SOLO qui e nei due router del
    # Cantiere. Non sta in `modifica_task` di proposito: quella funzione è
    # chiamata anche dalla propagazione di `salva_consuntivo`, dove a scrivere
    # è il DIPENDENTE che dichiara «ci sto lavorando». Bloccare lì punirebbe
    # chi il lavoro lo sta facendo per una lacuna di pianificazione del PM.
    # L'obbligo è di chi AVVIA il task, non di chi lo consuntiva.
    #
    # `not dipendente_id` copre insieme None e "" — il default del parametro è
    # la stringa vuota e i router passano `nt.dipendente_id` grezzo (DTO
    # `NuovoTask.dipendente_id: str = ""`): un `is None` mancherebbe il caso
    # che si verifica davvero.
    if stato == "In corso" and not dipendente_id:
        session.close()
        raise ValueError(
            f"Il task '{nome}' non può nascere in stato 'In corso' senza "
            f"assegnatario: un task che entra in lavorazione deve avere un "
            f"responsabile. Assegna un dipendente, oppure crealo in "
            f"'Da iniziare' e avvialo dopo averlo assegnato."
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

    # Step 4 sottotask (06/08/2026): qui si scriveva anche una riga
    # `Assegnazione` che duplicava `Task.dipendente_id`, appena impostato sopra.
    # Rimossa: l'assegnazione ha UNA sola sorgente, la colonna sul task. Il
    # mirror non veniva mantenuto da nessun'altra parte (`modifica_task`
    # aggiorna solo la colonna), quindi era destinato a divergere appena il PM
    # riassegnava un task dal Cantiere. La tabella resta in schema con le sue
    # righe storiche, ma nessuno la scrive né la legge più — vedi
    # `progetti_attivi_visibili`, che era il suo unico lettore.
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

def _nota_task(testo):
    """Normalizza la nota «a che punto sono»: stringa vuota o soli spazi → None.

    In DB la nota assente è NULL, non "": così `nota IS NOT NULL` significa
    davvero «il dipendente ha scritto qualcosa» e non serve ricordarsi di
    testare anche la stringa vuota ogni volta che la si legge.
    """
    testo = (testo or "").strip()
    return testo or None


def salva_consuntivo(dipendente_id, settimana, ore_per_task, stati_per_task,
                     giorni_sede=None, giorni_remoto=None,
                     ore_assenza=None, tipo_assenza=None, nota_assenza=None,
                     spese_lista=None, note_per_task=None):
    """
    Salva il consuntivo settimanale completo di un dipendente.

    I task da scrivere sono l'UNIONE delle chiavi di ore_per_task,
    stati_per_task e note_per_task: un task entra nel salvataggio se ha almeno
    uno dei tre, non solo se ha le ore.

    ore_per_task: dict {task_id: ore}. Chiave assente = ore non dichiarate,
                 che NON è 0: sulla riga esistente `ore_dichiarate` resta com'è
                 (dichiarare uno stato non azzera le ore già inserite), sulla
                 riga nuova si parte da 0.
    stati_per_task: dict {task_id: stato} — SOLO stati dichiarabili
                 (models.STATI_DICHIARABILI). La validazione sta a monte, nel
                 DTO della route: qui si assume già filtrato.
    note_per_task: dict {task_id: «a che punto sono»} → Consuntivo.nota.
                 None = non pervenuto, non toccare le note esistenti (stessa
                 convenzione di spese_lista). Chiave presente con stringa
                 vuota = cancella la nota; chiave assente = lascia com'è.
    spese_lista: None = non pervenuto, non toccare le spese esistenti.
                 [] o lista = stato COMPLETO della settimana, sostituisce.
    giorni_sede, giorni_remoto, ore_assenza, tipo_assenza, nota_assenza:
                 None = non pervenuto. Se lo sono TUTTI, PresenzaSettimanale
                 non viene nemmeno interrogata; se lo sono solo alcuni, la riga
                 esistente è aggiornata SUI SOLI campi pervenuti (caso misto:
                 `ore_assenza` senza i giorni non deve riportare i giorni a
                 zero).

    LO STATO È IL CAMPO PRIMARIO. Le ore sono secondarie: un task può arrivare
    con 0 ore e stato "Completato" ed è una compilazione valida. Per questo lo
    stato dichiarato NON si ferma sul Consuntivo — arriva su Task.stato, che è
    ciò che il PM legge nel Cantiere e ciò che decide se il task ricompare in
    /me la settimana dopo. Senza propagazione, marcare Completato non aveva
    alcun effetto osservabile.

    La propagazione passa da `modifica_task` — la stessa funzione che usa il
    Cantiere — e non da una `setattr` diretta: un solo punto di scrittura su
    Task.stato, così quando ci si appenderà logica (audit, cascata,
    notifiche) varrà per entrambe le porte d'ingresso.

    La `settimana` viene normalizzata al lunedì con `_lunedi` — stessa regola
    della lettura, e qui è la riga che ripara il bug dei duplicati. Prima
    arrivava `datetime.now()` dalla route, cioè il giorno della compilazione:
    la UNIQUE (task_id, dipendente_id, settimana) non riconosceva il doppione,
    e ricompilare martedì dopo aver compilato lunedì inseriva una riga NUOVA
    invece di aggiornare quella esistente. In lettura le due righe cadono
    entrambe nel range lun..dom e si sommano: 6h corrette in 8h diventavano
    14h. Stesso meccanismo su PresenzaSettimanale (UNIQUE dip+settimana).
    """
    from models import PresenzaSettimanale, Spesa

    session = get_session()
    settimana_date = _lunedi(settimana)

    # 1) Salva/aggiorna ore, stato e nota per ogni task.
    # Si itera sull'UNIONE delle chiavi dei tre dizionari, non su ore_per_task:
    # le ore non sono più il campo che decide se un task è stato compilato. Il
    # campo primario è lo stato — «a che punto sono», non «quanto ho lavorato»
    # — e le ore sono facoltative. Ciclando su ore_per_task, una compilazione
    # di soli stati (caso ormai normale) non entrava mai nel ciclo: la funzione
    # tornava True senza aver scritto una riga. Residuo di quando le ore erano
    # obbligatorie.
    # dict.fromkeys e non set(): preserva l'ordine di arrivo, così le scritture
    # restano deterministiche e i test riproducibili.
    task_toccati = dict.fromkeys(
        list(ore_per_task) + list(stati_per_task) + list(note_per_task or {})
    )
    stati_dichiarati = {}   # task_id → stato, da propagare dopo il commit
    for task_id in task_toccati:
        # `ore is None` = ore non dichiarate: diverso da 0 («non ci ho
        # lavorato»). Sulla riga esistente le ore non si toccano, sulla nuova
        # si parte da 0.
        ore = ore_per_task.get(task_id)
        stato = stati_per_task.get(task_id)
        # La nota conta come pervenuta anche se è la stringa vuota: cancellare
        # una nota è un ATTO del dipendente, non un non-evento, e va scritto.
        nota_pervenuta = note_per_task is not None and task_id in note_per_task
        # Salta solo i task che non portano NIENTE: né stato, né nota, né ore.
        # `not ore` copre insieme None (ore non dichiarate) e 0 («non ci ho
        # lavorato»): l'intenzione non dipende più dal fatto accidentale che
        # `None == 0` sia False, che è ciò che teneva in piedi il caso
        # «solo nota» — un `or 0` aggiunto a monte lo avrebbe rotto in
        # silenzio, facendo sparire le note senza errori.
        # La guardia serve ancora: il form manda a 0 anche i task su cui non
        # si è lavorato, e senza di essa ogni salvataggio creerebbe una riga
        # vuota per ciascuno.
        if not stato and not nota_pervenuta and not ore:
            continue

        # motivo_fermo è un flag, non un archivio: va RIALLINEATO a ogni
        # salvataggio, non solo popolato. Prima il ramo `else` non esisteva e
        # un task sbloccato la settimana dopo restava marcato «bloccato» per
        # sempre. Il perché del blocco lo scrive il dipendente in `nota`.
        motivo = "Segnalato come bloccato dal dipendente" if stato == "Bloccato" else None

        existing = session.query(Consuntivo).filter(
            Consuntivo.task_id == task_id,
            Consuntivo.dipendente_id == dipendente_id,
            Consuntivo.settimana == settimana_date,
        ).first()

        if existing:
            if ore is not None:
                existing.ore_dichiarate = ore
            existing.compilato = True
            existing.data_compilazione = datetime.utcnow()
            existing.motivo_fermo = motivo
            # Lo stato dichiarato resta anche sulla riga della settimana, non
            # solo su Task.stato: quest'ultimo è a sovrascrittura e non dice né
            # chi né quando. `stato` assente = non pervenuto, la colonna non si
            # tocca (stessa convenzione di note e presenze): un salvataggio di
            # sole ore non cancella la dichiarazione fatta prima.
            if stato:
                existing.stato_dichiarato = stato
            if note_per_task is not None and task_id in note_per_task:
                existing.nota = _nota_task(note_per_task[task_id])
        else:
            session.add(Consuntivo(
                task_id=task_id,
                dipendente_id=dipendente_id,
                settimana=settimana_date,
                ore_dichiarate=ore if ore is not None else 0,
                compilato=True,
                data_compilazione=datetime.utcnow(),
                motivo_fermo=motivo,
                nota=_nota_task((note_per_task or {}).get(task_id)),
                # None se il task non è in stati_per_task: la riga nasce da
                # sole ore o sola nota e nessuno si è espresso sullo stato.
                stato_dichiarato=stato,
            ))

        if stato:
            stati_dichiarati[task_id] = stato

    # 2) Presenze settimanali (smart working + assenze) — SOLO SE PERVENUTE.
    # Ogni campo è aggiornato singolarmente e solo se non è None: il blocco non
    # riscrive mai i campi che il chiamante non ha nominato. Stessa convenzione
    # di `spese_lista` e `note_per_task`: None = «non gestisco questo campo».
    # Prima erano parametri con default 0/0/0/""/"" scritti incondizionatamente,
    # e i default sono nati quando il body del form portava sempre tutto. Con un
    # client che manda solo uno stato (le presenze le ha compilate ieri, in
    # un'altra schermata) quei default tornavano in DB come dati veri: 1 giorno
    # in sede e 4 da remoto diventavano 3 e 2 al primo salvataggio di una nota.
    # Un default non è un dato dichiarato — e sovrascriverlo in silenzio è
    # peggio che non scriverlo.
    presenze_pervenute = {
        campo: valore
        for campo, valore in (
            ("giorni_sede", giorni_sede),
            ("giorni_remoto", giorni_remoto),
            ("ore_assenza", ore_assenza),
            ("tipo_assenza", tipo_assenza),
            ("nota_assenza", nota_assenza),
        )
        if valore is not None
    }

    if presenze_pervenute:
        existing_pres = session.query(PresenzaSettimanale).filter(
            PresenzaSettimanale.dipendente_id == dipendente_id,
            PresenzaSettimanale.settimana == settimana_date,
        ).first()

        if existing_pres is None:
            # Riga nuova: i campi NON pervenuti restano al default di colonna
            # (0), non a un valore inventato qui.
            existing_pres = PresenzaSettimanale(
                dipendente_id=dipendente_id,
                settimana=settimana_date,
            )
            session.add(existing_pres)

        for campo, valore in presenze_pervenute.items():
            setattr(existing_pres, campo, valore)

        # Coerenza dell'assenza: se le ore di assenza sono state dichiarate a
        # zero, l'assenza non c'è e tipo/nota non hanno più un referente —
        # vanno azzerati anche se sono arrivati valorizzati. Vale solo quando
        # `ore_assenza` è pervenuto: senza, non sappiamo nulla dell'assenza e
        # non tocchiamo ciò che c'è già.
        if ore_assenza is not None and ore_assenza <= 0:
            existing_pres.tipo_assenza = None
            existing_pres.nota_assenza = None

    # 3) Salva spese — SOSTITUZIONE, non accodamento.
    # Il form manda lo stato completo delle spese della settimana, non righe
    # incrementali: non c'è modo di dire «questa riga è nuova» o «questa l'ho
    # cancellata». Prima erano `session.add()` incondizionati senza lookup, e
    # Spesa non ha UNIQUE a proteggere: ogni ri-salvataggio re-inseriva tutte
    # le spese del form, moltiplicando i rimborsi a ogni click su «Invia».
    # Cancella-e-riscrivi è l'unica semantica coerente con un form di stato.
    # `spese_lista is None` = campo non pervenuto (chiamante che non gestisce
    # le spese) → non toccare nulla. `[]` = «questa settimana nessuna spesa»
    # → svuota davvero.
    if spese_lista is not None:
        session.query(Spesa).filter(
            Spesa.dipendente_id == dipendente_id,
            Spesa.settimana == settimana_date,
        ).delete(synchronize_session=False)

        for spesa in spese_lista:
            if spesa.get("importo", 0) > 0:
                session.add(Spesa(
                    dipendente_id=dipendente_id,
                    settimana=settimana_date,
                    descrizione=spesa.get("descrizione", ""),
                    importo=spesa["importo"],
                    categoria=spesa.get("categoria", ""),
                ))

    # 4) Legge lo stato ATTUALE dei task dichiarati (serve al passo 5, ma la
    # sessione è ancora aperta: una query in più invece di una sessione in più).
    stati_correnti = {}
    if stati_dichiarati:
        stati_correnti = dict(
            session.query(Task.id, Task.stato)
            .filter(Task.id.in_(list(stati_dichiarati)))
            .all()
        )

    session.commit()
    session.close()

    # 5) PROPAGAZIONE: lo stato dichiarato arriva su Task.stato.
    # Fuori dalla sessione del consuntivo e DOPO il commit, di proposito:
    # `modifica_task` apre la propria sessione (è la porta del Cantiere) e le
    # ore restano salvate anche se un task nel frattempo è sparito.
    for task_id, stato in stati_dichiarati.items():
        corrente = stati_correnti.get(task_id)
        if corrente is None or corrente == stato:
            continue  # task inesistente, o già in quello stato: niente da fare
        if corrente in ("Sospeso", "Annullato"):
            # Decisioni di pianificazione del PM. Il form del dipendente non le
            # mostra e non può rappresentarle: se propagassimo, un "In corso"
            # di default sovrascriverebbe in silenzio una sospensione decisa
            # altrove. Chi dichiara non può disfare ciò che non vede.
            continue
        modifica_task(task_id, stato=stato)

    return True

# ══════════════════════════════════════════════════════════════════════
# SAL — snapshot storico del GANTT (DESIGN_SAL.md)
# ══════════════════════════════════════════════════════════════════════

def _iso(d):
    """date/datetime → stringa ISO, None → None."""
    return d.isoformat() if d is not None else None


def _nome_dip(session, did):
    """Nome del dipendente per id, None se assente. Usa la sessione data."""
    if not did:
        return None
    row = session.query(Dipendente.nome).filter(Dipendente.id == did).first()
    return row[0] if row else None


def _serializza_stato_progetto(pid):
    """Serializza lo stato completo del progetto nel formato SAL concordato.

    Formato (DESIGN_SAL, confermato 26/06/2026):
      {schema_version, progetto:{...}, fasi:[{..., task:[...]}]}
    - nomi denormalizzati (pm, dipendente, azienda) → snapshot autocontenuto;
    - le tre ore sui task (stimate/pianificate/consumate) + ore di fase
      (vendute/pianificate/consumate);
    - ore_consumate calcolata QUI da SUM(Consuntivo.ore_dichiarate), NON dalla
      colonna denormalizzata (stale): rende la foto veritiera. Fase = somma dei
      consumi dei suoi task (coerenza fase↔task per costruzione).
    Solleva ValueError se il progetto non esiste.
    """
    from sqlalchemy import func
    from models import Fase, Azienda, DipendenzaTask

    session = get_session()
    try:
        p = session.query(Progetto).filter(Progetto.id == pid).first()
        if p is None:
            raise ValueError(f"Progetto '{pid}' non trovato")

        azienda_nome = None
        if p.azienda_id is not None:
            az = session.query(Azienda.nome).filter(Azienda.id == p.azienda_id).first()
            azienda_nome = az[0] if az else None

        progetto = {
            "id": p.id, "nome": p.nome, "cliente": p.cliente,
            "stato": p.stato, "tipologia": p.tipologia,
            "priorita": p.priorita, "ritardabilita": p.ritardabilita,
            "data_inizio": _iso(p.data_inizio), "data_fine": _iso(p.data_fine),
            "fase_corrente": p.fase_corrente, "sede": p.sede,
            "pm_id": p.pm_id, "pm_nome": _nome_dip(session, p.pm_id),
            "azienda_id": p.azienda_id, "azienda_nome": azienda_nome, "area": p.area,
            "scadenza_bando": _iso(p.scadenza_bando),
            # NB: i campi ECONOMICI (budget_ore, valore_contratto, giornate_vendute)
            # NON stanno nel SAL: il SAL fotografa SOLO la struttura del GANTT.
            # L'economia ha il suo archivio separato (Bollettino economico).
            # narrativa per IA-Archivio (il "perché")
            "descrizione": p.descrizione, "motivo_sospensione": p.motivo_sospensione,
            "lezioni_apprese": p.lezioni_apprese,
        }

        # ore_consumate reali: SUM(Consuntivo.ore_dichiarate) per task del progetto.
        cons_per_task = dict(
            session.query(
                Consuntivo.task_id,
                func.coalesce(func.sum(Consuntivo.ore_dichiarate), 0.0),
            )
            .join(Task, Consuntivo.task_id == Task.id)
            .filter(Task.progetto_id == pid)
            .group_by(Consuntivo.task_id)
            .all()
        )

        fasi = (
            session.query(Fase)
            .filter(Fase.progetto_id == pid)
            .order_by(Fase.ordine)
            .all()
        )
        fasi_out = []
        for f in fasi:
            tasks = (
                session.query(Task)
                .filter(Task.fase_id == f.id)
                .order_by(Task.ordine, Task.id)
                .all()
            )
            task_out = []
            fase_consumate = 0.0
            for t in tasks:
                t_cons = float(cons_per_task.get(t.id, 0.0))
                fase_consumate += t_cons
                deps = (
                    session.query(DipendenzaTask)
                    .filter(DipendenzaTask.task_successore_id == t.id)
                    .all()
                )
                task_out.append({
                    "id": t.id, "nome": t.nome, "stato": t.stato,
                    "data_inizio": _iso(t.data_inizio), "data_fine": _iso(t.data_fine),
                    "ore_stimate": t.ore_stimate,
                    "ore_pianificate": t.ore_pianificate,
                    "ore_consumate": t_cons,
                    "profilo_richiesto": t.profilo_richiesto,
                    "dipendente_id": t.dipendente_id,
                    "dipendente_nome": _nome_dip(session, t.dipendente_id),
                    "motivo_blocco": t.motivo_blocco, "note": t.note,
                    "dipendenze": [
                        {"task_predecessore_id": d.task_predecessore_id,
                         "tipo_dipendenza": d.tipo_dipendenza}
                        for d in deps
                    ],
                })
            fasi_out.append({
                "id": f.id, "nome": f.nome, "ordine": f.ordine,
                "data_inizio": _iso(f.data_inizio), "data_fine": _iso(f.data_fine),
                "stato": f.stato,
                "ore_vendute": f.ore_vendute, "ore_pianificate": f.ore_pianificate,
                "ore_consumate": round(fase_consumate, 1),
                "task": task_out,
            })

        # schema_version 2: rimossi i campi economici dal blocco progetto
        # (SAL puro strutturale; economia → Bollettino economico).
        return {"schema_version": 2, "progetto": progetto, "fasi": fasi_out}
    finally:
        session.close()


def get_progetto_meta(pid):
    """Metadati minimi per autorizzazione/esistenza: {id, nome, pm_id} o None."""
    session = get_session()
    try:
        p = session.query(Progetto.id, Progetto.nome, Progetto.pm_id).filter(
            Progetto.id == pid
        ).first()
        if p is None:
            return None
        return {"id": p[0], "nome": p[1], "pm_id": p[2]}
    finally:
        session.close()


def crea_snapshot(progetto_id, consolidato_da=None, nota=None):
    """Crea uno snapshot SAL serializzando lo stato corrente del progetto.

    Ritorna i metadati dello snapshot creato (non l'intero JSON).
    Solleva ValueError se il progetto non esiste (via serializzatore).
    """
    from models import SalSnapshot

    stato = _serializza_stato_progetto(progetto_id)  # ValueError se inesistente

    session = get_session()
    try:
        snap = SalSnapshot(
            progetto_id=progetto_id,
            consolidato_da=consolidato_da,
            nota=nota,
            stato=stato,
        )
        session.add(snap)
        session.commit()
        session.refresh(snap)  # per data_snapshot (server_default now())
        return {
            "id": snap.id,
            "progetto_id": snap.progetto_id,
            "data_snapshot": _iso(snap.data_snapshot),
            "consolidato_da": snap.consolidato_da,
            "nota": snap.nota,
        }
    finally:
        session.close()


def lista_snapshot_progetto(pid):
    """Storico SINTETICO degli snapshot di un progetto (NO JSON stato).

    Ritorna lista di {id, data_snapshot, consolidato_da, consolidato_da_nome,
    nota} ordinata per data desc (il più recente prima). Il JSON `stato`
    completo si legge solo nel dettaglio (get_snapshot).
    """
    from models import SalSnapshot
    session = get_session()
    try:
        rows = (
            session.query(
                SalSnapshot.id, SalSnapshot.data_snapshot,
                SalSnapshot.consolidato_da, SalSnapshot.nota,
            )
            .filter(SalSnapshot.progetto_id == pid)
            .order_by(SalSnapshot.data_snapshot.desc(), SalSnapshot.id.desc())
            .all()
        )
        return [{
            "id": r[0],
            "data_snapshot": _iso(r[1]),
            "consolidato_da": r[2],
            "consolidato_da_nome": _nome_dip(session, r[2]),
            "nota": r[3],
        } for r in rows]
    finally:
        session.close()


def get_snapshot_progetto_id(snap_id):
    """progetto_id di uno snapshot (per l'auth a monte), None se inesistente."""
    from models import SalSnapshot
    session = get_session()
    try:
        r = session.query(SalSnapshot.progetto_id).filter(
            SalSnapshot.id == snap_id
        ).first()
        return r[0] if r else None
    finally:
        session.close()


def get_snapshot(snap_id):
    """Snapshot COMPLETO (incluso JSON `stato`) o None se inesistente."""
    from models import SalSnapshot
    session = get_session()
    try:
        s = session.query(SalSnapshot).filter(SalSnapshot.id == snap_id).first()
        if s is None:
            return None
        return {
            "id": s.id,
            "progetto_id": s.progetto_id,
            "data_snapshot": _iso(s.data_snapshot),
            "consolidato_da": s.consolidato_da,
            "consolidato_da_nome": _nome_dip(session, s.consolidato_da),
            "nota": s.nota,
            "stato": s.stato,
        }
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════════
# ECONOMIA — marginalità per progetto + erosione + aggregato per azienda
# ══════════════════════════════════════════════════════════════════════

def _pct(margine, valore):
    """margine/valore in %, 0 se valore non positivo."""
    return round(margine / valore * 100, 1) if valore and valore > 0 else 0.0


def margini_economia():
    """Marginalità economica (versione B — erosione da sovraccarico).

    Solo progetti COMMERCIALI/BANDI: gli interni (tipologia 'interna') sono
    esclusi per TIPOLOGIA (non per id: il vecchio filtro `id != 'P010'` era un
    hack morto che, dopo il redesign seed, non escludeva più gli interni e per
    giunta tagliava fuori il nuovo P010/Maida).

    Per ogni progetto, tre margini = valore_contratto − costo su tre basi-ore:
      - VENDUTO   (contratto): costo da Fase.ore_vendute ripartite sui task in
        proporzione a ore_pianificate, al costo_ora dell'assegnatario (Opzione B).
        Fallback (→ costo_stimato=True): fase senza ore_pianificate → split
        uniforme; task/fase senza assegnatario → tariffa media di progetto.
      - PIANIFICATO (piano PM): Σ task (ore_pianificate × costo_ora[assegnatario]).
      - CONSUMATO  (reale): Σ consuntivi (ore_dichiarate × costo_ora[chi ha loggato]).
        Identico al precedente `margine_attuale` (oracolo invariato).

    Due erosioni (euro e punti percentuali):
      - commerciale = margine_venduto − margine_consumato  (sforiamo il contratto?)
      - operativa   = margine_pianificato − margine_consumato (sforiamo il piano?)

    Output a due livelli: {"progetti": [...], "totali_per_azienda": [...]}.
    Coerenza: i totali di azienda sono la SOMMA dei valori (arrotondati) dei
    progetti del ramo → Σ per-progetto == totale per costruzione.
    """
    from models import Fase, Azienda

    session = get_session()
    try:
        # mappe di supporto (una query ciascuna)
        dip = {
            d.id: {"nome": d.nome, "profilo": d.profilo, "costo_ora": float(d.costo_ora or 0)}
            for d in session.query(Dipendente).all()
        }
        azienda_nome = {a.id: a.nome for a in session.query(Azienda).all()}

        def rate(did):
            return dip.get(did, {}).get("costo_ora", 0.0) if did else 0.0

        progetti = (
            session.query(Progetto)
            .filter(Progetto.tipologia != "interna")  # esclusione per tipologia
            .all()
        )

        per_progetto = []
        for p in progetti:
            tasks = session.query(Task).filter(Task.progetto_id == p.id).all()
            fasi = session.query(Fase).filter(Fase.progetto_id == p.id).all()
            fallback = False

            # --- tariffa media di progetto (pesata sulle ore pianificate) ---
            num = sum((t.ore_pianificate or 0) * rate(t.dipendente_id)
                      for t in tasks if rate(t.dipendente_id))
            den = sum((t.ore_pianificate or 0)
                      for t in tasks if rate(t.dipendente_id))
            if den > 0:
                avg_rate = num / den
            else:
                rates = [rate(t.dipendente_id) for t in tasks if rate(t.dipendente_id)]
                avg_rate = sum(rates) / len(rates) if rates else 0.0

            # --- CONSUMATO (reale, dai consuntivi) — identico al vecchio calcolo ---
            costo_consumato = 0.0
            ore_consumate = 0.0
            costi_per_persona = {}
            cons = (session.query(Consuntivo).join(Task, Consuntivo.task_id == Task.id)
                    .filter(Task.progetto_id == p.id).all())
            for c in cons:
                if c.ore_dichiarate <= 0:
                    continue
                r = rate(c.dipendente_id)
                costo_consumato += c.ore_dichiarate * r
                ore_consumate += c.ore_dichiarate
                if c.dipendente_id not in costi_per_persona:
                    info = dip.get(c.dipendente_id, {"nome": c.dipendente_id, "profilo": "-"})
                    costi_per_persona[c.dipendente_id] = {
                        "nome": info["nome"], "profilo": info["profilo"],
                        "costo_ora": r, "ore": 0, "costo": 0,
                    }
                costi_per_persona[c.dipendente_id]["ore"] += c.ore_dichiarate
                costi_per_persona[c.dipendente_id]["costo"] += c.ore_dichiarate * r

            # --- PIANIFICATO (piano PM): ore_pianificate × rate assegnatario ---
            costo_pianificato = 0.0
            for t in tasks:
                op = t.ore_pianificate or 0
                if op <= 0:
                    continue
                r = rate(t.dipendente_id)
                if not r:  # ore pianificate senza tariffa attribuibile
                    r = avg_rate
                    fallback = True
                costo_pianificato += op * r

            # --- VENDUTO (Opzione B): Fase.ore_vendute ripartite per ore_pianificate ---
            costo_venduto = 0.0
            tasks_per_fase = {}
            for t in tasks:
                tasks_per_fase.setdefault(t.fase_id, []).append(t)
            for f in fasi:
                ov = float(f.ore_vendute or 0)
                if ov <= 0:
                    continue
                ftasks = tasks_per_fase.get(f.id, [])
                if not ftasks:
                    costo_venduto += ov * avg_rate
                    fallback = True
                    continue
                sum_plan = sum((t.ore_pianificate or 0) for t in ftasks)
                if sum_plan > 0:
                    for t in ftasks:
                        quota = ov * (t.ore_pianificate or 0) / sum_plan
                        r = rate(t.dipendente_id)
                        if not r:
                            r = avg_rate
                            fallback = True
                        costo_venduto += quota * r
                else:
                    # nessuna ora pianificata nella fase → split uniforme
                    fallback = True
                    n = len(ftasks)
                    for t in ftasks:
                        r = rate(t.dipendente_id) or avg_rate
                        costo_venduto += (ov / n) * r

            valore = float(p.valore_contratto or 0)
            m_venduto = round(valore - costo_venduto, 2)
            m_pianificato = round(valore - costo_pianificato, 2)
            m_consumato = round(valore - costo_consumato, 2)
            pct_venduto = _pct(m_venduto, valore)
            pct_pianificato = _pct(m_pianificato, valore)
            pct_consumato = _pct(m_consumato, valore)

            per_progetto.append({
                "progetto_id": p.id, "nome": p.nome,
                "cliente": p.cliente, "stato": p.stato, "tipologia": p.tipologia,
                "azienda_id": p.azienda_id,
                "azienda_nome": azienda_nome.get(p.azienda_id),
                "valore_contratto": valore,
                "ore_consuntivate": round(ore_consumate, 1),
                # tre costi e tre margini
                "costo_venduto": round(costo_venduto, 2),
                "costo_pianificato": round(costo_pianificato, 2),
                "costo_consumato": round(costo_consumato, 2),
                "margine_venduto": m_venduto, "margine_venduto_pct": pct_venduto,
                "margine_pianificato": m_pianificato, "margine_pianificato_pct": pct_pianificato,
                "margine_consumato": m_consumato, "margine_consumato_pct": pct_consumato,
                # due erosioni (euro e punti percentuali)
                "erosione_commerciale_eur": round(m_venduto - m_consumato, 2),
                "erosione_commerciale_pp": round(pct_venduto - pct_consumato, 1),
                "erosione_operativa_eur": round(m_pianificato - m_consumato, 2),
                "erosione_operativa_pp": round(pct_pianificato - pct_consumato, 1),
                # trasparenza: margine approssimato per dati incompleti
                "costo_stimato": fallback,
                # compat con il payload precedente (oracolo: margine_attuale invariato)
                "costo_effettivo": round(costo_consumato, 2),
                "margine_attuale": m_consumato, "margine_pct": pct_consumato,
                "dettaglio_persone": sorted(
                    costi_per_persona.values(), key=lambda x: x["costo"], reverse=True
                ),
            })

        # --- aggregato per azienda (somma dei valori arrotondati per coerenza) ---
        tot = {}
        for r in per_progetto:
            k = r["azienda_id"]
            if k not in tot:
                tot[k] = {
                    "azienda_id": k, "azienda_nome": r["azienda_nome"],
                    "n_progetti": 0, "valore_contratto": 0.0,
                    "costo_venduto": 0.0, "costo_pianificato": 0.0, "costo_consumato": 0.0,
                    "costo_stimato": False,
                }
            a = tot[k]
            a["n_progetti"] += 1
            a["valore_contratto"] += r["valore_contratto"]
            a["costo_venduto"] += r["costo_venduto"]
            a["costo_pianificato"] += r["costo_pianificato"]
            a["costo_consumato"] += r["costo_consumato"]
            a["costo_stimato"] = a["costo_stimato"] or r["costo_stimato"]

        totali_per_azienda = []
        for a in tot.values():
            val = round(a["valore_contratto"], 2)
            mv = round(val - a["costo_venduto"], 2)
            mp = round(val - a["costo_pianificato"], 2)
            mc = round(val - a["costo_consumato"], 2)
            pv, pp_, pc = _pct(mv, val), _pct(mp, val), _pct(mc, val)
            totali_per_azienda.append({
                "azienda_id": a["azienda_id"], "azienda_nome": a["azienda_nome"],
                "n_progetti": a["n_progetti"], "valore_contratto": val,
                "costo_venduto": round(a["costo_venduto"], 2),
                "costo_pianificato": round(a["costo_pianificato"], 2),
                "costo_consumato": round(a["costo_consumato"], 2),
                "margine_venduto": mv, "margine_venduto_pct": pv,
                "margine_pianificato": mp, "margine_pianificato_pct": pp_,
                "margine_consumato": mc, "margine_consumato_pct": pc,
                "erosione_commerciale_eur": round(mv - mc, 2),
                "erosione_commerciale_pp": round(pv - pc, 1),
                "erosione_operativa_eur": round(mp - mc, 2),
                "erosione_operativa_pp": round(pp_ - pc, 1),
                "costo_stimato": a["costo_stimato"],
            })

        per_progetto.sort(key=lambda x: x["margine_consumato_pct"])
        totali_per_azienda.sort(key=lambda x: (x["azienda_nome"] or ""))
        return {"progetti": per_progetto, "totali_per_azienda": totali_per_azienda}
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════════
# BOLLETTINO ECONOMICO — archivio storico della marginalità (DESIGN: separato dal SAL)
# ══════════════════════════════════════════════════════════════════════

def _serializza_economia_progetto(pid):
    """Congela l'economia di UN progetto nel formato Bollettino.

    Riusa margini_economia() (NON la tocca): ne filtra a valle la riga del
    progetto, che contiene già margini calcolati (3 margini + 2 erosioni),
    grezzi (valore, costi, costo_ora per persona in dettaglio_persone),
    azienda denormalizzata e flag costo_stimato. La arricchisce con le ore
    aggregate grezze (vendute/pianificate; le consumate ci sono già).
    Solleva ValueError se il progetto non è in Economia (inesistente o interno).
    """
    from sqlalchemy import func
    from models import Fase

    eco = margini_economia()
    riga = next((p for p in eco["progetti"] if p["progetto_id"] == pid), None)
    if riga is None:
        raise ValueError(
            f"Progetto '{pid}' non presente in Economia (inesistente o interno)"
        )

    riga = dict(riga)  # copia: non mutare l'output condiviso
    session = get_session()
    try:
        ore_vendute = float(
            session.query(func.coalesce(func.sum(Fase.ore_vendute), 0.0))
            .filter(Fase.progetto_id == pid).scalar() or 0.0
        )
        ore_pianificate = float(
            session.query(func.coalesce(func.sum(Task.ore_pianificate), 0.0))
            .filter(Task.progetto_id == pid).scalar() or 0.0
        )
    finally:
        session.close()
    riga["ore_vendute"] = round(ore_vendute, 1)
    riga["ore_pianificate"] = round(ore_pianificate, 1)

    return {"schema_version": 1, "progetto": riga}


def crea_bollettino(progetto_id, consolidato_da=None, nota=None):
    """Crea un Bollettino economico congelando l'economia corrente del progetto.
    Ritorna i metadati (non l'intero JSON). ValueError se progetto non in Economia.
    """
    from models import BollettinoEconomico

    stato = _serializza_economia_progetto(progetto_id)  # ValueError se assente

    session = get_session()
    try:
        b = BollettinoEconomico(
            progetto_id=progetto_id,
            consolidato_da=consolidato_da,
            nota=nota,
            stato=stato,
        )
        session.add(b)
        session.commit()
        session.refresh(b)
        return {
            "id": b.id,
            "progetto_id": b.progetto_id,
            "data_snapshot": _iso(b.data_snapshot),
            "consolidato_da": b.consolidato_da,
            "nota": b.nota,
        }
    finally:
        session.close()


def lista_bollettini_progetto(pid):
    """Storico SINTETICO dei bollettini di un progetto (NO JSON stato), data desc."""
    from models import BollettinoEconomico
    session = get_session()
    try:
        rows = (
            session.query(
                BollettinoEconomico.id, BollettinoEconomico.data_snapshot,
                BollettinoEconomico.consolidato_da, BollettinoEconomico.nota,
            )
            .filter(BollettinoEconomico.progetto_id == pid)
            .order_by(BollettinoEconomico.data_snapshot.desc(), BollettinoEconomico.id.desc())
            .all()
        )
        return [{
            "id": r[0],
            "data_snapshot": _iso(r[1]),
            "consolidato_da": r[2],
            "consolidato_da_nome": _nome_dip(session, r[2]),
            "nota": r[3],
        } for r in rows]
    finally:
        session.close()


def get_bollettino_progetto_id(bid):
    """progetto_id di un bollettino (per l'auth a monte), None se inesistente."""
    from models import BollettinoEconomico
    session = get_session()
    try:
        r = session.query(BollettinoEconomico.progetto_id).filter(
            BollettinoEconomico.id == bid
        ).first()
        return r[0] if r else None
    finally:
        session.close()


def get_bollettino(bid):
    """Bollettino COMPLETO (incluso JSON `stato`) o None se inesistente."""
    from models import BollettinoEconomico
    session = get_session()
    try:
        b = session.query(BollettinoEconomico).filter(BollettinoEconomico.id == bid).first()
        if b is None:
            return None
        return {
            "id": b.id,
            "progetto_id": b.progetto_id,
            "data_snapshot": _iso(b.data_snapshot),
            "consolidato_da": b.consolidato_da,
            "consolidato_da_nome": _nome_dip(session, b.consolidato_da),
            "nota": b.nota,
            "stato": b.stato,
        }
    finally:
        session.close()
