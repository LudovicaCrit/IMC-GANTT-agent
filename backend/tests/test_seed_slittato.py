"""
Il seed che slitta alla settimana corrente racconta la stessa situazione.

Le date del seed si spostano di settimane intere al lunedì di riferimento, e i
test fissano «oggi» spostato delle stesse settimane. Il patto è che, visti da
«oggi», i dati siano gli stessi: qui lo si verifica sul calcolo più sensibile
al tempo, il semaforo, e sulla Home che lo riassume.

Come: in due schemi di gantt_test si caricano migration e seed due volte, una
senza spostamento (riferimento = il lunedì dell'ancoraggio) e una spostata al
lunedì corrente. Poi, con le sessioni dell'applicazione puntate su ciascuno
schema e `get_oggi` fissato sulla data d'ancoraggio corrispondente, si
calcolano:
  - il semaforo di tutti i progetti, con fasi, task e sottotask;
  - la dashboard della Home per un manager, un PM e un dipendente, con le date
    riportate indietro dello spostamento (le date cambiano, il resto no).
I due risultati devono essere identici.

Si controlla anche che lo spostamento rispetti le settimane: i consuntivi
restano sul lunedì, e ogni blocco sta dentro la settimana del suo consuntivo.
"""

import os
import re
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from conftest import sostituisci_get_oggi

SCHEMA_FERMO = "seed_fermo"
SCHEMA_SPOSTATO = "seed_spostato"
UTENTI_HOME = (
    SimpleNamespace(ruolo_app="manager", dipendente_id=None),
    SimpleNamespace(ruolo_app="pm", dipendente_id="D002"),
    SimpleNamespace(ruolo_app="user", dipendente_id="D004"),
)
DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _riporta_indietro(valore, spostamento):
    """Il valore con ogni data spostata indietro di `spostamento`."""
    if isinstance(valore, dict):
        return {k: _riporta_indietro(v, spostamento) for k, v in valore.items()}
    if isinstance(valore, (list, tuple)):
        return [_riporta_indietro(v, spostamento) for v in valore]
    if isinstance(valore, datetime):
        return valore - spostamento
    if isinstance(valore, date):
        return valore - spostamento
    if isinstance(valore, str) and DATA_ISO.match(valore):
        return (date.fromisoformat(valore) - spostamento).isoformat()
    return valore


@pytest.fixture(scope="module")
def due_seed():
    """I due schemi caricati: {schema: (lunedì di riferimento, oggi)}. Tolti
    alla fine, per nome esatto."""
    import models
    from scripts.ricostruisci_db import applica_migration, carica_seed, lunedi_corrente
    from seed import ANCORAGGIO, lunedi_di, settimane_di_spostamento

    fermo = lunedi_di(ANCORAGGIO)
    spostato = lunedi_corrente()
    if spostato == fermo:          # nella settimana dell'ancoraggio non si sposterebbe niente
        spostato += timedelta(weeks=1)
    riferimenti = {SCHEMA_FERMO: fermo, SCHEMA_SPOSTATO: spostato}

    def togli_schemi():
        with models.engine.begin() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar() == "gantt_test"
            for schema in riferimenti:
                conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    togli_schemi()
    try:
        with models.engine.begin() as conn:
            for schema in riferimenti:
                conn.execute(text(f"CREATE SCHEMA {schema}"))
        url = os.environ["DATABASE_URL"]
        for schema, lunedi in riferimenti.items():
            applica_migration(url, schema=schema)
            carica_seed(url, lunedi, schema=schema)
        yield {schema: (lunedi, ANCORAGGIO + timedelta(weeks=settimane_di_spostamento(lunedi)))
               for schema, lunedi in riferimenti.items()}
    finally:
        togli_schemi()


def _nello_schema(schema):
    return create_engine(os.environ["DATABASE_URL"],
                         connect_args={"options": f"-c search_path={schema}"})


def _calcola(schema, oggi):
    """Semaforo e Home calcolati dal codice dell'applicazione sullo schema dato,
    con «oggi» fissato."""
    import models
    from data import semaforo_progetti
    from routes.home import dashboard

    engine = _nello_schema(schema)
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(models, "SessionLocal", sessionmaker(bind=engine))
            sostituisci_get_oggi(mp, oggi)
            with engine.connect() as conn:
                ids = [pid for (pid,) in conn.execute(text("SELECT id FROM progetti ORDER BY id"))]
            semaforo = semaforo_progetti(ids, oggi=oggi)
            home = [dashboard(current_user=u) for u in UTENTI_HOME]
        return ids, semaforo, home
    finally:
        engine.dispose()


def test_semaforo_e_home_uguali_col_seed_spostato(due_seed):
    (_, oggi_fermo), (_, oggi_spostato) = due_seed[SCHEMA_FERMO], due_seed[SCHEMA_SPOSTATO]
    spostamento = oggi_spostato - oggi_fermo
    assert spostamento.days % 7 == 0 and spostamento.days != 0

    ids_f, semaforo_f, home_f = _calcola(SCHEMA_FERMO, oggi_fermo)
    ids_s, semaforo_s, home_s = _calcola(SCHEMA_SPOSTATO, oggi_spostato)

    assert ids_f == ids_s
    assert len(semaforo_f) == len(ids_f) > 0
    assert semaforo_s == semaforo_f
    assert _riporta_indietro(home_s, spostamento) == home_f
    # Il confronto ha qualcosa da confrontare: non tutto verde o vuoto.
    colori = {n["semaforo"] for n in semaforo_f.values()}
    assert len(colori) > 1, colori


@pytest.mark.parametrize("schema", [SCHEMA_FERMO, SCHEMA_SPOSTATO])
def test_le_settimane_restano_allineate(due_seed, schema):
    engine = _nello_schema(schema)
    try:
        with engine.connect() as conn:
            consuntivi, consuntivi_non_lunedi = conn.execute(text("""
                SELECT count(*), count(*) FILTER (WHERE extract(isodow FROM settimana) <> 1)
                FROM consuntivi""")).one()
            blocchi, blocchi_fuori_settimana = conn.execute(text("""
                SELECT count(*), count(*) FILTER (WHERE c.id IS NULL)
                FROM blocchi_ore b
                LEFT JOIN consuntivi c
                       ON c.task_id = b.task_id AND c.dipendente_id = b.dipendente_id
                      AND b.giorno BETWEEN c.settimana AND c.settimana + 6""")).one()
    finally:
        engine.dispose()
    assert consuntivi > 0 and blocchi > 0
    assert consuntivi_non_lunedi == 0
    assert blocchi_fuori_settimana == 0
