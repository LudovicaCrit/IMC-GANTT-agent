#!/usr/bin/env python
"""
scenario_sottotask.py — il mondo-scomposto, in carne e ossa.

PERCHÉ ESISTE. Il database di sviluppo ha ZERO sottotask. Metà della
Consuntivazione — il ramo dei pezzi in `task_settimana_dipendente`, la
risoluzione dell'assegnatario (C2), N21 sui pezzi, la mutua esclusione M8/M9 in
`tipo_unita_per_task`, e nella griglia l'intero ramo `costruisciGruppi` che
costruisce intestazione + righe-pezzo — non è mai stata vista funzionare su dati
veri. È codice scritto, commentato, validato a tavolino e mai acceso. Questo
script lo accende: crea uno scenario SINTETICO, marchiato e cancellabile in un
colpo, in cui ognuno di quei rami ha un caso che lo percorre.

Non è una verifica: è la SCENOGRAFIA su cui una verifica (o un paio d'occhi)
può guardare. Lo spec `sottotask-griglia.spec.js` ci gira sopra.

COM'È MARCHIATO. Tutto pende da UN progetto, `PPROVA`, nome «[PROVA] …».
Cancellare quel progetto porta via l'intero scenario per cascata; lo script lo
fa comunque a mano, tabella per tabella, per poter dire quante righe ha tolto.
I DIPENDENTI sono quelli VERI e si toccano solo per riferimento: Helena (D004,
l'utente `user` del seed, «io» nella griglia) e Roberto (D002, il collega
proprietario del task nel caso C2). Nessun dipendente viene creato o modificato.

I QUATTRO CASI, scelti per coprire i rami e non per fare numero:

  T950 — SCOMPOSTO NORMALE. Tre pezzi di Helena: due senza `dipendente_id`
         (eredità dal task, il caso normale) e uno con l'override esplicito a
         D004. Il task porta anche un'ora messa PRIMA della scomposizione (M8),
         che nella griglia diventa la riga in sola lettura «ore sul task, prima
         della scomposizione». Su un pezzo c'è già una dichiarazione con ore:
         serve a vedere una riga-pezzo che si RIAPRE piena, non solo vuota.

  T951 — C2: IL TASK È DI UN COLLEGA, UN PEZZO È MIO. Task di Roberto (D002),
         due pezzi: uno suo (eredità) e uno con override a Helena. Dalla
         griglia di Helena il task deve comparire — non è suo, ci arriva dal
         ramo `task_con_pezzi_miei` — col pezzo di Roberto in sola lettura («di
         un collega») e il proprio dichiarabile. È il ramo che senza dati non
         si è mai potuto guardare.

  T952 — PEZZO ANNULLATO CON ORE (N21 sui pezzi). Due pezzi, entrambi
         Annullati, ma su uno Helena aveva già messo delle ore prima che il PM
         lo togliesse dal piano. Quel pezzo resta VISIBILE in sola lettura —
         le sue ore stanno nei totali, e una riga che non si vede
         contraddirebbe il totale. L'altro annullato, senza ore, non compare.
         E poiché nessun pezzo è più vivo, per M9 /me dichiara il task
         `modificabile: true` — è tornato un'unità di lavoro.
         ⚠ LA GRIGLIA OGGI NON LO MOSTRA COSÌ: `costruisciGruppi` entra nel ramo
         scomposto per il solo fatto che la lista dei pezzi non è vuota (ci sta
         dentro l'annullato-con-ore) e non disegna nessuna riga compilabile per
         il task. Ore dichiarabili dal backend, non dichiarabili dalla pagina.
         È il buco che accendere questo scenario ha fatto vedere; sta nel
         frontend e il test che lo aspetta è `test.fixme` in
         `sottotask-griglia.spec.js`.

  T953 — TUTTI I PEZZI ANNULLATI, NIENTE ORE (M9 puro). Due pezzi annullati e
         nessuna ora da nessuna parte: il payload di /me non porta affatto la
         chiave `sottotask`, e il task si compila come un task qualunque.
         Differisce da T952 per UNA cosa sola — le ore sul pezzo annullato — ed
         è quella differenza a isolare il ramo N21.

LE ORE NON SI INSERISCONO A MANO. Si scrivono chiamando
`salva_blocchi_settimana`, la stessa funzione che usa /salva-blocchi, così i
blocchi, la vista `ore_settimanali` e la doppia scrittura su
`consuntivi.ore_dichiarate` (N9) restano coerenti come in produzione. E
nell'ORDINE in cui succederebbe davvero: le ore sul task prima di scomporlo, le
ore sul pezzo prima di annullarlo. Scritte dopo, la validazione le rifiuterebbe
— giustamente.

Uso:
    python e2e/scenario_sottotask.py --crea
    python e2e/scenario_sottotask.py --cancella
    python e2e/scenario_sottotask.py --stato       # cosa c'è adesso
"""
import sys
import os
import argparse
from datetime import date, timedelta
from decimal import Decimal

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADICE, "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(RADICE, "backend", ".env"))

