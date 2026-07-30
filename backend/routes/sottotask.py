"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/sottotask.py — Router per endpoint /api/sottotask
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone il CRUD dei SOTTOTASK: i pezzi in cui il PM scompone un task dal
Cantiere. Il sottotask è la DEFINIZIONE del lavoro, condivisa da tutti i
collaboratori del task: non ha date proprie (eredita la finestra del task) né
assegnatario proprio (l'assegnazione resta a livello di task).

Step 2 dei sottotask — Cantiere backend (30/07/2026, DESIGN_SOTTOTASK.md).
Il modello è in `models.Sottotask` (migration f2a3b4c5d6e7) con lo stato di
pianificazione aggiunto da a3b4c5d6e7f8.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────────┬──────────┬─────────────────────┐
│ Path                                     │ Metodo   │ Auth                │
├──────────────────────────────────────────┼──────────┼─────────────────────┤
│ /api/sottotask                           │ POST     │ require_manager     │
│ /api/sottotask/{task_id}                 │ GET      │ require_manager     │
│ /api/sottotask/{sottotask_id}            │ PATCH    │ require_manager     │
│ /api/sottotask/{task_id}/riordina        │ PUT      │ require_manager     │
│ /api/sottotask/{sottotask_id}            │ DELETE   │ require_manager     │
└──────────────────────────────────────────┴──────────┴─────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. POST /api/sottotask
   - Body: {task_id, nome, ore_stimate?, ordine?}
   - 404 se il task padre non esiste (come `crea_fase` col progetto padre).
   - `ordine` assente → (max(ordine) dei sottotask del task or 0) + 1, cioè si
     parte da 1. Pattern di `crea_fase_catalogo` in routes/configurazione.py.
     Nota: `Task.ordine` NON è un precedente utilizzabile — al 30/07/2026 tutti
     i task in DB hanno ordine NULL, non viene mai inizializzato. Il precedente
     coerente è quello di Fase/FaseStandard, dove la base è 1.
   - `stato` NON è nel DTO: alla creazione è sempre "Da iniziare", settato
     server-side (stessa scelta di `crea_fase`).

2. GET /api/sottotask/{task_id}
   - Restituisce {task: {...}, sottotask: [...]}, NON un array nudo: serve un
     posto dove attaccare lo scostamento, che è un dato di livello TASK e non
     del singolo sottotask (Step 2.3, vedi sotto).
   - `sottotask`: la lista, ordinata per (ordine, id). Per ciascuno espone
     `n_dichiarazioni`: quante righe di ConsuntivoSottotask ci sono sopra.
     Serve al Cantiere per sapere in anticipo quali sottotask NON sono
     eliminabili (vedi DELETE) senza provare e incassare un 409. Analogo di
     `n_task` in `lista_fasi_progetto`.
   - `task`: task_id, nome, ore_pianificate e `scostamento`.

SEGNALAZIONE DI SCOSTAMENTO — «segnala, non impone»
───────────────────────────────────────────────────
Step 2.3 (30/07/2026). Il campo `task.scostamento` confronta la somma delle
stime dei sottotask col piano corrente del task:

    {"somma_stime_sottotask": 30.0, "ore_pianificate_task": 40.0,
     "differenza": 10.0}       ← differenza = piano − somma

oppure `null` quando non c'è niente da segnalare (task mai scomposto, o senza
`ore_pianificate`: manca il termine di confronto).

È INFORMAZIONE, non un vincolo. Creare o modificare un sottotask non viene MAI
rifiutato perché la somma sfora: nessun 422, nessun ribilanciamento automatico.
Il PM vede i due numeri e decide — stessa filosofia del 409 sul DELETE, che
propone l'alternativa invece di negare e basta.

Il calcolo NON sta qui: vive in `data_db_impl.scostamento_stime_sottotask`,
come `criticita_sforamento_progetti` e `margini_economia`. Le route del
progetto sono chiamanti puri, e lo stesso identico calcolo alimenta anche
`gantt_strutturato`: due esposizioni, una sola verità. Lì sta anche la
motivazione delle scelte (Annullati esclusi dalla somma, Sospesi inclusi;
riferimento `ore_pianificate` e non `ore_stimate`).

