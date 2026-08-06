"""sottotask dipendente_id — override dell'assegnatario

Aggiunge sottotask.dipendente_id: l'assegnatario PROPRIO del sottotask, in
override su quello del task padre.

Step 4 dei sottotask (motore ore-derivate). La colonna è un prerequisito del
motore: l'avanzamento di un sottotask lo dichiara il suo ASSEGNATARIO, quindi
il motore deve poter rispondere a «di chi è questo pezzo» — e la risposta non
può sempre essere «di chi ha il task», altrimenti un pezzo affidato a un altro
non avrebbe modo di essere dichiarato da chi lo fa davvero.

SEMANTICA DEL NULL — è informazione, non una lacuna
---------------------------------------------------
  NULL        → eredita da task.dipendente_id. È il caso NORMALE, non un dato
                mancante da riempire: il sottotask non ripartisce le persone,
                le eredita.
  valorizzato → override esplicito, «questo pezzo lo fa un altro». È
                l'eccezione, impostabile dal Cantiere.

La risoluzione è `sottotask.dipendente_id or task.dipendente_id`, e nel caso
normale è SEMPRE risolvibile: un task in lavorazione ha sempre un assegnatario,
garantito dalla guardia sull'ingresso in "In corso" (routes/tasks.py, Step 4
sotto-edit B). Senza quella guardia questa eredità potrebbe risolversi a NULL.

NESSUN BACKFILL, E NON PER PIGRIZIA
-----------------------------------
Al 06/08/2026 la tabella è vuota (0 righe: creata da f2a3b4c5d6e7, il CRUD
Cantiere non ne ha ancora scritte). Ma anche su un database dove i sottotask
esistessero già, il backfill sarebbe SBAGLIATO: copiare task.dipendente_id
dentro ogni riga trasformerebbe un'eredità viva in N override congelati, e alla
prima riassegnazione del task i sottotask resterebbero attaccati alla persona
vecchia. È lo stesso errore da cui veniamo — la tabella `assegnazioni`, recisa
oggi (sotto-edit A) proprio perché duplicava task.dipendente_id senza restare
allineata. Il NULL non è il valore da rimpiazzare: è quello giusto.

FORMA DELLA COLONNA
-------------------
Identica a task.dipendente_id: String(10), FK a dipendenti.id, nullable, senza
ondelete e senza relationship ORM. È la convenzione di questo progetto per la
colonna «chi fa il lavoro», e le due vanno lette insieme. Senza ondelete la FK
è RESTRICT: cancellare un dipendente con override attivi viene rifiutato dal
DB, che è il comportamento già in vigore per i task assegnati.

Il nome del vincolo, `sottotask_dipendente_id_fkey`, replica quello che
Postgres assegna da sé alle FK create dentro create_table (vedi
sottotask_task_id_fkey in f2a3b4c5d6e7): op.create_foreign_key esige un nome
esplicito, e inventarne uno diverso spezzerebbe l'uniformità dello schema.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-06 10:12:44.318702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_NAME = "sottotask_dipendente_id_fkey"


def upgrade() -> None:
    """
    1. ADD COLUMN nullable, senza server_default (il NULL è il valore giusto).
    2. FK verso dipendenti.id, senza ondelete (RESTRICT, come task.dipendente_id).
    """
    conn = op.get_bind()

    # ── 1. ADD COLUMN ───────────────────────────────────────────────────
    # Nessun server_default: a differenza di a3b4c5d6e7f8 (dove serviva a
    # riempire le righe prima di imporre NOT NULL) qui la colonna resta
    # nullable per sempre e il NULL è semanticamente pieno.
    op.add_column(
        'sottotask',
        sa.Column('dipendente_id', sa.String(length=10), nullable=True),
    )
    n_righe = conn.execute(sa.text("SELECT COUNT(*) FROM sottotask")).scalar() or 0
    print(f"✅ Colonna sottotask.dipendente_id aggiunta "
          f"({n_righe} sottotask in tabella, tutti in eredità dal task)")

    # ── 2. FOREIGN KEY ──────────────────────────────────────────────────
    op.create_foreign_key(
        FK_NAME, 'sottotask', 'dipendenti',
        ['dipendente_id'], ['id'],
    )
    print(f"✅ FK {FK_NAME} → dipendenti.id (RESTRICT, senza ondelete)")


def downgrade() -> None:
    """Drop della FK, poi della colonna.

    Perde gli override: tornando indietro ogni sottotask affidato a una persona
    diversa da quella del task torna indistinguibile dagli altri, cioè in
    eredità silenziosa. Le dichiarazioni in consuntivo_sottotask non vengono
    toccate — ma quelle scritte da un assegnatario in override resterebbero
    senza la ragione per cui era lui a scriverle.
    """
    op.drop_constraint(FK_NAME, 'sottotask', type_='foreignkey')
    print(f"✅ FK {FK_NAME} droppata")

    op.drop_column('sottotask', 'dipendente_id')
    print("✅ Colonna sottotask.dipendente_id droppata")