from data_db_impl import get_session, _lunedi, salva_blocchi_settimana  # noqa: E402
from models import (  # noqa: E402
    Progetto, Fase, Task, Sottotask, Consuntivo, ConsuntivoSottotask, BloccoOre,
)

PROGETTO = "PPROVA"
NOME_PROGETTO = "[PROVA] Scenario sottotask"
IO = "D004"          # Helena Ullah — l'utente `user` del seed
COLLEGA = "D002"     # Roberto Pezzuto — proprietario del task nel caso C2

TASK = ("T950", "T951", "T952", "T953")


def _settimana():
    """La settimana corrente, e i giorni su cui è lecito posare delle ore.

    Lunedì e martedì: sono passati o al più oggi in ogni giorno della settimana
    lavorativa, e `/salva-blocchi` rifiuta le ore nel futuro (N1). Uno scenario
    che si crea di lunedì non deve nascere già invalido.
    """
    lun = _lunedi()
    return lun, lun, lun + timedelta(days=1)


def crea():
    lun, giorno1, giorno2 = _settimana()
    session = get_session()
    try:
        if session.query(Progetto).filter(Progetto.id == PROGETTO).first():
            print(f"  {PROGETTO} c'è già — lancia prima --cancella")
            return

        # La finestra copre settimana corrente E precedente: lo scenario si
        # guarda da entrambe senza doverlo ricreare.
        inizio, fine = lun - timedelta(days=7), lun + timedelta(days=13)

        session.add(Progetto(
            id=PROGETTO, nome=NOME_PROGETTO, cliente="[PROVA]",
            stato="In esecuzione", tipologia="ordinario",
            data_inizio=inizio, data_fine=fine,
            descrizione="Scenario sintetico per il mondo-scomposto. "
                        "Si cancella con e2e/scenario_sottotask.py --cancella.",
        ))
        fase = Fase(progetto_id=PROGETTO, nome="[PROVA] Fase unica", ordine=1,
                    data_inizio=inizio, data_fine=fine)
        session.add(fase)
        session.flush()          # serve `fase.id` per i task

        def task(tid, nome, dipendente):
            session.add(Task(
                id=tid, progetto_id=PROGETTO, fase_id=fase.id, nome=nome,
                stato="In corso", dipendente_id=dipendente,
                data_inizio=inizio, data_fine=fine,
                ore_stimate=16, ore_pianificate=16,
            ))

        task("T950", "[PROVA] 1 · Task scomposto normale", IO)
        task("T951", "[PROVA] 2 · Task di un collega con un pezzo mio (C2)", COLLEGA)
        task("T952", "[PROVA] 3 · Pezzo annullato con ore (N21)", IO)
        task("T953", "[PROVA] 4 · Tutti i pezzi annullati (M9)", IO)
        session.commit()
        print(f"  {PROGETTO} + 4 task creati")
    finally:
        session.close()

    # ── T950: PRIMA l'ora sul task, POI la scomposizione ─────────────────
    # È l'ordine della vita reale (M8: «ore messe prima della scomposizione») ed
    # è anche l'unico che la validazione accetta — su un task già scomposto
    # `_motivo_non_modificabile` rifiuterebbe le ore sul task.
    salva_blocchi_settimana(IO, lun, [{
        "tipo": "task", "id": "T950",
        "blocchi": [(giorno1, Decimal("1.0"))],
        "tocca_stato": True, "stato": "In corso",
        "tocca_nota": False, "nota": None,
        "tocca_residuo": False, "residuo": None,
        "presa_visione": None,
    }])
    print("  T950: 1h sul task (prima della scomposizione, M8)")

    session = get_session()
    try:
        def pezzo(tid, nome, ordine, dipendente=None, stato="Da iniziare", ore=None):
            s = Sottotask(task_id=tid, nome=nome, ordine=ordine,
                          dipendente_id=dipendente, stato=stato, ore_stimate=ore)
            session.add(s)
            return s

        p_t950 = [
            pezzo("T950", "[PROVA] Analisi del tracciato", 1, ore=6),
            pezzo("T950", "[PROVA] Stesura del modulo", 2, ore=6),
            # Override esplicito a sé stessa: risolve a Helena come i due NULL
            # sopra, ma per una strada diversa.
            pezzo("T950", "[PROVA] Collaudo con il cliente", 3, dipendente=IO, ore=4),
        ]
        p_t951 = [
            pezzo("T951", "[PROVA] Parte di Roberto", 1, ore=8),
            pezzo("T951", "[PROVA] Parte affidata a Helena", 2, dipendente=IO, ore=8),
        ]
        p_t952 = [
            pezzo("T952", "[PROVA] Pezzo poi annullato, con ore", 1, ore=5),
            pezzo("T952", "[PROVA] Pezzo poi annullato, senza ore", 2, ore=5),
        ]
        p_t953 = [
            pezzo("T953", "[PROVA] Pezzo annullato A", 1, ore=4),
            pezzo("T953", "[PROVA] Pezzo annullato B", 2, ore=4),
        ]
        session.commit()
        ids = {
            "t950": [p.id for p in p_t950],
            "t951": [p.id for p in p_t951],
            "t952": [p.id for p in p_t952],
            "t953": [p.id for p in p_t953],
        }
        print(f"  9 pezzi creati: {ids}")
    finally:
        session.close()

    # ── Una riga-pezzo che si riapre PIENA ───────────────────────────────
    salva_blocchi_settimana(IO, lun, [{
        "tipo": "sottotask", "id": ids["t950"][1],
        "blocchi": [(giorno1, Decimal("2.0")), (giorno2, Decimal("1.5"))],
        "tocca_stato": True, "stato": "In corso",
        "tocca_nota": True, "nota": "Prima metà del modulo scritta.",
        "tocca_residuo": True, "residuo": 3.5,
        "presa_visione": None,
    }])
    print("  T950/pezzo 2: 3,5h + stato + nota + resta")

    # ── T952: le ore sul pezzo PRIMA che il PM lo annulli ────────────────
    salva_blocchi_settimana(IO, lun, [{
        "tipo": "sottotask", "id": ids["t952"][0],
        "blocchi": [(giorno2, Decimal("1.5"))],
        "tocca_stato": True, "stato": "In corso",
        "tocca_nota": False, "nota": None,
        "tocca_residuo": False, "residuo": None,
        "presa_visione": None,
    }])

    session = get_session()
    try:
        for sid in ids["t952"] + ids["t953"]:
            session.query(Sottotask).filter(Sottotask.id == sid).update({"stato": "Annullato"})
        session.commit()
        print("  T952 e T953: tutti i pezzi passati ad Annullato "
              "(su T952 uno porta 1,5h già dichiarate)")
    finally:
        session.close()

    stato()


