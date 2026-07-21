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
   - Layout A': parte dai TASK del dipendente (non dai Consuntivi),
     via data.task_settimana_dipendente (riusabile dalla Home-utente).
   - Query param opzionale `settimana` (ISO YYYY-MM-DD, qualsiasi giorno
     della settimana → normalizzato al lunedì da data.lunedi_settimana).
     Assente = settimana corrente. Ammesse solo corrente e precedente:
     qualsiasi altra → 400. Serve al recupero di chi non ha compilato in
     tempo; non si compila in anticipo né si riscrive un mese fa.
   - Restituisce: nome, profilo, ore_contrattuali, settimana (lunedì ISO),
     settimane_disponibili, totale_ore, task_settimana, compilato.
   - `settimane_disponibili`: le due settimane apribili, ciascuna con
     lunedi/etichetta/compilabile. CONSULTABILE ≠ COMPILABILE: la scorsa si
     apre sempre in lettura, ma `compilabile` è False se già completa (ore
     dichiarate >= ore contrattuali) — il recupero serve a chi non ha
     compilato, non a rivedere ciò che è chiuso. La guardia in scrittura sta
     su POST /salva, non qui.

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
La vista `/me` non ha più early-return sulla tabella Consuntivi vuota: parte
dai Task attivi, quindi `task_settimana` è popolata anche alla prima
compilazione (ore_consumate=0), non lista vuota.

STORIA
──────
Estratto da main.py il 5 maggio 2026 nell'ambito del refactoring strangler.
Letture migrate da DataFrame in cache a Postgres diretto il 21 maggio 2026
(handoff migrazione §6-ter), preservando iso-comportamento.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from deps import get_current_user, require_manager
from models import Utente, Dipendente, Task, Consuntivo, get_session
from data import (
    get_dipendente,
    task_settimana_dipendente,
    lunedi_settimana,
    settimane_selezionabili,
)


# Import condizionale per scrittura
try:
    from data import salva_consuntivo
    PERSISTENT_MODE = True
except ImportError:
    PERSISTENT_MODE = False


