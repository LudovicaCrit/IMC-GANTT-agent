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

Le stesse regole valgono su due seed:
  - `completo`: gantt_test com'è per tutta la sessione, «oggi» di venerdì;
  - `martedi`: uno schema a parte, caricato con «oggi» di martedì, dove le ore
    di mercoledì, giovedì e venerdì non devono esistere ancora.
"""

import json
import os
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.usefixtures("db_test")

SCHEMA_MARTEDI = "seed_martedi"


@pytest.fixture(scope="module")
def seed_martedi():
    """Migration e seed in uno schema a parte, con «oggi» di martedì."""
    import models
    from scripts.ricostruisci_db import applica_migration, carica_seed, lunedi_corrente

    def togli():
        with models.engine.begin() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar() == "gantt_test"
            conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA_MARTEDI} CASCADE"))

    lunedi = lunedi_corrente()
    martedi = lunedi + timedelta(days=1)
    togli()
    engine = None
    try:
        with models.engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {SCHEMA_MARTEDI}"))
        url = os.environ["DATABASE_URL"]
        applica_migration(url, schema=SCHEMA_MARTEDI)
        carica_seed(url, lunedi, martedi, schema=SCHEMA_MARTEDI)
        engine = create_engine(url, connect_args={"options": f"-c search_path={SCHEMA_MARTEDI}"})
        yield SimpleNamespace(sessione=sessionmaker(bind=engine), oggi=martedi, lunedi=lunedi)
    finally:
        if engine is not None:
            engine.dispose()
        togli()


@pytest.fixture(params=["completo", "martedi"])
def seed(request, oggi_del_seed):
    """Il seed da verificare: la fabbrica di sessioni, il suo «oggi» e il
    lunedì a cui ha spostato le date."""
    if request.param == "completo":
        from models import get_session
        return SimpleNamespace(sessione=get_session, oggi=oggi_del_seed,
                               lunedi=oggi_del_seed - timedelta(days=oggi_del_seed.weekday()))
    return request.getfixturevalue("seed_martedi")


def _una(seed, sql, **parametri):
    session = seed.sessione()
    try:
        return session.execute(text(sql), parametri).scalar()
    finally:
        session.close()


def test_nessun_giorno_sopra_le_24_ore(seed):
    assert _una(seed, """
        SELECT count(*) FROM (
            SELECT dipendente_id, giorno FROM blocchi_ore
            GROUP BY dipendente_id, giorno HAVING sum(ore) > 24) x
    """) == 0


def test_nessun_blocco_nel_fine_settimana(seed):
    assert _una(seed, "SELECT count(*) FROM blocchi_ore WHERE extract(isodow FROM giorno) > 5") == 0


def test_ogni_blocco_sta_nella_settimana_del_suo_consuntivo(seed):
    assert _una(seed, "SELECT count(*) FROM blocchi_ore") > 0
    assert _una(seed, """
        SELECT count(*) FROM blocchi_ore b
        LEFT JOIN consuntivi c
               ON c.task_id = b.task_id AND c.dipendente_id = b.dipendente_id
              AND c.settimana = date_trunc('week', b.giorno)::date
        WHERE c.id IS NULL
    """) == 0


def test_niente_dopo_oggi(seed):
    """Né ore, né consuntivi, né compilazioni dopo il giorno della fotografia."""
    assert _una(seed, "SELECT count(*) FROM blocchi_ore WHERE giorno > :oggi", oggi=seed.oggi) == 0
    assert _una(seed, "SELECT count(*) FROM consuntivi WHERE settimana > :oggi", oggi=seed.oggi) == 0
    assert _una(seed, "SELECT count(*) FROM consuntivi WHERE data_compilazione::date > :oggi",
                oggi=seed.oggi) == 0
    # Il taglio non svuota la settimana: fino a oggi le ore ci sono.
    assert _una(seed, "SELECT count(*) FROM blocchi_ore WHERE giorno BETWEEN :lun AND :oggi",
                lun=seed.lunedi, oggi=seed.oggi) > 0


def test_le_ore_del_seed_sono_compilate(seed):
    """Fonte `manuale`, come quelle della griglia: si possono modificare."""
    assert _una(seed, "SELECT count(*) FROM blocchi_ore WHERE fonte <> 'manuale'") == 0


def test_ore_positive_a_mezze_ore(seed):
    assert _una(seed, """
        SELECT count(*) FROM blocchi_ore
        WHERE ore <= 0 OR ore * 2 <> trunc(ore * 2)
    """) == 0


def _ore_del_json(seed):
    """Dal JSON del seed, con le settimane spostate come le sposta il seed:
    {(task, dipendente, settimana): ore}."""
    from seed import ANCORAGGIO, _SEED_DATA, lunedi_di

    spostamento = seed.lunedi - lunedi_di(ANCORAGGIO)
    dati = json.loads(_SEED_DATA.read_text(encoding="utf-8"))
    per_unita = defaultdict(Decimal)
    for r in dati["CONSUNTIVI"]:
        ore = Decimal(str(r["ore_dichiarate"]))
        lun = date.fromisoformat(r["settimana"]) + spostamento
        if ore > 0 and lun <= seed.oggi:
            per_unita[(r["task_id"], r["dipendente_id"], lun)] += ore
    return per_unita, {t["id"]: t["progetto_id"] for t in dati["TASKS"]}


def test_i_totali_restano_quelli_del_json(seed):
    """Sulle settimane concluse a «oggi» (venerdì compreso), per task e
    settimana e per progetto: spalmare le ore sui giorni non sposta un
    centesimo. Nella settimana in corso, se oggi non è venerdì, ci sono solo
    le ore fino a oggi: per nessuna unità più che nel JSON."""
    attesi, progetto_di = _ore_del_json(seed)
    session = seed.sessione()
    try:
        trovati = {(t, d, s): Decimal(o) for t, d, s, o in session.execute(text("""
            SELECT task_id, dipendente_id, date_trunc('week', giorno)::date, sum(ore)
            FROM blocchi_ore GROUP BY 1, 2, 3"""))}
    finally:
        session.close()

    def conclusa(lun):
        return lun + timedelta(days=4) <= seed.oggi

    assert ({k: v for k, v in trovati.items() if conclusa(k[2])}
            == {k: v for k, v in attesi.items() if conclusa(k[2])})
    per_progetto = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for (t, _, lun), ore in attesi.items():
        if conclusa(lun):
            per_progetto[progetto_di[t]][0] += ore
    for (t, _, lun), ore in trovati.items():
        if conclusa(lun):
            per_progetto[progetto_di[t]][1] += ore
    assert all(a == b for a, b in per_progetto.values()), dict(per_progetto)
    in_corso = {k: v for k, v in trovati.items() if not conclusa(k[2])}
    assert all(ore <= attesi[k] for k, ore in in_corso.items())


def test_le_regole_di_salva_blocchi_accettano_il_seed(seed):
    """`_valida_unita_blocchi` su ogni persona-settimana, con le unità che hanno
    ore e senza blocchi nuovi: N13, M8/M9 e N14 sui dati che ci sono."""
    from data_db_impl import ConsuntivoNonValido, _valida_unita_blocchi

    session = seed.sessione()
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
