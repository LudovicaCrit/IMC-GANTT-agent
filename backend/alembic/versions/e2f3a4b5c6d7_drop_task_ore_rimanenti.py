"""task: via `ore_rimanenti` — una copia che non ha mai detto niente di suo (5.6)

`Task.ore_rimanenti` doveva essere «quante ore mancano»: `ore_pianificate`
meno il consumato. Non è mai stata aggiornata da nessuno dopo il seed — che la
scriveva uguale a `ore_pianificate` — e non è mai stata letta da nessuno. Chi
mostra «quanto resta» lo calcola al volo dalla vista: `routes/fasi.py`
(`ore_vendute − ore_consumate`) e `task_settimana_dipendente`
(`ore_pianificate − consumato totale`). Il seed ha smesso di scriverla al 5.5.

LA GUARDIA — RIDONDANZA, non vuoto
──────────────────────────────────
Una guardia-vuoto qui fallirebbe: la colonna HA valori su tutte le righe, messi
dal seed. Ma sono una copia esatta di `ore_pianificate`, quindi non c'è
informazione da perdere — ed è esattamente questo che la guardia verifica:

    quante righe hanno `ore_rimanenti` VALORIZZATA e DIVERSA da
    `ore_pianificate`?

Zero significa «questa colonna non sa niente che non sia scritto altrove»: si
può droppare. Diverso da zero significa che QUALCUNO l'ha aggiornata davvero —
una decommissione andata a metà, un job, una mano umana — e allora quei valori
sono un dato e la migration si ferma elencandoli.

Il NULL non conta come divergenza, ed è il caso di un database seminato dopo il
passo 5.5: il seed ha smesso di scrivere la colonna, quindi lì è NULL ovunque.
Una colonna vuota non sa niente esattamente come una colonna-copia — pretendere
l'uguaglianza con `ore_pianificate` bloccherebbe il drop proprio sui database
più puliti.

È una guardia più forte del vuoto, non più debole: prova che il contenuto è
derivabile, non solo che è poco.

IL DOWNGRADE ricrea la colonna e la riempie da `ore_pianificate`, cioè
esattamente com'era: la copia torna copia.
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

TABELLA = "task"
COLONNA = "ore_rimanenti"
GEMELLA = "ore_pianificate"


def upgrade() -> None:
    conn = op.get_bind()
    diverse = conn.execute(sa.text(
        f"SELECT count(*) FROM {TABELLA} "
        f"WHERE {COLONNA} IS NOT NULL AND {COLONNA} IS DISTINCT FROM {GEMELLA}")).scalar()
    totali = conn.execute(sa.text(f"SELECT count(*) FROM {TABELLA}")).scalar()
    valorizzate = conn.execute(sa.text(
        f"SELECT count(*) FROM {TABELLA} WHERE {COLONNA} IS NOT NULL")).scalar()
    print(f"guardia: {TABELLA}.{COLONNA} → {valorizzate} righe valorizzate su {totali}, "
          f"di cui {diverse} diverse da {GEMELLA}")
    if diverse:
        esempi = conn.execute(sa.text(
            f"SELECT id, nome, {COLONNA}, {GEMELLA} FROM {TABELLA} "
            f"WHERE {COLONNA} IS NOT NULL AND {COLONNA} IS DISTINCT FROM {GEMELLA} "
            f"ORDER BY id LIMIT 10")).fetchall()
        raise RuntimeError(
            f"DROP NON ESEGUITO: {TABELLA}.{COLONNA} porta {diverse} valori che NON "
            f"sono la copia di {GEMELLA}, quindi dicono qualcosa di proprio → "
            f"{', '.join(f'{r[0]} «{r[1]}» {COLONNA}={r[2]} {GEMELLA}={r[3]}' for r in esempi)}. "
            f"Capire chi li ha scritti prima di buttarli."
        )

    op.drop_column(TABELLA, COLONNA)
    print(f"✅ {TABELLA}: droppata {COLONNA}")


def downgrade() -> None:
    op.add_column(TABELLA, sa.Column(COLONNA, sa.Float(), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text(f"UPDATE {TABELLA} SET {COLONNA} = {GEMELLA}"))
    print(f"↩ {TABELLA}: ricreata {COLONNA} come copia di {GEMELLA}")
