"""step_2_1_d1_task_fase_id_not_null_drop_fase_string

Step 2.1 D1 (handoff v15 §2.1).

Cambia il modello Task per eliminare la doppia rappresentazione fase:
prima esistevano `Task.fase_id` (FK) + `Task.fase` (stringa "legacy"); ora
solo `fase_id` resta, ed è NOT NULL.

Pre-condizione verificata (vedi diagnostico_d1.py del 13 mag 2026):
  - Tutti i 70 task hanno già `fase_id` valorizzato
  - La stringa `Task.fase` è perfettamente coerente con `fase_rel.nome`
  - Nessun task orfano

Quindi:
  - upgrade: rende `fase_id` NOT NULL, droppa colonna `fase`
  - downgrade: riaggiunge `fase` (nullable), ripopola dalla relazione,
    rende `fase_id` di nuovo nullable

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-13 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rende fase_id NOT NULL e droppa colonna fase legacy."""
    conn = op.get_bind()

    # Safety check: nessun task deve avere fase_id NULL
    null_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM task WHERE fase_id IS NULL")
    ).scalar()
    if null_count and null_count > 0:
        raise RuntimeError(
            f"Migration D1 abortita: {null_count} task hanno fase_id NULL. "
            "Lanciare diagnostico_d1.py per analisi e risolverli prima di proseguire."
        )

    # 1. fase_id NOT NULL
    op.alter_column('task', 'fase_id', existing_type=sa.Integer(), nullable=False)

    # 2. drop colonna fase stringa
    op.drop_column('task', 'fase')


def downgrade() -> None:
    """Ripristina la doppia rappresentazione fase (rollback)."""
    # 1. Riaggiungi colonna fase stringa (nullable)
    op.add_column('task', sa.Column('fase', sa.String(length=60), nullable=True))

    # 2. Ripopola dalla relazione fase_id → fasi.nome
    op.execute(
        "UPDATE task SET fase = fasi.nome "
        "FROM fasi WHERE task.fase_id = fasi.id"
    )

    # 3. Rendi fase_id di nuovo nullable
    op.alter_column('task', 'fase_id', existing_type=sa.Integer(), nullable=True)
