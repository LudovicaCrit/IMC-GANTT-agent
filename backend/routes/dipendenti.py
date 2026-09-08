"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/dipendenti.py — Router per endpoint /api/dipendenti
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint REST per la lettura dei dati anagrafici e operativi
dei dipendenti (carico, saturazione, progetti attivi, task in corso).
NON contiene endpoint di Configurazione (CRUD admin) — quelli stanno in
`routes/configurazione.py`. NON contiene endpoint di gestione consuntivi
o assegnazioni — quelli stanno nei rispettivi router.

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/dipendenti                  │ GET      │ require_manager (Scenario B) │
│ /api/dipendenti/{dip_id}         │ GET      │ self-or-manager              │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/dipendenti
   - Manager-only. Restituisce lista completa dei dipendenti aziendali con
     dati aggregati: profilo, ore_sett, competenze, carico_corrente,
     saturazione_pct, progetti_attivi, n_task_attivi.
   - Filosofia Scenario B: il dato aggregato sui colleghi è informazione
     manageriale, non visibile agli user (Helena vede solo se stessa).

2. GET /api/dipendenti/{dip_id}
   - Pattern self-or-manager. User può consultare SOLO il proprio profilo
     (verifica `dip_id == current_user.dipendente_id`); manager può
     consultare qualunque dipendente.
   - Restituisce dati anagrafici + carico + lista task in corso.
   - 403 se user prova ad accedere a un altro dipendente.
   - 404 se dipendente non esiste.

PATTERN AUTH USATI
──────────────────
- `require_manager`: dependency che blocca con 403 chi non è manager.
- `get_current_user` + check manuale `current_user.dipendente_id`: usato
  per il pattern self-or-manager dove la logica self richiede il dato
  dell'utente loggato.

DIPENDENZE
──────────
- `data` (modulo): funzioni `get_dipendente`, `get_progetti_dipendente`,
  `carico_settimanale_dipendente`.
- `models`: `Dipendente`, `Task`, `get_session` (lettura diretta Postgres).
- `data_db_impl._to_dt`: serializzazione date a datetime-mezzanotte (per
  preservare il formato ISO `YYYY-MM-DDT00:00:00` storicamente esposto).
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
`carico_settimanale_dipendente` resta come helper di `data` perché
contiene calcolo non meccanico (trappola §4 dell'handoff migrazione
Postgres): sarà trattata a parte. Le letture qui non passano più dai
DataFrame in cache: ogni richiesta interroga direttamente Postgres.

STORIA
──────
Estratto da main.py il 5 maggio 2026 come primo router del refactoring
"strangler" finalizzato a passare main.py da ~2780 righe a ≤200, lasciando
a Roberto un codice modulare per R2 (settembre 2026).
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import joinedload

from deps import get_current_user, require_manager
from models import (
    Utente, Dipendente, Task, Progetto, get_session,
    Competenza, DipendentiCompetenze,
)
from data import (
    get_dipendente, get_progetti_dipendente, carico_settimanale_dipendente,
)
from data_db_impl import _to_dt
from utils import get_oggi


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/dipendenti", tags=["dipendenti"])


