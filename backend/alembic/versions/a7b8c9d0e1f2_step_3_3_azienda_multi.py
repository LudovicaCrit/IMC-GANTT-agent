"""step_3_3_azienda_multi_struttura_gruppo

Step 3.3 (DESIGN_SEED_Innovation_Plaza, 26/06/2026). Introduce la struttura
multi-azienda del Gruppo IMC a livello di SCHEMA. Questa migration NON tocca
i dati del seed (data_legacy.py/seed.py): è solo il giro di schema.

CONTESTO
--------
Il Gruppo IMC ha più s.r.l.; nel seed modelliamo le 2 operative vive
(IMC-Improve, Innovation Plaza). Serve poter dire a quale azienda appartiene
una persona e (quando ha senso) un progetto. Vedi DESIGN_SEED_Innovation_Plaza
§1 per le decisioni congelate.

COSA FA
-------
1. Nuova tabella `azienda` (id, nome). Struttura estensibile: un ramo futuro
   = una riga in più, non una migration. `nome` UNIQUE: rende idempotenti i
   2 insert del seed e serve al backfill qui sotto per il lookup.

2. `dipendenti.azienda_id` -> FK a azienda.id, **NOT NULL** (ogni persona
   appartiene a un'azienda).

3. `progetti.azienda_id` -> FK a azienda.id, **nullable** (obbligatoria per
   commerciali/bandi, ma garantita nel seed / futuro CHECK condizionato; per
   ora nullable perche' gli interni restano legittimamente NULL = attivita'
   trasversale).

4. `progetti.area` -> String nullable. Valorizzato SOLO per i bandi Innovation
   ("PA" / "Imprese"); NULL altrove. Nessun CHECK qui: i valori ammessi li
   garantisce il seed (decisione DESIGN §1.3; un CHECK condizionato e' candidato
   futuro come per la tipologia).

SAFETY (pattern debito silenzioso, come f6a7b8c9d0e1)
-----------------------------------------------------
Il punto delicato e' il NOT NULL su `dipendenti.azienda_id`, perche' sul DB
live la tabella e' gia' popolata. La migration:
  - aggiunge la colonna NULLABLE;
  - SOLO se esistono gia' dipendenti (DB live), crea una riga azienda di
    backfill "IMC-Improve" (idempotente via UNIQUE) e ci aggancia tutti i
    dipendenti con azienda_id NULL;
  - verifica che non restino NULL (altrimenti RuntimeError, da risolvere a mano);
  - solo allora impone il NOT NULL.
Su un re-seed da zero (DROP SCHEMA + upgrade head + seed) la tabella e' VUOTA:
il ramo di backfill non scatta e i 2 insert azienda li fa il seed. Coerente con
la regola "le migration patchano il DB live, non la sorgente del seed".

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_DIP = 'fk_dipendenti_azienda_id_azienda'
FK_PROG = 'fk_progetti_azienda_id_azienda'
AZIENDA_BACKFILL = 'IMC-Improve'


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Tabella azienda -------------------------------------------------
    op.create_table(
        'azienda',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.UniqueConstraint('nome', name='uq_azienda_nome'),
    )

    # 2) progetti.area (nullable, nessun CHECK) --------------------------
    op.add_column('progetti', sa.Column('area', sa.String(length=20), nullable=True))

    # 3) progetti.azienda_id (nullable) ----------------------------------
    op.add_column('progetti', sa.Column('azienda_id', sa.Integer(), nullable=True))
    op.create_foreign_key(FK_PROG, 'progetti', 'azienda', ['azienda_id'], ['id'])

    # 4) dipendenti.azienda_id (nullable -> backfill -> NOT NULL) --------
    op.add_column('dipendenti', sa.Column('azienda_id', sa.Integer(), nullable=True))
    op.create_foreign_key(FK_DIP, 'dipendenti', 'azienda', ['azienda_id'], ['id'])

    # Backfill SOLO su DB gia' popolato (live). Su re-seed da zero la
    # tabella e' vuota e questo ramo non scatta: gli insert azienda li fa il seed.
    n_dip = conn.execute(sa.text("SELECT COUNT(*) FROM dipendenti")).scalar()
    if n_dip:
        az_id = conn.execute(
            sa.text("SELECT id FROM azienda WHERE nome = :n"),
            {"n": AZIENDA_BACKFILL},
        ).scalar()
        if az_id is None:
            az_id = conn.execute(
                sa.text("INSERT INTO azienda (nome) VALUES (:n) RETURNING id"),
                {"n": AZIENDA_BACKFILL},
            ).scalar()
        conn.execute(
            sa.text("UPDATE dipendenti SET azienda_id = :a WHERE azienda_id IS NULL"),
            {"a": az_id},
        )

    # Verifica: nessun dipendente senza azienda prima di imporre il vincolo.
    residui = conn.execute(
        sa.text("SELECT COUNT(*) FROM dipendenti WHERE azienda_id IS NULL")
    ).scalar()
    if residui and residui > 0:
        raise RuntimeError(
            f"Migration a7b8c9d0e1f2 abortita: {residui} dipendenti hanno "
            f"azienda_id NULL dopo il backfill. Assegnarli a un'azienda a mano "
            f"prima di riapplicare la migration."
        )

    op.alter_column('dipendenti', 'azienda_id', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    # Simmetrico, ordine inverso. NON conserva i dati delle FK: la struttura
    # multi-azienda viene rimossa per intero.
    op.drop_constraint(FK_DIP, 'dipendenti', type_='foreignkey')
    op.drop_column('dipendenti', 'azienda_id')

    op.drop_constraint(FK_PROG, 'progetti', type_='foreignkey')
    op.drop_column('progetti', 'azienda_id')

    op.drop_column('progetti', 'area')

    op.drop_table('azienda')
