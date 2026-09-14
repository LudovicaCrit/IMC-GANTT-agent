"""blocchi_ore.fonte: tolto 'ia' dal CHECK (manuale | storico)

Consuntivazione a ore — micro-passo di chiusura.

PERCHÉ
──────
La migration e9f0a1b2c3d4 ammetteva tre fonti: manuale, ia, storico. 'ia'
immaginava l'assistente che scrive ore-consuntivo come proposte. Stabilito
invece che l'IA NON scrive mai in `blocchi_ore`: lavora sul piano (GANTT,
assegnazioni), e le ore le dichiara solo chi le ha lavorate. Un valore che non
avrà mai uso lascerebbe il vincolo a dire il falso — e lascerebbe aperta una
porta che nessuno deve attraversare.

LA GUARDIA
──────────
Prima di stringere il CHECK si contano i blocchi con fonte='ia'. Devono essere
zero: un CHECK più stretto li renderebbe invalidi, e Postgres rifiuterebbe
l'ADD CONSTRAINT o — peggio, con NOT VALID — li lascerebbe lì fuori regola. Se
ce ne sono la migration si FERMA e li elenca: vanno decisi a mano, non forzati.

Il CHECK si ricrea VALIDATO (niente NOT VALID): Postgres riverifica tutte le
righe esistenti, quindi i blocchi 'storico' già presenti sono provati conformi
dal database stesso, non da un conteggio fatto qui.

Dichiarato anche in `models.py` (`FONTI_BLOCCO_ORE`), perché DB e ORM dicano la
stessa cosa e un `create_all` crei il vincolo già ristretto.
"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f8"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

CK = "ck_blocchi_ore_fonte"


def upgrade() -> None:
    conn = op.get_bind()
    n_ia = conn.execute(sa.text("SELECT count(*) FROM blocchi_ore WHERE fonte = 'ia'")).scalar()
    print(f"guardia: {n_ia} blocchi con fonte='ia'")
    if n_ia:
        esempi = conn.execute(sa.text(
            "SELECT id, dipendente_id, giorno, task_id FROM blocchi_ore "
            "WHERE fonte = 'ia' ORDER BY id LIMIT 10"
        )).fetchall()
        raise RuntimeError(
            f"CHECK NON RISTRETTO: {n_ia} blocchi hanno fonte='ia' e diventerebbero "
            f"invalidi -> {', '.join(f'#{r[0]} {r[1]} {r[2]} {r[3]}' for r in esempi)}. "
            f"Decidere a mano cosa farne, poi rieseguire."
        )

    op.drop_constraint(CK, "blocchi_ore", type_="check")
    op.create_check_constraint(CK, "blocchi_ore", "fonte IN ('manuale', 'storico')")
    print("✅ ck_blocchi_ore_fonte ristretto a ('manuale', 'storico')")


def downgrade() -> None:
    op.drop_constraint(CK, "blocchi_ore", type_="check")
    op.create_check_constraint(CK, "blocchi_ore", "fonte IN ('manuale', 'ia', 'storico')")
    print("⚠ ck_blocchi_ore_fonte riportato a ('manuale', 'ia', 'storico')")
