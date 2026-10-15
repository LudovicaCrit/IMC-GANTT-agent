"""task.fase_id: ON DELETE da SET NULL a RESTRICT, come dichiara models.py

Il vincolo `task_fase_id_fkey` nasce nella migration iniziale (e733e23ae7a1)
con `ondelete='SET NULL'`, quando `task.fase_id` era ancora nullable. La
migration b2c3d4e5f6a7 (Step 2.1 D1) ha reso la colonna NOT NULL ma non ha
toccato la FK, e `models.py` è passato a `ondelete="RESTRICT"`. Un database
costruito dalle migration aveva quindi SET NULL, uno creato con `create_all`
RESTRICT: è la differenza trovata confrontando gantt_test con gantt_db.

PERCHÉ RESTRICT
───────────────
Su una colonna NOT NULL, SET NULL è una regola che non può mai riuscire:
cancellare una fase che ha dei task chiederebbe al database di mettere NULL
in una colonna che il NULL lo rifiuta, e la cancellazione fallirebbe con un
errore di NOT NULL che parla d'altro. RESTRICT dice la stessa cosa in modo
vero: una fase con dei task non si cancella finché i task esistono. È anche
la regola che l'applicazione già segue: `DELETE /api/fasi/{id}` conta i task
prima di cancellare, e il Wizard (PUT /completo) cancella le fasi passando
dall'ORM, che con `cascade="all, delete-orphan"` su `Fase.task` toglie prima
i task e poi la fase, quindi RESTRICT non lo blocca.

Nessun dato cambia: si ricrea solo la regola della FK, con lo stesso nome.
Prima di agire la migration legge la definizione attuale e la stampa; se il
vincolo non esiste si ferma.

IL DOWNGRADE ripristina SET NULL, cioè lo stato esatto prodotto dalle
migration precedenti.
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None

TABELLA = "task"
VINCOLO = "task_fase_id_fkey"


def _definizione_attuale():
    return op.get_bind().execute(sa.text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'task'::regclass AND conname = :nome"
    ), {"nome": VINCOLO}).scalar()


def _ricrea(ondelete):
    prima = _definizione_attuale()
    print(f"guardia: {TABELLA}.{VINCOLO} prima → {prima}")
    if prima is None:
        raise RuntimeError(
            f"MIGRATION NON ESEGUITA: il vincolo {VINCOLO} su {TABELLA} non "
            f"esiste. Lo schema non è quello atteso: verificare il nome della "
            f"FK di task.fase_id prima di proseguire."
        )
    op.drop_constraint(VINCOLO, TABELLA, type_="foreignkey")
    op.create_foreign_key(
        VINCOLO, TABELLA, "fasi", ["fase_id"], ["id"], ondelete=ondelete,
    )
    print(f"✅ {TABELLA}.{VINCOLO} dopo → {_definizione_attuale()}")


def upgrade() -> None:
    _ricrea("RESTRICT")


def downgrade() -> None:
    _ricrea("SET NULL")
