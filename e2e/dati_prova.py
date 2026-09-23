#!/usr/bin/env python
"""
dati_prova.py — i task sintetici delle verifiche in browser.

PERCHÉ TASK INVENTATI e non quelli veri. I casi da provare non esistono nel DB
di sviluppo, e scrivere ore su un task vero sporcherebbe dati che poi qualcun
altro legge. Sono quattro, tutti su progetti dove Helena (D004) lavora già, e
tutti tolti da `--pulisci` insieme a ciò che le verifiche ci hanno scritto sopra.

Per «aggiungi riga» — servono task FUORI dalla settimana, che la griglia non
propone e che la selezione deve offrire:

  T900  su P002 — progetto su cui Helena STA GIÀ lavorando (ha T015 in griglia).
        Date dopo la settimana ma dentro l'orizzonte del mese. È il task su cui
        la verifica scrive davvero le ore.
  T901  su P011 — progetto su cui NON sta lavorando questa settimana. Serve
        all'ordinamento (dev'essere sotto P002) e al caso «solo stato, niente
        ore», che deve far comparire l'avvertenza.

Per il «banner attività senza spiegazione» — servono invece task DENTRO la
settimana, cioè righe che la griglia carica già, su cui nessuno ha ancora detto
niente. Non si possono usare quelli veri: la verifica ci scrive sopra, e le ore
vere non si toccano. Sono due perché i modi di spiegare un'attività sono due, e
vanno provati separatamente:

  T902  lo si spiega con lo STATO (Bloccato + nota), senza ore.
  T903  lo si spiega mettendoci le ORE.

`--pulisci` rimuove i quattro task E tutto ciò che le verifiche hanno scritto su
di loro (blocchi, consuntivi): il resto del database dev'essere byte per byte
quello di prima, ed è ciò che l'impronta md5 in fondo al README controlla.

Uso:
    python e2e/dati_prova.py --crea
    python e2e/dati_prova.py --pulisci
    python e2e/dati_prova.py --impronta     # md5 di blocchi_ore e consuntivi
"""
import sys
import os
import argparse
import hashlib
from datetime import date, timedelta

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADICE, "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(RADICE, "backend", ".env"))

from sqlalchemy import text  # noqa: E402
from data_db_impl import get_session  # noqa: E402
from models import Task, BloccoOre, Consuntivo  # noqa: E402
from scenario_sottotask import TASK as TASK_SCENARIO  # noqa: E402
from scenario_fasi import TASK as TASK_FASI  # noqa: E402

DIPENDENTE = "D004"          # Helena Ullah — l'utente `user` del seed

# Le date dei due task «dentro la settimana» si calcolano da oggi, non sono
# scritte: devono intersecare la settimana corrente qualunque giorno si lanci la
# verifica, o la griglia non li caricherebbe affatto.
_OGGI = date.today()
_LUN = _OGGI - timedelta(days=_OGGI.weekday())

TASK_PROVA = [
    # id     progetto  fase  nome                                   inizio      fine
    ("T900", "P002", 8, "[prova e2e] Ritocco integrazione fuori piano", date(2026, 10, 5), date(2026, 10, 12)),
    ("T901", "P011", 68, "[prova e2e] Sopralluogo non pianificato", date(2026, 10, 1), date(2026, 10, 9)),
    ("T902", "P002", 8, "[prova e2e] Da spiegare con lo stato", _LUN - timedelta(days=7), _LUN + timedelta(days=13)),
    ("T903", "P002", 8, "[prova e2e] Da spiegare con le ore", _LUN - timedelta(days=7), _LUN + timedelta(days=13)),
]


def crea():
    session = get_session()
    try:
        for tid, pid, fase_id, nome, inizio, fine in TASK_PROVA:
            if session.query(Task).filter(Task.id == tid).first():
                print(f"  {tid} c'è già")
                continue
            session.add(Task(
                id=tid, progetto_id=pid, fase_id=fase_id, nome=nome,
                stato="Da iniziare", dipendente_id=DIPENDENTE,
                data_inizio=inizio, data_fine=fine,
                ore_stimate=8, ore_pianificate=8,
            ))
            print(f"  {tid} creato ({pid}, {inizio} → {fine})")
        session.commit()
    finally:
        session.close()