3. PATCH /api/sottotask/{sottotask_id}
   - Body: {nome?, ore_stimate?, ordine?, stato?}. Semantica PATCH.
   - `stato` validato contro STATI_PIANIFICAZIONE_SOTTOTASK nel DTO → 400.
   - 404 se il sottotask non esiste.

4. PUT /api/sottotask/{task_id}/riordina
   - Body: {sottotask: [{sottotask_id, ordine}, ...]}
   - Riordino BATCH in un'unica transazione. Approccio "replace" degli ordini
     dichiarati, come `PUT /api/tasks/{id}/dipendenze`: si manda lo stato
     finale, non una sequenza di spostamenti.
   - Non esisteva un riordino batch nel progetto (fasi e catalogo si
     riordinano un PATCH per volta): è nuovo, modellato sul PUT sopra.
   - 404 task inesistente; 400 se un sottotask_id non appartiene al task.

5. DELETE /api/sottotask/{sottotask_id}
   - Elimina SOLO se non ha dichiarazioni (caso "creato per errore").
   - Se ne ha → 409 col conteggio e l'indicazione di usare Sospeso/Annullato.
     Vedi "SEGNALA, NON IMPONE" sotto.
   - 204 No Content in caso di successo, come `elimina_fase`.

SEGNALA, NON IMPONE — l'eliminazione con dichiarazioni
──────────────────────────────────────────────────────
Un sottotask su cui qualcuno ha già dichiarato lavoro non si cancella: quel
lavoro è successo, e la storia serve (consuntivazione, SAL, IA-Archivio).
Il DELETE non viene però negato in silenzio: risponde 409 dicendo QUANTE
dichiarazioni ci sono — così il PM sa quanto lavoro c'è sopra — e indica
l'azione giusta, cioè portare il sottotask a "Annullato" (lo toglie dal piano
CONSERVANDO il dato) o "Sospeso" (pausa). Stesso spirito e stessa forma di
`elimina_fase`, che rifiuta con 409 + conteggio task + cosa fare prima.

Da notare: `Sottotask.dichiarazioni` ha `cascade="all, delete-orphan"` e la FK
è ON DELETE CASCADE. Il DB, da solo, cancellerebbe volentieri le dichiarazioni
insieme al sottotask. Il presidio è quindi APPLICATIVO e sta qui: senza questo
check il cascade distruggerebbe silenziosamente lo storico. Il cascade resta
giusto per il caso in cui muore il TASK intero (il pezzo non sopravvive al
padre), ma non deve essere la via ordinaria per liberarsi delle dichiarazioni.

I DUE ASSI DELLO STATO
──────────────────────
Questo router scrive SOLO `Sottotask.stato`, l'asse di PIANIFICAZIONE
(Da iniziare / Sospeso / Annullato): cosa il PM decide del pezzo di piano.
L'asse dell'AVANZAMENTO (In corso / Completato / Bloccato) vive su
`ConsuntivoSottotask.stato_dichiarato`, lo scrive il dipendente in
Consuntivazione, e NON è raggiungibile da qui. I due CHECK a livello DB si
escludono a vicenda per costruzione. Vedi il commento su
STATI_PIANIFICAZIONE_SOTTOTASK in models.py.

PATTERN AUTH USATI
──────────────────
- `require_manager` su TUTTI gli endpoint, lettura inclusa: il Cantiere è del
  PM, e la scomposizione di un task è informazione di pianificazione. Stessa
  scelta di `routes/fasi.py`, dove anche il GET è manager-only.
  Quando la Consuntivazione dovrà mostrare i sottotask al dipendente (passo
  successivo) servirà un endpoint separato in `routes/consuntivi.py` con
  filtro self-or-manager, non l'apertura di questo.

DOVE VANNO LE VALIDAZIONI
─────────────────────────
Si applica il criterio della nota di metodo in `routes/consuntivi.py`: il DTO
vede solo il body, quindi ospita le regole che dal solo body si decidono —
stato in lista, id/ordini duplicati nel riordino — e alza `HTTPException(400)`
con messaggio parlante (non `ValueError`, che pydantic tradurrebbe in un dump
422). Le regole che dipendono dal DB — il task esiste, il sottotask appartiene
a quel task, ci sono dichiarazioni sopra — stanno nelle route.

