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

import json
import os
import subprocess
import sys
from datetime import date, datetime, time
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


def _esegui(*argomenti):
    """Lancia un comando Python del backend in un processo figlio, con lo
    stesso ambiente (quindi DATABASE_URL = gantt_test). Processo separato
    perché alembic riconfigura il logging alla sua maniera, e quel cambiamento
    non deve ricadere sui test."""
    esito = subprocess.run(
        [sys.executable, *argomenti], cwd=BACKEND, env=os.environ.copy(),
        capture_output=True, text=True, encoding="utf-8",
    )
    if esito.returncode != 0:
        pytest.fail(f"`{' '.join(argomenti)}` fallito:\n{esito.stdout}\n{esito.stderr}")


def _data_del_seed():
    """La data a cui il seed è ancorato (`_meta.ancorato_a` di seed_data.json).
    Le date del seed sono assolute: «oggi», per i test su questi dati, è
    questo giorno, non quello dell'orologio."""
    with open(BACKEND / "seed_data.json", encoding="utf-8") as f:
        return date.fromisoformat(json.load(f)["_meta"]["ancorato_a"])


@pytest.fixture(scope="session")
def db_test():
    """gantt_test ricostruito da zero, una volta per sessione: schema public
    svuotato, `alembic upgrade head`, seed. La usano solo i test che toccano
    il database; i test puri non la chiedono e girano anche senza database.

    Lo schema si ricrea com'era (proprietario pg_database_owner, USAGE a
    tutti) e il database non si droppa mai: vicacrit non potrebbe ricrearlo.

    Per tutta la sessione `utils.get_oggi()` restituisce la data del seed (a
    mezzanotte: get_oggi restituisce un datetime). I moduli fanno
    `from utils import get_oggi`, cioè tengono un riferimento proprio alla
    funzione: si sostituisce in `utils` e in ogni modulo già importato che la
    tiene, e chi viene importato dopo la riceve già sostituita. Il codice che
    legge `date.today()` per conto suo non è coperto da questo patch.
    Restituisce la data, che i test usano come «oggi».
    """
    from sqlalchemy import text
    import models

    if models.engine.url.database != DB_TEST:
        pytest.exit(f"GUARDIA: l'engine punta a «{models.engine.url.database}».",
                    returncode=3)

    with models.engine.begin() as conn:
        assert conn.execute(text("SELECT current_database()")).scalar() == DB_TEST
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public AUTHORIZATION pg_database_owner"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))
    models.engine.dispose()

    _esegui("-m", "alembic", "upgrade", "head")
    _esegui("seed.py")

    with models.engine.connect() as conn:
        assert conn.execute(text("SELECT current_database()")).scalar() == DB_TEST
        assert conn.execute(text("SELECT count(*) FROM dipendenti")).scalar() > 0, \
            "seed non caricato su gantt_test"

    import utils
    oggi_del_seed = _data_del_seed()
    originale = utils.get_oggi

    def get_oggi_del_seed():
        return datetime.combine(oggi_del_seed, time())

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(utils, "get_oggi", get_oggi_del_seed)
        for modulo in list(sys.modules.values()):
            try:
                tiene_originale = getattr(modulo, "get_oggi", None) is originale
            except Exception:
                continue
            if tiene_originale:
                mp.setattr(modulo, "get_oggi", get_oggi_del_seed)
        yield oggi_del_seed


@pytest.fixture(scope="session")
def oggi_del_seed(db_test):
    """La data «oggi» dei test su database: quella del seed (vedi db_test)."""
    return db_test
