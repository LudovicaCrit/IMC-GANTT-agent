"""
IMC-Group GANTT Agent — Data Layer (porta d'ingresso)

Ri-esporta l'implementazione Postgres (`data_db_impl`) per tutta
l'applicazione: le route non importano `data_db_impl` direttamente, importano
da qui. Non c'è una seconda implementazione fra cui scegliere — POSTGRES È
OBBLIGATORIO.

FINO AL 07/08/2026 QUI C'ERA UN DISPATCHER, e vale la pena sapere perché non
c'è più. Contava le righe di `dipendenti` dentro un `try/except Exception:
pass`; se la conta non riusciva — per QUALSIASI motivo — ripiegava sui
DataFrame sintetici di un secondo modulo (`data_legacy.py`, cancellato il
giorno stesso). Tre guasti diversi (Postgres spento, credenziali sbagliate,
migration non applicate) finivano tutti sullo stesso messaggio «⚠ Database non
disponibile — fallback in memoria (esegui: python seed.py)», che è il rimedio
giusto per un quarto caso e inutile per quei tre. E il fallback non funzionava
nemmeno: quel modulo copriva 13 dei 35 nomi che l'app importa da qui, quindi
l'avvio moriva comunque — ma con un `ImportError: cannot import name
'margini_economia'`, che accusa il file sbagliato. Un guasto di infrastruttura
si presentava come un bug applicativo.

I dati sintetici che quel modulo conteneva vivono ora in `seed_data.json`, letto
dal solo `seed.py`: sono impalcatura di sviluppo, non un ramo del runtime.

I TRE CASI, ORA DISTINTI (misurati, non ipotizzati):

  1. Postgres IRRAGGIUNGIBILE — server spento, porta chiusa, credenziali
     errate, database inesistente. `OperationalError` alla connessione.
     → DatabaseIrraggiungibile, dopo i tentativi. L'app non parte, e dice
       dove ha provato e per quanto.

  2. Database RAGGIUNGIBILE MA SENZA SCHEMA — succede solo prima di
     `alembic upgrade head`. Verificato che nessun flusso legittimo passa di
     qui: `alembic/env.py` importa `models` e non questo modulo, e `seed.py`
     legge da `seed_data.json`, quindi l'app viene avviata (README §Primo
     avvio, passo 8) quando migration e seed sono già passati.
     → SchemaAssente, subito, con il comando da eseguire. Meglio fermarsi
     qui che schiantarsi più avanti su una query, dentro una route, come 500
     opaco.

  3. Schema presente, TABELLE VUOTE — nessun errore, si prosegue. Non è un
     guasto: è lo stato normale di una prima installazione in PRODUZIONE, dove
     le migration girano ma il seed no (i dati sintetici sono impalcatura da
     sviluppo). Un'app appena installata ha zero dipendenti finché qualcuno non
     li inserisce, e serve liste vuote — non dati finti.

Il controllo è ESPLICITO e non affidato al tipo di eccezione: si tenta la
connessione, poi si chiede all'inspector se lo schema c'è. Dedurre il caso
dalla classe dell'eccezione funzionerebbe, ma legherebbe il messaggio a un
dettaglio interno di psycopg2.

Il controllo si fa all'AVVIO dell'applicazione, non all'import: lo chiama il
lifespan di FastAPI (main.py) attraverso `attendi_database`. Importare questo
modulo non tocca il database (CLAUDE.md, regola 13): così `import main`, la
raccolta dei test e gli script funzionano anche a database spento o vuoto, e
uvicorn non parte se all'avvio il database non c'è. È la differenza fra
accorgersi di un Postgres spento al boot e accorgersene al primo click di un
utente.

I TENTATIVI servono al caso del servizio Windows che parte prima di Postgres:
senza una dipendenza dichiarata fra i servizi l'ordine non è garantito, e
Postgres al boot è pronto in qualche secondo, qualche decina dopo uno
spegnimento brusco (ripassa il WAL). Si ritenta solo il caso 1: lo schema
assente non arriva aspettando.
"""