Il 400 sullo stato non ammesso segue `SalvaConsuntivoRequest`, che è il
precedente sulla validazione degli stati (`aggiorna_fase` usa invece 422 per
STATI_FASE: convenzione più vecchia, non replicata qui).

DIPENDENZE
──────────
- `models`: `get_session`, `Utente`, `Task`, `Sottotask`, `ConsuntivoSottotask`,
  `STATI_PIANIFICAZIONE_SOTTOTASK`.
- `deps`: `require_manager`.
- `sqlalchemy.func`: per max(ordine) e il conteggio aggregato delle dichiarazioni.

NOTE TECNICHE
─────────────
Sessione: `get_session()` + `try/finally: session.close()`, come `routes/fasi.py`.
Non si usa la dependency `get_db`: i router di pianificazione (fasi,
configurazione) aprono la sessione nel corpo, e questo li segue.

📌 Passi successivi previsti (NON in questo file):
   - motore ore-derivate: le ore di un sottotask si DERIVANO dalle
     dichiarazioni, non si dichiarano. Qui non c'è nessuna colonna ore
     consuntivate, e non deve comparirne.
   - segnalazione di coerenza somma(ore_stimate sottotask) vs ore del task.
   - lettura dei sottotask lato dipendente in Consuntivazione.

STORIA
──────
Nuovo il 30/07/2026 (Step 2 sottotask, Cantiere backend).
═══════════════════════════════════════════════════════════════════════════
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func

from deps import require_manager
from models import (
    get_session, Utente, Task, Sottotask, ConsuntivoSottotask,
    STATI_PIANIFICAZIONE_SOTTOTASK,
)
from data import scostamento_stime_sottotask


# ── DTO ──────────────────────────────────────────────────────────────────
class SottotaskRequest(BaseModel):
    """Body per POST /api/sottotask.

    `stato` non c'è di proposito: un sottotask nasce sempre "Da iniziare",
    valorizzato server-side. Farlo scegliere al client permetterebbe di creare
    un pezzo di piano già Annullato, che non vuol dire niente.
    """
    task_id: str = Field(..., min_length=1, max_length=10)
    nome: str = Field(..., min_length=1, max_length=200)
    ore_stimate: Optional[int] = Field(default=None, ge=0)
    ordine: Optional[int] = Field(default=None, ge=1)


class SottotaskUpdate(BaseModel):
    """Body per PATCH /api/sottotask/{sottotask_id}. Tutti i campi opzionali.

    `nome` e `stato` sono NOT NULL a livello DB: passarli esplicitamente a
    `null` non è "cancellali" ma un errore del chiamante, e viene rifiutato con
    400 nel validatore sotto. Senza quel controllo il None arriverebbe a
    `setattr` e poi al vincolo NOT NULL come IntegrityError, cioè un 500 opaco
    su un errore del client. `ore_stimate` e `ordine` sono invece colonne
    nullable: per loro `null` vuol dire davvero «azzera», ed è legittimo.
    """
    nome: Optional[str] = Field(default=None, min_length=1, max_length=200)
    ore_stimate: Optional[int] = Field(default=None, ge=0)
    ordine: Optional[int] = Field(default=None, ge=1)
    stato: Optional[str] = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _valida_stato_pianificazione(self):
        """Lo stato deve essere uno di quelli che il PM governa sulla definizione.

        Regola decidibile dal solo body → sta qui e non nella route (criterio
        della nota «DOVE VA UNA VALIDAZIONE» in routes/consuntivi.py). Scatta
        prima che si apra una sessione, e vale per chiunque costruisca il DTO.

        Il messaggio nomina gli stati dichiarabili perché è l'errore che ci si
        aspetta: chi arriva qui con "In corso" sta confondendo i due assi, e
        va rimandato alla Consuntivazione invece di leggere solo «non ammesso».

        `HTTPException` e non `ValueError` per la stessa ragione documentata in
        `SalvaConsuntivoRequest._valida_stati_dichiarabili`: vogliamo un 400 con
        un messaggio leggibile, non un dump di validazione 422.
        """
        campi_set = self.model_fields_set

        if "stato" in campi_set and self.stato is None:
            raise HTTPException(
                400,
                "Il campo 'stato' non può essere null: è obbligatorio sul "
                f"sottotask. Valori ammessi: {', '.join(STATI_PIANIFICAZIONE_SOTTOTASK)}. "
                "Ometti il campo per lasciarlo invariato.",
            )
        if "nome" in campi_set and self.nome is None:
            raise HTTPException(
                400,
                "Il campo 'nome' non può essere null: è obbligatorio sul "
                "sottotask. Ometti il campo per lasciarlo invariato.",
            )

        if self.stato is not None and self.stato not in STATI_PIANIFICAZIONE_SOTTOTASK:
            raise HTTPException(
                400,
                f"Stato '{self.stato}' non ammesso sul sottotask: il PM può "
                f"impostare solo {', '.join(STATI_PIANIFICAZIONE_SOTTOTASK)}. "
                f"Gli stati di avanzamento (In corso, Completato, Bloccato) li "
                f"dichiara il dipendente in Consuntivazione, settimana per "
                f"settimana, e vivono sulla dichiarazione — non sulla "
                f"definizione del sottotask.",
            )
        return self


