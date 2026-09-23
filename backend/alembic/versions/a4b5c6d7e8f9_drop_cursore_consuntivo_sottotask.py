"""consuntivo_sottotask: via `percentuale` e `ore_effettive` (passo 5.6)

Le due colonne del CURSORE sul pezzo di lavoro. `percentuale` era l'avanzamento
che il dipendente muoveva con lo slider; `ore_effettive` le ore che scriveva a
mano quando l'avanzamento non le catturava. Dalla Consuntivazione a ore le ore
si dichiarano per giorno (`blocchi_ore`) e non si derivano da nulla: il motore
che leggeva queste due colonne è uscito al passo 5.4, i campi sono usciti dai
payload al 5.5, e qui escono le colonne.

LA GUARDIA — VUOTO
──────────────────
Si contano i valori non-NULL prima del drop. Devono essere zero: sono colonne
che nessuno scrive dal 5.4 e che nessuno ha mai riempito in questo database
(`consuntivo_sottotask` è nata con lo Step 4 e lo slider non è mai stato usato
in produzione). Se ce ne fossero, vorrebbe dire che QUALCOSA le scriveva — un
percorso sfuggito al grep — e il drop butterebbe via dati veri: la migration si
ferma e li elenca, invece di distruggerli.

IL DOWNGRADE ricrea le colonne vuote, col CHECK sul range della percentuale.
Ricrea la FORMA, non il contenuto: i valori, se mai ce ne fossero stati, non
tornano. È il limite di ogni drop, ed è la ragione della guardia qui sopra.
"""
from alembic import op
import sqlalchemy as sa

revision = "a4b5c6d7e8f9"
down_revision = "a2b3c4d5e6f8"
branch_labels = None
depends_on = None

TABELLA = "consuntivo_sottotask"
COLONNE = ("percentuale", "ore_effettive")
CK_PCT = "ck_consuntivo_sottotask_percentuale"


def upgrade() -> None:
    conn = op.get_bind()
    for col in COLONNE:
        n = conn.execute(sa.text(
            f"SELECT count(*) FROM {TABELLA} WHERE {col} IS NOT NULL")).scalar()
        print(f"guardia: {TABELLA}.{col} → {n} valori non-NULL")
        if n:
            esempi = conn.execute(sa.text(
                f"SELECT id, sottotask_id, dipendente_id, settimana, {col} FROM {TABELLA} "
                f"WHERE {col} IS NOT NULL ORDER BY id LIMIT 10")).fetchall()
            raise RuntimeError(
                f"DROP NON ESEGUITO: {TABELLA}.{col} ha {n} valori non-NULL, "
                f"che il drop distruggerebbe → "
                f"{', '.join(f'#{r[0]} sott={r[1]} {r[2]} {r[3]} = {r[4]}' for r in esempi)}. "
                f"Qualcosa la scrive ancora: capire cosa, poi rieseguire."
            )

    for col in COLONNE:
        op.drop_column(TABELLA, col)
    print(f"✅ {TABELLA}: droppate {', '.join(COLONNE)} (col CHECK {CK_PCT})")


def downgrade() -> None:
    op.add_column(TABELLA, sa.Column("percentuale", sa.Integer(), nullable=True))
    op.add_column(TABELLA, sa.Column("ore_effettive", sa.Float(), nullable=True))
    op.create_check_constraint(
        CK_PCT, TABELLA,
        "percentuale IS NULL OR (percentuale >= 0 AND percentuale <= 100)")
    print(f"↩ {TABELLA}: ricreate percentuale, ore_effettive (vuote)")