@router.get("")
def lista_dipendenti(_: Utente = Depends(require_manager)):
    """Lista dipendenti con saturazione e progetti attivi (manager-only).

    Scenario B: il dettaglio aggregato sui colleghi è informazione
    manageriale, non visibile agli user.
    """
    session = get_session()
    dipendenti = session.query(Dipendente).filter(Dipendente.attivo == True).all()

    # ── UNA query per progetti-attivi E conteggio-task di TUTTI ───────────
    # Erano due query PER PERSONA — `get_progetti_dipendente` (che apriva anche
    # una sessione propria) e un `.count()` — su un ciclo di 18 dipendenti.
    #
    # Si fondono in una sola perché hanno il MEDESIMO filtro: i task attivi
    # della persona. Il conteggio è il numero di righe, l'elenco-progetti è la
    # deduplica di quelle righe per progetto. Chiedere due volte lo stesso
    # insieme per contarlo e poi per leggerlo era il vero spreco, più ancora
    # del fatto che fosse dentro un ciclo.
    #
    # `order_by(Task.id)` e la deduplica «prima occorrenza vince» replicano
    # esattamente `get_progetti_dipendente`: l'ordine dei nomi-progetto è quello
    # del primo task incontrato, e cambiarlo cambierebbe il payload.
    righe_attive = (
        session.query(Task.dipendente_id, Task.progetto_id, Progetto.nome)
        .join(Progetto, Task.progetto_id == Progetto.id)
        .filter(
            Task.dipendente_id.in_([d.id for d in dipendenti]),
            Task.stato.in_(["In corso", "Da iniziare"]),
        )
        .order_by(Task.id)
        .all()
    ) if dipendenti else []

    # ── UNA query per le competenze di TUTTI ──────────────────────────────
    # Fonte: la M2M `dipendenti_competenze`, non più il JSON `d.competenze`.
    # Il catalogo `Competenza` è la lista chiusa dei nomi validi e solo la M2M
    # lo referenzia per chiave; il JSON accettava stringhe libere, ed è da lì
    # che venivano 'IA' (doppione di 'AI/ML') e tre frammenti mai censiti.
    # Batch e non una query per persona, per la stessa ragione detta sopra per
    # progetti-e-task: il filtro è unico, l'insieme è unico, e questo ciclo di
    # 18 è esattamente il posto dove un N+1 si infila senza farsi notare.
    # Il payload non cambia forma: `competenze` resta una lista di nomi.
    comp_per_dip = {}
    righe_comp = (
        session.query(DipendentiCompetenze.dipendente_id, Competenza.nome)
        .join(Competenza, Competenza.id == DipendentiCompetenze.competenza_id)
        .filter(DipendentiCompetenze.dipendente_id.in_([d.id for d in dipendenti]))
        .order_by(Competenza.nome)
        .all()
    ) if dipendenti else []
    for did, nome in righe_comp:
        comp_per_dip.setdefault(did, []).append(nome)

    progetti_per_dip = {}
    visti_per_dip = {}
    n_task_per_dip = {}
    for did, pid, pnome in righe_attive:
        n_task_per_dip[did] = n_task_per_dip.get(did, 0) + 1
        visti = visti_per_dip.setdefault(did, set())
        if pid not in visti:
            visti.add(pid)
            progetti_per_dip.setdefault(did, []).append(pnome)

    result = []
    for d in dipendenti:
        # `carico_settimanale_dipendente` resta UNA CHIAMATA PER PERSONA, ed è
        # deliberato: dentro ha la finestra-settimana, una delle tre copie che
        # la scansione ha segnalato come regola-duplicata. Batcharla vorrebbe
        # dire riscrivere quella finestra qui — una QUARTA copia — oppure
        # spostarla, e nessuna delle due è un'ottimizzazione: sono decisioni
        # sulla regola, che vanno prese guardando tutte e tre le copie insieme.
        # Restano 18 query su 55: il resto è sparito senza toccare niente.
        carico = carico_settimanale_dipendente(d.id, get_oggi())
        progetti = progetti_per_dip.get(d.id, [])
        n_task_attivi = n_task_per_dip.get(d.id, 0)
        result.append({
            "id": d.id,
            "nome": d.nome,
            "profilo": d.profilo,
            "ore_sett": int(d.ore_sett),
            "competenze": comp_per_dip.get(d.id, []),
            "carico_corrente": float(carico),
            "saturazione_pct": round(carico / d.ore_sett * 100),
            "progetti_attivi": progetti,
            "n_task_attivi": n_task_attivi,
        })
    session.close()
    return result


@router.get("/{dip_id}")
def dettaglio_dipendente(
    dip_id: str,
    current_user: Utente = Depends(get_current_user),
):
    """Dettaglio dipendente (pattern self-or-manager).

    User può vedere solo il proprio profilo (verifica self via
    current_user.dipendente_id); manager può vedere chiunque.
    """
    if current_user.ruolo_app != "manager" and dip_id != current_user.dipendente_id:
        raise HTTPException(403, "Puoi vedere solo il tuo profilo")
    try:
        d = get_dipendente(dip_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    carico = carico_settimanale_dipendente(dip_id, get_oggi())
    progetti = get_progetti_dipendente(dip_id)
    session = get_session()
    tasks = session.query(Task).options(
        joinedload(Task.progetto), joinedload(Task.fase_rel)
    ).filter(
        Task.dipendente_id == dip_id,
        Task.stato.in_(["In corso", "Da iniziare"]),
    ).all()
    session.close()

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
                "id": t.id,
                "nome": t.nome,
                "progetto": t.progetto.nome if t.progetto else "",
                "fase": t.fase_rel.nome if t.fase_rel else "",
                "stato": t.stato,
                "ore_stimate": int(t.ore_stimate or 0),
                "data_inizio": _to_dt(t.data_inizio).isoformat() if t.data_inizio else None,
                "data_fine": _to_dt(t.data_fine).isoformat() if t.data_fine else None,
            }
            for t in tasks
        ],
    }