def cancella():
    session = get_session()
    try:
        sotto = [r[0] for r in session.query(Sottotask.id)
                 .filter(Sottotask.task_id.in_(TASK)).all()]
        n_cs = 0
        if sotto:
            n_cs = (session.query(ConsuntivoSottotask)
                    .filter(ConsuntivoSottotask.sottotask_id.in_(sotto))
                    .delete(synchronize_session=False))
        n_b = (session.query(BloccoOre).filter(BloccoOre.task_id.in_(TASK))
               .delete(synchronize_session=False))
        n_c = (session.query(Consuntivo).filter(Consuntivo.task_id.in_(TASK))
               .delete(synchronize_session=False))
        n_s = (session.query(Sottotask).filter(Sottotask.task_id.in_(TASK))
               .delete(synchronize_session=False))
        n_t = (session.query(Task).filter(Task.progetto_id == PROGETTO)
               .delete(synchronize_session=False))
        n_f = (session.query(Fase).filter(Fase.progetto_id == PROGETTO)
               .delete(synchronize_session=False))
        n_p = (session.query(Progetto).filter(Progetto.id == PROGETTO)
               .delete(synchronize_session=False))
        session.commit()
        print(f"  tolti: {n_p} progetto, {n_f} fasi, {n_t} task, {n_s} pezzi, "
              f"{n_b} blocchi, {n_c} consuntivi, {n_cs} dichiarazioni-pezzo")
    finally:
        session.close()


