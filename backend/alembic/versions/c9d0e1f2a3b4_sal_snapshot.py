"""sal_snapshot — tabella snapshot storico del GANTT (SAL)

DESIGN_SAL.md (26/06/2026). Il SAL è una fotografia IMMUTABILE e AUTOCONTENUTA
dello stato completo di un progetto in un istante, per consultazione storica
(PM) e nutrimento futuro dell'IA-Archivio.

STORAGE — JSONB (decisione di design, DESIGN_SAL §3 + scelta storage):
lo stato completo (progetto + fasi + task + ore + date + dipendenze tipizzate)
è serializzato in UNA colonna JSONB `stato`. NON tabelle relazionali speculari:
lo snapshot è un blocco autocontenuto, resta leggibile anche se il modello
evolve, e i consumatori lo leggono come blocco (non con query relazionali).

COLONNE = metadati dello snapshot; il contenuto-progetto vive nel JSONB:
  - id              PK
  - progetto_id     a quale progetto si riferisce (FK, vedi nota sotto)
  - data_snapshot   quando è stato consolidato (timestamp)
  - consolidato_da  chi l'ha consolidato (id dipendente, vedi nota sotto)
  - nota            nota opzionale del PM ("perché questo SAL")
  - stato           JSONB: lo stato completo del progetto nel formato concordato

DURABILITÀ (scelte motivate, l'archivio non deve perdere storia):
  - progetto_id è FK ma SENZA ondelete CASCADE: un progetto con snapshot non
    può essere cancellato a sorpresa portandosi via la storia (default RESTRICT).
  - consolidato_da è una semplice stringa (id dipendente) SENZA FK: lo snapshot
    resta integro e leggibile anche se quel dipendente venisse rimosso, coerente
    con i nomi denormalizzati dentro il JSONB.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sal_snapshot',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('progetto_id', sa.String(length=10), nullable=False),
        sa.Column('data_snapshot', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('consolidato_da', sa.String(length=10), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('stato', postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ['progetto_id'], ['progetti.id'],
            name='fk_sal_snapshot_progetto_id',
            # niente ondelete: RESTRICT di default → la storia non si cancella
            # cancellando il progetto.
        ),
    )
    # Indice per lo storico di un progetto (lista ordinata per data).
    op.create_index(
        'ix_sal_snapshot_progetto_id', 'sal_snapshot', ['progetto_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_sal_snapshot_progetto_id', table_name='sal_snapshot')
    op.drop_table('sal_snapshot')