class OrdineSottotask(BaseModel):
    """Una singola posizione nel riordino batch."""
    sottotask_id: int
    ordine: int = Field(..., ge=1)


class RiordinaRequest(BaseModel):
    """Body per PUT /api/sottotask/{task_id}/riordina.

    Si manda lo stato finale degli ordini, non una sequenza di spostamenti
    (approccio "replace", come `PUT /api/tasks/{id}/dipendenze`): più
    prevedibile, e il risultato non dipende dall'ordine di applicazione.
    Non serve elencare TUTTI i sottotask del task: quelli non citati restano
    con l'ordine che hanno.
    """
    sottotask: list[OrdineSottotask] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _valida_batch(self):
        """Nessun id ripetuto, nessun ordine ripetuto.

        Entrambe decidibili dal solo body. Un id ripetuto renderebbe il
        risultato dipendente dall'ordine di applicazione; due sottotask allo
        stesso `ordine` non è vietato dallo schema, ma in un riordino ESPLICITO
        è un errore del chiamante, non una scelta di piano — accettarlo
        significherebbe restituire una lista il cui ordine dipende dall'id.
        """
        ids = [s.sottotask_id for s in self.sottotask]
        dupl_id = sorted({i for i in ids if ids.count(i) > 1})
        if dupl_id:
            raise HTTPException(
                400,
                f"Riordino non valido: sottotask_id ripetuti "
                f"({', '.join(map(str, dupl_id))}). Ogni sottotask va citato "
                f"una volta sola.",
            )

        ordini = [s.ordine for s in self.sottotask]
        dupl_ord = sorted({o for o in ordini if ordini.count(o) > 1})
        if dupl_ord:
            raise HTTPException(
                400,
                f"Riordino non valido: ordine ripetuto "
                f"({', '.join(map(str, dupl_ord))}). Due sottotask non possono "
                f"occupare la stessa posizione.",
            )
        return self


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/sottotask", tags=["sottotask"])


def _task_o_404(session, task_id: str) -> Task:
    """Recupera il task padre o alza 404.

    Il check esplicito evita che una FK violata torni al client come
    IntegrityError (500 opaco) invece che come 404 — stessa ragione per cui
    `crea_fase` verifica il progetto padre prima di inserire.
    """
    task = session.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' non trovato.",
        )
    return task


def _sottotask_o_404(session, sottotask_id: int) -> Sottotask:
    """Recupera il sottotask o alza 404."""
    st = session.query(Sottotask).filter(Sottotask.id == sottotask_id).first()
    if not st:
        raise HTTPException(
            status_code=404,
            detail=f"Sottotask {sottotask_id} non trovato.",
        )
    return st


