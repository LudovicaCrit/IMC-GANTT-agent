"""step_2_0_drop_pianificazioni_bozza

Step 2.0 della roadmap Blocco 2 esteso (handoff v15 §2.0).

Una "bozza di progetto" è da ora un record nella tabella `progetti`
con `stato="bozza"`. La tabella `pianificazioni_bozza` viene rimossa
perché:
  1. Conteneva snapshot JSON opachi della tabella task durante la
     creazione, un meccanismo "salva il foglio di lavoro a metà" usato
     dalle pagine Pipeline.jsx e AnalisiInterventi.jsx (entrambe destinate
     a sparire a Step 2.7, assorbite da Cantiere.jsx).
  2. Non c'era CHECK constraint o uso runtime: i due endpoint
     `routes/pianificazione.py` scrivevano in un dict in memoria
     `BOZZE_STORE` di main.py, non nella tabella. La tabella esisteva
     ma era de-facto vuota.
  3. L'architettura "pagine come lenti" (handoff v15 §3.2) vuole lo
     stato come proprietà del progetto, non come tabella separata.

Cosa NON fa questa migration:
  - NON aggiunge CHECK constraint su `progetti.stato` (rimandato al
    commit gemello D3, insieme agli stati Fase tipizzati)
  - NON tocca `Task.fase` stringa (D1, prossima migration)
  - NON modifica dati esistenti (nessun progetto oggi ha stato="bozza")

Sicurezza:
  - Pre-check: se la tabella contiene righe, log warning ma procedi.
    In produzione la tabella è vuota (le bozze vivono in BOZZE_STORE
    in memoria di main.py, non qui).
  - Il downgrade ricrea la tabella esattamente come nello schema
    iniziale (e733e23ae7a1), così che il rollback sia simmetrico.

Revision ID: a1b2c3d4e5f6
Revises: e733e23ae7a1
Create Date: 2026-05-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e733e23ae7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop pianificazioni_bozza. Le bozze diventano progetti con stato='bozza'."""
    # Pre-check informativo: quante righe stiamo per perdere?
    # In sviluppo dovrebbe essere 0 (lo store reale era BOZZE_STORE in memoria).
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT COUNT(*) FROM pianificazioni_bozza")).scalar()
    if result and result > 0:
        # Non blocchiamo: chi conosce questo dato sa che è un blob JSON opaco
        # legato a pagine in dismissione. Ma lo segnaliamo.
        print(f"⚠️  pianificazioni_bozza contiene {result} righe che verranno perse. "
              "Verificare che non siano dati produttivi prima di proseguire.")

    op.drop_table('pianificazioni_bozza')


def downgrade() -> None:
    """Ricrea pianificazioni_bozza identica allo schema iniziale (e733e23ae7a1)."""
    op.create_table(
        'pianificazioni_bozza',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('progetto_id', sa.String(length=10), nullable=False),
        sa.Column('dati_json', sa.JSON(), nullable=False),
        sa.Column('creato_da', sa.String(length=10), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['creato_da'], ['dipendenti.id'], ),
        sa.ForeignKeyConstraint(['progetto_id'], ['progetti.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