def stato():
    """Cosa c'è adesso, e nessun dipendente toccato: la conta serve a dire che
    lo scenario è tutto qui dentro e che fuori non ha lasciato niente."""
    session = get_session()
    try:
        prog = session.query(Progetto).filter(Progetto.id == PROGETTO).first()
        print(f"  progetto {PROGETTO}: {'c’è' if prog else 'assente'}")
        if prog:
            for t in session.query(Task).filter(Task.progetto_id == PROGETTO).order_by(Task.id):
                pezzi = (session.query(Sottotask).filter(Sottotask.task_id == t.id)
                         .order_by(Sottotask.ordine).all())
                ore_task = (session.query(BloccoOre)
                            .filter(BloccoOre.task_id == t.id,
                                    BloccoOre.sottotask_id.is_(None)).all())
                print(f"    {t.id} ({t.dipendente_id}) {t.nome}"
                      + (f"  [{sum(float(b.ore) for b in ore_task)}h sul task]" if ore_task else ""))
                for p in pezzi:
                    ore = (session.query(BloccoOre)
                           .filter(BloccoOre.sottotask_id == p.id).all())
                    tot = sum(float(b.ore) for b in ore)
                    print(f"       #{p.id} {p.stato:12} "
                          f"{'di ' + p.dipendente_id if p.dipendente_id else 'eredita'}"
                          f"{f'  {tot}h' if tot else ''}  {p.nome}")
        print(f"  sottotask in tutto il DB: {session.query(Sottotask).count()}")
        print(f"  blocchi_ore in tutto il DB: {session.query(BloccoOre).count()}")
    finally:
        session.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crea", action="store_true", help="crea lo scenario")
    ap.add_argument("--cancella", action="store_true", help="lo toglie tutto")
    ap.add_argument("--stato", action="store_true", help="dice cosa c'è adesso")
    args = ap.parse_args()
    # ORDINE ESPLICITO — cancella, poi crea, poi racconta. Non quello in cui
    # arrivano le opzioni: `--cancella --crea` vuol dire «rifallo da capo», e
    # eseguirlo al contrario butterebbe via ciò che ha appena creato.
    if args.cancella:
        cancella()
    if args.crea:
        crea()
    if args.stato:
        stato()
    if not (args.crea or args.cancella or args.stato):
        ap.print_help()