@router.post("", status_code=201)
def crea_sottotask(req: SottotaskRequest, _: Utente = Depends(require_manager)):
    """Crea un sottotask sotto un task esistente.

    `ordine` assente → si accoda in fondo: (max(ordine) del task or 0) + 1,
    quindi il primo sottotask di un task prende 1. Pattern di
    `crea_fase_catalogo`. Così il caso `ordine = NULL` — che la colonna ammette
    e che in `ORDER BY` finirebbe in coda — in pratica non si verifica per i
    sottotask creati da qui.
    """
    session = get_session()
    try:
        _task_o_404(session, req.task_id)

        ordine = req.ordine
        if ordine is None:
            max_ordine = session.query(func.max(Sottotask.ordine)).filter(
                Sottotask.task_id == req.task_id
            ).scalar() or 0
            ordine = max_ordine + 1

        st = Sottotask(
            task_id=req.task_id,
            nome=req.nome,
            ore_stimate=req.ore_stimate,
            ordine=ordine,
            stato="Da iniziare",
        )
        session.add(st)
        session.commit()
        return {
            "id": st.id,
            "task_id": st.task_id,
            "nome": st.nome,
            "ore_stimate": st.ore_stimate,
            "ordine": st.ordine,
            "stato": st.stato,
        }
    finally:
        session.close()


@router.get("/{task_id}")
def lista_sottotask_task(task_id: str, _: Utente = Depends(require_manager)):
    """Sottotask di un task, col conteggio delle dichiarazioni e lo scostamento.

    Forma: {task: {...}, sottotask: [...]}. L'array nudo di prima non aveva un
    posto dove mettere lo scostamento, che descrive il TASK e non i singoli
    pezzi.

    Ordinati per (ordine, id): l'id come secondo criterio rende l'output
    stabile anche per eventuali sottotask con `ordine` NULL — che in Postgres
    l'ASC manda in coda — come fa il loader in data_db_impl per Task.

    `n_dichiarazioni` arriva da una sola query aggregata, non da un conteggio
    per riga: evita l'N+1 su un endpoint che il Cantiere chiama a ogni apertura
    di task.

    `scostamento` è `null` quando non c'è niente da segnalare — task mai
    scomposto, o senza `ore_pianificate`. La lista dei sottotask resta comunque
    piena: sono due informazioni indipendenti, e un piano mancante non è una
    ragione per non mostrare la scomposizione.
    """
    session = get_session()
    try:
        task = _task_o_404(session, task_id)
        task_nome = task.nome
        task_ore_pianificate = task.ore_pianificate

        sottotask = session.query(Sottotask).filter(
            Sottotask.task_id == task_id
        ).order_by(Sottotask.ordine, Sottotask.id).all()

        conteggi = dict(
            session.query(
                ConsuntivoSottotask.sottotask_id,
                func.count(ConsuntivoSottotask.id),
            )
            .filter(ConsuntivoSottotask.sottotask_id.in_([s.id for s in sottotask]))
            .group_by(ConsuntivoSottotask.sottotask_id)
            .all()
        ) if sottotask else {}

        righe = [
            {
                "id": s.id,
                "task_id": s.task_id,
                "nome": s.nome,
                "ore_stimate": s.ore_stimate,
                "ordine": s.ordine,
                "stato": s.stato,
                "n_dichiarazioni": conteggi.get(s.id, 0),
            }
            for s in sottotask
        ]
    finally:
        session.close()

    # Fuori dal try/finally: il calcolo apre la propria sessione (strato dati),
    # non deve accodarsi a quella della route.
    scostamento = scostamento_stime_sottotask([task_id]).get(task_id)

    return {
        "task": {
            "task_id": task_id,
            "nome": task_nome,
            "ore_pianificate": task_ore_pianificate,
            "scostamento": scostamento,
        },
        "sottotask": righe,
    }


@router.patch("/{sottotask_id}")
def modifica_sottotask(
    sottotask_id: int,
    req: SottotaskUpdate,
    _: Utente = Depends(require_manager),
):
    """Modifica nome, ore_stimate, ordine o stato di un sottotask.

    Lo `stato` che si può impostare qui è quello di PIANIFICAZIONE
    (Da iniziare / Sospeso / Annullato), già validato dal DTO. "Annullato" è la
    via corretta per togliere dal piano un sottotask su cui è stato dichiarato
    lavoro: conserva le dichiarazioni, che il DELETE distruggerebbe.
    """
    update_data = req.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nessun campo da modificare.")

    session = get_session()
    try:
        st = _sottotask_o_404(session, sottotask_id)

        for campo, valore in update_data.items():
            setattr(st, campo, valore)

        session.commit()
        return {
            "id": st.id,
            "task_id": st.task_id,
            "nome": st.nome,
            "ore_stimate": st.ore_stimate,
            "ordine": st.ordine,
            "stato": st.stato,
            "aggiornato": True,
        }
    finally:
        session.close()


