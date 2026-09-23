#!/usr/bin/env python
"""
scenario_fasi.py — due fasi per provare la guardia del ritorno a «Da iniziare».

PERCHÉ ESISTE. `PATCH /api/fasi/{id}` con `cascade` rifiuta di riportare una
fase da «In corso» a «Da iniziare» se sui suoi task ci sono ore dichiarate: non
si può fingere che il lavoro non sia cominciato. Per provarla servono due fasi
che differiscano per UNA cosa sola — le ore — e nel database di sviluppo non ce
ne sono: le fasi vere stanno quasi tutte in altri stati, e cambiare stato a una
fase vera per provare una guardia vuol dire scrivere sui dati di qualcun altro.

  PFASI / [PROVA] Fase CON ore     — «In corso», un task (T960) con 4h vere
  PFASI / [PROVA] Fase SENZA ore   — «In corso», un task (T961) e nessuna ora

Il primo PATCH deve prendere 409, il secondo 200. Prima del fix del 23/09/2026
prendevano tutti e due 200, perché la guardia leggeva `Task.ore_consumate` — una
colonna che nessuno aggiorna più e che vale 0 ovunque. `--stato` lo mostra:
stampa le ore vere accanto alla colonna-copia, e si vedono divergere.

Le ore si scrivono con `salva_blocchi_settimana`, la stessa funzione di
/salva-blocchi: la guardia legge la vista `ore_settimanali`, e la vista si nutre
dei blocchi. Scriverli a mano proverebbe la guardia contro dati che nessun
percorso reale produce.

Il dipendente è quello vero (Helena, D004), solo referenziato.

Uso:
    python e2e/scenario_fasi.py --crea
    python e2e/scenario_fasi.py --cancella
    python e2e/scenario_fasi.py --stato
"""
import sys
import os
import argparse
from datetime import timedelta
from decimal import Decimal

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADICE, "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(RADICE, "backend", ".env"))

from sqlalchemy import func  # noqa: E402
from data_db_impl import get_session, _lunedi, salva_blocchi_settimana  # noqa: E402
from models import (  # noqa: E402
    Progetto, Fase, Task, Consuntivo, BloccoOre, OreSettimanali,
)

PROGETTO = "PFASI"
NOME_PROGETTO = "[PROVA] Scenario fasi"
IO = "D004"                       # Helena Ullah
TASK = ("T960", "T961")
CON_ORE, SENZA_ORE = TASK

NOME_FASE_CON = "[PROVA] Fase CON ore"
NOME_FASE_SENZA = "[PROVA] Fase SENZA ore"


def crea():
    lun = _lunedi()
    session = get_session()
    try:
        if session.query(Progetto).filter(Progetto.id == PROGETTO).first():
            print(f"  {PROGETTO} c'è già — lancia prima --cancella")
            return

        inizio, fine = lun - timedelta(days=7), lun + timedelta(days=13)
        session.add(Progetto(
            id=PROGETTO, nome=NOME_PROGETTO, cliente="[PROVA]",
            stato="In esecuzione", tipologia="ordinario",
            data_inizio=inizio, data_fine=fine,
            descrizione="Scenario sintetico per la guardia del ritorno a «Da "
                        "iniziare». Si cancella con e2e/scenario_fasi.py --cancella.",
        ))
        # Le due fasi nascono «In corso»: è lo stato da cui la guardia sorveglia
        # il ritorno indietro, e crearle così evita di doverle muovere prima.
        fasi = {}
        for nome in (NOME_FASE_CON, NOME_FASE_SENZA):
            f = Fase(progetto_id=PROGETTO, nome=nome, ordine=len(fasi) + 1,
                     stato="In corso", data_inizio=inizio, data_fine=fine)
            session.add(f)
            session.flush()
            fasi[nome] = f.id

        for tid, nome_fase, nome in (
            (CON_ORE, NOME_FASE_CON, "[PROVA] Task con ore dichiarate"),
            (SENZA_ORE, NOME_FASE_SENZA, "[PROVA] Task senza ore"),
        ):
            session.add(Task(
                id=tid, progetto_id=PROGETTO, fase_id=fasi[nome_fase], nome=nome,
                stato="In corso", dipendente_id=IO,
                data_inizio=inizio, data_fine=fine,
                ore_stimate=8, ore_pianificate=8,
            ))
        session.commit()
        print(f"  {PROGETTO}: 2 fasi «In corso» + 2 task creati "
              f"(fase con ore: {fasi[NOME_FASE_CON]}, senza: {fasi[NOME_FASE_SENZA]})")
    finally:
        session.close()

    salva_blocchi_settimana(IO, lun, [{
        "tipo": "task", "id": CON_ORE,
        "blocchi": [(lun, Decimal("4.0"))],
        "tocca_stato": True, "stato": "In corso",
        "tocca_nota": False, "nota": None,
        "tocca_residuo": False, "residuo": None,
        "presa_visione": None,
    }])
    print(f"  {CON_ORE}: 4h dichiarate (via salva_blocchi_settimana)")
    stato()


def cancella():
    session = get_session()
    try:
        n_b = (session.query(BloccoOre).filter(BloccoOre.task_id.in_(TASK))
               .delete(synchronize_session=False))
        n_c = (session.query(Consuntivo).filter(Consuntivo.task_id.in_(TASK))
               .delete(synchronize_session=False))
        n_t = (session.query(Task).filter(Task.progetto_id == PROGETTO)
               .delete(synchronize_session=False))
        n_f = (session.query(Fase).filter(Fase.progetto_id == PROGETTO)
               .delete(synchronize_session=False))
        n_p = (session.query(Progetto).filter(Progetto.id == PROGETTO)
               .delete(synchronize_session=False))
        session.commit()
        print(f"  tolti: {n_p} progetto, {n_f} fasi, {n_t} task, "
              f"{n_b} blocchi, {n_c} consuntivi")
    finally:
        session.close()


def stato():
    """Le ore VERE accanto alla colonna-copia, che è il punto di tutto."""
    session = get_session()
    try:
        prog = session.query(Progetto).filter(Progetto.id == PROGETTO).first()
        print(f"  progetto {PROGETTO}: {'c’è' if prog else 'assente'}")
        if not prog:
            return
        reali = dict(
            session.query(OreSettimanali.c.task_id, func.sum(OreSettimanali.c.ore))
            .filter(OreSettimanali.c.task_id.in_(TASK))
            .group_by(OreSettimanali.c.task_id).all()
        )
        for f in (session.query(Fase).filter(Fase.progetto_id == PROGETTO)
                  .order_by(Fase.ordine).all()):
            print(f"    fase {f.id} «{f.nome}» [{f.stato}]")
            for t in (session.query(Task).filter(Task.fase_id == f.id)
                      .order_by(Task.id).all()):
                print(f"       {t.id}  ore vere (vista): {float(reali.get(t.id) or 0):4.1f}h"
                      f"   Task.ore_consumate (colonna-copia): {float(t.ore_consumate or 0):4.1f}h")
    finally:
        session.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crea", action="store_true")
    ap.add_argument("--cancella", action="store_true")
    ap.add_argument("--stato", action="store_true")
    args = ap.parse_args()
    # Ordine esplicito: cancella → crea → racconta, non quello delle opzioni.
    if args.cancella:
        cancella()
    if args.crea:
        crea()
    if args.stato:
        stato()
    if not (args.crea or args.cancella or args.stato):
        ap.print_help()
