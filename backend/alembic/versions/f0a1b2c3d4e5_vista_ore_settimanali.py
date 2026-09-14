"""vista ore_settimanali: somma dei blocchi per task, dipendente, settimana

Consuntivazione a ore, passo 1 — sotto-passo 2 di 3.

Sostituisce `consuntivi.ore_dichiarate` come SORGENTE delle ore settimanali. È
una vista e non una colonna: una colonna andrebbe riscritta dal motore a ogni
salvataggio e prima o poi divergerebbe dai blocchi; una vista non può.

`settimana` = lunedì ISO di `giorno` (`date_trunc('week')` in Postgres parte dal
lunedì), la stessa normalizzazione di `_lunedi` in data_db_impl.

I lettori NON leggono ancora la vista: lo spostamento degli 11 lettori di
`ore_dichiarate` è il passo 2. Qui la vista nasce e basta.

Dichiarata anche in `models.py` (`VISTA_ORE_SETTIMANALI`, via eventi DDL sulla
tabella) perché sopravviva a un `create_all`. Il testo è identico.
"""
from alembic import op

revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE VIEW ore_settimanali AS
SELECT task_id,
       dipendente_id,
       (date_trunc('week', giorno))::date AS settimana,
       sum(ore) AS ore
FROM blocchi_ore
GROUP BY task_id, dipendente_id, (date_trunc('week', giorno))::date
""")
    print("✅ vista ore_settimanali creata")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ore_settimanali")
