"""consuntivi: via `modalita`, `percentuale`, `ore_effettive` (passo 5.6)

Le tre colonne sempre vuote della tabella-consuntivo.

  modalita       non è MAI stata scritta da nessuno: zero occorrenze in tutto
                 il codice, zero valori in database. Nata con lo schema
                 iniziale (e733e23ae7a1) per distinguere sede/remoto, non ha
                 mai avuto né una scrittura né un lettore.
  percentuale    l'avanzamento del cursore sul TASK come unità di lavoro
                 (Step 4). Gemella di quella sui pezzi, droppata dalla
                 migration precedente.
  ore_effettive  le ore scritte a mano quando l'avanzamento non le catturava.

Tutte e tre sono uscite dai payload al passo 5.5 e nessuno le scrive dal 5.4.

LA GUARDIA — VUOTO
──────────────────
Conteggio dei non-NULL prima del drop, zero atteso su tutte e tre. Se una
avesse dei valori la migration si ferma e li elenca: significherebbe che
qualcosa le scrive ancora, e il drop distruggerebbe dati veri.

`motivo_fermo` NON è qui: è l'unica colonna condannata di questa tabella che ha
un valore in database, ha una guardia diversa e una migration sua (la
successiva). Tenerle insieme avrebbe voluto dire una guardia che si ferma per
una colonna e lascia passare le altre — o peggio, una guardia sola allentata
fino ad accogliere il caso peggiore.

IL DOWNGRADE ricrea le tre colonne vuote, col CHECK sul range della
percentuale. La forma, non il contenuto.
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None

TABELLA = "consuntivi"
COLONNE = ("modalita", "percentuale", "ore_effettive")
CK_PCT = "ck_consuntivi_percentuale"


def upgrade() -> None:
    conn = op.get_bind()
    for col in COLONNE:
        n = conn.execute(sa.text(
            f"SELECT count(*) FROM {TABELLA} WHERE {col} IS NOT NULL")).scalar()
        print(f"guardia: {TABELLA}.{col} → {n} valori non-NULL")
        if n:
            esempi = conn.execute(sa.text(
                f"SELECT id, task_id, dipendente_id, settimana, {col} FROM {TABELLA} "
                f"WHERE {col} IS NOT NULL ORDER BY id LIMIT 10")).fetchall()
            raise RuntimeError(
                f"DROP NON ESEGUITO: {TABELLA}.{col} ha {n} valori non-NULL, "
                f"che il drop distruggerebbe → "
                f"{', '.join(f'#{r[0]} {r[1]}/{r[2]} {r[3]} = {r[4]!r}' for r in esempi)}. "
                f"Qualcosa la scrive ancora: capire cosa, poi rieseguire."
            )

    for col in COLONNE:
        op.drop_column(TABELLA, col)
    print(f"✅ {TABELLA}: droppate {', '.join(COLONNE)} (col CHECK {CK_PCT})")


def downgrade() -> None:
    op.add_column(TABELLA, sa.Column("modalita", sa.String(length=10), nullable=True))
    op.add_column(TABELLA, sa.Column("percentuale", sa.Integer(), nullable=True))
    op.add_column(TABELLA, sa.Column("ore_effettive", sa.Float(), nullable=True))
    op.create_check_constraint(
        CK_PCT, TABELLA,
        "percentuale IS NULL OR (percentuale >= 0 AND percentuale <= 100)")
    print(f"↩ {TABELLA}: ricreate modalita, percentuale, ore_effettive (vuote)")
