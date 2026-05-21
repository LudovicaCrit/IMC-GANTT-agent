"""
═══════════════════════════════════════════════════════════════════════════
backend/routes/consuntivi.py — Router per endpoint /api/consuntivi
═══════════════════════════════════════════════════════════════════════════

SCOPO
─────
Espone gli endpoint relativi ai consuntivi settimanali dei dipendenti.
È il cuore tecnico della pagina Consuntivazione e della futura Vista
Helena (Blocco 3 roadmap). Implementa rigorosamente il pattern
Scenario B + self-or-manager + Pattern Y (anti-impersonation in scrittura).

ENDPOINT ESPOSTI
────────────────
┌──────────────────────────────────┬──────────┬──────────────────────────────┐
│ Path                             │ Metodo   │ Auth                         │
├──────────────────────────────────┼──────────┼──────────────────────────────┤
│ /api/consuntivi/settimana        │ GET      │ require_manager              │
│ /api/consuntivi/me               │ GET      │ AUTH-ONLY (intrinseco self)  │
│ /api/consuntivi/salva            │ POST     │ Pattern Y (self-or-manager)  │
└──────────────────────────────────┴──────────┴──────────────────────────────┘

DETTAGLIO ENDPOINT
──────────────────
1. GET /api/consuntivi/settimana
   - Manager-only.
   - Vista AZIENDALE: tutti i dipendenti, settimana corrente.
   - Per ogni dipendente: ore_per_task, totale_ore, flag `compilato`.
   - Include anche dipendenti che NON hanno compilato (totale_ore=0,
     compilato=False), purché abbiano almeno 1 task attivo.
   - Output ordinato: prima i compilati, poi per nome.

2. GET /api/consuntivi/me
   - AUTH-ONLY: nessun parametro `dipendente_id` accettato.
     L'identità del chiamante determina di chi mostrare i consuntivi.
   - Vista PERSONALE: il dipendente vede SOLO i propri consuntivi.
   - Funziona per user (Helena) e per manager (Ludovica può vedere se
     stessa così, anche se ha accesso a /settimana per la vista aziendale).
   - 400 se l'utente non è collegato a un dipendente
     (current_user.dipendente_id is None).
   - Restituisce: nome, profilo, ore_contrattuali, totale_ore,
     ore_per_task, compilato.

3. POST /api/consuntivi/salva
   - Pattern Y (self-or-manager): l'user può salvare SOLO i propri
     consuntivi (controllo self via current_user.dipendente_id);
     il manager può salvare per chiunque.
   - Body: dipendente_id, ore_per_task, stati_per_task, giorni sede/remoto,
     ore_assenza, tipo_assenza, nota_assenza, spese.
   - 403 se user prova a salvare per un altro dipendente.
   - 404 se dipendente non esiste.
   - Persiste in db (PERSISTENT_MODE) o ritorna conferma simulata altrimenti.

PATTERN AUTH USATI
──────────────────
- `require_manager`: per la vista aziendale aggregata.
- `get_current_user` + check `dipendente_id`: per il pattern self-or-manager
  in scrittura (Pattern Y) e per la vista personale intrinseca (`/me`).

NOTE DI DOMINIO
───────────────
La vista personale `/api/consuntivi/me` è esattamente quella che alimenterà
la pagina Consuntivazione di Helena nella Vista User (Blocco 3 roadmap).
Coerente con la "filosofia della settimana intera" e con Scenario B.

📌 TODO Blocco 3 roadmap (Vista Helena + Form Consuntivazione):
   Il payload restituito da `/api/consuntivi/me` potrebbe arricchirsi:
   - reminder integrati ("non hai ancora compilato")
   - task in scadenza
   - flag `motivo_richiesto` se task bloccato/in ritardo senza nota
   - storia delle ultime N settimane

DIPENDENZE
──────────
- `data` (modulo): `get_dipendente`, `salva_consuntivo` (in PERSISTENT_MODE).
- `models`: `Dipendente`, `Task`, `Consuntivo`, `get_session` (lettura
  diretta Postgres).
- `deps`: `get_current_user`, `require_manager`.
- `models`: classe `Utente` per type hint.

NOTE TECNICHE
─────────────
Helper privato `_consuntivo_vuoto_per_user` per coerenza del payload
quando l'utente non ha ancora consuntivi.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
Letture migrate da DataFrame in cache a Postgres diretto il 21 maggio 2026
(handoff migrazione §6-ter), preservando iso-comportamento.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from deps import get_current_user, require_manager
from models import Utente, Dipendente, Task, Consuntivo, get_session
from data import get_dipendente


# Import condizionale per scrittura
try:
    from data import salva_consuntivo
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False


# ── DTO ──────────────────────────────────────────────────────────────────
class SalvaConsuntivoRequest(BaseModel):
    dipendente_id: str
    ore_per_task: dict[str, float] = {}
    stati_per_task: dict[str, str] = {}
    giorni_sede: int = 3
    giorni_remoto: int = 2
    ore_assenza: float = 0
    tipo_assenza: str = ""
    nota_assenza: str = ""
    spese: list[dict] = []


# ── Helper privato ───────────────────────────────────────────────────────
def _consuntivo_vuoto_per_user(dipendente_id: str):
    """Payload coerente quando l'utente non ha ancora consuntivi."""
    try:
        dip = get_dipendente(dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")
    return {
        "dipendente_id": dipendente_id,
        "nome": dip["nome"],
        "profilo": dip["profilo"],
        "ore_contrattuali": int(dip["ore_sett"]),
        "totale_ore": 0,
        "ore_per_task": [],
        "compilato": False,
    }


# ── Router ───────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/consuntivi", tags=["consuntivi"])


@router.get("/settimana")
def consuntivi_settimana_corrente(_: Utente = Depends(require_manager)):
    """Vista MANAGER-ONLY: riepilogo aziendale settimana corrente.
    Per la vista personale del dipendente vedi /api/consuntivi/me."""
    lun = datetime.now() - timedelta(days=datetime.now().weekday())
    lun_date = lun.date() if hasattr(lun, 'date') else lun
    ven_date = lun_date + timedelta(days=6)

    session = get_session()
    # Iso-comportamento: l'originale fa early-return [] se la tabella
    # consuntivi è completamente vuota (db appena seedato, prima
    # compilazione mai avvenuta). Replicato con una query indicizzata
    # su PK, di costo trascurabile.
    has_any = session.query(Consuntivo.id).first() is not None
    if not has_any:
        session.close()
        return []

    # Una sola query con joinedload su Task → Progetto: evita N+1 nel
    # lookup di nome task/progetto durante il loop.
    cons_sett = session.query(Consuntivo).options(
        joinedload(Consuntivo.task).joinedload(Task.progetto)
    ).filter(
        Consuntivo.settimana >= lun_date,
        Consuntivo.settimana <= ven_date,
    ).all()

    # Raggruppa per dipendente_id (mantiene l'ordine di arrivo, come
    # `unique()` su pandas Series).
    cons_per_dip = {}
    for c in cons_sett:
        cons_per_dip.setdefault(c.dipendente_id, []).append(c)

    risultato = []
    for did, lista_cons in cons_per_dip.items():
        try:
            dip = get_dipendente(did)
        except (IndexError, KeyError):
            continue
        ore_per_task = []
        totale = 0
        for c in lista_cons:
            if c.ore_dichiarate > 0:
                t = c.task
                if t is not None:
                    proj_nome = t.progetto.nome if t.progetto else "?"
                    ore_per_task.append({
                        "task_nome": t.nome,
                        "progetto": proj_nome,
                        "ore": float(c.ore_dichiarate),
                    })
                    totale += float(c.ore_dichiarate)

        if ore_per_task:
            risultato.append({
                "dipendente_id": did,
                "nome": dip["nome"],
                "profilo": dip["profilo"],
                "ore_contrattuali": int(dip["ore_sett"]),
                "totale_ore": round(totale, 1),
                "ore_per_task": ore_per_task,
                "compilato": True,
            })

    # Aggiungi dipendenti che NON hanno compilato (con almeno 1 task attivo).
    # Conteggio task attivi per dipendente fatto in UNA query aggregata,
    # invece di un filtro DataFrame per ciascuno.
    dipendenti_attivi = session.query(Dipendente).filter(Dipendente.attivo == True).all()
    task_count_rows = session.query(
        Task.dipendente_id, func.count(Task.id)
    ).filter(
        Task.stato.in_(["In corso", "Da iniziare"])
    ).group_by(Task.dipendente_id).all()
    task_count = {row[0]: row[1] for row in task_count_rows}
    session.close()

    ids_gia_presenti = {r["dipendente_id"] for r in risultato}
    for d in dipendenti_attivi:
        if d.id in ids_gia_presenti:
            continue
        if task_count.get(d.id, 0) > 0:
            risultato.append({
                "dipendente_id": d.id,
                "nome": d.nome,
                "profilo": d.profilo,
                "ore_contrattuali": int(d.ore_sett),
                "totale_ore": 0,
                "ore_per_task": [],
                "compilato": False,
            })

    return sorted(risultato, key=lambda x: (-x["compilato"], x["nome"]))


@router.get("/me")
def consuntivi_settimana_me(current_user: Utente = Depends(get_current_user)):
    """Vista PERSONALE: i consuntivi del solo chiamante (settimana corrente).
    Self intrinseco: il dipendente è l'utente loggato, niente parametri."""
    if not current_user.dipendente_id:
        raise HTTPException(400, "Utente non collegato a un dipendente")

    lun = datetime.now() - timedelta(days=datetime.now().weekday())
    lun_date = lun.date() if hasattr(lun, 'date') else lun
    ven_date = lun_date + timedelta(days=6)

    session = get_session()
    # Iso-comportamento: payload vuoto se la tabella consuntivi è
    # totalmente vuota (replica l'early-return su _CONSUNTIVI().empty).
    has_any = session.query(Consuntivo.id).first() is not None
    if not has_any:
        session.close()
        return _consuntivo_vuoto_per_user(current_user.dipendente_id)

    cons_user = session.query(Consuntivo).options(
        joinedload(Consuntivo.task).joinedload(Task.progetto)
    ).filter(
        Consuntivo.dipendente_id == current_user.dipendente_id,
        Consuntivo.settimana >= lun_date,
        Consuntivo.settimana <= ven_date,
    ).all()
    session.close()

    try:
        dip = get_dipendente(current_user.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    ore_per_task = []
    totale = 0
    for c in cons_user:
        if c.ore_dichiarate > 0:
            t = c.task
            if t is not None:
                proj_nome = t.progetto.nome if t.progetto else "?"
                ore_per_task.append({
                    "task_nome": t.nome,
                    "progetto": proj_nome,
                    "ore": float(c.ore_dichiarate),
                })
                totale += float(c.ore_dichiarate)

    return {
        "dipendente_id": current_user.dipendente_id,
        "nome": dip["nome"],
        "profilo": dip["profilo"],
        "ore_contrattuali": int(dip["ore_sett"]),
        "totale_ore": round(totale, 1),
        "ore_per_task": ore_per_task,
        "compilato": bool(ore_per_task),
    }


@router.post("/salva")
def salva_consuntivo_endpoint(
    req: SalvaConsuntivoRequest,
    current_user: Utente = Depends(get_current_user),
):
    """Salva il consuntivo settimanale (Pattern Y: self-or-manager)."""
    # User può salvare SOLO i propri consuntivi (anti-impersonation)
    if current_user.ruolo_app != "manager" and req.dipendente_id != current_user.dipendente_id:
        raise HTTPException(403, "Puoi salvare solo i tuoi consuntivi")

    try:
        dip = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    if PERSISTENT_MODE:
        ok = salva_consuntivo(
            dipendente_id=req.dipendente_id,
            settimana=datetime.now(),
            ore_per_task=req.ore_per_task,
            stati_per_task=req.stati_per_task,
            giorni_sede=req.giorni_sede,
            giorni_remoto=req.giorni_remoto,
            ore_assenza=req.ore_assenza,
            tipo_assenza=req.tipo_assenza,
            nota_assenza=req.nota_assenza,
            spese_lista=req.spese if req.spese else None,
        )
        return {"salvato": ok, "dipendente": dip["nome"]}
    return {
        "salvato": True,
        "dipendente": dip["nome"],
        "nota": "Dati non persistenti (db non attivo)",
    }
