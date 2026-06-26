"""bollettino_economico — archivio storico della marginalità (Bollettino)

Decisione architetturale (26/06/2026): SAL e dimensione economica sono archivi
SEPARATI — non si mescolano contenuti di pagine diverse. Il SAL fotografa la
STRUTTURA del GANTT (sal_snapshot); il Bollettino economico fotografa
l'ECONOMIA di un progetto in un istante (margini + grezzi che li producono).

Struttura IDENTICA a sal_snapshot (stesso pattern immutabile/autocontenuto,
storage JSONB): cambia solo cosa contiene il JSONB `stato`.

COLONNE:
  - id              PK
  - progetto_id     FK→progetti.id, NOT NULL, SENZA CASCADE (storia protetta)
  - data_snapshot   timestamp del consolidamento (server_default now())
  - consolidato_da  id dipendente come stringa, SENZA FK (durabilità: lo
                    snapshot resta leggibile anche se la persona viene rimossa)
  - nota            nota opzionale
  - stato           JSONB: l'economia del progetto (margini calcolati + grezzi)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bollettino_economico',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('progetto_id', sa.String(length=10), nullable=False),
        sa.Column('data_snapshot', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('consolidato_da', sa.String(length=10), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('stato', postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ['progetto_id'], ['progetti.id'],
            name='fk_bollettino_economico_progetto_id',
            # niente ondelete: RESTRICT → la storia non si cancella col progetto.
        ),
    )
    op.create_index(
        'ix_bollettino_economico_progetto_id', 'bollettino_economico', ['progetto_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_bollettino_economico_progetto_id', table_name='bollettino_economico')
    op.drop_table('bollettino_economico')
