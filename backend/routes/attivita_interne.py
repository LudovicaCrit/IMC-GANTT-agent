"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/attivita_interne.py — Router per /api/attivita-interne
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone la vista delle ATTIVITÀ INTERNE: il lavoro che non ha un cliente —
formazione, mansioni continuative, sviluppo di strumenti interni. Risponde a
una domanda manageriale: «chi passa quanto tempo su cosa che non è cliente».

Concettualmente diverse dai task di progetto-cliente:
  - non hanno un cliente (`cliente='IMC-Group'`, `azienda_id` NULL)
  - non concorrono a marginalità (`margini_economia` filtra
    `tipologia != "interna"`)
  - sono spesso ricorrenti, non scadenze fisse
  - le ore consuntivate qui sono «costo struttura»

⚠ RISCRITTO il 03/09/2026 — IL BUG DI P010
────────────────────────────────────────────
Fino a oggi questo modulo aveva `P010` CABLATO in otto punti: le attività
interne erano modellate come task di UN progetto-contenitore con quell'id.

Quel modello non esiste più. Il contenitore è stato spacchettato in 27
progetti `tipologia='interna'` (corsi PC01-05, mansioni continuative
PI01-15b, sviluppo interno PN01-03), e — questo è il punto — **l'id P010 è
stato RIUSATO per un progetto-cliente vero**: «AIoT Smart City Maida»,
cliente Comune di Maida, `tipologia='ordinario'`, azienda IMC-Improve.

Le conseguenze erano due, ed entrambe silenziose:
  1. LETTURA — la pagina chiedeva i task di P010 e mostrava i 5 task del
     progetto Maida spacciandoli per attività interne, mentre le 27 interne
     vere non comparivano da nessuna parte.
  2. SCRITTURA — il POST creava task con `progetto_id="P010"` cablato: ogni
     «attività interna» creata da lì sarebbe finita DENTRO un progetto
     fatturabile, inquinandone le ore. E il DELETE, che accettava solo task
     di P010, permetteva di cancellare i task di Maida e rifiutava tutti gli
     altri — la protezione girata al contrario.
Nessun task spurio era ancora stato creato (verificato: i 5 task di P010
sono tutti del progetto Maida), ma la strada era aperta.

Il criterio ora è `tipologia == 'interna'`, lo stesso che `margini_economia`
usa dal 03/06/2026 col commento «esclusione per TIPOLOGIA (non per id: il
vecchio filtro `id != 'P010'` era un hack morto)». Quella correzione era
stata fatta là e non qui.

LA CREAZIONE NON VIVE PIÙ QUI
─────────────────────────────
Il vecchio `POST` è stato RIMOSSO, non riparato, perché nel modello nuovo la
domanda che poneva è diventata ambigua: «crea un'attività interna» significava
«aggiungi un task al contenitore», ma i contenitori ora sono 27 e il form non
aveva modo di dire quale. Le sue sette `CATEGORIE` cablate («Formazione»,
«Amministrazione», …) non corrispondono ai progetti reali: a «Formazione» oggi
corrispondono almeno tre progetti distinti (PC01 Corso di inglese, PI15
Formazione tecnica individuale, PI15b Formazione e aggiornamento ARIS).

Aggiungere un task a un progetto interno si fa dal CANTIERE, che è la casa di
quel gesto per ogni progetto e non ha bisogno di un'eccezione: tutte e 27 le
interne sono in stato attivo, quindi già visibili e modificabili da lì.
Riscrivere qui un secondo canale di creazione avrebbe significato mantenere
due percorsi per la stessa scrittura.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────────┬──────────┬─────────────────────────┐
│ Path                                 │ Metodo   │ Auth                    │
├──────────────────────────────────────┼──────────┼─────────────────────────┤
│ /api/attivita-interne                │ GET      │ get_current_user        │
│ /api/attivita-interne/{task_id}      │ DELETE   │ Pattern Y (lookup task) │
└──────────────────────────────────────┴──────────┴─────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/attivita-interne
   - Restituisce le attività interne organizzate PER PERSONA, che è l'asse
     della domanda a cui la pagina risponde. Un elenco piatto dei 27 progetti
     direbbe meno: 19 su 27 sono mansioni continuative con la stessa finestra
     annuale, e in fila sarebbero una lista amorfa.
   - `get_current_user` e non `require_manager`: la pagina deve poter essere
     aperta anche da chi non è manager.
   - Forma: {progetti: [...], per_persona: [{dipendente, ore_settimana,
     attivita: [...]}], totali: {...}}.

