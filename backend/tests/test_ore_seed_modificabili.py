"""
Le ore del seed nella settimana corrente si possono modificare dalla griglia.

Il seed scrive le sue ore con fonte `manuale`, come la griglia. Con la fonte
`storico` la sostituzione di /salva-blocchi non le toccava (FONTI_SOSTITUIBILI)
e N23 rifiutava un'ora manuale sullo stesso giorno: chi apriva la settimana
corrente trovava le ore del seed in sola lettura.

Qui, sulla settimana di «oggi», un task che ha già ore del seed: si cambia un
giorno, se ne aggiunge uno nuovo, si salva con `salva_blocchi_settimana` (la
stessa funzione della route), e si rilegge. Alla fine si rimettono i blocchi
di prima con lo stesso salvataggio. Solo le ore: stato e nota non si toccano,
quindi né il consuntivo né il task cambiano.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from models import get_session

pytestmark = pytest.mark.usefixtures("db_test")


def _blocchi(dip, task_id, lun):
    session = get_session()
    try:
        return {g: (Decimal(o), f) for g, o, f in session.execute(text("""
            SELECT giorno, ore, fonte FROM blocchi_ore
            WHERE dipendente_id = :d AND task_id = :t AND sottotask_id IS NULL
              AND giorno BETWEEN :lun AND :lun + 6 ORDER BY giorno"""),
            {"d": dip, "t": task_id, "lun": lun})}
    finally:
        session.close()


def _unita(task_id, blocchi):
    return [{"tipo": "task", "id": task_id, "blocchi": sorted(blocchi.items()),
             "tocca_stato": False, "tocca_nota": False, "tocca_residuo": False,
             "presa_visione": None}]


def test_si_modificano_e_si_aggiungono_ore_su_un_task_con_ore_del_seed(oggi_del_seed):
    from data_db_impl import salva_blocchi_settimana

    lun = oggi_del_seed - timedelta(days=oggi_del_seed.weekday())
    session = get_session()
    try:
        # Un task con ore del seed questa settimana, e almeno un giorno feriale
        # libero fino a oggi: il primo per dipendente e task.
        scelta = session.execute(text("""
            SELECT dipendente_id, task_id FROM blocchi_ore
            WHERE giorno BETWEEN :lun AND :oggi AND sottotask_id IS NULL
            GROUP BY dipendente_id, task_id
            HAVING count(*) < (:oggi - :lun) + 1
            ORDER BY dipendente_id, task_id LIMIT 1"""),
            {"lun": lun, "oggi": oggi_del_seed}).one_or_none()
    finally:
        session.close()
    assert scelta is not None, "nessun task con ore del seed e un giorno libero"
    dip, task_id = scelta

    prima = _blocchi(dip, task_id, lun)
    assert prima and all(f == "manuale" for _, f in prima.values())
    originali = {g: o for g, (o, _) in prima.items()}
    giorno_cambiato = min(originali)
    giorno_nuovo = next(lun + timedelta(days=i) for i in range((oggi_del_seed - lun).days + 1)
                        if lun + timedelta(days=i) not in originali)
    nuovi = dict(originali)
    nuovi[giorno_cambiato] += Decimal("0.5")
    nuovi[giorno_nuovo] = Decimal("1.0")

    try:
        salva_blocchi_settimana(dip, lun, _unita(task_id, nuovi))
        dopo = _blocchi(dip, task_id, lun)
        assert {g: o for g, (o, _) in dopo.items()} == nuovi
        assert all(f == "manuale" for _, f in dopo.values())
    finally:
        salva_blocchi_settimana(dip, lun, _unita(task_id, originali))
    assert {g: o for g, (o, _) in _blocchi(dip, task_id, lun).items()} == originali