def pulisci():
    ids = [t[0] for t in TASK_PROVA]
    session = get_session()
    try:
        n_b = session.query(BloccoOre).filter(BloccoOre.task_id.in_(ids)).delete(synchronize_session=False)
        n_c = session.query(Consuntivo).filter(Consuntivo.task_id.in_(ids)).delete(synchronize_session=False)
        n_t = session.query(Task).filter(Task.id.in_(ids)).delete(synchronize_session=False)
        session.commit()
        print(f"  tolti: {n_t} task, {n_b} blocchi, {n_c} consuntivi")
    finally:
        session.close()


def impronta():
    """md5 dello storico che nessuna verifica deve toccare.

    Fuori dal conto stanno TUTTI gli id sintetici — i quattro task di prova, i
    cinque dello scenario sottotask e i due dello scenario fasi. Prima della verifica non esistono e dopo
    la pulizia nemmeno, ma tenerli fuori rende l'impronta confrontabile anche a
    verifica in corso, cioè quando lo scenario è in piedi: è l'unico modo perché
    «md5 PRIMA» e «md5 DOPO» misurino la stessa cosa.
    """
    ids = tuple(t[0] for t in TASK_PROVA) + TASK_SCENARIO + TASK_FASI
    session = get_session()
    try:
        blocchi = session.execute(text(
            "select dipendente_id, giorno, task_id, sottotask_id, ore, fonte "
            "from blocchi_ore where task_id not in :ids or task_id is null "
            "order by 1,2,3,4,5,6"), {"ids": ids}).all()
        consuntivi = session.execute(text(
            "select dipendente_id, settimana, task_id, ore_dichiarate, stato_dichiarato, nota "
            "from consuntivi where task_id not in :ids order by 1,2,3"), {"ids": ids}).all()
        # Anche i TASK, e non per zelo: salvare una dichiarazione PROPAGA lo
        # stato sul task (`salva_blocchi_settimana` → `modifica_task`). Se una
        # verifica scrivesse per sbaglio su un task vero, i blocchi tornerebbero
        # a posto con la pulizia e lo stato no: resterebbe cambiato in silenzio.
        task = session.execute(text(
            "select id, stato, dipendente_id, data_inizio, data_fine "
            "from task where id not in :ids order by 1"), {"ids": ids}).all()
        # E i DIPENDENTI, che nessuno script di prova deve toccare: sono persone
        # vere, referenziate e basta.
        dipendenti = session.execute(text(
            "select id, nome, ruolo_id, ore_sett, costo_ora, attivo from dipendenti order by 1")).all()
    finally:
        session.close()
    print(f"  blocchi_ore  {hashlib.md5(repr(blocchi).encode()).hexdigest()}  ({len(blocchi)} righe)")
    print(f"  consuntivi   {hashlib.md5(repr(consuntivi).encode()).hexdigest()}  ({len(consuntivi)} righe)")
    print(f"  task         {hashlib.md5(repr(task).encode()).hexdigest()}  ({len(task)} righe)")
    print(f"  dipendenti   {hashlib.md5(repr(dipendenti).encode()).hexdigest()}  ({len(dipendenti)} righe)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crea", action="store_true")
    ap.add_argument("--pulisci", action="store_true")
    ap.add_argument("--impronta", action="store_true")
    args = ap.parse_args()
    # L'ordine è PULISCI → CREA → IMPRONTA, non quello in cui arrivano le
    # opzioni: `--pulisci --crea` vuol dire «riparti da zero», e farlo al
    # contrario cancellerebbe i task appena creati.
    if args.pulisci:
        pulisci()
    if args.crea:
        crea()
    if args.impronta:
        impronta()
    if not (args.crea or args.pulisci or args.impronta):
        ap.print_help()
