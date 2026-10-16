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
  T901  su P008 — progetto su cui Helena non ha nessun task del seed, quindi
        mai attivo per lei in nessuna settimana (con P011, dove ha T112, lo
        diventava appena T112 entrava in griglia). Il nome viene prima di quello
        di P002 in ordine alfabetico: serve all'ordinamento (dev'essere sotto
        P002 anche se alfabeticamente verrebbe prima) e al caso «solo stato,
        niente ore», che deve far comparire l'avvertenza.

Per il «banner attività senza spiegazione» — servono invece task DENTRO la
settimana, cioè righe che la griglia carica già, su cui nessuno ha ancora detto
niente. Non si possono usare quelli veri: la verifica ci scrive sopra, e le ore
vere non si toccano. Sono due perché i modi di spiegare un'attività sono due, e
vanno provati separatamente:

  T902  lo si spiega con lo STATO (Bloccato + nota), senza ore.
  T903  lo si spiega mettendoci le ORE.

Per i confini della lista di «aggiungi riga» — prima erano task veri del seed,
ma le loro date sono fisse e col passare delle settimane cambiavano categoria
(un task «già in griglia» usciva dall'orizzonte, uno «da offrire» entrava in
griglia). Questi le hanno relative, e restano ciò che il test dichiara:

  T904  su P008 — da OFFRIRE: fuori dalla griglia, dentro l'orizzonte. È quello
        che il test aggiunge per sbaglio e poi toglie.
  T905  GIÀ IN GRIGLIA perché la sua finestra interseca la settimana, ed è
        dentro l'orizzonte: se non fosse offerto, è per la griglia.
  T906  GIÀ IN GRIGLIA perché scaduto e ancora vivo, dentro l'orizzonte.
  T907  FUORI ORIZZONTE: Completato, finito prima del lunedì-30. Non è in
        griglia, quindi se non è offerto è per l'orizzonte.

Per la «settimana intonsa» del banner — serve una persona che nella settimana
abbia righe ma non abbia ancora dichiarato niente. Il seed riempie le settimane
di tutti quelli che lavorano, quindi non la si cerca nei dati: la si costruisce.

  T908  dentro la settimana, assegnato a un dipendente scelto con una query
        (attivo, senza un utente, senza consuntivi né blocchi nella settimana),
        che per la verifica riceve un utente di prova, UTENTE_INTONSA. Il
        dipendente non si tocca: si aggiungono solo il suo task e il suo accesso.

`--pulisci` rimuove i task di prova E tutto ciò che le verifiche hanno scritto su
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
from models import Task, BloccoOre, Consuntivo, Dipendente, Utente  # noqa: E402
from auth import hash_password  # noqa: E402
from scenario_sottotask import TASK as TASK_SCENARIO  # noqa: E402
from scenario_fasi import TASK as TASK_FASI  # noqa: E402

DIPENDENTE = "D004"          # Helena Ullah — l'utente `user` del seed

# Le date si calcolano dal lunedì della settimana in cui si lancia la verifica,
# non sono scritte: con date fisse il calendario sposta i task da una parte
# all'altra della regola che il test vuole provare.
#
# T902, T903 — DENTRO la settimana: devono intersecarla, o la griglia non li
# caricherebbe.
# T900, T901 — FUORI dalla griglia ma DENTRO l'orizzonte della lista «Ho
# lavorato su altro». Fuori dalla griglia vuol dire che non intersecano la
# settimana (inizio dopo la domenica) e non sono scaduti (la griglia carica
# anche i task scaduti e ancora vivi). L'orizzonte va dal lunedì-30 alla
# domenica+30 (AggiungiRiga.jsx). Iniziano due settimane avanti e non una: se
# la verifica parte domenica sera e passa la mezzanotte, la settimana corrente
# scatta di sette giorni e un task che iniziasse il lunedì dopo ci finirebbe
# dentro.
_OGGI = date.today()
_LUN = _OGGI - timedelta(days=_OGGI.weekday())

#
# T904-T907 — i confini della lista di «aggiungi riga». T904 come T900/T901
# (inizio due settimane avanti). T905 copre la settimana corrente e la
# successiva, così la interseca anche se la verifica passa la mezzanotte di
# domenica. T906 è finito prima del lunedì ed è ancora vivo: la griglia lo carica
# come scaduto, e la sua fine (lunedì-8) resta dentro l'orizzonte anche quando
# la settimana scatta di sette giorni (lunedì-23). T907 è Completato e finito al
# lunedì-45: fuori dall'orizzonte (lunedì-30) anche dopo lo scatto (lunedì-23).
_DA_INIZIARE = "Da iniziare"

TASK_PROVA = [
    # id     progetto  fase  nome                                   inizio      fine      stato
    ("T900", "P002", 8, "[prova e2e] Ritocco integrazione fuori piano", _LUN + timedelta(days=15), _LUN + timedelta(days=22), _DA_INIZIARE),
    ("T901", "P008", 31, "[prova e2e] Sopralluogo non pianificato", _LUN + timedelta(days=14), _LUN + timedelta(days=20), _DA_INIZIARE),
    ("T902", "P002", 8, "[prova e2e] Da spiegare con lo stato", _LUN - timedelta(days=7), _LUN + timedelta(days=13), _DA_INIZIARE),
    ("T903", "P002", 8, "[prova e2e] Da spiegare con le ore", _LUN - timedelta(days=7), _LUN + timedelta(days=13), _DA_INIZIARE),
    ("T904", "P008", 31, "[prova e2e] Da offrire nella lista", _LUN + timedelta(days=16), _LUN + timedelta(days=25), _DA_INIZIARE),
    ("T905", "P002", 8, "[prova e2e] In griglia dentro la settimana", _LUN - timedelta(days=7), _LUN + timedelta(days=13), _DA_INIZIARE),
    ("T906", "P002", 8, "[prova e2e] In griglia perché scaduto", _LUN - timedelta(days=21), _LUN - timedelta(days=8), _DA_INIZIARE),
    ("T907", "P002", 8, "[prova e2e] Completato fuori orizzonte", _LUN - timedelta(days=60), _LUN - timedelta(days=45), "Completato"),
]