# ── DTO ──────────────────────────────────────────────────────────────────
class SalvaConsuntivoRequest(BaseModel):
    dipendente_id: str
    # Lunedì della settimana in ISO. Assente = settimana corrente. Qualsiasi
    # giorno è accettato e normalizzato al lunedì (data.lunedi_settimana).
    settimana: Optional[str] = None
    ore_per_task: dict[str, float] = {}
    stati_per_task: dict[str, str] = {}
    giorni_sede: int = 3
    giorni_remoto: int = 2
    ore_assenza: float = 0
    tipo_assenza: str = ""
    nota_assenza: str = ""
    # None = il chiamante non gestisce le spese, non toccarle. [] = «questa
    # settimana nessuna spesa», svuota. Il default è None e NON [] proprio
    # per tenere distinti i due casi: con [] come default, un client che
    # omette il campo cancellerebbe le spese senza volerlo.
    spese: Optional[list[dict]] = None


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
def consuntivi_settimana_me(
    settimana: Optional[str] = Query(
        None,
        description="Lunedì della settimana in ISO (YYYY-MM-DD). Assente = "
                    "settimana corrente. Ammesse solo la corrente e la "
                    "precedente; qualsiasi giorno della settimana è accettato "
                    "e viene normalizzato al lunedì.",
    ),
    current_user: Utente = Depends(get_current_user),
):
    """Vista PERSONALE (Layout A'): «ecco cosa era previsto per te in questa
    settimana». Self intrinseco: il dipendente è l'utente loggato, niente
    parametro `dipendente_id`.

    Parte dai TASK del dipendente (non dai Consuntivi): la lista
    `task_settimana` contiene sempre i task da compilare, con le ore già
    dichiarate attaccate (0 se non ancora compilato). La logica riusabile
    sta in data.task_settimana_dipendente (la userà anche la Home-utente).

    Il param `settimana` serve al recupero all'indietro: chi non ha compilato
    entro domenica deve poter tornare sulla settimana scorsa. Si ferma lì —
    non si compila in anticipo e non si riscrive un mese fa. La
    normalizzazione al lunedì passa da data.lunedi_settimana (la stessa regola
    della scrittura: mai ricalcolarla qui).

    Attenzione alla differenza fra CONSULTABILE e COMPILABILE: la settimana
    scorsa è sempre consultabile (la si apre in sola lettura), ma è
    `compilabile` solo se incompleta. La guardia sulla scrittura sta su
    POST /salva, non qui.
    """
    if not current_user.dipendente_id:
        raise HTTPException(400, "Utente non collegato a un dipendente")

    try:
        dip = get_dipendente(current_user.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    disponibili = settimane_selezionabili(current_user.dipendente_id)

    if settimana is None:
        lun = lunedi_settimana()
    else:
        try:
            lun = lunedi_settimana(settimana)
        except ValueError:
            raise HTTPException(
                400,
                f"Settimana '{settimana}' non è una data ISO valida "
                f"(atteso YYYY-MM-DD)",
            )
        ammesse = [s["lunedi"] for s in disponibili]
        if lun.isoformat() not in ammesse:
            raise HTTPException(
                400,
                f"Settimana '{lun.isoformat()}' non consultabile: sono "
                f"ammesse solo la corrente e la precedente "
                f"({', '.join(ammesse)})",
            )

    task_settimana = task_settimana_dipendente(current_user.dipendente_id, lun)
    totale = sum(t["ore_consumate"] for t in task_settimana)

    return {
        "dipendente_id": current_user.dipendente_id,
        "nome": dip["nome"],
        "profilo": dip["profilo"],
        "ore_contrattuali": int(dip["ore_sett"]),
        "settimana": lun.isoformat(),
        "settimane_disponibili": disponibili,
        "totale_ore": round(totale, 1),
        "task_settimana": task_settimana,
        # ⚠️ DIVERGENZA NOTA — `compilato` e `compilabile` (dentro
        # settimane_disponibili) misurano due cose diverse e possono
        # contraddirsi:
        #   compilato   = totale_ore > 0, sui soli task VISIBILI questa
        #                 settimana. Vero appena si dichiara un'ora.
        #   compilabile = ore dichiarate + assenze < ore contrattuali, su
        #                 TUTTI i consuntivi del dip. Guarda la copertura.
        # Una settimana con 4h su 40 è `compilato: True` e `compilabile:
        # True` insieme. `compilato` è un contratto già consumato dal
        # frontend: si allinea quando rifacciamo la pagina, non prima.
        "compilato": totale > 0,
    }


@router.post("/salva")
def salva_consuntivo_endpoint(
    req: SalvaConsuntivoRequest,
    current_user: Utente = Depends(get_current_user),
):
    """Salva il consuntivo settimanale (Pattern Y: self-or-manager).

    La settimana di destinazione arriva dal body (`settimana`, opzionale) e
    viene normalizzata al lunedì da data.lunedi_settimana. Prima era
    `datetime.now()`, cioè il giorno della compilazione: vedi la docstring di
    salva_consuntivo per il meccanismo dei duplicati che ne seguiva.

    La guardia sta QUI, non solo nel frontend: si scrive sulla settimana
    corrente sempre, sulla precedente solo se ancora incompleta. Nascondere il
    bottone non è una guardia — la POST resta raggiungibile.
    """
    # User può salvare SOLO i propri consuntivi (anti-impersonation)
    if current_user.ruolo_app != "manager" and req.dipendente_id != current_user.dipendente_id:
        raise HTTPException(403, "Puoi salvare solo i tuoi consuntivi")

    try:
        dip = get_dipendente(req.dipendente_id)
    except (IndexError, KeyError):
        raise HTTPException(404, "Dipendente non trovato")

    # Settimana bersaglio: sempre quella del DIPENDENTE consuntivato, non di
    # chi salva — un manager che compila per altri deve ricadere sulle
    # settimane aperte per quel dipendente.
    if req.settimana is None:
        lun = lunedi_settimana()
    else:
        try:
            lun = lunedi_settimana(req.settimana)
        except ValueError:
            raise HTTPException(
                400,
                f"Settimana '{req.settimana}' non è una data ISO valida "
                f"(atteso YYYY-MM-DD)",
            )

    disponibili = {s["lunedi"]: s for s in settimane_selezionabili(req.dipendente_id)}
    scelta = disponibili.get(lun.isoformat())
    if scelta is None:
        raise HTTPException(
            400,
            f"Settimana '{lun.isoformat()}' non compilabile: sono ammesse solo "
            f"la corrente e la precedente ({', '.join(disponibili)})",
        )
    if not scelta["compilabile"]:
        raise HTTPException(
            400,
            f"La {scelta['etichetta'].lower()} risulta già compilata: il "
            f"recupero è previsto per chi non ha compilato, non per rivedere "
            f"una settimana chiusa",
        )

    if PERSISTENT_MODE:
        ok = salva_consuntivo(
            dipendente_id=req.dipendente_id,
            settimana=lun,
            ore_per_task=req.ore_per_task,
            stati_per_task=req.stati_per_task,
            giorni_sede=req.giorni_sede,
            giorni_remoto=req.giorni_remoto,
            ore_assenza=req.ore_assenza,
            tipo_assenza=req.tipo_assenza,
            nota_assenza=req.nota_assenza,
            # req.spese passa così com'è: None e [] hanno significati diversi
            # (vedi DTO). Il vecchio `req.spese if req.spese else None`
            # collassava [] su None, rendendo impossibile svuotare le spese.
            spese_lista=req.spese,
        )
        return {"salvato": ok, "dipendente": dip["nome"], "settimana": lun.isoformat()}
    return {
        "salvato": True,
        "dipendente": dip["nome"],
        "settimana": lun.isoformat(),
        "nota": "Dati non persistenti (db non attivo)",
    }
