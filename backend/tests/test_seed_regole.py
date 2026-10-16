"""
Il seed rispetta le regole dell'applicazione.

I blocchi del seed non passano da /salva-blocchi: li scrive `seed.py`
direttamente. Qui si controlla che, se fossero passati di lì, sarebbero stati
accettati, e che spalmare le ore sui giorni non abbia cambiato nessun totale.

Le regole che vivono nello strato dati si verificano con la stessa funzione di
/salva-blocchi, `_valida_unita_blocchi`, chiamata per ogni persona e settimana
senza blocchi nuovi: così controlla quelli che ci sono già.
  - N13: ogni unità con ore è del dipendente (assegnata a lui, non chiusa);
  - M8/M9: nessuna ora su un task scomposto in sottotask;
  - N14: nessun giorno sopra le 24 ore.
Quelle che vivono nella route o nel DTO, dove non c'è una funzione da
chiamare, si verificano in SQL: giorni da lunedì a venerdì della settimana
(N2), niente ore nel futuro rispetto a «oggi» (N1), ore positive e con al più
due decimali (N3, N4); più la granularità della mezz'ora del seed.
"""

import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from models import get_session

pytestmark = pytest.mark.usefixtures("db_test")


def _una(sql, **parametri):
    session = get_session()
    try:
        return session.execute(text(sql), parametri).scalar()
    finally:
        session.close()


def test_nessun_giorno_sopra_le_24_ore():
    assert _una("""
        SELECT count(*) FROM (
            SELECT dipendente_id, giorno FROM blocchi_ore
            GROUP BY dipendente_id, giorno HAVING sum(ore) > 24) x
    """) == 0


def test_nessun_blocco_nel_fine_settimana():
    assert _una("SELECT count(*) FROM blocchi_ore WHERE extract(isodow FROM giorno) > 5") == 0


def test_ogni_blocco_sta_nella_settimana_del_suo_consuntivo():
    assert _una("SELECT count(*) FROM blocchi_ore") > 0
    assert _una("""
        SELECT count(*) FROM blocchi_ore b
        LEFT JOIN consuntivi c
               ON c.task_id = b.task_id AND c.dipendente_id = b.dipendente_id
              AND c.settimana = date_trunc('week', b.giorno)::date
        WHERE c.id IS NULL
    """) == 0


def test_niente_ore_nel_futuro(oggi_del_seed):
    assert _una("SELECT count(*) FROM blocchi_ore WHERE giorno > :oggi",
                oggi=oggi_del_seed) == 0


def test_ore_positive_a_mezze_ore():
    assert _una("""
        SELECT count(*) FROM blocchi_ore
        WHERE ore <= 0 OR ore * 2 <> trunc(ore * 2)
    """) == 0


def _ore_del_json(oggi_del_seed):
    """Dal JSON del seed, con le settimane spostate come le sposta il seed:
    {(task, dipendente, settimana): ore} e {progetto: ore}."""
    from seed import ANCORAGGIO, _SEED_DATA

    spostamento = oggi_del_seed - ANCORAGGIO
    dati = json.loads(_SEED_DATA.read_text(encoding="utf-8"))
    progetto_di = {t["id"]: t["progetto_id"] for t in dati["TASKS"]}
    per_unita, per_progetto = defaultdict(Decimal), defaultdict(Decimal)
    for r in dati["CONSUNTIVI"]:
        ore = Decimal(str(r["ore_dichiarate"]))
        if ore <= 0:
            continue
        lun = date.fromisoformat(r["settimana"]) + spostamento
        per_unita[(r["task_id"], r["dipendente_id"], lun)] += ore
        per_progetto[progetto_di[r["task_id"]]] += ore
    return per_unita, per_progetto


def test_i_totali_restano_quelli_del_json(oggi_del_seed):
    """Per task e settimana, e per progetto: spalmare le ore sui giorni non
    sposta un centesimo."""
    attesi_unita, attesi_progetto = _ore_del_json(oggi_del_seed)
    session = get_session()
    try:
        unita = {(t, d, s): Decimal(o) for t, d, s, o in session.execute(text("""
            SELECT task_id, dipendente_id, date_trunc('week', giorno)::date, sum(ore)
            FROM blocchi_ore WHERE fonte = 'storico' GROUP BY 1, 2, 3"""))}
        progetto = {p: Decimal(o) for p, o in session.execute(text("""
            SELECT t.progetto_id, sum(b.ore) FROM blocchi_ore b
            JOIN task t ON t.id = b.task_id
            WHERE b.fonte = 'storico' GROUP BY 1"""))}
    finally:
        session.close()
    assert unita == dict(attesi_unita)
    assert progetto == dict(attesi_progetto)


def test_le_regole_di_salva_blocchi_accettano_il_seed():
    """`_valida_unita_blocchi` su ogni persona-settimana, con le unità che hanno
    ore e senza blocchi nuovi: N13, M8/M9 e N14 sui dati che ci sono."""
    from data_db_impl import ConsuntivoNonValido, _valida_unita_blocchi

    session = get_session()
    try:
        unita_per_settimana = defaultdict(set)
        for dip, lun, task_id in session.execute(text("""
                SELECT DISTINCT dipendente_id, date_trunc('week', giorno)::date, task_id
                FROM blocchi_ore ORDER BY 1, 2, 3""")):
            unita_per_settimana[(dip, lun)].add(task_id)
        assert unita_per_settimana

        errori = []
        for (dip, lun), task_ids in sorted(unita_per_settimana.items()):
            unita = [{"tipo": "task", "id": t, "blocchi": [], "tocca_stato": False,
                      "tocca_nota": False, "nota": None} for t in sorted(task_ids)]
            try:
                _valida_unita_blocchi(session, dip, lun, unita)
            except ConsuntivoNonValido as e:
                errori.append(f"{dip} {lun}: {e}")
    finally:
        session.close()
    assert not errori, "\n".join(errori[:20])
