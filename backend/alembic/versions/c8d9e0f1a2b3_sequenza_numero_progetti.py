"""Sequenza per il numero degli id dei progetti

Fino a qui l'id di un progetto nuovo si calcolava come «massimo degli id + 1»
(`_next_progetto_id`). Due difetti:
  - `progetti.id` è testo, e il massimo è quello alfabetico: con «PPROVA» o
    «PN03» presenti il massimo non è un numero e il calcolo ricadeva su
    «P001», che esiste già. Ogni creazione dal Wizard prendeva 409.
  - due creazioni contemporanee leggono lo stesso massimo e scelgono lo
    stesso id.

Una sequenza Postgres risolve entrambi: dà numeri unici anche in parallelo,
e non dipende dagli id di altra forma.

ALLINEAMENTO. La sequenza parte dal numero più alto fra gli id della forma
«P» seguita da sole cifre già presenti; gli altri (PC01, PN03, PPROVA…) si
ignorano. Il filtro sta nel WHERE, che Postgres applica prima dell'aggregato:
il cast a bigint non vede mai un id non numerico. Su una tabella vuota (un
database appena costruito dalle migration) parte da 1. La migration stampa il
numero che verrà dato al prossimo progetto.

La sequenza è dichiarata anche in models.py (SEQUENZA_NUMERO_PROGETTO), con
gli stessi parametri, così `create_all` e le migration producono lo stesso
schema.

IL DOWNGRADE elimina la sequenza, dopo aver contato che ce ne sia una e
stampato l'ultimo numero dato. Nessun dato dipende da lei: gli id già
assegnati restano nella tabella.
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

SEQUENZA = "progetti_numero_seq"


def upgrade() -> None:
    op.execute(f"CREATE SEQUENCE {SEQUENZA} AS bigint START WITH 1 MINVALUE 1")
    conn = op.get_bind()
    massimo = conn.execute(sa.text(
        "SELECT max(substr(id, 2)::bigint) FROM progetti WHERE id ~ '^P[0-9]+$'"
    )).scalar()
    if not massimo:
        conn.execute(sa.text(f"SELECT setval('{SEQUENZA}', 1, false)"))
    else:
        conn.execute(sa.text(f"SELECT setval('{SEQUENZA}', :n, true)"), {"n": massimo})
    prossimo = (massimo or 0) + 1
    print(f"✅ {SEQUENZA}: numero più alto presente {massimo}, "
          f"il prossimo progetto prenderà {prossimo}")


def downgrade() -> None:
    trovate = op.get_bind().execute(sa.text(
        "SELECT count(*), max(last_value) FROM pg_sequences "
        "WHERE schemaname = current_schema() AND sequencename = :nome"
    ), {"nome": SEQUENZA}).one()
    print(f"guardia: {SEQUENZA} presenti {trovate[0]}, ultimo numero dato {trovate[1]}")
    if trovate[0] != 1:
        raise RuntimeError(
            f"DOWNGRADE NON ESEGUITO: attesa una sequenza {SEQUENZA}, "
            f"trovate {trovate[0]}."
        )
    op.execute(f"DROP SEQUENCE {SEQUENZA}")