# La settimana intonsa: lo stesso indirizzo e la stessa password stanno in
# utenti.js, da dove apparecchia.js fa il login. Utente usa-e-getta, tolto da
# `--pulisci` per indirizzo esatto.
TASK_INTONSA = ("T908", "P002", 8, "[prova e2e] Settimana intonsa", _LUN - timedelta(days=7), _LUN + timedelta(days=13), _DA_INIZIARE)
UTENTE_INTONSA = ("e2e-settimana-intonsa@prova.invalid", "prova-e2e-intonsa")


def _dipendente_senza_dichiarazioni(session):
    """Il primo dipendente attivo, per nome, senza un utente e senza consuntivi
    né blocchi nella settimana corrente."""
    fine = _LUN + timedelta(days=6)
    return session.query(Dipendente).filter(
        Dipendente.attivo.is_(True),
        ~session.query(Utente).filter(Utente.dipendente_id == Dipendente.id).exists(),
        ~session.query(Consuntivo).filter(
            Consuntivo.dipendente_id == Dipendente.id,
            Consuntivo.settimana == _LUN).exists(),
        ~session.query(BloccoOre).filter(
            BloccoOre.dipendente_id == Dipendente.id,
            BloccoOre.giorno.between(_LUN, fine)).exists(),
    ).order_by(Dipendente.nome, Dipendente.id).first()


def _crea_settimana_intonsa(session):
    tid, pid, fase_id, nome, inizio, fine, stato = TASK_INTONSA
    if session.query(Task).filter(Task.id == tid).first():
        print(f"  {tid} c'è già")
        return
    dip = _dipendente_senza_dichiarazioni(session)
    if dip is None:
        raise SystemExit("nessun dipendente attivo senza utente e senza dichiarazioni "
                         "in questa settimana: la settimana intonsa non si può costruire")
    session.add(Task(id=tid, progetto_id=pid, fase_id=fase_id, nome=nome, stato=stato,
                     dipendente_id=dip.id, data_inizio=inizio, data_fine=fine,
                     ore_stimate=8, ore_pianificate=8))
    email, password = UTENTE_INTONSA
    session.add(Utente(email=email, password_hash=hash_password(password),
                       ruolo_app="user", dipendente_id=dip.id))
    print(f"  {tid} creato per {dip.nome}, con l'utente {email}")


def crea():
    session = get_session()
    try:
        for tid, pid, fase_id, nome, inizio, fine, stato in TASK_PROVA:
            if session.query(Task).filter(Task.id == tid).first():
                print(f"  {tid} c'è già")
                continue
            session.add(Task(
                id=tid, progetto_id=pid, fase_id=fase_id, nome=nome,
                stato=stato, dipendente_id=DIPENDENTE,
                data_inizio=inizio, data_fine=fine,
                ore_stimate=8, ore_pianificate=8,
            ))
            print(f"  {tid} creato ({pid}, {inizio} → {fine})")
        _crea_settimana_intonsa(session)
        session.commit()
    finally:
        session.close()


def pulisci():
    ids = [t[0] for t in TASK_PROVA] + [TASK_INTONSA[0]]
    session = get_session()
    try:
        n_b = session.query(BloccoOre).filter(BloccoOre.task_id.in_(ids)).delete(synchronize_session=False)
        n_c = session.query(Consuntivo).filter(Consuntivo.task_id.in_(ids)).delete(synchronize_session=False)
        n_t = session.query(Task).filter(Task.id.in_(ids)).delete(synchronize_session=False)
        n_u = session.query(Utente).filter(Utente.email == UTENTE_INTONSA[0]).delete(synchronize_session=False)
        session.commit()
        print(f"  tolti: {n_t} task, {n_b} blocchi, {n_c} consuntivi, {n_u} utenti")
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
    ids = tuple(t[0] for t in TASK_PROVA) + (TASK_INTONSA[0],) + TASK_SCENARIO + TASK_FASI
    session = get_session()
    try:
        blocchi = session.execute(text(
            "select dipendente_id, giorno, task_id, sottotask_id, ore, fonte "
            "from blocchi_ore where task_id not in :ids or task_id is null "
            "order by 1,2,3,4,5,6"), {"ids": ids}).all()
        # SOLO LE COLONNE SUPERSTITI. `ore_dichiarate` stava in questa lista
        # ed è uscita col passo 5.6: un'impronta che la includesse cambierebbe
        # per il drop stesso, cioè misurerebbe la migration invece dei dati.
        # Le ore non spariscono dal conto — sono in `blocchi_ore`, la prima
        # impronta qui sopra.
        consuntivi = session.execute(text(
            "select dipendente_id, settimana, task_id, compilato, stato_dichiarato, nota "
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
