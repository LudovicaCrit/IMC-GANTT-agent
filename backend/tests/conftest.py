"""Configurazione comune dei test.

QUALE DATABASE
I test non usano mai il database di sviluppo. Prima di qualunque import del
backend, qui si legge DATABASE_URL_TEST (dall'ambiente o da backend/.env) e la
si copia in DATABASE_URL. I moduli del backend leggono DATABASE_URL al loro
primo import (`models` crea l'engine lì, `data` si collega subito) e chiamano
`load_dotenv()`, che NON sovrascrive una variabile già presente: trovano quindi
l'URL di test e non quello del .env. pytest carica questo file prima di
raccogliere i moduli di test, quindi prima di ogni loro import.

LA GUARDIA
Se DATABASE_URL_TEST manca, o punta a un database che non si chiama
esattamente `gantt_test`, la sessione si ferma qui, prima di qualunque
connessione. Vale anche per i test puri: una configurazione sbagliata si
corregge, non si aggira.

IMPORT DEL BACKEND
I moduli dell'applicazione stanno direttamente in backend/ e si importano
«piatti» (`from models import …`): backend/ va in testa a sys.path, ricavato
dalla posizione di questo file, da qualunque cartella si lanci pytest.
"""

import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parent.parent
DB_TEST = "gantt_test"

load_dotenv(BACKEND / ".env")   # non sovrascrive: l'ambiente vince sul file

_url_test = os.environ.get("DATABASE_URL_TEST", "").strip()
if not _url_test:
    pytest.exit(
        "GUARDIA: DATABASE_URL_TEST non impostata (né nell'ambiente né in "
        "backend/.env). I test non partono senza un database di test.",
        returncode=3,
    )
try:
    _nome_db = make_url(_url_test).database
except Exception as e:
    pytest.exit(f"GUARDIA: DATABASE_URL_TEST non è un URL valido ({e}).",
                returncode=3)
if _nome_db != DB_TEST:
    pytest.exit(
        f"GUARDIA: DATABASE_URL_TEST punta al database «{_nome_db}», non a "
        f"«{DB_TEST}». I test scrivono sul database: si fermano qui.",
        returncode=3,
    )
if "models" in sys.modules:
    pytest.exit("GUARDIA: `models` era già importato prima del conftest: "
                "il suo engine potrebbe puntare a un altro database.",
                returncode=3)

os.environ["DATABASE_URL"] = _url_test

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def sostituisci_get_oggi(mp, giorno):
    """Fa restituire a `get_oggi()` il giorno dato (a mezzanotte: get_oggi
    restituisce un datetime), per la durata di `mp`. I moduli fanno
    `from utils import get_oggi`, cioè tengono un riferimento proprio alla
    funzione: si sostituisce in `utils` e in ogni modulo già importato che
    tiene quella in uso ora, e chi viene importato dopo la riceve già
    sostituita. Il codice che legge `date.today()` per conto suo non è coperto."""
    import utils

    in_uso = utils.get_oggi

    def get_oggi_fisso():
        return datetime.combine(giorno, time())

    mp.setattr(utils, "get_oggi", get_oggi_fisso)
    for modulo in list(sys.modules.values()):
        try:
            tiene_quella_in_uso = getattr(modulo, "get_oggi", None) is in_uso
        except Exception:
            continue
        if tiene_quella_in_uso:
            mp.setattr(modulo, "get_oggi", get_oggi_fisso)


@pytest.fixture(scope="session")
def db_test():
    """gantt_test ricostruito da zero, una volta per sessione, con la stessa
    procedura di chi lavora: `scripts/ricostruisci_db.py` (schema public
    svuotato, `alembic upgrade head`, seed con le date slittate al lunedì
    corrente). La usano solo i test che toccano il database; i test puri non
    la chiedono e girano anche senza database.

    Per tutta la sessione `get_oggi()` restituisce la data d'ancoraggio del
    seed spostata delle stesse settimane delle date: i dati stanno rispetto a
    «oggi» sempre nello stesso punto, qualunque sia il giorno in cui girano i
    test. Restituisce quella data, che i test usano come «oggi».
    """
    from sqlalchemy import text
    import models
    from scripts.ricostruisci_db import lunedi_corrente, ricostruisci
    from seed import ANCORAGGIO, settimane_di_spostamento

    if models.engine.url.database != DB_TEST:
        pytest.exit(f"GUARDIA: l'engine punta a «{models.engine.url.database}».",
                    returncode=3)

    models.engine.dispose()
    lunedi = lunedi_corrente()
    try:
        ricostruisci(os.environ["DATABASE_URL"], conferma=DB_TEST, lunedi_riferimento=lunedi)
    except Exception as e:
        pytest.fail(f"ricostruzione di {DB_TEST} fallita: {e}")

    with models.engine.connect() as conn:
        assert conn.execute(text("SELECT current_database()")).scalar() == DB_TEST
        assert conn.execute(text("SELECT count(*) FROM dipendenti")).scalar() > 0, \
            "seed non caricato su gantt_test"

    oggi_del_seed = ANCORAGGIO + timedelta(weeks=settimane_di_spostamento(lunedi))
    with pytest.MonkeyPatch.context() as mp:
        sostituisci_get_oggi(mp, oggi_del_seed)
        yield oggi_del_seed


@pytest.fixture(scope="session")
def oggi_del_seed(db_test):
    """La data «oggi» dei test su database: quella del seed (vedi db_test)."""
    return db_test
