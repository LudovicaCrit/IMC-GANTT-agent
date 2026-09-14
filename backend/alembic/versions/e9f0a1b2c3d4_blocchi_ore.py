"""blocchi_ore: le ore consuntivate per persona, giorno e unità di lavoro

Consuntivazione a ore, passo 1 — sotto-passo 1 di 3 (tabella; poi la vista
`ore_settimanali`, poi la migrazione dello storico).

PERCHÉ UNA TABELLA NUOVA
─────────────────────────
Fino a qui le ore stavano in `consuntivi.ore_dichiarate`, una per (task,
dipendente, settimana), e in modalità cursore erano DERIVATE da una percentuale
contro una baseline. La consuntivazione diventa a ore dichiarate per giorno:
«lunedì 2h su X + 3h su Y». Serve una grana più fine della settimana, e le ore
diventano fatti invece che differenze calcolate.

`blocchi_ore` è la sorgente unica. Le somme settimanali le darà una VISTA
(migration successiva), non una colonna tenuta allineata dal motore.

I VINCOLI, e cosa garantiscono
───────────────────────────────
- ck_blocchi_ore_positive (ore > 0): nessuna riga a zero ore. «Nessuna ora» è
  l'assenza della riga.
- ck_blocchi_ore_fonte: manuale | ia | storico.
- fk_blocchi_ore_sottotask_task, FK COMPOSTA (sottotask_id, task_id) →
  sottotask(id, task_id): un blocco su un pezzo porta il task a cui il pezzo
  appartiene. Richiede sul bersaglio la coppia UNIQUE uq_sottotask_id_task.
- uq_blocchi_ore (dipendente_id, giorno, task_id, sottotask_id) NULLS NOT
  DISTINCT: un blocco per persona/giorno/unità, anche quando l'unità è il task
  (sottotask_id NULL). Richiede Postgres 15+.

Tutti dichiarati ANCHE in `models.py` (`__table_args__`), per la lezione dei
CHECK spariti: un `create_all` non conosce ciò che vive solo qui.

NESSUN DATO in questa migration: la tabella nasce vuota.
"""
from alembic import op
import sqlalchemy as sa

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_sottotask_id_task", "sottotask", ["id", "task_id"])

    op.create_table(
        "blocchi_ore",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dipendente_id", sa.String(length=10), nullable=False),
        sa.Column("giorno", sa.Date(), nullable=False),
        sa.Column("task_id", sa.String(length=10), nullable=False),
        sa.Column("sottotask_id", sa.Integer(), nullable=True),
        sa.Column("ore", sa.Numeric(5, 2), nullable=False),
        sa.Column("fonte", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dipendente_id"], ["dipendenti.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["sottotask_id", "task_id"], ["sottotask.id", "sottotask.task_id"],
            ondelete="CASCADE", name="fk_blocchi_ore_sottotask_task",
        ),
        sa.UniqueConstraint(
            "dipendente_id", "giorno", "task_id", "sottotask_id",
            name="uq_blocchi_ore", postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("ore > 0", name="ck_blocchi_ore_positive"),
        sa.CheckConstraint("fonte IN ('manuale', 'ia', 'storico')", name="ck_blocchi_ore_fonte"),
    )
    op.create_index("ix_blocchi_ore_task_id", "blocchi_ore", ["task_id"])
    op.create_index("ix_blocchi_ore_sottotask_id", "blocchi_ore", ["sottotask_id"])
    print("✅ blocchi_ore creata (vuota) + uq_sottotask_id_task")


def downgrade() -> None:
    op.drop_index("ix_blocchi_ore_sottotask_id", table_name="blocchi_ore")
    op.drop_index("ix_blocchi_ore_task_id", table_name="blocchi_ore")
    op.drop_table("blocchi_ore")
    op.drop_constraint("uq_sottotask_id_task", "sottotask", type_="unique")