import logging
import time

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from models import engine

logger = logging.getLogger(__name__)

# Dodici tentativi a cinque secondi l'uno dall'altro: circa un minuto, che
# copre un avvio normale di Postgres. Oltre, un errore chiaro serve più di
# un'attesa lunga, e il riavvio automatico del servizio fa il resto.
TENTATIVI_AVVIO = 12
ATTESA_FRA_TENTATIVI_S = 5

# Tabella-sentinella per stabilire se lo schema è stato applicato. Vale
# qualunque tabella del modello; `dipendenti` è fra le più antiche e non è mai
# stata rinominata. Se un domani sparisse, questo controllo mentirebbe
# dicendo «manca lo schema» — l'alternativa (confrontare `alembic_version`
# con l'head atteso) sarebbe più precisa ma farebbe fallire l'avvio anche per
# una migration semplicemente in ritardo, che è più rigido di quanto serva.
_TABELLA_SENTINELLA = "dipendenti"


class DatabaseIrraggiungibile(RuntimeError):
    """Caso 1: Postgres non risponde. Aspettando può arrivare."""


class SchemaAssente(RuntimeError):
    """Caso 2: Postgres risponde ma lo schema non c'è. Aspettando non arriva."""


def verifica_database():
    """Postgres deve esserci e avere lo schema. Un tentativo solo.

    I due messaggi sono diversi di proposito: i rimedi sono opposti — avviare
    il database contro applicare le migration — e un messaggio unico per
    entrambi è esattamente il difetto che questo modulo aveva prima.
    """
    # `render_as_string(hide_password=True)` invece dell'URL grezza: il
    # messaggio finisce nei log, e la password no.
    dove = engine.url.render_as_string(hide_password=True)

    try:
        with engine.connect():
            pass
    except OperationalError as e:
        raise DatabaseIrraggiungibile(
            f"Postgres non raggiungibile a {dove}: {e.orig}\n"
            f"L'applicazione richiede un database Postgres attivo. Verifica "
            f"che il servizio PostgreSQL sia avviato e che DATABASE_URL in "
            f"backend/.env sia corretta."
        ) from e

    if not inspect(engine).has_table(_TABELLA_SENTINELLA):
        raise SchemaAssente(
            f"Database raggiungibile a {dove} ma senza schema "
            f"(tabella '{_TABELLA_SENTINELLA}' assente).\n"
            f"Esegui le migration prima di avviare l'applicazione:\n"
            f"    cd backend && alembic upgrade head"
        )


def attendi_database(tentativi=TENTATIVI_AVVIO, attesa_s=ATTESA_FRA_TENTATIVI_S,
                     verifica=verifica_database, dormi=time.sleep):
    """`verifica_database` con qualche tentativo, per l'avvio dell'applicazione.

    Se Postgres non risponde si riprova fino a `tentativi` volte, `attesa_s`
    secondi l'una dall'altra; poi l'errore dice quanto si è aspettato e cosa
    controllare. Se manca lo schema si solleva subito. `verifica` e `dormi`
    sono parametri perché i test possano provare i tentativi senza Postgres e
    senza aspettare."""
    for n in range(1, tentativi + 1):
        try:
            verifica()
            return
        except DatabaseIrraggiungibile as e:
            if n == tentativi:
                raise DatabaseIrraggiungibile(
                    f"{e}\nRinuncio dopo {tentativi} tentativi in circa "
                    f"{(tentativi - 1) * attesa_s} secondi."
                ) from e
            logger.warning("Postgres non risponde (tentativo %d di %d), riprovo fra %d s.",
                           n, tentativi, attesa_s)
            dormi(attesa_s)


# Nessun ramo alternativo: c'è una sola implementazione.
from data_db_impl import *  # noqa: E402,F401,F403