2. DELETE /api/attivita-interne/{task_id}
   - Pattern Y «doppio»: recupera il task, poi verifica che il suo
     `dipendente_id` corrisponda al chiamante (se non manager).
   - Vincolo: il task deve appartenere a un progetto `tipologia='interna'`.
     Un task di progetto-cliente — Maida compreso — viene RIFIUTATO con 400.
   - Soft delete: stato → "Eliminato".

NOTA SULLA CONSUNTIVAZIONE
──────────────────────────
Questa pagina NON è il canale con cui un dipendente dichiara le ore interne.
Quel canale è la Consuntivazione: `task_settimana_dipendente` non filtra per
tipologia, quindi i task interni compaiono in `/me` come tutti gli altri, col
loro slider di avanzamento e le ore derivate (verificato il 03/09/2026: 15
dipendenti su 18 hanno task interni assegnati, e una dichiarazione al 35% su
un progetto interno deriva correttamente le ore). Il payload porta anche un
flag `interna` apposta, per il badge blu/grigio. Qui si GUARDA, non si dichiara.

STORIA
──────
- Creato con il modello P010-contenitore.
- 03/09/2026: riscritto sul modello a 27 progetti `tipologia='interna'`.
  POST rimosso, GET aggiunto, DELETE messo in sicurezza.
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from deps import get_current_user
from models import Utente, Progetto, Task, Dipendente, get_session
from data import modifica_task


# Le tre FAMIGLIE, dedotte dal prefisso dell'id progetto. Il modello non ha una
# colonna per questo: il prefisso è la sola informazione disponibile, ed è
# stabile perché assegnato al seed.
# Serve alla pagina per raggruppare 27 voci in tre gruppi leggibili. Un id fuori
# schema ricade su "Altre" invece di sparire — degradare è meglio che nascondere.
FAMIGLIE = {"PC": "Corsi", "PI": "Mansioni continuative", "PN": "Sviluppo interno"}


def _famiglia(progetto_id):
    return FAMIGLIE.get((progetto_id or "")[:2], "Altre")


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/attivita-interne", tags=["attivita-interne"])