@router.put("/{task_id}/riordina")
def riordina_sottotask(
    task_id: str,
    req: RiordinaRequest,
    _: Utente = Depends(require_manager),
):
    """Aggiorna in blocco l'ordine dei sottotask di un task.

    Tutto in una transazione: o si applicano tutte le posizioni, o nessuna. Un
    riordino applicato a metà lascerebbe la lista in uno stato che il PM non ha
    chiesto e non vede.

    L'appartenenza dei sottotask al task dipende dal DB, quindi è verificata
    qui e non nel DTO: citare un sottotask di un ALTRO task non è un errore di
    forma ma un tentativo di scrivere fuori dal proprio perimetro, e prende 400
    con l'elenco degli id estranei.
    """
    session = get_session()
    try:
        _task_o_404(session, task_id)

        richiesti = {s.sottotask_id: s.ordine for s in req.sottotask}
        posseduti = {
            s.id: s
            for s in session.query(Sottotask).filter(
                Sottotask.id.in_(richiesti.keys())
            ).all()
        }

        # Un id può mancare perché non esiste o perché appartiene a un altro
        # task: per il chiamante è lo stesso errore — "non è tuo".
        estranei = sorted(
            sid for sid in richiesti
            if sid not in posseduti or posseduti[sid].task_id != task_id
        )
        if estranei:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Riordino rifiutato: {len(estranei)} sottotask non "
                    f"appartengono al task '{task_id}' (o non esistono): "
                    f"{', '.join(map(str, estranei))}. Nessuna posizione è "
                    f"stata modificata."
                ),
            )

        for sid, ordine in richiesti.items():
            posseduti[sid].ordine = ordine

        session.commit()

        aggiornati = session.query(Sottotask).filter(
            Sottotask.task_id == task_id
        ).order_by(Sottotask.ordine, Sottotask.id).all()
        return {
            "task_id": task_id,
            "riordinati": len(richiesti),
            "sottotask": [
                {"id": s.id, "nome": s.nome, "ordine": s.ordine} for s in aggiornati
            ],
        }
    finally:
        session.close()


@router.delete("/{sottotask_id}", status_code=204)
def elimina_sottotask(sottotask_id: int, _: Utente = Depends(require_manager)):
    """Elimina un sottotask, SOLO se nessuno ha dichiarato lavoro sopra.

    Il caso legittimo è il sottotask creato per errore, su cui non è ancora
    successo niente: quello si cancella senza cerimonie.

    Se invece ci sono dichiarazioni, 409 con il CONTEGGIO (così il PM sa quanto
    lavoro c'è sopra) e l'indicazione dell'azione giusta: "Annullato" toglie il
    pezzo dal piano conservando il dato, "Sospeso" lo mette in pausa. Il
    DELETE, per via del cascade su `consuntivo_sottotask`, distruggerebbe le
    dichiarazioni in silenzio — ed è esattamente ciò che questo check impedisce.
    Stessa forma di `elimina_fase` (409 + conteggio + cosa fare invece).
    """
    session = get_session()
    try:
        st = _sottotask_o_404(session, sottotask_id)

        n_dich = session.query(ConsuntivoSottotask).filter(
            ConsuntivoSottotask.sottotask_id == sottotask_id
        ).count()
        if n_dich > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Impossibile eliminare il sottotask '{st.nome}': ha "
                    f"{n_dich} dichiarazioni di lavoro. Eliminarlo cancellerebbe "
                    f"anche quelle. Porta il sottotask a 'Annullato' per "
                    f"toglierlo dal piano conservando lo storico, o a 'Sospeso' "
                    f"per metterlo in pausa "
                    f"(PATCH /api/sottotask/{sottotask_id} con stato=...)."
                ),
            )

        session.delete(st)
        session.commit()
        return None  # 204 No Content
    finally:
        session.close()
