"""step_3_1_dipendenza_task

Step 3.1 — Migration #1 del Piano "3 Migration" (25/05/2026, PIANO_3_MIGRATION.md).

Sostituisce il campo `Task.predecessore` (stringa singola, tipo non registrato)
con una tabella-grafo `dipendenza_task` che modella dipendenze multiple e
tipizzate (FS/SS/FF/SF). È il prerequisito per il GANTT "fatto bene" e per
l'IA di Cantiere.

Nuova tabella `dipendenza_task`:
  - id PK
  - task_predecessore_id String(10) FK → task.id ON DELETE CASCADE
  - task_successore_id   String(10) FK → task.id ON DELETE CASCADE
  - tipo_dipendenza      String(2) NOT NULL DEFAULT 'FS', CHECK IN (FS,SS,FF,SF)
  - created_at           DateTime
  - UNIQUE (task_predecessore_id, task_successore_id)
  - CHECK (task_predecessore_id != task_successore_id)

upgrade():
  1. CREATE TABLE dipendenza_task con vincoli.
  2. Diagnostico: cerco task con predecessore non NULL/non-empty che punta a
     un id inesistente (FK orfana). Se ne trovo → RuntimeError con l'elenco.
  3. INSERT in dipendenza_task una riga per ogni task con predecessore valorizzato
     (tipo_dipendenza='FS' — è quello che il frontend assume oggi hardcoded
     in AnalisiInterventi.jsx riga 374).
  4. DROP COLUMN task.predecessore.

downgrade():
  1. Safety: se un task_successore_id compare in >1 riga (più predecessori),
     RuntimeError con l'elenco — la colonna singola non può rappresentarli.
  2. ADD COLUMN task.predecessore String(10) nullable default ''.
  3. UPDATE task SET predecessore = (task_predecessore_id corrispondente).
  4. DROP TABLE dipendenza_task.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-25 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIPI_DIPENDENZA = ("FS", "SS", "FF", "SF")


def upgrade() -> None:
    """
    1. Crea tabella dipendenza_task con FK, UNIQUE e CHECK.
    2. Diagnostico: verifica che ogni task.predecessore punti a un task esistente.
    3. Migra i dati esistenti come dipendenze tipo 'FS'.
    4. Droppa la colonna task.predecessore.
    """
    conn = op.get_bind()

    # ── 1. CREATE TABLE ────────────────────────────────────────────────
    tipi_str = ", ".join(f"'{t}'" for t in TIPI_DIPENDENZA)
    op.create_table(
        "dipendenza_task",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "task_predecessore_id",
            sa.String(length=10),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_successore_id",
            sa.String(length=10),
            sa.ForeignKey("task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tipo_dipendenza",
            sa.String(length=2),
            nullable=False,
            server_default="FS",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "task_predecessore_id",
            "task_successore_id",
            name="uq_dipendenza_task",
        ),
        sa.CheckConstraint(
            "task_predecessore_id <> task_successore_id",
            name="ck_dipendenza_task_no_self",
        ),
        sa.CheckConstraint(
            f"tipo_dipendenza IN ({tipi_str})",
            name="ck_dipendenza_task_tipo",
        ),
    )
    print("✅ Tabella dipendenza_task creata")

    # ── 2. DIAGNOSTICO: predecessori orfani ────────────────────────────
    # Verifica che ogni task.predecessore non vuoto punti a un task esistente.
    # Se ce ne sono orfani, l'INSERT in dipendenza_task violerebbe la FK.
    orfani = conn.execute(sa.text(
        """
        SELECT t.id, t.predecessore
        FROM task t
        WHERE t.predecessore IS NOT NULL
          AND t.predecessore <> ''
          AND NOT EXISTS (
              SELECT 1 FROM task tp WHERE tp.id = t.predecessore
          )
        ORDER BY t.id
        """
    )).fetchall()

    if orfani:
        descrizione = ", ".join(
            f"{r[0]}→{r[1]!r}" for r in orfani
        )
        raise RuntimeError(
            f"Migration Step 3.1 abortita: {len(orfani)} task hanno "
            f"predecessore che punta a un id inesistente (FK orfana). "
            f"Coppie (task_id → predecessore_inesistente): {descrizione}. "
            f"Sistemare a mano (UPDATE task SET predecessore = '' WHERE id IN (...)) "
            f"oppure inserire i task mancanti, e rilanciare la migration."
        )

    print("✅ Diagnostico predecessori: nessun orfano")

    # ── 3. MIGRA I DATI ─────────────────────────────────────────────────
    # Per ogni task con predecessore valorizzato, inserisci una riga
    # (task_predecessore_id = task.predecessore, task_successore_id = task.id,
    #  tipo_dipendenza = 'FS').
    risultato = conn.execute(sa.text(
        """
        INSERT INTO dipendenza_task
            (task_predecessore_id, task_successore_id, tipo_dipendenza, created_at)
        SELECT t.predecessore, t.id, 'FS', CURRENT_TIMESTAMP
        FROM task t
        WHERE t.predecessore IS NOT NULL
          AND t.predecessore <> ''
        """
    ))
    n_migrate = risultato.rowcount if risultato.rowcount is not None else 0
    print(f"✅ Migrate {n_migrate} dipendenze esistenti (tipo 'FS')")

    # ── 4. DROP COLUMN ──────────────────────────────────────────────────
    op.drop_column("task", "predecessore")
    print("✅ Colonna task.predecessore droppata")


def downgrade() -> None:
    """
    Rollback:
    1. Safety: se ci sono task con >1 predecessore non si può tornare alla
       colonna singola → RuntimeError.
    2. Ricrea colonna task.predecessore.
    3. Copia dati da dipendenza_task indietro nella colonna.
    4. Droppa tabella dipendenza_task.
    """
    conn = op.get_bind()

    # ── 1. SAFETY: task con multipli predecessori ──────────────────────
    multipli = conn.execute(sa.text(
        """
        SELECT task_successore_id, COUNT(*) as n
        FROM dipendenza_task
        GROUP BY task_successore_id
        HAVING COUNT(*) > 1
        ORDER BY task_successore_id
        """
    )).fetchall()

    if multipli:
        descrizione = ", ".join(
            f"{r[0]} ({r[1]} predecessori)" for r in multipli
        )
        raise RuntimeError(
            f"Downgrade Step 3.1 abortito: {len(multipli)} task hanno più di "
            f"un predecessore — la colonna singola Task.predecessore non può "
            f"rappresentarli. Task: {descrizione}. "
            f"Risolvere a mano (cancellare le righe in eccesso da dipendenza_task) "
            f"prima del downgrade — NON ne scelgo uno a caso in silenzio."
        )

    # ── 2. RICREA COLONNA ──────────────────────────────────────────────
    op.add_column(
        "task",
        sa.Column("predecessore", sa.String(length=10), nullable=True, server_default=""),
    )
    print("✅ Colonna task.predecessore ricreata")

    # ── 3. COPIA DATI INDIETRO ─────────────────────────────────────────
    risultato = conn.execute(sa.text(
        """
        UPDATE task
        SET predecessore = dt.task_predecessore_id
        FROM dipendenza_task dt
        WHERE task.id = dt.task_successore_id
        """
    ))
    n_riportate = risultato.rowcount if risultato.rowcount is not None else 0
    print(f"✅ Riportate {n_riportate} dipendenze nella colonna task.predecessore")

    # ── 4. DROP TABLE ──────────────────────────────────────────────────
    op.drop_table("dipendenza_task")
    print("✅ Tabella dipendenza_task droppata")