@router.get("")
def lista_attivita_interne(_: Utente = Depends(get_current_user)):
    """Le attività interne, per persona.

    TRE QUERY FISSE, non una per progetto: i progetti interni, i loro task con
    il dipendente già caricato (`joinedload`), e l'anagrafica delle persone
    coinvolte. Su 27 progetti e 47 task una lettura per progetto sarebbe un N+1
    su una pagina che si apre spesso.

    `ore_settimana` è DERIVATA e non una colonna: `ore_pianificate` spalmate
    sulle settimane di durata del task, la stessa formula di
    `carico_settimanale_dipendente`. È volutamente un'APPROSSIMAZIONE — la
    distribuzione uniforme è il debito noto documentato in quella funzione — e
    qui serve a rispondere «quanto tempo non-cliente ha questa persona», non a
    fare un conto esatto. Le ore REALI stanno nei consuntivi.

    I task «Eliminato» sono esclusi: sono soft-delete, non lavoro.
    """
    session = get_session()
    try:
        progetti = (
            session.query(Progetto)
            .filter(Progetto.tipologia == "interna")
            .order_by(Progetto.id)
            .all()
        )
        ids = [p.id for p in progetti]

        task = (
            session.query(Task)
            .options(joinedload(Task.progetto))
            .filter(Task.progetto_id.in_(ids), Task.stato != "Eliminato")
            .order_by(Task.id).all()
        ) if ids else []

        dip_ids = {t.dipendente_id for t in task if t.dipendente_id}
        persone = {
            d.id: d for d in session.query(Dipendente)
            .filter(Dipendente.id.in_(dip_ids)).all()
        } if dip_ids else {}

        # ── Serializzazione ──────────────────────────────────────────────
        progetti_out = [{
            "id": p.id,
            "nome": p.nome,
            "famiglia": _famiglia(p.id),
            "stato": p.stato,
            "data_inizio": p.data_inizio.isoformat() if p.data_inizio else None,
            "data_fine": p.data_fine.isoformat() if p.data_fine else None,
        } for p in progetti]

        per_dip = {}
        senza_assegnatario = []
        for t in task:
            # Ore/settimana: piano diviso per le settimane di durata. `max(1, …)`
            # per i task più corti di una settimana — senza, dividerebbe per zero
            # o gonfierebbe il numero.
            ore_sett = None
            if t.data_inizio and t.data_fine and t.ore_pianificate:
                settimane = max(1, (t.data_fine - t.data_inizio).days / 7)
                ore_sett = round(float(t.ore_pianificate) / settimane, 1)

            voce = {
                "task_id": t.id,
                "nome": t.nome,
                "progetto_id": t.progetto_id,
                "progetto_nome": t.progetto.nome if t.progetto else "?",
                "famiglia": _famiglia(t.progetto_id),
                "stato": t.stato,
                "ore_pianificate": float(t.ore_pianificate or 0),
                "ore_settimana": ore_sett,
                "data_inizio": t.data_inizio.isoformat() if t.data_inizio else None,
                "data_fine": t.data_fine.isoformat() if t.data_fine else None,
                "dipendente_id": t.dipendente_id,
            }
            if not t.dipendente_id:
                senza_assegnatario.append(voce)
                continue
            per_dip.setdefault(t.dipendente_id, []).append(voce)

        gruppi = []
        for did, voci in per_dip.items():
            d = persone.get(did)
            gruppi.append({
                "dipendente_id": did,
                "nome": d.nome if d else did,
                "profilo": d.profilo if d else "",
                "ore_sett": int(d.ore_sett) if d and d.ore_sett else None,
                "ore_settimana_interne": round(
                    sum(v["ore_settimana"] or 0 for v in voci), 1),
                "attivita": voci,
            })
        # Ordine per ORE INTERNE decrescenti: la domanda della pagina è «chi
        # passa più tempo su lavoro non-cliente», e la risposta va in cima.
        # Il nome come spareggio, così l'ordine non balla a parità di ore.
        gruppi.sort(key=lambda g: (-g["ore_settimana_interne"], g["nome"]))

        return {
            "progetti": progetti_out,
            "per_persona": gruppi,
            "senza_assegnatario": senza_assegnatario,
            "totali": {
                "n_progetti": len(progetti_out),
                "n_task": len(task),
                "n_persone": len(gruppi),
                "per_famiglia": {
                    f: sum(1 for p in progetti_out if p["famiglia"] == f)
                    for f in dict.fromkeys(p["famiglia"] for p in progetti_out)
                },
            },
        }
    finally:
        session.close()


@router.delete("/{task_id}")
def elimina_attivita_interna(
    task_id: str,
    current_user: Utente = Depends(get_current_user),
):
    """Elimina (soft) un task di attività interna.

    LA GUARDIA È SULLA TIPOLOGIA DEL PROGETTO, non su un id.
    Prima era `if task.progetto_id != "P010"`, e con P010 diventato il progetto
    Maida quella riga faceva l'opposto di ciò che prometteva: lasciava
    cancellare i task di un progetto-cliente e rifiutava tutti gli altri.
    Ora un task di progetto-cliente — Maida compreso — riceve un 400.
    """
    session = get_session()
    try:
        riga = (
            session.query(Task, Progetto.tipologia, Progetto.nome)
            .join(Progetto, Progetto.id == Task.progetto_id)
            .filter(Task.id == task_id).first()
        )
        if riga is None:
            raise HTTPException(404, "Task non trovato")
        task, tipologia, progetto_nome = riga
        dip_task = task.dipendente_id
    finally:
        session.close()

    if tipologia != "interna":
        raise HTTPException(
            400,
            f"Il task '{task_id}' appartiene al progetto '{progetto_nome}', che "
            f"non è un'attività interna. Da qui si eliminano solo le attività "
            f"interne; per gli altri task usa il Cantiere.",
        )

    # User può cancellare SOLO le proprie attività (anti-impersonation)
    if current_user.ruolo_app != "manager" and dip_task != current_user.dipendente_id:
        raise HTTPException(403, "Puoi cancellare solo le tue attività")

    if modifica_task(task_id, stato="Eliminato"):
        return {"ok": True, "messaggio": f"Task {task_id} eliminato"}
    raise HTTPException(500, "Errore nell'eliminazione")
